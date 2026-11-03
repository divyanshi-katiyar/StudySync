import assert from 'node:assert/strict'
import { test } from 'node:test'
import { createRealtime } from '../src/api/realtime.js'
import { streamResponse, until } from './helpers.mjs'

const make = (fetchImpl, extra = {}) => {
  const calls = { refresh: 0, tokens: 0 }
  const rt = createRealtime({
    url: 'http://x/api/stream',
    getToken: async () => `t${++calls.tokens}`,
    refreshToken: async () => {
      calls.refresh++
    },
    fetchImpl,
    backoffMs: [10, 20],
    ...extra,
  })
  const events = []
  const statuses = []
  rt.subscribe((e) => events.push(e))
  rt.onStatus((s) => statuses.push(s))
  return { rt, events, statuses, calls }
}

test('parses events split across network chunks and marks the connection live', async () => {
  const { rt, events, statuses } = make(async () =>
    streamResponse(['retry: 3000\n\nid: 0\nevent: ready\nda', 'ta: {"userId":"u1"}\n\n: ping\n\nid: 5\nevent: group.updated\ndata: {"groupId":"g1","kind":"resources"}\n\n'], { keepOpen: true }),
  )
  rt.start()
  await until(() => events.length >= 1)
  assert.deepEqual(events[0], { type: 'group.updated', groupId: 'g1', kind: 'resources' })
  assert.ok(statuses.includes('live'))
  rt.stop()
  assert.equal(rt.status, 'idle')
})

test('a notification keeps its own type field instead of clashing with the event type', async () => {
  const note = { id: 'n1', type: 'resource', message: 'Sam shared a new resource', isRead: false }
  const { rt, events } = make(async () => streamResponse([`event: notification\ndata: ${JSON.stringify(note)}\n\n`], { keepOpen: true }))
  rt.start()
  await until(() => events.length)
  assert.deepEqual(events[0], { type: 'notification', notification: note })
  rt.stop()
})

test('sends the access token in the Authorization header', async () => {
  let seen
  const { rt } = make(async (url, opts) => {
    seen = opts.headers.Authorization
    return streamResponse([], { keepOpen: true })
  })
  rt.start()
  await until(() => seen)
  assert.equal(seen, 'Bearer t1')
  rt.stop()
})

test('reconnects after the connection drops, with backoff', async () => {
  let n = 0
  const { rt, statuses } = make(async () => (++n < 3 ? streamResponse([]) : streamResponse(['event: ready\ndata: {}\n\n'], { keepOpen: true })))
  rt.start()
  await until(() => rt.status === 'live')
  assert.equal(n, 3)
  assert.ok(statuses.includes('offline') && statuses.includes('reconnecting'))
  rt.stop()
})

test('refreshes the token and reconnects at once when the server says it expired', async () => {
  let n = 0
  const { rt, calls } = make(async () => (++n === 1 ? streamResponse(['event: token-expired\ndata: {}\n\n']) : streamResponse(['event: ready\ndata: {}\n\n'], { keepOpen: true })))
  rt.start()
  await until(() => rt.status === 'live')
  assert.equal(calls.refresh, 1)
  assert.equal(n, 2)
  rt.stop()
})

test('a 401 on connect refreshes the token and tries again', async () => {
  let n = 0
  const { rt, calls } = make(async () => (++n === 1 ? new Response('{}', { status: 401 }) : streamResponse(['event: ready\ndata: {}\n\n'], { keepOpen: true })))
  rt.start()
  await until(() => rt.status === 'live')
  assert.equal(calls.refresh, 1)
  rt.stop()
})

test('stops for good when the session cannot be refreshed', async () => {
  const rt = createRealtime({
    url: 'http://x',
    getToken: async () => 't',
    refreshToken: async () => {
      throw Object.assign(new Error('expired'), { status: 401 })
    },
    fetchImpl: async () => new Response('{}', { status: 401 }),
    backoffMs: [10],
  })
  rt.start()
  await until(() => rt.status === 'idle')
  assert.equal(rt.status, 'idle')
})

test('a silent connection is treated as dead and replaced', async () => {
  let n = 0
  const { rt } = make(
    async (url, opts) => {
      n++
      return streamResponse(['event: ready\ndata: {}\n\n'], { keepOpen: true, signal: opts.signal })
    },
    { stallMs: 60 },
  )
  rt.start()
  await until(() => n >= 2, 3000)
  assert.ok(n >= 2, 'should have reconnected after the stall')
  rt.stop()
})
