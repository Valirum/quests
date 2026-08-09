const BASE = ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })
  if (res.status === 204) return null

  const text = await res.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error(
        res.ok
          ? `Ответ не JSON: ${text.slice(0, 120)}`
          : `HTTP ${res.status}: ${text.slice(0, 200)}`,
      )
    }
  }

  if (!res.ok) {
    const detail = data?.detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

export function listQuests(params = {}) {
  const q = new URLSearchParams()
  if (params.status) q.set('status', params.status)
  if (params.pinned != null) q.set('pinned', String(params.pinned))
  const qs = q.toString()
  return request(`/api/quests${qs ? `?${qs}` : ''}`)
}

/** Aggregated liveness: API + overlay/telegram heartbeats. */
export function fetchHealth() {
  return request('/api/health')
}

function quietQs(quiet) {
  return quiet ? '?quiet=1' : ''
}

/** Manual web edits are quiet by default (no overlay toasts). */
export function createQuest(payload, { quiet = true } = {}) {
  return request(`/api/quests${quietQs(quiet)}`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateQuest(id, payload, { quiet = true } = {}) {
  return request(`/api/quests/${id}${quietQs(quiet)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function updateQuestStep(questId, stepId, payload, { quiet = true } = {}) {
  return request(`/api/quests/${questId}/steps/${stepId}${quietQs(quiet)}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteQuest(id, { quiet = true } = {}) {
  return request(`/api/quests/${id}${quietQs(quiet)}`, { method: 'DELETE' })
}

export function listTemplates(params = {}) {
  const q = new URLSearchParams()
  if (params.enabled != null) q.set('enabled', String(params.enabled))
  const qs = q.toString()
  return request(`/api/templates${qs ? `?${qs}` : ''}`)
}

export function createTemplate(payload) {
  return request('/api/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateTemplate(id, payload) {
  return request(`/api/templates/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteTemplate(id) {
  return request(`/api/templates/${id}`, { method: 'DELETE' })
}

export function copyTemplate(id) {
  return request(`/api/templates/${id}/copy`, { method: 'POST' })
}

export function getHero() {
  return request('/api/hero')
}

export function listCategories() {
  return request('/api/categories')
}

export function listQuestlines() {
  return request('/api/questlines')
}

export function createQuestline(payload) {
  return request('/api/questlines', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateQuestline(id, payload) {
  return request(`/api/questlines/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteQuestline(id) {
  return request(`/api/questlines/${id}`, { method: 'DELETE' })
}

/** Upload custom questline image (not added to built-in SVG pool). */
export async function uploadQuestlineIcon(id, file) {
  const body = new FormData()
  body.append('file', file)
  const res = await fetch(`/api/questlines/${id}/icon`, {
    method: 'POST',
    body,
  })
  const text = await res.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      throw new Error(res.ok ? `Ответ не JSON` : `HTTP ${res.status}`)
    }
  }
  if (!res.ok) {
    const detail = data?.detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return data
}

export function clearQuestlineIcon(id) {
  return request(`/api/questlines/${id}/icon`, { method: 'DELETE' })
}

export const QUESTLINE_ICONS = ['document', 'flag', 'map', 'layers', 'target', 'scroll']

export const QUESTLINE_COLORS = [
  '#5a8a9a',
  '#8a8578',
  '#7a9e3a',
  '#6a7ab8',
  '#c47a20',
  '#c9a227',
  '#b54a3a',
  '#9a9a9a',
]

export const TEMPLATE_FREQS = ['daily', 'weekly']

export const TEMPLATE_EMIT_MODES = [
  { id: 'fixed', label: 'Обычный' },
  { id: 'surprise', label: 'Событие' },
]

export const WEEKDAY_LABELS = [
  { id: 0, label: 'Пн' },
  { id: 1, label: 'Вт' },
  { id: 2, label: 'Ср' },
  { id: 3, label: 'Чт' },
  { id: 4, label: 'Пт' },
  { id: 5, label: 'Сб' },
  { id: 6, label: 'Вс' },
]

export const QUEST_STATUSES = [
  'active',
  'delayed',
  'completed',
  'failed',
  'archived',
]

/** @type {Record<string, string>} */
export const QUEST_STATUS_LABELS = {
  active: 'активен',
  delayed: 'отложен',
  completed: 'выполнен',
  failed: 'провален',
  archived: 'архив',
}

/** @type {Record<string, string>} */
export const TEMPLATE_FREQ_LABELS = {
  daily: 'ежедневно',
  weekly: 'еженедельно',
}

/** @type {{ id: string, label: string }[]} */
export const QUEST_SIGNIFICANCES = [
  { id: 'common', label: 'обычное' },
  { id: 'uncommon', label: 'необычное' },
  { id: 'epic', label: 'эпическое' },
  { id: 'legendary', label: 'легендарное' },
]
