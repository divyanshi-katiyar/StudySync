import { forwardRef, useId } from 'react'
import { AlertCircle } from 'lucide-react'

const controlClasses = (error) =>
  `block w-full rounded-md border bg-white px-3 py-2.5 text-base text-ink placeholder:text-muted/70 md:text-sm ${
    error ? 'border-danger' : 'border-ink/30 hover:border-ink/60'
  }`

/** Shared wrapper: visible label, optional hint, and an error message linked with aria-describedby. */
function FieldShell({ id, label, hint, error, required, children }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-semibold text-ink">
        {label}
        {required && <span aria-hidden="true" className="text-danger"> *</span>}
      </label>
      {hint && (
        <p id={`${id}-hint`} className="mb-1.5 text-sm text-muted">
          {hint}
        </p>
      )}
      {children}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 flex items-start gap-1.5 text-sm font-medium text-danger">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{error}</span>
        </p>
      )}
    </div>
  )
}

const describedBy = (id, hint, error) => [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(' ') || undefined

export const Input = forwardRef(function Input({ label, hint, error, required, id, className = '', ...props }, ref) {
  const auto = useId()
  const inputId = id ?? auto
  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error} required={required}>
      <input ref={ref} id={inputId} aria-invalid={error ? 'true' : undefined} aria-describedby={describedBy(inputId, hint, error)} aria-required={required || undefined} className={`${controlClasses(error)} ${className}`} {...props} />
    </FieldShell>
  )
})

export const Textarea = forwardRef(function Textarea({ label, hint, error, required, id, rows = 4, ...props }, ref) {
  const auto = useId()
  const inputId = id ?? auto
  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error} required={required}>
      <textarea ref={ref} id={inputId} rows={rows} aria-invalid={error ? 'true' : undefined} aria-describedby={describedBy(inputId, hint, error)} aria-required={required || undefined} className={controlClasses(error)} {...props} />
    </FieldShell>
  )
})

export const Select = forwardRef(function Select({ label, hint, error, required, id, children, ...props }, ref) {
  const auto = useId()
  const inputId = id ?? auto
  return (
    <FieldShell id={inputId} label={label} hint={hint} error={error} required={required}>
      <select ref={ref} id={inputId} aria-invalid={error ? 'true' : undefined} aria-describedby={describedBy(inputId, hint, error)} aria-required={required || undefined} className={controlClasses(error)} {...props}>
        {children}
      </select>
    </FieldShell>
  )
})

/** Group of radio buttons with a legend (used for visibility and RSVP-style choices). */
export function RadioGroup({ legend, name, value, onChange, options, error }) {
  return (
    <fieldset>
      <legend className="mb-1.5 text-sm font-semibold text-ink">{legend}</legend>
      <div className="space-y-2">
        {options.map((o) => (
          <label key={o.value} className={`flex cursor-pointer items-start gap-3 rounded-md border p-3 ${value === o.value ? 'border-marker bg-marker-soft' : 'border-ink/25 bg-white hover:border-ink/50'}`}>
            <input type="radio" name={name} value={o.value} checked={value === o.value} onChange={() => onChange(o.value)} className="mt-1 h-4 w-4 accent-[#2F4FCF]" />
            <span>
              <span className="block text-sm font-semibold text-ink">{o.label}</span>
              <span className="block text-sm text-muted">{o.description}</span>
            </span>
          </label>
        ))}
      </div>
      {error && <p className="mt-1.5 text-sm font-medium text-danger">{error}</p>}
    </fieldset>
  )
}

/** Focuses the first invalid control after a failed submit so keyboard and screen-reader users land on the problem. */
export function focusFirstError(formEl) {
  requestAnimationFrame(() => formEl?.querySelector('[aria-invalid="true"]')?.focus())
}
