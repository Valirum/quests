<script>
  import { updateQuestStep } from '../js/api.js'
  import Icon from '../ui/Icon.svelte'
  import MentionTextarea from '../ui/MentionTextarea.svelte'
  import { untrack } from 'svelte'

  /** @type {{
   *   open: boolean,
   *   questId?: number | null,
   *   step?: any | null,
   *   quests?: any[],
   *   questlines?: any[],
   *   notes?: any[],
   *   attachments?: any[],
   *   onClose: () => void,
   *   onSaved: (q: any) => void,
   * }} */
  let {
    open = false,
    questId = null,
    step = null,
    quests = [],
    questlines = [],
    notes = [],
    attachments = [],
    onClose,
    onSaved,
  } = $props()

  let title = $state('')
  let description = $state('')
  let progressCurrent = $state(0)
  let progressTotal = $state(1)
  let checkCommand = $state('')
  let checkInterval = $state('')
  let waitPrevious = $state(false)
  let runMode = $state('poll')
  let checkOpen = $state(false)
  let saving = $state(false)
  let formError = $state('')

  function resetFromStep(s) {
    if (!s) {
      title = ''
      description = ''
      progressCurrent = 0
      progressTotal = 1
      checkCommand = ''
      checkInterval = ''
      waitPrevious = false
      runMode = 'poll'
      checkOpen = false
      return
    }
    title = s.title ?? ''
    description = s.description ?? ''
    progressCurrent = s.progress_current ?? 0
    progressTotal = s.progress_total ?? 1
    checkCommand = s.check_command ?? ''
    checkInterval =
      s.check_interval_seconds != null ? String(s.check_interval_seconds) : ''
    waitPrevious = Boolean(s.wait_previous)
    runMode = s.run_mode === 'once' ? 'once' : 'poll'
    checkOpen = Boolean(String(s.check_command || '').trim())
  }

  $effect(() => {
    if (!open) return
    untrack(() => {
      formError = ''
      saving = false
      resetFromStep(step)
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
    if (!step?.id || questId == null || saving) return
    const trimmed = title.trim()
    if (!trimmed) {
      formError = 'Нужно название шага'
      return
    }
    saving = true
    formError = ''
    try {
      const cmd = String(checkCommand || '').trim()
      const intervalRaw = String(checkInterval ?? '').trim()
      const interval = intervalRaw === '' ? null : Math.max(15, Number(intervalRaw) || 15)
      const saved = await updateQuestStep(questId, step.id, {
        title: trimmed,
        description: description.trim(),
        progress_current: Math.max(0, Number(progressCurrent) || 0),
        progress_total: Math.max(1, Number(progressTotal) || 1),
        check_command: cmd || null,
        check_interval_seconds: cmd ? interval : null,
        wait_previous: cmd ? Boolean(waitPrevious) : false,
        run_mode: cmd && runMode === 'once' ? 'once' : 'poll',
      })
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
      aria-labelledby="step-modal-title"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="step-modal-title" class="modal__title">
          <Icon name="edit" size={18} />
          <span>Редактировать шаг</span>
        </h2>
        <button type="button" class="btn btn--ghost btn--icon" aria-label="Закрыть" onclick={onClose}>
          <Icon name="close" size={14} />
        </button>
      </header>

      {#if formError}
        <p class="modal__error">{formError}</p>
      {/if}

      <form class="modal__form" onsubmit={onSubmit}>
        <label class="field">
          <span class="label">Название</span>
          <input type="text" bind:value={title} required />
        </label>

        <div class="field">
          <span class="label">Описание</span>
          <MentionTextarea
            bind:value={description}
            {quests}
            {questlines}
            {notes}
            {attachments}
            rows={3}
            placeholder="@название — квест, заметка, файл, шаг, квестлайн"
          />
        </div>

        <div class="field field--progress">
          <span class="label">Прогресс</span>
          <div class="progress-row">
            <input type="number" min="0" title="текущее" bind:value={progressCurrent} />
            <span class="progress-row__slash">/</span>
            <input type="number" min="1" title="всего" bind:value={progressTotal} />
            <button
              type="button"
              class="btn btn--ghost btn--icon"
              class:btn--check-on={checkOpen}
              onclick={() => (checkOpen = !checkOpen)}
              aria-label="Команда проверки"
              title="Команда проверки"
            >
              <Icon name="terminal" size={14} />
            </button>
          </div>
        </div>

        {#if checkOpen}
          <div class="field">
            <span class="label">Авто-проверка</span>
            <div class="check-row">
              <input
                type="text"
                class="check-row__cmd"
                placeholder="команда: опрос (stdout → число) или разовый запуск"
                bind:value={checkCommand}
                spellcheck="false"
              />
              <input
                type="number"
                class="check-row__interval"
                min="15"
                step="15"
                placeholder="сек"
                title="Интервал опроса (сек, мин. 15)"
                bind:value={checkInterval}
                disabled={!String(checkCommand || '').trim() || runMode === 'once'}
              />
            </div>
            <div class="auto-opts">
              <label class="check">
                <input
                  type="checkbox"
                  bind:checked={waitPrevious}
                  disabled={!String(checkCommand || '').trim()}
                />
                ждать предыдущий
              </label>
              <div class="opt-slider" role="radiogroup" aria-label="Режим автошага">
                <button
                  type="button"
                  class="opt-slider__opt"
                  class:opt-slider__opt--on={runMode !== 'once'}
                  role="radio"
                  aria-checked={runMode !== 'once'}
                  disabled={!String(checkCommand || '').trim()}
                  onclick={() => (runMode = 'poll')}
                >
                  опрос
                </button>
                <button
                  type="button"
                  class="opt-slider__opt"
                  class:opt-slider__opt--on={runMode === 'once'}
                  role="radio"
                  aria-checked={runMode === 'once'}
                  disabled={!String(checkCommand || '').trim()}
                  onclick={() => (runMode = 'once')}
                >
                  разово
                </button>
              </div>
            </div>
          </div>
        {/if}

        <footer class="modal__foot">
          <button type="button" class="btn" onclick={onClose} disabled={saving}>Отмена</button>
          <button type="submit" class="btn btn--accent" disabled={saving}>
            {#if saving}
              …
            {:else}
              <Icon name="save" size={15} />
              <span>Сохранить</span>
            {/if}
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
    z-index: 45;
    display: grid;
    place-items: center;
    padding: var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
    backdrop-filter: blur(2px);
  }

  .modal {
    width: min(32rem, 100%);
    max-height: min(90vh, 44rem);
    overflow: auto;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 16px 48px color-mix(in srgb, #000 45%, transparent);
    font-family: var(--font-ui, sans-serif);
  }

  .modal__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
  }

  .modal__title {
    display: inline-flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
    font-size: var(--text-lg, 1.1rem);
    font-weight: 600;
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

  .progress-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .progress-row input[type='number'] {
    width: 4rem;
  }

  .progress-row__slash {
    color: var(--color-fg-muted, #9a9a9a);
  }

  .check-row {
    display: grid;
    grid-template-columns: 1fr 4.5rem;
    gap: 0.5rem;
  }

  .check-row__cmd {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
  }

  .auto-opts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
    margin-top: 0.35rem;
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    margin: 0;
    font-size: var(--text-sm, 0.875rem);
  }

  .opt-slider {
    display: inline-flex;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    overflow: hidden;
  }

  .opt-slider__opt {
    border: 0;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.35rem 0.65rem;
    cursor: pointer;
    font: inherit;
  }

  .opt-slider__opt--on {
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
  }

  .opt-slider__opt:disabled {
    opacity: 0.45;
    cursor: not-allowed;
  }

  .btn--check-on {
    color: var(--color-accent, #c9a227);
  }

  .modal__foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    padding-top: 0.25rem;
  }
</style>
