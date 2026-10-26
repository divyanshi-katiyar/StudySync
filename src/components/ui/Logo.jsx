import { Link } from 'react-router-dom'

/** Logo mark: lines of text with a highlighter stroke across the last one. */
export function LogoMark({ className = 'h-8 w-8' }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="7" fill="#14213D" />
      <rect x="6" y="18" width="20" height="7" rx="1.5" fill="#FFE45C" />
      <path d="M9 21.5h14" stroke="#14213D" strokeWidth="2" strokeLinecap="round" />
      <path d="M9 8h14M9 13h9" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  )
}

export default function Logo({ to = '/', dark = false }) {
  return (
    <Link to={to} className="inline-flex items-center gap-2.5 rounded-md" aria-label="StudySync home">
      <LogoMark />
      <span className={`font-display text-xl font-extrabold tracking-tight ${dark ? 'text-white' : 'text-ink'}`}>StudySync</span>
    </Link>
  )
}
