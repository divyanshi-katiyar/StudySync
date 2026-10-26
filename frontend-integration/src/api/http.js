/**
 * HTTP client for the Week 3 Flask API. Same function names and return shapes as the Week 2 mock (mock.js),
 * so no page or component changes. Created with a factory so it can be tested outside the browser.
 *
 * Tokens: the 15-minute access token lives only in memory. The 7-day refresh token is an httpOnly cookie the
 * script cannot read; on page load and after a 401 the client calls POST /auth/refresh to get a new access token.
 */
import { ApiError } from './errors'

export function createHttpApi(baseUrl, fetchImpl = (...args) => fetch(...args)) {
  let accessToken = null
  let refreshing = null // single flight: parallel 401s share one refresh call (the server rotates the cookie on every use)

  async function raw(method, path, { body, query, token } = {}) {
    const url = new URL(baseUrl.replace(/\/$/, '') + path)
    Object.entries(query ?? {}).forEach(([k, v]) => v !== '' && v != null && url.searchParams.set(k, v))
    let res
    try {
      res = await fetchImpl(url.toString(), {
        method,
        credentials: 'include',
        headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: body !== undefined ? JSON.stringify(body) : undefined,
      })
    } catch {
      throw new ApiError(0, 'Cannot reach the server. Check your connection and try again.')
    }
    const json = await res.json().catch(() => null)
    if (!res.ok || !json?.success) throw new ApiError(res.status, json?.message ?? 'Something went wrong. Please try again.', json?.errors ?? {})
    return json.data
  }

  function refresh() {
    refreshing ??= raw('POST', '/auth/refresh')
      .then((data) => {
        accessToken = data.accessToken
        return data
      })
      .catch((err) => {
        accessToken = null
        throw err
      })
      .finally(() => {
        refreshing = null
      })
    return refreshing
  }

  async function call(method, path, opts = {}) {
    if (!accessToken) await refresh()
    try {
      return await raw(method, path, { ...opts, token: accessToken })
    } catch (err) {
      if (err.status !== 401) throw err
      await refresh() // the access token expired: get a new one once, then retry
      return raw(method, path, { ...opts, token: accessToken })
    }
  }

  const signIn = (data) => {
    accessToken = data.accessToken
    return data.user
  }
  const iso = (local) => (local ? new Date(local).toISOString() : local) // <input type="datetime-local"> gives local time without an offset

  const auth = {
    register: async (values) => signIn(await raw('POST', '/auth/register', { body: values })),
    login: async (values) => signIn(await raw('POST', '/auth/login', { body: values })),
    me: async () => (accessToken ? call('GET', '/users/me') : (await refresh()).user),
    logout: async () => {
      await raw('POST', '/auth/logout').catch(() => {})
      accessToken = null
      return { ok: true }
    },
    updateProfile: (values) => call('PATCH', '/users/me', { body: values }),
    changePassword: (values) => call('POST', '/users/me/password', { body: values }),
    resetDemoData: async () => ({ ok: true }), // mock-only feature
  }

  const groups = {
    list: (params = {}) => call('GET', '/groups', { query: params }),
    mine: () => call('GET', '/groups/mine'),
    get: (id) => call('GET', `/groups/${id}`),
    create: (values) => call('POST', '/groups', { body: values }),
    update: (id, values) => call('PATCH', `/groups/${id}`, { body: values }),
    join: (id) => call('POST', `/groups/${id}/join`),
    joinByCode: (code) => call('POST', '/groups/join-by-code', { body: { code } }),
    leave: (id) => call('DELETE', `/groups/${id}/leave`),
    remove: (id) => call('DELETE', `/groups/${id}`),
    transferOwnership: (id, userId) => call('POST', `/groups/${id}/transfer-ownership`, { body: { userId } }),
    members: (id) => call('GET', `/groups/${id}/members`),
    setMemberRole: (id, userId, role) => call('PATCH', `/groups/${id}/members/${userId}`, { body: { role } }),
    removeMember: (id, userId) => call('DELETE', `/groups/${id}/members/${userId}`),
  }

  const resources = {
    list: (groupId, { type = '', search = '' } = {}) => call('GET', `/groups/${groupId}/resources`, { query: { type, search } }),
    add: (groupId, values) => call('POST', `/groups/${groupId}/resources`, { body: values }),
    update: (id, values) => call('PATCH', `/resources/${id}`, { body: values }),
    remove: (id) => call('DELETE', `/resources/${id}`),
  }

  const posts = {
    list: (groupId) => call('GET', `/groups/${groupId}/posts`),
    create: (groupId, values) => call('POST', `/groups/${groupId}/posts`, { body: values }),
    get: (id) => call('GET', `/posts/${id}`),
    update: (id, values) => call('PATCH', `/posts/${id}`, { body: values }),
    remove: (id) => call('DELETE', `/posts/${id}`),
    addComment: (postId, values) => call('POST', `/posts/${postId}/comments`, { body: values }),
    removeComment: (id) => call('DELETE', `/comments/${id}`),
  }

  const sessions = {
    list: (groupId) => call('GET', `/groups/${groupId}/sessions`),
    upcoming: () => call('GET', '/sessions'),
    create: (groupId, v) => call('POST', `/groups/${groupId}/sessions`, { body: { ...v, startsAt: iso(v.startsAt), durationMin: Number(v.durationMin) } }),
    update: (id, v) => call('PATCH', `/sessions/${id}`, { body: v.startsAt ? { ...v, startsAt: iso(v.startsAt) } : v }),
    remove: (id) => call('DELETE', `/sessions/${id}`),
    rsvp: (id, status) => call('PUT', `/sessions/${id}/rsvp`, { body: { status } }),
  }

  const notifications = {
    list: () => call('GET', '/notifications'),
    markRead: (id) => call('PATCH', `/notifications/${id}/read`),
    markAllRead: () => call('PATCH', '/notifications/read-all'),
    simulateIncoming: async () => null, // live events arrive over Socket.io in Week 4
  }

  const dashboard = { get: () => call('GET', '/users/me/dashboard') }

  return { auth, groups, resources, posts, sessions, notifications, dashboard }
}
