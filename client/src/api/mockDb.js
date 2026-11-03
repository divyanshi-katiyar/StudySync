/**
 * Browser-side mock database (localStorage).
 *
 * The REST API from the Week 1 design is built in Week 3. Until then this module plays the role of
 * MongoDB: eight collections that mirror the Week 1 ER diagram. The shape of every record matches the
 * planned Mongoose schemas, so swapping in the real API only touches src/api/index.js.
 *
 * DEMO ONLY: passwords are stored in plain text here because there is no server. The real API hashes them with bcrypt.
 */

const DB_KEY = 'studysync.db.v1'
export const SESSION_KEY = 'studysync.session'
export const DEMO_ACCOUNT = { email: 'demo@studysync.app', password: 'Password123' }

let cache = null

const HOUR = 3_600_000
const fromNow = (hours) => new Date(Date.now() + hours * HOUR).toISOString()

export const uid = (prefix) => `${prefix}_${Math.random().toString(36).slice(2, 10)}`

function seed() {
  const now = new Date().toISOString()
  const users = [
    { id: 'u1', name: 'Alex Rao', email: DEMO_ACCOUNT.email, password: DEMO_ACCOUNT.password, role: 'student', createdAt: fromNow(-24 * 60) },
    { id: 'u2', name: 'Priya Nair', email: 'priya@studysync.app', password: 'Password123', role: 'student', createdAt: fromNow(-24 * 70) },
    { id: 'u3', name: 'Sam Mathew', email: 'sam@studysync.app', password: 'Password123', role: 'student', createdAt: fromNow(-24 * 65) },
    { id: 'u4', name: 'Rohan Verma', email: 'rohan@studysync.app', password: 'Password123', role: 'student', createdAt: fromNow(-24 * 50) },
    { id: 'u5', name: 'Meera Iyer', email: 'meera@studysync.app', password: 'Password123', role: 'student', createdAt: fromNow(-24 * 45) },
    { id: 'u6', name: 'Kabir Shah', email: 'kabir@studysync.app', password: 'Password123', role: 'student', createdAt: fromNow(-24 * 40) },
  ]

  const g = (id, name, subject, description, visibility, ownerId, inviteCode, days) => ({
    id, name, subject, description, visibility, ownerId, inviteCode, createdAt: fromNow(-24 * days),
  })
  const groups = [
    g('g1', 'Algorithms Study Circle', 'Data Structures', 'Weekly problem-solving rounds for interviews and exams. We start with graphs, then move to dynamic programming.', 'public', 'u2', 'DAT-4821', 30),
    g('g2', 'Database Gang', 'Databases', 'Normalisation, indexing and SQL practice for the DBMS paper. Bring your own tricky queries.', 'public', 'u3', 'DAT-7710', 28),
    g('g3', 'OS Notes Hub', 'Operating Systems', 'Shared notes on scheduling, memory and file systems, with worked examples from past papers.', 'public', 'u4', 'OPE-3302', 25),
    g('g4', 'Web Dev Buddies', 'Web Development', 'Build small full stack projects together and review each other\u2019s code. React, Node and MongoDB.', 'public', 'u5', 'WEB-5519', 22),
    g('g5', 'Aptitude Daily', 'Placements', 'Ten aptitude and reasoning questions a day, plus mock tests every weekend.', 'public', 'u6', 'PLA-1208', 20),
    g('g6', 'ML Reading Club', 'AI and ML', 'We read one paper or chapter every week and discuss it on Sundays.', 'public', 'u2', 'AIA-9043', 14),
    g('g7', 'Compiler Design Crew', 'Compilers', 'Private group for the compiler design project team. Join with the invite code.', 'private', 'u3', 'COM-2026', 12),
    g('g8', 'Networks Lab Partners', 'Networks', 'Pair up for the networks lab: packet tracing, socket programming and subnetting drills.', 'public', 'u4', 'NET-6671', 9),
  ]

  const m = (groupId, userId, role = 'member', days = 5) => ({ id: uid('m'), groupId, userId, role, joinedAt: fromNow(-24 * days) })
  const memberships = [
    m('g1', 'u2', 'owner', 30), m('g1', 'u1', 'member', 12), m('g1', 'u3'), m('g1', 'u4'), m('g1', 'u5'),
    m('g2', 'u3', 'owner', 28), m('g2', 'u1', 'moderator', 20), m('g2', 'u2'), m('g2', 'u4'),
    m('g3', 'u4', 'owner', 25), m('g3', 'u2'), m('g3', 'u5'), m('g3', 'u6'),
    m('g4', 'u5', 'owner', 22), m('g4', 'u1', 'member', 8), m('g4', 'u3'), m('g4', 'u6'), m('g4', 'u2'),
    m('g5', 'u6', 'owner', 20), m('g5', 'u2'), m('g5', 'u3'), m('g5', 'u4'), m('g5', 'u5'),
    m('g6', 'u2', 'owner', 14), m('g6', 'u3'), m('g6', 'u5'),
    m('g7', 'u3', 'owner', 12), m('g7', 'u4'),
    m('g8', 'u4', 'owner', 9), m('g8', 'u6'), m('g8', 'u5'),
  ]

  const r = (groupId, uploadedBy, title, type, url, tags, hoursAgo, body = '') => ({
    id: uid('r'), groupId, uploadedBy, title, type, url, body, tags, createdAt: fromNow(-hoursAgo),
  })
  const resources = [
    r('g1', 'u3', 'Graph algorithms cheat-sheet', 'link', 'https://example.com/graph-cheat-sheet', ['graphs', 'notes'], 48),
    r('g1', 'u2', 'DP patterns: video playlist', 'link', 'https://example.com/dp-patterns', ['dp', 'video'], 96),
    r('g1', 'u1', 'Mock test 3', 'file', 'https://example.com/mock-test-3.pdf', ['practice', 'mock-test'], 170),
    r('g1', 'u4', 'Big-O quick notes', 'note', '', ['complexity'], 200, 'O(1) constant, O(log n) halving, O(n) one pass, O(n log n) sorting, O(n^2) nested loops. When two loops run one after the other, add them; when nested, multiply.'),
    r('g2', 'u3', 'Normalisation worked examples', 'note', '', ['normalisation', 'exam'], 6, '1NF removes repeating groups, 2NF removes partial dependencies, 3NF removes transitive dependencies. Try each rule on the student-course-teacher table.'),
    r('g2', 'u2', 'SQL joins visualised', 'link', 'https://example.com/sql-joins', ['sql', 'joins'], 72),
    r('g3', 'u4', 'Process scheduling notes', 'note', '', ['scheduling'], 40, 'Compare FCFS, SJF, round robin and priority scheduling using the same five processes so the differences in waiting time are easy to see.'),
    r('g4', 'u5', 'React hooks mental model', 'link', 'https://example.com/react-hooks', ['react', 'hooks'], 30),
    r('g4', 'u6', 'CSS grid in 20 minutes', 'link', 'https://example.com/css-grid', ['css', 'layout'], 120),
    r('g5', 'u6', 'Aptitude shortcuts sheet', 'link', 'https://example.com/aptitude-shortcuts', ['aptitude'], 60),
  ]

  const posts = [
    { id: 'p1', groupId: 'g1', authorId: 'u3', title: 'How do you decide between BFS and DFS in interviews?', body: 'I keep second-guessing myself. My rule so far: BFS for shortest path in unweighted graphs, DFS for anything about connectivity or ordering. What are your rules of thumb?', createdAt: fromNow(-52) },
    { id: 'p2', groupId: 'g1', authorId: 'u2', title: 'Weekly plan: graphs first, then dynamic programming', body: 'Proposal: two weeks on graphs (traversals, shortest paths, topological sort), then three weeks on DP patterns. Reply if you want a different order.', createdAt: fromNow(-120) },
    { id: 'p3', groupId: 'g2', authorId: 'u2', title: 'Is BCNF always worth it?', body: 'In the lab project we denormalised a table for speed. When is it fine to stop at 3NF and accept some redundancy?', createdAt: fromNow(-30) },
    { id: 'p4', groupId: 'g4', authorId: 'u6', title: 'Which state library should we use for the group project?', body: 'Context plus React Query feels enough for us, but a few people mentioned Redux Toolkit. Thoughts?', createdAt: fromNow(-70) },
  ]
  const comments = [
    { id: 'c1', postId: 'p1', authorId: 'u2', body: 'Same rule here. I also use BFS whenever the question says "minimum number of steps".', createdAt: fromNow(-40) },
    { id: 'c2', postId: 'p1', authorId: 'u4', body: 'DFS is easier to write recursively, so I default to it unless distance matters.', createdAt: fromNow(-26) },
    { id: 'c3', postId: 'p3', authorId: 'u3', body: 'If the table is read far more than it is written, redundancy is usually fine. Just document it.', createdAt: fromNow(-20) },
  ]

  const s = (groupId, createdBy, title, hours, durationMin, meetingLink, attendees) => ({
    id: uid('s'), groupId, createdBy, title, startsAt: fromNow(hours), durationMin, meetingLink, attendees, createdAt: fromNow(-100),
  })
  const sessions = [
    s('g1', 'u2', 'Graph problems: practice round', 26, 90, 'https://meet.example.com/graphs', [{ userId: 'u2', status: 'going' }, { userId: 'u3', status: 'going' }, { userId: 'u4', status: 'maybe' }]),
    s('g1', 'u2', 'Dynamic programming drill', 122, 60, 'https://meet.example.com/dp', [{ userId: 'u2', status: 'going' }]),
    s('g2', 'u1', 'DBMS revision: normalisation', 50, 75, 'https://meet.example.com/dbms', [{ userId: 'u3', status: 'going' }, { userId: 'u2', status: 'going' }]),
    s('g4', 'u5', 'Build a landing page together', 75, 120, 'https://meet.example.com/webdev', [{ userId: 'u5', status: 'going' }, { userId: 'u6', status: 'maybe' }]),
    s('g3', 'u4', 'Paging and segmentation recap', -48, 60, 'https://meet.example.com/os', [{ userId: 'u4', status: 'going' }]),
  ]

  const n = (text, link, hoursAgo, read) => ({ id: uid('n'), userId: 'u1', type: 'info', message: text, link, isRead: read, createdAt: fromNow(-hoursAgo) })
  const notifications = [
    n('Sam shared a new resource in Database Gang', '/app/groups/g2?tab=resources', 6, false),
    n('Priya replied to a post in Algorithms Study Circle', '/app/groups/g1/posts/p1', 26, false),
    n('Session tomorrow: Graph problems: practice round', '/app/groups/g1?tab=sessions', 30, false),
    n('Meera joined Web Dev Buddies', '/app/groups/g4?tab=members', 120, true),
  ]

  return { users, groups, memberships, resources, posts, comments, sessions, notifications, seededAt: now }
}

export function load() {
  if (cache) return cache
  try {
    const raw = localStorage.getItem(DB_KEY)
    if (raw) {
      cache = JSON.parse(raw)
      return cache
    }
  } catch {
    /* corrupted or unavailable storage: fall through and re-seed */
  }
  cache = seed()
  save(cache)
  return cache
}

export function save(db) {
  cache = db
  try {
    localStorage.setItem(DB_KEY, JSON.stringify(db))
  } catch {
    /* storage full or blocked: keep working in memory */
  }
}

/** Wipes everything and re-seeds. Used by "Reset demo data" on the profile page and by tests. */
export function resetDb() {
  cache = null
  try {
    localStorage.removeItem(DB_KEY)
    localStorage.removeItem(SESSION_KEY)
  } catch {
    /* ignore */
  }
  return load()
}
