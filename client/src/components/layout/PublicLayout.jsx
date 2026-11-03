import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../../context/AuthContext'
import Button from '../ui/Button'
import Logo from '../ui/Logo'

export default function PublicLayout() {
  const { status } = useAuth()
  const { pathname } = useLocation()
  const onLanding = pathname === '/'

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#main" className="sr-only z-[70] rounded-md bg-ink px-4 py-2 font-semibold text-white focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to main content
      </a>
      <header className="border-b border-line bg-white/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 md:px-8">
          <Logo />
          <nav aria-label="Account" className="flex items-center gap-2">
            {status === 'authed' ? (
              <Button to="/app/dashboard" size="sm">
                Go to dashboard
              </Button>
            ) : (
              <>
                {onLanding && (
                  <a href="#how-it-works" className="hidden rounded-md px-3 py-2 text-sm font-semibold text-ink hover:bg-ink/5 sm:inline-block">
                    How it works
                  </a>
                )}
                <Button to="/login" variant="ghost" size="sm">
                  Log in
                </Button>
                <Button to="/register" size="sm">
                  Sign up
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      <main id="main" tabIndex={-1} className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-sm text-muted md:flex-row md:items-center md:justify-between md:px-8">
          <p>StudySync is a student project built for the Full Stack Developer internship, Week 2.</p>
          <p>
            <Link to="/login" className="font-semibold text-ink underline underline-offset-2">
              Log in
            </Link>{' '}
            to try the demo account.
          </p>
        </div>
      </footer>
    </div>
  )
}
