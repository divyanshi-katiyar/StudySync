import { useEffect, useRef, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { Compass, LayoutDashboard, CalendarDays, Library, LogOut, Search, UserRound } from 'lucide-react'
import { useAuth } from '../../context/AuthContext'
import { NotificationsProvider } from '../../context/NotificationsContext'
import Avatar from '../ui/Avatar'
import Logo from '../ui/Logo'
import NotificationBell from './NotificationBell'

const NAV = [
  { to: '/app/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/app/groups', label: 'My groups', icon: Library },
  { to: '/app/discover', label: 'Discover', icon: Compass },
  { to: '/app/sessions', label: 'Sessions', icon: CalendarDays },
  { to: '/app/profile', label: 'Profile', icon: UserRound },
]

const linkClasses = ({ isActive }) =>
  `relative flex min-h-[44px] items-center gap-3 rounded-md px-3 text-sm font-semibold ${
    isActive ? 'bg-hilite-soft text-ink before:absolute before:left-0 before:top-2 before:bottom-2 before:w-1 before:rounded-full before:bg-marker' : 'text-muted hover:bg-ink/5 hover:text-ink'
  }`

/**
 * Shell for every signed-in page: skip link, top bar (search, notifications, account),
 * side navigation on wide screens, bottom navigation on phones.
 * After each route change focus moves to <main> so keyboard and screen-reader users start at the new content.
 */
export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const mainRef = useRef(null)
  const firstRender = useRef(true)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false
      return
    }
    window.scrollTo(0, 0)
    mainRef.current?.focus({ preventScroll: true })
  }, [pathname])

  const onSearch = (e) => {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/app/discover?search=${encodeURIComponent(q)}` : '/app/discover')
  }

  const onLogout = async () => {
    await logout()
    navigate('/', { replace: true })
  }

  return (
    <NotificationsProvider>
      <div className="min-h-screen">
        <a href="#main" className="sr-only z-[70] rounded-md bg-ink px-4 py-2 font-semibold text-white focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
          Skip to main content
        </a>

        <header className="sticky top-0 z-30 border-b border-line bg-white">
          <div className="flex h-16 items-center gap-3 px-4 md:px-6">
            <Logo to="/app/dashboard" />
            <form role="search" onSubmit={onSearch} className="ml-auto hidden max-w-md flex-1 md:ml-8 md:block">
              <label htmlFor="global-search" className="sr-only">
                Search study groups
              </label>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" aria-hidden="true" />
                <input
                  id="global-search"
                  type="search"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search study groups"
                  className="w-full rounded-md border border-ink/25 bg-paper py-2 pl-9 pr-3 text-sm placeholder:text-muted hover:border-ink/50"
                />
              </div>
            </form>
            <div className="ml-auto flex items-center gap-1 md:ml-0">
              <NotificationBell />
              <NavLink to="/app/profile" className="flex min-h-[44px] items-center gap-2 rounded-md px-2 hover:bg-ink/5" aria-label={`${user?.name}, profile`}>
                <Avatar name={user?.name} />
                <span className="hidden text-sm font-semibold lg:inline">{user?.name}</span>
              </NavLink>
              <button type="button" onClick={onLogout} className="flex min-h-[44px] items-center gap-2 rounded-md px-3 text-sm font-semibold text-muted hover:bg-ink/5 hover:text-ink">
                <LogOut className="h-4 w-4" aria-hidden="true" />
                <span className="hidden sm:inline">Log out</span>
                <span className="sr-only sm:hidden">Log out</span>
              </button>
            </div>
          </div>
        </header>

        <div className="md:grid md:grid-cols-[14rem_1fr]">
          <nav aria-label="Main" className="sticky top-16 hidden h-[calc(100vh-4rem)] border-r border-line bg-white p-3 md:block">
            <ul className="space-y-1">
              {NAV.map(({ to, label, icon: Icon }) => (
                <li key={to}>
                  <NavLink to={to} className={linkClasses}>
                    <Icon className="h-5 w-5" aria-hidden="true" />
                    {label}
                  </NavLink>
                </li>
              ))}
            </ul>
          </nav>

          <main id="main" ref={mainRef} tabIndex={-1} className="min-w-0 px-4 pb-28 pt-6 md:px-8 md:pb-12">
            <div className="mx-auto max-w-5xl">
              <Outlet />
            </div>
          </main>
        </div>

        <nav aria-label="Main (mobile)" className="fixed inset-x-0 bottom-0 z-30 border-t border-line bg-white pb-[env(safe-area-inset-bottom)] md:hidden">
          <ul className="grid grid-cols-5">
            {NAV.map(({ to, label, icon: Icon }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  className={({ isActive }) => `flex min-h-[56px] flex-col items-center justify-center gap-0.5 text-xs font-semibold ${isActive ? 'text-ink' : 'text-muted'}`}
                >
                  {({ isActive }) => (
                    <>
                      <span className={`rounded-full px-4 py-1 ${isActive ? 'bg-hilite' : ''}`}>
                        <Icon className="h-5 w-5" aria-hidden="true" />
                      </span>
                      {label}
                    </>
                  )}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </NotificationsProvider>
  )
}
