import { useCallback, useState } from 'react'
import { validate } from '../utils/validation'

/**
 * Small controlled-form helper.
 *   const form = useForm({ email: '' }, { email: [required('your email'), email] })
 *   <Input {...form.bind('email')} />        // value, onChange, error, name
 *   const errors = form.check()               // validates everything, stores and returns the errors
 * Editing a field clears its own error so messages do not linger once the user fixes the problem.
 */
export function useForm(initial, rules = {}) {
  const [values, setValues] = useState(initial)
  const [errors, setErrors] = useState({})

  const setField = useCallback((name, value) => {
    setValues((v) => ({ ...v, [name]: value }))
    setErrors((e) => (e[name] ? { ...e, [name]: '' } : e))
  }, [])

  const bind = (name) => ({
    name,
    value: values[name] ?? '',
    error: errors[name],
    onChange: (e) => setField(name, e?.target ? e.target.value : e),
  })

  const check = () => {
    const found = validate(rules, values)
    setErrors(found)
    return found
  }

  const reset = () => {
    setValues(initial)
    setErrors({})
  }

  return { values, errors, setErrors, setField, bind, check, reset }
}
