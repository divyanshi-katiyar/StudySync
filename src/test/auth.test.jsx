import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { prepare, renderApp } from './helpers'

describe('authentication flow', () => {
  beforeEach(() => prepare())

  it('shows the landing page with links to sign up and log in', () => {
    renderApp('/')
    expect(screen.getByRole('heading', { level: 1, name: /study together without losing the thread/i })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /create a free account/i })[0]).toHaveAttribute('href', '/register')
  })

  it('redirects signed-out visitors from the dashboard to the login page', async () => {
    renderApp('/app/dashboard')
    expect(await screen.findByRole('heading', { name: /log in/i })).toBeInTheDocument()
  })

  it('shows field errors and moves focus to the first invalid field', async () => {
    const user = userEvent.setup()
    renderApp('/login')
    await user.type(screen.getByLabelText(/email/i), 'not-an-email')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))

    expect(await screen.findByText(/enter a valid email address/i)).toBeInTheDocument()
    expect(screen.getByText(/enter your password/i)).toBeInTheDocument()
    const email = screen.getByLabelText(/email/i)
    expect(email).toHaveAttribute('aria-invalid', 'true')
    await waitFor(() => expect(email).toHaveFocus())
  })

  it('rejects wrong credentials with a clear message', async () => {
    const user = userEvent.setup()
    renderApp('/login')
    await user.type(screen.getByLabelText(/email/i), 'demo@studysync.app')
    await user.type(screen.getByLabelText(/^password/i), 'WrongPass1')
    await user.click(screen.getByRole('button', { name: /^log in$/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/email or password is incorrect/i)
  })

  it('logs in with the demo account and lands on the dashboard', async () => {
    const user = userEvent.setup()
    renderApp('/login')
    await user.click(screen.getByRole('button', { name: /fill in the demo account/i }))
    await user.click(screen.getByRole('button', { name: /^log in$/i }))
    expect(await screen.findByRole('heading', { level: 1, name: /alex/i })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /upcoming sessions/i })).toBeInTheDocument()
  })

  it('registers a new account, then shows the empty states', async () => {
    const user = userEvent.setup()
    renderApp('/register')
    await user.type(screen.getByLabelText(/full name/i), 'Divya Test')
    await user.type(screen.getByLabelText(/email/i), 'divya@example.com')
    await user.type(screen.getByLabelText(/^password/i), 'Study1234')
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByRole('heading', { level: 1, name: /divya/i })).toBeInTheDocument()
    expect(await screen.findByText(/you have not joined a group yet/i)).toBeInTheDocument()
  })

  it('refuses an email that is already registered', async () => {
    const user = userEvent.setup()
    renderApp('/register')
    await user.type(screen.getByLabelText(/full name/i), 'Someone Else')
    await user.type(screen.getByLabelText(/email/i), 'demo@studysync.app')
    await user.type(screen.getByLabelText(/^password/i), 'Study1234')
    await user.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByText(/an account with this email already exists/i)).toBeInTheDocument()
  })
})
