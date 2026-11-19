import { describe, expect, it, vi } from 'vitest'
import { act, renderHook, waitFor } from '@testing-library/react'
import { useAsync } from '../hooks/useAsync'
import { useDebounce } from '../hooks/useDebounce'
import { useForm } from '../hooks/useForm'
import { usePageTitle } from '../hooks/usePageTitle'
import { RealtimeContext, useLiveGroupReload, useLiveUpdates } from '../context/RealtimeContext'
import { email, required } from '../utils/validation'

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))
/** A promise that the test resolves or rejects by hand, to control exactly when a "request" finishes. */
const deferred = () => {
  let resolve, reject
  const promise = new Promise((res, rej) => ((resolve = res), (reject = rej)))
  return { promise, resolve, reject }
}

describe('useAsync', () => {
  it('starts loading, then exposes the data', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve(['a', 'b'])))
    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual(['a', 'b'])
    expect(result.current.error).toBeNull()
  })

  it('exposes the error and no data when the request fails', async () => {
    const boom = new Error('server down')
    const { result } = renderHook(() => useAsync(() => Promise.reject(boom)))
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.error).toBe(boom)
    expect(result.current.data).toBeNull()
  })

  it('keeps showing the old data while a reload is in flight', async () => {
    const second = deferred()
    const fn = vi.fn().mockReturnValueOnce(Promise.resolve('first')).mockReturnValueOnce(second.promise)
    const { result } = renderHook(() => useAsync(fn))
    await waitFor(() => expect(result.current.data).toBe('first'))
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.loading).toBe(true))
    expect(result.current.data).toBe('first') // no flash back to a skeleton
    await act(async () => second.resolve('second'))
    await waitFor(() => expect(result.current.data).toBe('second'))
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('ignores a slow answer that arrives after a newer request was made', async () => {
    const slow = deferred()
    const fn = vi.fn((id) => (id === 1 ? slow.promise : Promise.resolve('fast answer for 2')))
    const { result, rerender } = renderHook(({ id }) => useAsync(() => fn(id), [id]), { initialProps: { id: 1 } })
    rerender({ id: 2 })
    await waitFor(() => expect(result.current.data).toBe('fast answer for 2'))
    await act(async () => slow.resolve('stale answer for 1'))
    await wait(20)
    expect(result.current.data).toBe('fast answer for 2')
  })

  it('refetches when a dependency changes', async () => {
    const fn = vi.fn((q) => Promise.resolve(`results for ${q}`))
    const { result, rerender } = renderHook(({ q }) => useAsync(() => fn(q), [q]), { initialProps: { q: 'graphs' } })
    await waitFor(() => expect(result.current.data).toBe('results for graphs'))
    rerender({ q: 'dp' })
    await waitFor(() => expect(result.current.data).toBe('results for dp'))
    expect(fn).toHaveBeenCalledTimes(2)
  })

  it('setData supports optimistic updates with a value or an updater function', async () => {
    const { result } = renderHook(() => useAsync(() => Promise.resolve([1, 2])))
    await waitFor(() => expect(result.current.data).toEqual([1, 2]))
    act(() => result.current.setData((list) => [...list, 3]))
    expect(result.current.data).toEqual([1, 2, 3])
    act(() => result.current.setData(['replaced']))
    expect(result.current.data).toEqual(['replaced'])
  })
})

describe('useDebounce', () => {
  it('returns the first value at once and follows changes only after the delay', async () => {
    const { result, rerender } = renderHook(({ v }) => useDebounce(v, 40), { initialProps: { v: 'a' } })
    expect(result.current).toBe('a')
    rerender({ v: 'ab' })
    expect(result.current).toBe('a')
    await waitFor(() => expect(result.current).toBe('ab'))
  })

  it('restarts the wait on every change, so typing quickly produces one update', async () => {
    const seen = []
    const { result, rerender } = renderHook(({ v }) => {
      const value = useDebounce(v, 60)
      seen.push(value)
      return value
    }, { initialProps: { v: 'g' } })
    for (const v of ['gr', 'gra', 'grap', 'graph']) {
      rerender({ v })
      await wait(15)
    }
    expect(result.current).toBe('g')
    await waitFor(() => expect(result.current).toBe('graph'))
    expect(seen.filter((x) => x !== 'g' && x !== 'graph')).toEqual([]) // never showed an in-between value
  })
})

describe('useForm', () => {
  const rules = { email: [required('your email'), email], name: [required('your name')] }

  it('binds values and updates them from events or plain values', () => {
    const { result } = renderHook(() => useForm({ email: '', name: '' }, rules))
    expect(result.current.bind('email')).toMatchObject({ name: 'email', value: '', error: undefined })
    act(() => result.current.bind('email').onChange({ target: { value: 'a@b.co' } }))
    expect(result.current.values.email).toBe('a@b.co')
    act(() => result.current.bind('name').onChange('Alex'))
    expect(result.current.values.name).toBe('Alex')
  })

  it('check() stores and returns the errors for invalid fields only', () => {
    const { result } = renderHook(() => useForm({ email: 'nope', name: 'Alex' }, rules))
    let found
    act(() => {
      found = result.current.check()
    })
    expect(Object.keys(found)).toEqual(['email'])
    expect(result.current.errors.email).toMatch(/valid email/)
    expect(result.current.bind('email').error).toMatch(/valid email/)
  })

  it('editing a field clears its own error but leaves the others', () => {
    const { result } = renderHook(() => useForm({ email: '', name: '' }, rules))
    act(() => {
      result.current.check()
    })
    expect(Object.keys(result.current.errors).sort()).toEqual(['email', 'name'])
    act(() => result.current.setField('email', 'a@b.co'))
    expect(result.current.errors.email).toBe('')
    expect(result.current.errors.name).toMatch(/Enter your name/)
  })

  it('reset() restores the starting values and removes every error', () => {
    const { result } = renderHook(() => useForm({ email: '', name: '' }, rules))
    act(() => {
      result.current.setField('name', 'Alex')
      result.current.check()
    })
    act(() => result.current.reset())
    expect(result.current.values).toEqual({ email: '', name: '' })
    expect(result.current.errors).toEqual({})
  })

  it('setErrors lets the page show errors that came from the server', () => {
    const { result } = renderHook(() => useForm({ email: 'a@b.co' }, rules))
    act(() => result.current.setErrors({ email: 'An account with this email already exists.' }))
    expect(result.current.bind('email').error).toBe('An account with this email already exists.')
  })
})

describe('usePageTitle', () => {
  it('sets the document title with the product name, and the bare name when empty', () => {
    const { rerender } = renderHook(({ t }) => usePageTitle(t), { initialProps: { t: 'Discover' } })
    expect(document.title).toBe('Discover - StudySync')
    rerender({ t: '' })
    expect(document.title).toBe('StudySync')
  })
})

/** A stand-in for the live connection: tests push events through it exactly as the server would. */
function fakeLive() {
  const listeners = new Set()
  return {
    value: { subscribe: (fn) => (listeners.add(fn), () => listeners.delete(fn)), status: 'live' },
    emit: (event) => act(() => listeners.forEach((fn) => fn(event))),
    count: () => listeners.size,
  }
}
const withLive = (live) => ({ children }) => <RealtimeContext.Provider value={live.value}>{children}</RealtimeContext.Provider>

describe('useLiveUpdates', () => {
  it('calls the handler only for events that match', () => {
    const live = fakeLive()
    const onMatch = vi.fn()
    renderHook(() => useLiveUpdates((e) => e.type === 'notification', onMatch), { wrapper: withLive(live) })
    live.emit({ type: 'group.updated', groupId: 'g1' })
    expect(onMatch).toHaveBeenCalledTimes(0)
    live.emit({ type: 'notification', notification: { id: 'n1' } })
    expect(onMatch).toHaveBeenCalledTimes(1)
    expect(onMatch).toHaveBeenCalledWith({ type: 'notification', notification: { id: 'n1' } })
  })

  it('always passes a resync event, even when the filter would reject it', () => {
    const live = fakeLive()
    const onMatch = vi.fn()
    renderHook(() => useLiveUpdates(() => false, onMatch), { wrapper: withLive(live) })
    live.emit({ type: 'resync' })
    expect(onMatch).toHaveBeenCalledTimes(1)
  })

  it('stops listening when the component unmounts', () => {
    const live = fakeLive()
    const { unmount } = renderHook(() => useLiveUpdates(() => true, () => {}), { wrapper: withLive(live) })
    expect(live.count()).toBe(1)
    unmount()
    expect(live.count()).toBe(0)
  })

  it('uses the latest handler without resubscribing', () => {
    const live = fakeLive()
    const first = vi.fn()
    const second = vi.fn()
    const { rerender } = renderHook(({ fn }) => useLiveUpdates(() => true, fn), { wrapper: withLive(live), initialProps: { fn: first } })
    rerender({ fn: second })
    live.emit({ type: 'group.updated' })
    expect(first).toHaveBeenCalledTimes(0)
    expect(second).toHaveBeenCalledTimes(1)
    expect(live.count()).toBe(1)
  })

  it('collapses a burst of events into one call when a debounce is set', async () => {
    const live = fakeLive()
    const onMatch = vi.fn()
    renderHook(() => useLiveUpdates(() => true, onMatch, { debounceMs: 40 }), { wrapper: withLive(live) })
    for (let i = 0; i < 5; i++) live.emit({ type: 'group.updated', i })
    expect(onMatch).toHaveBeenCalledTimes(0)
    await waitFor(() => expect(onMatch).toHaveBeenCalledTimes(1))
    expect(onMatch).toHaveBeenCalledWith({ type: 'group.updated', i: 4 }) // the last event of the burst
    await wait(80)
    expect(onMatch).toHaveBeenCalledTimes(1)
  })

  it('drops a pending debounced call when the component unmounts', async () => {
    const live = fakeLive()
    const onMatch = vi.fn()
    const { unmount } = renderHook(() => useLiveUpdates(() => true, onMatch, { debounceMs: 30 }), { wrapper: withLive(live) })
    live.emit({ type: 'group.updated' })
    unmount()
    await wait(70)
    expect(onMatch).toHaveBeenCalledTimes(0)
  })

  it('does nothing and does not crash without a provider (mock mode)', () => {
    const onMatch = vi.fn()
    const { result } = renderHook(() => useLiveUpdates(() => true, onMatch))
    expect(result.error).toBeUndefined()
    expect(onMatch).toHaveBeenCalledTimes(0)
  })
})

describe('useLiveGroupReload', () => {
  const setup = (args) => {
    const live = fakeLive()
    const reload = vi.fn()
    renderHook(() => useLiveGroupReload(args.groupId, args.kinds, reload, args.postId), { wrapper: withLive(live) })
    return { live, reload }
  }

  it('reloads for the right group and kind, once per burst', async () => {
    const { live, reload } = setup({ groupId: 'g1', kinds: ['resources'] })
    live.emit({ type: 'group.updated', groupId: 'g2', kind: 'resources' })
    live.emit({ type: 'group.updated', groupId: 'g1', kind: 'posts' })
    live.emit({ type: 'notification', notification: {} })
    await wait(250)
    expect(reload).toHaveBeenCalledTimes(0)
    live.emit({ type: 'group.updated', groupId: 'g1', kind: 'resources' })
    live.emit({ type: 'group.updated', groupId: 'g1', kind: 'resources' })
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1))
    await wait(250)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('for a single post, ignores changes to other posts but reacts to group-wide ones', async () => {
    const { live, reload } = setup({ groupId: 'g1', kinds: ['posts'], postId: 'p1' })
    live.emit({ type: 'group.updated', groupId: 'g1', kind: 'posts', postId: 'p2' })
    await wait(250)
    expect(reload).toHaveBeenCalledTimes(0)
    live.emit({ type: 'group.updated', groupId: 'g1', kind: 'posts', postId: 'p1' })
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1))
  })

  it('a resync event reloads regardless of group', async () => {
    const { live, reload } = setup({ groupId: 'g1', kinds: ['resources'] })
    live.emit({ type: 'resync' })
    await waitFor(() => expect(reload).toHaveBeenCalledTimes(1))
  })
})
