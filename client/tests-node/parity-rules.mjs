// Prints the client's verdict (true = valid) for each test case read from stdin. Used by scripts/parity_check.py,
// which compares these answers with the server's validation functions for the same inputs.
import * as v from '../src/utils/validation.js'

const rules = {
  required: (label) => v.required(label),
  minLength: (label, n) => v.minLength(n, label),
  maxLength: (label, n) => v.maxLength(n, label),
  singleLine: (label) => (v.singleLine ? v.singleLine(label) : () => ''), // the client had no such rule before Week 5: it accepted everything
  email: () => v.email,
  password: () => v.password,
  url: () => v.url,
}
let input = ''
process.stdin.on('data', (c) => (input += c))
process.stdin.on('end', () => {
  const cases = JSON.parse(input)
  const out = cases.map((c) => {
    const rule = rules[c.rule](c.label ?? 'Field', c.n)
    return rule(c.value) === ''
  })
  console.log(JSON.stringify(out))
})
