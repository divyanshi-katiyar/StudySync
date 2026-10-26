import { useRef, useState } from 'react'
import { ExternalLink, FileText, Link2, Plus, Search, StickyNote, Trash2 } from 'lucide-react'
import { resources, ApiError } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import { useDebounce } from '../../hooks/useDebounce'
import { useForm } from '../../hooks/useForm'
import { useToast } from '../../context/ToastContext'
import { required, minLength, maxLength, url } from '../../utils/validation'
import { timeAgo } from '../../utils/format'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import ConfirmDialog from '../ui/ConfirmDialog'
import Modal from '../ui/Modal'
import { Input, Select, Textarea, focusFirstError } from '../ui/Fields'
import { EmptyState, ErrorState } from '../ui/States'
import { ListSkeleton } from '../ui/Skeleton'

const TYPES = [
  { value: '', label: 'All' },
  { value: 'link', label: 'Links' },
  { value: 'note', label: 'Notes' },
  { value: 'file', label: 'Files' },
]
const ICONS = { link: Link2, file: FileText, note: StickyNote }
const TYPE_NAMES = { link: 'Link', file: 'File', note: 'Note' }

function AddResourceModal({ open, onClose, groupId, onAdded }) {
  const toast = useToast()
  const formRef = useRef(null)
  const [saving, setSaving] = useState(false)
  const [tagText, setTagText] = useState('')
  const [type, setType] = useState('link')

  const rules = {
    title: [required('a title'), minLength(3, 'Title'), maxLength(100, 'Title')],
    ...(type === 'note' ? { body: [required('your note'), minLength(10, 'Note')] } : { url: [required('a link'), url] }),
  }
  const form = useForm({ title: '', url: '', body: '' }, rules)

  const close = () => {
    form.reset()
    setTagText('')
    setType('link')
    onClose()
  }

  const submit = async (e) => {
    e.preventDefault()
    if (Object.keys(form.check()).length) return focusFirstError(formRef.current)
    setSaving(true)
    try {
      await resources.add(groupId, { ...form.values, type, tags: tagText.split(',') })
      toast.success('Resource added. Your group can see it now.')
      close()
      onAdded()
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
    <Modal open={open} onClose={close} title="Add a resource" description="Share a link, a file link or a short note with the group.">
      <form ref={formRef} onSubmit={submit} noValidate className="space-y-4">
        <Select label="Type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="link">Link to a web page or video</option>
          <option value="file">Link to a file (PDF, slides, sheet)</option>
          <option value="note">Note written here</option>
        </Select>
        <Input label="Title" required {...form.bind('title')} />
        {type === 'note' ? (
          <Textarea label="Note" required rows={5} {...form.bind('body')} />
        ) : (
          <Input label={type === 'file' ? 'File link' : 'Link'} required type="url" inputMode="url" placeholder="https://" hint={type === 'file' ? 'Paste a share link from Drive, Dropbox or GitHub. Uploading files directly comes with the back end.' : undefined} {...form.bind('url')} />
        )}
        <Input label="Tags" hint="Separate with commas, for example: graphs, exam" value={tagText} onChange={(e) => setTagText(e.target.value)} />
        <div className="flex flex-col-reverse gap-2 pt-2 sm:flex-row sm:justify-end">
          <Button variant="secondary" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" loading={saving}>
            Add resource
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function ResourceItem({ resource, onDelete }) {
  const Icon = ICONS[resource.type]
  return (
    <li className="flex gap-3 rounded-md border border-line bg-white p-4">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-paper text-ink" aria-hidden="true">
        <Icon className="h-5 w-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="font-display text-base font-bold leading-snug">
            {resource.type === 'note' ? (
              resource.title
            ) : (
              <a href={resource.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 hover:text-marker hover:underline">
                {resource.title}
                <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                <span className="sr-only">(opens in a new tab)</span>
              </a>
            )}
          </h3>
          <Badge>{TYPE_NAMES[resource.type]}</Badge>
        </div>
        <p className="mt-0.5 text-sm text-muted">
          Shared by {resource.uploaderName}, {timeAgo(resource.createdAt)}
        </p>
        {resource.type === 'note' && (
          <details className="mt-2 text-sm">
            <summary className="cursor-pointer font-semibold text-marker">Read note</summary>
            <p className="mt-2 whitespace-pre-wrap rounded bg-paper p-3 text-ink">{resource.body}</p>
          </details>
        )}
        {resource.tags.length > 0 && (
          <ul className="mt-2 flex flex-wrap gap-1.5" aria-label="Tags">
            {resource.tags.map((t) => (
              <li key={t}>
                <Badge tone="marker">#{t}</Badge>
              </li>
            ))}
          </ul>
        )}
      </div>
      {resource.canDelete && (
        <button type="button" onClick={() => onDelete(resource)} className="-m-1 h-11 w-11 shrink-0 self-start rounded-md p-1 text-muted hover:bg-danger-soft hover:text-danger" aria-label={`Delete ${resource.title}`}>
          <Trash2 className="mx-auto h-5 w-5" aria-hidden="true" />
        </button>
      )}
    </li>
  )
}

export default function ResourcesTab({ group }) {
  const toast = useToast()
  const [type, setType] = useState('')
  const [search, setSearch] = useState('')
  const debounced = useDebounce(search, 250)
  const [adding, setAdding] = useState(false)
  const [toDelete, setToDelete] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const { data, error, loading, reload } = useAsync(() => resources.list(group.id, { type, search: debounced }), [group.id, type, debounced])

  const confirmDelete = async () => {
    setDeleting(true)
    try {
      await resources.remove(toDelete.id)
      toast.success(`"${toDelete.title}" was deleted.`)
      setToDelete(null)
      reload()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setDeleting(false)
    }
  }

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-center">
        <div role="search" className="relative flex-1">
          <label htmlFor="resource-search" className="sr-only">
            Search resources by title or tag
          </label>
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
          <input id="resource-search" type="search" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search by title or tag" className="w-full rounded-md border border-ink/30 bg-white py-2.5 pl-9 pr-3 text-sm placeholder:text-muted hover:border-ink/60" />
        </div>
        <div role="group" aria-label="Filter by type" className="inline-flex overflow-hidden rounded-md border border-ink/30">
          {TYPES.map((t, i) => (
            <button key={t.label} type="button" aria-pressed={type === t.value} onClick={() => setType(t.value)} className={`min-h-[44px] px-4 text-sm font-semibold ${i > 0 ? 'border-l border-ink/30' : ''} ${type === t.value ? 'bg-hilite text-ink' : 'bg-white text-muted hover:bg-paper hover:text-ink'}`}>
              {t.label}
            </button>
          ))}
        </div>
        <Button onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Add resource
        </Button>
      </div>

      <div aria-live="polite">
        {error ? (
          <ErrorState error={error} onRetry={reload} />
        ) : loading && !data ? (
          <ListSkeleton />
        ) : data.length === 0 ? (
          <EmptyState icon={FileText} title={search || type ? 'No resources match' : 'Nothing shared yet'} action={!search && !type ? <Button onClick={() => setAdding(true)}>Add the first resource</Button> : <Button variant="secondary" onClick={() => { setSearch(''); setType('') }}>Clear filters</Button>}>
            {search || type ? 'Try a different word or clear the filters.' : 'Notes, links and files your group shares will be kept here, newest first.'}
          </EmptyState>
        ) : (
          <ul className="space-y-3">
            {data.map((r) => (
              <ResourceItem key={r.id} resource={r} onDelete={setToDelete} />
            ))}
          </ul>
        )}
      </div>

      <AddResourceModal open={adding} onClose={() => setAdding(false)} groupId={group.id} onAdded={reload} />
      <ConfirmDialog open={Boolean(toDelete)} onClose={() => setToDelete(null)} onConfirm={confirmDelete} loading={deleting} title="Delete this resource?" message={`"${toDelete?.title}" will be removed for everyone in the group.`} confirmLabel="Delete resource" />
    </div>
  )
}
