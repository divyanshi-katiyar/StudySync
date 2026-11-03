import { initials } from '../../utils/format'

const PALETTE = ['#0F7B70', '#6446C9', '#B4540B', '#1D6FA5', '#2F7D32', '#B8325A', '#7A5C00', '#3B5BA9']
const colorFor = (name) => PALETTE[[...name].reduce((sum, ch) => sum + ch.charCodeAt(0), 0) % PALETTE.length]

/** Decorative initials badge. The person's name is always written next to it, so it is hidden from screen readers. */
export default function Avatar({ name = '?', size = 'md' }) {
  const dim = size === 'sm' ? 'h-7 w-7 text-xs' : size === 'lg' ? 'h-14 w-14 text-lg' : 'h-9 w-9 text-sm'
  return (
    <span aria-hidden="true" className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white ${dim}`} style={{ backgroundColor: colorFor(name) }}>
      {initials(name)}
    </span>
  )
}
