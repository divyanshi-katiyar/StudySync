// Smoke test for the front end HTTP client (frontend-integration/src/api/http.js).
// 1. STUDYSYNC_DATABASE=/tmp/smoke.db python manage.py reset && STUDYSYNC_DATABASE=/tmp/smoke.db PORT=5055 python run.py
// 2. copy http.js to scripts/http.mjs and errors.js to scripts/errors.mjs, changing its import to ./errors.mjs
// 3. node scripts/client_smoke_test.mjs   (needs Node 20+; prints PASS/FAIL per check)
import { createHttpApi } from './http.mjs'
const { auth, groups, resources, posts, sessions, notifications, dashboard } = createHttpApi('http://127.0.0.1:5055/api', (u, o) => {
  // minimal cookie jar so the httpOnly refresh cookie behaves like a browser
  globalThis.jar ??= ''
  o.headers = { ...o.headers, ...(jar ? { Cookie: jar } : {}) }
  return fetch(u, o).then((r) => { const c = r.headers.getSetCookie?.() ?? []; c.forEach((x) => { const [kv] = x.split(';'); if (/Max-Age=0/i.test(x)) jar = ''; else jar = kv }); return r })
})
const check = (label, cond) => { console.log((cond ? 'PASS ' : 'FAIL ') + label); if (!cond) process.exitCode = 1 }
const u = await auth.login({ email: 'demo@studysync.app', password: 'Password123' })
check('login returns user', u.name === 'Alex Rao')
const d = await dashboard.get(); check('dashboard', d.counts.groups === 3)
const mine = await groups.mine(); check('mine', mine.length === 3)
const found = await groups.list({ search: 'data', subject: '', sort: 'popular', page: 1 }); check('discover', found.items.length >= 1)
const g = await groups.create({ name: 'Smoke Test Group', description: 'Created by the smoke test.', subject: 'Networks', visibility: 'public' }); check('create group', g.myRole === 'owner')
const r = await resources.add(g.id, { title: 'Smoke resource', type: 'link', url: 'https://example.com/s', tags: ['smoke'] }); check('add resource', r.tags[0] === 'smoke')
const s = await sessions.create(g.id, { title: 'Smoke session', startsAt: new Date(Date.now() + 864e5).toISOString().slice(0, 16), durationMin: '60', meetingLink: '' }); check('create session from datetime-local value', s.durationMin === 60)
const rv = await sessions.rsvp(s.id, 'maybe'); check('rsvp', rv.myRsvp === 'maybe')
try { await groups.get('g7'); check('private group throws', false) } catch (e) { check('private group -> ApiError 403', e.status === 403) }
try { await groups.create({ name: 'x' }); check('validation throws', false) } catch (e) { check('validation -> 422 with fields', e.status === 422 && 'description' in e.fields) }
await auth.logout()
try { await dashboard.get(); check('after logout rejected', false) } catch (e) { check('after logout -> 401', e.status === 401) }
// page reload: no access token in memory, cookie jar has the refresh cookie from a fresh login
await auth.login({ email: 'demo@studysync.app', password: 'Password123' })
const api2 = createHttpApi('http://127.0.0.1:5055/api', (u, o) => { o.headers = { ...o.headers, ...(jar ? { Cookie: jar } : {}) }; return fetch(u, o) })
const me = await api2.auth.me(); check('reload restores session via refresh cookie', me.email === 'demo@studysync.app')
