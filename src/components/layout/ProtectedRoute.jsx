import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { Loader2 } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'

/** Sends signed-out visitors to the login page and returns them to where they were headed afterwards. */
export default function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return (
      <div role="status" className="flex min-h-screen items-center justify-center gap-3 text-muted">
        <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
        Checking your session
      </div>
    )
  }
  if (status === 'anon') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return <Outlet />
}
