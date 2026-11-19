"""Unit tests: small pieces tested on their own, without going through HTTP."""
import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from flask import Flask

from studysync import config, errors, realtime, utils, validation
from studysync.errors import ApiError
from studysync.ratelimit import RateLimiter
from studysync.seed import DEMO_PASSWORD, seed_database
from .base import PASSWORD, ApiTestCase


class RateLimiterTests(unittest.TestCase):
    def test_allows_up_to_the_limit_then_blocks_with_a_retry_time(self):
        rl = RateLimiter()
        self.assertEqual([rl.hit("k", 3, 60, now=0.0)[0] for _ in range(3)], [True] * 3)
        allowed, retry = rl.hit("k", 3, 60, now=10.0)
        self.assertFalse(allowed)
        self.assertEqual(retry, 50)  # the oldest hit leaves the window at t=60

    def test_the_window_slides(self):
        rl = RateLimiter()
        for t in (0, 1, 2):
            rl.hit("k", 3, 10, now=float(t))
        self.assertFalse(rl.hit("k", 3, 10, now=5.0)[0])
        self.assertTrue(rl.hit("k", 3, 10, now=10.5)[0])  # the first hit has expired

    def test_keys_are_independent(self):
        rl = RateLimiter()
        rl.hit("a", 1, 60, now=0.0)
        self.assertFalse(rl.hit("a", 1, 60, now=1.0)[0])
        self.assertTrue(rl.hit("b", 1, 60, now=1.0)[0])

    def test_blocked_record_and_clear_track_failures_without_counting_checks(self):
        rl = RateLimiter()
        self.assertEqual(rl.blocked("f", 2, 60, now=0.0), (False, 0))
        rl.record("f", now=0.0); rl.record("f", now=1.0)
        blocked, retry = rl.blocked("f", 2, 60, now=2.0)
        self.assertTrue(blocked)
        self.assertEqual(retry, 58)
        rl.clear("f")
        self.assertFalse(rl.blocked("f", 2, 60, now=3.0)[0])

    def test_old_keys_are_swept_so_memory_cannot_grow_forever(self):
        rl = RateLimiter()
        for i in range(20_005):
            rl.hit(f"ip{i}", 5, 1, now=0.0)
        rl.hit("trigger", 5, 1, now=100.0)
        self.assertLess(len(rl._hits), 20_000)


class UtilsTests(unittest.TestCase):
    def test_iso_helpers(self):
        self.assertEqual(utils.to_iso(datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)), "2026-01-02T03:04:05.000Z")
        self.assertEqual(utils.to_iso(datetime(2026, 1, 2, 3, 4, 5)), "2026-01-02T03:04:05.000Z")  # naive means UTC
        self.assertEqual(utils.parse_iso("2026-01-02T03:04:05+02:00").utcoffset(), timedelta(hours=2))
        self.assertEqual(utils.parse_iso("2026-01-02T03:04:05Z").tzinfo, timezone.utc)
        self.assertEqual(utils.parse_iso("2026-01-02T03:04:05").tzinfo, timezone.utc)

    def test_parse_iso_rejects_nonsense(self):
        for bad in (None, 5, "", "   ", "not a date", "2026-13-45T00:00:00Z", ["2026-01-01"]):
            self.assertIsNone(utils.parse_iso(bad), bad)
        self.assertIsNone(utils.parse_iso("9999-12-31T23:59:59-05:00"))  # overflows when converted to UTC

    def test_like_pattern_escapes_wildcards(self):
        self.assertEqual(utils.like_pattern("50%_off\\"), "%50\\%\\_off\\\\%")

    def test_ids_have_a_prefix_and_are_unique(self):
        ids = {utils.new_id("g") for _ in range(500)}
        self.assertEqual(len(ids), 500)
        self.assertTrue(all(i.startswith("g_") and len(i) == 14 for i in ids))


class ValidationUnitTests(ApiTestCase):
    def test_text_and_visible(self):
        self.assertEqual(validation.text("  hi "), "hi")
        self.assertEqual(validation.text(None), "")
        self.assertEqual(validation.text(["x"]), "")
        self.assertEqual(validation.visible("a\u200bb\x00c"), "abc")
        self.assertEqual(validation.visible("\u200b \ufeff"), "")
        self.assertEqual(validation.visible(5), "")

    def test_required_rejects_text_that_is_only_invisible_characters(self):
        rule = validation.required("a password")
        for empty in ("", "   ", "\u200b", "\u200d\u2060", "\ufeff", "\x00", None, 0):
            self.assertEqual(rule(empty), "Enter a password.", repr(empty))
        self.assertEqual(rule("x"), "")
        self.assertEqual(rule("\u200bx"), "")

    def test_normalise_email_makes_look_alikes_equal(self):
        self.assertEqual(validation.normalise_email(" Zo\u00e9@Example.COM "), validation.normalise_email("zoe\u0301@example.com"))
        self.assertEqual(validation.normalise_email("\uff41@example.com"), "a@example.com")  # full-width letter

    def test_single_line(self):
        rule = validation.single_line("Name")
        self.assertEqual(rule("Alex Rao"), "")
        self.assertEqual(rule("  Alex  \n"), "")  # outer whitespace is trimmed first
        self.assertIn("single line", rule("Alex\nRao"))
        self.assertEqual(rule(None), "")

    def test_length_rules_count_visible_characters_only(self):
        self.assertTrue(validation.min_length(3, "Title")("ab\u200b"))
        self.assertEqual(validation.min_length(3, "Title")("abc"), "")
        self.assertEqual(validation.max_length(3, "Title")("abc"), "")
        self.assertTrue(validation.max_length(3, "Title")("abcd"))

    def test_email_rule_boundaries(self):
        self.assertEqual(validation.email_rule("a@b.co"), "")
        for bad in ("", "a", "a@b", "a b@c.co", "@b.co", "a@@b.co", "a" * 250 + "@b.co"):
            self.assertTrue(validation.email_rule(bad), bad)

    def test_password_rule_boundaries(self):
        self.assertEqual(validation.password_rule("abcdefg1"), "")
        self.assertEqual(validation.password_rule("a1" * 64), "")  # 128 characters
        for bad in ("abcdefg", "abcdefgh", "12345678", "a1" * 64 + "x", None, 12345678):
            self.assertTrue(validation.password_rule(bad), bad)

    def test_url_rule(self):
        self.assertEqual(validation.url_rule("https://example.com/a?b=1"), "")
        self.assertEqual(validation.url_rule("http://localhost:5000"), "")
        for bad in ("", "example.com", "javascript:alert(1)", "data:text/html,x", "ftp://x.co", "https://", "https://x.co/" + "a" * 2100):
            self.assertTrue(validation.url_rule(bad), bad[:30])

    def test_validate_reports_the_first_failing_rule_per_field(self):
        errs = validation.validate({"a": [validation.required("a"), validation.min_length(5, "A")], "b": [validation.required("b")]}, {"a": "xy", "b": "ok"})
        self.assertEqual(list(errs), ["a"])
        self.assertIn("at least 5", errs["a"])
        with self.assertRaises(ApiError) as ctx:
            validation.check({"a": [validation.required("a")]}, {})
        self.assertEqual((ctx.exception.status, list(ctx.exception.errors)), (422, ["a"]))

    def test_one_of_accepts_only_listed_strings(self):
        rule = validation.one_of(("x", "y"), "bad")
        self.assertEqual((rule("x"), rule("z"), rule(None), rule(["x"])), ("", "bad", "bad", "bad"))

    def test_clean_tags(self):
        self.assertEqual(validation.clean_tags(None), [])
        self.assertEqual(validation.clean_tags(["#Graphs", "graphs", "DP Notes", "<b>", "", "  "]), ["graphs", "dp-notes", "b"])
        self.assertEqual(len(validation.clean_tags([f"t{i}" for i in range(20)])), 6)
        self.assertEqual(len(validation.clean_tags(["x" * 100])[0]), 30)
        for bad in ("graphs", {"a": 1}, [1], [None]):
            with self.assertRaises(ApiError):
                validation.clean_tags(bad)

    def test_int_arg(self):
        with self.app.test_request_context("/?n=7&big=999999&neg=-4&empty=&junk=abc"):
            self.assertEqual(validation.int_arg("n", 1, 1, 10), 7)
            self.assertEqual(validation.int_arg("big", 1, 1, 10), 10)
            self.assertEqual(validation.int_arg("neg", 1, 1, 10), 1)
            self.assertEqual(validation.int_arg("empty", 5, 1, 10), 5)
            self.assertEqual(validation.int_arg("missing", 3, 1, 10), 3)
            with self.assertRaises(ApiError):
                validation.int_arg("junk", 1, 1, 10)


class ConfigTests(unittest.TestCase):
    def test_boolean_environment_values(self):
        for raw, expected in (("true", True), ("1", True), ("YES", True), ("on", True), ("false", False), ("0", False), ("", False)):
            with mock.patch.dict(os.environ, {"STUDYSYNC_TRUST_PROXY": raw}):
                self.assertEqual(config.load_config("development")["TRUST_PROXY"], expected, raw)

    def test_cors_origins_are_split_and_trimmed(self):
        with mock.patch.dict(os.environ, {"STUDYSYNC_CORS_ORIGINS": " https://a.example , https://b.example ,, "}):
            self.assertEqual(config.load_config("development")["CORS_ORIGINS"], ["https://a.example", "https://b.example"])

    def test_testing_profile_is_fast_and_unthrottled(self):
        cfg = config.load_config("testing")
        self.assertTrue(cfg["TESTING"])
        self.assertFalse(cfg["RATE_LIMIT_ENABLED"])
        self.assertTrue(cfg["PASSWORD_HASH_METHOD"].startswith("pbkdf2"))

    def test_production_needs_a_secret_and_secure_cookies(self):
        with mock.patch.dict(os.environ, {"STUDYSYNC_SECRET_KEY": "x" * 40}):
            cfg = config.load_config("production")
            self.assertTrue(cfg["COOKIE_SECURE"])
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("STUDYSYNC_SECRET_KEY", None)
            with self.assertRaises(RuntimeError):
                config.load_config("production")


class ErrorHelperTests(ApiTestCase):
    def test_error_response_shape_and_headers(self):
        with self.app.test_request_context():
            res = errors.error_response(429, "Slow down", {"f": "m"}, {"Retry-After": "7"})
        self.assertEqual(res.status_code, 429)
        self.assertEqual(res.get_json(), {"success": False, "message": "Slow down", "errors": {"f": "m"}})
        self.assertEqual(res.headers["Retry-After"], "7")


class RealtimeUnitTests(unittest.TestCase):
    def test_event_format_is_valid_sse(self):
        text = realtime.format_event(7, "group.updated", {"groupId": "g1", "kind": "posts"})
        self.assertEqual(text, 'id: 7\nevent: group.updated\ndata: {"groupId":"g1","kind":"posts"}\n\n')

    def test_stream_generator_sends_ready_heartbeats_events_and_expiry(self):
        import time
        hub = realtime.Hub()
        sub = hub.subscribe("u1", 5)
        gen = realtime.event_stream(hub, sub, "u1", time.time() + 0.5, 0.1)
        self.assertEqual(next(gen), "retry: 3000\n\n")
        self.assertIn('"userId":"u1"', next(gen))
        self.assertEqual(next(gen), ": ping\n\n")  # nothing queued: heartbeat
        hub.publish(["u1"], "notification", {"id": "n1"})
        self.assertIn("event: notification", next(gen))
        last = list(gen)
        self.assertIn("event: token-expired", last[-1])
        self.assertEqual(hub.count("u1"), 0)  # the finally block unsubscribed

    def test_hub_limits_connections_per_user_and_counts(self):
        hub = realtime.Hub()
        subs = [hub.subscribe("u", 2) for _ in range(3)]
        self.assertIsNone(subs[2])
        self.assertEqual((hub.count("u"), hub.count()), (2, 2))
        hub.unsubscribe(subs[0]); hub.unsubscribe(subs[1])
        self.assertEqual(hub.count(), 0)


class SeedTests(unittest.TestCase):
    def test_seed_creates_the_demo_data_once_and_reset_restores_it(self):
        from studysync import create_app
        path = os.path.join(tempfile.mkdtemp(), "seed.db")
        self.assertTrue(seed_database(path))
        self.assertFalse(seed_database(path))  # second call: already has users
        app = create_app({"ENV": "testing", "DATABASE": path})
        c = app.test_client()
        res = c.post("/api/auth/login", json={"email": "demo@studysync.app", "password": DEMO_PASSWORD})
        self.assertEqual(res.status_code, 200)
        h = {"Authorization": "Bearer " + res.get_json()["data"]["accessToken"]}
        self.assertEqual(len(c.get("/api/groups/mine", headers=h).get_json()["data"]), 3)
        self.assertEqual(c.get("/api/groups?limit=50", headers=h).get_json()["data"]["total"], 7)  # 8 groups, 1 private
        self.assertTrue(seed_database(path, reset=True))
        self.assertEqual(len(c.get("/api/notifications", headers=h).get_json()["data"]), 4)


class AppFactoryTests(ApiTestCase):
    def test_trust_proxy_uses_the_forwarded_address_for_rate_limits(self):
        from studysync import create_app
        app = create_app({"ENV": "testing", "DATABASE": os.path.join(self.tmp, "p.db"), "TRUST_PROXY": True, "RATE_LIMIT_ENABLED": True, "RATE_LIMIT_GLOBAL": (2, 60)})
        c = app.test_client()
        a = [c.get("/api/health", headers={"X-Forwarded-For": "1.1.1.1"}).status_code for _ in range(3)]
        b = c.get("/api/health", headers={"X-Forwarded-For": "2.2.2.2"}).status_code
        self.assertEqual((a, b), ([200, 200, 429], 200))

    def test_request_id_from_the_client_is_echoed_and_trimmed(self):
        res = self.app.test_client().get("/api/health", headers={"X-Request-Id": "trace-" + "z" * 100})
        self.assertEqual(len(res.headers["X-Request-Id"]), 64)
        self.assertTrue(res.headers["X-Request-Id"].startswith("trace-"))

    def test_request_logging_is_on_outside_tests(self):
        from studysync import create_app
        app = create_app({"ENV": "development", "DATABASE": os.path.join(self.tmp, "l.db"), "RATE_LIMIT_ENABLED": False, "TESTING": False})
        with self.assertLogs("studysync", level="INFO") as logs:
            app.test_client().get("/api/health")
        self.assertRegex(logs.output[0], r"GET /api/health -> 200 in [\d.]+ ms")

    def test_database_helpers(self):
        from studysync.db import init_db
        init_db(self.db_path)  # running it again on an existing database must be harmless
        init_db(self.db_path)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM users")[0][0], 0)


class ServiceBranchTests(ApiTestCase):
    def test_register_race_after_the_duplicate_check_is_a_409(self):
        from studysync.services import auth as auth_service
        real = auth_service.one
        calls = {"n": 0}

        def stale_first(sql, params=()):
            calls["n"] += 1
            return None if calls["n"] == 1 else real(sql, params)  # the duplicate check misses a row added a moment earlier

        self.actor(email="taken@example.com")
        with mock.patch.object(auth_service, "one", side_effect=stale_first):
            res = self.app.test_client().post("/api/auth/register", json={"name": "Late Comer", "email": "taken@example.com", "password": PASSWORD})
        self.assertEqual(res.status_code, 409)

    def test_invite_code_collisions_are_retried_and_give_up_cleanly(self):
        a = self.actor()
        codes = iter(["DAT-AAAAAA", "DAT-AAAAAA", "DAT-BBBBBB"])
        with mock.patch("studysync.services.groups._new_invite_code", side_effect=lambda s: next(codes)):
            first = self.group(a, name="First one")
            second = self.group(a, name="Second one")  # first attempt collides, second succeeds
        self.assertEqual((first["inviteCode"], second["inviteCode"]), ("DAT-AAAAAA", "DAT-BBBBBB"))
        with mock.patch("studysync.services.groups._new_invite_code", return_value="DAT-AAAAAA"):
            res = a.post("/api/groups", json={"name": "Doomed group", "description": "Never gets a code.", "subject": "Networks", "visibility": "public"})
        self.assertEqual(res.status_code, 500)
        self.assertFalse(res.get_json()["success"])

    def test_editing_resource_fields_is_validated_per_type(self):
        a = self.actor()
        g = self.group(a)
        link = self.resource(a, g)
        note = a.post(f"/api/groups/{g['id']}/resources", json={"title": "A note", "type": "note", "body": "Some useful notes here."}).get_json()["data"]
        self.assertEqual(a.patch(f"/api/resources/{link['id']}", json={"url": "javascript:x"}).status_code, 422)
        self.assertEqual(a.patch(f"/api/resources/{link['id']}", json={"url": "https://example.com/new"}).get_json()["data"]["url"], "https://example.com/new")
        self.assertEqual(a.patch(f"/api/resources/{note['id']}", json={"body": "short"}).status_code, 422)
        self.assertEqual(a.patch(f"/api/resources/{note['id']}", json={"body": "A completely rewritten note."}).get_json()["data"]["body"], "A completely rewritten note.")
        self.assertEqual(a.patch(f"/api/resources/{note['id']}", json={"url": "https://ignored.example"}).status_code, 422)  # a note has no link to edit


class LastBranchTests(ApiTestCase):
    def test_a_refresh_cookie_the_server_never_issued_is_rejected_and_cleared(self):
        c = self.app.test_client()
        c.set_cookie("studysync_refresh", "made-up-token-value", path="/api/auth")
        res = c.post("/api/auth/refresh")
        self.assertEqual(res.status_code, 401)
        self.assertIn("Max-Age=0", res.headers["Set-Cookie"])

    def test_avatar_link_can_be_set_and_cleared(self):
        a = self.actor()
        self.assertEqual(a.patch("/api/users/me", json={"avatarUrl": "https://example.com/me.png"}).get_json()["data"]["avatarUrl"], "https://example.com/me.png")
        self.assertEqual(a.patch("/api/users/me", json={"avatarUrl": ""}).get_json()["data"]["avatarUrl"], "")

    def test_a_plain_member_cannot_delete_someone_elses_post(self):
        owner, member, other = self.actor(), self.actor(), self.actor()
        g = self.group(owner)
        self.joined(g, member, other)
        p = self.post_(member, g)
        self.assertEqual(other.delete(f"/api/posts/{p['id']}").status_code, 403)
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], 1)


class ParityFixTests(unittest.TestCase):
    """Cases found by scripts/parity_check.py, where the server disagreed with the form."""

    def test_urls_with_spaces_or_control_characters_are_rejected(self):
        for bad in ("https://exa mple.com", "https://example.com/path with space", "https://ex\x00ample.com", "https://example.com/\tx"):
            self.assertTrue(validation.url_rule(bad), repr(bad))

    def test_passwords_need_ascii_digits_and_may_contain_any_character(self):
        self.assertTrue(validation.password_rule("abcdefgh\u0663"))  # an Arabic-Indic digit is not a number for this rule
        self.assertEqual(validation.password_rule("abc12345\n"), "")
        self.assertEqual(validation.password_rule("p\u00e4ssw\u00f6rd1"), "")
