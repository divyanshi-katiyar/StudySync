/**
 * Live updates client for GET /api/stream (Server-Sent Events).
 *
 * The browser's built-in EventSource cannot send an Authorization header, and putting the token in the URL would leak it into
 * logs, so the stream is read with fetch() and parsed here. The client reconnects by itself with a growing delay, refreshes the
 * access token when the server says it expired, and treats a silent connection (no data or heartbeat for `stallMs`) as dead.
 *
 * Status values: 'idle' (not started), 'connecting', 'live', 'reconnecting', 'offline' (waiting to retry).
 */
export function createRealtime({
  url,
  getToken,
  refreshToken,
  fetchImpl = (...args) => fetch(...args),
  backoffMs = [1000, 2000, 5000, 10000, 30000],
  stallMs = 45_000,
}) {
  let running = false
  let controller = null
  let status = 'idle'
  let wake = null
  const listeners = new Set()
  const statusListeners = new Set()

  const setStatus = (next) => {
    if (next === status) return
    status = next
    statusListeners.forEach((fn) => fn(status))
  }
  const emit = (event) => listeners.forEach((fn) => fn(event))
  const sleep = (ms) =>
    new Promise((resolve) => {
      const timer = setTimeout(resolve, ms)
      wake = () => {
        clearTimeout(timer)
        resolve()
      }
    })

  /** Parse one SSE message block ("id: 3\nevent: x\ndata: {...}") into { event, data }. */
  function parseBlock(block) {
    let event = 'message'
    const data = []
    for (const line of block.split('\n')) {
      if (!line || line.startsWith(':')) continue
      const colon = line.indexOf(':')
      const field = colon === -1 ? line : line.slice(0, colon)
      const value = colon === -1 ? '' : line.slice(colon + 1).replace(/^ /, '')
      if (field === 'event') event = value
      else if (field === 'data') data.push(value)
    }
    if (!data.length) return null
    try {
      return { event, data: JSON.parse(data.join('\n')) }
    } catch {
      return null
    }
  }

  async function readStream(body, signal) {
    const reader = body.getReader()
    signal.addEventListener('abort', () => reader.cancel().catch(() => {}), { once: true }) // stop() must end a read that is waiting for data
    const decoder = new TextDecoder()
    let buffer = ''
    let last = Date.now()
    const watchdog = setInterval(() => {
      if (Date.now() - last > stallMs) controller.abort()
    }, Math.min(5000, stallMs))
    try {
      let expired = false
      while (!signal.aborted) {
        const { value, done } = await reader.read()
        if (done) break
        last = Date.now()
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n')
        let split
        while ((split = buffer.indexOf('\n\n')) !== -1) {
          const message = parseBlock(buffer.slice(0, split))
          buffer = buffer.slice(split + 2)
          if (!message) continue
          if (message.event === 'ready') setStatus('live')
          else if (message.event === 'token-expired') expired = true
          else emit(message.event === 'notification' ? { type: 'notification', notification: message.data } : { type: message.event, ...message.data })
        }
      }
      return expired
    } finally {
      clearInterval(watchdog)
      reader.cancel().catch(() => {})
    }
  }

  async function loop() {
    let attempt = 0
    while (running) {
      setStatus(attempt === 0 ? 'connecting' : 'reconnecting')
      controller = new AbortController()
      let reconnectNow = false
      try {
        const token = await getToken()
        const res = await fetchImpl(url, { headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, credentials: 'include', signal: controller.signal })
        if (res.status === 401) {
          await refreshToken() // throws when the session is really over, which ends the loop below
          reconnectNow = true
        } else if (!res.ok || !res.body) {
          throw new Error(`stream refused: ${res.status}`)
        } else {
          attempt = 0
          if (await readStream(res.body, controller.signal)) {
            await refreshToken()
            reconnectNow = true
          }
        }
      } catch (err) {
        if (!running) return
        if (err?.status === 401) {
          running = false
          setStatus('idle')
          return
        }
      }
      if (!running) return
      if (reconnectNow) {
        attempt = 0
        continue
      }
      setStatus('offline')
      await sleep(backoffMs[Math.min(attempt, backoffMs.length - 1)])
      attempt += 1
    }
  }

  return {
    start() {
      if (running) return
      running = true
      loop()
    },
    stop() {
      running = false
      controller?.abort()
      wake?.()
      setStatus('idle')
    },
    subscribe(fn) {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
    onStatus(fn) {
      statusListeners.add(fn)
      return () => statusListeners.delete(fn)
    },
    get status() {
      return status
    },
  }
}
