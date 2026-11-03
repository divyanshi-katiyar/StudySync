// Shared helpers for the Node integration tests (no packages needed: node:test, fetch and streams are built in).
export function streamResponse(chunks, { status = 200, keepOpen = false, signal } = {}) {
  const enc = new TextEncoder()
  const body = new ReadableStream({
    async start(controller) {
      signal?.addEventListener('abort', () => controller.error(Object.assign(new Error('aborted'), { name: 'AbortError' })))
      for (const c of chunks) {
        await new Promise((r) => setTimeout(r, 5))
        controller.enqueue(enc.encode(c))
      }
      if (!keepOpen) controller.close()
    },
  })
  return new Response(body, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

export const jsonResponse = (data, status = 200) => new Response(JSON.stringify(status < 400 ? { success: true, data } : { success: false, ...data }), { status, headers: { 'Content-Type': 'application/json' } })

export const until = async (fn, ms = 2000) => {
  const end = Date.now() + ms
  while (Date.now() < end) {
    const v = fn()
    if (v) return v
    await new Promise((r) => setTimeout(r, 10))
  }
  return fn()
}

/** fetch() with a tiny cookie jar, so each "browser" keeps its own httpOnly refresh cookie like a real one. */
export function browserFetch() {
  let jar = ''
  const fetchImpl = async (url, options = {}) => {
    const res = await fetch(url, { ...options, headers: { ...options.headers, ...(jar ? { Cookie: jar } : {}) } })
    for (const c of res.headers.getSetCookie?.() ?? []) {
      const [pair] = c.split(';')
      jar = /Max-Age=0/i.test(c) ? '' : pair
    }
    return res
  }
  return fetchImpl
}
