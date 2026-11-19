"""Run every test layer and write a dated log.

    python scripts/run_all_tests.py             all layers that can run on this machine
    python scripts/run_all_tests.py --quick     skip the slower checks (end-to-end, mutation check)
    python scripts/run_all_tests.py --full      also run the mutation check

Layers (each is skipped with a clear note if its tool is missing):
  1. server tests         python unittest, 190+ tests, unit + integration + security + live events
  2. server coverage      line coverage with a floor of 95 % (fails below it)
  3. client/server parity form rules and subject colours must match the API's
  4. client Node tests    HTTP client, live-update client, utilities (no packages needed)
  5. end-to-end           real client code against a real freshly seeded server
  6. React tests          Vitest (hooks, pages): needs `npm install` first
  7. mutation check       deliberately breaks 17 lines and expects tests to fail   (--full only)

Output goes to the screen and to logs/test-run-<timestamp>.txt (and logs/latest-test-run.txt).
"""
import argparse
import datetime
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER, CLIENT, LOGS = ROOT / "server", ROOT / "client", ROOT / "logs"
PY = sys.executable


def run(cmd, cwd, timeout=900):
    t = time.time()
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr), time.time() - t
    except subprocess.TimeoutExpired:
        return 124, "timed out", time.time() - t
    except FileNotFoundError as err:
        return 127, str(err), time.time() - t


def summary(text, pattern, default=""):
    m = re.findall(pattern, text)
    return m[-1] if m else default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--full", action="store_true")
    args = ap.parse_args()
    node = shutil.which("node")
    npm = shutil.which("npm")
    layers = [
        ("Server tests (unittest)", [PY, "-m", "unittest", "discover", "-s", "tests", "-t", "."], SERVER, lambda o: summary(o, r"Ran (\d+) tests") + " tests, " + ("OK" if "\nOK" in o else "FAILED"), True),
        ("Server line coverage (floor 95 %)", [PY, "scripts/coverage_report.py", "--fail-under", "95", "--out", str(LOGS / "coverage.txt")], SERVER, lambda o: "total " + summary(o, r"TOTAL\s+\d+\s+\d+\s+([\d.]+%)"), sys.version_info >= (3, 12)),
        ("Client/server validation parity", [PY, "scripts/parity_check.py"], ROOT, lambda o: o.strip().splitlines()[0] if o.strip() else "", bool(node)),
        ("Client Node tests", [node or "node", "--test", "--test-timeout=20000", "tests-node/http.test.mjs", "tests-node/realtime.test.mjs", "tests-node/utils.test.mjs"], CLIENT, lambda o: summary(o, r"# pass (\d+)") + " passed, " + summary(o, r"# fail (\d+)") + " failed", bool(node)),
        ("End-to-end (real client + real server)", [PY, "scripts/e2e.py"], ROOT, lambda o: summary(o, r"# pass (\d+)") + " passed, " + summary(o, r"# fail (\d+)") + " failed", bool(node) and not args.quick),
        ("React tests (Vitest)", [npm or "npm", "test"], CLIENT, lambda o: summary(o, r"Tests\s+(.*)"), bool(npm) and (CLIENT / "node_modules").exists()),
        ("Mutation check (do tests notice bugs?)", [PY, "scripts/mutation_check.py"], ROOT, lambda o: summary(o, r"(\d+ of \d+ deliberate bugs[^\n]*)"), bool(node) and args.full),
    ]
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    lines = [f"StudySync test run {stamp}", f"Python {sys.version.split()[0]}, Node {subprocess.run([node, '-v'], capture_output=True, text=True).stdout.strip() if node else 'not found'}", ""]
    failed = False
    for name, cmd, cwd, parse, enabled in layers:
        if not enabled:
            why = ("needs Node" if "Node" in name or "parity" in name or "End-to-end" in name else
                   "run `npm install` in client/ first" if "React" in name else
                   "needs Python 3.12 (use coverage.py on older versions)" if "coverage" in name else
                   "slow; add --full to run it")
            lines.append(f"SKIP  {name:44s} {why}")
            print(lines[-1])
            continue
        code, out, secs = run(cmd, cwd)
        status = "PASS" if code == 0 else "FAIL"
        failed |= code != 0
        lines.append(f"{status}  {name:44s} {parse(out):38s} {secs:6.1f}s")
        print(lines[-1])
        if code != 0:
            lines.append("      --- output (last 40 lines) ---")
            lines += ["      " + l for l in out.strip().splitlines()[-40:]]
    lines += ["", "RESULT: " + ("SOME LAYERS FAILED" if failed else "ALL LAYERS PASSED")]
    LOGS.mkdir(exist_ok=True)
    text = "\n".join(lines) + "\n"
    (LOGS / f"test-run-{stamp}.txt").write_text(text)
    (LOGS / "latest-test-run.txt").write_text(text)
    print("\n" + lines[-1])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
