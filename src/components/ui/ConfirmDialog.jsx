import Modal from './Modal'
import Button from './Button'

/** Confirmation step for destructive actions. The confirm button says what will happen ("Delete group"), never just "OK". */
export default function ConfirmDialog({ open, onClose, onConfirm, title, message, confirmLabel, loading = false }) {
  return (
    <Modal open={open} onClose={onClose} title={title} size="sm">
      <p className="text-sm text-ink">{message}</p>
      <div className="mt-5 flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} loading={loading}>
          {confirmLabel}
        </Button>
      </div>
    </Modal>
  )
}
