import { Link } from 'react-router-dom'
import { Loader2 } from 'lucide-react'

const VARIANTS = {
  primary: 'bg-marker text-white hover:bg-marker-dark',
  secondary: 'bg-white text-ink border border-ink/30 hover:border-ink hover:bg-paper',
  ghost: 'text-ink hover:bg-ink/5',
  danger: 'bg-danger text-white hover:bg-[#8F1B12]',
  highlight: 'bg-hilite text-ink hover:bg-[#FFD93A]',
}
const SIZES = { md: 'min-h-[44px] px-4 text-sm', sm: 'min-h-[36px] px-3 text-sm', lg: 'min-h-[52px] px-6 text-base' }

/**
 * One button for every action. Pass `to` to render a router link that looks like a button.
 * `loading` disables the button, shows a spinner and sets aria-busy for assistive technology.
 */
export default function Button({ variant = 'primary', size = 'md', loading = false, to, className = '', children, ...props }) {
  const classes = `inline-flex items-center justify-center gap-2 rounded-md font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${SIZES[size]} ${VARIANTS[variant]} ${className}`
  if (to) {
    return (
      <Link to={to} className={classes} {...props}>
        {children}
      </Link>
    )
  }
  return (
    <button type="button" className={classes} disabled={loading || props.disabled} aria-busy={loading || undefined} {...props}>
      {loading && <Loader2 className="h-4 w-4 animate-spin motion-reduce:animate-none" aria-hidden="true" />}
      {children}
    </button>
  )
}
