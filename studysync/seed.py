"""Demo data: the same students, groups, resources, posts and sessions as the Week 2 front-end mock database.

Demo login: demo@studysync.app / Password123 (every seeded user has the password Password123).
"""
from datetime import datetime, timedelta, timezone

from .db import connect, init_db
from .security import hash_password
from .utils import to_iso

DEMO_PASSWORD = "Password123"


def seed_database(path: str, reset: bool = False):
    from flask import Flask

    init_db(path)
    conn = connect(path)
    if reset:
        for table in ("notifications", "session_attendees", "study_sessions", "comments", "posts", "resource_tags", "resources", "memberships", "study_groups", "refresh_tokens", "users"):
            conn.execute(f"DELETE FROM {table}")
    elif conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
        conn.close()
        return False

    now = datetime.now(timezone.utc)
    at = lambda hours: to_iso(now + timedelta(hours=hours))  # noqa: E731  (negative hours are in the past)
    app = Flask(__name__)
    app.config["PASSWORD_HASH_METHOD"] = "scrypt"
    with app.app_context():
        pw = hash_password(DEMO_PASSWORD)

    users = [("u1", "Alex Rao", "demo@studysync.app", 60), ("u2", "Priya Nair", "priya@studysync.app", 70), ("u3", "Sam Mathew", "sam@studysync.app", 65),
             ("u4", "Rohan Verma", "rohan@studysync.app", 50), ("u5", "Meera Iyer", "meera@studysync.app", 45), ("u6", "Kabir Shah", "kabir@studysync.app", 40)]
    conn.executemany("INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?,?,?,?,?)", [(i, n, e, pw, at(-24 * d)) for i, n, e, d in users])

    groups = [
        ("g1", "Algorithms Study Circle", "Data Structures", "Weekly problem-solving rounds for interviews and exams. We start with graphs, then move to dynamic programming.", "public", "u2", "DAT-4821", 30),
        ("g2", "Database Gang", "Databases", "Normalisation, indexing and SQL practice for the DBMS paper. Bring your own tricky queries.", "public", "u3", "DAT-7710", 28),
        ("g3", "OS Notes Hub", "Operating Systems", "Shared notes on scheduling, memory and file systems, with worked examples from past papers.", "public", "u4", "OPE-3302", 25),
        ("g4", "Web Dev Buddies", "Web Development", "Build small full stack projects together and review each other\u2019s code. React, Node and MongoDB.", "public", "u5", "WEB-5519", 22),
        ("g5", "Aptitude Daily", "Placements", "Ten aptitude and reasoning questions a day, plus mock tests every weekend.", "public", "u6", "PLA-1208", 20),
        ("g6", "ML Reading Club", "AI and ML", "We read one paper or chapter every week and discuss it on Sundays.", "public", "u2", "AIA-9043", 14),
        ("g7", "Compiler Design Crew", "Compilers", "Private group for the compiler design project team. Join with the invite code.", "private", "u3", "COM-2026", 12),
        ("g8", "Networks Lab Partners", "Networks", "Pair up for the networks lab: packet tracing, socket programming and subnetting drills.", "public", "u4", "NET-6671", 9),
    ]
    conn.executemany(
        "INSERT INTO study_groups (id, name, subject, description, visibility, owner_id, invite_code, created_at) VALUES (?,?,?,?,?,?,?,?)",
        [(i, n, s, d, v, o, c, at(-24 * days)) for i, n, s, d, v, o, c, days in groups],
    )

    members = {
        "g1": [("u2", "owner", 30), ("u1", "member", 12), ("u3", "member", 5), ("u4", "member", 5), ("u5", "member", 5)],
        "g2": [("u3", "owner", 28), ("u1", "moderator", 20), ("u2", "member", 5), ("u4", "member", 5)],
        "g3": [("u4", "owner", 25), ("u2", "member", 5), ("u5", "member", 5), ("u6", "member", 5)],
        "g4": [("u5", "owner", 22), ("u1", "member", 8), ("u3", "member", 5), ("u6", "member", 5), ("u2", "member", 5)],
        "g5": [("u6", "owner", 20), ("u2", "member", 5), ("u3", "member", 5), ("u4", "member", 5), ("u5", "member", 5)],
        "g6": [("u2", "owner", 14), ("u3", "member", 5), ("u5", "member", 5)],
        "g7": [("u3", "owner", 12), ("u4", "member", 5)],
        "g8": [("u4", "owner", 9), ("u6", "member", 5), ("u5", "member", 5)],
    }
    conn.executemany(
        "INSERT INTO memberships (id, group_id, user_id, role, joined_at) VALUES (?,?,?,?,?)",
        [(f"m_{g}_{u}", g, u, role, at(-24 * days)) for g, rows in members.items() for u, role, days in rows],
    )

    resources = [
        ("r1", "g1", "u3", "Graph algorithms cheat-sheet", "link", "https://example.com/graph-cheat-sheet", "", ["graphs", "notes"], 48),
        ("r2", "g1", "u2", "DP patterns: video playlist", "link", "https://example.com/dp-patterns", "", ["dp", "video"], 96),
        ("r3", "g1", "u1", "Mock test 3", "file", "https://example.com/mock-test-3.pdf", "", ["practice", "mock-test"], 170),
        ("r4", "g1", "u4", "Big-O quick notes", "note", "", "O(1) constant, O(log n) halving, O(n) one pass, O(n log n) sorting, O(n^2) nested loops. When two loops run one after the other, add them; when nested, multiply.", ["complexity"], 200),
        ("r5", "g2", "u3", "Normalisation worked examples", "note", "", "1NF removes repeating groups, 2NF removes partial dependencies, 3NF removes transitive dependencies. Try each rule on the student-course-teacher table.", ["normalisation", "exam"], 6),
        ("r6", "g2", "u2", "SQL joins visualised", "link", "https://example.com/sql-joins", "", ["sql", "joins"], 72),
        ("r7", "g3", "u4", "Process scheduling notes", "note", "", "Compare FCFS, SJF, round robin and priority scheduling using the same five processes so the differences in waiting time are easy to see.", ["scheduling"], 40),
        ("r8", "g4", "u5", "React hooks mental model", "link", "https://example.com/react-hooks", "", ["react", "hooks"], 30),
        ("r9", "g4", "u6", "CSS grid in 20 minutes", "link", "https://example.com/css-grid", "", ["css", "layout"], 120),
        ("r10", "g5", "u6", "Aptitude shortcuts sheet", "link", "https://example.com/aptitude-shortcuts", "", ["aptitude"], 60),
    ]
    conn.executemany("INSERT INTO resources (id, group_id, uploaded_by, title, type, url, body, created_at) VALUES (?,?,?,?,?,?,?,?)", [(i, g, u, t, ty, url, body, at(-h)) for i, g, u, t, ty, url, body, _, h in resources])
    conn.executemany("INSERT INTO resource_tags (resource_id, tag) VALUES (?,?)", [(r[0], tag) for r in resources for tag in r[7]])

    posts = [
        ("p1", "g1", "u3", "How do you decide between BFS and DFS in interviews?", "I keep second-guessing myself. My rule so far: BFS for shortest path in unweighted graphs, DFS for anything about connectivity or ordering. What are your rules of thumb?", 52),
        ("p2", "g1", "u2", "Weekly plan: graphs first, then dynamic programming", "Proposal: two weeks on graphs (traversals, shortest paths, topological sort), then three weeks on DP patterns. Reply if you want a different order.", 120),
        ("p3", "g2", "u2", "Is BCNF always worth it?", "In the lab project we denormalised a table for speed. When is it fine to stop at 3NF and accept some redundancy?", 30),
        ("p4", "g4", "u6", "Which state library should we use for the group project?", "Context plus React Query feels enough for us, but a few people mentioned Redux Toolkit. Thoughts?", 70),
    ]
    conn.executemany("INSERT INTO posts (id, group_id, author_id, title, body, created_at) VALUES (?,?,?,?,?,?)", [(i, g, u, t, b, at(-h)) for i, g, u, t, b, h in posts])
    comments = [
        ("c1", "p1", "u2", 'Same rule here. I also use BFS whenever the question says "minimum number of steps".', 40),
        ("c2", "p1", "u4", "DFS is easier to write recursively, so I default to it unless distance matters.", 26),
        ("c3", "p3", "u3", "If the table is read far more than it is written, redundancy is usually fine. Just document it.", 20),
    ]
    conn.executemany("INSERT INTO comments (id, post_id, author_id, body, created_at) VALUES (?,?,?,?,?)", [(i, p, u, b, at(-h)) for i, p, u, b, h in comments])

    sessions = [
        ("s1", "g1", "u2", "Graph problems: practice round", 26, 90, "https://meet.example.com/graphs", [("u2", "going"), ("u3", "going"), ("u4", "maybe")]),
        ("s2", "g1", "u2", "Dynamic programming drill", 122, 60, "https://meet.example.com/dp", [("u2", "going")]),
        ("s3", "g2", "u1", "DBMS revision: normalisation", 50, 75, "https://meet.example.com/dbms", [("u3", "going"), ("u2", "going")]),
        ("s4", "g4", "u5", "Build a landing page together", 75, 120, "https://meet.example.com/webdev", [("u5", "going"), ("u6", "maybe")]),
        ("s5", "g3", "u4", "Paging and segmentation recap", -48, 60, "https://meet.example.com/os", [("u4", "going")]),
    ]
    conn.executemany("INSERT INTO study_sessions (id, group_id, created_by, title, starts_at, duration_min, meeting_link, created_at) VALUES (?,?,?,?,?,?,?,?)", [(i, g, u, t, at(h), d, link, at(-100)) for i, g, u, t, h, d, link, _ in sessions])
    conn.executemany("INSERT INTO session_attendees (session_id, user_id, status) VALUES (?,?,?)", [(s[0], u, st) for s in sessions for u, st in s[7]])

    notes = [
        ("n1", "resource", "Sam shared a new resource in Database Gang", "/app/groups/g2?tab=resources", 6, 0),
        ("n2", "reply", "Priya replied to a post in Algorithms Study Circle", "/app/groups/g1/posts/p1", 26, 0),
        ("n3", "session", "Session tomorrow: Graph problems: practice round", "/app/groups/g1?tab=sessions", 30, 0),
        ("n4", "member", "Meera joined Web Dev Buddies", "/app/groups/g4?tab=members", 120, 1),
    ]
    conn.executemany("INSERT INTO notifications (id, user_id, type, message, link, is_read, created_at) VALUES (?,?,?,?,?,?,?)", [(i, "u1", t, m, link, r, at(-h)) for i, t, m, link, h, r in notes])
    conn.commit()
    conn.close()
    return True
