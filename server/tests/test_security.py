import os
import sqlite3
from unittest import mock

from studysync import create_app
from studysync.config import load_config
from .base import ApiTestCase, PASSWORD


class HeaderAndCorsTests(ApiTestCase):
    def test_security_headers_on_every_response(self):
        for res in (self.app.test_client().get("/api/health"), self.app.test_client().get("/nothing-here")):
            self.assertEqual(res.headers["X-Content-Type-Options"], "nosniff")
            self.assertEqual(res.headers["X-Frame-Options"], "DENY")
            self.assertEqual(res.headers["Referrer-Policy"], "no-referrer")
            self.assertIn("default-src 'none'", res.headers["Content-Security-Policy"])
            self.assertEqual(res.headers["Cache-Control"], "no-store")
            self.assertTrue(res.headers["X-Request-Id"])

    def test_allowed_origin_gets_cors_headers_with_credentials(self):
        res = self.app.test_client().get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(res.headers["Access-Control-Allow-Origin"], "http://localhost:5173")
        self.assertEqual(res.headers["Access-Control-Allow-Credentials"], "true")
        self.assertIn("Origin", res.headers["Vary"])

    def test_unknown_origin_gets_no_cors_headers(self):
        res = self.app.test_client().get("/api/health", headers={"Origin": "https://evil.example"})
        self.assertNotIn("Access-Control-Allow-Origin", res.headers)

    def test_preflight(self):
        res = self.app.test_client().options("/api/groups", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
        self.assertIn("Authorization", res.headers["Access-Control-Allow-Headers"])
        self.assertIn("PATCH", res.headers["Access-Control-Allow-Methods"])

    def test_hsts_and_secure_cookie_in_production_style_config(self):
        app = create_app({"ENV": "testing", "DATABASE": os.path.join(self.tmp, "p.db"), "COOKIE_SECURE": True, "COOKIE_SAMESITE": "None"})
        res = app.test_client().post("/api/auth/register", json={"name": "Alex Rao", "email": "s@example.com", "password": PASSWORD})
        cookie = res.headers["Set-Cookie"]
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=None", cookie)
        self.assertIn("max-age=31536000", res.headers["Strict-Transport-Security"])

    def test_production_refuses_to_start_without_a_real_secret(self):
        with mock.patch.dict(os.environ, {"STUDYSYNC_SECRET_KEY": ""}, clear=False):
            os.environ.pop("STUDYSYNC_SECRET_KEY")
            with self.assertRaises(RuntimeError):
                load_config("production")


class ErrorHandlingTests(ApiTestCase):
    def test_errors_are_json_with_the_standard_shape(self):
        c = self.app.test_client()
        cases = [(c.get("/api/nope"), 404), (c.delete("/api/health"), 405)]
        for res, code in cases:
            self.assertEqual(res.status_code, code)
            body = res.get_json()
            self.assertFalse(body["success"])
            self.assertIsInstance(body["message"], str)

    def test_body_must_be_json_object(self):
        a = self.actor()
        self.assertEqual(a.client.post("/api/groups", data="name=x", headers={"Authorization": f"Bearer {a.token}"}).status_code, 415)
        self.assertEqual(a.client.post("/api/groups", data="{broken", content_type="application/json", headers={"Authorization": f"Bearer {a.token}"}).status_code, 400)
        self.assertEqual(a.post("/api/groups", json=[1, 2, 3]).status_code, 400)

    def test_oversized_body_is_413(self):
        res = self.app.test_client().post("/api/auth/login", data="x" * 1_100_000, content_type="application/json")
        self.assertEqual(res.status_code, 413)

    def test_unexpected_errors_return_a_generic_500_without_details(self):
        a = self.actor()
        with mock.patch("studysync.services.groups.my_groups", side_effect=RuntimeError("secret database path /var/db")), self.assertLogs("studysync", level="ERROR"):
            res = a.get("/api/groups/mine")
        self.assertEqual(res.status_code, 500)
        self.assertNotIn("secret", res.get_data(as_text=True))
        self.assertNotIn("Traceback", res.get_data(as_text=True))

    def test_every_success_response_uses_the_envelope(self):
        a = self.actor()
        g = self.group(a)
        for path in ("/api/users/me", "/api/groups", "/api/groups/mine", f"/api/groups/{g['id']}", f"/api/groups/{g['id']}/members", "/api/sessions", "/api/notifications", "/api/users/me/dashboard"):
            body = a.get(path).get_json()
            self.assertEqual(set(body), {"success", "data"}, path)
            self.assertTrue(body["success"])


class AccessControlTests(ApiTestCase):
    def test_outsider_is_blocked_from_every_group_endpoint(self):
        owner, outsider = self.actor(), self.actor()
        g = self.group(owner, visibility="private")
        r, p, s = self.resource(owner, g), self.post_(owner, g), self.session(owner, g)
        gid = g["id"]
        reads = [f"/api/groups/{gid}", f"/api/groups/{gid}/members", f"/api/groups/{gid}/resources", f"/api/groups/{gid}/posts", f"/api/groups/{gid}/sessions", f"/api/posts/{p['id']}"]
        for path in reads:
            self.assertEqual(outsider.get(path).status_code, 403, path)
        writes = [
            ("post", f"/api/groups/{gid}/resources", {"title": "Sneaky", "type": "link", "url": "https://x.co"}),
            ("post", f"/api/groups/{gid}/posts", {"title": "Sneaky post", "body": "Sneaky body text"}),
            ("post", f"/api/posts/{p['id']}/comments", {"body": "Sneaky comment"}),
            ("put", f"/api/sessions/{s['id']}/rsvp", {"status": "going"}),
            ("patch", f"/api/groups/{gid}", {"name": "Hijacked"}),
            ("delete", f"/api/groups/{gid}", None),
            ("delete", f"/api/resources/{r['id']}", None),
            ("delete", f"/api/posts/{p['id']}", None),
            ("delete", f"/api/sessions/{s['id']}", None),
            ("post", f"/api/groups/{gid}/join", None),
        ]
        for method, path, body in writes:
            self.assertEqual(getattr(outsider, method)(path, json=body).status_code, 403, f"{method} {path}")
        # nothing changed
        self.assertEqual(owner.get(f"/api/groups/{gid}").get_json()["data"]["name"], "Algorithms Circle")
        self.assertEqual(self.sql("SELECT COUNT(*) FROM memberships WHERE group_id = ?", (gid,))[0][0], 1)

    def test_private_groups_are_invisible_in_discovery_and_to_other_users_mine(self):
        owner, other = self.actor(), self.actor()
        self.group(owner, name="Hidden group", visibility="private")
        self.assertEqual(other.get("/api/groups").get_json()["data"]["total"], 0)
        self.assertEqual(other.get("/api/groups/mine").get_json()["data"], [])

    def test_every_data_endpoint_requires_authentication(self):
        c = self.app.test_client()
        paths = ["/api/users/me", "/api/users/me/dashboard", "/api/groups", "/api/groups/mine", "/api/groups/g1", "/api/groups/g1/members", "/api/groups/g1/resources",
                 "/api/groups/g1/posts", "/api/groups/g1/sessions", "/api/posts/p1", "/api/sessions", "/api/notifications"]
        for path in paths:
            self.assertEqual(c.get(path).status_code, 401, path)
        for method, path in (("post", "/api/groups"), ("post", "/api/groups/join-by-code"), ("delete", "/api/groups/g1"), ("put", "/api/sessions/s1/rsvp"), ("patch", "/api/notifications/read-all")):
            self.assertEqual(getattr(c, method)(path, json={}).status_code, 401, path)

    def test_registration_cannot_grant_admin(self):
        c = self.app.test_client()
        res = c.post("/api/auth/register", json={"name": "Mallory", "email": "m@example.com", "password": PASSWORD, "role": "admin", "id": "u_forced"})
        self.assertEqual(res.get_json()["data"]["user"]["role"], "student")
        self.assertNotEqual(res.get_json()["data"]["user"]["id"], "u_forced")

    def test_password_hashes_never_appear_in_responses(self):
        a = self.actor()
        g = self.group(a)
        for path in ("/api/users/me", f"/api/groups/{g['id']}/members", f"/api/groups/{g['id']}", "/api/users/me/dashboard"):
            text = a.get(path).get_data(as_text=True)
            self.assertNotIn("pbkdf2", text)
            self.assertNotIn("password", text.lower())

    def test_database_enforces_foreign_keys(self):
        self.actor()
        with self.assertRaises(sqlite3.IntegrityError):
            self.sql("INSERT INTO resources (id, group_id, title, type, created_at) VALUES ('r_x', 'g_nope', 'x', 'link', 'now')")


class RateLimitTests(ApiTestCase):
    config = {"RATE_LIMIT_ENABLED": True, "RATE_LIMIT_GLOBAL": (5, 60), "RATE_LIMIT_JOIN_CODE": (2, 60), "RATE_LIMIT_AUTH": (100, 60)}

    def test_global_limit_returns_429_with_retry_after(self):
        c = self.app.test_client()
        codes = [c.get("/api/health").status_code for _ in range(7)]
        self.assertEqual(codes, [200] * 5 + [429] * 2)
        res = c.get("/api/health")
        self.assertIn("Retry-After", res.headers)
        self.assertFalse(res.get_json()["success"])

    def test_preflight_requests_are_not_counted(self):
        c = self.app.test_client()
        for _ in range(10):
            c.options("/api/groups", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(c.get("/api/health").status_code, 200)

    def test_invite_code_guessing_is_throttled(self):
        a = self.actor()
        statuses = [a.post("/api/groups/join-by-code", json={"code": f"AAA-{i:06d}"}).status_code for i in range(4)]
        self.assertEqual(statuses[:2], [404, 404])
        self.assertEqual(statuses[2:], [429, 429])
