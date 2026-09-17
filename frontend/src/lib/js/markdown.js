import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { REF_RE, refHref } from './refs.js'

marked.setOptions({ gfm: true, breaks: true })

const PURIFY_OPTS = {
  ALLOWED_TAGS: [
    'p',
    'br',
    'ul',
    'ol',
    'li',
    'strong',
    'em',
    'code',
    'pre',
    'a',
    'img',
    'h1',
    'h2',
    'h3',
    'h4',
    'blockquote',
    'hr',
    'table',
    'thead',
    'tbody',
    'tfoot',
    'tr',
    'th',
    'td',
  ],
  ALLOWED_ATTR: ['href', 'rel', 'target', 'src', 'alt', 'align'],
  ALLOW_DATA_ATTR: false,
}

let hooked = false

function ensureLinkHook() {
  if (hooked || typeof window === 'undefined') return
  hooked = true
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName === 'A') {
      const href = node.getAttribute('href') || ''
      if (href.startsWith('?') || href.startsWith('/')) {
        node.removeAttribute('target')
        node.removeAttribute('rel')
        return
      }
      node.setAttribute('target', '_blank')
      node.setAttribute('rel', 'noopener noreferrer')
    }
  })
}

function splitCode(src) {
  return String(src || '').split(/(```[\s\S]*?```|`[^`]+`)/)
}

/**
 * @param {string} source
 * @param {{ labels?: Record<string, string> }} [opts]
 */
function linkifyRefs(source, opts = {}) {
  const labels = opts.labels || {}
  const withMdLinks = splitCode(source)
    .map((part, i) => {
      if (i % 2 === 1) return part
      let chunk = part.replace(/\]\(attachment:(\d+)\)/g, (_, id) => `](?attachment=${id})`)
      chunk = chunk.replace(REF_RE, (full, kind, id) => {
        const label = labels[`${kind}:${id}`] || full
        return `[${label}](${refHref(kind, id)})`
      })
      return chunk
    })
    .join('')
  return withMdLinks
}

/** Render markdown to sanitized HTML. Journal refs become in-app `?kind=id` links. */
export function renderMarkdown(source, opts = {}) {
  const text = String(source ?? '')
  if (!text.trim()) return ''
  const dirty = marked.parse(linkifyRefs(text, opts), { async: false })
  if (typeof dirty !== 'string' || typeof window === 'undefined') return ''
  ensureLinkHook()
  return DOMPurify.sanitize(dirty, PURIFY_OPTS)
}
