"""Measure live-update latency and connection capacity.

    python scripts/benchmark_live.py        (writes docs/benchmark_live.json)

1. Latency: N members of one group each hold an open stream; one member shares a resource; we time how long each stream takes to
   receive the notification after the POST was sent (the POST's own response time is reported separately).
2. Capacity: opens many streams at once on the threaded development server and checks that normal requests stay fast.
Lab numbers on one machine over loopback.
"""
import json
import logging
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
logging.getLogger("werkzeug").setLevel(logging.ERROR)

from studysync import create_app  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    app = create_app({"ENV": "testing", "DATABASE": os.path.join(tmp, "b.db"), "SSE_HEARTBEAT_SECONDS": 15, "SSE_MAX_STREAMS_PER_USER": 5, "RATE_LIMIT_ENABLED": False})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"

    def register(i):
        r = requests.post(f"{base}/api/auth/register", json={"name": f"Bench User {i}", "email": f"b{i}@example.com", "password": "Password123"})
        return r.json()["data"]["accessToken"], r.json()["data"]["user"]["id"]

    N = 40
    users = [register(i) for i in range(N)]
    owner_token = users[0][0]
    h = {"Authorization": f"Bearer {owner_token}"}
    g = requests.post(f"{base}/api/groups", headers=h, json={"name": "Latency group", "description": "Group used for the live latency benchmark.", "subject": "Networks", "visibility": "public"}).json()["data"]
    for token, _ in users[1:]:
        requests.post(f"{base}/api/groups/{g['id']}/join", headers={"Authorization": f"Bearer {token}"})

    received, ready = {}, threading.Barrier(N)  # N-1 listeners + the main thread

    def listen(idx, token):
        r = requests.get(f"{base}/api/stream", headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=60)
        event, started = None, False
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("event:"):
                event = line[6:].strip()
            elif line and line.startswith("data:") and event:
                if event == "ready" and not started:
                    started = True
                    ready.wait(10)
                elif event == "notification":
                    received[idx] = time.perf_counter()
                    r.close()
                    return
                event = None

    threads = [threading.Thread(target=listen, args=(i, users[i][0]), daemon=True) for i in range(1, N)]
    [t.start() for t in threads]
    ready.wait(15)
    time.sleep(0.3)
    sent = time.perf_counter()
    resp = requests.post(f"{base}/api/groups/{g['id']}/resources", headers=h, json={"title": "Latency probe", "type": "link", "url": "https://example.com/p", "tags": []})
    post_ms = (time.perf_counter() - sent) * 1000
    [t.join(10) for t in threads]
    lat = sorted((t - sent) * 1000 for t in received.values())
    result = {
        "latency": {
            "listeners": N - 1, "delivered": len(lat), "post_response_ms": round(post_ms, 1),
            "push_ms": {"min": round(lat[0], 1), "median": round(statistics.median(lat), 1), "p95": round(lat[int(0.95 * (len(lat) - 1))], 1), "max": round(lat[-1], 1)},
        }
    }

    # capacity: many open streams, then time ordinary requests
    open_streams = []
    extra = [register(1000 + i) for i in range(60)]
    for token, _ in extra:
        r = requests.get(f"{base}/api/stream", headers={"Authorization": f"Bearer {token}"}, stream=True, timeout=30)
        open_streams.append(r)
    times = []
    for _ in range(100):
        t = time.perf_counter()
        requests.get(f"{base}/api/users/me/dashboard", headers=h)
        times.append((time.perf_counter() - t) * 1000)
    times.sort()
    result["capacity"] = {"open_streams": len(open_streams), "hub_connections": app.extensions["hub"].count(), "dashboard_ms": {"median": round(statistics.median(times), 1), "p95": round(times[94], 1)}}
    for r in open_streams:
        r.close()
    result["environment"] = {"python": sys.version.split()[0], "server": "werkzeug threaded dev server", "note": "one machine, loopback"}
    server.shutdown()
    (ROOT / "docs" / "benchmark_live.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
