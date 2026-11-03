import time
from datetime import datetime, timedelta, timezone

import jwt

from studysync.utils import to_iso
from .base import PASSWORD, ApiTestCase


class RegisterTests(ApiTestCase):
    def test_register_returns_user_token_and_httponly_cookie(self):
        c = self.app.test_client()
        res = c.post("/api/auth/register", json={"name": "Alex Rao", "email": "Alex@Example.com", "password": PASSWORD})
        body = res.get_json()
        self.assertEqual(res.status_code, 201)
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["user"]["email"], "alex@example.com")  # normalised
        self.assertNotIn("password_hash", body["data"]["user"])
        self.assertEqual(body["data"]["expiresIn"], 900)
        cookie = res.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Path=/api/auth", cookie)
        self.assertIn("SameSite=Lax", cookie)

    def test_password_is_stored_hashed(self):
        self.actor(email="h@example.com")
        stored = self.sql("SELECT password_hash FROM users WHERE email = 'h@example.com'")[0][0]
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(stored.startswith(("pbkdf2:", "scrypt:")))

    def test_validation_lists_every_bad_field(self):
        res = self.app.test_client().post("/api/auth/register", json={"name": "A", "email": "nope", "password": "short"})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(set(res.get_json()["errors"]), {"name", "email", "password"})

    def test_password_needs_letter_and_number(self):
        for bad in ("onlyletters", "12345678", "short1"):
            res = self.app.test_client().post("/api/auth/register", json={"name": "Alex", "email": "a@b.co", "password": bad})
            self.assertEqual(res.status_code, 422, bad)

    def test_duplicate_email_is_409_even_with_different_case(self):
        self.actor(email="dup@example.com")
        res = self.app.test_client().post("/api/auth/register", json={"name": "Other", "email": "DUP@example.com", "password": PASSWORD})
        self.assertEqual(res.status_code, 409)
        self.assertIn("email", res.get_json()["errors"])

    def test_non_string_values_are_rejected_not_crashed(self):
        res = self.app.test_client().post("/api/auth/register", json={"name": ["x"], "email": {"a": 1}, "password": 12345678})
        self.assertEqual(res.status_code, 422)


class LoginTests(ApiTestCase):
    def test_login_success(self):
        self.actor(email="l@example.com")
        res = self.app.test_client().post("/api/auth/login", json={"email": "L@example.com", "password": PASSWORD})
        self.assertEqual(res.status_code, 200)
        self.assertIn("accessToken", res.get_json()["data"])

    def test_wrong_password_and_unknown_email_give_the_same_answer(self):
        self.actor(email="l@example.com")
        c = self.app.test_client()
        wrong = c.post("/api/auth/login", json={"email": "l@example.com", "password": "Wrong1234"})
        unknown = c.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong1234"})
        self.assertEqual((wrong.status_code, unknown.status_code), (401, 401))
        self.assertEqual(wrong.get_json(), unknown.get_json())

    def test_login_validation(self):
        res = self.app.test_client().post("/api/auth/login", json={"email": "", "password": ""})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(set(res.get_json()["errors"]), {"email", "password"})

    def test_sql_injection_in_login_is_just_a_wrong_email(self):
        c = self.app.test_client()
        self.assertEqual(c.post("/api/auth/login", json={"email": "' OR '1'='1", "password": "x"}).status_code, 422)  # not an email
        res = c.post("/api/auth/login", json={"email": "a'--@x.co", "password": "x' OR '1'='1"})  # shaped like an email, parameterised anyway
        self.assertEqual(res.status_code, 401)


class TokenTests(ApiTestCase):
    def test_protected_route_needs_a_token(self):
        for header in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}, {"Authorization": "Bearer not.a.jwt"}):
            res = self.app.test_client().get("/api/users/me", headers=header)
            self.assertEqual(res.status_code, 401, header)

    def test_me_returns_the_current_user(self):
        a = self.actor("Priya Nair", "p@example.com")
        data = a.get("/api/users/me").get_json()["data"]
        self.assertEqual((data["name"], data["email"]), ("Priya Nair", "p@example.com"))

    def _token(self, **override):
        now = datetime.now(timezone.utc)
        payload = {"sub": self.actor().id, "typ": "access", "iat": now, "exp": now + timedelta(minutes=5), **override}
        return jwt.encode(payload, self.app.config["SECRET_KEY"], algorithm="HS256")

    def test_expired_token_is_rejected_with_a_clear_message(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=30)
        res = self.app.test_client().get("/api/users/me", headers={"Authorization": f"Bearer {self._token(iat=past, exp=past + timedelta(minutes=1))}"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("expired", res.get_json()["message"])

    def test_token_signed_with_another_key_is_rejected(self):
        bad = jwt.encode({"sub": "u_x", "typ": "access", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, "a-different-secret-key-0123456789abcdef", algorithm="HS256")
        self.assertEqual(self.app.test_client().get("/api/users/me", headers={"Authorization": f"Bearer {bad}"}).status_code, 401)

    def test_alg_none_token_is_rejected(self):
        forged = jwt.encode({"sub": self.actor().id, "typ": "access", "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}, key=None, algorithm="none")
        self.assertEqual(self.app.test_client().get("/api/users/me", headers={"Authorization": f"Bearer {forged}"}).status_code, 401)

    def test_token_without_expiry_or_wrong_type_is_rejected(self):
        no_exp = jwt.encode({"sub": self.actor().id, "typ": "access", "iat": datetime.now(timezone.utc)}, self.app.config["SECRET_KEY"], algorithm="HS256")
        wrong_type = self._token(typ="refresh")
        for t in (no_exp, wrong_type):
            self.assertEqual(self.app.test_client().get("/api/users/me", headers={"Authorization": f"Bearer {t}"}).status_code, 401)

    def test_token_for_a_deleted_user_is_rejected(self):
        a = self.actor()
        self.sql("DELETE FROM users WHERE id = ?", (a.id,))
        self.assertEqual(a.get("/api/users/me").status_code, 401)


class RefreshTests(ApiTestCase):
    def test_refresh_issues_new_access_token_and_rotates_cookie(self):
        a = self.actor()
        old_cookie = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        res = a.client.post("/api/auth/refresh")
        self.assertEqual(res.status_code, 200)
        self.assertIn("accessToken", res.get_json()["data"])
        self.assertNotEqual(a.client.get_cookie("studysync_refresh", path="/api/auth").value, old_cookie)

    def test_refresh_without_cookie_is_401(self):
        self.assertEqual(self.app.test_client().post("/api/auth/refresh").status_code, 401)

    def test_refresh_tokens_are_stored_hashed(self):
        a = self.actor()
        raw = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        stored = self.sql("SELECT token_hash FROM refresh_tokens")[0][0]
        self.assertNotEqual(raw, stored)
        self.assertEqual(len(stored), 64)

    def test_reusing_an_old_token_after_the_grace_window_revokes_the_whole_family(self):
        a = self.actor()
        stolen = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        a.client.post("/api/auth/refresh")  # legitimate rotation; `stolen` is now revoked
        old = to_iso(datetime.now(timezone.utc) - timedelta(minutes=5))
        self.sql("UPDATE refresh_tokens SET revoked_at = ? WHERE revoked_at IS NOT NULL", (old,))
        thief = self.app.test_client()
        thief.set_cookie("studysync_refresh", stolen, path="/api/auth")
        self.assertEqual(thief.post("/api/auth/refresh").status_code, 401)
        # the victim's newest token was in the same family, so it is dead too
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 401)

    def test_quick_double_refresh_is_treated_as_a_race_not_theft(self):
        a = self.actor()
        first = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 200)
        second = self.app.test_client()
        second.set_cookie("studysync_refresh", first, path="/api/auth")
        self.assertEqual(second.post("/api/auth/refresh").status_code, 401)
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 200)  # the family survived

    def test_expired_refresh_token_is_rejected(self):
        a = self.actor()
        self.sql("UPDATE refresh_tokens SET expires_at = ?", (to_iso(datetime.now(timezone.utc) - timedelta(days=1)),))
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 401)

    def test_logout_revokes_the_refresh_token_and_clears_the_cookie(self):
        a = self.actor()
        cookie = a.client.get_cookie("studysync_refresh", path="/api/auth").value
        res = a.client.post("/api/auth/logout")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Max-Age=0", res.headers["Set-Cookie"])
        again = self.app.test_client()
        again.set_cookie("studysync_refresh", cookie, path="/api/auth")
        self.assertEqual(again.post("/api/auth/refresh").status_code, 401)

    def test_logout_works_even_when_signed_out(self):
        self.assertEqual(self.app.test_client().post("/api/auth/logout").status_code, 200)

    def test_cookie_endpoints_refuse_unknown_origins(self):
        a = self.actor()
        self.assertEqual(a.client.post("/api/auth/refresh", headers={"Origin": "https://evil.example"}).status_code, 403)
        self.assertEqual(a.client.post("/api/auth/refresh", headers={"Origin": "http://localhost:5173"}).status_code, 200)


class ProfileTests(ApiTestCase):
    def test_update_name(self):
        a = self.actor()
        res = a.patch("/api/users/me", json={"name": "  Alexandra Rao "})
        self.assertEqual(res.get_json()["data"]["name"], "Alexandra Rao")

    def test_update_validation_and_empty_body(self):
        a = self.actor()
        self.assertEqual(a.patch("/api/users/me", json={"name": "A"}).status_code, 422)
        self.assertEqual(a.patch("/api/users/me", json={}).status_code, 422)
        self.assertEqual(a.patch("/api/users/me", json={"avatarUrl": "javascript:alert(1)"}).status_code, 422)

    def test_email_and_role_cannot_be_changed_through_profile_update(self):
        a = self.actor(email="keep@example.com")
        a.patch("/api/users/me", json={"name": "Alex R", "email": "new@example.com", "role": "admin"})
        row = self.sql("SELECT email, role FROM users WHERE id = ?", (a.id,))[0]
        self.assertEqual(tuple(row), ("keep@example.com", "student"))

    def test_change_password_flow(self):
        a = self.actor(email="cp@example.com")
        self.assertEqual(a.post("/api/users/me/password", json={"currentPassword": "Wrong1234", "newPassword": "NewPass123"}).status_code, 422)
        self.assertEqual(a.post("/api/users/me/password", json={"currentPassword": PASSWORD, "newPassword": "weak"}).status_code, 422)
        self.assertEqual(a.post("/api/users/me/password", json={"currentPassword": PASSWORD, "newPassword": "NewPass123"}).status_code, 200)
        c = self.app.test_client()
        self.assertEqual(c.post("/api/auth/login", json={"email": "cp@example.com", "password": PASSWORD}).status_code, 401)
        self.assertEqual(c.post("/api/auth/login", json={"email": "cp@example.com", "password": "NewPass123"}).status_code, 200)
        self.assertEqual(a.client.post("/api/auth/refresh").status_code, 401)  # old sessions were ended


class RateLimitTests(ApiTestCase):
    config = {"RATE_LIMIT_ENABLED": True, "RATE_LIMIT_AUTH": (5, 60), "RATE_LIMIT_LOGIN_FAILURES": (3, 60), "RATE_LIMIT_GLOBAL": (1000, 60)}

    def test_repeated_failed_logins_for_one_email_are_blocked(self):
        c = self.app.test_client()
        codes = [c.post("/api/auth/login", json={"email": "victim@example.com", "password": "Wrong1234"}).status_code for _ in range(5)]
        self.assertEqual(codes[:3], [401, 401, 401])
        self.assertEqual(codes[3], 429)

    def test_failed_logins_for_one_email_do_not_lock_out_another(self):
        c = self.app.test_client()
        for _ in range(3):
            c.post("/api/auth/login", json={"email": "victim@example.com", "password": "Wrong1234"})
        self.assertEqual(c.post("/api/auth/login", json={"email": "other@example.com", "password": "Wrong1234"}).status_code, 401)

    def test_auth_endpoints_have_a_per_ip_limit_with_retry_after(self):
        c = self.app.test_client()
        results = [c.post("/api/auth/login", json={"email": f"x{i}@example.com", "password": "Wrong1234"}) for i in range(7)]
        self.assertEqual([r.status_code for r in results[:5]], [401] * 5)
        self.assertEqual(results[5].status_code, 429)
        self.assertGreaterEqual(int(results[5].headers["Retry-After"]), 1)
