import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Search, SearchX } from 'lucide-react'
import { groups } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useDebounce } from '../hooks/useDebounce'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../context/ToastContext'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/States'
import { CardSkeleton } from '../components/ui/Skeleton'
import GroupCard from '../components/groups/GroupCard'

/**
 * Search public groups. Filters live in the URL (?search=&subject=&sort=&page=), so a search can be
 * bookmarked, shared, and survives the Back button.
 */
export default function Discover() {
  usePageTitle('Discover groups')
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const subject = params.get('subject') ?? ''
  const sort = params.get('sort') ?? 'popular'
  const page = Number(params.get('page') ?? 1)
  const urlSearch = params.get('search') ?? ''

  const [text, setText] = useState(urlSearch)
  const debounced = useDebounce(text, 300)
  const [joiningId, setJoiningId] = useState(null)

  // Keep the box in step when the global search bar in the top bar changes the URL.
  useEffect(() => setText(urlSearch), [urlSearch])

  const update = (changes) => {
    const next = new URLSearchParams(params)
    Object.entries(changes).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)))
    if (!('page' in changes)) next.delete('page')
    setParams(next, { replace: true })
  }

  useEffect(() => {
    if (debounced !== urlSearch) update({ search: debounced.trim() })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debounced])

  const { data, error, loading, reload, setData } = useAsync(() => groups.list({ search: urlSearch, subject, sort, page }), [urlSearch, subject, sort, page])

  const join = async (group) => {
    setJoiningId(group.id)
    try {
      const updated = await groups.join(group.id)
      setData((d) => ({ ...d, items: d.items.map((g) => (g.id === group.id ? updated : g)) }))
      toast.success(`You joined "${group.name}".`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setJoiningId(null)
    }
  }

  const hasFilters = Boolean(urlSearch || subject)
  const clear = () => {
    setText('')
    setParams({}, { replace: true })
  }

  return (
    <>
      <PageHeader title="Discover study groups">Find a public group by name or subject. Private groups are joined with an invite code from My groups.</PageHeader>

      <div className="mb-5 grid gap-3 md:grid-cols-[1fr_12rem_10rem]">
        <div role="search">
          <label htmlFor="discover-search" className="mb-1 block text-sm font-semibold">
            Search groups
          </label>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
            <input id="discover-search" type="search" value={text} onChange={(e) => setText(e.target.value)} placeholder="Name, subject or keyword" className="w-full rounded-md border border-ink/30 bg-white py-2.5 pl-9 pr-3 text-base placeholder:text-muted hover:border-ink/60 md:text-sm" />
          </div>
        </div>
        <div>
          <label htmlFor="discover-subject" className="mb-1 block text-sm font-semibold">
            Subject
          </label>
          <select id="discover-subject" value={subject} onChange={(e) => update({ subject: e.target.value })} className="w-full rounded-md border border-ink/30 bg-white px-3 py-2.5 text-base hover:border-ink/60 md:text-sm">
            <option value="">All subjects</option>
            {groups.subjects.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="discover-sort" className="mb-1 block text-sm font-semibold">
            Sort by
          </label>
          <select id="discover-sort" value={sort} onChange={(e) => update({ sort: e.target.value === 'popular' ? '' : e.target.value })} className="w-full rounded-md border border-ink/30 bg-white px-3 py-2.5 text-base hover:border-ink/60 md:text-sm">
            <option value="popular">Most members</option>
            <option value="newest">Newest</option>
          </select>
        </div>
      </div>

      <p aria-live="polite" className="mb-3 min-h-[1.5rem] text-sm text-muted">
        {data && !error ? `Showing ${data.items.length} of ${data.total} ${data.total === 1 ? 'group' : 'groups'}` : ''}
      </p>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <CardSkeleton count={6} />
      ) : data.items.length === 0 ? (
        <EmptyState icon={SearchX} title="No groups match your search" action={hasFilters ? <Button variant="secondary" onClick={clear}>Clear search and filters</Button> : undefined}>
          Try a shorter keyword or a different subject.
        </EmptyState>
      ) : (
        <>
          <ul className={`grid gap-4 sm:grid-cols-2 lg:grid-cols-3 ${loading ? 'opacity-60' : ''}`}>
            {data.items.map((g) => (
              <li key={g.id} className="flex">
                <div className="flex-1">
                  <GroupCard group={g} onJoin={join} joining={joiningId === g.id} />
                </div>
              </li>
            ))}
          </ul>

          {data.pages > 1 && (
            <nav aria-label="Pagination" className="mt-6 flex items-center justify-center gap-3">
              <Button variant="secondary" size="sm" disabled={data.page <= 1} onClick={() => update({ page: String(data.page - 1) })}>
                <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                Previous
              </Button>
              <p className="text-sm text-muted" aria-current="page">
                Page {data.page} of {data.pages}
              </p>
              <Button variant="secondary" size="sm" disabled={data.page >= data.pages} onClick={() => update({ page: String(data.page + 1) })}>
                Next
                <ChevronRight className="h-4 w-4" aria-hidden="true" />
              </Button>
            </nav>
          )}
        </>
      )}
    </>
  )
}
