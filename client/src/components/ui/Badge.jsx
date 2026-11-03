const TONES = {
  neutral: 'bg-ink/10 text-ink',
  marker: 'bg-marker-soft text-marker-dark',
  hilite: 'bg-hilite text-ink',
  success: 'bg-success-soft text-success',
  danger: 'bg-danger-soft text-danger',
}

export default function Badge({ tone = 'neutral', children, className = '' }) {
  return <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-semibold ${TONES[tone]} ${className}`}>{children}</span>
}
