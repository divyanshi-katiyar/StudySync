# StudySync: full-stack application (Weeks 1 to 5)

StudySync is a collaborative study-group platform: students create or join groups, share resources, discuss questions and schedule sessions.
This repository joins the three earlier pieces into one running application.

| Week | Piece | Where |
|---|---|---|
| 1 | Planning, wireframes, architecture, API and database design | design documents (submitted separately) |
| 2 | React front end (originally on a browser mock database) | `client/` |
| 3 | Flask REST API and SQLite database | `server/` |
| 4 | **Integration:** the front end talks to the real API, with live updates | this README, `client/src/api/`, `server/studysync/realtime.py` |
| 5 | **Testing, debugging, optimization:** 200 API tests, client tests, end-to-end and parity checks, 8 bugs fixed, 38 to 43 % faster responses | [docs/TESTING.md](docs/TESTING.md), [docs/DEBUGGING.md](docs/DEBUGGING.md), [logs/](logs/README.md) |

```
 Browser (React 18, Vite, Tailwind)                     Flask API                         SQLite
┌─────────────────────────────────┐   REST + JSON    ┌──────────────────────────┐     ┌──────────────┐
│ pages and components            │ ───────────────► │ routes -> services       │ ──► │ 11 tables    │
│   hooks: useAsync, useForm ...  │ ◄─────────────── │ JWT auth, validation,    │ ◄── │ constraints  │
│ src/api/index.js  (the only     │                  │ rate limits, permissions │     └──────────────┘
│   place that knows the backend) │   live events    │ event hub (SSE)          │
│   http.js    REST client        │ ◄─ GET /stream ─ │                          │
│   realtime.js live-update client│   (text/event-   └──────────────────────────┘
└─────────────────────────────────┘    stream)
```

## 1. Run the whole application locally

You need **Python 3.10 or newer** and **Node.js 20 or newer**. Use two terminals.

**Terminal 1: the API**

```bash
cd server
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py seed                  # demo data (safe to repeat; "reset" wipes and re-seeds)
python run.py                          # http://localhost:5000/api/health should answer {"success":true,...}
```

**Terminal 2: the front end**

```bash
cd client
cp .env.example .env                   # Windows: copy .env.example .env   (sets VITE_API_URL=http://localhost:5000/api)
npm install
npm run dev                            # http://localhost:5173
```

Sign in with the demo account **demo@studysync.app / Password123** (every seeded user, for example priya@studysync.app, has the same password),
or register a new account.

**See the live updates:** open the app in two windows (one normal, one private/incognito so they do not share cookies).
Sign in as `demo@studysync.app` in one and `priya@studysync.app` in the other, open *Algorithms Study Circle* in both, and add a resource,
start a discussion or RSVP to a session in one window. The other window shows a toast, the bell count and the page content update without a refresh.

To go back to the offline mock (Week 2 behaviour) leave `VITE_API_URL` empty in `client/.env`; no server is needed then.

### Configuration

| Setting | File | Default | Purpose |
|---|---|---|---|
| `VITE_API_URL` | `client/.env` | `http://localhost:5000/api` | Where the front end sends requests. Empty = mock database |
| `STUDYSYNC_CORS_ORIGINS` | `server/.env` | `http://localhost:5173` | Front-end addresses the API accepts (comma separated) |
| `STUDYSYNC_DATABASE`, `PORT` | `server/.env` | `studysync.db`, `5000` | Database file and port |
| `STUDYSYNC_SECRET_KEY` | `server/.env` | development value | **Required** in production |
| `STUDYSYNC_COOKIE_SECURE`, `STUDYSYNC_COOKIE_SAMESITE` | `server/.env` | `false`, `Lax` | Use `true` and `None` when the front end and API are on different sites |

## 2. How the integration was done

### 2.1 One switch, no page changes
The Week 2 design kept every network call behind `client/src/api/index.js`. Integration kept that promise:

* `mock.js` is the old browser database; `http.js` is the new client with the same function names and return shapes;
  `index.js` picks one from `VITE_API_URL`. No page or component had to learn where data comes from.
* The server's serializers return exactly the shapes the pages already read (`memberCount`, `myRole`, `canDelete`, `goingCount` ...),
  and the seed data is the Week 2 mock data, so both back ends look the same on screen.
* The 23 existing Vitest tests still run on the mock (they never set `VITE_API_URL`).

### 2.2 Contract review: what each screen calls

| Screen | Front-end call | Endpoint |
|---|---|---|
| Register, log in, log out, restore session | `auth.register/login/logout/me` | `POST /auth/register, /login, /logout, /refresh` |
| Dashboard | `dashboard.get` | `GET /users/me/dashboard` |
| Discover | `groups.list({search, subject, sort, page})` | `GET /groups` |
| My groups, create, join, join by code, leave | `groups.mine/create/join/joinByCode/leave` | `GET /groups/mine`, `POST /groups`, `/groups/:id/join`, `/groups/join-by-code`, `DELETE /groups/:id/leave` |
| Group workspace | `groups.get/members/setMemberRole/removeMember` | `GET /groups/:id`, `/members`, `PATCH/DELETE /members/:userId` |
| Resources tab | `resources.list/add/remove` | `GET/POST /groups/:id/resources`, `DELETE /resources/:id` |
| Discussion tab, post page | `posts.list/create/get/addComment` | `/groups/:id/posts`, `/posts/:id`, `/posts/:id/comments` |
| Sessions tab and page, RSVP | `sessions.list/upcoming/create/rsvp` | `/groups/:id/sessions`, `/sessions`, `PUT /sessions/:id/rsvp` |
| Notification bell | `notifications.list/markRead/markAllRead` + live stream | `/notifications`, `GET /stream` |

The full reference with request rules and real example responses is in `server/docs/API.md` (and `server/docs/openapi.yaml` for Postman or Swagger UI).

### 2.3 Asynchronous data fetching and state management
* **Server data stays in the page that shows it** (`useAsync`: loading, error, data, reload). Shared state is limited to the signed-in user, toasts and notifications (React Context).
* **URL as state:** search, filters, page number and the active tab are query parameters, so links and the Back button work.
* **Optimistic updates:** an RSVP changes on screen at once and rolls back with a message if the server refuses.
* **Sign-in:** the 15-minute access token lives only in memory; the 7-day refresh token is an httpOnly cookie the page cannot read.
  On load the app asks `/auth/refresh` whether a session exists (the `loading` state), and a 401 on any call triggers one refresh and one retry.
  Parallel requests share a single refresh (the server rotates the cookie on every use).
* **Live updates** (section 2.5) are *hints*: the page reloads its data through the normal REST call, so there is one source of truth.

### 2.4 Handling failures gracefully

| What goes wrong | What the user sees | How |
|---|---|---|
| Invalid form input | message under the field, focus on the first bad field | server returns 422 `{errors:{field:message}}`; `ApiError.fields` feeds the same form code the mock used |
| Not allowed / not found / duplicate | readable message from the server (403, 404, 409) | `ApiError.message` shown by each page's error state or toast |
| Wrong password | one generic message | server answers identically for unknown email and wrong password |
| Access token expired | nothing; the request just works | refresh once, retry once |
| Session over (refresh cookie expired or revoked) | sent to the login page, and back to the same link after sign-in | the refresh fails with 401, the client announces `onSessionEnd`, `AuthContext` signs out |
| Network down, server stopped | "Cannot reach the server" with a Try again button | `ApiError(0)`; reads retry once after 400 ms, **writes are never retried** (they might have been applied) |
| Server hangs | "The server took too long to answer" after 12 s | request timeout |
| Too many requests | message with the wait time | 429 + `Retry-After` |
| Live connection lost | yellow banner "Live updates are paused. Trying to reconnect. Your changes are still saved." | automatic reconnect with growing delay |

### 2.5 Real-time interaction (Server-Sent Events)
Week 1 planned Socket.io. The app only needs *server to browser* pushes (user actions already travel over REST), so I used
**Server-Sent Events**, which Week 1 listed as the one-way alternative: plain HTTP, no extra package, and it works with the existing JWT.

* `GET /api/stream` keeps a response open and writes events as they happen. Events: `notification`, `group.updated` (with `kind` = resources, posts, sessions, members, group, deleted),
  `resync`, `token-expired`. Documented in `server/docs/API.md`.
* **Who hears what:** only current members of the group, never the person who acted; events go out only after the request succeeded and was saved.
* **Browser side:** `RealtimeContext` keeps one connection while someone is signed in. `useLiveGroupReload(groupId, ['resources'], reload)` is all a page needs to refresh itself.
  Live events are wired into the resource, discussion, session and member tabs, the post page, group page, My groups, Sessions, Dashboard and the notification bell.
* **Resilience:** heartbeat every 15 s; the client treats 45 s of silence as a dead connection; reconnect delay 1, 2, 5, 10, 30 s; the server closes the stream when the access token expires and the client refreshes and reconnects;
  a slow client gets a `resync` event instead of unbounded memory use; at most 5 open streams per account.

## 3. Testing and validation

| Layer | Command | Result | What it proves |
|---|---|---|---|
| API | `cd server && python -m unittest discover -s tests -t . -v` | **200 tests pass** (about 15 s) | rules, security, permissions, live events over a real socket, docs match code |
| Front-end clients | `cd client && npm run test:integration` | **28 tests pass** (under 1 s) | token refresh, retry, timeout, SSE parsing, reconnect, expiry handling, no packages needed |
| Whole stack, no browser | `python scripts/e2e.py` (from this folder) | **5 scenarios pass** | the real client code against a real, freshly seeded server: sign-in, dashboard, two users with a change appearing live, error mapping, reload and logout |
| React interface | `cd client && npm test` | the 23 Week 2 Vitest tests (run on the mock) | components and pages still behave as before |

`python scripts/e2e.py` starts its own server on a free port and a temporary database, so it never touches your data.

### Performance (lab numbers, one machine, loopback; development server)

| Measure | Result |
|---|---|
| REST reads, demo data (200 requests per endpoint) | median 2 to 4.6 ms, 95th percentile at most 5.1 ms |
| REST reads after loading 18,000 memberships and 10,000 resources | 95th percentile at most 13 ms |
| 20 concurrent clients for 10 s | 220 requests per second, 0 errors, 95th percentile 167 ms |
| Live push, one change reaching 39 open streams | median 22 ms, 95th percentile 32 ms after the request was sent |
| 60 open live connections while using the app | dashboard median 3.4 ms, 95th percentile 4.8 ms |

Reproduce with `python server/scripts/benchmark.py` and `python server/scripts/benchmark_live.py`. The Week 1 target was under 300 ms for typical requests.

### 3.1 Week 5: testing strategy, debugging and optimization

One command runs every layer that can run on your machine and writes a dated log to `logs/`:

```bash
python scripts/run_all_tests.py            # add --quick to skip slow checks, --full to include the mutation check
```

| Layer | Command | Count |
|---|---|---|
| API unit, integration, security, real-time, robustness | `cd server && python -m unittest discover -s tests -t .` | 200 |
| API line coverage (stdlib tool, floor 95 %) | `cd server && python scripts/coverage_report.py --fail-under 95` | 100 % of 1,581 lines |
| Client unit tests (HTTP client, live client, utilities) | `cd client && npm run test:integration` | 28 |
| React hooks (Vitest) | `cd client && npm install && npm test` | 24 new + 23 from Week 2 |
| Form rules equal API rules | `python scripts/parity_check.py` | 85 cases |
| End to end, real client vs real server | `python scripts/e2e.py` | 5 scenarios |
| Do the tests notice bugs? | `python scripts/mutation_check.py` | 17 of 17 caught |

What Week 5 produced:
* **8 bugs fixed**, found by new robustness tests (a refresh-token race that let 6 simultaneous refreshes all succeed, a join race that returned 500 to 7 of 8 callers, RSVPs of people who had left, date overflow, crash on deeply nested JSON, invisible or multi-line names, look-alike Unicode emails) and **21 form/API mismatches** found by the parity check. Evidence before and after the fixes is in `logs/`; explanations in [docs/DEBUGGING.md](docs/DEBUGGING.md).
* **Performance:** profiling showed connection handling, not queries, as the main cost. A connection pool, a trigger-maintained member count with an index, and fewer dashboard queries made the 12 read endpoints **38 % (demo data) to 43 % (large data) faster**, discovery **72 % faster**, and throughput under 20 concurrent clients went from **220 to 469 requests per second** (p95 167 ms to 82 ms). Table in [docs/TESTING.md](docs/TESTING.md#5-optimization-summary).
* **Test quality:** line coverage rose from 93.8 % to 100 %, and a mutation check (deliberately breaking 17 lines) confirmed the tests fail when the code is wrong.
* **Not verified in this environment:** the 23 Week 2 Vitest tests, the production build, and the GitHub Actions workflow (`.github/workflows/ci.yml`). Run `npm test`, `npm run build` and `python scripts/run_all_tests.py --full` on your machine.

## 4. Challenges and solutions

| # | Challenge | Solution |
|---|---|---|
| 1 | The browser blocked requests from `localhost:5173` to `localhost:5000`, and cookies were not sent | exact-match CORS allow-list with credentials on the server, `credentials: 'include'` on the client; cross-site hosting needs `SameSite=None; Secure` (settings above) |
| 2 | The access token lives only in memory, so a page reload looked like a sign-out | on start the client calls `/auth/refresh` with the httpOnly cookie; the app shows a `loading` state until that answers |
| 3 | Rotating refresh tokens plus parallel requests (and React StrictMode running effects twice) look like token theft | one in-flight refresh shared by all callers on the client, and a 10-second grace window on the server for a just-rotated token |
| 4 | `<input type="datetime-local">` sends a time with no time zone, so sessions would shift by the user's offset | the client converts it to an ISO time before sending; the server stores UTC |
| 5 | The session form sends the length as a string | the server accepts whole-number strings and returns numbers |
| 6 | The browser's `EventSource` cannot send an `Authorization` header, and a token in the URL would end up in logs | the stream is read with `fetch` and a small SSE parser (`realtime.js`) |
| 7 | A notification event has its own `type` field ("resource", "reply") that collided with the event type | notification events are wrapped as `{type:'notification', notification}`; covered by a test |
| 8 | A live event sent before the database commit could make a fast client reload and miss the change | events are queued during the request and sent only after a successful response; a test reads the data right after the event |
| 9 | A stream outlives the 15-minute access token | the server ends the stream at token expiry; the client refreshes and reconnects immediately |
| 10 | Proxies and sleeping laptops leave connections that look open but are dead | 15-second heartbeats, a 45-second silence watchdog and reconnect with backoff |
| 11 | A stalled client could make the server queue events without limit | bounded queue per connection; overflow sends one `resync` so the page reloads |
| 12 | Each live connection holds a server thread, and users open many tabs | limit of 5 streams per account; production uses one gthread worker with many threads |
| 13 | Showing both real data and the old mock without touching every page | single `api/index.js` switch and identical response shapes; mock-only features (reset demo data, simulated notification) hide in real mode |
| 14 | No browser available to test the integration automatically | the real client modules run in Node against a real server (`scripts/e2e.py`); Node ESM needs explicit `.js` import extensions, which are now used in `src/api` |
| 15 | Two copies of the same data (REST list and pushed event) can disagree | events are hints; pages reload through REST. Only notifications are inserted directly, de-duplicated by id |

## 5. Deployment notes and known limits

* **One server process for live updates.** The event hub is in memory. Run `gunicorn wsgi:app --worker-class gthread --workers 1 --threads 50`.
  Several workers or servers need a shared channel (Redis pub/sub) so an event reaches users connected to another process; that is the main next step for scale.
* The rate limiter is also in memory (same Redis step). SQLite needs a persistent disk, or move to PostgreSQL, before real users arrive.
* With the front end on one site and the API on another, set `STUDYSYNC_CORS_ORIGINS`, `STUDYSYNC_COOKIE_SAMESITE=None` and `STUDYSYNC_COOKIE_SECURE=true`, serve both over HTTPS, and set `STUDYSYNC_TRUST_PROXY=true` behind a proxy.
* No live deployment is included; the application is run locally (section 1).
* **Verified here:** the API (200 tests), the client modules (28 tests), the whole stack through the real client code (5 scenarios), and syntax of every changed React file.
  **Run on your machine before submitting:** `npm install`, `npm test`, `npm run build` and the two-window live demo in section 1, because the React interface itself could not be rendered in the environment where this was prepared.
* Files are shared as links (no upload), and there is no email (verification, reminders). Both were Could items in Week 1.

## 6. Repository layout

```
README.md                  this file
scripts/e2e.py             starts a seeded API and runs the full-stack client tests
docs/DEMO_SCRIPT.md        shot list for the screen recording
docs/TESTING.md            test strategy, how to run, rationale, optimization summary (Week 5)
docs/DEBUGGING.md          bugs found, causes, fixes, lessons learned (Week 5)
logs/                      error logs, before/after evidence, coverage, profiles (index in logs/README.md)
scripts/                   e2e.py, run_all_tests.py, parity_check.py, mutation_check.py
client/                    React application
  src/api/                 index.js (switch), http.js, realtime.js, errors.js, mock.js + mockDb.js (Week 2 mock)
  src/context/             Auth, Toast, Notifications, Realtime
  src/hooks/               useAsync, useForm, useRsvp, useDebounce ...
  tests-node/              integration tests that run with plain Node
  src/test/                the Week 2 Vitest tests
server/                    Flask API (own README with details)
  studysync/               app, routes, services, realtime, security, validation
  tests/                   200 tests
  docs/                    API.md, openapi.yaml, benchmark results
```
