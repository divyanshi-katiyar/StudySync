/**
 * API layer entry point. The only file the rest of the app imports from.
 *   VITE_API_URL set   -> talks to the Flask API (Week 3)
 *   VITE_API_URL empty -> uses the browser mock database (Week 2; this is also what the Vitest suite uses)
 */
import { SUBJECTS } from '../utils/subjects'
import { ApiError } from './errors'
import { createHttpApi } from './http'
import * as mock from './mock'

const baseUrl = import.meta.env.VITE_API_URL
export const usesRealApi = Boolean(baseUrl)

const real = usesRealApi ? createHttpApi(baseUrl) : null
const pick = (name) => (real ? { ...real[name], ...(name === 'groups' ? { subjects: SUBJECTS } : {}) } : mock[name])

export { ApiError }
export const setLatency = mock.setLatency
export const auth = pick('auth')
export const groups = pick('groups')
export const resources = pick('resources')
export const posts = pick('posts')
export const sessions = pick('sessions')
export const notifications = pick('notifications')
export const dashboard = pick('dashboard')
