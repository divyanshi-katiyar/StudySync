import { Link } from 'react-router-dom'
import { Clock, ExternalLink, Users } from 'lucide-react'
import { formatTime, pluralize } from '../../utils/format'

const OPTIONS = [
  { value: 'going', label: 'Going' },
  { value: 'maybe', label: 'Maybe' },
  { value: 'no', label: 'Can\u2019t go' },
]

/** One study session: a date block like a ticket stub, the details, and a three-way RSVP control. */
export default function SessionItem({ session, onRsvp, showGroup = false, past = false }) {
  const start = new Date(session.startsAt)
  const day = start.getDate()
  const month = start.toLocaleString('en-IN', { month: 'short' })
  const weekday = start.toLocaleString('en-IN', { weekday: 'short' })
  const end = new Date(start.getTime() + session.durationMin * 60_000)

  return (
    <li className={`flex gap-4 rounded-md border border-line bg-white p-4 ${past ? 'opacity-75' : ''}`}>
      <div aria-hidden="true" className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded border-2 border-dashed border-ink/30 bg-paper text-center leading-none">
        <span className="text-xs font-semibold text-muted">{weekday}</span>
        <span className="font-display text-2xl font-extrabold">{day}</span>
        <span className="text-xs font-semibold text-muted">{month}</span>
      </div>

      <div className="min-w-0 flex-1">
        <h3 className="font-display text-base font-bold leading-snug">{session.title}</h3>
        {showGroup && (
          <p className="text-sm">
            <Link to={`/app/groups/${session.groupId}?tab=sessions`} className="font-semibold hover:underline" style={{ color: session.groupColor }}>
              {session.groupName}
            </Link>
          </p>
        )}
        <p className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
          <span className="inline-flex items-center gap-1.5">
            <Clock className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">{start.toDateString()}, </span>
            {formatTime(start)} to {formatTime(end)}
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Users className="h-4 w-4" aria-hidden="true" />
            {pluralize(session.goingCount, 'person')} going
          </span>
          {session.meetingLink && (
            <a href={session.meetingLink} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1.5 font-semibold text-marker hover:underline">
              Meeting link
              <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
              <span className="sr-only">(opens in a new tab)</span>
            </a>
          )}
        </p>

        {!past && onRsvp && (
          <div role="group" aria-label={`RSVP for ${session.title}`} className="mt-3 inline-flex overflow-hidden rounded-md border border-ink/30">
            {OPTIONS.map((o, i) => {
              const pressed = session.myRsvp === o.value
              return (
                <button
                  key={o.value}
                  type="button"
                  aria-pressed={pressed}
                  onClick={() => onRsvp(session, o.value)}
                  className={`min-h-[40px] px-3.5 text-sm font-semibold ${i > 0 ? 'border-l border-ink/30' : ''} ${pressed ? 'bg-hilite text-ink' : 'bg-white text-muted hover:bg-paper hover:text-ink'}`}
                >
                  {o.label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </li>
  )
}
