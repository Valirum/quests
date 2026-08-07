import { QUEST_SIGNIFICANCES } from './api.js'
import { formatRemaining, remainingFromDeadline, timerTone } from './time.js'

export const OPEN_STATUSES = new Set(['active', 'delayed'])

export function isQuestInactive(q) {
  return !OPEN_STATUSES.has(q?.status)
}

export function statusColor(status) {
  return `var(--color-status-${status}, var(--color-fg-muted, #9a9a9a))`
}

export function periodBadge(q) {
  if (!q?.template_id) return null
  const key = q.period_key || ''
  return key || 'цикл'
}

export function significanceLabel(q) {
  const id = q?.significance || 'common'
  return QUEST_SIGNIFICANCES.find((s) => s.id === id)?.label || 'обычное'
}

/** @param {any} q @param {number} nowMs */
export function questTimer(q, nowMs) {
  if (!q?.deadline_at) return null
  if (q.status === 'completed' || q.status === 'failed') return null
  const rem = remainingFromDeadline(q.deadline_at, nowMs)
  if (rem == null || rem <= 0) return null
  const tone = q.timer_tone || timerTone(rem, q.duration_seconds) || 'red'
  const remLabel = formatRemaining(rem)
  const durLabel =
    q.duration_seconds != null ? formatRemaining(q.duration_seconds) : null
  return {
    rem,
    label: remLabel,
    tone,
    detailLabel: durLabel ? `${remLabel} / ${durLabel}` : remLabel,
  }
}
