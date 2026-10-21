/**
 * Tiny form-validation helpers. Each rule returns an error message or ''.
 * `validate(rules, values)` returns an object of { field: message } (empty when valid).
 * The same rules are mirrored by Zod schemas on the server in Week 3.
 */
export const required = (label) => (v) => (String(v ?? '').trim() ? '' : `Enter ${label}.`)
export const minLength = (n, label) => (v) =>
  String(v ?? '').trim().length >= n ? '' : `${label} needs at least ${n} characters.`
export const maxLength = (n, label) => (v) =>
  String(v ?? '').trim().length <= n ? '' : `${label} can have at most ${n} characters.`
export const email = (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(v ?? '').trim()) ? '' : 'Enter a valid email address, like you@college.edu.')
export const password = (v) =>
  /^(?=.*[A-Za-z])(?=.*\d).{8,}$/.test(String(v ?? '')) ? '' : 'Use at least 8 characters with a letter and a number.'
export const url = (v) => {
  try {
    const u = new URL(String(v ?? '').trim())
    return ['http:', 'https:'].includes(u.protocol) ? '' : 'Enter a link that starts with http:// or https://.'
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
