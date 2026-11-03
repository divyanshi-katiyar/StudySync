import { validate, required, email, password, url } from '../utils/validation'
import { timeAgo, initials, pluralize } from '../utils/format'

describe('validation rules', () => {
  it('returns messages only for invalid fields', () => {
    const errors = validate({ email: [required('your email'), email], password: [password] }, { email: 'a@b.co', password: 'short' })
    expect(errors.email).toBeUndefined()
    expect(errors.password).toMatch(/at least 8 characters/i)
  })
  it('accepts only http and https links', () => {
    expect(url('https://example.com/a')).toBe('')
    expect(url('ftp://example.com')).not.toBe('')
    expect(url('example.com')).not.toBe('')
  })
})

describe('format helpers', () => {
  const now = new Date('2026-10-21T12:00:00Z').getTime()
  it('describes past and future times', () => {
    expect(timeAgo('2026-10-19T12:00:00Z', now)).toBe('2 days ago')
    expect(timeAgo('2026-10-21T15:00:00Z', now)).toBe('in 3 hours')
    expect(timeAgo('2026-10-21T11:59:40Z', now)).toBe('just now')
  })
  it('builds initials and plurals', () => {
    expect(initials('Priya Nair')).toBe('PN')
    expect(pluralize(1, 'member')).toBe('1 member')
    expect(pluralize(4, 'member')).toBe('4 members')
  })
})
