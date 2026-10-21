import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom'
import { AlertCircle } from 'lucide-react'
import { ApiError } from '../api'
import { DEMO_ACCOUNT } from '../api/mockDb'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useForm } from '../hooks/useForm'
import { usePageTitle } from '../hooks/usePageTitle'
import { required, minLength, email, password } from '../utils/validation'
import Button from '../components/ui/Button'
import { Input, focusFirstError } from '../components/ui/Fields'

const LOGIN_RULES = { email: [required('your email'), email], password: [required('your password')] }
const REGISTER_RULES = { name: [required('your name'), minLength(2, 'Name')], email: [required('your email'), email], password: [required('a password'), password] }

/** Login and registration share one layout; `mode` switches the fields, rules and copy. */
export default function AuthPage({ mode }) {
  const isRegister = mode === 'register'
  usePageTitle(isRegister ? 'Create your account' : 'Log in')
  const { status, login, register } = useAuth()
  const toast = useToast()
  const location = useLocation()
  const [params] = useSearchParams()
  const formRef = useRef(null)
  const [showPassword, setShowPassword] = useState(false)
  const [formError, setFormError] = useState('')
  const [saving, setSaving] = useState(false)
  const form = useForm(isRegister ? { name: '', email: '', password: '' } : { email: '', password: '' }, isRegister ? REGISTER_RULES : LOGIN_RULES)

  // "Try the demo account" links here with ?demo=1 and pre-fills the credentials.
  useEffect(() => {
    if (!isRegister && params.get('demo')) {
      form.setField('email', DEMO_ACCOUNT.email)
      form.setField('password', DEMO_ACCOUNT.password)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isRegister, params])

  if (status === 'authed') return <Navigate to={location.state?.from ?? '/app/dashboard'} replace />

  const submit = async (e) => {
    e.preventDefault()
    setFormError('')
    if (Object.keys(form.check()).length) return focusFirstError(formRef.current)
    setSaving(true)
    try {
      const u = await (isRegister ? register(form.values) : login(form.values))
      toast.success(isRegister ? `Welcome to StudySync, ${u.name.split(' ')[0]}.` : `Welcome back, ${u.name.split(' ')[0]}.`)
    } catch (err) {
      if (err instanceof ApiError && Object.keys(err.fields).length) {
        form.setErrors(err.fields)
        focusFirstError(formRef.current)
      } else {
        setFormError(err.message)
      }
      setSaving(false)
    }
  }

  const useDemo = () => {
    form.setField('email', DEMO_ACCOUNT.email)
    form.setField('password', DEMO_ACCOUNT.password)
  }

  return (
    <div className="mx-auto grid min-h-[calc(100vh-9rem)] max-w-6xl items-center gap-10 px-4 py-10 md:px-8 lg:grid-cols-2">
      <div className="hidden lg:block">
        <p className="font-display text-4xl font-extrabold leading-tight">
          {isRegister ? 'Start a group, or find one that fits.' : 'Pick up where your group left off.'}
        </p>
        <p className="mt-4 max-w-md text-lg text-ink/80">
          {isRegister ? 'Your account gives you a dashboard, a shelf for shared material and a calendar of sessions.' : 'Your resources, discussions and next sessions are waiting.'}
        </p>
      </div>

      <div className="mx-auto w-full max-w-md rounded-lg border border-line bg-white p-6 sm:p-8">
        <h1 className="font-display text-2xl font-bold">{isRegister ? 'Create your account' : 'Log in'}</h1>

        {formError && (
          <div role="alert" className="mt-4 flex items-start gap-2 rounded-md border border-danger/40 bg-danger-soft p-3 text-sm font-medium text-ink">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-hidden="true" />
            {formError}
          </div>
        )}

        <form ref={formRef} onSubmit={submit} noValidate className="mt-5 space-y-4">
          {isRegister && <Input label="Full name" required autoComplete="name" {...form.bind('name')} />}
          <Input label="Email" required type="email" autoComplete="email" inputMode="email" placeholder="you@college.edu" {...form.bind('email')} />
          <Input
            label="Password"
            required
            type={showPassword ? 'text' : 'password'}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            hint={isRegister ? 'At least 8 characters, with a letter and a number.' : undefined}
            {...form.bind('password')}
          />
          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={showPassword} onChange={(e) => setShowPassword(e.target.checked)} className="h-4 w-4 accent-[#2F4FCF]" />
            Show password
          </label>
          <Button type="submit" size="lg" className="w-full" loading={saving}>
            {isRegister ? 'Create account' : 'Log in'}
          </Button>
        </form>

        {!isRegister && (
          <div className="mt-4">
            <Button variant="secondary" className="w-full" onClick={useDemo}>
              Fill in the demo account
            </Button>
          </div>
        )}

        <p className="mt-6 text-center text-sm text-muted">
          {isRegister ? 'Already have an account?' : 'New to StudySync?'}{' '}
          <Link to={isRegister ? '/login' : '/register'} state={location.state} className="font-semibold text-marker underline underline-offset-2">
            {isRegister ? 'Log in' : 'Create an account'}
          </Link>
        </p>
      </div>
    </div>
  )
}
