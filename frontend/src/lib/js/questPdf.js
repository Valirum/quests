import { jsPDF } from 'jspdf'

const PAGE_W = 210
const PAGE_H = 297
const MARGIN = 16
const CONTENT_W = PAGE_W - MARGIN * 2
const LINE_H = 6.2
const TITLE_H = 9
const META_H = 5.5
const STEP_H = 6

/**
 * @param {any} quest
 * @returns {{ title: string, exportedAt: string, steps: { title: string, progress: string, done: boolean }[] }}
 */
export function buildQuestPdfPayload(quest) {
  const exportedAt = new Date().toLocaleString('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
  const steps = (quest?.steps || []).map((s) => {
    const cur = Number(s.progress_current) || 0
    const tot = Math.max(1, Number(s.progress_total) || 1)
    return {
      title: String(s.title || `step=${s.id}`),
      progress: `${cur}/${tot}`,
      done: Boolean(s.done) || cur >= tot,
    }
  })
  return {
    title: String(quest?.title || `quest=${quest?.id ?? ''}`),
    exportedAt,
    steps,
  }
}

function pdfFilename(quest) {
  const id = quest?.id != null ? String(quest.id) : 'x'
  const raw = String(quest?.title || 'quest')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u0400-\u04FF-]+/g, '')
    .slice(0, 48)
  return `quest-${id}${raw ? `-${raw}` : ''}.pdf`
}

/**
 * jsPDF core fonts lack Cyrillic — draw via canvas using system UI fonts.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} text
 * @param {number} maxWidth
 * @param {string} font
 */
function wrapLines(ctx, text, maxWidth, font) {
  ctx.font = font
  const words = String(text || '').split(/\s+/).filter(Boolean)
  if (!words.length) return ['']
  const lines = []
  let cur = words[0]
  for (let i = 1; i < words.length; i++) {
    const trial = `${cur} ${words[i]}`
    if (ctx.measureText(trial).width <= maxWidth) {
      cur = trial
    } else {
      lines.push(cur)
      cur = words[i]
    }
  }
  lines.push(cur)
  return lines
}

/**
 * Download a simple quest PDF (title, export time, step list with progress).
 * @param {any} quest
 */
export async function downloadQuestPdf(quest) {
  if (!quest) return
  const payload = buildQuestPdfPayload(quest)
  const doc = new jsPDF({ unit: 'mm', format: 'a4' })
  const scale = 3
  const cssW = CONTENT_W * scale * (96 / 25.4)
  const cssPageH = (PAGE_H - MARGIN * 2) * scale * (96 / 25.4)

  const canvas = document.createElement('canvas')
  canvas.width = Math.ceil(cssW)
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('canvas unavailable')

  const titleFont = `600 ${Math.round(18 * scale * 0.75)}px system-ui, "Segoe UI", sans-serif`
  const metaFont = `400 ${Math.round(12 * scale * 0.75)}px system-ui, "Segoe UI", sans-serif`
  const bodyFont = `400 ${Math.round(13 * scale * 0.75)}px system-ui, "Segoe UI", sans-serif`
  const pxPerMm = scale * (96 / 25.4)
  const titlePx = TITLE_H * pxPerMm
  const metaPx = META_H * pxPerMm
  const stepPx = STEP_H * pxPerMm
  const gapPx = 2.5 * pxPerMm

  /** @type {{ text: string, font: string, h: number, color: string }[]} */
  const blocks = []
  for (const line of wrapLines(ctx, payload.title, cssW, titleFont)) {
    blocks.push({ text: line, font: titleFont, h: titlePx, color: '#1a1a1a' })
  }
  blocks.push({
    text: `Выгрузка: ${payload.exportedAt}`,
    font: metaFont,
    h: metaPx,
    color: '#666666',
  })
  blocks.push({
    text: `Прогресс: ${payload.steps.filter((s) => s.done).length} / ${payload.steps.length || 0}`,
    font: metaFont,
    h: metaPx + gapPx,
    color: '#666666',
  })

  if (!payload.steps.length) {
    blocks.push({ text: 'Шагов нет', font: bodyFont, h: stepPx, color: '#444444' })
  } else {
    payload.steps.forEach((s, i) => {
      const mark = s.done ? '✓' : '○'
      const line = `${mark}  ${i + 1}. ${s.title}  (${s.progress})`
      for (const wrapped of wrapLines(ctx, line, cssW, bodyFont)) {
        blocks.push({
          text: wrapped,
          font: bodyFont,
          h: stepPx,
          color: s.done ? '#2a6b3c' : '#1a1a1a',
        })
      }
    })
  }

  let pageBlocks = /** @type {typeof blocks} */ ([])
  let used = 0
  let first = true

  const flush = () => {
    if (!pageBlocks.length) return
    const h = Math.max(1, Math.ceil(used))
    canvas.height = h
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, canvas.width, h)
    ctx.textBaseline = 'top'
    let y = 0
    for (const b of pageBlocks) {
      ctx.font = b.font
      ctx.fillStyle = b.color
      ctx.fillText(b.text, 0, y)
      y += b.h
    }
    if (!first) doc.addPage()
    first = false
    const imgH = (h / pxPerMm)
    doc.addImage(
      canvas.toDataURL('image/png'),
      'PNG',
      MARGIN,
      MARGIN,
      CONTENT_W,
      Math.min(imgH, PAGE_H - MARGIN * 2),
    )
    pageBlocks = []
    used = 0
  }

  for (const b of blocks) {
    if (used + b.h > cssPageH && pageBlocks.length) flush()
    pageBlocks.push(b)
    used += b.h
  }
  flush()

  doc.save(pdfFilename(quest))
}
