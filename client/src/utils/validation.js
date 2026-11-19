/**
 * Tiny form-validation helpers. Each rule returns an error message or ''.
 * `validate(rules, values)` returns an object of { field: message } (empty when valid).
 * The same rules are mirrored by Zod schemas on the server in Week 3.
 */
const str = (v) => String(v ?? '')
/** Number of characters a person sees as typed: code points, not UTF-16 units (an emoji is 1, not 2). Matches Python's len(). */
const size = (v) => Array.from(v).length
/** The text a person can actually see: control and invisible "format" characters (zero-width spaces, joiners, byte-order marks) are dropped. */
const visible = (v) => str(v).replace(/[\p{Cc}\p{Cf}]/gu, '').trim()

export const required = (label) => (v) => (visible(v) ? '' : `Enter ${label}.`)
export const minLength = (n, label) => (v) => (size(visible(v)) >= n ? '' : `${label} needs at least ${n} characters.`)
export const maxLength = (n, label) => (v) => (size(str(v).trim()) <= n ? '' : `${label} can have at most ${n} characters.`)
/** Names, titles and emails are one line: no new lines, tabs or other control characters inside. */
export const singleLine = (label) => (v) => (/\p{Cc}/u.test(str(v).trim()) ? `${label} must be a single line of text.` : '')
export const email = (v) => {
  const value = str(v).trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) && size(value) <= 254 ? '' : 'Enter a valid email address, like you@college.edu.'
}
export const password = (v) => {
  const value = str(v)
  return /^(?=[\s\S]*[A-Za-z])(?=[\s\S]*[0-9])[\s\S]{8,}$/u.test(value) && size(value) <= 128 ? '' : 'Use 8 to 128 characters with a letter and a number.'
}
export const url = (v) => {
  const value = str(v).trim()
  if (size(value) > 2048) return 'That link is too long.'
  // must look like http(s)://host, with no spaces or control characters; the browser's URL parser alone accepts "http:/x" and "http:///x"
  if (!/^https?:\/\/[^\s/?#\\]/i.test(value) || /[\s\p{Cc}]/u.test(value)) return 'Enter a full link that starts with http:// or https://.'
  try {
    new URL(value)
    return ''
  } catch {
    return 'Enter a full link, like https://example.com/notes.'
  }
}

export function validate(rules, values) {
  const errors = {}
  for (const [field, fieldRules] of Object.entries(rules)) {
    for (const rule of fieldRules) {
      const message = rule(values[field])
      if (message) {
        errors[field] = message
        break
      }
    }
  }
  return errors
}
