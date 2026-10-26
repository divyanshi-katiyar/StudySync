import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { ArrowLeft, Copy, Lock, LogOut, Trash2, Users } from 'lucide-react'
import { groups } from '../api'
import { useAsync } from '../hooks/useAsync'
import { usePageTitle } from '../hooks/usePageTitle'
import { useToast } from '../context/ToastContext'
import { pluralize } from '../utils/format'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import Tabs from '../components/ui/Tabs'
import { ErrorState } from '../components/ui/States'
import { Skeleton } from '../components/ui/Skeleton'
import JoinByCodeModal from '../components/groups/JoinByCodeModal'
import ResourcesTab from '../components/groups/ResourcesTab'
import DiscussionTab from '../components/groups/DiscussionTab'
import SessionsTab from '../components/groups/SessionsTab'
import MembersTab from '../components/groups/MembersTab'

const TAB_IDS = ['resources', 'discussion', 'sessions', 'members']

/**
 * Group workspace (the "detail view"). The active tab lives in ?tab= so links from notifications
 * and the browser's Back button land on the right panel.
 */
export default function GroupDetail() {
  const { groupId } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [params, setParams] = useSearchParams()
  const tab = TAB_IDS.includes(params.get('tab')) ? params.get('tab') : 'resources'
  const { data: group, error, loading, reload, setData } = useAsync(() => groups.get(groupId), [groupId])
  usePageTitle(group?.name ?? 'Group')

  const [confirm, setConfirm] = useState(null) // 'leave' | 'delete'
  const [busy, setBusy] = useState(false)
  const [codeOpen, setCodeOpen] = useState(false)
  const [joining, setJoining] = useState(false)

  const setTab = (id) => setParams({ tab: id }, { replace: true })

  const join = async () => {
    setJoining(true)
    try {
      const updated = await groups.join(groupId)
      setData(updated)
      toast.success(`You joined "${updated.name}".`)
    } catch (err) {
      toast.error(err.message)
    } finally {
      setJoining(false)
    }
  }

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(group.inviteCode)
      toast.success(`Invite code ${group.inviteCode} copied.`)
    } catch {
      toast.info(`Your invite code is ${group.inviteCode}.`)
    }
  }

  const runConfirmed = async () => {
    setBusy(true)
    try {
      if (confirm === 'leave') {
        await groups.leave(groupId)
        toast.success(`You left "${group.name}".`)
      } else {
        await groups.remove(groupId)
        toast.success(`"${group.name}" was deleted.`)
      }
      navigate('/app/groups')
    } catch (err) {
      toast.error(err.message)
      setConfirm(null)
    } finally {
      setBusy(false)
    }
  }

  if (error) {
    return (
      <div className="space-y-4">
        <Link to="/app/groups" className="inline-flex items-center gap-1.5 text-sm font-semibold text-marker hover:underline">
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to my groups
        </Link>
        <ErrorState error={error} onRetry={error.status === 403 || error.status === 404 ? undefined : reload} title={error.status === 403 ? 'You need an invite to open this group' : error.status === 404 ? 'Group not found' : 'We could not load this group'} />
        {error.status === 403 && <Button onClick={() => setCodeOpen(true)}>Enter an invite code</Button>}
        <JoinByCodeModal open={codeOpen} onClose={() => setCodeOpen(false)} />
      </div>
    )
  }

  if (loading && !group) {
    return (
      <div aria-busy="true" aria-label="Loading group" className="space-y-4">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-5 w-1/4" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }

  const tabs = [
    { id: 'resources', label: 'Resources' },
    { id: 'discussion', label: 'Discussion' },
    { id: 'sessions', label: 'Sessions' },
    { id: 'members', label: 'Members', count: group.memberCount },
  ]

  return (
    <>
      <Link to="/app/groups" className="mb-4 inline-flex items-center gap-1.5 text-sm font-semibold text-marker hover:underline">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        Back to my groups
      </Link>

      <header className="mb-6 flex overflow-hidden rounded-md border border-line bg-white">
        <div aria-hidden="true" className="w-3 shrink-0" style={{ backgroundColor: group.color }} />
        <div className="min-w-0 flex-1 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="font-display text-3xl font-bold leading-tight">{group.name}</h1>
            {group.visibility === 'private' && (
              <Badge>
                <Lock className="h-3 w-3" aria-hidden="true" />
                Private
              </Badge>
            )}
            {group.isMember && <Badge tone="marker">{group.myRole === 'owner' ? 'You own this group' : group.myRole === 'moderator' ? 'You moderate' : 'You are a member'}</Badge>}
          </div>
          <p className="mt-1 font-semibold" style={{ color: group.color }}>
            {group.subject}
          </p>
          <p className="mt-3 max-w-3xl text-ink/90">{group.description}</p>
          <p className="mt-3 flex items-center gap-1.5 text-sm text-muted">
            <Users className="h-4 w-4" aria-hidden="true" />
            {pluralize(group.memberCount, 'member')}, started by {group.ownerName}
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {!group.isMember && group.visibility === 'public' && (
              <Button onClick={join} loading={joining}>
                Join group
              </Button>
            )}
            {group.isMember && group.inviteCode && (
              <Button variant="secondary" size="sm" onClick={copyCode}>
                <Copy className="h-4 w-4" aria-hidden="true" />
                Copy invite code <code className="ml-1 rounded bg-paper px-1.5 py-0.5 text-xs">{group.inviteCode}</code>
              </Button>
            )}
            {group.isMember && group.myRole !== 'owner' && (
              <Button variant="ghost" size="sm" onClick={() => setConfirm('leave')}>
                <LogOut className="h-4 w-4" aria-hidden="true" />
                Leave group
              </Button>
            )}
            {group.myRole === 'owner' && (
              <Button variant="ghost" size="sm" className="text-danger hover:bg-danger-soft" onClick={() => setConfirm('delete')}>
                <Trash2 className="h-4 w-4" aria-hidden="true" />
                Delete group
              </Button>
            )}
          </div>
        </div>
      </header>

      {group.isMember ? (
        <>
          <Tabs tabs={tabs} value={tab} onChange={setTab} label="Group sections" />
          <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} tabIndex={0} className="pt-5">
            {tab === 'resources' && <ResourcesTab group={group} />}
            {tab === 'discussion' && <DiscussionTab group={group} />}
            {tab === 'sessions' && <SessionsTab group={group} />}
            {tab === 'members' && <MembersTab group={group} onChanged={reload} />}
          </div>
        </>
      ) : (
        <div className="rounded-md border border-dashed border-ink/30 bg-white p-8 text-center">
          <h2 className="font-display text-xl font-bold">Join to see what the group shares</h2>
          <p className="mx-auto mt-1 max-w-md text-sm text-muted">Resources, discussions, sessions and members are visible to members only.</p>
          <div className="mt-4 flex justify-center">
            <Button onClick={join} loading={joining}>
              Join group
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirm !== null}
        onClose={() => setConfirm(null)}
        onConfirm={runConfirmed}
        loading={busy}
        title={confirm === 'delete' ? 'Delete this group?' : 'Leave this group?'}
        message={confirm === 'delete' ? 'This permanently deletes the group with all its resources, discussions and sessions for every member.' : 'You will lose access to the group until you join again.'}
        confirmLabel={confirm === 'delete' ? 'Delete group' : 'Leave group'}
      />
    </>
  )
}
