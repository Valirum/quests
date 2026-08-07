<script>
  import {
    QUEST_SIGNIFICANCES,
    QUEST_STATUSES,
    QUEST_STATUS_LABELS,
    createQuest,
    updateQuest,
    deleteQuest,
    listCategories,
    listQuestlines,
  } from '../lib/api.js'
  import {
    defaultLocalDeadlineParts,
    localInputToUtcIso,
    localTimeZone,
    toLocalInputValue,
  } from '../lib/time.js'
  import Icon from './Icon.svelte'
  import ConfirmModal from './ConfirmModal.svelte'

  /** @type {{ open: boolean, mode: 'create' | 'edit', quest?: any, defaults?: { questline_id?: number | null, category_id?: number | null }, onClose: () => void, onSaved: (q: any) => void, onDeleted?: (id: number) => void }} */
  let {
    open = false,
    mode = 'create',
    quest = null,
    defaults = null,
    onClose,
    onSaved,
    onDeleted,
  } = $props()

  let title = $state('')
  let description = $state('')
  let status = $state('active')
  let significance = $state('common')
  let pinned = $state(false)
  let sortOrder = $state(0)
  /** Empty string = no category. */
  let categoryId = $state('')
  /** Empty string = no questline. */
  let questlineId = $state('')
  /** @type {{ id: number, slug: string, label: string, color?: string }[]} */
  let categories = $state([])
  /** @type {{ id: number, title: string, category_id?: number | null, color?: string }[]} */
  let questlines = $state([])
  /** Local date YYYY-MM-DD + 24h clock (no native time picker — it follows OS 12h). */
  let deadlineDate = $state('')
  let deadlineHour = $state('12')
  let deadlineMinute = $state('00')
  /** duration as hours + minutes (optional) */
  let durationHours = $state('')
  let durationMinutes = $state('')
  /** Collapsed = no deadline; expanded shows date/time/duration. */
  let deadlineOpen = $state(false)
  /** @type {{ key: string, title: string, progress_current: number, progress_total: number }[]} */
  let steps = $state([])
  let saving = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let formError = $state('')

  const HOURS_24 = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'))
  const MINUTES_60 = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'))

  let heading = $derived(mode === 'create' ? 'Новый квест' : 'Редактировать квест')
  let selectedLine = $derived(
    questlineId === ''
      ? null
      : questlines.find((l) => String(l.id) === questlineId) ?? null,
  )
  let categoryLocked = $derived(selectedLine != null)
  let deadlineLocal = $derived(
    deadlineDate ? `${deadlineDate}T${deadlineHour}:${deadlineMinute}` : '',
  )

  function applyQuestline(idStr) {
    questlineId = idStr
    if (idStr === '') return
    const line = questlines.find((l) => String(l.id) === idStr)
    if (!line) return
    categoryId = line.category_id != null ? String(line.category_id) : ''
  }

  function blankStep() {
    return {
      key: crypto.randomUUID(),
      title: '',
      progress_current: 0,
      progress_total: 1,
      check_command: '',
      check_interval_seconds: '',
      check_open: false,
    }
  }

  function applyDefaultDeadline() {
    const parts = defaultLocalDeadlineParts()
    deadlineDate = parts.date
    deadlineHour = parts.hour
    deadlineMinute = parts.minute
  }

  function clearDeadline() {
    deadlineDate = ''
    durationHours = ''
    durationMinutes = ''
  }

  function toggleDeadline() {
    if (deadlineOpen) {
      deadlineOpen = false
      clearDeadline()
      return
    }
    deadlineOpen = true
    if (!deadlineDate) applyDefaultDeadline()
  }

  function resetFromQuest(q) {
    if (!q) {
      title = ''
      description = ''
      status = 'active'
      significance = 'common'
      pinned = false
      sortOrder = 0
      categoryId =
        defaults?.category_id != null ? String(defaults.category_id) : ''
      questlineId =
        defaults?.questline_id != null ? String(defaults.questline_id) : ''
      deadlineOpen = false
      clearDeadline()
      steps = [blankStep()]
      return
    }
    title = q.title ?? ''
    description = q.description ?? ''
    status = q.status ?? 'active'
    significance = q.significance ?? 'common'
    pinned = Boolean(q.pinned)
    sortOrder = q.sort_order ?? 0
    categoryId = q.category_id != null ? String(q.category_id) : ''
    questlineId = q.questline_id != null ? String(q.questline_id) : ''
    const local = toLocalInputValue(q.deadline_at)
    if (local && local.includes('T')) {
      deadlineOpen = true
      const [d, t] = local.split('T')
      deadlineDate = d || ''
      const [hh = '12', mm = '00'] = (t || '').slice(0, 5).split(':')
      deadlineHour = String(Math.min(23, Math.max(0, Number(hh) || 0))).padStart(2, '0')
      deadlineMinute = String(Math.min(59, Math.max(0, Number(mm) || 0))).padStart(2, '0')
    } else {
      deadlineOpen = false
      clearDeadline()
    }
    const dur = Number(q.duration_seconds) || 0
    if (dur > 0) {
      durationHours = String(Math.floor(dur / 3600))
      durationMinutes = String(Math.floor((dur % 3600) / 60))
    } else {
      durationHours = ''
      durationMinutes = ''
    }
    steps =
      q.steps?.length > 0
        ? q.steps.map((s) => ({
            key: String(s.id ?? crypto.randomUUID()),
            title: s.title ?? '',
            progress_current: s.progress_current ?? 0,
            progress_total: s.progress_total ?? 1,
            check_command: s.check_command ?? '',
            check_interval_seconds:
              s.check_interval_seconds != null ? String(s.check_interval_seconds) : '',
            check_open: Boolean(String(s.check_command || '').trim()),
          }))
        : [blankStep()]
  }

  // Init only on open false→true. A plain `if (open) { reset… }` re-runs on
  // parent re-renders (App ticks nowMs / WS refresh) and wipes steps + selects.
  let wasOpen = false
  $effect(() => {
    const isOpen = open
    if (isOpen && !wasOpen) {
      formError = ''
      saving = false
      deleting = false
      deleteConfirmOpen = false
      resetFromQuest(mode === 'edit' ? quest : null)
      Promise.all([listCategories(), listQuestlines()])
        .then(([cats, lines]) => {
          categories = Array.isArray(cats) ? cats : []
          questlines = Array.isArray(lines) ? lines : []
          if (mode === 'create' && defaults?.questline_id != null) {
            applyQuestline(String(defaults.questline_id))
          }
        })
        .catch(() => {
          categories = []
          questlines = []
        })
    }
    wasOpen = isOpen
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

  function addStep() {
    steps = [...steps, blankStep()]
  }

  function removeStep(key) {
    if (steps.length <= 1) {
      steps = [blankStep()]
      return
    }
    steps = steps.filter((s) => s.key !== key)
  }

  function buildStepsPayload() {
    return steps
      .map((s, i) => {
        const cmd = String(s.check_command || '').trim()
        const intervalRaw = String(s.check_interval_seconds ?? '').trim()
        const interval = intervalRaw === '' ? null : Math.max(15, Number(intervalRaw) || 15)
        return {
          title: s.title.trim(),
          description: '',
          progress_current: Math.max(0, Number(s.progress_current) || 0),
          progress_total: Math.max(1, Number(s.progress_total) || 1),
          sort_order: i,
          check_command: cmd || null,
          check_interval_seconds: cmd ? interval : null,
        }
      })
      .filter((s) => s.title)
  }

  async function onSubmit(event) {
    event.preventDefault()
    if (!title.trim()) {
      formError = 'Нужен заголовок'
      return
    }
    const stepsPayload = buildStepsPayload()
    saving = true
    formError = ''
    try {
      const deadline_at = deadlineOpen ? localInputToUtcIso(deadlineLocal) : null
      const h = Number(durationHours)
      const m = Number(durationMinutes)
      let duration_seconds = null
      if (deadline_at && (Number.isFinite(h) || Number.isFinite(m))) {
        const hours = Number.isFinite(h) ? Math.max(0, h) : 0
        const mins = Number.isFinite(m) ? Math.max(0, m) : 0
        const total = Math.round(hours * 3600 + mins * 60)
        if (total > 0) duration_seconds = total
      }
      const payload = {
        title: title.trim(),
        description: description.trim(),
        status,
        significance,
        pinned,
        sort_order: Number(sortOrder) || 0,
        category_id: categoryId === '' ? null : Number(categoryId),
        questline_id: questlineId === '' ? null : Number(questlineId),
        deadline_at,
        ...(deadline_at && duration_seconds != null ? { duration_seconds } : {}),
        steps: stepsPayload,
      }
      // Clear duration when clearing deadline.
      if (!deadline_at) {
        payload.duration_seconds = null
      }
      const saved =
        mode === 'create' ? await createQuest(payload) : await updateQuest(quest.id, payload)
      onSaved(saved)
      onClose()
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  function requestDelete() {
    if (!quest?.id || deleting || saving) return
    deleteConfirmOpen = true
  }

  async function confirmDelete() {
    if (!quest?.id) return
    deleting = true
    formError = ''
    try {
      await deleteQuest(quest.id)
      deleteConfirmOpen = false
      onDeleted?.(quest.id)
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
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="quest-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="quest-modal-title" class="modal__title">
          <Icon name={mode === 'create' ? 'document' : 'edit'} size={18} />
          <span>{heading}</span>
        </h2>
        <button type="button" class="btn btn--ghost btn--icon btn--close" onclick={onClose} aria-label="Закрыть">
          <Icon name="close" size={14} />
        </button>
      </header>

      {#if formError}
        <p class="modal__error">{formError}</p>
      {/if}

      <form class="modal__form" onsubmit={onSubmit}>
        <label class="field">
          <span class="label">Заголовок</span>
          <input type="text" bind:value={title} required />
        </label>

        <label class="field">
          <span class="label">Описание</span>
          <textarea rows="3" bind:value={description}></textarea>
        </label>

        <div class="field">
          <span class="label">Статус</span>
          <div class="opt-slider" role="radiogroup" aria-label="Статус">
            {#each QUEST_STATUSES as s}
              <button
                type="button"
                class="opt-slider__opt"
                class:opt-slider__opt--on={status === s}
                role="radio"
                aria-checked={status === s}
                onclick={() => (status = s)}
              >
                {QUEST_STATUS_LABELS[s] ?? s}
              </button>
            {/each}
          </div>
        </div>

        <div class="field">
          <span class="label">Значимость</span>
          <div class="opt-slider" role="radiogroup" aria-label="Значимость">
            {#each QUEST_SIGNIFICANCES as s}
              <button
                type="button"
                class="opt-slider__opt opt-slider__opt--sig"
                class:opt-slider__opt--on={significance === s.id}
                data-sig={s.id}
                role="radio"
                aria-checked={significance === s.id}
                onclick={() => (significance = s.id)}
              >
                {s.label}
              </button>
            {/each}
          </div>
        </div>

        <div class="field">
          <span class="label">Квестлайн</span>
          <div class="opt-slider opt-slider--wrap" role="radiogroup" aria-label="Квестлайн">
            <button
              type="button"
              class="opt-slider__opt"
              class:opt-slider__opt--on={questlineId === ''}
              role="radio"
              aria-checked={questlineId === ''}
              onclick={() => applyQuestline('')}
            >
              Нет
            </button>
            {#each questlines as line}
              <button
                type="button"
                class="opt-slider__opt opt-slider__opt--cat"
                class:opt-slider__opt--on={questlineId === String(line.id)}
                style="--opt-color: {line.color || '#9a9a9a'}"
                role="radio"
                aria-checked={questlineId === String(line.id)}
                onclick={() => applyQuestline(String(line.id))}
              >
                {line.title}
              </button>
            {/each}
          </div>
        </div>

        <div class="field">
          <span class="label">Раздел{categoryLocked ? ' (от квестлайна)' : ''}</span>
          <div
            class="opt-slider opt-slider--wrap"
            class:opt-slider--locked={categoryLocked}
            role="radiogroup"
            aria-label="Раздел"
            aria-disabled={categoryLocked}
          >
            <button
              type="button"
              class="opt-slider__opt opt-slider__opt--cat"
              class:opt-slider__opt--on={categoryId === ''}
              data-cat="none"
              role="radio"
              aria-checked={categoryId === ''}
              disabled={categoryLocked}
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
                disabled={categoryLocked}
                onclick={() => (categoryId = String(c.id))}
              >
                {c.label}
              </button>
            {/each}
          </div>
        </div>

        <label class="check">
          <input type="checkbox" bind:checked={pinned} />
          Закрепить (показывать в оверлее)
        </label>

        <div class="deadline-block">
          <button
            type="button"
            class="deadline-toggle"
            aria-expanded={deadlineOpen}
            onclick={toggleDeadline}
          >
            <span class="deadline-toggle__label">Срок ({localTimeZone()}, 24ч)</span>
            <span class="deadline-toggle__hint">
              {deadlineOpen ? 'задан' : 'не задан'}
            </span>
            <span class="deadline-toggle__chevron" aria-hidden="true">
              <Icon name={deadlineOpen ? 'chevron-down' : 'chevron-right'} size={14} />
            </span>
          </button>
          {#if deadlineOpen}
            <div class="deadline-body">
              <div class="deadline-row">
                <label class="field field--deadline">
                  <span class="label">Дата и время</span>
                  <div class="deadline-inputs">
                    <input type="date" lang="ru-RU" bind:value={deadlineDate} required />
                    <div class="time-24" title="Часы:минуты (0–23)">
                      <select bind:value={deadlineHour} aria-label="Часы (0–23)">
                        {#each HOURS_24 as h}
                          <option value={h}>{h}</option>
                        {/each}
                      </select>
                      <span class="time-24__sep">:</span>
                      <select bind:value={deadlineMinute} aria-label="Минуты">
                        {#each MINUTES_60 as m}
                          <option value={m}>{m}</option>
                        {/each}
                      </select>
                    </div>
                  </div>
                </label>
                <div class="field field--duration">
                  <span class="label">Длительность окна</span>
                  <div class="duration-row">
                    <input type="number" min="0" placeholder="ч" bind:value={durationHours} />
                    <span class="duration-row__sep">:</span>
                    <input
                      type="number"
                      min="0"
                      max="59"
                      placeholder="мин"
                      bind:value={durationMinutes}
                    />
                  </div>
                </div>
              </div>
              <p class="hint">
                Длительность пусто = от создания/изменения до срока. Окно срочности = срок −
                длительность. Свернуть строку «Срок» = убрать дедлайн.
              </p>
            </div>
          {/if}
        </div>

        <div class="steps-block">
          <div class="steps-block__head">
            <span class="label">Шаги</span>
            <button type="button" class="btn btn--ghost btn--add-step" onclick={addStep}>
              <Icon name="add" size={16} />
              <span class="btn__text">шаг</span>
            </button>
          </div>
          {#each steps as step (step.key)}
            <div class="step-edit">
              <div class="step-edit__row">
                <input
                  type="text"
                  class="step-edit__title"
                  placeholder="Название шага"
                  bind:value={step.title}
                />
                <input
                  type="number"
                  class="step-edit__num"
                  min="0"
                  title="текущее"
                  bind:value={step.progress_current}
                />
                <span class="step-edit__slash">/</span>
                <input
                  type="number"
                  class="step-edit__num"
                  min="1"
                  title="всего"
                  bind:value={step.progress_total}
                />
                <button
                  type="button"
                  class="btn btn--ghost btn--icon"
                  class:btn--check-on={step.check_open}
                  onclick={() => (step.check_open = !step.check_open)}
                  aria-label="Команда проверки"
                  title="Команда проверки"
                >
                  <Icon name="terminal" size={14} />
                </button>
                <button
                  type="button"
                  class="btn btn--ghost btn--icon btn--step-remove"
                  onclick={() => removeStep(step.key)}
                  aria-label="Удалить шаг"
                >
                  <Icon name="delete" size={14} />
                </button>
              </div>
              {#if step.check_open}
                <div class="step-edit__check">
                  <input
                    type="text"
                    class="step-edit__cmd"
                    placeholder="команда проверки (stdout → число), напр. find ~/docs -type f | wc -l"
                    bind:value={step.check_command}
                    spellcheck="false"
                  />
                  <input
                    type="number"
                    class="step-edit__interval"
                    min="15"
                    step="15"
                    placeholder="сек"
                    title="Интервал проверки (сек, мин. 15)"
                    bind:value={step.check_interval_seconds}
                    disabled={!String(step.check_command || '').trim()}
                  />
                </div>
              {/if}
            </div>
          {/each}
          <p class="hint">
            Пустые шаги отбрасываются. Команда проверки — по кнопке терминала у шага: сервер раз в N сек
            читает число из stdout и пишет в текущее значение.
          </p>
        </div>

        <footer class="modal__foot">
          {#if mode === 'edit'}
            <button
              type="button"
              class="btn btn--danger"
              onclick={requestDelete}
              disabled={saving || deleting}
              aria-label={deleting ? 'Удаление…' : 'Удалить'}
            >
              <Icon name="delete" size={14} />
              <span class="btn__text">{deleting ? '…' : 'Удалить'}</span>
            </button>
          {:else}
            <span></span>
          {/if}
          <div class="modal__foot-right">
            <button
              type="button"
              class="btn"
              onclick={onClose}
              disabled={saving || deleting}
              aria-label="Отмена"
            >
              <Icon name="close" size={12} />
              <span class="btn__text">Отмена</span>
            </button>
            <button
              type="submit"
              class="btn btn--accent"
              disabled={saving || deleting}
              aria-label={mode === 'create' ? 'Создать' : 'Сохранить'}
            >
              {#if saving}
                <span>…</span>
              {:else if mode === 'create'}
                <Icon name="checkmark" size={15} />
                <span class="btn__text">Создать</span>
              {:else}
                <Icon name="save" size={15} />
                <span class="btn__text">Сохранить</span>
              {/if}
            </button>
          </div>
        </footer>
      </form>
    </div>
  </div>
{/if}

<ConfirmModal
  open={deleteConfirmOpen}
  title="Удалить квест?"
  message={quest ? `Удалить квест «${quest.title}»?` : ''}
  busy={deleting}
  onCancel={() => {
    if (!deleting) deleteConfirmOpen = false
  }}
  onConfirm={confirmDelete}
/>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 40;
    display: grid;
    place-items: center;
    padding: var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
    backdrop-filter: blur(2px);
  }

  .modal {
    width: min(36rem, 100%);
    max-height: min(90vh, 52rem);
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
    gap: var(--space-2, 0.5rem);
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-lg, 1.25rem);
    color: var(--color-accent, #c9a227);
  }

  .modal__error {
    margin: 0;
    padding: var(--space-2, 0.5rem) var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 18%, transparent);
    color: var(--color-danger, #b54a3a);
    font-size: var(--text-sm, 0.875rem);
  }

  .modal__form {
    display: grid;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem);
  }

  .field {
    display: grid;
    gap: var(--space-1, 0.25rem);
  }

  .label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .deadline-block {
    display: grid;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    overflow: hidden;
  }

  .deadline-toggle {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    width: 100%;
    margin: 0;
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    border: 0;
    border-radius: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .deadline-toggle:hover {
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 70%, transparent);
  }

  .deadline-toggle__label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .deadline-toggle__hint {
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .deadline-toggle__chevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    justify-self: end;
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .deadline-body {
    display: grid;
    gap: var(--space-2, 0.5rem);
    padding: 0 var(--space-3, 0.75rem) var(--space-3, 0.75rem);
  }

  .deadline-row {
    display: grid;
    grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr);
    gap: var(--space-3, 0.75rem);
    align-items: end;
  }

  .deadline-inputs {
    display: grid;
    grid-template-columns: 1.15fr auto;
    gap: var(--space-2, 0.5rem);
    align-items: center;
  }

  input[type='text'],
  input[type='number'],
  input[type='date'],
  input[type='time'],
  textarea,
  select {
    width: 100%;
    padding: var(--space-2, 0.5rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg, #121212);
    color: var(--color-fg, #e8e8e8);
    font: inherit;
  }

  input:focus,
  textarea:focus,
  select:focus {
    outline: 1px solid var(--color-accent, #c9a227);
    outline-offset: 1px;
  }

  .opt-slider {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 2px;
    padding: 3px;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-muted, #242424);
    overflow-x: auto;
  }

  .opt-slider__opt {
    flex: 1 1 0;
    margin: 0;
    padding: 0.45rem 0.5rem;
    border: 0;
    border-radius: calc(var(--radius-lg, 12px) - 2px);
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    font: inherit;
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.02em;
    white-space: nowrap;
    cursor: pointer;
  }

  .opt-slider__opt:hover {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 80%, transparent);
  }

  .opt-slider__opt--on {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 22%, var(--color-bg, #121212));
    color: var(--color-accent, #c9a227);
    font-weight: 600;
  }

  .opt-slider--wrap {
    flex-wrap: wrap;
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

  .opt-slider--locked {
    opacity: 0.72;
  }

  .opt-slider--locked .opt-slider__opt:disabled {
    cursor: default;
  }

  .time-24 {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  .time-24 select {
    width: 3.6rem;
    padding: var(--space-2, 0.5rem) 0.35rem;
    text-align: center;
    font-variant-numeric: tabular-nums;
  }

  .time-24__sep {
    color: var(--color-fg-subtle, #6e6e6e);
    font-weight: 600;
  }

  .duration-row {
    display: flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    min-height: 2.25rem;
  }

  .duration-row input {
    width: 4.5rem;
  }

  .duration-row__sep {
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .steps-block {
    display: grid;
    gap: var(--space-2, 0.5rem);
    padding-top: var(--space-2, 0.5rem);
    border-top: 1px dashed var(--color-border, #333);
  }

  .steps-block__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .step-edit {
    display: grid;
    gap: var(--space-2, 0.5rem);
  }

  .step-edit__row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 3.2rem auto 3.2rem auto auto;
    gap: var(--space-2, 0.5rem);
    align-items: center;
  }

  .step-edit__check {
    display: grid;
    grid-template-columns: 1fr 4.5rem;
    gap: var(--space-2, 0.5rem);
    align-items: center;
  }

  .step-edit__cmd {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
  }

  .step-edit__interval {
    width: 100%;
  }

  .step-edit__slash {
    color: var(--color-fg-subtle, #6e6e6e);
    text-align: center;
  }

  .hint {
    margin: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .modal__foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    padding-top: var(--space-2, 0.5rem);
    border-top: 1px solid var(--color-border, #333);
  }

  .modal__foot-right {
    display: flex;
    gap: var(--space-2, 0.5rem);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font: inherit;
    font-size: var(--text-sm, 0.875rem);
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    cursor: pointer;
  }

  .btn:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: wait;
  }

  .btn--accent {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, var(--color-bg-muted, #242424));
    color: var(--color-accent, #c9a227);
  }

  .btn--danger {
    border-color: transparent;
    background: transparent;
    color: color-mix(in srgb, var(--color-danger, #b54a3a) 78%, var(--color-fg, #e8e8e8));
  }

  .btn--danger:hover:not(:disabled) {
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 10%, transparent);
  }

  .btn--ghost {
    border-color: transparent;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .btn--ghost:hover {
    color: var(--color-fg, #e8e8e8);
    background: var(--color-bg-hover, #2a2a2a);
  }

  .btn--add-step {
    align-items: center;
    line-height: 1;
    gap: 0.2rem;
    padding: 0.2rem 0.35rem;
  }

  .btn--add-step :global(.icon) {
    display: block;
  }

  .btn--add-step .btn__text {
    line-height: 1;
    display: inline-flex;
    align-items: center;
  }

  .btn--add-step:hover {
    background: transparent;
    color: var(--color-fg, #e8e8e8);
  }

  .btn--close {
    border: 0;
    background: transparent;
  }

  .btn--icon {
    padding: var(--space-2, 0.5rem);
  }

  .btn--step-remove:hover {
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 10%, transparent);
  }

  .btn--check-on {
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
  }

  @media (max-width: 520px) {
    .deadline-row,
    .deadline-inputs {
      grid-template-columns: 1fr;
    }
  }

  @media (orientation: portrait) {
    .opt-slider {
      flex-direction: column;
      overflow-x: visible;
    }

    .opt-slider__opt {
      flex: 0 0 auto;
      width: 100%;
      text-align: left;
    }

    .btn__text {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }

    .btn:not(.btn--icon) {
      padding: var(--space-2, 0.5rem);
    }
  }
</style>
