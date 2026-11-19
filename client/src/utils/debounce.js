/**
 * Trailing-edge debounce: a burst of calls becomes one call, `ms` after the last one.
 * Used for live-update reloads, where one user action can produce several events at once and the page only needs to reload once.
 * The returned function has .cancel() so a component can drop a pending call when it unmounts.
 */
export function debounce(fn, ms) {
  let timer = null
  const debounced = (...args) => {
    clearTimeout(timer)
    timer = setTimeout(() => {
      timer = null
      fn(...args)
    }, ms)
  }
  debounced.cancel = () => {
    clearTimeout(timer)
    timer = null
  }
  return debounced
}
