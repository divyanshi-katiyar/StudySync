import Button from '../components/ui/Button'
import Logo from '../components/ui/Logo'
import { usePageTitle } from '../hooks/usePageTitle'

export default function NotFound() {
  usePageTitle('Page not found')
  return (
    <main id="main" className="flex min-h-screen flex-col items-center justify-center gap-6 px-4 text-center">
      <Logo />
      <div>
        <h1 className="font-display text-3xl font-bold">We could not find that page</h1>
        <p className="mt-2 max-w-md text-muted">The link may be mistyped, or the page may have moved. Go back to your dashboard or the home page.</p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Button to="/app/dashboard">Go to dashboard</Button>
        <Button to="/" variant="secondary">
          Back to home
        </Button>
      </div>
    </main>
  )
}
