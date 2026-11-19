# Logs and evidence (Week 5)

Every file here was produced by a command in this repository; nothing is hand-written. "Before" files come from the Week 4 code, "after" files from the Week 5 code.

| File | What it shows | Produced by |
|---|---|---|
| `bugs-before-fix.txt` | The robustness tests failing: 12 of 17 fail, with tracebacks (`RecursionError`, `OverflowError`, `IntegrityError`, 6 refreshes all succeeding) | `python -m unittest -v tests.test_robustness` on the unfixed code |
| `bugs-after-fix.txt` | The same 17 tests passing after the fixes | same command, fixed code |
| `parity-before-fix.txt` | 21 differences between the form rules and the API rules | `python scripts/parity_check.py` before the fixes |
| `parity-after-fix.txt` | 85 cases, 0 mismatches, subjects and colours identical | same, after |
| `coverage-baseline.txt` | 127 tests, 93.8 % line coverage, with the lines that never ran | `python scripts/coverage_report.py` at the start of Week 5 |
| `coverage-after.txt`, `coverage.txt` | 200 tests, 100 % line coverage | same, at the end |
| `profile-before.txt`, `profile-before-scale.txt` | Time per request, SQL statements per request and the cProfile hot spots on demo data and on a large dataset (Week 4 code) | `python scripts/profile_api.py [--scale]` |
| `profile-after.txt`, `profile-after-scale.txt` | The same after the optimizations | same |
| `optimization-summary.txt` | Before/after table for all 12 endpoints, plus the HTTP load comparison | built from the profile files and the two benchmark files |
| `benchmark-before.json` | Over-HTTP benchmark of the Week 4 code (`docs/benchmark.json` in `server/` is the Week 5 result) | `python server/scripts/benchmark.py` |
| `mutation-check.txt` | 17 deliberate bugs in server and client code: all caught by the tests | `python scripts/mutation_check.py` |
| `hook-mutation-check.txt` | 5 deliberate bugs in React hooks: all caught by the hook tests | run in the Chromium test harness |
| `react-hook-tests-harness.txt` | The 24 React hook tests passing in headless Chromium (stand-in for Vitest, React 19) | harness (not shipped; use `npm test`) |
| `test-run-*.txt`, `latest-test-run.txt` | Dated summary of every layer in one run | `python scripts/run_all_tests.py --full` |

Server error logs now include the request id, for example
`Unhandled error on GET /api/groups/mine [request trace-abc-123]: disk exploded` followed by the traceback; the same id is returned in the `X-Request-Id` response header.
