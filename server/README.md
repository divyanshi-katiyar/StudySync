# StudySync back end (Week 3)

REST API for StudySync, the collaborative study-group platform planned in Week 1 and built as a React front end in Week 2.
It implements the Week 1 API design (register/login with JWT and rotating refresh tokens, groups with roles, resources, discussion,
sessions with RSVP, notifications, dashboard) and returns exactly the JSON shapes the Week 2 front end already uses.

| | |
|---|---|
| Language / framework | Python 3.10+ with **Flask 3** |
| Database | **SQLite** (relational, 11 tables, foreign keys enforced) |
| Auth | Password hashing with scrypt, JWT access token (15 min), rotating refresh token in an httpOnly cookie (7 days) |
| Tests | 127 automated tests (`unittest`), including security, live events and a docs-versus-code check |
| Docs | `docs/API.md`, `docs/openapi.yaml` (importable into Postman or Swagger UI) |

## Run it

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                 # optional for development; every setting has a default

python manage.py seed                # demo data: log in with demo@studysync.app / Password123
python run.py                        # http://localhost:5000   (try /api/health)
```

`python manage.py reset` wipes the database and re-seeds it; `python manage.py init-db` only creates empty tables.
Environment variables are listed in `.env.example`. In production set `STUDYSYNC_ENV=production` and a long random
`STUDYSYNC_SECRET_KEY` (the app refuses to start without one), then run `gunicorn wsgi:app --worker-class gthread --workers 1 --threads 50`. Live updates keep one thread busy per open stream, and the event hub lives inside one process, so use one worker with many threads (several workers would need Redis pub/sub, see the root README).
Cross-site deployments (front end on Vercel, API on Render) need `STUDYSYNC_COOKIE_SAMESITE=None`, `STUDYSYNC_COOKIE_SECURE=true`,
`STUDYSYNC_CORS_ORIGINS=https://your-front-end` and `STUDYSYNC_TRUST_PROXY=true`.

## Run the tests

```bash
python -m unittest discover -s tests -t . -v      # 127 tests, about 15 seconds, uses a temporary database per test
python scripts/gen_docs.py                        # regenerate docs/API.md and docs/openapi.yaml
python scripts/benchmark.py                       # response-time measurements, writes docs/benchmark.json
```

## Connect the React front end

The front end now lives next to this folder (`../client`) and is already wired to the API. Set `VITE_API_URL=http://localhost:5000/api`
in `client/.env` and run `npm run dev`. See the README in the parent folder for the complete walkthrough.

## Project layout

```
studysync/
  __init__.py        app factory: config, CORS, security headers, rate limiting, request logging
  config.py          environment-based settings
  db.py, schema.sql  SQLite connection per request, full schema with constraints and indexes
  security.py        password hashing, JWT, refresh-token rotation and reuse detection, auth_required
  validation.py      validation rules (same messages as the front end), query-parameter parsing
  errors.py          one error type and one JSON error shape
  ratelimit.py       sliding-window rate limiter
  serializers.py     database rows -> camelCase JSON
  routes/            thin HTTP layer: auth, users, groups, content (resources/posts/comments), sessions + notifications
  services/          business rules and SQL: auth, groups, content, sessions, notifications
  seed.py            demo data
tests/               auth, groups, content, sessions, security, docs
docs/                spec.py (source of truth), API.md, openapi.yaml, benchmark.json
scripts/             gen_docs.py, benchmark.py, client_smoke_test.mjs
```

## Design notes

* **Layers** follow Week 1: routes parse the request and shape the response, services hold business rules, SQL lives next to the rules it serves.
* **Security:** parameterised SQL only; LIKE wildcards escaped; validation on every body and query parameter; generic login errors with equal timing;
  per-IP and per-account rate limits; exact-match CORS allow-list; origin check on cookie endpoints; security headers; 1 MB body limit; no stack traces in responses.
* **Authorisation** is checked on the server for every group route (member, moderator, owner). Outsiders get 403 on private data; the invite code is never sent to non-members.
* **Notifications** are stored per recipient when something happens and pushed live over Server-Sent Events (`GET /api/stream`, see `docs/API.md`, section Real-time events).
* **Limits:** the rate limiter is in memory (one process); SQLite suits a single server. Both are isolated behind small modules so they can be swapped for Redis and PostgreSQL.
