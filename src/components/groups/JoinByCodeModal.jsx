import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { groups, ApiError } from '../../api'
import { useToast } from '../../context/ToastContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'
import { Input, focusFirstError } from '../ui/Fields'

export default function JoinByCodeModal({ open, onClose }) {
  const navigate = useNavigate()
  const toast = useToast()
  const formRef = useRef(null)
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  const close = () => {
    setCode('')
    setError('')
    onClose()
  }

  const submit = async (e) => {
    e.preventDefault()
    if (!code.trim()) {
      setError('Enter an invite code.')
      return focusFirstError(formRef.current)
    }
    setSaving(true)
    try {
      const group = await groups.joinByCode(code)
      toast.success(`You joined "${group.name}".`)
      close()
      navigate(`/app/groups/${group.id}`)
    } catch (err) {
      if (err instanceof ApiError && err.fields?.code) {
        setError(err.fields.code)
        focusFirstError(formRef.current)
      } else toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal open={open} onClose={close} size="sm" title="Join with an invite code" description="Ask a group owner or moderator for their code. Try COM-2026 to join the private demo group.">
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <Input
          label="Invite code"
          value={code}
          error={error}
          onChange={(e) => {
            setCode(e.target.value)
            setError('')
          }}
          autoComplete="off"
          autoCapitalize="characters"
          placeholder="ABC-1234"
        />
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Join group
          </Button>
        </div>
      </form>
    </Modal>
  )
}
