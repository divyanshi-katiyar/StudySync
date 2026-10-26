import { AlertTriangle } from 'lucide-react'
import Button from './Button'

/** Empty lists are an invitation to act: say what belongs here and offer the next step. */
export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="rounded-md border border-dashed border-ink/30 bg-white px-6 py-10 text-center">
      {Icon && <Icon className="mx-auto mb-3 h-8 w-8 text-muted" aria-hidden="true" />}
      <h3 className="font-display text-lg font-bold text-ink">{title}</h3>
      {children && <p className="mx-auto mt-1 max-w-md text-sm text-muted">{children}</p>}
      {action && <div className="mt-4 flex justify-center">{action}</div>}
    </div>
  )
}

/** Errors say what happened and how to recover. */
export function ErrorState({ error, onRetry, title = 'We could not load this' }) {
  return (
    <div role="alert" className="rounded-md border border-danger/40 bg-danger-soft p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden="true" />
        <div>
          <h3 className="font-semibold text-ink">{title}</h3>
          <p className="mt-1 text-sm text-ink">{error?.message ?? 'Something went wrong. Check your connection and try again.'}</p>
          {onRetry && (
            <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
              Try again
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
