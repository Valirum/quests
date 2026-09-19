import { jsPDF } from 'jspdf'
import { renderMarkdown } from './markdown.js'

const MARGIN_MM = 14
const PAGE_W = 210
const PAGE_H = 297
const CONTENT_W_MM = PAGE_W - MARGIN_MM * 2
/** CSS width of offscreen render host — maps to CONTENT_W_MM in the PDF. */
const HOST_CSS_W = 720

/**
 * @param {{ id?: number | null, title?: string }} note
 * @param {'md' | 'pdf'} ext
 */
export function noteExportFilename(note, ext) {
  const id = note?.id != null ? String(note.id) : 'x'
  const raw = String(note?.title || 'note')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\w\u0400-\u04FF-]+/g, '')
    .slice(0, 48)
  return `note-${id}${raw ? `-${raw}` : ''}.${ext}`
}

/**
 * @param {{ id?: number | null, title?: string, description?: string }} note
 */
export function downloadNoteMarkdown(note) {
  if (!note) return
  const title = String(note.title || '').trim() || `note=${note.id ?? ''}`
  const body = String(note.description || '')
  const text = body.trimStart().startsWith('#')
    ? body
    : `# ${title}\n\n${body}`
  const blob = new Blob([text], { type: 'text/markdown;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = noteExportFilename(note, 'md')
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/**
 * PDF of rendered markdown (same pipeline as journal preview), via html2canvas + jsPDF.
 * html2canvas is already pulled by jspdf; no new heavy stack.
 *
 * @param {{ id?: number | null, title?: string, description?: string }} note
 * @param {{ labels?: Record<string, string> }} [opts]
 */
export async function downloadNotePdf(note, opts = {}) {
  if (!note) return
  const title = String(note.title || '').trim() || `note=${note.id ?? ''}`
  const labels = opts.labels || {}
  const bodyHtml = renderMarkdown(note.description || '', { labels })
  const exportedAt = new Date().toLocaleString('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  const host = document.createElement('div')
  host.setAttribute('data-note-pdf-host', '')
  host.setAttribute('aria-hidden', 'true')
  Object.assign(host.style, {
    position: 'fixed',
    left: '-12000px',
    top: '0',
    width: `${HOST_CSS_W}px`,
    padding: '0',
    margin: '0',
    background: '#ffffff',
    color: '#1a1a1a',
    zIndex: '-1',
    pointerEvents: 'none',
  })

  host.innerHTML = `
    <style>
      [data-note-pdf-sheet] {
        box-sizing: border-box;
        width: ${HOST_CSS_W}px;
        padding: 8px 4px 24px;
        background: #fff;
        color: #1a1a1a;
        font-family: Georgia, "Times New Roman", serif;
        font-size: 15px;
        line-height: 1.55;
        -webkit-font-smoothing: antialiased;
      }
      [data-note-pdf-sheet] * { box-sizing: border-box; }
      [data-note-pdf-sheet] .note-pdf__title {
        margin: 0 0 0.35em;
        font-family: system-ui, "Segoe UI", sans-serif;
        font-size: 1.75rem;
        font-weight: 700;
        line-height: 1.2;
        color: #111;
      }
      [data-note-pdf-sheet] .note-pdf__meta {
        margin: 0 0 1.25em;
        font-family: system-ui, "Segoe UI", sans-serif;
        font-size: 0.75rem;
        color: #666;
      }
      [data-note-pdf-sheet] .md { white-space: normal; }
      [data-note-pdf-sheet] .md > :first-child { margin-top: 0; }
      [data-note-pdf-sheet] .md > :last-child { margin-bottom: 0; }
      [data-note-pdf-sheet] .md p,
      [data-note-pdf-sheet] .md ul,
      [data-note-pdf-sheet] .md ol,
      [data-note-pdf-sheet] .md .md-codeblock {
        margin: 0 0 0.65em;
      }
      [data-note-pdf-sheet] .md h1,
      [data-note-pdf-sheet] .md h2,
      [data-note-pdf-sheet] .md h3,
      [data-note-pdf-sheet] .md h4 {
        margin: 1.1em 0 0.4em;
        font-family: system-ui, "Segoe UI", sans-serif;
        font-weight: 700;
        line-height: 1.25;
        color: #111;
      }
      [data-note-pdf-sheet] .md h1 { font-size: 1.45rem; }
      [data-note-pdf-sheet] .md h2 { font-size: 1.25rem; }
      [data-note-pdf-sheet] .md h3 { font-size: 1.1rem; }
      [data-note-pdf-sheet] .md h4 { font-size: 1rem; }
      [data-note-pdf-sheet] .md ul,
      [data-note-pdf-sheet] .md ol { padding-left: 1.35em; }
      [data-note-pdf-sheet] .md li { margin: 0.15em 0; }
      [data-note-pdf-sheet] .md a { color: #1a5fb4; text-decoration: underline; }
      [data-note-pdf-sheet] .md blockquote {
        margin: 0 0 0.65em;
        padding: 0.15em 0 0.15em 0.85em;
        border-left: 3px solid #ccc;
        color: #444;
      }
      [data-note-pdf-sheet] .md hr {
        border: 0;
        border-top: 1px solid #ddd;
        margin: 1em 0;
      }
      [data-note-pdf-sheet] .md code {
        font-family: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
        font-size: 0.88em;
        padding: 0.08em 0.32em;
        border-radius: 3px;
        background: #f0f0f0;
      }
      [data-note-pdf-sheet] .md .md-codeblock {
        position: relative;
        margin: 0 0 0.75em;
        border-radius: 4px;
        background: #f4f4f4;
        border: 1px solid #e0e0e0;
        overflow: hidden;
      }
      [data-note-pdf-sheet] .md .md-codeblock[data-lang]::before {
        content: attr(data-lang);
        display: block;
        padding: 0.35em 0.75em 0;
        font-family: system-ui, sans-serif;
        font-size: 0.68rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        color: #888;
      }
      [data-note-pdf-sheet] .md pre {
        margin: 0;
        padding: 0.75em 0.85em;
        overflow: auto;
      }
      [data-note-pdf-sheet] .md pre code {
        padding: 0;
        background: transparent;
        font-size: 0.82rem;
        line-height: 1.45;
        color: #222;
      }
      [data-note-pdf-sheet] .md table {
        width: 100%;
        border-collapse: collapse;
        margin: 0 0 0.75em;
        font-size: 0.92em;
      }
      [data-note-pdf-sheet] .md th,
      [data-note-pdf-sheet] .md td {
        border: 1px solid #ddd;
        padding: 0.35em 0.5em;
        text-align: left;
      }
      [data-note-pdf-sheet] .md th { background: #f6f6f6; }
      [data-note-pdf-sheet] .md img {
        max-width: 100%;
        height: auto;
      }
      [data-note-pdf-sheet] .md .hljs-comment,
      [data-note-pdf-sheet] .md .hljs-quote { color: #6a737d; }
      [data-note-pdf-sheet] .md .hljs-keyword,
      [data-note-pdf-sheet] .md .hljs-selector-tag { color: #d73a49; }
      [data-note-pdf-sheet] .md .hljs-string,
      [data-note-pdf-sheet] .md .hljs-attr { color: #032f62; }
      [data-note-pdf-sheet] .md .hljs-number,
      [data-note-pdf-sheet] .md .hljs-literal { color: #005cc5; }
      [data-note-pdf-sheet] .md .hljs-title,
      [data-note-pdf-sheet] .md .hljs-section { color: #6f42c1; }
      [data-note-pdf-sheet] .md .hljs-built_in,
      [data-note-pdf-sheet] .md .hljs-type { color: #e36209; }
    </style>
    <div data-note-pdf-sheet>
      <h1 class="note-pdf__title"></h1>
      <p class="note-pdf__meta"></p>
      <div class="md note-pdf__body"></div>
    </div>
  `

  const titleEl = host.querySelector('.note-pdf__title')
  const metaEl = host.querySelector('.note-pdf__meta')
  const bodyEl = host.querySelector('.note-pdf__body')
  if (titleEl) titleEl.textContent = title
  if (metaEl) metaEl.textContent = `Выгрузка: ${exportedAt}`
  if (bodyEl) {
    if (bodyHtml) bodyEl.innerHTML = bodyHtml
    else bodyEl.innerHTML = '<p style="color:#888">(пусто)</p>'
  }

  document.body.appendChild(host)
  try {
    if (document.fonts?.ready) {
      try {
        await document.fonts.ready
      } catch {
        /* ignore */
      }
    }
    // Let layout settle (images / highlight).
    await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))

    const sheet = host.querySelector('[data-note-pdf-sheet]')
    if (!sheet) throw new Error('pdf sheet missing')

    const { default: html2canvas } = await import('html2canvas')
    const canvas = await html2canvas(/** @type {HTMLElement} */ (sheet), {
      scale: 2,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
      windowWidth: HOST_CSS_W,
    })

    const doc = new jsPDF({ unit: 'mm', format: 'a4' })
    const pageContentH = PAGE_H - MARGIN_MM * 2
    const imgW = CONTENT_W_MM
    const fullImgH = (canvas.height * imgW) / canvas.width
    const pageSlicePx = Math.max(1, Math.floor((pageContentH / fullImgH) * canvas.height))
    const elementCuts = collectElementCutYs(/** @type {HTMLElement} */ (sheet), canvas)

    let y = 0
    let first = true
    while (y < canvas.height - 1) {
      const idealEnd = Math.min(y + pageSlicePx, canvas.height)
      const cut =
        idealEnd >= canvas.height
          ? canvas.height
          : findPageCut(canvas, y, idealEnd, elementCuts)
      const sliceH = Math.max(1, cut - y)

      const pageCanvas = document.createElement('canvas')
      pageCanvas.width = canvas.width
      pageCanvas.height = sliceH
      const ctx = pageCanvas.getContext('2d')
      if (!ctx) throw new Error('canvas unavailable')
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(0, 0, pageCanvas.width, pageCanvas.height)
      ctx.drawImage(canvas, 0, y, canvas.width, sliceH, 0, 0, canvas.width, sliceH)

      const sliceMm = (sliceH * imgW) / canvas.width
      if (!first) doc.addPage()
      first = false
      doc.addImage(
        pageCanvas.toDataURL('image/png'),
        'PNG',
        MARGIN_MM,
        MARGIN_MM,
        imgW,
        sliceMm,
      )
      y = cut
    }

    doc.save(noteExportFilename(note, 'pdf'))
  } finally {
    host.remove()
  }
}

/**
 * Bottoms of block-level nodes in canvas coords — preferred page breaks.
 * @param {HTMLElement} sheet
 * @param {HTMLCanvasElement} canvas
 */
function collectElementCutYs(sheet, canvas) {
  const sheetH = Math.max(1, sheet.offsetHeight)
  const scaleY = canvas.height / sheetH
  const sheetTop = sheet.getBoundingClientRect().top
  /** @type {number[]} */
  const cuts = []

  /** @param {Element | null} el */
  const addBottom = (el) => {
    if (!(el instanceof HTMLElement)) return
    const bottom = (el.getBoundingClientRect().bottom - sheetTop) * scaleY
    const y = Math.round(bottom)
    if (y > 0 && y < canvas.height) cuts.push(y)
  }

  addBottom(sheet.querySelector('.note-pdf__title'))
  addBottom(sheet.querySelector('.note-pdf__meta'))
  const body = sheet.querySelector('.note-pdf__body')
  if (body) {
    for (const child of body.children) {
      addBottom(child)
      if (child instanceof HTMLElement && child.children.length && child.offsetHeight > 80) {
        for (const nested of child.querySelectorAll(
          ':scope > li, :scope > p, :scope > pre, :scope > .md-codeblock',
        )) {
          addBottom(nested)
        }
      }
    }
  }
  cuts.push(canvas.height)
  return [...new Set(cuts)].sort((a, b) => a - b)
}

/**
 * Cut at or above idealEnd — block boundary first, else quietest pixel row (line gap).
 * @param {HTMLCanvasElement} canvas
 * @param {number} startY
 * @param {number} idealEnd
 * @param {number[]} elementCuts
 */
function findPageCut(canvas, startY, idealEnd, elementCuts) {
  if (idealEnd >= canvas.height - 1) return canvas.height

  const span = idealEnd - startY
  const minAdvance = Math.max(8, Math.floor(span * 0.35))
  const lo = startY + minAdvance
  const hi = idealEnd

  let bestEl = -1
  for (const c of elementCuts) {
    if (c <= startY + 4) continue
    if (c > hi) break
    if (c >= lo) bestEl = c
  }
  if (bestEl > startY) return bestEl

  const quiet = findQuietestRow(canvas, lo, hi)
  if (quiet != null && quiet > startY) return quiet

  return hi
}

/**
 * Most empty horizontal row in [lo, hi] — usually the gap between text lines.
 * @param {HTMLCanvasElement} canvas
 * @param {number} lo
 * @param {number} hi
 * @returns {number | null}
 */
function findQuietestRow(canvas, lo, hi) {
  if (hi <= lo) return null
  const ctx = canvas.getContext('2d', { willReadFrequently: true })
  if (!ctx) return null

  const w = canvas.width
  const stepX = Math.max(1, Math.floor(w / 160))
  const cols = Math.ceil(w / stepX)

  let bestY = hi
  let bestScore = Infinity

  for (let y = hi; y >= lo; y--) {
    const row = ctx.getImageData(0, y, w, 1).data
    let ink = 0
    for (let x = 0; x < w; x += stepX) {
      const i = x * 4
      ink += 255 - row[i] + (255 - row[i + 1]) + (255 - row[i + 2])
    }
    // Prefer emptier rows; slight bias toward keeping the page fuller (higher y).
    const score = ink / cols - (y - lo) * 0.02
    if (score < bestScore) {
      bestScore = score
      bestY = y
    }
  }

  return bestY
}
