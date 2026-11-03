/** Date and text formatting helpers (all pure functions, easy to unit test). */

const dateFmt = new Intl.DateTimeFormat('en-IN', { weekday: 'short', day: 'numeric', month: 'short' })
const timeFmt = new Intl.DateTimeFormat('en-IN', { hour: 'numeric', minute: '2-digit', hour12: true })

export const formatDate = (iso) => dateFmt.format(new Date(iso))
export const formatTime = (iso) => timeFmt.format(new Date(iso))
export const formatDateTime = (iso) => `${formatDate(iso)}, ${formatTime(iso)}`

/** "2 days ago", "just now", "in 3 hours" */
export function timeAgo(iso, now = Date.now()) {
  const diff = new Date(iso).getTime() - now
  const abs = Math.abs(diff)
  const units = [
    ['day', 86_400_000],
    ['hour', 3_600_000],
    ['minute', 60_000],
  ]
  for (const [name, ms] of units) {
    if (abs >= ms) {
      const n = Math.floor(abs / ms)
      const label = `${n} ${name}${n > 1 ? 's' : ''}`
      return diff < 0 ? `${label} ago` : `in ${label}`
    }
  }
  return 'just now'
}

export const initials = (name = '') =>
  name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join('')

export const pluralize = (n, word) => `${n} ${word}${n === 1 ? '' : 's'}`
