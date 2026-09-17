<script>
  import {
    QUESTLINE_COLORS,
    QUESTLINE_ICONS,
    clearNoteIcon,
    updateNote,
    uploadNoteIcon,
  } from '../js/api.js'
  import Icon from '../ui/Icon.svelte'
  import QuestlineIcon from '../ui/QuestlineIcon.svelte'
  import { untrack } from 'svelte'

  /** @type {{ open: boolean, note?: any | null, onClose: () => void, onSaved: (row: any) => void }} */
  let { open = false, note = null, onClose, onSaved } = $props()

  let color = $state('#9a9a9a')
  let icon = $state('document')
  let iconUrl = $state(/** @type {string | null} */ (null))
  let pendingFile = $state(/** @type {File | null} */ (null))
  let pendingPreview = $state(/** @type {string | null} */ (null))
  let clearCustom = $state(false)
  let saving = $state(false)
  let formError = $state('')
  let fileInput = $state(/** @type {HTMLInputElement | null} */ (null))

  let previewUrl = $derived(pendingPreview || (!clearCustom ? iconUrl : null))
  let title = $derived(note?.title?.trim() ? note.title : `note=${note?.id ?? ''}`)

  function revokePendingPreview() {
    if (pendingPreview) URL.revokeObjectURL(pendingPreview)
    pendingPreview = null
  }

  function resetFromNote(row) {
    revokePendingPreview()
    pendingFile = null
    clearCustom = false
    if (!row) {
      color = '#9a9a9a'
      icon = 'document'
      iconUrl = null
      return
    }
    color = row.color || '#9a9a9a'
    icon = row.icon || 'document'
    iconUrl = row.icon_url || null
  }

  function pickBuiltin(name) {
    icon = name
    clearCustom = true
    pendingFile = null
    revokePendingPreview()
  }

  function onFileChange(event) {
    const input = /** @type {HTMLInputElement} */ (event.currentTarget)
    const file = input.files?.[0] || null
    input.value = ''
    if (!file) return
    revokePendingPreview()
    pendingFile = file
    pendingPreview = URL.createObjectURL(file)
    clearCustom = false
  }

  function removeCustom() {
    pendingFile = null
    revokePendingPreview()
    clearCustom = true
  }

  $effect(() => {
    if (!open) return
    untrack(() => {
      formError = ''
      saving = false
      resetFromNote(note)
    })
  })

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function onSubmit(event) {
    event.preventDefault()
    if (!note?.id || saving) return
    saving = true
    formError = ''
    try {
      let saved = await updateNote(note.id, {
        color: color || '#9a9a9a',
        icon: icon || 'document',
      })
      if (pendingFile) {
        saved = await uploadNoteIcon(note.id, pendingFile)
      } else if (clearCustom && iconUrl) {
        saved = await clearNoteIcon(note.id)
      }
      onSaved(saved)
      onClose()
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  function onBackdrop(event) {
    if (event.target === event.currentTarget) onClose()
  }
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdrop}>
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="note-icon-title"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="note-icon-title">Иконка — {title}</h2>
        <button type="button" class="icon-btn" aria-label="Закрыть" onclick={onClose}>
          <Icon name="close" size={18} />
        </button>
      </header>
      {#if formError}
        <p class="modal__error">{formError}</p>
      {/if}
      <form class="modal__form" onsubmit={onSubmit}>
        <div class="field">
          <span class="label">Цвет</span>
          <div class="swatches" role="radiogroup" aria-label="Цвет">
            {#each QUESTLINE_COLORS as c}
              <button
                type="button"
                class="swatch"
                class:swatch--on={color === c}
                style="--swatch: {c}"
                role="radio"
                aria-checked={color === c}
                aria-label={c}
                onclick={() => (color = c)}
              ></button>
            {/each}
          </div>
          <input class="color-hex" type="text" bind:value={color} maxlength="16" />
        </div>

        <div class="field">
          <span class="label">Иконка</span>
          <div class="icon-picker" role="radiogroup" aria-label="Иконка">
            {#each QUESTLINE_ICONS as name}
              <button
                type="button"
                class="icon-pick"
                class:icon-pick--on={!previewUrl && icon === name}
                role="radio"
                aria-checked={!previewUrl && icon === name}
                aria-label={name}
                onclick={() => pickBuiltin(name)}
              >
                <Icon {name} size={16} />
              </button>
            {/each}
          </div>
          <div class="icon-custom">
            {#if previewUrl}
              <span class="icon-custom__preview" style="--line-color: {color}">
                <QuestlineIcon iconUrl={previewUrl} size="md" />
              </span>
              <button type="button" class="btn btn--ghost" onclick={removeCustom}>
                Убрать свою
              </button>
            {/if}
            <button type="button" class="btn" onclick={() => fileInput?.click()}>Загрузить…</button>
            <input
              bind:this={fileInput}
              class="icon-custom__file"
              type="file"
              accept="image/png,image/jpeg,image/webp,image/gif,image/svg+xml"
              onchange={onFileChange}
            />
          </div>
          <p class="hint">Своя иконка только у этой заметки, в общий пул SVG не попадает.</p>
        </div>

        <footer class="modal__foot">
          <button type="button" class="btn btn--ghost" onclick={onClose}>Отмена</button>
          <button type="submit" class="btn btn--accent" disabled={saving}>
            <Icon name="save" />
            {saving ? '…' : 'Сохранить'}
          </button>
        </footer>
      </form>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    place-items: center;
    padding: 1rem;
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
  }

  .modal {
    width: min(32rem, 100%);
    max-height: min(90vh, 36rem);
    overflow: auto;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 16px 48px color-mix(in srgb, #000 45%, transparent);
  }

  .modal__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .modal__head h2 {
    margin: 0;
    font-size: var(--text-lg, 1.1rem);
    color: var(--color-accent, #c9a227);
  }

  .icon-btn {
    display: inline-flex;
    border: 0;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.35rem;
    cursor: pointer;
  }

  .modal__error {
    margin: 0.75rem 1rem 0;
    color: var(--color-danger, #b54a3a);
  }

  .modal__form {
    display: grid;
    gap: 0.85rem;
    padding: 1rem;
  }

  .field {
    display: grid;
    gap: 0.35rem;
  }

  .label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .swatches {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .swatch {
    width: 1.35rem;
    height: 1.35rem;
    border: 2px solid transparent;
    border-radius: var(--radius-sm, 2px);
    background: var(--swatch);
    cursor: pointer;
    padding: 0;
  }

  .swatch--on {
    border-color: var(--color-fg, #e8e8e8);
  }

  .color-hex {
    max-width: 8rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg, #121212);
    color: var(--color-fg, #e8e8e8);
    padding: 0.45rem 0.55rem;
    font: inherit;
  }

  .icon-picker {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .icon-pick {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 2rem;
    height: 2rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg-muted, #9a9a9a);
    cursor: pointer;
  }

  .icon-pick--on {
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
    background: color-mix(in srgb, var(--color-accent, #c9a227) 16%, transparent);
  }

  .icon-custom {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .icon-custom__preview {
    display: inline-flex;
  }

  .icon-custom__file {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }

  .hint {
    margin: 0.4rem 0 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .modal__foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding-top: 0.25rem;
  }
</style>
