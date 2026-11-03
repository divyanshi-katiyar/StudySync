"""Measure API response times against a real HTTP server (not the in-process test client).

    python scripts/benchmark.py            # writes docs/benchmark.json and prints a table

What it does
  1. Seeds the demo database and starts the API on a free local port (multi-threaded development server).
  2. Sequential run: every endpoint is called 200 times by one client; reports mean, p50, p95, p99 in milliseconds.
  3. Scale run: adds 2,000 groups, 6,000 users, 18,000 memberships, 10,000 resources, 4,000 posts directly through SQL,
     then repeats the list and search endpoints to show how the indexes hold up.
  4. Concurrency run: 20 client threads send a mixed read workload for 10 seconds; reports requests per second and p95.
Lab numbers: one machine, local loopback, no network latency. They show the application's own cost.
"""
import json
import os
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests
from werkzeug.serving import make_server

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studysync import create_app  # noqa: E402
from studysync.db import connect  # noqa: E402
from studysync.seed import seed_database  # noqa: E402
from studysync.subjects import SUBJECTS  # noqa: E402

N = 200


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(round(q * (len(values) - 1))))]


def summarize(times):
    return {"n": len(times), "mean": round(statistics.mean(times), 2), "p50": round(pct(times, 0.5), 2), "p95": round(pct(times, 0.95), 2), "p99": round(pct(times, 0.99), 2), "max": round(max(times), 2)}


def timed(session, method, url, **kw):
    t = time.perf_counter()
    r = session.request(method, url, **kw)
    return (time.perf_counter() - t) * 1000, r


def bulk_load(path):
    conn = connect(path)
    now = "2026-10-01T00:00:00.000Z"
    users = [(f"bu{i}", f"Bulk User {i}", f"bulk{i}@example.com", "x", now) for i in range(6000)]
    conn.executemany("INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?,?,?,?,?)", users)
    groups = [(f"bg{i}", f"Bulk Group {i} {SUBJECTS[i % 8]}", "A generated group used for the scale benchmark run.", SUBJECTS[i % 8], "public" if i % 5 else "private", f"BLK-{i:06d}", f"bu{i}", f"2026-09-{1 + i % 28:02d}T00:00:00.000Z") for i in range(2000)]
    conn.executemany("INSERT INTO study_groups (id, name, description, subject, visibility, invite_code, owner_id, created_at) VALUES (?,?,?,?,?,?,?,?)", groups)
    members = [(f"bm{i}_0", f"bg{i}", f"bu{i}", "owner", now) for i in range(2000)]
    n = 0
    for i in range(2000):
        for k in range(1, 9):
            members.append((f"bm{i}_{k}", f"bg{i}", f"bu{(i * 7 + k * 13) % 6000}", "member", now))
            n += 1
    seen, rows = set(), []
    for m in members:
        key = (m[1], m[2])
        if key not in seen:
            seen.add(key)
            rows.append(m)
    conn.executemany("INSERT INTO memberships (id, group_id, user_id, role, joined_at) VALUES (?,?,?,?,?)", rows)
    conn.executemany("INSERT INTO resources (id, group_id, uploaded_by, title, type, url, created_at) VALUES (?,?,?,?,'link','https://example.com/x',?)", [(f"br{i}", f"bg{i % 2000}", f"bu{i % 6000}", f"Bulk resource {i}", f"2026-09-{1 + i % 28:02d}T{i % 24:02d}:00:00.000Z") for i in range(10000)])
    conn.executemany("INSERT INTO resource_tags (resource_id, tag) VALUES (?,?)", [(f"br{i}", ["graphs", "dp", "sql", "notes"][i % 4]) for i in range(10000)])
    conn.executemany("INSERT INTO posts (id, group_id, author_id, title, body, created_at) VALUES (?,?,?,?,?,?)", [(f"bp{i}", f"bg{i % 2000}", f"bu{i % 6000}", f"Bulk post {i}", "Generated body text for the scale benchmark.", now) for i in range(4000)])
    # make the demo user a member of 40 bulk groups so /groups/mine and the dashboard have real work to do
    conn.executemany("INSERT OR IGNORE INTO memberships (id, group_id, user_id, role, joined_at) VALUES (?,?,?,?,?)", [(f"bd{i}", f"bg{i}", "u1", "member", now) for i in range(0, 200, 5)])
    conn.commit()
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users", "study_groups", "memberships", "resources", "posts")}
    conn.close()
    return counts


def main():
    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "bench.db")
    seed_database(db_path)
    app = create_app({"ENV": "development", "DATABASE": db_path, "RATE_LIMIT_ENABLED": False, "SECRET_KEY": "benchmark-secret-key-0123456789abcdef", "TESTING": True})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    port = server.server_port
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"
    s = requests.Session()

    # login cost (scrypt) is measured separately because it is deliberately slow
    login_times = []
    for _ in range(15):
        t, r = timed(s, "post", f"{base}/api/auth/login", json={"email": "demo@studysync.app", "password": "Password123"})
        assert r.status_code == 200
        login_times.append(t)
    token = r.json()["data"]["accessToken"]
    h = {"Authorization": f"Bearer {token}"}
    t_ref, _ = timed(s, "get", f"{base}/api/health")

    def sequential(cases):
        out = {}
        for label, method, url, kw in cases:
            times = []
            for _ in range(N):
                t, r = timed(s, method, base + url, headers=h, **kw)
                assert r.status_code < 400, (label, r.status_code, r.text[:200])
                times.append(t)
            out[label] = summarize(times)
        return out

    small_cases = [
        ("GET /api/health", "get", "/api/health", {}),
        ("GET /api/users/me", "get", "/api/users/me", {}),
        ("GET /api/users/me/dashboard", "get", "/api/users/me/dashboard", {}),
        ("GET /api/groups (discover)", "get", "/api/groups", {}),
        ("GET /api/groups?search=data", "get", "/api/groups?search=data", {}),
        ("GET /api/groups/mine", "get", "/api/groups/mine", {}),
        ("GET /api/groups/{id}", "get", "/api/groups/g1", {}),
        ("GET /api/groups/{id}/resources", "get", "/api/groups/g1/resources", {}),
        ("GET /api/groups/{id}/posts", "get", "/api/groups/g1/posts", {}),
        ("GET /api/posts/{id}", "get", "/api/posts/p1", {}),
        ("GET /api/sessions", "get", "/api/sessions", {}),
        ("GET /api/notifications", "get", "/api/notifications", {}),
        ("PUT /api/sessions/{id}/rsvp", "put", "/api/sessions/s1/rsvp", {"json": {"status": "going"}}),
    ]
    results = {"login_scrypt": summarize(login_times), "small_dataset": sequential(small_cases)}
    write_times = []
    for i in range(N):
        t, r = timed(s, "post", f"{base}/api/groups/g1/resources", headers=h, json={"title": f"Bench resource {i}", "type": "link", "url": "https://example.com/b", "tags": ["bench"]})
        assert r.status_code == 201
        write_times.append(t)
    results["small_dataset"]["POST /api/groups/{id}/resources (writes + notifications)"] = summarize(write_times)

    counts = bulk_load(db_path)
    scale_cases = [
        ("GET /api/groups (discover)", "get", "/api/groups", {}),
        ("GET /api/groups?search=graph&subject=Databases", "get", "/api/groups?search=group&subject=Databases", {}),
        ("GET /api/groups?sort=newest&page=50", "get", "/api/groups?sort=newest&page=50", {}),
        ("GET /api/groups/mine (40 groups)", "get", "/api/groups/mine", {}),
        ("GET /api/users/me/dashboard", "get", "/api/users/me/dashboard", {}),
        ("GET /api/groups/{id}/resources", "get", "/api/groups/bg0/resources", {}),
    ]
    results["scale_dataset"] = {"rows": counts, "endpoints": sequential(scale_cases)}

    # concurrency: 20 threads, 10 seconds, mixed reads
    paths = ["/api/users/me/dashboard", "/api/groups", "/api/groups/mine", "/api/groups/g1/resources", "/api/sessions", "/api/notifications", "/api/posts/p1", "/api/groups?search=data"]
    times, errors, stop = [], [0], time.time() + 10
    lock = threading.Lock()

    def worker(k):
        sess = requests.Session()
        i = k
        while time.time() < stop:
            t, r = timed(sess, "get", base + paths[i % len(paths)], headers=h)
            with lock:
                times.append(t)
                if r.status_code != 200:
                    errors[0] += 1
            i += 1

    threads = [threading.Thread(target=worker, args=(k,)) for k in range(20)]
    start = time.time()
    [t.start() for t in threads]
    [t.join() for t in threads]
    elapsed = time.time() - start
    results["concurrency"] = {"threads": 20, "seconds": round(elapsed, 1), "requests": len(times), "errors": errors[0], "requests_per_second": round(len(times) / elapsed, 1), **{k: v for k, v in summarize(times).items() if k != "n"}}
    results["db_size_mb_after_scale"] = round(os.path.getsize(db_path) / 1_000_000, 1)
    results["environment"] = {"python": sys.version.split()[0], "server": "werkzeug threaded dev server, single process", "note": "loopback, no network latency"}
    server.shutdown()

    (ROOT / "docs" / "benchmark.json").write_text(json.dumps(results, indent=2))
    print(f"{'Endpoint':58s} {'mean':>7s} {'p50':>7s} {'p95':>7s} {'p99':>7s}")
    for group in ("small_dataset",):
        for k, v in results[group].items():
            print(f"{k:58s} {v['mean']:7.2f} {v['p50']:7.2f} {v['p95']:7.2f} {v['p99']:7.2f}")
    print("-- scale dataset", counts)
    for k, v in results["scale_dataset"]["endpoints"].items():
        print(f"{k:58s} {v['mean']:7.2f} {v['p50']:7.2f} {v['p95']:7.2f} {v['p99']:7.2f}")
    print("login (scrypt)", results["login_scrypt"])
    print("concurrency", results["concurrency"])


if __name__ == "__main__":
    main()
