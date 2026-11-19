import assert from 'node:assert/strict'
import { test } from 'node:test'
import { debounce } from '../src/utils/debounce.js'
import { initials, pluralize, timeAgo } from '../src/utils/format.js'
import * as v from '../src/utils/validation.js'
import { SUBJECTS, SUBJECT_COLORS } from '../src/utils/subjects.js'

const wait = (ms) => new Promise((r) => setTimeout(r, ms))

test('debounce turns a burst of calls into one call with the last arguments', async () => {
  const seen = []
  const d = debounce((x) => seen.push(x), 30)
  d(1); d(2); d(3)
  assert.deepEqual(seen, [])
  await wait(70)
  assert.deepEqual(seen, [3])
  d(4)
  await wait(70)
  assert.deepEqual(seen, [3, 4])
})

test('debounce.cancel drops a pending call', async () => {
  let n = 0
  const d = debounce(() => n++, 20)
  d()
  d.cancel()
  await wait(50)
  assert.equal(n, 0)
})

test('timeAgo describes past and future times with the right unit and plural', () => {
  const now = Date.parse('2026-10-27T12:00:00Z')
  const at = (ms) => new Date(now + ms).toISOString()
  assert.equal(timeAgo(at(-10_000), now), 'just now')
  assert.equal(timeAgo(at(-60_000), now), '1 minute ago')
  assert.equal(timeAgo(at(-5 * 60_000), now), '5 minutes ago')
  assert.equal(timeAgo(at(-3_600_000), now), '1 hour ago')
  assert.equal(timeAgo(at(-2 * 86_400_000), now), '2 days ago')
  assert.equal(timeAgo(at(3 * 3_600_000), now), 'in 3 hours')
  assert.equal(timeAgo(at(86_400_000 * 1.9), now), 'in 1 day')
})

test('initials and pluralize', () => {
  assert.equal(initials('Alex Rao'), 'AR')
  assert.equal(initials('  priya  nair  kumar '), 'PN')
  assert.equal(initials('sam'), 'S')
  assert.equal(initials(''), '')
  assert.equal(pluralize(1, 'member'), '1 member')
  assert.equal(pluralize(0, 'member'), '0 members')
  assert.equal(pluralize(5, 'session'), '5 sessions')
})

test('validation: required, lengths count what people see', () => {
  assert.equal(v.required('a name')('  '), 'Enter a name.')
  assert.equal(v.required('a name')('\u200b\u200b'), 'Enter a name.')
  assert.equal(v.required('a name')(null), 'Enter a name.')
  assert.equal(v.minLength(3, 'Title')('😀😀😀'), '')
  assert.match(v.minLength(3, 'Title')('😀😀'), /at least 3/)
  assert.equal(v.maxLength(3, 'Title')('😀😀😀'), '')
  assert.match(v.maxLength(3, 'Title')('😀😀😀😀'), /at most 3/)
  assert.match(v.singleLine('Name')('a\nb'), /single line/)
  assert.equal(v.singleLine('Name')(' a b \n'), '')
})

test('validation: email, password and url', () => {
  assert.equal(v.email('a@b.co'), '')
  for (const bad of ['', 'a', 'a@b', 'a b@c.co', 'a'.repeat(250) + '@b.co']) assert.ok(v.email(bad), bad)
  assert.equal(v.password('abcdefg1'), '')
  for (const bad of ['short1', 'abcdefgh', '12345678', 'a1'.repeat(64) + 'x', 'abcdefg\u0663']) assert.ok(v.password(bad), bad)
  assert.equal(v.url('https://example.com/a?b=1'), '')
  for (const bad of ['example.com', 'ftp://x.co', 'javascript:alert(1)', 'http:/x.co', 'https://exa mple.com', 'https://']) assert.ok(v.url(bad), bad)
})

test('validate returns only the first problem per field and nothing when valid', () => {
  const rules = { name: [v.required('a name'), v.minLength(2, 'Name')], email: [v.required('an email'), v.email] }
  assert.deepEqual(v.validate(rules, { name: '', email: 'x' }), { name: 'Enter a name.', email: 'Enter a valid email address, like you@college.edu.' })
  assert.deepEqual(v.validate(rules, { name: 'Al', email: 'al@x.co' }), {})
})

test('subjects: every subject has a colour that meets text contrast on white', () => {
  assert.equal(SUBJECTS.length, 8)
  const lum = (hex) => {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  for (const [name, hex] of Object.entries(SUBJECT_COLORS)) {
    const ratio = 1.05 / (lum(hex) + 0.05)
    assert.ok(ratio >= 4.5, `${name} ${hex} has contrast ${ratio.toFixed(2)}`)
  }
})
