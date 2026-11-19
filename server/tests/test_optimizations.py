"""Tests that protect the Week 5 optimizations: they must stay fast AND stay correct."""
import os
import random
import sqlite3
import tempfile
import threading
from unittest import mock

from studysync import db as dbmod
from studysync.db import connect, init_db
from .base import ApiTestCase


class ConnectionPoolTests(ApiTestCase):
    def test_sequential_requests_reuse_one_connection(self):
        a = self.actor()
        with mock.patch.object(dbmod, "connect", wraps=dbmod.connect) as spy:
            for _ in range(10):
                self.assertEqual(a.get("/api/users/me").status_code, 200)
        self.assertLessEqual(spy.call_count, 1)  # at most the first request opens one; the rest reuse it

    def test_pooling_can_be_switched_off_for_debugging(self):
        self.app.config["DB_POOL"] = False
        a = self.actor()
        with mock.patch.object(dbmod, "connect", wraps=dbmod.connect) as spy:
            for _ in range(5):
                a.get("/api/users/me")
        self.assertEqual(spy.call_count, 5)

    def test_a_failed_request_cannot_leak_half_written_data_into_the_next_one(self):
        a = self.actor()
        g = self.group(a)

        def explode(*args, **kwargs):
            dbmod.get_db().execute("INSERT INTO posts (id, group_id, author_id, title, body, created_at) VALUES ('p_leak', ?, ?, 'x', 'y', 'now')", (g["id"], a.id))
            raise RuntimeError("boom after a write")

        with mock.patch("studysync.services.content.list_posts", side_effect=explode), self.assertLogs("studysync", level="ERROR"):
            self.assertEqual(a.get(f"/api/groups/{g['id']}/posts").status_code, 500)
        self.assertEqual(a.get(f"/api/groups/{g['id']}/posts").get_json()["data"], [])  # the stray row was rolled back
        self.assertEqual(self.sql("SELECT COUNT(*) FROM posts")[0][0], 0)
        self.assertEqual(a.post(f"/api/groups/{g['id']}/posts", json={"title": "A fine title", "body": "A body that is long enough."}).status_code, 201)

    def test_idle_connections_are_capped(self):
        path = self.db_path
        conns = [connect(path) for _ in range(dbmod.POOL_MAX_IDLE + 5)]
        for c in conns:
            dbmod._release(path, c)
        self.assertEqual(dbmod._pool(path).qsize(), dbmod.POOL_MAX_IDLE)

    def test_a_broken_connection_is_discarded_not_pooled(self):
        path = self.db_path
        conn = connect(path)
        conn.close()  # e.g. the database file went away mid-request
        before = dbmod._pool(path).qsize()
        dbmod._release(path, conn)  # must not raise, and must not put a dead connection back
        self.assertEqual(dbmod._pool(path).qsize(), before)

    def test_concurrent_readers_and_writers_do_not_collide(self):
        owner = self.actor()
        g = self.group(owner)
        members = [self.actor() for _ in range(4)]
        self.joined(g, *members)
        errors, barrier = [], threading.Barrier(len(members) + 1)

        def work(user):
            barrier.wait()
            for i in range(15):
                r = user.get(f"/api/groups/{g['id']}/resources")
                w = user.post(f"/api/groups/{g['id']}/resources", json={"title": f"Concurrent {user.id[-4:]} {i}", "type": "link", "url": "https://example.com/c", "tags": []})
                if r.status_code != 200 or w.status_code != 201:
                    errors.append((r.status_code, w.status_code))

        threads = [threading.Thread(target=work, args=(m,)) for m in members]
        [t.start() for t in threads]
        barrier.wait()
        [t.join() for t in threads]
        self.assertEqual(errors, [])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM resources")[0][0], 60)


class MemberCountTests(ApiTestCase):
    def counts_agree(self):
        rows = self.sql("SELECT g.id, g.member_count, (SELECT COUNT(*) FROM memberships m WHERE m.group_id = g.id) AS real FROM study_groups g")
        return [(r[0], r[1], r[2]) for r in rows if r[1] != r[2]]

    def test_counts_follow_every_kind_of_membership_change(self):
        owner, a, b, c = self.actor(), self.actor(), self.actor(), self.actor()
        g = self.group(owner)
        self.assertEqual(self.sql("SELECT member_count FROM study_groups")[0][0], 1)
        self.joined(g, a, b, c)
        self.assertEqual(self.sql("SELECT member_count FROM study_groups")[0][0], 4)
        a.delete(f"/api/groups/{g['id']}/leave")
        owner.delete(f"/api/groups/{g['id']}/members/{b.id}")
        self.assertEqual(self.sql("SELECT member_count FROM study_groups")[0][0], 2)
        owner.post(f"/api/groups/{g['id']}/transfer-ownership", json={"userId": c.id})  # roles change, headcount does not
        self.assertEqual(self.sql("SELECT member_count FROM study_groups")[0][0], 2)
        self.assertEqual(c.get(f"/api/groups/{g['id']}").get_json()["data"]["memberCount"], 2)
        c.delete(f"/api/groups/{g['id']}")
        self.assertEqual(self.counts_agree(), [])

    def test_counts_stay_correct_over_many_random_operations(self):
        rng = random.Random(2026)  # fixed seed: the same sequence every run
        owner = self.actor()
        users = [self.actor() for _ in range(6)]
        groups = [self.group(owner, name=f"Random group {i}") for i in range(4)]
        for _ in range(250):
            u, g = rng.choice(users), rng.choice(groups)
            action = rng.choice(["join", "leave", "remove", "code"])
            if action == "join":
                u.post(f"/api/groups/{g['id']}/join")
            elif action == "leave":
                u.delete(f"/api/groups/{g['id']}/leave")
            elif action == "remove":
                owner.delete(f"/api/groups/{g['id']}/members/{u.id}")
            else:
                u.post("/api/groups/join-by-code", json={"code": g["inviteCode"]})
        self.assertEqual(self.counts_agree(), [])

    def test_discovery_orders_by_popularity_then_name(self):
        owner = self.actor()
        fans = [self.actor() for _ in range(3)]
        small, big, medium_b, medium_a = (self.group(owner, name=n) for n in ("Small", "Big", "Medium B", "Medium A"))
        self.joined(big, *fans)
        self.joined(medium_a, fans[0]); self.joined(medium_b, fans[1])
        names = [x["name"] for x in fans[2].get("/api/groups").get_json()["data"]["items"]]
        self.assertEqual(names, ["Big", "Medium A", "Medium B", "Small"])

    def test_the_popular_sort_is_answered_from_the_index(self):
        plan = " ".join(r[3] for r in self.sql("EXPLAIN QUERY PLAN SELECT id FROM study_groups WHERE visibility = 'public' ORDER BY member_count DESC, name LIMIT 6"))
        self.assertIn("idx_groups_popular", plan)
        self.assertNotIn("TEMP B-TREE", plan)  # no sorting of the whole table

    def test_an_old_database_is_upgraded_and_backfilled(self):
        path = os.path.join(self.tmp, "old.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
                                role TEXT NOT NULL DEFAULT 'student', avatar_url TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL);
            CREATE TABLE study_groups (id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, subject TEXT NOT NULL,
                                       visibility TEXT NOT NULL, invite_code TEXT NOT NULL UNIQUE, owner_id TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE memberships (id TEXT PRIMARY KEY, group_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'member',
                                      joined_at TEXT NOT NULL, UNIQUE (group_id, user_id));
            INSERT INTO users VALUES ('u1','A','a@x.co','h','student','','t'), ('u2','B','b@x.co','h','student','','t'), ('u3','C','c@x.co','h','student','','t');
            INSERT INTO study_groups VALUES ('g1','Old group','d','Networks','public','OLD-1','u1','t');
            INSERT INTO memberships VALUES ('m1','g1','u1','owner','t'), ('m2','g1','u2','member','t'), ('m3','g1','u3','member','t');
        """)
        conn.commit(); conn.close()
        init_db(path)
        init_db(path)  # a second run changes nothing
        conn = connect(path)
        self.assertEqual(conn.execute("SELECT member_count FROM study_groups WHERE id = 'g1'").fetchone()[0], 3)
        conn.execute("DELETE FROM memberships WHERE id = 'm3'")
        self.assertEqual(conn.execute("SELECT member_count FROM study_groups WHERE id = 'g1'").fetchone()[0], 2)
        conn.close()
