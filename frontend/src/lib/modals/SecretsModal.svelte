<script>
  import {
    listTemplates,
    listTemplateSecrets,
    setTemplateSecret,
    deleteTemplateSecret,
  } from '../js/api.js'
  import Icon from '../ui/Icon.svelte'
  import ModalShell from './ModalShell.svelte'
  import ModalHead from './ModalHead.svelte'
  import { untrack } from 'svelte'

  /** Standalone secrets manager — GitHub-style: names are visible, values
   * never are, only add/overwrite/delete. Scoped to templates today (the
   * only owner emit_pool_command has), but kept as its own modal rather
   * than a TemplatesModal subsection since secrets may outgrow templates
   * later.
   * @type {{ open: boolean, onClose: () => void }} */
  let { open = false, onClose } = $props()

  let loading = $state(false)
  let error = $state('')
  let templates = $state(/** @type {any[]} */ ([]))
  let templateId = $state(/** @type {number | null} */ (null))

  let keys = $state(/** @type {string[]} */ ([]))
  let keysLoading = $state(false)
  let keysError = $state('')

  let newKey = $state('')
  let newValue = $state('')
  let saving = $state(false)

  /** key being overwritten inline, or null */
  let editingKey = $state(/** @type {string | null} */ (null))
  let editValue = $state('')

  const KEY_PATTERN = /^[A-Za-z_][A-Za-z0-9_]*$/

  let selectedTemplate = $derived(templates.find((t) => t.id === templateId) ?? null)

  async function refreshTemplates() {
    loading = true
    error = ''
    try {
      templates = await listTemplates({})
      if (templateId == null && templates.length > 0) {
        templateId = templates[0].id
      }
    } catch (e) {
      error = e.message || String(e)
      templates = []
    } finally {
      loading = false
    }
  }

  /** Bumped on every refreshKeys() call so a slower, older request can't
   * clobber a newer one's result if responses arrive out of order (e.g. the
   * template-switch effect's own fetch racing an explicit post-save refresh). */
  let keysRequestSeq = 0

  async function refreshKeys() {
    if (templateId == null) {
      keys = []
      return
    }
    const seq = ++keysRequestSeq
    keysLoading = true
    keysError = ''
    try {
      const result = await listTemplateSecrets(templateId)
      if (seq !== keysRequestSeq) return
      keys = result
    } catch (e) {
      if (seq !== keysRequestSeq) return
      keysError = e.message || String(e)
      keys = []
    } finally {
      if (seq === keysRequestSeq) keysLoading = false
    }
  }

  // Reset on open — only track `open`.
  $effect(() => {
    if (!open) return
    untrack(() => {
      error = ''
      newKey = ''
      newValue = ''
      editingKey = null
      void refreshTemplates()
    })
  })

  // Reload keys whenever the selected template changes (including the
  // initial pick once templates load).
  $effect(() => {
    if (!open) return
    void templateId
    untrack(() => void refreshKeys())
  })

  async function onAdd(event) {
    event.preventDefault()
    if (templateId == null || saving) return
    const key = newKey.trim()
    if (!KEY_PATTERN.test(key)) {
      keysError = 'Имя ключа — как переменная окружения: [A-Za-z_][A-Za-z0-9_]*'
      return
    }
    if (!newValue) {
      keysError = 'Нужно значение'
      return
    }
    saving = true
    keysError = ''
    try {
      await setTemplateSecret(templateId, key, newValue)
      newKey = ''
      newValue = ''
      await refreshKeys()
    } catch (e) {
      keysError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  function startEdit(key) {
    editingKey = key
    editValue = ''
    keysError = ''
  }

  function cancelEdit() {
    editingKey = null
    editValue = ''
  }

  async function saveEdit(key) {
    if (templateId == null || saving) return
    if (!editValue) {
      keysError = 'Нужно значение'
      return
    }
    saving = true
    keysError = ''
    try {
      await setTemplateSecret(templateId, key, editValue)
      editingKey = null
      editValue = ''
      await refreshKeys()
    } catch (e) {
      keysError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  async function onDelete(key) {
    if (templateId == null || saving) return
    saving = true
    keysError = ''
    try {
      await deleteTemplateSecret(templateId, key)
      if (editingKey === key) editingKey = null
      await refreshKeys()
    } catch (e) {
      keysError = e.message || String(e)
    } finally {
      saving = false
    }
  }
</script>

<ModalShell {open} {onClose} labelledby="secrets-modal-title" zIndex={40} maxWidth="30rem">
  <ModalHead id="secrets-modal-title" title="Секреты" icon="key" {onClose} />

  <div class="modal__body">
    {#if loading}
      <p class="hint">Загрузка…</p>
    {:else if error}
      <p class="modal__error">{error}</p>
    {:else if templates.length === 0}
      <p class="hint">Шаблонов нет — секретам пока некуда принадлежать.</p>
    {:else}
      <label class="field">
        <span class="label">Шаблон</span>
        <select bind:value={templateId}>
          {#each templates as t}
            <option value={t.id}>{t.title}</option>
          {/each}
        </select>
      </label>

      {#if keysError}
        <p class="modal__error">{keysError}</p>
      {/if}

      {#if keysLoading}
        <p class="hint">Загрузка ключей…</p>
      {:else}
        <ul class="secrets-list">
          {#each keys as key (key)}
            <li class="secret-row">
              <code class="secret-row__key">{key}</code>
              {#if editingKey === key}
                <input
                  type="password"
                  class="secret-row__input"
                  placeholder="новое значение"
                  bind:value={editValue}
                  autocomplete="off"
                />
                <button type="button" class="btn btn--ghost btn--icon" aria-label="Сохранить" onclick={() => saveEdit(key)} disabled={saving}>
                  <Icon name="checkmark" size={14} />
                </button>
                <button type="button" class="btn btn--ghost btn--icon" aria-label="Отмена" onclick={cancelEdit} disabled={saving}>
                  <Icon name="close" size={14} />
                </button>
              {:else}
                <span class="secret-row__value" aria-hidden="true">••••••••</span>
                <button type="button" class="btn btn--ghost btn--icon" aria-label="Изменить" onclick={() => startEdit(key)} disabled={saving}>
                  <Icon name="edit" size={14} />
                </button>
                <button type="button" class="btn btn--ghost btn--icon" aria-label="Удалить" onclick={() => onDelete(key)} disabled={saving}>
                  <Icon name="delete" size={14} />
                </button>
              {/if}
            </li>
          {:else}
            <li class="hint">Секретов не заведено.</li>
          {/each}
        </ul>
      {/if}

      <form class="add-row" onsubmit={onAdd}>
        <input
          type="text"
          class="add-row__key"
          placeholder="ИМЯ_КЛЮЧА"
          bind:value={newKey}
          spellcheck="false"
          autocomplete="off"
        />
        <input
          type="password"
          class="add-row__value"
          placeholder="значение"
          bind:value={newValue}
          autocomplete="off"
        />
        <button type="submit" class="btn btn--accent" disabled={saving}>
          <Icon name="add" size={14} />
          <span class="btn__text">Добавить</span>
        </button>
      </form>

      <p class="hint">
        Значения хранятся как есть (сервер — доверенная граница) и попадают в
        окружение скрипта только в момент запуска. Ни один инструмент
        (включая этот список) их обратно не показывает — только имена.
      </p>
    {/if}
  </div>
</ModalShell>

<style>

  .secrets-list {
    display: grid;
    gap: 0.4rem;
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .secret-row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.5rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
  }

  .secret-row__key {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm, 0.875rem);
  }

  .secret-row__value {
    flex: 1;
    color: var(--color-fg-subtle, #6e6e6e);
    letter-spacing: 0.15em;
  }

  .secret-row__input {
    flex: 1;
    min-width: 0;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
  }

  .add-row {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 0.5rem;
  }

  .add-row__key {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm, 0.875rem);
  }

</style>
