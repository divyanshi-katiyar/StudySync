import { useState } from 'react'
import { Library, Plus } from 'lucide-react'
import { groups } from '../api'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import Button from '../components/ui/Button'
import PageHeader from '../components/ui/PageHeader'
import { EmptyState, ErrorState } from '../components/ui/States'
import { CardSkeleton } from '../components/ui/Skeleton'
import GroupCard from '../components/groups/GroupCard'
import CreateGroupModal from '../components/groups/CreateGroupModal'
import JoinByCodeModal from '../components/groups/JoinByCodeModal'

export default function MyGroups() {
  usePageTitle('My groups')
  const { data, error, loading, reload } = useAsync(() => groups.mine(), [])
  const [creating, setCreating] = useState(false)
  const [joining, setJoining] = useState(false)

  return (
    <>
      <PageHeader
        title="My groups"
        actions={
          <>
            <Button variant="secondary" onClick={() => setJoining(true)}>
              Join with code
            </Button>
            <Button onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden="true" />
              Create group
            </Button>
          </>
        }
      >
        Every group you belong to, with the next session at a glance.
      </PageHeader>

      {error ? (
        <ErrorState error={error} onRetry={reload} />
      ) : loading && !data ? (
        <CardSkeleton />
      ) : data.length === 0 ? (
        <EmptyState icon={Library} title="You are not in any groups yet" action={<Button to="/app/discover">Discover groups</Button>}>
          Find a public group by subject, or create one for your own study circle.
        </EmptyState>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((g) => (
            <li key={g.id} className="flex">
              <div className="flex-1">
                <GroupCard group={g} />
              </div>
            </li>
          ))}
        </ul>
      )}

      <CreateGroupModal open={creating} onClose={() => { setCreating(false); reload() }} />
      <JoinByCodeModal open={joining} onClose={() => setJoining(false)} />
    </>
  )
}
