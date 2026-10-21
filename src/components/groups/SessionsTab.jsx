import { useRef, useState } from 'react'
import { CalendarDays, Plus } from 'lucide-react'
import { sessions, ApiError } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import { useForm } from '../../hooks/useForm'
import { useRsvp } from '../../hooks/useRsvp'
import { useToast } from '../../context/ToastContext'
import { required, minLength, maxLength, url } from '../../utils/validation'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import { Input, focusFirstError } from '../ui/Fields'
import { EmptyState, ErrorState } from '../ui/States'
import { ListSkeleton } from '../ui/Skeleton'
import SessionItem from './SessionItem'

const RULES = {
  title: [required('a title'), minLength(3, 'Title'), maxLength(100, 'Title')],
  startsAt: [(v) => (!v ? 'Pick a date and time.' : new Date(v) <= new Date() ? 'Pick a time in the future.' : '')],
  durationMin: [(v) => (Number(v) >= 15 && Number(v) <= 300 ? '' : 'Enter a length between 15 and 300 minutes.')],
  meetingLink: [(v) => (String(v ?? '').trim() ? url(v) : '')],
}

function ScheduleModal({ open, onClose, groupId, onCreated }) {
  const toast = useToast()
  const formRef = useRef(null)
  const form = useForm({ title: '', startsAt: '', durationMin: '60', meetingLink: '' }, RULES)
  const [saving, setSaving] = useState(false)

  const close = () => {
    form.reset()
    onClose()
  }
  const submit = async (e) => {
    e.preventDefault()
    if (Object.keys(form.check()).length) return focusFirstError(formRef.current)
    setSaving(true)
    try {
      await sessions.create(groupId, form.values)
      toast.success('Session scheduled. Members can RSVP now.')
      close()
      onCreated()
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        form.setErrors(err.fields)
        focusFirstError(formRef.current)
      } else toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={close} title="Schedule a session" description="Members will see it on their dashboard and can reply with Going, Maybe or Can’t go.">
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <Input label="Title" required {...form.bind('title')} />
        <Input label="Starts at" required type="datetime-local" {...form.bind('startsAt')} />
        <Input label="Length in minutes" required type="number" min="15" max="300" step="5" inputMode="numeric" {...form.bind('durationMin')} />
        <Input label="Meeting link" type="url" inputMode="url" placeholder="https://" hint="Optional. Add a Meet, Zoom or Teams link." {...form.bind('meetingLink')} />
        <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Schedule session
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export default function SessionsTab({ group }) {
  const [scheduling, setScheduling] = useState(false)
  const { data, error, loading, reload, setData } = useAsync(() => sessions.list(group.id), [group.id])
  const onRsvp = useRsvp((updater) => setData((list) => updater(list ?? [])))
  const canSchedule = ['owner', 'moderator'].includes(group.myRole)
  const now = Date.now()
  const upcoming = (data ?? []).filter((s) => new Date(s.startsAt).getTime() > now)
  const past = (data ?? []).filter((s) => new Date(s.startsAt).getTime() <= now).reverse()

  return (
    <div>
      {canSchedule && (
        <div className="mb-4 flex justify-end">
          <Button onClick={() => setScheduling(true)}>
            <Plus className="h-4 w-4" aria-hidden="true" />
            Schedule session
          </Button>
        </div>
      )}

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <ListSkeleton />
      ) : (
        <>
          {upcoming.length === 0 ? (
            <EmptyState icon={CalendarDays} title="No sessions coming up" action={canSchedule ? <Button onClick={() => setScheduling(true)}>Schedule one</Button> : undefined}>
              {canSchedule ? 'Pick a time and the group can RSVP.' : 'A moderator or the owner can schedule the next session.'}
            </EmptyState>
          ) : (
            <section aria-labelledby="upcoming-heading">
              <h2 id="upcoming-heading" className="mb-3 font-display text-lg font-bold">
                Upcoming
              </h2>
              <ul className="space-y-3">
                {upcoming.map((s) => (
                  <SessionItem key={s.id} session={s} onRsvp={onRsvp} />
                ))}
              </ul>
            </section>
          )}
          {past.length > 0 && (
            <section aria-labelledby="past-heading" className="mt-8">
              <h2 id="past-heading" className="mb-3 font-display text-lg font-bold">
                Earlier sessions
              </h2>
              <ul className="space-y-3">
                {past.map((s) => (
                  <SessionItem key={s.id} session={s} past />
                ))}
              </ul>
            </section>
          )}
        </>
      )}

      <ScheduleModal open={scheduling} onClose={() => setScheduling(false)} groupId={group.id} onCreated={reload} />
    </div>
  )
}
