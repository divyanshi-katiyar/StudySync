import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { auth } from '../api'
import { SESSION_KEY } from '../api/mockDb'

const AuthContext = createContext(null)

/**
 * Holds the signed-in user. `status` is 'loading' while the saved session is verified,
 * then 'authed' or 'anon'. Route guards and the navbar read from here.
 */
export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(() => (localStorage.getItem(SESSION_KEY) ? 'loading' : 'anon'))

  useEffect(() => {
    if (status !== 'loading') return
    auth
      .me()
      .then((u) => {
        setUser(u)
        setStatus('authed')
      })
      .catch(() => setStatus('anon'))
  }, [status])

  const login = useCallback(async (values) => {
    const u = await auth.login(values)
    setUser(u)
    setStatus('authed')
    return u
  }, [])

  const register = useCallback(async (values) => {
    const u = await auth.register(values)
    setUser(u)
    setStatus('authed')
    return u
  }, [])

  const logout = useCallback(async () => {
    await auth.logout()
    setUser(null)
    setStatus('anon')
  }, [])

  const updateProfile = useCallback(async (values) => {
    const u = await auth.updateProfile(values)
    setUser(u)
    return u
  }, [])

  const value = useMemo(() => ({ user, status, login, register, logout, updateProfile }), [user, status, login, register, logout, updateProfile])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
