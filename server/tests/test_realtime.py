"""Live events over Server-Sent Events, tested against a real HTTP server (the in-process test client cannot stream)."""
import json
import logging
import threading
import time

import requests
from werkzeug.serving import make_server

from studysync.realtime import QUEUE_SIZE, Hub
from .base import ApiTestCase


logging.getLogger("werkzeug").setLevel(logging.ERROR)  # keep test output readable


class Stream:
    """A live connection that collects events in a background thread so tests can wait for them."""

    def __init__(self, base, token):
        self.events, self.ended = [], threading.Event()
        self.response = requests.get(f"{base}/api/stream", headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=10)
        self.status = self.response.status_code
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self):
        event = None
        try:
            for line in self.response.iter_lines(decode_unicode=True):
                if line is None or line.startswith(":"):
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:") and event:
                    self.events.append((event, json.loads(line[5:])))
                    event = None
        except Exception:
            pass
        self.ended.set()

    def wait_for(self, event_type, timeout=3, match=lambda data: True):
        deadline = time.time() + timeout
        while time.time() < deadline:
            for name, data in list(self.events):
                if name == event_type and match(data):
                    return data
            time.sleep(0.02)
        return None

    def types(self):
        return [name for name, _ in self.events]

    def close(self):
        self.response.close()


class LiveCase(ApiTestCase):
    config = {"SSE_HEARTBEAT_SECONDS": 0.2}

    def setUp(self):
        super().setUp()
        self.server = make_server("127.0.0.1", 0, self.app, threaded=True)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.streams = []

    def tearDown(self):
        for s in self.streams:
            s.close()
        self.server.shutdown()
        super().tearDown()

    def stream(self, actor):
        s = Stream(self.base, actor.token)
        self.streams.append(s)
        return s


class StreamTests(LiveCase):
    def test_stream_needs_a_token(self):
        self.assertEqual(requests.get(f"{self.base}/api/stream", timeout=5).status_code, 401)

    def test_connection_starts_with_a_ready_event(self):
        a = self.actor()
        s = self.stream(a)
        self.assertEqual(s.wait_for("ready"), {"userId": a.id})
        self.assertEqual(s.response.headers["Content-Type"], "text/event-stream; charset=utf-8")

    def test_members_get_a_notification_and_a_refresh_hint_when_someone_shares(self):
        owner, member = self.actor("Priya Nair"), self.actor("Sam Mathew")
        g = self.group(owner)
        self.joined(g, member)
        owner_stream, member_stream = self.stream(owner), self.stream(member)
        owner_stream.wait_for("ready"); member_stream.wait_for("ready")
        self.resource(member, g, "Live resource")
        note = owner_stream.wait_for("notification")
        self.assertIn("Sam Mathew shared a new resource", note["message"])
        self.assertFalse(note["isRead"])
        self.assertEqual(owner_stream.wait_for("group.updated"), {"groupId": g["id"], "kind": "resources"})
        # the notification pushed live is the same row the REST API returns
        stored = owner.get("/api/notifications").get_json()["data"]
        self.assertIn(note["id"], [n["id"] for n in stored])
        time.sleep(0.5)
        self.assertEqual(member_stream.types(), ["ready"])  # the person who acted hears nothing about their own action

    def test_people_outside_the_group_get_nothing(self):
        owner, member, outsider = self.actor(), self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(outsider)
        s.wait_for("ready")
        self.resource(member, g)
        self.post_(member, g)
        time.sleep(0.5)
        self.assertEqual(s.types(), ["ready"])

    def test_failed_requests_send_no_events(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(owner)
        s.wait_for("ready")
        res = member.post(f"/api/groups/{g['id']}/resources", json={"title": "ab", "type": "link", "url": "javascript:x"})
        self.assertEqual(res.status_code, 422)
        time.sleep(0.5)
        self.assertEqual(s.types(), ["ready"])

    def test_a_change_that_is_rolled_back_never_produces_live_events(self):
        """Events are queued while the transaction is still open. If it fails afterwards, nobody may hear about a change that never happened."""
        from unittest import mock
        from studysync.services import content

        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(owner)
        s.wait_for("ready")
        real_announce = content.announce

        def announce_then_fail(*args, **kwargs):
            real_announce(*args, **kwargs)  # the notification and the group event are both queued by now
            raise RuntimeError("database error right before commit")

        with mock.patch.object(content, "announce", side_effect=announce_then_fail), self.assertLogs("studysync", level="ERROR"):
            res = member.post(f"/api/groups/{g['id']}/resources", json={"title": "Never saved", "type": "link", "url": "https://example.com/x", "tags": []})
        self.assertEqual(res.status_code, 500)
        time.sleep(0.5)
        self.assertEqual(s.types(), ["ready"])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM resources")[0][0], 0)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM notifications WHERE type = 'resource'")[0][0], 0)

    def test_events_arrive_after_the_data_is_saved(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(owner)
        s.wait_for("ready")
        r = self.resource(member, g, "Visible immediately")
        s.wait_for("group.updated")
        titles = [x["title"] for x in owner.get(f"/api/groups/{g['id']}/resources").get_json()["data"]]
        self.assertIn("Visible immediately", titles)

    def test_each_kind_of_change_is_announced(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(member)
        s.wait_for("ready")
        gid = g["id"]
        p = self.post_(owner, g)
        self.assertEqual(s.wait_for("group.updated", match=lambda d: d["kind"] == "posts")["postId"], p["id"])
        sess = self.session(owner, g)
        self.assertTrue(s.wait_for("group.updated", match=lambda d: d["kind"] == "sessions"))
        s.events.clear()
        owner.put(f"/api/sessions/{sess['id']}/rsvp", json={"status": "maybe"})
        self.assertTrue(s.wait_for("group.updated", match=lambda d: d["kind"] == "sessions"))
        owner.patch(f"/api/groups/{gid}/members/{member.id}", json={"role": "moderator"})
        self.assertTrue(s.wait_for("group.updated", match=lambda d: d["kind"] == "members"))
        owner.delete(f"/api/groups/{gid}")
        self.assertTrue(s.wait_for("group.updated", match=lambda d: d["kind"] == "deleted"))

    def test_a_removed_member_is_told_too(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.stream(member)
        s.wait_for("ready")
        owner.delete(f"/api/groups/{g['id']}/members/{member.id}")
        self.assertTrue(s.wait_for("group.updated", match=lambda d: d["kind"] == "members"))


class LifecycleTests(LiveCase):
    def test_stream_closes_when_the_access_token_expires(self):
        self.app.config["ACCESS_TOKEN_MINUTES"] = 0.03  # about 2 seconds
        a = self.actor()
        s = self.stream(a)
        self.assertTrue(s.ended.wait(8), "the stream should end by itself")
        self.assertIn("token-expired", s.types())

    def test_open_connections_per_account_are_limited(self):
        self.app.config["SSE_MAX_STREAMS_PER_USER"] = 2
        a = self.actor()
        first, second = self.stream(a), self.stream(a)
        self.assertEqual((first.status, second.status), (200, 200))
        third = self.stream(a)
        self.assertEqual(third.status, 429)

    def test_disconnecting_frees_the_slot(self):
        hub = self.app.extensions["hub"]
        a = self.actor()
        s = self.stream(a)
        s.wait_for("ready")
        self.assertEqual(hub.count(a.id), 1)
        s.close()
        deadline = time.time() + 5
        while time.time() < deadline and hub.count(a.id):
            time.sleep(0.05)
        self.assertEqual(hub.count(a.id), 0)


class HubTests(ApiTestCase):
    def test_slow_client_gets_a_resync_instead_of_unbounded_memory(self):
        hub = Hub()
        sub = hub.subscribe("u1", 5)
        for i in range(QUEUE_SIZE + 5):
            hub.publish(["u1"], "group.updated", {"i": i})
        first = sub.queue.get_nowait()
        self.assertEqual(first[1], "resync")
        self.assertLess(sub.queue.qsize(), QUEUE_SIZE)

    def test_publish_reaches_only_the_named_users(self):
        hub = Hub()
        a, b = hub.subscribe("a", 5), hub.subscribe("b", 5)
        hub.publish(["a"], "x", {})
        self.assertEqual(a.queue.qsize(), 1)
        self.assertEqual(b.queue.qsize(), 0)
