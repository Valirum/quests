<script>
  /** Shared backdrop + dialog + Escape-close wrapper used by every modal.
   * @type {{
   *   open: boolean,
   *   onClose: () => void,
   *   labelledby: string,
   *   zIndex?: number,
   *   maxWidth?: string,
   *   closeDisabled?: boolean,
   *   dialogClass?: string,
   *   children?: import('svelte').Snippet,
   * }} */
  let {
    open = false,
    onClose,
    labelledby,
    zIndex = 50,
    maxWidth = '32rem',
    closeDisabled = false,
    dialogClass = '',
    children,
  } = $props()

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        if (!closeDisabled) onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  })

  function onBackdrop(event) {
    if (closeDisabled) return
    if (event.target === event.currentTarget) onClose()
  }
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdrop} style:z-index={zIndex}>
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="modal {dialogClass}"
      role="dialog"
      aria-modal="true"
      aria-labelledby={labelledby}
      tabindex="-1"
      style:max-width={maxWidth}
      onclick={(e) => e.stopPropagation()}
    >
      {@render children?.()}
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    display: grid;
    place-items: center;
    padding: var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
    backdrop-filter: blur(2px);
  }

  .modal {
    width: 100%;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: color-mix(in srgb, var(--color-bg, #121212) 88%, var(--color-bg-raised, #1a1a1a));
    box-shadow: 0 16px 48px color-mix(in srgb, #000 45%, transparent);
    font-family: var(--font-ui, sans-serif);
  }
</style>
