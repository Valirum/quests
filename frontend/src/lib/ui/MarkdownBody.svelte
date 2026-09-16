<script>
  import { renderMarkdown } from '../js/markdown.js'

  /** @type {{ source?: string, class?: string }} */
  let { source = '', class: className = '' } = $props()

  let html = $derived(renderMarkdown(source))
</script>

{#if html}
  <div class={['md', className]}>{@html html}</div>
{/if}
