<script>
  /**
   * @typedef {{ id: string, label?: string, danger?: boolean, sep?: boolean }} CtxItem
   * @type {{ open: boolean, x: number, y: number, items: CtxItem[], onSelect: (id: string) => void, onClose: () => void }}
   */
  let { open = false, x = 0, y = 0, items = [], onSelect, onClose } = $props()

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    const onPointer = (event) => {
      const el = event.target
      if (el instanceof Element && el.closest('.ctx-menu')) return
      onClose()
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('pointerdown', onPointer, true)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('pointerdown', onPointer, true)
    }
  })
</script>

{#if open}
  <div
    class="ctx-menu"
    style="left: {x}px; top: {y}px"
    role="menu"
  >
    {#each items as item (item.id)}
      {#if item.sep}
        <div class="ctx-menu__sep" role="separator"></div>
      {:else}
        <button
          type="button"
          class="ctx-menu__item"
          class:ctx-menu__item--danger={item.danger}
          role="menuitem"
          onclick={() => {
            onSelect(item.id)
            onClose()
          }}
        >
          {item.label}
        </button>
      {/if}
    {/each}
  </div>
{/if}

<style>
  .ctx-menu {
    position: fixed;
    z-index: 80;
    min-width: 11.5rem;
    padding: 0.25rem;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 10px 28px color-mix(in srgb, #000 40%, transparent);
  }

  .ctx-menu__item {
    display: block;
    width: 100%;
    border: 0;
    background: transparent;
    color: var(--color-fg, #e8e8e8);
    text-align: left;
    padding: 0.4rem 0.55rem;
    font: inherit;
    font-size: var(--text-sm, 0.875rem);
    cursor: pointer;
    border-radius: var(--radius-md, 4px);
  }

  .ctx-menu__item:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .ctx-menu__item--danger {
    color: var(--color-danger, #b54a3a);
  }

  .ctx-menu__item--danger:hover {
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 14%, transparent);
  }

  .ctx-menu__sep {
    height: 1px;
    margin: 0.3rem 0.35rem;
    background: var(--color-border, #333);
  }
</style>
