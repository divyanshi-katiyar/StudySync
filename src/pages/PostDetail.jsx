import { useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { posts, ApiError } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useForm } from '../hooks/useForm'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../context/ToastContext'
import { required, minLength, maxLength } from '../utils/validation'
import { timeAgo, pluralize } from '../utils/format'
import Avatar from '../components/ui/Avatar'
import Button from '../components/ui/Button'
import { Textarea, focusFirstError } from '../components/ui/Fields'
import { ErrorState } from '../components/ui/States'
import { Skeleton } from '../components/ui/Skeleton'

export default function PostDetail() {
  const { groupId, postId } = useParams()
  const toast = useToast()
  const formRef = useRef(null)
  const { data: post, error, loading, reload, setData } = useAsync(() => posts.get(postId), [postId])
  usePageTitle(post?.title ?? 'Discussion')
  const form = useForm({ body: '' }, { body: [required('a reply'), minLength(2, 'Reply'), maxLength(1000, 'Reply')] })
  const [saving, setSaving] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (Object.keys(form.check()).length) return focusFirstError(formRef.current)
    setSaving(true)
    try {
      const comment = await posts.addComment(postId, form.values)
      setData((p) => ({ ...p, comments: [...p.comments, comment] }))
      form.reset()
      toast.success('Reply posted.')
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        form.setErrors(err.fields)
        focusFirstError(formRef.current)
      } else toast.error(err.message)
    } finally {
      setSaving(false)
    }
  }

  const back = (
    <Link to={`/app/groups/${groupId}?tab=discussion`} className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-marker hover:underline">
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to {post ? post.group.name : 'the group'}
    </Link>
  )

  if (error) return <div className="space-y-4">{back}<ErrorState error={error} onRetry={error.status ? undefined : reload} title="We could not open this discussion" /></div>
  if (loading && !post) return <div aria-busy="true" aria-label="Loading discussion" className="space-y-3"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-24 w-full" /></div>

  return (
    <>
      {back}
      <article className="rounded-md border border-line bg-white p-5">
        <h1 className="font-display text-2xl font-bold leading-tight">{post.title}</h1>
        <p className="mt-2 flex items-center gap-2 text-sm text-muted">
          <Avatar name={post.authorName} size="sm" />
          {post.authorName} posted {timeAgo(post.createdAt)}
        </p>
        <p className="mt-4 max-w-3xl whitespace-pre-wrap text-ink">{post.body}</p>
      </article>

      <section aria-labelledby="replies-heading" className="mt-8">
        <h2 id="replies-heading" className="mb-3 font-display text-xl font-bold">
          {pluralize(post.comments.length, 'reply').replace('replys', 'replies')}
        </h2>
        {post.comments.length > 0 && (
          <ul className="mb-6 space-y-3">
            {post.comments.map((c) => (
              <li key={c.id} className="flex gap-3 rounded-md border border-line bg-white p-4">
                <Avatar name={c.authorName} />
                <div className="min-w-0">
                  <p className="text-sm">
                    <span className="font-semibold">{c.authorName}</span> <span className="text-muted">{timeAgo(c.createdAt)}</span>
                  </p>
                  <p className="mt-1 whitespace-pre-wrap">{c.body}</p>
                </div>
              </li>
            ))}
          </ul>
        )}
        <form ref={formRef} onSubmit={submit} noValidate className="space-y-3">
          <Textarea label="Add a reply" rows={3} {...form.bind('body')} />
          <Button type="submit" loading={saving}>
            Post reply
          </Button>
        </form>
      </section>
    </>
  )
}
