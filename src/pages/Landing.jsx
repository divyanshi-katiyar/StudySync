import { CalendarDays, FolderOpen, MessagesSquare } from 'lucide-react'
import Button from '../components/ui/Button'
import { LogoMark } from '../components/ui/Logo'
import { usePageTitle } from '../hooks/usePageTitle'

const FEATURES = [
  { icon: FolderOpen, title: 'A shelf for everything you share', text: 'Links, file links and short notes live in one searchable list with tags, instead of scrolling up through chat.' },
  { icon: MessagesSquare, title: 'Questions that stay answered', text: 'Each discussion is its own thread, so the explanation that cleared things up is still there before the exam.' },
  { icon: CalendarDays, title: 'Sessions everyone can see', text: 'Schedule a time, add the meeting link, and watch who is going, who might, and who cannot make it.' },
]

const STEPS = [
  { title: 'Create a group or join one', text: 'Search public groups by subject, or enter an invite code from a friend.' },
  { title: 'Put your material in the shelf', text: 'Add the notes, playlists and past papers your group already uses.' },
  { title: 'Meet and keep the thread', text: 'Schedule sessions, reply to questions, and see updates in your notifications.' },
]

/** The page-level preview in the hero: a session stub and a shelf entry with the highlighter mark. */
function HeroPreview() {
  return (
    <div role="img" aria-label="Preview of a group page: an upcoming session with RSVP buttons, and a shared resource list" className="relative mx-auto w-full max-w-md space-y-4 lg:mx-0">
      <div className="-rotate-1 rounded-md border border-ink/20 bg-white p-4 shadow-pop">
        <p className="text-sm font-semibold text-muted">Algorithms Study Circle</p>
        <div className="mt-2 flex gap-3">
          <div className="flex h-16 w-16 shrink-0 flex-col items-center justify-center rounded border-2 border-dashed border-ink/30 bg-paper leading-none">
            <span className="text-xs font-semibold text-muted">Tue</span>
            <span className="font-display text-2xl font-extrabold">24</span>
            <span className="text-xs font-semibold text-muted">Oct</span>
          </div>
          <div>
            <p className="font-display font-bold">Graph problems: practice round</p>
            <p className="text-sm text-muted">7:00 pm to 8:30 pm, 12 going</p>
            <div className="mt-2 inline-flex overflow-hidden rounded border border-ink/30 text-xs font-semibold">
              <span className="bg-hilite px-3 py-1.5">Going</span>
              <span className="border-l border-ink/30 px-3 py-1.5 text-muted">Maybe</span>
              <span className="border-l border-ink/30 px-3 py-1.5 text-muted">Can’t go</span>
            </div>
          </div>
        </div>
      </div>
      <div className="ml-6 rotate-1 rounded-md border border-ink/20 bg-white p-4 shadow-pop">
        <ul className="space-y-3 text-sm">
          <li>
            <p className="font-display text-base font-bold">
              <span className="mark-hilite">Graph algorithms cheat-sheet</span>
            </p>
            <p className="text-muted">Shared by Sam, 2 days ago</p>
          </li>
          <li className="border-t border-line pt-3">
            <p className="font-display text-base font-bold">DP patterns: video playlist</p>
            <p className="text-muted">Shared by Priya, 4 days ago</p>
          </li>
        </ul>
      </div>
    </div>
  )
}

export default function Landing() {
  usePageTitle('Study together')
  return (
    <>
      <section className="bg-grid border-b border-line">
        <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-14 md:px-8 lg:grid-cols-[1.1fr_1fr] lg:py-20">
          <div>
            <h1 className="font-display text-4xl font-extrabold leading-[1.08] tracking-tight text-ink sm:text-5xl">
              Study together without losing the thread.
            </h1>
            <p className="mt-5 max-w-xl text-lg text-ink/80">
              StudySync keeps your group’s notes, questions and session times in one place, so the thing you need the night before the exam is never buried in chat.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button to="/register" size="lg">
                Create a free account
              </Button>
              <Button to="/login?demo=1" variant="secondary" size="lg">
                Try the demo account
              </Button>
            </div>
          </div>
          <HeroPreview />
        </div>
      </section>

      <section aria-labelledby="features-heading" className="mx-auto max-w-6xl px-4 py-16 md:px-8">
        <h2 id="features-heading" className="max-w-2xl font-display text-3xl font-bold">
          Everything a study group reaches for, in one place
        </h2>
        <div className="mt-8 grid gap-x-10 gap-y-8 md:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <div key={title} className="border-t-2 border-ink pt-4">
              <Icon className="h-6 w-6 text-marker" aria-hidden="true" />
              <h3 className="mt-3 font-display text-lg font-bold">{title}</h3>
              <p className="mt-1 text-muted">{text}</p>
            </div>
          ))}
        </div>
      </section>

      <section id="how-it-works" aria-labelledby="how-heading" className="border-y border-line bg-white">
        <div className="mx-auto max-w-6xl px-4 py-16 md:px-8">
          <h2 id="how-heading" className="font-display text-3xl font-bold">
            How it works
          </h2>
          <ol className="mt-8 grid gap-8 md:grid-cols-3">
            {STEPS.map((s, i) => (
              <li key={s.title} className="flex gap-4">
                <span aria-hidden="true" className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-hilite font-display text-lg font-extrabold">
                  {i + 1}
                </span>
                <div>
                  <h3 className="font-display text-lg font-bold">{s.title}</h3>
                  <p className="mt-1 text-muted">{s.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="on-dark bg-ink">
        <div className="mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 py-14 md:flex-row md:items-center md:justify-between md:px-8">
          <div className="flex items-center gap-4">
            <LogoMark className="hidden h-12 w-12 sm:block" />
            <div>
              <h2 className="font-display text-2xl font-bold text-white">Bring your group in today.</h2>
              <p className="mt-1 text-white/80">Sign-up takes under a minute, and the demo account is already filled with study groups.</p>
            </div>
          </div>
          <Button to="/register" variant="highlight" size="lg">
            Create a free account
          </Button>
        </div>
      </section>
    </>
  )
}
