import { useRef } from 'react'

/**
 * Tab list following the WAI-ARIA tabs pattern: roving tabindex, arrow keys / Home / End move and
 * activate tabs. The caller renders the matching `role="tabpanel"` with id `panel-${value}`.
 * Styled like notebook index tabs; the active tab shares the page's colour and carries the highlighter mark.
 */
export default function Tabs({ tabs, value, onChange, label }) {
  const refs = useRef({})

  const onKeyDown = (e) => {
    const index = tabs.findIndex((t) => t.id === value)
    let next = null
    if (e.key === 'ArrowRight') next = (index + 1) % tabs.length
    if (e.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length
    if (e.key === 'Home') next = 0
    if (e.key === 'End') next = tabs.length - 1
    if (next === null) return
    e.preventDefault()
    onChange(tabs[next].id)
    refs.current[tabs[next].id]?.focus()
  }

  return (
    <div role="tablist" aria-label={label} onKeyDown={onKeyDown} className="-mb-px flex gap-1 overflow-x-auto border-b border-line">
      {tabs.map((t) => {
        const active = t.id === value
        return (
          <button
            key={t.id}
            ref={(el) => (refs.current[t.id] = el)}
            role="tab"
            type="button"
            id={`tab-${t.id}`}
            aria-selected={active}
            aria-controls={`panel-${t.id}`}
            tabIndex={active ? 0 : -1}
            onClick={() => onChange(t.id)}
            className={`relative flex min-h-[44px] shrink-0 items-center gap-2 rounded-t-md border border-b-0 px-4 text-sm font-semibold ${
              active ? 'border-line bg-white text-ink' : 'border-transparent text-muted hover:bg-ink/5 hover:text-ink'
            }`}
          >
            {t.label}
            {t.count !== undefined && <span className={`rounded-full px-2 py-0.5 text-xs ${active ? 'bg-hilite text-ink' : 'bg-ink/10 text-ink'}`}>{t.count}</span>}
          </button>
        )
      })}
    </div>
  )
}
