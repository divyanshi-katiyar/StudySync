// End-to-end check of the REAL client code against a REAL running API (no mocks).
// Run through  python scripts/e2e.py  from the project root; it starts a fresh seeded server and sets STUDYSYNC_API_URL.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { ApiError } from '../src/api/errors.js'
import { createHttpApi } from '../src/api/http.js'
import { browserFetch, until } from './helpers.mjs'

const URL_ = process.env.STUDYSYNC_API_URL
const opts = { skip: URL_ ? false : 'set STUDYSYNC_API_URL (use scripts/e2e.py)' }

/** One simulated browser: its own API client and its own cookie jar. */
const browser = () => {
  const fetchImpl = browserFetch()
  return { fetchImpl, api: createHttpApi(URL_, fetchImpl) }
}
const signIn = async (email) => {
  const b = browser()
  b.user = await b.api.auth.login({ email, password: 'Password123' })
  return b
}
const listen = (api) => {
  const events = []
  api.realtime.subscribe((e) => events.push(e))
  api.realtime.start()
  return events
}

test('sign in, dashboard and my groups come from the database', opts, async () => {
  const alex = await signIn('demo@studysync.app')
  assert.equal(alex.user.name, 'Alex Rao')
  const dash = await alex.api.dashboard.get()
  assert.equal(dash.counts.groups, 3)
  assert.equal((await alex.api.groups.mine()).length, 3)
  const found = await alex.api.groups.list({ search: 'data', subject: '', sort: 'popular', page: 1 })
  assert.ok(found.items.length >= 1 && found.total >= 1)
})

test('a change by one person appears live for another person', opts, async () => {
  const alex = await signIn('demo@studysync.app')
  const priya = await signIn('priya@studysync.app')
  const seen = listen(alex.api)
  const priyaSeen = listen(priya.api)
  await until(() => alex.api.realtime.status === 'live' && priya.api.realtime.status === 'live')
  assert.equal(alex.api.realtime.status, 'live')

  // Priya (owner of g1) shares a resource; Alex is a member
  const shared = await priya.api.resources.add('g1', { title: 'Live demo resource', type: 'link', url: 'https://example.com/live', tags: ['live'] })
  const note = await until(() => seen.find((e) => e.type === 'notification' && /Live demo resource|shared a new resource/.test(e.notification.message)))
  assert.ok(note, 'Alex should receive a notification without reloading')
  assert.equal(note.notification.type, 'resource')
  assert.ok(await until(() => seen.find((e) => e.type === 'group.updated' && e.groupId === 'g1' && e.kind === 'resources')))
  const stored = await alex.api.notifications.list()
  assert.ok(stored.some((n) => n.id === note.notification.id), 'the live notification is the same one the REST API returns')
  const list = await alex.api.resources.list('g1')
  assert.ok(list.some((r) => r.id === shared.id), 'reloading after the hint shows the new resource')
  assert.ok(!seen.some((e) => e.type === 'group.updated' && e.kind === 'resources' && e.by), 'events carry no private details')

  // Alex starts a discussion; Priya's open page gets a hint that names the post
  const post = await alex.api.posts.create('g1', { title: 'Live discussion check', body: 'Does this reach everyone instantly?' })
  const hint = await until(() => priyaSeen.find((e) => e.type === 'group.updated' && e.kind === 'posts' && e.postId === post.id))
  assert.ok(hint)

  // RSVP changes are announced to the other members of the group
  priyaSeen.length = 0
  await alex.api.sessions.rsvp('s1', 'going')
  assert.ok(await until(() => priyaSeen.find((e) => e.type === 'group.updated' && e.kind === 'sessions')))

  alex.api.realtime.stop()
  priya.api.realtime.stop()
  assert.equal(alex.api.realtime.status, 'idle')
})

test('errors reach the user interface as ApiError with readable messages', opts, async () => {
  const alex = await signIn('demo@studysync.app')
  await assert.rejects(alex.api.groups.get('g7'), (e) => e instanceof ApiError && e.status === 403 && /private/.test(e.message))
  await assert.rejects(alex.api.groups.get('g_missing'), (e) => e.status === 404)
  await assert.rejects(alex.api.groups.create({ name: 'x', description: 'short', subject: 'Nope', visibility: 'secret' }), (e) => e.status === 422 && 'name' in e.fields && 'subject' in e.fields)
  await assert.rejects(alex.api.groups.joinByCode('NOPE-000000'), (e) => e.status === 404)
  await assert.rejects(alex.api.sessions.create('g1', { title: 'Not allowed', startsAt: new Date(Date.now() + 10 * 864e5).toISOString().slice(0, 16), durationMin: 60 }), (e) => e.status === 403)
  const bad = browser()
  await assert.rejects(bad.api.auth.login({ email: 'demo@studysync.app', password: 'WrongPass1' }), (e) => e.status === 401 && /incorrect/.test(e.message))
})

test('a page reload keeps the session (refresh cookie) and logout ends it', opts, async () => {
  const alex = await signIn('demo@studysync.app')
  const reloaded = createHttpApi(URL_, alex.fetchImpl) // new JavaScript state, same browser cookies
  const me = await reloaded.auth.me()
  assert.equal(me.email, 'demo@studysync.app')
  assert.equal((await reloaded.groups.mine()).length, 3)
  await reloaded.auth.logout()
  await assert.rejects(createHttpApi(URL_, alex.fetchImpl).auth.me(), (e) => e.status === 401)
})

test('create group, schedule a session and RSVP, as the interface does it', opts, async () => {
  const sam = await signIn('sam@studysync.app')
  const g = await sam.api.groups.create({ name: 'Integration Test Group', description: 'Created by the end-to-end test.', subject: 'Networks', visibility: 'private' })
  assert.equal(g.myRole, 'owner')
  assert.match(g.inviteCode, /^NET-/)
  const s = await sam.api.sessions.create(g.id, { title: 'Subnetting drill', startsAt: new Date(Date.now() + 10 * 864e5).toISOString().slice(0, 16), durationMin: '45', meetingLink: 'https://meet.example.com/net' })
  assert.equal(s.durationMin, 45)
  const joiner = await signIn('meera@studysync.app')
  const joined = await joiner.api.groups.joinByCode(g.inviteCode)
  assert.equal(joined.myRole, 'member')
  const after = await joiner.api.sessions.rsvp(s.id, 'going')
  assert.equal(after.goingCount, 2)
})
