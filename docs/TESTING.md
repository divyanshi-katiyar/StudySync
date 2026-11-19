# Testing, debugging and optimization (Week 5)

This document explains how StudySync is tested, how to run every test, and what was optimized. The debugging story (bugs found, causes, fixes)
is in [DEBUGGING.md](DEBUGGING.md). Raw evidence (logs, profiles, coverage) is in [../logs/](../logs/README.md).

## 1. Quick start

```bash
# everything that can run on your machine, with a dated log in logs/
python scripts/run_all_tests.py            # add --quick to skip the slow checks, --full to include the mutation check

# or layer by layer
cd server && python -m unittest discover -s tests -t . -v      # 200 API tests
cd server && python scripts/coverage_report.py --fail-under 95   # line coverage (stdlib only)
python scripts/parity_check.py                                   # form rules == API rules
cd client && npm run test:integration                            # 28 client tests, plain Node
python scripts/e2e.py                                            # real client code vs real server
cd client && npm install && npm test                             # React tests (Vitest, jsdom)
python scripts/mutation_check.py                                 # do the tests notice deliberate bugs?
```

Requirements: Python 3.12 (3.10+ works for the tests; the coverage script uses 3.12's `sys.monitoring`), Node 20+. The API tests need only
Flask and PyJWT. Optional tools (`pytest`, `coverage.py`) are listed in `server/requirements-dev.txt`; `pytest` runs the same tests.

## 2. Test strategy

The project is tested as a pyramid: many fast unit tests at the bottom, fewer integration tests in the middle, a few end-to-end scenarios on top.
Different layers catch different mistakes, so none of them is redundant.

| Layer | What it tests | Tool | Count | Speed |
|---|---|---|---|---|
| Unit (server) | pure functions and small classes: validation rules, rate limiter, time helpers, config, event formatting, seed | `unittest` | 42 | instant |
| Unit (client) | utilities (format, validation, debounce, subjects) and the HTTP and live-update clients with a fake `fetch` | Node `node:test` | 28 | under 1 s |
| Unit (React hooks) | `useAsync`, `useDebounce`, `useForm`, `usePageTitle`, `useLiveUpdates`, `useLiveGroupReload` | Vitest + Testing Library | 24 new (+23 from Week 2) | seconds |
| Integration (server) | each endpoint through Flask's test client with a real temporary SQLite database: auth, groups, roles, content, sessions, notifications | `unittest` | 92 | 8 s |
| Security (server) | token attacks, access control sweeps, injection strings, headers, CORS, rate limits | `unittest` | 21 | 1 s |
| Real-time (server) | live events over a real socket: delivery, privacy, expiry, limits, rollback | `unittest` + real HTTP server | 14 | 9 s |
| Robustness (server) | hostile input, races between simultaneous requests, data integrity | `unittest` + threads | 18 | 1 s |
| Optimization guards | pooling, member-count triggers, migration, query plan | `unittest` | 11 | 1 s |
| Contract | every route is documented, and every documented route exists | `unittest` | 2 | instant |
| Cross-layer | client and server validation rules give identical verdicts (85 cases) and share subject colours | `scripts/parity_check.py` | 85 | 0.2 s |
| End to end | the real client modules against a freshly seeded real server: sign-in, live changes between two users, error mapping, reload, logout | Node + Python | 5 scenarios | 2 s |
| Test quality | 17 deliberate bugs in real code must make the tests fail (plus 5 for the hook tests) | `scripts/mutation_check.py` | 17 | 1 min |

Totals run in the environment where this was prepared: **200 server tests, 28 client tests, 5 end-to-end scenarios, 85 parity cases, 24 React hook tests**.

### Why these tests (rationale)

* **Unit tests** give fast, exact failures: when `clean_tags` breaks, one small test names it.
* **Integration tests** use a real database on purpose. Most bugs in this app are in the SQL, the constraints and the permission rules, which a mocked database would hide. Each test gets its own temporary database.
* **Security tests** are written from the attacker's side (forged tokens, `alg: none`, another group's ids, injection strings) rather than from the feature's side.
* **Real-time tests** run against a real HTTP server because Flask's test client cannot hold a stream open.
* **Robustness tests** exist because the happy-path tests had 94 % line coverage and still missed eight bugs (see DEBUGGING.md). They ask "what is the nastiest input or timing this code could meet?"
* **Parity check** exists because validation is written twice (forms and API). If the copies drift, users meet confusing errors or the API accepts what the form was meant to block.
* **End-to-end tests** run the same modules the interface uses, so they prove that the client's token refresh, error mapping and live updates work with the real API, not with a fake.
* **Mutation check** answers "would the tests complain if this line were wrong?" Coverage only says the line ran.

### Conventions
* Each test builds its own world (new database, new users) and cleans up; tests never depend on order.
* Test names say what must be true ("a refresh token can only be spent once even when two requests overlap").
* Races are tested twice: deterministically (a stale read is simulated with a mock) and with real threads.
* Waiting for live events uses polling with a deadline, never fixed sleeps, except to prove that something does *not* arrive.

## 3. Coverage

`server/scripts/coverage_report.py` measures line coverage with Python's `sys.monitoring` (no install needed):

| | Tests | Lines | Covered |
|---|---|---|---|
| Start of Week 5 (`logs/coverage-baseline.txt`) | 127 | 1,531 | **93.8 %** (seed.py 0 %) |
| End of Week 5 (`logs/coverage-after.txt`) | 200 | 1,581 | **100 %** |

Coverage is a floor, not a goal. 100 % of lines does not mean 100 % of behaviours: the eight server bugs found this week were in lines that were already "covered".
Branch coverage is not measured by this script; `coverage run --branch` does it if you install coverage.py.

## 4. Debugging techniques used

Full write-up in [DEBUGGING.md](DEBUGGING.md). In short: reproduce with a failing test first; log the failure before fixing (`logs/bugs-before-fix.txt`);
fix the root cause; keep the test as a regression test; look for the second-order effect of the fix; re-run everything. Techniques: adversarial inputs,
race reproduction with `Barrier`ed threads and with mocks that return stale reads, cross-layer comparison, `EXPLAIN QUERY PLAN`, `cProfile`, SQL statement tracing,
request ids in error logs, mutation checks, and a `DB_POOL=False` switch to turn an optimization off while hunting a bug.

## 5. Optimization summary

All figures: same script, same machine, before = the Week 4 code (`logs/profile-before*.txt`), after = Week 5 (`logs/profile-after*.txt`,
full table in `logs/optimization-summary.txt`). In-process profile (`server/scripts/profile_api.py`) removes network noise; the HTTP result uses `server/scripts/benchmark.py`.

| # | Finding (from the profile) | Change | Effect |
|---|---|---|---|
| 1 | Every request opened a SQLite connection, ran 3 PRAGMAs, and closed it with a WAL clean-up. The profile showed `connect` + `close` + PRAGMAs as the biggest costs after the queries themselves (22,500 statements for 3,600 requests, 10,800 of them PRAGMAs; about 0.7 ms of a 1.5 to 2.2 ms request) | Connection pool (`db.py`); `journal_mode=WAL` set once at start-up; rollback of unfinished transactions on release; `DB_POOL=False` to switch it off | Health check 1.51 -> 0.83 ms (the saving applies to every request) |
| 2 | Discovery sorted all public groups by counting each group's members on every request (5.1 ms with 2,008 groups) | `member_count` column kept exact by two database triggers; index `(visibility, member_count DESC, name)`; old databases are migrated and back-filled automatically | Discover **5.12 -> 1.41 ms (-72 %)** on the large dataset; query plan has no temporary sort |
| 3 | Dashboard ran three COUNT queries one after another | One statement with three sub-selects | 6 -> 4 SQL statements, 2.38 -> 1.58 ms |
| 4 | Identical GET requests fire together (React StrictMode runs effects twice in development; two components can ask for the same list) | Client shares one in-flight call per identical GET and hands each caller its own copy; writes are never merged | Fewer requests in development (verified by count in Node tests; not measured in a browser) |
| 5 | One user action produces several live events; pages reloaded once per event | Debounced reloads (150 ms) for live updates | One reload per burst (hook tests prove it); not measured in a browser |
| 6 | Dead code | `db.run` helper removed | Smaller surface |

| Result | Before | After |
|---|---|---|
| All 12 read endpoints, demo data (sum of mean ms) | 24.22 | 15.07 (**-38 %**) |
| All 12 read endpoints, large data (sum of mean ms) | 28.69 | 16.30 (**-43 %**) |
| Throughput, 20 concurrent clients over HTTP | 220 requests/s | **469 requests/s** (2.1x) |
| Response time under that load, p95 | 167 ms | **82 ms** |
| Errors under load | 0 | 0 |

Honest limits: the numbers are from one machine over loopback with the development server; the connection pool's gain depends on the server (it helps most when
requests are short, as here). Front-end optimizations 4 and 5 are verified by tests of the code, not by a browser measurement, because no browser build was possible in the
environment used; re-run Lighthouse after `npm run build` to measure them. Optimizations were kept only when the profile pointed at them and a test proved behaviour unchanged.

## 6. What was not verified here

* The 23 existing Vitest tests and the production build could not be run (no network to install React tooling). The 24 new hook tests were run in headless Chromium through a small
  Vitest/Testing-Library stand-in with React 19 (the project uses 18.3), and were mutation-checked there (5 of 5 deliberate hook bugs caught). Run `npm test` to confirm under real Vitest.
* `.github/workflows/ci.yml` is written for GitHub Actions but was not executed.
* Page-level React tests (rendering whole screens against the live API) are not included; the end-to-end layer covers the data flow, not the pixels.
