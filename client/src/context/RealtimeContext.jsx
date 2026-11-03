import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { realtime } from '../api'
import { useAuth } from './AuthContext'

/**
 * Keeps one live connection to the server while someone is signed in and shares it with the rest of the app.
 * Components do not talk to the stream directly: they call useLiveUpdates() to react to the events they care about.
 * Without a provider (mock mode, unit tests) the hooks quietly do nothing.
 */
const RealtimeContext = createContext({ subscribe: () => () => {}, status: 'idle' })

export function RealtimeProvider({ children }) {
  const { status: authStatus } = useAuth()
  const [status, setStatus] = useState(realtime.status)

  useEffect(() => realtime.onStatus(setStatus), [])
  useEffect(() => {
    if (authStatus !== 'authed') return undefined
    realtime.start()
    return () => realtime.stop()
  }, [authStatus])

  const value = useMemo(() => ({ subscribe: realtime.subscribe, status }), [status])
  return <RealtimeContext.Provider value={value}>{children}</RealtimeContext.Provider>
}

export function useRealtime() {
  return useContext(RealtimeContext)
}

/**
 * Run `onMatch(event)` whenever a live event satisfies `match(event)`.
 * Example: reload the resource list when another member changes this group's resources.
 */
export function useLiveUpdates(match, onMatch) {
  const { subscribe } = useRealtime()
  const latest = useRef({ match, onMatch })
  latest.current = { match, onMatch }
  useEffect(
    () =>
      subscribe((event) => {
        if (event.type === 'resync' || latest.current.match(event)) latest.current.onMatch(event)
      }),
    [subscribe],
  )
}

/** Shorthand for the common case: reload when `kind` changes in group `groupId` (and optionally one post). */
export function useLiveGroupReload(groupId, kinds, reload, postId) {
  useLiveUpdates(
    (e) => e.type === 'group.updated' && e.groupId === groupId && kinds.includes(e.kind) && (!postId || !e.postId || e.postId === postId),
    reload,
  )
}
