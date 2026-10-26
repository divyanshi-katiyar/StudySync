import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import App from '../App'
import { AuthProvider } from '../context/AuthContext'
import { ToastProvider } from '../context/ToastContext'
import { setLatency } from '../api'
import { resetDb, SESSION_KEY } from '../api/mockDb'

/** Fresh database, no artificial delay, optional signed-in demo user. */
export function prepare({ signedIn = false } = {}) {
  setLatency(0)
  localStorage.clear()
  resetDb()
  if (signedIn) localStorage.setItem(SESSION_KEY, JSON.stringify({ userId: 'u1' }))
}

/** Renders the whole app at a given URL, wrapped in the same providers as main.jsx. */
export function renderApp(route = '/') {
  return render(
    <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </MemoryRouter>,
  )
}
