"""Profile the API to find bottlenecks (Week 5).

    python scripts/profile_api.py                 # prints a report and writes logs/profile.txt
    python scripts/profile_api.py --scale         # same, on the large dataset (18,000 memberships, 10,000 resources)

For each endpoint it reports: time per request, number of SQL statements per request, and (with cProfile) where the Python time goes.
Runs in-process with Flask's test client, so numbers exclude network and server overhead and isolate the application's own cost.
"""
import argparse
import cProfile
import io
import os
import pstats
import sqlite3
import statistics
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark import bulk_load  # noqa: E402
from studysync import create_app, db as dbmod  # noqa: E402
from studysync.seed import seed_database  # noqa: E402

ENDPOINTS = [
    ("GET /api/health", "/api/health"),
    ("GET /api/users/me", "/api/users/me"),
    ("GET /api/users/me/dashboard", "/api/users/me/dashboard"),
    ("GET /api/groups (discover)", "/api/groups"),
    ("GET /api/groups?search=group", "/api/groups?search=group&subject=Databases"),
    ("GET /api/groups/mine", "/api/groups/mine"),
    ("GET /api/groups/g1", "/api/groups/g1"),
    ("GET /api/groups/g1/resources", "/api/groups/g1/resources"),
    ("GET /api/groups/g1/posts", "/api/groups/g1/posts"),
    ("GET /api/posts/p1", "/api/posts/p1"),
    ("GET /api/sessions", "/api/sessions"),
    ("GET /api/notifications", "/api/notifications"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", action="store_true")
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--out", default=str(ROOT.parent / "logs" / "profile.txt"))
    args = ap.parse_args()

    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "profile.db")
    seed_database(path)
    if args.scale:
        bulk_load(path)
    app = create_app({"ENV": "testing", "DATABASE": path, "RATE_LIMIT_ENABLED": False})
    c = app.test_client()
    with app.app_context():
        from studysync.security import create_access_token
        token = create_access_token("u1")[0]
    h = {"Authorization": f"Bearer {token}"}

    # count SQL statements per request by tracing every connection the app opens
    counter = {"n": 0}
    real_connect = dbmod.connect

    def traced_connect(p):
        conn = real_connect(p)
        conn.set_trace_callback(lambda stmt: counter.__setitem__("n", counter["n"] + 1))
        return conn

    dbmod.connect = traced_connect

    out = [f"Dataset: {'large' if args.scale else 'demo'}   requests per endpoint: {args.n}", "",
           f"{'Endpoint':34s} {'ms/request':>10s} {'p95 ms':>8s} {'SQL stmts':>10s}"]
    profiler = cProfile.Profile()
    for label, url in ENDPOINTS:
        c.get(url, headers=h)  # warm up
        times, stmts = [], []
        for _ in range(args.n):
            counter["n"] = 0
            t = time.perf_counter()
            profiler.enable()
            r = c.get(url, headers=h)
            profiler.disable()
            times.append((time.perf_counter() - t) * 1000)
            stmts.append(counter["n"])
            assert r.status_code == 200, (label, r.status_code)
        times.sort()
        out.append(f"{label:34s} {statistics.mean(times):10.2f} {times[int(0.95 * (len(times) - 1))]:8.2f} {statistics.median(stmts):10.0f}")
    buf = io.StringIO()
    pstats.Stats(profiler, stream=buf).sort_stats("tottime").print_stats(18)
    body = buf.getvalue()
    cut = body.index("ncalls") if "ncalls" in body else 0
    out += ["", "Where the Python time goes across all requests above (cProfile, sorted by own time):", body[cut:]]
    text = "\n".join(out)
    print(text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text)


if __name__ == "__main__":
    main()
