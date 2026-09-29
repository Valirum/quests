/**
 * Live updates via WebSocket. Reconnects with backoff.
 * onEvent receives parsed server messages ({ type, revision, action, quest_id }).
 */

// Server sends an app-level {type:'ping'} every 25s (see wsPingInterval in
// go/internal/httpapi/events.go) regardless of real traffic — so silence
// this long means the socket is dead, not just quiet.
const STALE_AFTER_MS = 70_000
const WATCHDOG_INTERVAL_MS = 10_000

export function subscribeQuestEvents(onEvent, { onStatus } = {}) {
  let stopped = false
  let socket = null
  let attempt = 0
  let timer = null
  let watchdog = null
  let lastMessageAt = 0

  const wsUrl = () => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${proto}//${location.host}/ws`
  }

  const setStatus = (status) => {
    if (onStatus) onStatus(status)
  }

  const schedule = () => {
    if (stopped) return
    const delay = Math.min(8000, 500 * 2 ** attempt)
    attempt += 1
    timer = setTimeout(connect, delay)
  }

  const connect = () => {
    if (stopped) return
    setStatus('connecting')
    socket = new WebSocket(wsUrl())

    socket.addEventListener('open', () => {
      attempt = 0
      lastMessageAt = Date.now()
      setStatus('live')
    })

    socket.addEventListener('message', (ev) => {
      lastMessageAt = Date.now()
      try {
        const data = JSON.parse(ev.data)
        if (data?.type === 'ping') {
          try {
            socket?.send('pong')
          } catch {
            /* ignore */
          }
          return
        }
        onEvent(data)
      } catch {
        /* ignore malformed */
      }
    })

    socket.addEventListener('close', () => {
      setStatus('reconnect')
      schedule()
    })

    socket.addEventListener('error', () => {
      socket?.close()
    })
  }

  /** readyState can stay OPEN forever on a half-open ("zombie") connection —
   * e.g. after a laptop sleep/wake or a network switch that never delivers
   * a close frame. The server-side ping is our only reliable heartbeat:
   * if nothing (not even a ping) arrived recently, the socket is dead —
   * force-close it so the existing reconnect logic takes over. */
  const checkStale = () => {
    if (stopped || !socket || socket.readyState !== WebSocket.OPEN) return
    if (Date.now() - lastMessageAt > STALE_AFTER_MS) {
      try {
        socket.close()
      } catch {
        /* ignore */
      }
    }
  }

  const hardClose = () => {
    stopped = true
    if (timer) clearTimeout(timer)
    if (watchdog) clearInterval(watchdog)
    try {
      socket?.close()
    } catch {
      /* ignore */
    }
    socket = null
    setStatus('off')
  }

  // Drop the socket on unload so the server doesn't keep a zombie client
  // (zombies made the overlay think a tab was still open → no new tab, no UI).
  const onPageHide = (ev) => {
    if (ev && ev.persisted) {
      try {
        socket?.close()
      } catch {
        /* ignore */
      }
      return
    }
    hardClose()
  }
  window.addEventListener('pagehide', onPageHide)
  window.addEventListener('beforeunload', onPageHide)

  connect()
  watchdog = setInterval(checkStale, WATCHDOG_INTERVAL_MS)

  return () => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('beforeunload', onPageHide)
    hardClose()
  }
}
