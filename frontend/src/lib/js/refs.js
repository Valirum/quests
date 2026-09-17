/** Tokens agents already paste: note=12, quest=23, … */

export const REF_RE = /\b(note|quest|questline|step|attachment)=(\d+)\b/g

export const REF_KINDS = ['note', 'quest', 'questline', 'step', 'attachment']

/**
 * @param {string} text
 * @returns {{ kind: string, id: number }[]}
 */
export function parseRefs(text) {
  const seen = new Set()
  const out = []
  const src = String(text || '')
  for (const m of src.matchAll(REF_RE)) {
    const kind = m[1]
    const id = Number(m[2])
    const key = `${kind}=${id}`
    if (!id || seen.has(key)) continue
    seen.add(key)
    out.push({ kind, id })
  }
  return out
}

/** @param {string} kind @param {number} id */
export function refHref(kind, id) {
  return `?${kind}=${id}`
}

/** @param {string} href */
export function parseRefHref(href) {
  try {
    const u = new URL(href, 'http://local')
    for (const kind of REF_KINDS) {
      const raw = u.searchParams.get(kind)
      if (!raw) continue
      const id = Number(raw)
      if (Number.isFinite(id) && id > 0) return { kind, id }
    }
  } catch {
    /* ignore */
  }
  return null
}
