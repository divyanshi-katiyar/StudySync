"""Do the tests notice when the code is broken?  (a small, hand-picked "mutation test")

    python scripts/mutation_check.py          exits 1 if any deliberate bug goes unnoticed

For each entry the script (1) changes one line of real code to introduce a realistic bug, (2) runs the tests that should catch it,
(3) expects them to FAIL, and (4) always restores the file. A mutation that the tests do not catch means a gap in the test suite.
Coverage says which lines ran; this checks that the tests would actually complain if the line were wrong.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVER, CLIENT = ROOT / "server", ROOT / "client"
PY = [sys.executable, "-m", "unittest"]
NODE = ["node", "--test", "--test-timeout=20000"]

M = [  # (description, file, old text, new text, command, working directory)
    ("refresh token no longer claimed atomically (rotation race)", SERVER / "studysync/security.py", "AND revoked_at IS NULL\", (now_iso(), row[\"id\"])).rowcount", "\", (now_iso(), row[\"id\"])).rowcount or 1", PY + ["tests.test_robustness"], SERVER),
    ("losing a join race crashes again", SERVER / "studysync/services/groups.py", "    except sqlite3.IntegrityError:\n        raise ApiError(409, \"You are already in this group.\")", "    except ZeroDivisionError:\n        raise ApiError(409, \"You are already in this group.\")", PY + ["tests.test_robustness"], SERVER),
    ("leaving a group keeps the RSVPs", SERVER / "studysync/services/groups.py", "        _forget_rsvps(db, group_id, user_id)\n", "", PY + ["tests.test_robustness"], SERVER),
    ("far-future dates overflow again", SERVER / "studysync/utils.py", "    except (OverflowError, ValueError):\n        return None", "    except ZeroDivisionError:\n        return None", PY + ["tests.test_robustness"], SERVER),
    ("invisible-character names accepted", SERVER / "studysync/validation.py", "    return lambda v: \"\" if visible(v) else", "    return lambda v: \"\" if text(v) else", PY + ["tests.test_robustness", "tests.test_units"], SERVER),
    ("private group readable by outsiders", SERVER / "studysync/services/groups.py", "    if row[\"visibility\"] == \"private\" and row[\"my_role\"] is None:", "    if False:", PY + ["tests.test_security", "tests.test_groups"], SERVER),
    ("owner check removed from group deletion", SERVER / "studysync/services/groups.py", "    if membership[\"role\"] != \"owner\":\n        raise ApiError(403, \"Only the owner can delete a group.\")", "    if False:\n        pass", PY + ["tests.test_groups"], SERVER),
    ("member counter trigger removed", SERVER / "studysync/schema.sql", "  UPDATE study_groups SET member_count = member_count + 1 WHERE id = NEW.group_id;", "  SELECT 1;", PY + ["tests.test_optimizations"], SERVER),
    ("events sent for failed requests", SERVER / "studysync/realtime.py", "    if status_code < 400:", "    if True:", PY + ["tests.test_realtime"], SERVER),
    ("stream never ends at token expiry", SERVER / "studysync/realtime.py", "            if remaining <= 0:", "            if False:", PY + ["tests.test_realtime"], SERVER),
    ("client sends writes twice after a failure", CLIENT / "src/api/http.js", "if (method !== 'GET' || !transient(err)) throw err", "if (!transient(err)) throw err", NODE + ["tests-node/http.test.mjs"], CLIENT),
    ("identical GETs no longer share one call", CLIENT / "src/api/http.js", "    if (method !== 'GET') return callWithRetry(method, path, opts)", "    return callWithRetry(method, path, opts)", NODE + ["tests-node/http.test.mjs"], CLIENT),
    ("client forgets to refresh an expired token", CLIENT / "src/api/http.js", "      if (err.status !== 401) throw err\n      await refresh() // the access token expired", "      throw err\n      await refresh() // the access token expired", NODE + ["tests-node/http.test.mjs"], CLIENT),
    ("live client never reconnects", CLIENT / "src/api/realtime.js", "      await sleep(backoffMs[Math.min(attempt, backoffMs.length - 1)])\n      attempt += 1", "      return", NODE + ["tests-node/realtime.test.mjs"], CLIENT),
    ("notification event type clobbered by its own type", CLIENT / "src/api/realtime.js", "message.event === 'notification' ? { type: 'notification', notification: message.data } : { type: message.event, ...message.data }", "{ type: message.event, ...message.data }", NODE + ["tests-node/realtime.test.mjs"], CLIENT),
    ("client counts emoji as two characters", CLIENT / "src/utils/validation.js", "const size = (v) => Array.from(v).length", "const size = (v) => v.length", NODE + ["tests-node/utils.test.mjs"], CLIENT),
    ("debounce fires on every call", CLIENT / "src/utils/debounce.js", "    clearTimeout(timer)\n    timer = setTimeout(() => {", "    timer = setTimeout(() => {", NODE + ["tests-node/utils.test.mjs"], CLIENT),
]


def main():
    escaped, lines = [], []
    for desc, path, old, new, cmd, cwd in M:
        original = path.read_text()
        if original.count(old) != 1:
            lines.append(f"SKIPPED  {desc}  (could not find the line to change in {path.name}; update the script)")
            escaped.append(desc)
            continue
        try:
            path.write_text(original.replace(old, new))
            result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=240)
        finally:
            path.write_text(original)  # always restore
        caught = result.returncode != 0
        lines.append(f"{'CAUGHT ' if caught else 'MISSED '}  {desc}   [{path.name}]")
        if not caught:
            escaped.append(desc)
    print("\n".join(lines))
    print(f"\n{len(M) - len(escaped)} of {len(M)} deliberate bugs were caught by the tests")
    return 1 if escaped else 0


if __name__ == "__main__":
    sys.exit(main())
