/** Shared by the mock API and the HTTP client so `err instanceof ApiError` works with either. */
export class ApiError extends Error {
  constructor(status, message, fields = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fields = fields
  }
}
