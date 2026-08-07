/**
 * Live updates via WebSocket. Reconnects with backoff.
 * onEvent receives parsed server messages ({ type, revision, action, quest_id }).
 */
export function subscribeQuestEvents(onEvent, { onStatus } = {}) {
  let stopped = false
  let socket = null
  let attempt = 0
  let timer = null

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
      setStatus('live')
    })

    socket.addEventListener('message', (ev) => {
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

  const hardClose = () => {
    stopped = true
    if (timer) clearTimeout(timer)
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

  return () => {
    window.removeEventListener('pagehide', onPageHide)
    window.removeEventListener('beforeunload', onPageHide)
    hardClose()
  }
}
