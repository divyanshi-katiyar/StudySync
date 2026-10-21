/**
 * API layer.
 *
 * Every function here corresponds to an endpoint from the Week 1 API design (noted in each comment).
 * For now they run against the localStorage mock database with a short artificial delay so loading and
 * error states behave like they will with a network. In Week 3 only this file changes: each function
 * becomes an Axios call, and the rest of the app keeps working untouched.
 */
import { SUBJECTS, subjectColor } from '../utils/subjects'
import { validate, required, minLength, maxLength, email, password, url } from '../utils/validation'
import { load, save, uid, resetDb, SESSION_KEY } from './mockDb'

/* ---------- plumbing ---------- */

let latency = { min: 180, max: 420 }
/** Tests call setLatency(0) so interactions resolve immediately. */
export const setLatency = (min, max = min) => {
  latency = { min, max }
}
const wait = () => new Promise((resolve) => setTimeout(resolve, latency.min + Math.random() * (latency.max - latency.min)))

export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fields = fields
  }
}

const clone = (v) => JSON.parse(JSON.stringify(v))
async function run(fn) {
  await wait()
  return clone(fn(load()))
}

const sessionUserId = () => {
  try {
    return JSON.parse(localStorage.getItem(SESSION_KEY))?.userId ?? null
  } catch {
    return null
  }
}
const me = () => {
  const id = sessionUserId()
  if (!id) throw new ApiError(401, 'Sign in to continue.')
  return id
}
const publicUser = (u) => (u ? { id: u.id, name: u.name, email: u.email, role: u.role, createdAt: u.createdAt } : null)
const userName = (db, id) => db.users.find((u) => u.id === id)?.name ?? 'Former member'
const membershipOf = (db, groupId, userId) => db.memberships.find((m) => m.groupId === groupId && m.userId === userId)
const groupOrThrow = (db, id) => {
  const group = db.groups.find((g) => g.id === id)
  if (!group) throw new ApiError(404, 'That group does not exist.')
  return group
}
const requireMember = (db, groupId, userId) => {
  const membership = membershipOf(db, groupId, userId)
  if (!membership) throw new ApiError(403, 'Join this group to see its content.')
  return membership
}
const isStaff = (membership) => membership && ['owner', 'moderator'].includes(membership.role)
const failValidation = (errors) => {
  if (Object.keys(errors).length) throw new ApiError(422, 'Please fix the highlighted fields.', errors)
}

function decorateGroup(db, group, userId) {
  const membership = userId ? membershipOf(db, group.id, userId) : null
  const upcoming = db.sessions
    .filter((s) => s.groupId === group.id && new Date(s.startsAt) > new Date())
    .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt))[0]
  return {
    id: group.id,
    name: group.name,
    description: group.description,
    subject: group.subject,
    color: subjectColor(group.subject),
    visibility: group.visibility,
    ownerId: group.ownerId,
    ownerName: userName(db, group.ownerId),
    createdAt: group.createdAt,
    memberCount: db.memberships.filter((m) => m.groupId === group.id).length,
    isMember: Boolean(membership),
    myRole: membership?.role ?? null,
    inviteCode: membership ? group.inviteCode : undefined,
    nextSession: upcoming ? { id: upcoming.id, title: upcoming.title, startsAt: upcoming.startsAt } : null,
  }
}

function decorateSession(db, session, userId) {
  const group = db.groups.find((g) => g.id === session.groupId)
  const mine = session.attendees.find((a) => a.userId === userId)
  return {
    ...session,
    groupName: group?.name,
    groupColor: group ? subjectColor(group.subject) : undefined,
    goingCount: session.attendees.filter((a) => a.status === 'going').length,
    maybeCount: session.attendees.filter((a) => a.status === 'maybe').length,
    myRsvp: mine?.status ?? null,
    createdByName: userName(db, session.createdBy),
  }
}

const addMembership = (db, groupId, userId, role = 'member') => {
  db.memberships.push({ id: uid('m'), groupId, userId, role, joinedAt: new Date().toISOString() })
}

/* ---------- auth: /api/auth/* ---------- */

export const auth = {
  /** POST /api/auth/register */
  register: ({ name, email: mail, password: pass }) =>
    run((db) => {
      failValidation(validate({ name: [required('your name'), minLength(2, 'Name'), maxLength(60, 'Name')], email: [required('your email'), email], password: [required('a password'), password] }, { name, email: mail, password: pass }))
      const normalised = mail.trim().toLowerCase()
      if (db.users.some((u) => u.email === normalised)) {
        throw new ApiError(409, 'That email is already registered.', { email: 'An account with this email already exists. Try logging in instead.' })
      }
      const user = { id: uid('u'), name: name.trim(), email: normalised, password: pass, role: 'student', createdAt: new Date().toISOString() }
      db.users.push(user)
      save(db)
      localStorage.setItem(SESSION_KEY, JSON.stringify({ userId: user.id }))
      return publicUser(user)
    }),

  /** POST /api/auth/login */
  login: ({ email: mail, password: pass }) =>
    run((db) => {
      failValidation(validate({ email: [required('your email'), email], password: [required('your password')] }, { email: mail, password: pass }))
      const user = db.users.find((u) => u.email === mail.trim().toLowerCase())
      if (!user || user.password !== pass) throw new ApiError(401, 'The email or password is incorrect.')
      localStorage.setItem(SESSION_KEY, JSON.stringify({ userId: user.id }))
      return publicUser(user)
    }),

  /** GET /api/users/me */
  me: () => run((db) => publicUser(db.users.find((u) => u.id === me()))),

  /** POST /api/auth/logout */
  logout: () =>
    run(() => {
      localStorage.removeItem(SESSION_KEY)
      return { ok: true }
    }),

  /** PATCH /api/users/me */
  updateProfile: ({ name }) =>
    run((db) => {
      failValidation(validate({ name: [required('your name'), minLength(2, 'Name'), maxLength(60, 'Name')] }, { name }))
      const user = db.users.find((u) => u.id === me())
      user.name = name.trim()
      save(db)
      return publicUser(user)
    }),

  /** Demo helper: wipes and re-seeds the mock database. Not part of the real API. */
  resetDemoData: () =>
    run(() => {
      resetDb()
      return { ok: true }
    }),
}

/* ---------- groups: /api/groups/* ---------- */

export const groups = {
  subjects: SUBJECTS,

  /** GET /api/groups?search=&subject=&sort=&page= (public groups only) */
  list: ({ search = '', subject = '', sort = 'popular', page = 1, limit = 6 } = {}) =>
    run((db) => {
      const userId = sessionUserId()
      const q = search.trim().toLowerCase()
      let items = db.groups
        .filter((g) => g.visibility === 'public')
        .filter((g) => !subject || g.subject === subject)
        .filter((g) => !q || [g.name, g.subject, g.description].some((t) => t.toLowerCase().includes(q)))
        .map((g) => decorateGroup(db, g, userId))
      items.sort((a, b) => (sort === 'newest' ? new Date(b.createdAt) - new Date(a.createdAt) : b.memberCount - a.memberCount))
      const total = items.length
      const pages = Math.max(1, Math.ceil(total / limit))
      const safePage = Math.min(Math.max(1, page), pages)
      items = items.slice((safePage - 1) * limit, safePage * limit)
      return { items, total, page: safePage, pages }
    }),

  /** GET /api/groups/mine */
  mine: () =>
    run((db) => {
      const userId = me()
      return db.memberships
        .filter((m) => m.userId === userId)
        .map((m) => decorateGroup(db, groupOrThrow(db, m.groupId), userId))
        .sort((a, b) => a.name.localeCompare(b.name))
    }),

  /** GET /api/groups/:id */
  get: (id) =>
    run((db) => {
      const userId = me()
      const group = groupOrThrow(db, id)
      if (group.visibility === 'private' && !membershipOf(db, id, userId)) {
        throw new ApiError(403, 'This group is private. Ask the owner for an invite code.')
      }
      return decorateGroup(db, group, userId)
    }),

  /** POST /api/groups */
  create: ({ name, description, subject, visibility }) =>
    run((db) => {
      const userId = me()
      failValidation(
        validate(
          {
            name: [required('a group name'), minLength(3, 'Group name'), maxLength(60, 'Group name')],
            description: [required('a short description'), minLength(10, 'Description'), maxLength(300, 'Description')],
            subject: [(v) => (SUBJECTS.includes(v) ? '' : 'Choose a subject.')],
            visibility: [(v) => (['public', 'private'].includes(v) ? '' : 'Choose who can find this group.')],
          },
          { name, description, subject, visibility },
        ),
      )
      const group = {
        id: uid('g'),
        name: name.trim(),
        description: description.trim(),
        subject,
        visibility,
        ownerId: userId,
        inviteCode: `${subject.replace(/[^A-Za-z]/g, '').slice(0, 3).toUpperCase()}-${Math.floor(1000 + Math.random() * 9000)}`,
        createdAt: new Date().toISOString(),
      }
      db.groups.push(group)
      addMembership(db, group.id, userId, 'owner')
      save(db)
      return decorateGroup(db, group, userId)
    }),

  /** POST /api/groups/:id/join */
  join: (id) =>
    run((db) => {
      const userId = me()
      const group = groupOrThrow(db, id)
      if (group.visibility === 'private') throw new ApiError(403, 'This group is private. Ask the owner for an invite code.')
      if (membershipOf(db, id, userId)) throw new ApiError(409, 'You are already in this group.')
      addMembership(db, id, userId)
      save(db)
      return decorateGroup(db, group, userId)
    }),

  /** POST /api/groups/join-by-code */
  joinByCode: (code) =>
    run((db) => {
      const userId = me()
      const normalised = String(code ?? '').trim().toUpperCase()
      if (!normalised) throw new ApiError(422, 'Enter an invite code.', { code: 'Enter an invite code.' })
      const group = db.groups.find((g) => g.inviteCode === normalised)
      if (!group) throw new ApiError(404, 'No group matches that invite code.', { code: 'No group matches that code. Check it and try again.' })
      if (membershipOf(db, group.id, userId)) throw new ApiError(409, 'You are already in this group.', { code: 'You are already in this group.' })
      addMembership(db, group.id, userId)
      save(db)
      return decorateGroup(db, group, userId)
    }),

  /** DELETE /api/groups/:id/leave */
  leave: (id) =>
    run((db) => {
      const userId = me()
      const membership = requireMember(db, id, userId)
      if (membership.role === 'owner') throw new ApiError(409, 'Owners cannot leave their own group. Delete it instead.')
      db.memberships = db.memberships.filter((m) => m.id !== membership.id)
      save(db)
      return { ok: true }
    }),

  /** DELETE /api/groups/:id */
  remove: (id) =>
    run((db) => {
      const userId = me()
      const membership = requireMember(db, id, userId)
      if (membership.role !== 'owner') throw new ApiError(403, 'Only the owner can delete a group.')
      const postIds = db.posts.filter((p) => p.groupId === id).map((p) => p.id)
      db.groups = db.groups.filter((g) => g.id !== id)
      db.memberships = db.memberships.filter((m) => m.groupId !== id)
      db.resources = db.resources.filter((r) => r.groupId !== id)
      db.sessions = db.sessions.filter((s) => s.groupId !== id)
      db.posts = db.posts.filter((p) => p.groupId !== id)
      db.comments = db.comments.filter((c) => !postIds.includes(c.postId))
      save(db)
      return { ok: true }
    }),

  /** GET /api/groups/:id/members */
  members: (id) =>
    run((db) => {
      requireMember(db, id, me())
      const order = { owner: 0, moderator: 1, member: 2 }
      return db.memberships
        .filter((m) => m.groupId === id)
        .map((m) => ({ userId: m.userId, name: userName(db, m.userId), role: m.role, joinedAt: m.joinedAt }))
        .sort((a, b) => order[a.role] - order[b.role] || a.name.localeCompare(b.name))
    }),

  /** PATCH /api/groups/:id/members/:userId */
  setMemberRole: (id, targetId, role) =>
    run((db) => {
      const mine = requireMember(db, id, me())
      if (mine.role !== 'owner') throw new ApiError(403, 'Only the owner can change roles.')
      const target = membershipOf(db, id, targetId)
      if (!target || target.role === 'owner') throw new ApiError(404, 'That member cannot be changed.')
      if (!['moderator', 'member'].includes(role)) throw new ApiError(422, 'Choose moderator or member.')
      target.role = role
      save(db)
      return { ok: true }
    }),

  /** DELETE /api/groups/:id/members/:userId */
  removeMember: (id, targetId) =>
    run((db) => {
      const mine = requireMember(db, id, me())
      const target = membershipOf(db, id, targetId)
      if (!target || target.role === 'owner') throw new ApiError(404, 'That member cannot be removed.')
      const allowed = mine.role === 'owner' || (mine.role === 'moderator' && target.role === 'member')
      if (!allowed) throw new ApiError(403, 'You do not have permission to remove this member.')
      db.memberships = db.memberships.filter((m) => m.id !== target.id)
      save(db)
      return { ok: true }
    }),
}

/* ---------- resources ---------- */

export const resources = {
  /** GET /api/groups/:id/resources */
  list: (groupId, { type = '', search = '' } = {}) =>
    run((db) => {
      const userId = me()
      const membership = requireMember(db, groupId, userId)
      const q = search.trim().toLowerCase()
      return db.resources
        .filter((r) => r.groupId === groupId)
        .filter((r) => !type || r.type === type)
        .filter((r) => !q || r.title.toLowerCase().includes(q) || r.tags.some((t) => t.includes(q)))
        .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
        .map((r) => ({ ...r, uploaderName: userName(db, r.uploadedBy), canDelete: r.uploadedBy === userId || isStaff(membership) }))
    }),

  /** POST /api/groups/:id/resources */
  add: (groupId, { title, type, url: link, body, tags }) =>
    run((db) => {
      const userId = me()
      requireMember(db, groupId, userId)
      const rules = {
        title: [required('a title'), minLength(3, 'Title'), maxLength(100, 'Title')],
        type: [(v) => (['link', 'file', 'note'].includes(v) ? '' : 'Choose a type.')],
      }
      if (type === 'note') rules.body = [required('your note'), minLength(10, 'Note')]
      else rules.url = [required('a link'), url]
      failValidation(validate(rules, { title, type, url: link, body }))
      const resource = {
        id: uid('r'),
        groupId,
        uploadedBy: userId,
        title: title.trim(),
        type,
        url: type === 'note' ? '' : link.trim(),
        body: type === 'note' ? body.trim() : '',
        tags: [...new Set((tags ?? []).map((t) => t.trim().toLowerCase().replace(/^#/, '')).filter(Boolean))].slice(0, 6),
        createdAt: new Date().toISOString(),
      }
      db.resources.push(resource)
      save(db)
      return resource
    }),

  /** DELETE /api/resources/:id */
  remove: (id) =>
    run((db) => {
      const userId = me()
      const resource = db.resources.find((r) => r.id === id)
      if (!resource) throw new ApiError(404, 'That resource no longer exists.')
      const membership = membershipOf(db, resource.groupId, userId)
      if (resource.uploadedBy !== userId && !isStaff(membership)) throw new ApiError(403, 'Only the uploader or a moderator can delete this.')
      db.resources = db.resources.filter((r) => r.id !== id)
      save(db)
      return { ok: true }
    }),
}

/* ---------- discussion ---------- */

export const posts = {
  /** GET /api/groups/:id/posts */
  list: (groupId) =>
    run((db) => {
      requireMember(db, groupId, me())
      return db.posts
        .filter((p) => p.groupId === groupId)
        .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
        .map((p) => ({ ...p, authorName: userName(db, p.authorId), commentCount: db.comments.filter((c) => c.postId === p.id).length }))
    }),

  /** POST /api/groups/:id/posts */
  create: (groupId, { title, body }) =>
    run((db) => {
      const userId = me()
      requireMember(db, groupId, userId)
      failValidation(validate({ title: [required('a title'), minLength(5, 'Title'), maxLength(120, 'Title')], body: [required('some details'), minLength(10, 'Details')] }, { title, body }))
      const post = { id: uid('p'), groupId, authorId: userId, title: title.trim(), body: body.trim(), createdAt: new Date().toISOString() }
      db.posts.push(post)
      save(db)
      return post
    }),

  /** GET /api/posts/:id (with comments) */
  get: (postId) =>
    run((db) => {
      const userId = me()
      const post = db.posts.find((p) => p.id === postId)
      if (!post) throw new ApiError(404, 'That post does not exist.')
      requireMember(db, post.groupId, userId)
      const group = groupOrThrow(db, post.groupId)
      return {
        ...post,
        authorName: userName(db, post.authorId),
        group: { id: group.id, name: group.name },
        comments: db.comments
          .filter((c) => c.postId === postId)
          .sort((a, b) => new Date(a.createdAt) - new Date(b.createdAt))
          .map((c) => ({ ...c, authorName: userName(db, c.authorId) })),
      }
    }),

  /** POST /api/posts/:id/comments */
  addComment: (postId, { body }) =>
    run((db) => {
      const userId = me()
      const post = db.posts.find((p) => p.id === postId)
      if (!post) throw new ApiError(404, 'That post does not exist.')
      requireMember(db, post.groupId, userId)
      failValidation(validate({ body: [required('a comment'), minLength(2, 'Comment'), maxLength(1000, 'Comment')] }, { body }))
      const comment = { id: uid('c'), postId, authorId: userId, body: body.trim(), createdAt: new Date().toISOString() }
      db.comments.push(comment)
      save(db)
      return { ...comment, authorName: userName(db, userId) }
    }),
}

/* ---------- sessions ---------- */

export const sessions = {
  /** GET /api/groups/:id/sessions */
  list: (groupId) =>
    run((db) => {
      const userId = me()
      requireMember(db, groupId, userId)
      return db.sessions
        .filter((s) => s.groupId === groupId)
        .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt))
        .map((s) => decorateSession(db, s, userId))
    }),

  /** GET /api/sessions (upcoming sessions across all my groups; used by Dashboard and Sessions page) */
  upcoming: () =>
    run((db) => {
      const userId = me()
      const mine = new Set(db.memberships.filter((m) => m.userId === userId).map((m) => m.groupId))
      return db.sessions
        .filter((s) => mine.has(s.groupId) && new Date(s.startsAt) > new Date())
        .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt))
        .map((s) => decorateSession(db, s, userId))
    }),

  /** POST /api/groups/:id/sessions (moderators and owners) */
  create: (groupId, { title, startsAt, durationMin, meetingLink }) =>
    run((db) => {
      const userId = me()
      const membership = requireMember(db, groupId, userId)
      if (!isStaff(membership)) throw new ApiError(403, 'Only moderators and the owner can schedule sessions.')
      const minutes = Number(durationMin)
      failValidation(
        validate(
          {
            title: [required('a title'), minLength(3, 'Title'), maxLength(100, 'Title')],
            startsAt: [(v) => (!v || Number.isNaN(new Date(v).getTime()) ? 'Pick a date and time.' : new Date(v) <= new Date() ? 'Pick a time in the future.' : '')],
            durationMin: [() => (Number.isFinite(minutes) && minutes >= 15 && minutes <= 300 ? '' : 'Enter a length between 15 and 300 minutes.')],
            meetingLink: [(v) => (String(v ?? '').trim() ? url(v) : '')],
          },
          { title, startsAt, durationMin, meetingLink },
        ),
      )
      const session = {
        id: uid('s'),
        groupId,
        createdBy: userId,
        title: title.trim(),
        startsAt: new Date(startsAt).toISOString(),
        durationMin: minutes,
        meetingLink: String(meetingLink ?? '').trim(),
        attendees: [{ userId, status: 'going' }],
        createdAt: new Date().toISOString(),
      }
      db.sessions.push(session)
      save(db)
      return decorateSession(db, session, userId)
    }),

  /** PUT /api/sessions/:id/rsvp */
  rsvp: (sessionId, status) =>
    run((db) => {
      const userId = me()
      const session = db.sessions.find((s) => s.id === sessionId)
      if (!session) throw new ApiError(404, 'That session no longer exists.')
      requireMember(db, session.groupId, userId)
      if (!['going', 'maybe', 'no'].includes(status)) throw new ApiError(422, 'Choose going, maybe or no.')
      const existing = session.attendees.find((a) => a.userId === userId)
      if (existing) existing.status = status
      else session.attendees.push({ userId, status })
      save(db)
      return decorateSession(db, session, userId)
    }),
}

/* ---------- notifications ---------- */

export const notifications = {
  /** GET /api/notifications */
  list: () =>
    run((db) => {
      const userId = me()
      return db.notifications.filter((n) => n.userId === userId).sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt))
    }),

  /** PATCH /api/notifications/:id/read */
  markRead: (id) =>
    run((db) => {
      const n = db.notifications.find((x) => x.id === id && x.userId === me())
      if (n) n.isRead = true
      save(db)
      return { ok: true }
    }),

  /** PATCH /api/notifications/read-all */
  markAllRead: () =>
    run((db) => {
      const userId = me()
      db.notifications.filter((n) => n.userId === userId).forEach((n) => (n.isRead = true))
      save(db)
      return { ok: true }
    }),

  /**
   * Stand-in for a Socket.io "notification" event. Another member shares a resource in one of your groups,
   * and the matching notification is stored, exactly what the notification service will do in Week 4.
   */
  simulateIncoming: () =>
    run((db) => {
      const userId = me()
      const mine = db.memberships.filter((m) => m.userId === userId)
      if (!mine.length) return null
      const membership = mine[Math.floor(Math.random() * mine.length)]
      const group = groupOrThrow(db, membership.groupId)
      const others = db.memberships.filter((m) => m.groupId === group.id && m.userId !== userId)
      if (!others.length) return null
      const sender = others[Math.floor(Math.random() * others.length)].userId
      const title = 'Last-minute revision checklist'
      db.resources.push({
        id: uid('r'), groupId: group.id, uploadedBy: sender, title, type: 'note', url: '',
        body: 'A short checklist of the topics most likely to come up, ordered by how often they appeared in past papers.',
        tags: ['revision'], createdAt: new Date().toISOString(),
      })
      const n = {
        id: uid('n'), userId, type: 'resource',
        message: `${userName(db, sender)} shared a new resource in ${group.name}`,
        link: `/app/groups/${group.id}?tab=resources`, isRead: false, createdAt: new Date().toISOString(),
      }
      db.notifications.push(n)
      save(db)
      return n
    }),
}

/* ---------- dashboard ---------- */

export const dashboard = {
  /** GET /api/users/me/dashboard */
  get: () =>
    run((db) => {
      const userId = me()
      const mineIds = db.memberships.filter((m) => m.userId === userId).map((m) => m.groupId)
      const weekAhead = Date.now() + 7 * 24 * 3_600_000
      const weekAgo = Date.now() - 7 * 24 * 3_600_000
      const upcoming = db.sessions
        .filter((s) => mineIds.includes(s.groupId) && new Date(s.startsAt) > new Date())
        .sort((a, b) => new Date(a.startsAt) - new Date(b.startsAt))
      return {
        counts: {
          groups: mineIds.length,
          sessionsThisWeek: upcoming.filter((s) => new Date(s.startsAt).getTime() < weekAhead).length,
          newResources: db.resources.filter((r) => mineIds.includes(r.groupId) && r.uploadedBy !== userId && new Date(r.createdAt).getTime() > weekAgo).length,
        },
        upcomingSessions: upcoming.slice(0, 3).map((s) => decorateSession(db, s, userId)),
        myGroups: mineIds.map((id) => decorateGroup(db, groupOrThrow(db, id), userId)).slice(0, 3),
      }
    }),
}
