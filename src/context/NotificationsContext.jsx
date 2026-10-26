import { createContext, useCallback, useContext, useEffect, useMemo } from 'react'
import { notifications } from '../api'
import { useAsync } from '../hooks/useAsync'
import { useToast } from './ToastContext'

const NotificationsContext = createContext(null)

/** How long after sign-in the simulated "real-time" event arrives (disabled in tests). */
const LIVE_DEMO_DELAY_MS = 25_000

/**
 * Notification feed for the signed-in user. In Week 4 the live event will come from a Socket.io
 * connection; until then `simulateIncoming` plays that role once, shortly after sign-in.
 */
export function NotificationsProvider({ children }) {
  const toast = useToast()
  const { data, reload, setData, loading } = useAsync(() => notifications.list(), [])
  const items = data ?? []
  const unread = items.filter((n) => !n.isRead).length

  useEffect(() => {
    if (import.meta.env.MODE === 'test') return undefined
    const id = setTimeout(async () => {
      try {
        const n = await notifications.simulateIncoming()
        if (n) {
          toast.info(n.message)
          reload()
        }
      } catch {
        /* the live demo is best-effort */
      }
    }, LIVE_DEMO_DELAY_MS)
    return () => clearTimeout(id)
  }, [reload, toast])

  const markRead = useCallback(
    async (id) => {
      setData((list) => (list ?? []).map((n) => (n.id === id ? { ...n, isRead: true } : n)))
      await notifications.markRead(id)
    },
    [setData],
  )
  const markAllRead = useCallback(async () => {
    setData((list) => (list ?? []).map((n) => ({ ...n, isRead: true })))
    await notifications.markAllRead()
  }, [setData])

  const value = useMemo(() => ({ items, unread, loading, reload, markRead, markAllRead }), [items, unread, loading, reload, markRead, markAllRead])
  return <NotificationsContext.Provider value={value}>{children}</NotificationsContext.Provider>
}

export function useNotifications() {
  const ctx = useContext(NotificationsContext)
  if (!ctx) throw new Error('useNotifications must be used inside <NotificationsProvider>')
  return ctx
}
