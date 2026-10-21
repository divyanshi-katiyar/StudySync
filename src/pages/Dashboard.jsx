import { Link } from 'react-router-dom'
import { CalendarDays, Library } from 'lucide-react'
import { dashboard } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useRsvp } from '../hooks/useRsvp'
import { usePageTitle } from '../hooks/usePageTitle'
import { useAuth } from '../context/AuthContext'
import { useNotifications } from '../context/NotificationsContext'
import { timeAgo } from '../utils/format'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/States'
import { CardSkeleton, ListSkeleton, Skeleton } from '../components/ui/Skeleton'
import GroupCard from '../components/groups/GroupCard'
import SessionItem from '../components/groups/SessionItem'

const greeting = () => {
  const h = new Date().getHours()
  return h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening'
}

export default function Dashboard() {
  usePageTitle('Dashboard')
  const { user } = useAuth()
  const { items: notifications } = useNotifications()
  const { data, error, loading, reload, setData } = useAsync(() => dashboard.get(), [])
  const onRsvp = useRsvp((updater) => setData((d) => ({ ...d, upcomingSessions: updater(d.upcomingSessions) })))
  const first = user?.name.split(' ')[0]

  const summary = data && [
    { label: data.counts.groups === 1 ? 'group joined' : 'groups joined', value: data.counts.groups, to: '/app/groups' },
    { label: data.counts.sessionsThisWeek === 1 ? 'session this week' : 'sessions this week', value: data.counts.sessionsThisWeek, to: '/app/sessions' },
    { label: 'new resources this week', value: data.counts.newResources, to: '/app/groups' },
  ]

  return (
    <>
      <PageHeader title={`${greeting()}, ${first}`} actions={<Button to="/app/discover" variant="secondary">Find a group</Button>}>
        Here is what is coming up and what changed in your groups.
      </PageHeader>

      {error ? (
        <ErrorState error={error} onRetry={reload} title="We could not load your dashboard" />
      ) : (
        <div className="grid gap-8 lg:grid-cols-[1fr_20rem]">
          <div className="min-w-0 space-y-8">
            {/* Summary: three counts that link to the full lists */}
            {loading && !data ? (
              <Skeleton className="h-20 w-full" />
            ) : (
              <dl className="grid grid-cols-3 divide-x divide-line rounded-md border border-line bg-white">
                {summary.map((s) => (
                  <div key={s.label} className="p-4">
                    <dd className="font-display text-3xl font-extrabold">{s.value}</dd>
                    <dt className="mt-0.5 text-sm">
                      <Link to={s.to} className="text-muted underline-offset-2 hover:text-marker hover:underline">
                        {s.label}
                      </Link>
                    </dt>
                  </div>
                ))}
              </dl>
            )}

            <section aria-labelledby="upcoming-heading">
              <div className="mb-3 flex items-baseline justify-between">
                <h2 id="upcoming-heading" className="font-display text-xl font-bold">
                  Upcoming sessions
                </h2>
                <Link to="/app/sessions" className="text-sm font-semibold text-marker hover:underline">
                  See all sessions
                </Link>
              </div>
              {loading && !data ? (
                <ListSkeleton rows={2} />
              ) : data.upcomingSessions.length === 0 ? (
                <EmptyState icon={CalendarDays} title="No sessions scheduled" action={<Button to="/app/groups" variant="secondary">Open one of your groups</Button>}>
                  When a moderator schedules a session in one of your groups, it will appear here.
                </EmptyState>
              ) : (
                <ul className="space-y-3">
                  {data.upcomingSessions.map((s) => (
                    <SessionItem key={s.id} session={s} onRsvp={onRsvp} showGroup />
                  ))}
                </ul>
              )}
            </section>

            <section aria-labelledby="groups-heading">
              <div className="mb-3 flex items-baseline justify-between">
                <h2 id="groups-heading" className="font-display text-xl font-bold">
                  Your groups
                </h2>
                <Link to="/app/groups" className="text-sm font-semibold text-marker hover:underline">
                  See all groups
                </Link>
              </div>
              {loading && !data ? (
                <CardSkeleton count={2} />
              ) : data.myGroups.length === 0 ? (
                <EmptyState icon={Library} title="You have not joined a group yet" action={<Button to="/app/discover">Discover groups</Button>}>
                  Join a public group or create your own to start sharing resources.
                </EmptyState>
              ) : (
                <div className="grid gap-4 sm:grid-cols-2">
                  {data.myGroups.map((g) => (
                    <GroupCard key={g.id} group={g} />
                  ))}
                </div>
              )}
            </section>
          </div>

          <aside aria-labelledby="activity-heading" className="min-w-0">
            <h2 id="activity-heading" className="mb-3 font-display text-xl font-bold">
              Recent activity
            </h2>
            {notifications.length === 0 ? (
              <p className="rounded-md border border-dashed border-ink/30 bg-white p-4 text-sm text-muted">Updates from your groups will show up here.</p>
            ) : (
              <ul className="divide-y divide-line rounded-md border border-line bg-white">
                {notifications.slice(0, 5).map((n) => (
                  <li key={n.id}>
                    <Link to={n.link} className={`block p-3 text-sm hover:bg-paper ${n.isRead ? 'text-muted' : 'font-semibold text-ink'}`}>
                      {!n.isRead && <span className="mr-1.5 inline-block h-2 w-2 rounded-full bg-hilite ring-1 ring-ink" aria-hidden="true" />}
                      {!n.isRead && <span className="sr-only">Unread: </span>}
                      {n.message}
                      <span className="mt-0.5 block text-xs font-normal text-muted">{timeAgo(n.createdAt)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </aside>
        </div>
      )}
    </>
  )
}
