import { renderMarkdown } from './markdown.js'

const MARGIN_MM = 15

/**
 * @param {{ id?: number | null, title?: string }} note
 * @param {'md' | 'pdf'} ext
 */
export function noteExportFilename(note, ext) {
  const id = note?.id != null ? String(note.id) : 'x'
  const raw = String(note?.title || 'note')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/[^\wЀ-ӿ-]+/g, '')
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
 * Self-contained HTML document for the note, styled for print (@page +
 * break-inside rules) — WeasyPrint lays this out itself, so there's no
 * pixel math to get right: it's a real paginator, not a screenshot cropper.
 * @param {{ id?: number | null, title?: string, description?: string }} note
 * @param {{ labels?: Record<string, string> }} [opts]
 */
function buildNotePdfHtml(note, opts = {}) {
  const title = String(note.title || '').trim() || `note=${note.id ?? ''}`
  const labels = opts.labels || {}
  const bodyHtml = renderMarkdown(note.description || '', { labels })
  const exportedAt = new Date().toLocaleString('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  })

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
  @page {
    size: A4;
    margin: ${MARGIN_MM}mm;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: #fff;
    color: #1a1a1a;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 12pt;
    line-height: 1.55;
  }
  .note-pdf__title {
    margin: 0 0 0.35em;
    font-family: system-ui, "Segoe UI", sans-serif;
    font-size: 1.75rem;
    font-weight: 700;
    line-height: 1.2;
    color: #111;
  }
  .note-pdf__meta {
    margin: 0 0 1.25em;
    font-family: system-ui, "Segoe UI", sans-serif;
    font-size: 0.75rem;
    color: #666;
  }
  .md > :first-child { margin-top: 0; }
  .md > :last-child { margin-bottom: 0; }
  .md p, .md ul, .md ol, .md .md-codeblock, .md table, .md blockquote {
    margin: 0 0 0.65em;
    break-inside: avoid-page;
  }
  .md h1, .md h2, .md h3, .md h4 {
    margin: 1.1em 0 0.4em;
    font-family: system-ui, "Segoe UI", sans-serif;
    font-weight: 700;
    line-height: 1.25;
    color: #111;
    break-after: avoid-page;
  }
  .md h1 { font-size: 1.45rem; }
  .md h2 { font-size: 1.25rem; }
  .md h3 { font-size: 1.1rem; }
  .md h4 { font-size: 1rem; }
  .md ul, .md ol { padding-left: 1.35em; }
  .md li { margin: 0.15em 0; break-inside: avoid-page; }
  .md a { color: #1a5fb4; text-decoration: underline; }
  .md blockquote {
    padding: 0.15em 0 0.15em 0.85em;
    border-left: 3px solid #ccc;
    color: #444;
  }
  .md hr { border: 0; border-top: 1px solid #ddd; margin: 1em 0; }
  .md code {
    font-family: ui-monospace, "Cascadia Code", "SF Mono", Menlo, monospace;
    font-size: 0.88em;
    padding: 0.08em 0.32em;
    border-radius: 3px;
    background: #f0f0f0;
  }
  .md .md-codeblock {
    position: relative;
    border-radius: 4px;
    background: #f4f4f4;
    border: 1px solid #e0e0e0;
  }
  .md .md-codeblock[data-lang]::before {
    content: attr(data-lang);
    position: absolute;
    top: 0.35em;
    left: 0.75em;
    font-family: system-ui, sans-serif;
    font-size: 0.68rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #888;
  }
  .md pre {
    margin: 0;
    padding: 0.75em 0.85em;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .md .md-codeblock[data-lang] pre {
    padding-top: 1.55em;
  }
  .md pre code {
    padding: 0;
    background: transparent;
    font-size: 0.82rem;
    line-height: 1.45;
    color: #222;
  }
  .md table { width: 100%; border-collapse: collapse; font-size: 0.92em; }
  .md tr { break-inside: avoid-page; }
  .md th, .md td { border: 1px solid #ddd; padding: 0.35em 0.5em; text-align: left; }
  .md th { background: #f6f6f6; }
  .md img { max-width: 100%; height: auto; }
  .md .hljs-comment, .md .hljs-quote { color: #6a737d; }
  .md .hljs-keyword, .md .hljs-selector-tag { color: #d73a49; }
  .md .hljs-string, .md .hljs-attr { color: #032f62; }
  .md .hljs-number, .md .hljs-literal { color: #005cc5; }
  .md .hljs-title, .md .hljs-section { color: #6f42c1; }
  .md .hljs-built_in, .md .hljs-type { color: #e36209; }
</style>
</head>
<body>
  <h1 class="note-pdf__title">${escapeHtml(title)}</h1>
  <p class="note-pdf__meta">Выгрузка: ${escapeHtml(exportedAt)}</p>
  <div class="md note-pdf__body">${bodyHtml || '<p style="color:#888">(пусто)</p>'}</div>
</body>
</html>`
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  })[c])
}

/**
 * Renders the note to PDF server-side (WeasyPrint — real HTML+CSS
 * pagination, real selectable text) and downloads the result.
 * @param {{ id?: number | null, title?: string, description?: string }} note
 * @param {{ labels?: Record<string, string> }} [opts]
 */
export async function downloadNotePdf(note, opts = {}) {
  if (!note) return
  const html = buildNotePdfHtml(note, opts)
  const filename = noteExportFilename(note, 'pdf')

  const resp = await fetch('/api/export/pdf', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ html, filename }),
  })
  if (!resp.ok) {
    const detail = await resp.text().catch(() => '')
    throw new Error(`PDF render failed (${resp.status}): ${detail.slice(0, 500)}`)
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.rel = 'noopener'
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
