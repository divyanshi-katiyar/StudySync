import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { auth, ApiError, usesRealApi } from '../api'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { useForm } from '../hooks/useForm'
import { usePageTitle } from '../hooks/usePageTitle'
import { required, minLength, maxLength } from '../utils/validation'
import { formatDate } from '../utils/format'
import Avatar from '../components/ui/Avatar'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import PageHeader from '../components/ui/PageHeader'
import { Input, focusFirstError } from '../components/ui/Fields'

export default function Profile() {
  usePageTitle('Profile')
  const { user, updateProfile, logout } = useAuth()
  const toast = useToast()
  const navigate = useNavigate()
  const formRef = useRef(null)
  const form = useForm({ name: user.name }, { name: [required('your name'), minLength(2, 'Name'), maxLength(60, 'Name')] })
  const [saving, setSaving] = useState(false)
  const [confirmReset, setConfirmReset] = useState(false)
  const [resetting, setResetting] = useState(false)

  const save = async (e) => {
    e.preventDefault()
    if (Object.keys(form.check()).length) return focusFirstError(formRef.current)
    setSaving(true)
    try {
      await updateProfile(form.values)
      toast.success('Profile updated.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        form.setErrors(err.fields)
        focusFirstError(formRef.current)
      } else toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const reset = async () => {
    setResetting(true)
    try {
      await auth.resetDemoData()
      await logout()
      toast.success('Demo data was reset. Log in with the demo account to start fresh.')
      navigate('/login?demo=1', { replace: true })
    } catch (err) {
      toast.error(err.message)
      setResetting(false)
    }
  }

  return (
    <>
      <PageHeader title="Your profile">Update how your name appears to other members.</PageHeader>

      <div className="max-w-xl space-y-8">
        <section aria-labelledby="account-heading" className="rounded-md border border-line bg-white p-5">
          <div className="mb-5 flex items-center gap-4">
            <Avatar name={user.name} size="lg" />
            <div>
              <h2 id="account-heading" className="font-display text-xl font-bold">
                {user.name}
              </h2>
              <p className="text-sm text-muted">
                {user.email}, member since {formatDate(user.createdAt)}
              </p>
            </div>
          </div>
          <form ref={formRef} onSubmit={save} noValidate className="space-y-4">
            <Input label="Full name" required autoComplete="name" {...form.bind('name')} />
            <Button type="submit" loading={saving}>
              Save changes
            </Button>
          </form>
        </section>

        {!usesRealApi && (
        <section aria-labelledby="demo-heading" className="rounded-md border border-line bg-white p-5">
          <h2 id="demo-heading" className="font-display text-lg font-bold">
            Demo data
          </h2>
          <p className="mt-1 text-sm text-muted">This version stores everything in your browser. Resetting restores the sample groups and signs you out.</p>
          <Button variant="secondary" className="mt-3" onClick={() => setConfirmReset(true)}>
            Reset demo data
          </Button>
        </section>
        )}
      </div>

      <ConfirmDialog open={confirmReset} onClose={() => setConfirmReset(false)} onConfirm={reset} loading={resetting} title="Reset demo data?" message="Groups, posts, resources and accounts you created in this browser will be removed." confirmLabel="Reset demo data" />
    </>
  )
}
