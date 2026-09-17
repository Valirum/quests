<script>
  import { renderMarkdown } from '../js/markdown.js'
  import { parseRefHref } from '../js/refs.js'

  /** @type {{
   *   source?: string,
   *   class?: string,
   *   labels?: Record<string, string>,
   *   onRef?: (kind: string, id: number) => void,
   * }} */
  let {
    source = '',
    class: className = '',
    labels = {},
    onRef,
  } = $props()

  let html = $derived(renderMarkdown(source, { labels }))

  function onClick(event) {
    const a = event.target instanceof Element ? event.target.closest('a') : null
    if (!a) return
    const href = a.getAttribute('href') || ''
    const ref = parseRefHref(href)
    if (!ref) return
    event.preventDefault()
    onRef?.(ref.kind, ref.id)
  }
</script>

{#if html}
  <div class={['md', className]} onclick={onClick}>{@html html}</div>
{/if}
