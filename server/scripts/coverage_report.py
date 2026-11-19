"""Line-coverage report for the API test suite, using only the standard library (Python 3.12+ sys.monitoring).

    python scripts/coverage_report.py                 # run all tests, print a table, write logs/coverage.txt
    python scripts/coverage_report.py --fail-under 90 # exit 1 if total line coverage is below 90 %

Why not coverage.py: it is not installed in every environment (and this project has no network-installed dev tools by default).
`pip install coverage` and `coverage run -m unittest discover -s tests -t .` give the same numbers plus branch coverage; see docs/TESTING.md.
Counts "executable lines" as the lines that the bytecode of each module maps to, so docstrings and blank lines are ignored.
"""
import argparse
import sys
import threading
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "studysync"
sys.path.insert(0, str(ROOT))

mon = sys.monitoring
TOOL = mon.COVERAGE_ID
hits: dict[str, set[int]] = {}
lock = threading.Lock()


def on_line(code: types.CodeType, line: int):
    filename = code.co_filename
    if filename.startswith(str(PKG)):
        with lock:
            hits.setdefault(filename, set()).add(line)
    return mon.DISABLE  # each line only needs to be seen once; disabling keeps the run fast


def executable_lines(path: Path) -> set[int]:
    code = compile(path.read_text(), str(path), "exec")
    lines, stack = set(), [code]
    while stack:
        c = stack.pop()
        lines.update(ln for _, _, ln in c.co_lines() if ln)
        stack.extend(k for k in c.co_consts if isinstance(k, types.CodeType))
    return lines


def compress(nums):
    out, start, prev = [], None, None
    for n in sorted(nums):
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}-{prev}" if start != prev else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}-{prev}" if start != prev else str(start))
    return ",".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fail-under", type=float, default=0)
    ap.add_argument("--out", default=str(ROOT.parent / "logs" / "coverage.txt"))
    args = ap.parse_args()

    mon.use_tool_id(TOOL, "studysync-coverage")
    mon.register_callback(TOOL, mon.events.LINE, on_line)
    mon.set_events(TOOL, mon.events.LINE)

    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))
    result = unittest.TextTestRunner(verbosity=0, stream=open("/dev/null", "w") if sys.platform != "win32" else sys.stderr).run(suite)
    mon.set_events(TOOL, 0)

    rows, total_exec, total_hit = [], 0, 0
    for path in sorted(PKG.rglob("*.py")):
        ex = executable_lines(path)
        if not ex:
            continue
        got = hits.get(str(path), set()) & ex
        missing = ex - got
        total_exec += len(ex)
        total_hit += len(got)
        rows.append((str(path.relative_to(ROOT)), len(ex), len(missing), 100 * len(got) / len(ex), compress(missing)))

    lines = [f"Tests run: {result.testsRun}, failures: {len(result.failures)}, errors: {len(result.errors)}", "",
             f"{'File':44s} {'Lines':>6s} {'Miss':>5s} {'Cover':>7s}  Missing lines"]
    for name, n, miss, pct, missing in rows:
        lines.append(f"{name:44s} {n:6d} {miss:5d} {pct:6.1f}%  {missing}")
    total = 100 * total_hit / total_exec
    lines += ["-" * 80, f"{'TOTAL':44s} {total_exec:6d} {total_exec - total_hit:5d} {total:6.1f}%"]
    text = "\n".join(lines)
    print(text)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text + "\n")
    if not result.wasSuccessful() or total < args.fail_under:
        sys.exit(1)


if __name__ == "__main__":
    main()
