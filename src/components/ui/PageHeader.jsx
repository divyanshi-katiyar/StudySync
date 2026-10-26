/** Page title block. The h1 is focusable so route changes can move focus here for screen-reader users. */
export default function PageHeader({ title, children, actions }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="font-display text-3xl font-bold leading-tight text-ink">{title}</h1>
        {children && <p className="mt-1 max-w-2xl text-muted">{children}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
