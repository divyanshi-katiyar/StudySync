"""Full-stack check without a browser: start the real API on a fresh demo database, then run the real client code against it.

    python scripts/e2e.py            (needs Python 3.10+ with the server requirements installed, and Node 20+)

1. creates a temporary seeded database and starts the Flask server on a free port
2. runs client/tests-node/e2e.test.mjs, which drives the front end's own HTTP and live-update modules
3. stops the server and exits with the test result
"""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER, CLIENT = ROOT / "server", ROOT / "client"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> int:
    tmp = tempfile.mkdtemp()
    port = free_port()
    env = {**os.environ, "STUDYSYNC_DATABASE": os.path.join(tmp, "e2e.db"), "PORT": str(port), "STUDYSYNC_ENV": "development"}
    subprocess.run([sys.executable, "manage.py", "reset"], cwd=SERVER, env=env, check=True, stdout=subprocess.DEVNULL)
    server = subprocess.Popen([sys.executable, "run.py"], cwd=SERVER, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}/api"
        for _ in range(50):
            try:
                urllib.request.urlopen(url + "/health", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        else:
            print("server did not start")
            return 1
        tests = sorted(str(p.relative_to(CLIENT)) for p in (CLIENT / "tests-node").glob("*.test.mjs"))
        result = subprocess.run(["node", "--test", "--test-timeout=20000", *tests], cwd=CLIENT, env={**os.environ, "STUDYSYNC_API_URL": url})
        return result.returncode
    finally:
        server.terminate()
        server.wait(timeout=5)


if __name__ == "__main__":
    sys.exit(main())
