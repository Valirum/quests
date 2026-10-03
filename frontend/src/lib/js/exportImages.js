const IMG_TAG_RE = /<img\b[^>]*?\bsrc="\/api\/attachments\/(\d+)\/image"[^>]*>/g

/** @param {Blob} blob @returns {Promise<string>} */
function blobToDataUri(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(blob)
  })
}

/**
 * The PDF is rendered server-side from the HTML we post, so a relative
 * `/api/attachments/N/image` can't resolve there. Fetch each attachment image
 * (with the page's own session) and embed it as a data: URI; an image that
 * can't be fetched becomes the same "недоступно" marker as in the journal.
 * @param {string} html
 * @returns {Promise<string>}
 */
export async function inlineAttachmentImages(html) {
  const ids = [...new Set([...html.matchAll(IMG_TAG_RE)].map((m) => m[1]))]
  if (!ids.length) return html
  /** @type {Map<string, string>} */
  const uris = new Map()
  await Promise.all(
    ids.map(async (id) => {
      try {
        const res = await fetch(`/api/attachments/${id}/image`, { credentials: 'same-origin' })
        if (!res.ok) return
        uris.set(id, await blobToDataUri(await res.blob()))
      } catch {
        /* falls through to the placeholder */
      }
    }),
  )
  return html.replace(IMG_TAG_RE, (tag, id) => {
    const uri = uris.get(id)
    if (uri) return tag.replace(`/api/attachments/${id}/image`, uri)
    return `<span class="md-img-missing">▢ вложение недоступно (attachment=${id})</span>`
  })
}
