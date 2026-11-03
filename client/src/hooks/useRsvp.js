import { useCallback } from 'react'
import { sessions } from '../api'
import { useToast } from '../context/ToastContext'

const MESSAGES = {
  going: (t) => `You are going to "${t}".`,
  maybe: (t) => `Marked as maybe for "${t}".`,
  no: (t) => `Marked as not going to "${t}".`,
}

/**
 * Optimistic RSVP: the button updates immediately, then the server confirms.
 * `setList` receives an updater over the array of sessions that the caller displays.
 */
export function useRsvp(setList) {
  const toast = useToast()
  return useCallback(
    async (session, status) => {
      if (session.myRsvp === status) return
      const before = session
      setList((list) => list.map((s) => (s.id === session.id ? { ...s, myRsvp: status } : s)))
      try {
        const updated = await sessions.rsvp(session.id, status)
        setList((list) => list.map((s) => (s.id === session.id ? { ...s, ...updated } : s)))
        toast.success(MESSAGES[status](session.title))
      } catch (err) {
        setList((list) => list.map((s) => (s.id === session.id ? before : s)))
        toast.error(err.message)
      }
    },
    [setList, toast],
  )
}
