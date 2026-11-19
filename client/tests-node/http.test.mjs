import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ApiError } from '../src/api/errors.js'
import { createHttpApi } from '../src/api/http.js'
import { jsonResponse } from './helpers.mjs'

/** A fake server: `routes` maps "METHOD /path" to a function returning a Response. */
function fake(routes) {
  const log = []
  const fetchImpl = async (url, opts) => {
    const u = new URL(url)
    const key = `${opts.method} ${u.pathname}`
    log.push({ key, opts, url: u })
    const handler = routes[key]
    if (!handler) return jsonResponse({ message: 'not found' }, 404)
    return handler(opts, u, log.filter((l) => l.key === key).length)
  }
  return { fetchImpl, log }
}
const login = { 'POST /api/auth/refresh': () => jsonResponse({ accessToken: 'tok1', user: { id: 'u1' } }) }

test('sends cookies and the bearer token, and unwraps { success, data }', async () => {
  const { fetchImpl, log } = fake({ ...login, 'GET /api/groups/mine': () => jsonResponse([{ id: 'g1' }]) })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  assert.deepEqual(await api.groups.mine(), [{ id: 'g1' }])
  const call = log.find((l) => l.key === 'GET /api/groups/mine')
  assert.equal(call.opts.credentials, 'include')
  assert.equal(call.opts.headers.Authorization, 'Bearer tok1')
})

test('parallel first requests share one token refresh', async () => {
  const { fetchImpl, log } = fake({ ...login, 'GET /api/groups/mine': () => jsonResponse([]), 'GET /api/sessions': () => jsonResponse([]) })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  await Promise.all([api.groups.mine(), api.sessions.upcoming(), api.groups.mine()])
  assert.equal(log.filter((l) => l.key === 'POST /api/auth/refresh').length, 1)
})

test('an expired access token is refreshed once and the request is retried', async () => {
  let first = true
  const { fetchImpl, log } = fake({
    'POST /api/auth/refresh': () => jsonResponse({ accessToken: first ? 'old' : 'new', user: {} }),
    'GET /api/groups/mine': (opts) => {
      if (opts.headers.Authorization === 'Bearer old') {
        first = false
        return jsonResponse({ message: 'Your session has expired.' }, 401)
      }
      return jsonResponse(['ok'])
    },
  })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  assert.deepEqual(await api.groups.mine(), ['ok'])
  assert.equal(log.filter((l) => l.key === 'POST /api/auth/refresh').length, 2)
})

test('validation errors become ApiError with per-field messages', async () => {
  const { fetchImpl } = fake({ ...login, 'POST /api/groups': () => jsonResponse({ message: 'Please fix the highlighted fields.', errors: { name: 'Enter a group name.' } }, 422) })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  await assert.rejects(api.groups.create({}), (err) => err instanceof ApiError && err.status === 422 && err.fields.name === 'Enter a group name.')
})

test('reads are retried once after a network failure, writes are not', async () => {
  let gets = 0
  let posts = 0
  const { fetchImpl } = fake({
    ...login,
    'GET /api/groups/mine': () => {
      if (++gets === 1) throw new TypeError('fetch failed')
      return jsonResponse(['recovered'])
    },
    'POST /api/groups': () => {
      posts++
      throw new TypeError('fetch failed')
    },
  })
  const api = createHttpApi('http://api.test/api', fetchImpl, { retryDelayMs: 1 })
  assert.deepEqual(await api.groups.mine(), ['recovered'])
  assert.equal(gets, 2)
  await assert.rejects(api.groups.create({ name: 'x' }), (err) => err.status === 0 && /Cannot reach the server/.test(err.message))
  assert.equal(posts, 1, 'a write must not be sent twice')
})

test('a request that hangs is cut off with a clear message', async () => {
  const fetchImpl = (url, opts) =>
    new Promise((resolve, reject) => {
      if (url.includes('/auth/refresh')) return resolve(jsonResponse({ accessToken: 't', user: {} }))
      opts.signal.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' })))
    })
  const api = createHttpApi('http://api.test/api', fetchImpl, { timeoutMs: 30, retryDelayMs: 1 })
  await assert.rejects(api.groups.create({ name: 'x' }), (err) => err.status === 0 && /too long/.test(err.message))
})

test('a relative base URL such as /api is resolved against the page origin', async () => {
  globalThis.location = { origin: 'http://localhost:5173' }
  const { fetchImpl, log } = fake({ ...login, 'GET /api/groups/mine': () => jsonResponse([]) })
  await createHttpApi('/api', fetchImpl).groups.mine()
  assert.equal(log.at(-1).url.origin, 'http://localhost:5173')
  delete globalThis.location
})

test('datetime-local values are sent as ISO times and the length as a number', async () => {
  let body
  const { fetchImpl } = fake({ ...login, 'POST /api/groups/g1/sessions': (opts) => ((body = JSON.parse(opts.body)), jsonResponse({ id: 's1' }, 201)) })
  await createHttpApi('http://api.test/api', fetchImpl).sessions.create('g1', { title: 'T', startsAt: '2030-01-02T19:00', durationMin: '60', meetingLink: '' })
  assert.match(body.startsAt, /^2030-01-0\dT\d\d:\d\d:00\.000Z$/)
  assert.equal(body.durationMin, 60)
})

test('the app is told when the session can no longer be renewed', async () => {
  const { fetchImpl } = fake({ 'POST /api/auth/refresh': () => jsonResponse({ message: 'Your session has expired.' }, 401) })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  let ended = 0
  const off = api.auth.onSessionEnd(() => ended++)
  await assert.rejects(api.groups.mine(), (e) => e.status === 401)
  assert.equal(ended, 1)
  off()
  await assert.rejects(api.groups.mine())
  assert.equal(ended, 1, 'unsubscribed listeners are not called')
})

test('identical GET requests made at the same time share one network call', async () => {
  let calls = 0
  const { fetchImpl } = fake({
    ...login,
    'GET /api/groups/mine': async () => {
      calls++
      await new Promise((r) => setTimeout(r, 20))
      return jsonResponse([{ id: 'g1', tags: ['a'] }])
    },
  })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  const [a, b, c] = await Promise.all([api.groups.mine(), api.groups.mine(), api.groups.mine()])
  assert.equal(calls, 1)
  assert.deepEqual(a, b)
  a[0].tags.push('changed')
  assert.deepEqual(c[0].tags, ['a'], 'each caller gets its own copy')
  await api.groups.mine()
  assert.equal(calls, 2, 'a later request is a new call, nothing is cached')
})

test('different URLs, queries and writes are never merged', async () => {
  let gets = 0
  let posts = 0
  const { fetchImpl } = fake({
    ...login,
    'GET /api/groups': () => (gets++, jsonResponse({ items: [] })),
    'POST /api/groups': () => (posts++, jsonResponse({ id: 'g' }, 201)),
  })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  await Promise.all([api.groups.list({ search: 'a' }), api.groups.list({ search: 'b' }), api.groups.list({ search: 'a' })])
  assert.equal(gets, 2, 'two distinct queries, the repeated one is shared')
  await Promise.all([api.groups.create({ name: 'x' }), api.groups.create({ name: 'x' })])
  assert.equal(posts, 2, 'two writes are two writes')
})

test('a failed shared GET fails every waiting caller, then the next call tries again', async () => {
  let n = 0
  const { fetchImpl } = fake({ ...login, 'GET /api/sessions': () => (++n <= 1 ? jsonResponse({ message: 'down' }, 500) : jsonResponse(['ok'])) })
  const api = createHttpApi('http://api.test/api', fetchImpl)
  const results = await Promise.allSettled([api.sessions.upcoming(), api.sessions.upcoming()])
  assert.deepEqual(results.map((r) => r.status), ['rejected', 'rejected'])
  assert.deepEqual(await api.sessions.upcoming(), ['ok'])
})
