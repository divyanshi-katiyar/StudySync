import { Link } from 'react-router-dom'
import { CalendarDays, Lock, Users } from 'lucide-react'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import { formatDateTime, pluralize } from '../../utils/format'

/**
 * Group summary. The coloured spine on the left is the subject colour, like the binding of a notebook;
 * the subject name is always written out too, so colour is never the only cue.
 */
export default function GroupCard({ group, onJoin, joining = false }) {
  const headingId = `group-${group.id}-name`
  return (
    <article aria-labelledby={headingId} className="flex overflow-hidden rounded-md border border-line bg-white">
      <div aria-hidden="true" className="w-2 shrink-0" style={{ backgroundColor: group.color }} />
      <div className="flex min-w-0 flex-1 flex-col p-4">
        <div className="flex items-start justify-between gap-2">
          <h3 id={headingId} className="font-display text-lg font-bold leading-snug">
            <Link to={`/app/groups/${group.id}`} className="rounded hover:text-marker hover:underline">
              {group.name}
            </Link>
          </h3>
          {group.isMember && <Badge tone="marker">{group.myRole === 'owner' ? 'Owner' : group.myRole === 'moderator' ? 'Moderator' : 'Member'}</Badge>}
        </div>
        <p className="mt-0.5 text-sm font-semibold" style={{ color: group.color }}>
          {group.subject}
        </p>
        <p className="mt-2 line-clamp-3 flex-1 text-sm text-muted">{group.description}</p>

        <dl className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
          <div className="flex items-center gap-1.5">
            <Users className="h-4 w-4" aria-hidden="true" />
            <dt className="sr-only">Members</dt>
            <dd>{pluralize(group.memberCount, 'member')}</dd>
          </div>
          {group.visibility === 'private' && (
            <div className="flex items-center gap-1.5">
              <Lock className="h-4 w-4" aria-hidden="true" />
              <dt className="sr-only">Visibility</dt>
              <dd>Private</dd>
            </div>
          )}
          {group.nextSession && (
            <div className="flex items-center gap-1.5">
              <CalendarDays className="h-4 w-4" aria-hidden="true" />
              <dt className="sr-only">Next session</dt>
              <dd>{formatDateTime(group.nextSession.startsAt)}</dd>
            </div>
          )}
        </dl>

        <div className="mt-4">
          {group.isMember ? (
            <Button to={`/app/groups/${group.id}`} variant="secondary" size="sm">
              Open group<span className="sr-only">: {group.name}</span>
            </Button>
          ) : (
            <Button size="sm" loading={joining} onClick={() => onJoin?.(group)}>
              Join group<span className="sr-only">: {group.name}</span>
            </Button>
          )}
        </div>
      </div>
    </article>
  )
}
