/** Session cache of attachment *metadata* (not file bytes).
 *
 * Journal load seeds every owner from GET /api/attachments (SQLite only).
 * Opening a quest then paints instantly; WebDAV Stat runs once per owner
 * in the background so `available` / `source_updated` can fill in later.
 */

function key(ownerType, ownerId) {
  return `${ownerType}:${ownerId}`
}

function asIdList(rows) {
  return (rows || []).map((row) => row.id).join(',')
}

/** @type {Map<string, { items: any[], probed: boolean }>} */
const cache = new Map()
const liveListeners = new Set()

function notifyLive() {
  for (const fn of liveListeners) fn()
}

export function peekAttachmentList(ownerType, ownerId) {
  if (ownerId == null || ownerId === '') return null
  return cache.get(key(ownerType, ownerId)) ?? null
}

export function setAttachmentList(ownerType, ownerId, items, { probed = false } = {}) {
  cache.set(key(ownerType, ownerId), { items: items || [], probed })
}

function rowsFor(bucket, id) {
  if (!bucket || typeof bucket !== 'object') return []
  return bucket[id] || bucket[String(id)] || []
}

function keepLiveFlags(prevItems, incoming) {
  const prev = new Map((prevItems || []).map((row) => [row.id, row]))
  return (incoming || []).map((row) => {
    const old = prev.get(row.id)
    if (!old) return row
    return {
      ...row,
      available: old.available,
      source_updated: old.source_updated,
      last_modified: old.last_modified,
    }
  })
}

/** Seed (or refresh) every listed owner. Empty owners get `[]` so a click
 * does not look like a cache miss and refetch. */
export function seedAttachmentIndex(index, { questIds = [], questlineIds = [], noteIds = [] } = {}) {
  const byQuest = index?.quest ?? {}
  const byLine = index?.questline ?? {}
  const byNote = index?.note ?? {}
  const apply = (type, id, incoming) => {
    const k = key(type, id)
    const cur = cache.get(k)
    if (cur?.probed && asIdList(cur.items) === asIdList(incoming)) {
      cache.set(k, { probed: true, items: keepLiveFlags(cur.items, incoming) })
      return
    }
    cache.set(k, { items: incoming, probed: incoming.length === 0 })
  }
  for (const id of questIds) apply('quest', id, rowsFor(byQuest, id))
  for (const id of questlineIds) apply('questline', id, rowsFor(byLine, id))
  for (const id of noteIds) apply('note', id, rowsFor(byNote, id))
}

/** Drop live WebDAV flags so the open quest re-STATs after DAV flips. */
export function invalidateAttachmentLiveFlags() {
  for (const [k, entry] of cache) {
    if (entry?.items?.length) {
      cache.set(k, { items: entry.items, probed: false })
    }
  }
  notifyLive()
}

export function onAttachmentLiveInvalidate(fn) {
  liveListeners.add(fn)
  return () => liveListeners.delete(fn)
}
