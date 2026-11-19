# Debugging report and lessons learned (Week 5)

## 1. Process

1. **Find** bugs on purpose: write tests from the point of view of a hostile user and of a slow, busy server (`server/tests/test_robustness.py`), and compare the two copies of the validation rules (`scripts/parity_check.py`).
2. **Record** the failure before touching the code. The failing output is saved in `logs/bugs-before-fix.txt` and `logs/parity-before-fix.txt`.
3. **Explain** the root cause (not just the symptom).
4. **Fix** the cause, in the smallest place that fixes every path that has the problem.
5. **Keep** the failing test as a regression test, and save the passing output (`logs/bugs-after-fix.txt`, `logs/parity-after-fix.txt`).
6. **Look for the side effect** of the fix (two of the fixes below caused a new problem that was found by thinking, then covered by a test).
7. **Re-run everything** (`python scripts/run_all_tests.py --full`) and check with the mutation check that the new tests really fail when the fix is removed.

Tools: `unittest` with `threading.Barrier` (simultaneous requests), `unittest.mock` (to replay "the other request saw stale data" deterministically), cProfile, SQL statement tracing,
`EXPLAIN QUERY PLAN`, a small line-coverage tool, and a headless browser for React hook tests.

## 2. Bugs found and fixed

Starting point: 127 server tests passing, 93.8 % line coverage. The new robustness tests made **12 assertions fail across 8 distinct bugs** the first time they ran.

| ID | Severity | Symptom | Evidence (before) |
|---|---|---|---|
| B1 | Medium | A request body nested 60,000 levels deep crashed the request with a 500 | `RecursionError: maximum recursion depth exceeded while decoding a JSON array` |
| B2 | Medium | Scheduling a session on `9999-12-31` (or year 1 with an offset) returned a 500 | `OverflowError: date value out of range`; `500 != 422` |
| B3 | **High** | Joining a group twice at the same moment gave 500 for the loser; with 8 simultaneous joins, **7 of 8 got a 500** | `[200, 500, 500, 500, 500, 500, 500, 500] != [200, 409, ...]`; 9 x `sqlite3.IntegrityError: UNIQUE constraint failed: memberships.group_id, memberships.user_id` |
| B4 | **High (security)** | One refresh token could be spent several times at once: **6 simultaneous refreshes all succeeded**, creating 6 live tokens, so refresh-token rotation and theft detection did not work under concurrency | `AssertionError: 6 != 1 : [200, 200, 200, 200, 200, 200]` |
| B5 | Medium | People who left (or were removed from) a group still counted as "going" or "maybe" for its sessions | `AssertionError: 2 != 1` |
| B6 | Low | A group name made only of zero-width characters (looks blank) was accepted | `201 != 422 : '\u200b\u200b\u200b\u200b'` |
| B7 | Low | New lines and NUL characters were accepted inside names and emails | `201 != 422 : ('name', 'Alex\nRao')` |
| B8 | Medium | `zoe\u0301@example.com` and `zo\u00e9@example.com` (the same address spelled two ways in Unicode) could register as two accounts | `201 != 409` |

### Root causes and fixes

* **B1** `request.get_json(silent=True)` only silences `ValueError`; a deep body raises `RecursionError`. *Fix:* catch it in `json_body()` and answer 400.
* **B2** Python cannot convert the far ends of the calendar to UTC. *Fix:* `parse_iso` returns "invalid" when the conversion overflows, and a sane window (not more than two years ahead) was added to the session rules.
* **B3** "check if already a member, then insert" is two steps; two requests can both pass the check. The unique index correctly stopped the second insert, but the error was not handled. *Fix:* turn the `IntegrityError` into the normal 409 (for join and join-by-code). The database constraint stays the real guard.
* **B4** The code read the token row, then revoked it with an unconditional `UPDATE`; two requests could both read "unused". *Fix:* claim the token atomically with `UPDATE ... WHERE id = ? AND revoked_at IS NULL` and accept only the request whose update changed exactly one row.
  * *Side effect found by reasoning:* the losing request answered 401 **and cleared the cookie**, which would delete the winner's new cookie and sign the user out when two tabs refreshed together. *Fix:* a lost race keeps the cookie; genuine reuse long after rotation (theft) still clears it. Covered by `CookieAfterLostRaceTests`.
* **B5** RSVPs live in their own table and nothing removed them when membership ended. *Fix:* delete that person's RSVPs for the group's sessions on leave and on removal (same transaction).
* **B6/B7** `str.strip()` does not remove zero-width or control characters. *Fix:* `visible()` drops control and format characters before "not empty / long enough" checks; a `single_line` rule rejects control characters in names, titles and emails.
* **B8** Emails were only lower-cased. *Fix:* Unicode-normalise (NFKC) then lower-case, for register and login.
  * *Side effect:* the Week 3 session test used the year 2099, which the new two-year rule rejects; the test was updated. Later the end-to-end test failed for the same reason (it scheduled a session in 2031) and was fixed: the cross-layer test caught an incompatibility between two weeks' work.

## 3. Client/server drift found by the parity check

`scripts/parity_check.py` runs 85 inputs through the form rules (Node) and the API rules (Python). First run: **21 mismatches** (`logs/parity-before-fix.txt`). After the fixes: **0** (`logs/parity-after-fix.txt`).

| Group | Mismatch | Fix |
|---|---|---|
| Characters | The form counted an emoji as 2 characters (JavaScript counts UTF-16 units), the API as 1 | Count code points in the form |
| Invisible text | The form accepted zero-width-only text that the API rejects | Same `visible` rule in both |
| One-line fields | The form had no "single line" rule | Added `singleLine` to the form |
| Length limits | The form had no upper limit for email (254), password (128), URL (2048) | Limits added to the form |
| Passwords | The API counted Arabic-Indic digits as digits (Python `\d` is Unicode) and rejected a password containing a line break; the form did the opposite | API: ASCII digits only, any character allowed; form matches |
| URLs | The API accepted `https://exa mple.com` and control characters; the form accepted `http:/x`, `http:///x`, `https:\\x` | API rejects whitespace and control characters; form requires `http(s)://host` shape |

## 4. Performance debugging

Profiling the API (`server/scripts/profile_api.py`, results in `logs/profile-before.txt`) showed that **most of a 2 ms request was not the query**: connecting to SQLite,
three PRAGMAs and closing the connection cost about 0.7 ms of a 1.5 to 2.2 ms request. A second profile on a large dataset showed discovery at 5.1 ms because every request counted
members for every public group before sorting. The fixes and their measured effect are in [TESTING.md](TESTING.md#5-optimization-summary); the query plans were checked with
`EXPLAIN QUERY PLAN` (the popular sort is now served by an index with no temporary sort), and each optimization has a test that fails if it is removed or wrong
(`tests/test_optimizations.py`, including a randomised 250-operation check that the member counter always equals the real count).

Debugging aids added to the product: error logs now carry the method, path and **request id** (`Unhandled error on GET /api/groups/mine [request trace-abc-123]: ...` followed by the traceback), and the same id is returned in the `X-Request-Id` response header, so a user report can be matched to a log line; `DB_POOL=False` turns the connection pool off.

## 5. Gaps found in the tests themselves (mutation check)

The first mutation run caught 15 of 17 deliberate bugs. The two it missed showed real gaps:
1. `required()` ignoring invisible characters went unnoticed because another rule happened to catch the same input. *Fix:* a direct unit test.
2. Nothing proved that live events from a *rolled-back* change are never sent. *Fix:* a test that makes the transaction fail after the events were queued and checks nobody hears about it.

Final result: **17 of 17** (`logs/mutation-check.txt`) and 5 of 5 for the React hook tests (`logs/hook-mutation-check.txt`).

## 6. Lessons learned

1. **Coverage is not correctness.** 94 % line coverage and 127 passing tests still hid eight bugs. Tests written from an attacker's or a race's point of view found them in an afternoon.
2. **Anything done in two steps can be interleaved.** "Check, then act" (join, refresh) needs the database to enforce the rule, and the code to treat losing the race as a normal outcome.
3. **A fix can create a new bug.** The refresh fix could have logged users out; ask "who else is affected by this change?" before closing a bug.
4. **Duplicate rules drift.** Anything written twice (validation, subject colours) needs a test that compares the copies.
5. **Measure before optimizing.** The profile contradicted the obvious guess (slow queries): connection handling was the bigger cost. The biggest single win (discovery, -72 %) came from reading a query plan, not from tuning code.
6. **Keep the optimization testable.** A trigger-maintained counter is only safe because a randomised test checks it against the truth after hundreds of operations.
7. **Test the tests.** Deliberately breaking code showed two weak tests that coverage said were fine.
8. **Cross-layer tests earn their keep.** The end-to-end test failed the moment the server's rules tightened; unit tests on either side alone would have stayed green.
9. **Write down the evidence.** Saving the failing output before the fix makes the report honest and the fix verifiable.
