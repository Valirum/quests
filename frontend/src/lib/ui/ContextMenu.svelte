<script>
  import { tick } from 'svelte'

  /**
   * @typedef {{ id: string, label?: string, danger?: boolean, sep?: boolean }} CtxItem
   * @type {{ open: boolean, x: number, y: number, items: CtxItem[], onSelect: (id: string) => void, onClose: () => void }}
   */
  let { open = false, x = 0, y = 0, items = [], onSelect, onClose } = $props()

  let menuEl = $state(/** @type {HTMLDivElement | null} */ (null))
  let posX = $state(0)
  let posY = $state(0)
  let placed = $state(false)

  const PAD = 8

  function place() {
    const el = menuEl
    if (!el) return
    const { width, height } = el.getBoundingClientRect()
    const vw = window.innerWidth
    const vh = window.innerHeight
    let left = x
    let top = y
    if (left + width > vw - PAD) left = x - width
    if (left < PAD) left = PAD
    if (left + width > vw - PAD) left = Math.max(PAD, vw - width - PAD)
    if (top + height > vh - PAD) top = y - height
    if (top < PAD) top = PAD
    if (top + height > vh - PAD) top = Math.max(PAD, vh - height - PAD)
    posX = left
    posY = top
    placed = true
  }

  $effect(() => {
    if (!open) {
      placed = false
      return
    }
    const ax = x
    const ay = y
    void items.length
    posX = ax
    posY = ay
    placed = false
    let cancelled = false
    tick().then(() => {
      if (cancelled) return
      if (!menuEl) {
        requestAnimationFrame(() => {
          if (!cancelled) place()
        })
        return
      }
      place()
    })
    const onResize = () => place()
    window.addEventListener('resize', onResize)
    return () => {
      cancelled = true
      window.removeEventListener('resize', onResize)
    }
  })

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
    bind:this={menuEl}
    class="ctx-menu"
    class:ctx-menu--placed={placed}
    style="left: {posX}px; top: {posY}px"
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
    max-height: calc(100vh - 16px);
    overflow-y: auto;
    padding: 0.25rem;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 10px 28px color-mix(in srgb, #000 40%, transparent);
    opacity: 0;
    visibility: hidden;
    pointer-events: none;
  }

  .ctx-menu--placed {
    opacity: 1;
    visibility: visible;
    pointer-events: auto;
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
