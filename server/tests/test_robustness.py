"""Bug-hunting tests: odd inputs, races and data-integrity cases that ordinary happy-path tests do not reach.

Each test names the failure it guards against. Several of these failed before the Week 5 fixes (see logs/bugs-before-fix.txt
and docs/DEBUGGING.md); they now stay in the suite as regression tests.
"""
import threading
from unittest import mock

from .base import PASSWORD, ApiTestCase


class HostileInputTests(ApiTestCase):
    def test_deeply_nested_json_is_a_400_not_a_crash(self):
        c = self.app.test_client()
        body = "[" * 60000 + "]" * 60000
        res = c.post("/api/auth/login", data=body, content_type="application/json")
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.get_json()["success"])

    def test_huge_numbers_in_query_parameters_are_rejected_cleanly(self):
        a = self.actor()
        res = a.get("/api/groups?page=" + "9" * 6000)
        self.assertEqual(res.status_code, 422)

    def test_a_giant_token_is_just_a_401(self):
        res = self.app.test_client().get("/api/users/me", headers={"Authorization": "Bearer " + "a" * 200_000})
        self.assertEqual(res.status_code, 401)

    def test_session_dates_outside_a_sane_range_are_a_422_not_a_500(self):
        a = self.actor()
        g = self.group(a)
        for when in ("9999-12-31T23:59:59-05:00", "9999-12-31T23:59:59Z", "0001-01-01T00:00:00+14:00", "2300-01-01T00:00:00Z"):
            res = a.post(f"/api/groups/{g['id']}/sessions", json={"title": "Far away", "startsAt": when, "durationMin": 60})
            self.assertEqual(res.status_code, 422, when)
            self.assertIn("startsAt", res.get_json()["errors"])

    def test_names_made_only_of_invisible_characters_are_rejected(self):
        a = self.actor()
        for sneaky in ("\u200b\u200b\u200b\u200b", "\u200d\u2060\u200c\ufeff", "   \u200b   "):
            res = a.post("/api/groups", json={"name": sneaky, "description": "Weekly problem solving.", "subject": "Networks", "visibility": "public"})
            self.assertEqual(res.status_code, 422, repr(sneaky))
            self.assertIn("name", res.get_json()["errors"])

    def test_single_line_fields_reject_control_characters(self):
        c = self.app.test_client()
        for field, value in (("name", "Alex\nRao"), ("name", "Alex\x00Rao"), ("email", "a\x00b@example.com")):
            body = {"name": "Alex Rao", "email": "ok@example.com", "password": PASSWORD, field: value}
            self.assertEqual(c.post("/api/auth/register", json=body).status_code, 422, (field, value))

    def test_look_alike_unicode_emails_cannot_create_a_second_account(self):
        c = self.app.test_client()
        first = c.post("/api/auth/register", json={"name": "Zoe Reed", "email": "zo\u00e9@example.com", "password": PASSWORD})  # precomposed e-acute
        second = c.post("/api/auth/register", json={"name": "Zoe Imposter", "email": "zoe\u0301@example.com", "password": PASSWORD})  # e + combining accent
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 409)
        login = c.post("/api/auth/login", json={"email": "zoe\u0301@example.com", "password": PASSWORD})
        self.assertEqual(login.status_code, 200)  # either spelling reaches the same account

    def test_emoji_and_non_latin_text_round_trips(self):
        a = self.actor("Priya Nair")
        g = a.post("/api/groups", json={"name": "\u7b97\u6cd5 Study \U0001F9EA", "description": "Discuss \u4e8c\u5206\u63a2\u7d22 and DP \U0001F468\u200d\U0001F469\u200d\U0001F467.", "subject": "Data Structures", "visibility": "public"}).get_json()["data"]
        again = a.get(f"/api/groups/{g['id']}").get_json()["data"]
        self.assertEqual(again["name"], "\u7b97\u6cd5 Study \U0001F9EA")
        self.assertIn("\U0001F468\u200d\U0001F469\u200d\U0001F467", again["description"])  # joiner characters inside emoji are kept


class RaceConditionTests(ApiTestCase):
    def test_losing_a_join_race_is_a_409_not_a_500(self):
        """Two requests pass the 'already a member?' check before either inserts. Reproduced deterministically."""
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        self.assertEqual(user.post(f"/api/groups/{g['id']}/join").status_code, 200)
        with mock.patch("studysync.services.groups.membership_of", return_value=None):  # the stale answer the losing request saw
            res = user.post(f"/api/groups/{g['id']}/join")
        self.assertEqual(res.status_code, 409)

    def test_join_by_code_race_is_a_409_too(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, user)
        with mock.patch("studysync.services.groups.membership_of", return_value=None):
            res = user.post("/api/groups/join-by-code", json={"code": g["inviteCode"]})
        self.assertEqual(res.status_code, 409)

    def test_many_simultaneous_joins_give_exactly_one_success(self):
        owner, user = self.actor(), self.actor()
        g = self.group(owner)
        results, barrier = [], threading.Barrier(8)

        def go():
            barrier.wait()
            results.append(user.post(f"/api/groups/{g['id']}/join").status_code)

        threads = [threading.Thread(target=go) for _ in range(8)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), [200] + [409] * 7, results)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM memberships WHERE group_id = ?", (g["id"],))[0][0], 2)

    def test_many_simultaneous_sign_ups_with_one_email_give_one_account(self):
        results, barrier = [], threading.Barrier(6)

        def go(i):
            barrier.wait()
            c = self.app.test_client()
            results.append(c.post("/api/auth/register", json={"name": f"Racer {i}", "email": "same@example.com", "password": PASSWORD}).status_code)

        threads = [threading.Thread(target=go, args=(i,)) for i in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(results), [201] + [409] * 5, results)

    def test_a_refresh_token_can_only_be_spent_once_even_when_two_requests_overlap(self):
        """Both overlapping requests read the token as unused. Only one may receive a successor token."""
        a = self.actor()
        raw = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        from studysync import security
        from studysync.db import one as real_one

        with self.app.test_request_context():
            stale = real_one("SELECT * FROM refresh_tokens WHERE token_hash = ?", (security._hash(raw),))
            first = security.rotate_refresh_token(raw)
            with mock.patch("studysync.security.one", return_value=stale):  # the second request still sees the unused row
                with self.assertRaises(Exception) as ctx:
                    security.rotate_refresh_token(raw)
        self.assertEqual(getattr(ctx.exception, "status", None), 401)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM refresh_tokens WHERE revoked_at IS NULL")[0][0], 1)  # exactly one live successor
        self.assertTrue(first[1])

    def test_parallel_refreshes_never_create_two_live_tokens(self):
        a = self.actor()
        raw = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        codes, barrier = [], threading.Barrier(6)

        def go():
            c = self.app.test_client()
            c.set_cookie("studysync_refresh", raw, path="/api/auth")
            barrier.wait()
            codes.append(c.post("/api/auth/refresh").status_code)

        threads = [threading.Thread(target=go) for _ in range(6)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(codes.count(200), 1, codes)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM refresh_tokens WHERE revoked_at IS NULL")[0][0], 1)


class DataIntegrityTests(ApiTestCase):
    def test_people_who_leave_a_group_stop_counting_in_its_rsvps(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.session(owner, g)
        member.put(f"/api/sessions/{s['id']}/rsvp", json={"status": "going"})
        self.assertEqual(owner.get(f"/api/groups/{g['id']}/sessions").get_json()["data"][0]["goingCount"], 2)
        member.delete(f"/api/groups/{g['id']}/leave")
        self.assertEqual(owner.get(f"/api/groups/{g['id']}/sessions").get_json()["data"][0]["goingCount"], 1)

    def test_removed_members_stop_counting_in_rsvps_and_can_rejoin_cleanly(self):
        owner, member = self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member)
        s = self.session(owner, g)
        member.put(f"/api/sessions/{s['id']}/rsvp", json={"status": "maybe"})
        owner.delete(f"/api/groups/{g['id']}/members/{member.id}")
        self.assertEqual(owner.get(f"/api/groups/{g['id']}/sessions").get_json()["data"][0]["maybeCount"], 0)
        self.joined(g, member)
        self.assertIsNone(member.get(f"/api/groups/{g['id']}/sessions").get_json()["data"][0]["myRsvp"])  # a fresh start, not a ghost answer

    def test_rsvps_of_other_groups_are_untouched_when_leaving_one(self):
        owner, member = self.actor(), self.actor()
        g1, g2 = self.group(owner, name="First group"), self.group(owner, name="Second group")
        self.joined(g1, member); self.joined(g2, member)
        s2 = self.session(owner, g2)
        member.put(f"/api/sessions/{s2['id']}/rsvp", json={"status": "going"})
        member.delete(f"/api/groups/{g1['id']}/leave")
        self.assertEqual(member.get(f"/api/groups/{g2['id']}/sessions").get_json()["data"][0]["myRsvp"], "going")


class CookieAfterLostRaceTests(ApiTestCase):
    """Fixing the refresh race created a second-order risk: the loser's 401 must not delete the winner's new cookie."""

    def test_a_lost_race_keeps_the_cookie_but_theft_clears_it(self):
        from datetime import datetime, timedelta, timezone
        from studysync.utils import to_iso

        a = self.actor()
        old = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 200)  # the winner; `old` is now spent
        loser = self.app.test_client()
        loser.set_cookie("studysync_refresh", old, path="/api/auth")
        res = loser.post("/api/auth/refresh")  # within the 10-second grace window
        self.assertEqual(res.status_code, 401)
        self.assertNotIn("Max-Age=0", res.headers.get("Set-Cookie", ""))
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 200)  # and the winner's session is untouched

        self.sql("UPDATE refresh_tokens SET revoked_at = ? WHERE revoked_at IS NOT NULL", (to_iso(datetime.now(timezone.utc) - timedelta(minutes=5)),))
        theft = self.app.test_client()
        theft.set_cookie("studysync_refresh", old, path="/api/auth")
        res = theft.post("/api/auth/refresh")  # long after rotation: treated as theft
        self.assertEqual(res.status_code, 401)
        self.assertIn("Max-Age=0", res.headers["Set-Cookie"])
