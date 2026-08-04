<script>
  import {
    QUESTLINE_COLORS,
    QUESTLINE_ICONS,
    createQuestline,
    deleteQuestline,
    listCategories,
    updateQuestline,
  } from '../lib/api.js'
  import Icon from './Icon.svelte'
  import ConfirmModal from './ConfirmModal.svelte'

  /** @type {{ open: boolean, mode: 'create' | 'edit', line?: any, onClose: () => void, onSaved: (line: any) => void, onDeleted?: (id: number) => void }} */
  let {
    open = false,
    mode = 'create',
    line = null,
    onClose,
    onSaved,
    onDeleted,
  } = $props()

  let title = $state('')
  let description = $state('')
  /** Empty string = no category. */
  let categoryId = $state('')
  let color = $state('#9a9a9a')
  let icon = $state('document')
  /** @type {{ id: number, slug: string, label: string, color?: string }[]} */
  let categories = $state([])
  let saving = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let formError = $state('')

  let heading = $derived(mode === 'create' ? 'Новый квестлайн' : 'Редактировать квестлайн')

  function resetFromLine(row) {
    if (!row) {
      title = ''
      description = ''
      categoryId = ''
      color = '#9a9a9a'
      icon = 'document'
      return
    }
    title = row.title ?? ''
    description = row.description ?? ''
    categoryId = row.category_id != null ? String(row.category_id) : ''
    color = row.color || '#9a9a9a'
    icon = row.icon || 'document'
  }

  $effect(() => {
    if (open) {
      formError = ''
      saving = false
      deleting = false
      deleteConfirmOpen = false
      resetFromLine(mode === 'edit' ? line : null)
      listCategories()
        .then((rows) => {
          categories = Array.isArray(rows) ? rows : []
        })
        .catch(() => {
          categories = []
        })
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
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function onSubmit(event) {
    event.preventDefault()
    if (!title.trim()) {
      formError = 'Нужен title'
      return
    }
    saving = true
    formError = ''
    try {
      const payload = {
        title: title.trim(),
        description: description.trim(),
        category_id: categoryId === '' ? null : Number(categoryId),
        color: color || '#9a9a9a',
        icon: icon || 'document',
      }
      const saved =
        mode === 'create'
          ? await createQuestline(payload)
          : await updateQuestline(line.id, payload)
      onSaved(saved)
      onClose()
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  async function confirmDelete() {
    if (!line?.id || deleting) return
    deleting = true
    formError = ''
    try {
      await deleteQuestline(line.id)
      deleteConfirmOpen = false
      onDeleted?.(line.id)
      onClose()
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      deleting = false
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
      aria-labelledby="ql-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="ql-modal-title">{heading}</h2>
        <div class="modal__head-actions">
          {#if mode === 'edit'}
            <button
              type="button"
              class="icon-btn icon-btn--danger"
              aria-label="Удалить"
              disabled={deleting || saving}
              onclick={() => (deleteConfirmOpen = true)}
            >
              <Icon name="delete" />
            </button>
          {/if}
          <button type="button" class="icon-btn" aria-label="Закрыть" onclick={onClose}>
            <Icon name="close" />
          </button>
        </div>
      </header>

      {#if formError}
        <p class="modal__error">{formError}</p>
      {/if}

      <form class="modal__form" onsubmit={onSubmit}>
        <label class="field">
          <span class="label">Title</span>
          <input type="text" bind:value={title} required />
        </label>

        <label class="field">
          <span class="label">Description</span>
          <textarea rows="2" bind:value={description}></textarea>
        </label>

        <div class="field">
          <span class="label">Раздел</span>
          <div class="opt-slider opt-slider--wrap" role="radiogroup" aria-label="Раздел">
            <button
              type="button"
              class="opt-slider__opt opt-slider__opt--cat"
              class:opt-slider__opt--on={categoryId === ''}
              data-cat="none"
              role="radio"
              aria-checked={categoryId === ''}
              onclick={() => (categoryId = '')}
            >
              Нет
            </button>
            {#each categories as c}
              <button
                type="button"
                class="opt-slider__opt opt-slider__opt--cat"
                class:opt-slider__opt--on={categoryId === String(c.id)}
                style="--opt-color: {c.color || '#9a9a9a'}"
                role="radio"
                aria-checked={categoryId === String(c.id)}
                onclick={() => (categoryId = String(c.id))}
              >
                {c.label}
              </button>
            {/each}
          </div>
        </div>

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
                class:icon-pick--on={icon === name}
                role="radio"
                aria-checked={icon === name}
                aria-label={name}
                onclick={() => (icon = name)}
              >
                <Icon {name} size={16} />
              </button>
            {/each}
          </div>
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

<ConfirmModal
  open={deleteConfirmOpen}
  title="Удалить квестлайн?"
  message="Квесты останутся, но отвяжутся от линии."
  confirmLabel="Удалить"
  busy={deleting}
  onCancel={() => (deleteConfirmOpen = false)}
  onConfirm={confirmDelete}
/>

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
    max-height: min(90vh, 40rem);
    overflow: auto;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-md, 4px);
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

  .modal__head-actions {
    display: flex;
    gap: 0.25rem;
  }

  .icon-btn {
    display: inline-flex;
    border: 0;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.35rem;
    cursor: pointer;
  }

  .icon-btn--danger {
    color: var(--color-danger, #b54a3a);
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

  input,
  textarea {
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg, #121212);
    color: var(--color-fg, #e8e8e8);
    padding: 0.45rem 0.55rem;
    font: inherit;
  }

  .opt-slider {
    display: flex;
    flex-wrap: nowrap;
    gap: 0;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    overflow: hidden;
    background: var(--color-bg-muted, #242424);
  }

  .opt-slider--wrap {
    flex-wrap: wrap;
  }

  .opt-slider__opt {
    flex: 1 1 auto;
    border: 0;
    border-right: 1px solid var(--color-border, #333);
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.4rem 0.55rem;
    cursor: pointer;
    font: inherit;
    font-size: var(--text-sm, 0.875rem);
  }

  .opt-slider__opt:last-child {
    border-right: 0;
  }

  .opt-slider__opt--cat {
    color: var(--opt-color, var(--color-fg-muted, #9a9a9a));
    background: color-mix(in srgb, var(--opt-color, #9a9a9a) 12%, transparent);
  }

  .opt-slider__opt--cat[data-cat='none'] {
    color: var(--color-fg-muted, #9a9a9a);
    background: transparent;
  }

  .opt-slider__opt--cat.opt-slider__opt--on {
    color: color-mix(in srgb, var(--opt-color, #e8e8e8) 85%, #fff);
    background: color-mix(
      in srgb,
      var(--opt-color, #9a9a9a) 34%,
      var(--color-bg, #121212)
    );
  }

  .opt-slider__opt--cat[data-cat='none'].opt-slider__opt--on {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 80%, transparent);
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

  .modal__foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    padding: 0.4rem 0.65rem;
    cursor: pointer;
    font: inherit;
  }

  .btn--accent {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, var(--color-bg-muted, #242424));
    color: var(--color-accent, #c9a227);
  }

  .btn--ghost {
    border-color: transparent;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
  }
</style>
