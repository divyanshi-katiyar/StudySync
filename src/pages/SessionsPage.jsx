import { CalendarDays } from 'lucide-react'
import { sessions } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useRsvp } from '../hooks/useRsvp'
import { usePageTitle } from '../hooks/usePageTitle'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/States'
import { ListSkeleton } from '../components/ui/Skeleton'
import SessionItem from '../components/groups/SessionItem'

export default function SessionsPage() {
  usePageTitle('Sessions')
  const { data, error, loading, reload, setData } = useAsync(() => sessions.upcoming(), [])
  const onRsvp = useRsvp((updater) => setData((list) => updater(list ?? [])))

  return (
    <>
      <PageHeader title="Upcoming sessions">Every session in your groups, soonest first. Tell the group whether you are coming.</PageHeader>
      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <ListSkeleton />
      ) : data.length === 0 ? (
        <EmptyState icon={CalendarDays} title="No sessions coming up" action={<Button to="/app/groups" variant="secondary">Go to my groups</Button>}>
          Sessions scheduled by your group moderators will appear here.
        </EmptyState>
      ) : (
        <ul className="space-y-3">
          {data.map((s) => (
            <SessionItem key={s.id} session={s} onRsvp={onRsvp} showGroup />
          ))}
        </ul>
      )}
    </>
  )
}
