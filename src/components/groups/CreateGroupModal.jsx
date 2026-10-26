import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { groups, ApiError } from '../../api'
import { useForm } from '../../hooks/useForm'
import { useToast } from '../../context/ToastContext'
import { required, minLength, maxLength } from '../../utils/validation'
import { SUBJECTS } from '../../utils/subjects'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { Input, Select, Textarea, RadioGroup, focusFirstError } from '../ui/Fields'

const RULES = {
  name: [required('a group name'), minLength(3, 'Group name'), maxLength(60, 'Group name')],
  description: [required('a short description'), minLength(10, 'Description'), maxLength(300, 'Description')],
  subject: [(v) => (v ? '' : 'Choose a subject.')],
}

export default function CreateGroupModal({ open, onClose }) {
  const navigate = useNavigate()
  const toast = useToast()
  const formRef = useRef(null)
  const form = useForm({ name: '', subject: '', description: '', visibility: 'public' }, RULES)
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
      const group = await groups.create(form.values)
      toast.success(`"${group.name}" is ready. Share the invite code ${group.inviteCode} to bring people in.`)
      form.reset()
      onClose()
      navigate(`/app/groups/${group.id}`)
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
    <Modal open={open} onClose={close} title="Create a study group" description="Pick a subject and say what the group is for. You can invite people afterwards.">
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <Input label="Group name" required maxLength={60} {...form.bind('name')} />
        <Select label="Subject" required {...form.bind('subject')}>
          <option value="">Choose a subject</option>
          {SUBJECTS.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
        <Textarea label="What is this group for?" required hint="Up to 300 characters." {...form.bind('description')} />
        <RadioGroup
          legend="Who can find this group?"
          name="visibility"
          value={form.values.visibility}
          onChange={(v) => form.setField('visibility', v)}
          options={[
            { value: 'public', label: 'Public', description: 'Anyone can find it in Discover and join.' },
            { value: 'private', label: 'Private', description: 'Only people with the invite code can join.' },
          ]}
        />
        <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Create group
          </Button>
        </div>
      </form>
    </Modal>
  )
}
