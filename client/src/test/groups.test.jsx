import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { prepare, renderApp } from './helpers'

describe('discovering and joining groups', () => {
  beforeEach(() => prepare({ signedIn: true }))

  it('lists public groups and hides private ones', async () => {
    renderApp('/app/discover')
    expect(await screen.findByRole('heading', { name: 'Algorithms Study Circle' })).toBeInTheDocument()
    expect(screen.queryByText('Compiler Design Crew')).not.toBeInTheDocument()
  })

  it('filters the list as the user types a search and updates the result count', async () => {
    const user = userEvent.setup()
    renderApp('/app/discover')
    await screen.findByRole('heading', { name: 'Algorithms Study Circle' })
    await user.type(screen.getByLabelText(/search groups/i), 'database')
    await waitFor(() => expect(screen.queryByRole('heading', { name: 'Algorithms Study Circle' })).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Database Gang' })).toBeInTheDocument()
    expect(screen.getByText(/showing 1 of 1 group$/i)).toBeInTheDocument()
  })

  it('shows a helpful empty state when nothing matches', async () => {
    const user = userEvent.setup()
    renderApp('/app/discover')
    await screen.findByRole('heading', { name: 'Algorithms Study Circle' })
    await user.type(screen.getByLabelText(/search groups/i), 'zzzz')
    expect(await screen.findByText(/no groups match your search/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /clear search and filters/i }))
    expect(await screen.findByRole('heading', { name: 'Algorithms Study Circle' })).toBeInTheDocument()
  })

  it('joins a group from its card and the card switches to "Open group"', async () => {
    const user = userEvent.setup()
    renderApp('/app/discover')
    const card = (await screen.findByRole('heading', { name: 'OS Notes Hub' })).closest('article')
    await user.click(within(card).getByRole('button', { name: /join group/i }))
    expect(await within(card).findByRole('link', { name: /open group/i })).toBeInTheDocument()
    expect(await screen.findByText(/you joined "os notes hub"/i)).toBeInTheDocument()
  })

  it('joins the private group with an invite code', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups')
    await screen.findByRole('heading', { name: 'Algorithms Study Circle' })
    await user.click(screen.getByRole('button', { name: /join with code/i }))
    const dialog = await screen.findByRole('dialog', { name: /join with an invite code/i })
    await user.type(within(dialog).getByLabelText(/invite code/i), 'wrong-code')
    await user.click(within(dialog).getByRole('button', { name: /join group/i }))
    expect(await within(dialog).findByText(/no group matches that code/i)).toBeInTheDocument()

    await user.clear(within(dialog).getByLabelText(/invite code/i))
    await user.type(within(dialog).getByLabelText(/invite code/i), 'com-2026')
    await user.click(within(dialog).getByRole('button', { name: /join group/i }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Compiler Design Crew' })).toBeInTheDocument()
  })
})

describe('group workspace', () => {
  beforeEach(() => prepare({ signedIn: true }))

  it('shows resources and supports keyboard navigation between tabs', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups/g1')
    expect(await screen.findByText('Graph algorithms cheat-sheet')).toBeInTheDocument()

    const resourcesTab = screen.getByRole('tab', { name: 'Resources' })
    resourcesTab.focus()
    await user.keyboard('{ArrowRight}')
    const discussion = screen.getByRole('tab', { name: 'Discussion' })
    expect(discussion).toHaveFocus()
    expect(discussion).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByRole('link', { name: /bfs and dfs in interviews/i })).toBeInTheDocument()
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'tab-discussion')
  })

  it('adds a resource through the dialog and validates the link first', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups/g1')
    await screen.findByText('Graph algorithms cheat-sheet')
    await user.click(screen.getByRole('button', { name: /add resource/i }))

    const dialog = await screen.findByRole('dialog', { name: /add a resource/i })
    await user.type(within(dialog).getByLabelText(/title/i), 'Segment tree notes')
    await user.type(within(dialog).getByLabelText(/^link/i), 'not a link')
    await user.click(within(dialog).getByRole('button', { name: /add resource/i }))
    expect(await within(dialog).findByText(/enter a full link/i)).toBeInTheDocument()

    await user.clear(within(dialog).getByLabelText(/^link/i))
    await user.type(within(dialog).getByLabelText(/^link/i), 'https://example.com/segment-tree')
    await user.type(within(dialog).getByLabelText(/tags/i), 'trees, exam')
    await user.click(within(dialog).getByRole('button', { name: /add resource/i }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(await screen.findByText('Segment tree notes')).toBeInTheDocument()
    expect(screen.getByText('#trees')).toBeInTheDocument()
  })

  it('closes dialogs with Escape and returns focus to the button that opened them', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups/g1')
    await screen.findByText('Graph algorithms cheat-sheet')
    const open = screen.getByRole('button', { name: /add resource/i })
    await user.click(open)
    await screen.findByRole('dialog')
    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(open).toHaveFocus()
  })

  it('updates the RSVP state immediately when a session button is pressed', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups/g1?tab=sessions')
    const session = (await screen.findByRole('heading', { name: /graph problems: practice round/i })).closest('li')
    const maybe = within(session).getByRole('button', { name: 'Maybe' })
    expect(maybe).toHaveAttribute('aria-pressed', 'false')
    await user.click(maybe)
    expect(maybe).toHaveAttribute('aria-pressed', 'true')
    expect(await screen.findByText(/marked as maybe/i)).toBeInTheDocument()
  })

  it('opens a discussion thread and posts a reply', async () => {
    const user = userEvent.setup()
    renderApp('/app/groups/g1/posts/p1')
    expect(await screen.findByRole('heading', { level: 1, name: /bfs and dfs in interviews/i })).toBeInTheDocument()
    await user.type(screen.getByLabelText(/add a reply/i), 'I draw the graph first, then pick.')
    await user.click(screen.getByRole('button', { name: /post reply/i }))
    expect(await screen.findByText('I draw the graph first, then pick.')).toBeInTheDocument()
  })

  it('blocks non-members from a private group and explains how to get in', async () => {
    renderApp('/app/groups/g7')
    expect(await screen.findByRole('heading', { name: /you need an invite/i })).toBeInTheDocument()
    expect(screen.getByText(/this group is private/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /enter an invite code/i })).toBeInTheDocument()
  })

  it('only offers the Schedule button to moderators and owners', async () => {
    renderApp('/app/groups/g1?tab=sessions') // Alex is a plain member here
    await screen.findByRole('heading', { name: /graph problems: practice round/i })
    expect(screen.queryByRole('button', { name: /schedule session/i })).not.toBeInTheDocument()
  })
})
