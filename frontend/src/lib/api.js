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

export function createQuest(payload) {
  return request('/api/quests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateQuest(id, payload) {
  return request(`/api/quests/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function updateQuestStep(questId, stepId, payload) {
  return request(`/api/quests/${questId}/steps/${stepId}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  })
}

export function deleteQuest(id) {
  return request(`/api/quests/${id}`, { method: 'DELETE' })
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

/** @type {{ id: string, label: string }[]} */
export const QUEST_SIGNIFICANCES = [
  { id: 'common', label: 'обычное' },
  { id: 'uncommon', label: 'необычное' },
  { id: 'epic', label: 'эпическое' },
  { id: 'legendary', label: 'легендарное' },
]
