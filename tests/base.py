"""Shared test helpers: a fresh app and database per test, and 'actors' that behave like separate browsers."""
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from studysync import create_app
from studysync.db import connect
from studysync.utils import to_iso

PASSWORD = "Password123"


class Actor:
    """One signed-in user with its own cookie jar (like one browser)."""

    def __init__(self, app, name, email):
        self.client = app.test_client()
        res = self.client.post("/api/auth/register", json={"name": name, "email": email, "password": PASSWORD})
        assert res.status_code == 201, res.get_json()
        data = res.get_json()["data"]
        self.token, self.id, self.name, self.email = data["accessToken"], data["user"]["id"], name, email

    def _call(self, method, path, json=None, **kw):
        headers = dict(kw.pop("headers", {}))
        if self.token:
            headers.setdefault("Authorization", f"Bearer {self.token}")
        return getattr(self.client, method)(path, json=json, headers=headers, **kw)

    def get(self, path, **kw): return self._call("get", path, **kw)
    def post(self, path, json=None, **kw): return self._call("post", path, json=json, **kw)
    def patch(self, path, json=None, **kw): return self._call("patch", path, json=json, **kw)
    def put(self, path, json=None, **kw): return self._call("put", path, json=json, **kw)
    def delete(self, path, **kw): return self._call("delete", path, **kw)


class ApiTestCase(unittest.TestCase):
    config: dict = {}

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmp, "test.db")
        self.app = create_app({"ENV": "testing", "DATABASE": self.db_path, **self.config})
        self._n = 0

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def actor(self, name="Alex Rao", email=None) -> Actor:
        self._n += 1
        return Actor(self.app, name, email or f"user{self._n}@example.com")

    def sql(self, query, params=()):
        conn = connect(self.db_path)
        try:
            rows = conn.execute(query, params).fetchall()
            conn.commit()
            return rows
        finally:
            conn.close()

    # ---- builders ----
    def group(self, owner, name="Algorithms Circle", subject="Data Structures", visibility="public", **extra):
        body = {"name": name, "description": "Weekly problem solving for exams.", "subject": subject, "visibility": visibility, **extra}
        res = owner.post("/api/groups", json=body)
        assert res.status_code == 201, res.get_json()
        return res.get_json()["data"]

    def joined(self, group, *users):
        for u in users:
            res = u.post("/api/groups/join-by-code", json={"code": group["inviteCode"]})
            assert res.status_code == 200, res.get_json()

    def in_hours(self, hours):
        return to_iso(datetime.now(timezone.utc) + timedelta(hours=hours))

    def session(self, owner, group, title="Graph problems", hours=24, **extra):
        res = owner.post(f"/api/groups/{group['id']}/sessions", json={"title": title, "startsAt": self.in_hours(hours), "durationMin": 60, "meetingLink": "https://meet.example.com/x", **extra})
        assert res.status_code == 201, res.get_json()
        return res.get_json()["data"]

    def resource(self, user, group, title="Graph cheat-sheet", **extra):
        res = user.post(f"/api/groups/{group['id']}/resources", json={"title": title, "type": "link", "url": "https://example.com/g", "tags": ["graphs"], **extra})
        assert res.status_code == 201, res.get_json()
        return res.get_json()["data"]

    def post_(self, user, group, title="BFS or DFS here?"):
        res = user.post(f"/api/groups/{group['id']}/posts", json={"title": title, "body": "How do you decide between them?"})
        assert res.status_code == 201, res.get_json()
        return res.get_json()["data"]
