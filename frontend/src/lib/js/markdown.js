import { marked } from 'marked'
import DOMPurify from 'dompurify'

marked.setOptions({ gfm: true, breaks: true })

const PURIFY_OPTS = {
  ALLOWED_TAGS: ['p', 'br', 'ul', 'ol', 'li', 'strong', 'em', 'code', 'pre', 'a'],
  ALLOWED_ATTR: ['href', 'rel', 'target'],
  ALLOW_DATA_ATTR: false,
  ALLOWED_URI_REGEXP: /^(?:https?|mailto):/i,
}

let hooked = false

function ensureLinkHook() {
  if (hooked || typeof window === 'undefined') return
  hooked = true
  DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node.tagName !== 'A') return
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  })
}

/** Render quest/step description markdown to sanitized HTML. */
export function renderMarkdown(source) {
  const text = String(source ?? '')
  if (!text.trim()) return ''
  const dirty = marked.parse(text, { async: false })
  if (typeof dirty !== 'string' || typeof window === 'undefined') return ''
  ensureLinkHook()
  return DOMPurify.sanitize(dirty, PURIFY_OPTS)
}
