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

export const QUEST_STATUSES = [
  'active',
  'delayed',
  'completed',
  'failed',
  'archived',
]
