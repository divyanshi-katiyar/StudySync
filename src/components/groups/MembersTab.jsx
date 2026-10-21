import { useState } from 'react'
import { groups } from '../../api'
import { useAsync } from '../../hooks/useAsync'
import { useAuth } from '../../context/AuthContext'
import { useToast } from '../../context/ToastContext'
import { timeAgo } from '../../utils/format'
import Avatar from '../ui/Avatar'
import Badge from '../ui/Badge'
import Button from '../ui/Button'
import ConfirmDialog from '../ui/ConfirmDialog'
import { ErrorState } from '../ui/States'
import { ListSkeleton } from '../ui/Skeleton'

const ROLE_LABEL = { owner: 'Owner', moderator: 'Moderator', member: 'Member' }

export default function MembersTab({ group, onChanged }) {
  const { user } = useAuth()
  const toast = useToast()
  const { data, error, loading, reload } = useAsync(() => groups.members(group.id), [group.id])
  const [toRemove, setToRemove] = useState(null)
  const [removing, setRemoving] = useState(false)
  const isOwner = group.myRole === 'owner'
  const isMod = group.myRole === 'moderator'

  const changeRole = async (member, role) => {
    try {
      await groups.setMemberRole(group.id, member.userId, role)
      toast.success(`${member.name} is now a ${role}.`)
      reload()
    } catch (err) {
      toast.error(err.message)
    }
  }

  const confirmRemove = async () => {
    setRemoving(true)
    try {
      await groups.removeMember(group.id, toRemove.userId)
      toast.success(`${toRemove.name} was removed from the group.`)
      setToRemove(null)
      reload()
      onChanged?.()
    } catch (err) {
      toast.error(err.message)
    } finally {
      setRemoving(false)
    }
  }

  if (error) return <ErrorState error={error} onRetry={reload} />
  if (loading && !data) return <ListSkeleton />

  return (
    <div>
      <ul className="divide-y divide-line rounded-md border border-line bg-white">
        {data.map((m) => {
          const isSelf = m.userId === user?.id
          const canRemove = !isSelf && m.role !== 'owner' && (isOwner || (isMod && m.role === 'member'))
          return (
            <li key={m.userId} className="flex flex-wrap items-center gap-3 p-4">
              <Avatar name={m.name} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold">
                  {m.name}
                  {isSelf && <span className="font-normal text-muted"> (you)</span>}
                </p>
                <p className="text-sm text-muted">Joined {timeAgo(m.joinedAt)}</p>
              </div>
              {isOwner && !isSelf && m.role !== 'owner' ? (
                <div>
                  <label htmlFor={`role-${m.userId}`} className="sr-only">
                    Role for {m.name}
                  </label>
                  <select id={`role-${m.userId}`} value={m.role} onChange={(e) => changeRole(m, e.target.value)} className="min-h-[40px] rounded-md border border-ink/30 bg-white px-2 text-sm hover:border-ink/60">
                    <option value="member">Member</option>
                    <option value="moderator">Moderator</option>
                  </select>
                </div>
              ) : (
                <Badge tone={m.role === 'owner' ? 'hilite' : m.role === 'moderator' ? 'marker' : 'neutral'}>{ROLE_LABEL[m.role]}</Badge>
              )}
              {canRemove && (
                <Button variant="ghost" size="sm" onClick={() => setToRemove(m)} className="text-danger hover:bg-danger-soft">
                  Remove<span className="sr-only"> {m.name}</span>
                </Button>
              )}
            </li>
          )
        })}
      </ul>
      <ConfirmDialog open={Boolean(toRemove)} onClose={() => setToRemove(null)} onConfirm={confirmRemove} loading={removing} title="Remove this member?" message={`${toRemove?.name} will lose access to the group's resources, discussions and sessions. They can rejoin later.`} confirmLabel="Remove member" />
    </div>
  )
}
