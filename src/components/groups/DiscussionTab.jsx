import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageSquare, Plus } from 'lucide-react'
import { posts, ApiError } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import { useForm } from '../../hooks/useForm'
import { useToast } from '../../context/ToastContext'
import { required, minLength, maxLength } from '../../utils/validation'
import { pluralize, timeAgo } from '../../utils/format'
import Avatar from '../ui/Avatar'
import Button from '../ui/Button'
import Modal from '../ui/Modal'
import { Input, Textarea, focusFirstError } from '../ui/Fields'
import { EmptyState, ErrorState } from '../ui/States'
import { ListSkeleton } from '../ui/Skeleton'

const RULES = {
  title: [required('a title'), minLength(5, 'Title'), maxLength(120, 'Title')],
  body: [required('some details'), minLength(10, 'Details')],
}

function NewPostModal({ open, onClose, groupId, onCreated }) {
  const toast = useToast()
  const formRef = useRef(null)
  const form = useForm({ title: '', body: '' }, RULES)
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
      await posts.create(groupId, form.values)
      toast.success('Post published.')
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
    <Modal open={open} onClose={close} title="Start a discussion" description="Ask a question or share a plan. Everyone in the group can reply.">
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <Input label="Title" required {...form.bind('title')} />
        <Textarea label="Details" required rows={5} {...form.bind('body')} />
        <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Publish post
          </Button>
        </div>
      </form>
    </Modal>
  )
}

export default function DiscussionTab({ group }) {
  const [creating, setCreating] = useState(false)
  const { data, error, loading, reload } = useAsync(() => posts.list(group.id), [group.id])

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <Button onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          New post
        </Button>
      </div>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <ListSkeleton />
      ) : data.length === 0 ? (
        <EmptyState icon={MessageSquare} title="No discussions yet" action={<Button onClick={() => setCreating(true)}>Start the first one</Button>}>
          Ask a question, propose a study plan or compare approaches. Replies stay together in one thread.
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {data.map((p) => (
            <li key={p.id} className="flex gap-3 rounded-md border border-line bg-white p-4">
              <Avatar name={p.authorName} />
              <div className="min-w-0 flex-1">
                <h3 className="font-display text-base font-bold leading-snug">
                  <Link to={`/app/groups/${group.id}/posts/${p.id}`} className="hover:text-marker hover:underline">
                    {p.title}
                  </Link>
                </h3>
                <p className="mt-0.5 text-sm text-muted">
                  {p.authorName} posted {timeAgo(p.createdAt)}
                </p>
                <p className="mt-2 line-clamp-2 text-sm text-ink">{p.body}</p>
                <p className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-muted">
                  <MessageSquare className="h-4 w-4" aria-hidden="true" />
                  {pluralize(p.commentCount, 'reply').replace('replys', 'replies')}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <NewPostModal open={creating} onClose={() => setCreating(false)} groupId={group.id} onCreated={reload} />
    </div>
  )
}
