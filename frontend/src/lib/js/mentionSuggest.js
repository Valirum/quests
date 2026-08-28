const KIND_LABEL = {
  questline: 'квестлайн',
  quest: 'квест',
  step: 'шаг',
}

/**
 * Candidates for `@query` autocomplete in the assistant prompt — matches
 * against already-loaded quests/questlines (and their nested steps) by
 * title substring. Ranked: title starts with query > title contains query,
 * questlines/quests before their nested steps within each tier.
 */
export function matchMentions(query, { quests = [], questlines = [] } = {}, limit = 8) {
  const q = query.trim().toLowerCase()
  if (!q) return []

  const starts = []
  const contains = []

  function push(kind, id, title, hint) {
    const t = title.toLowerCase()
    const idx = t.indexOf(q)
    if (idx < 0) return
    const item = { kind, id, title, hint, label: KIND_LABEL[kind] }
    ;(idx === 0 ? starts : contains).push(item)
  }

  for (const line of questlines) push('questline', line.id, line.title || '')
  for (const quest of quests) {
    push('quest', quest.id, quest.title || '')
    for (const step of quest.steps || []) {
      push('step', step.id, step.title || '', quest.title)
    }
  }

  return [...starts, ...contains].slice(0, limit)
}

/** `@partial` token ending at `caret` in `text`, or null if caret isn't inside one. */
export function activeMentionToken(text, caret) {
  const upto = text.slice(0, caret)
  const m = upto.match(/@([^\s@]*)$/)
  if (!m) return null
  return { query: m[1], start: caret - m[0].length }
}

/** Replace the `@query` token with `kind=id ` (space after, cursor lands there). */
export function applyMention(text, token, item) {
  const tagEnd = token.start + 1 + token.query.length
  const before = text.slice(0, token.start)
  const after = text.slice(tagEnd)
  const tag = `${item.kind}=${item.id}`
  return { text: `${before}${tag} ${after}`, caret: before.length + tag.length + 1 }
}
