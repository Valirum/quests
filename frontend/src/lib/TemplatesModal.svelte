<script>
  import {
    TEMPLATE_FREQS,
    TEMPLATE_FREQ_LABELS,
    TEMPLATE_EMIT_MODES,
    WEEKDAY_LABELS,
    QUEST_SIGNIFICANCES,
    copyTemplate,
    createTemplate,
    deleteTemplate,
    listCategories,
    listQuestlines,
    listTemplates,
    updateTemplate,
  } from '../lib/api.js'
  import { defaultLocalDeadlineParts, localTimeZone } from '../lib/time.js'
  import Icon from './Icon.svelte'
  import ConfirmModal from './ConfirmModal.svelte'

  /** @type {{ open: boolean, onClose: () => void, onChanged: () => void }} */
  let { open = false, onClose, onChanged } = $props()

  let templates = $state(/** @type {any[]} */ ([]))
  let loading = $state(false)
  let error = $state('')
  /** @type {'list' | 'create' | 'edit'} */
  let view = $state('list')
  let editing = $state(/** @type {any | null} */ (null))

  let title = $state('')
  let description = $state('')
  let pinned = $state(false)
  let significance = $state('common')
  let enabled = $state(true)
  let freq = $state('daily')
  let emitMode = $state('fixed')
  /** Empty string = no category. */
  let categoryId = $state('')
  /** Empty string = no questline. */
  let questlineId = $state('')
  /** @type {{ id: number, slug: string, label: string, color?: string }[]} */
  let categories = $state([])
  /** @type {{ id: number, title: string, category_id?: number | null, color?: string }[]} */
  let questlines = $state([])
  /** 0..100 for UI; sent as 0..1 */
  let emitChancePct = $state(100)
  let windowStartHour = $state('09')
  let windowStartMinute = $state('00')
  let windowEndHour = $state('18')
  let windowEndMinute = $state('00')
  /** @type {Set<number>} */
  let weekdays = $state(new Set([0, 1, 2, 3, 4]))
  let timezone = $state(localTimeZone() || 'Europe/Moscow')
  /** Empty hour = no deadline (like empty date on quests). */
  let deadlineHour = $state('')
  let deadlineMinute = $state('00')
  let durationHours = $state('')
  let durationMinutes = $state('')
  /** @type {{ key: string, title: string, progress_range: string, check_command: string, check_interval_seconds: string, check_open: boolean }[]} */
  let steps = $state([])
  let saving = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let formError = $state('')

  const HOURS_24 = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'))
  const MINUTES_60 = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'))

  let isSurprise = $derived(emitMode === 'surprise')
  let hasDeadline = $derived(!isSurprise && Boolean(deadlineHour))
  let selectedLine = $derived(
    questlineId === ''
      ? null
      : questlines.find((l) => String(l.id) === questlineId) ?? null,
  )
  let categoryLocked = $derived(selectedLine != null)

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
      progress_range: '1',
      check_command: '',
      check_interval_seconds: '',
      check_open: false,
    }
  }

  function formatProgressRange(min, max) {
    const lo = Math.max(1, Number(min) || 1)
    const hi = Math.max(lo, Number(max) || lo)
    return lo === hi ? String(lo) : `${lo}..${hi}`
  }

  function parseProgressRange(raw) {
    const text = String(raw ?? '').trim()
    if (!text) return { progress_min: 1, progress_max: 1 }
    const sep = text.includes('..') ? '..' : text.includes('-') ? '-' : null
    if (sep) {
      const [a, b] = text.split(sep, 2)
      let lo = Math.max(1, Number(a) || 1)
      let hi = Math.max(1, Number(b) || lo)
      if (hi < lo) [lo, hi] = [hi, lo]
      return { progress_min: lo, progress_max: hi }
    }
    const n = Math.max(1, Number(text) || 1)
    return { progress_min: n, progress_max: n }
  }

  function parseClock(raw, fallbackH, fallbackM) {
    const text = String(raw || '').trim()
    if (text && text.includes(':')) {
      const [hh = fallbackH, mm = fallbackM] = text.split(':')
      return {
        hour: String(Math.min(23, Math.max(0, Number(hh) || 0))).padStart(2, '0'),
        minute: String(Math.min(59, Math.max(0, Number(mm) || 0))).padStart(2, '0'),
      }
    }
    return { hour: fallbackH, minute: fallbackM }
  }

  function applyDefaultDeadlineTime() {
    const parts = defaultLocalDeadlineParts()
    deadlineHour = parts.hour
    deadlineMinute = parts.minute
  }

  function parseWeekdays(raw) {
    const set = new Set()
    for (const part of String(raw || '').split(',')) {
      const n = Number(part.trim())
      if (Number.isInteger(n) && n >= 0 && n <= 6) set.add(n)
    }
    return set.size ? set : new Set([0, 1, 2, 3, 4])
  }

  function resetForm(t = null) {
    formError = ''
    if (!t) {
      title = ''
      description = ''
      pinned = false
      significance = 'common'
      enabled = true
      freq = 'daily'
      emitMode = 'fixed'
      categoryId = ''
      questlineId = ''
      emitChancePct = 100
      windowStartHour = '09'
      windowStartMinute = '00'
      windowEndHour = '18'
      windowEndMinute = '00'
      weekdays = new Set([0, 1, 2, 3, 4])
      timezone = localTimeZone() || 'Europe/Moscow'
      applyDefaultDeadlineTime()
      durationHours = ''
      durationMinutes = ''
      steps = [blankStep()]
      return
    }
    title = t.title ?? ''
    description = t.description ?? ''
    pinned = Boolean(t.pinned)
    significance = t.significance ?? 'common'
    enabled = t.enabled !== false
    freq = t.freq ?? 'daily'
    emitMode = t.emit_mode === 'surprise' ? 'surprise' : 'fixed'
    categoryId = t.category_id != null ? String(t.category_id) : ''
    questlineId = t.questline_id != null ? String(t.questline_id) : ''
    emitChancePct = Math.round(Math.max(0, Math.min(1, Number(t.emit_chance) || 1)) * 100)
    const ws = parseClock(t.emit_window_start, '09', '00')
    const we = parseClock(t.emit_window_end, '18', '00')
    windowStartHour = ws.hour
    windowStartMinute = ws.minute
    windowEndHour = we.hour
    windowEndMinute = we.minute
    weekdays = parseWeekdays(t.weekdays)
    timezone = t.timezone || localTimeZone() || 'Europe/Moscow'
    const rawTime = String(t.deadline_time || '').trim()
    if (rawTime && rawTime.includes(':')) {
      const [hh = '', mm = '00'] = rawTime.split(':')
      deadlineHour = String(Math.min(23, Math.max(0, Number(hh) || 0))).padStart(2, '0')
      deadlineMinute = String(Math.min(59, Math.max(0, Number(mm) || 0))).padStart(2, '0')
    } else {
      deadlineHour = ''
      deadlineMinute = '00'
    }
    const dur = Number(t.duration_seconds) || 0
    if (dur > 0) {
      durationHours = String(Math.floor(dur / 3600))
      durationMinutes = String(Math.floor((dur % 3600) / 60))
    } else {
      durationHours = ''
      durationMinutes = ''
    }
    steps =
      t.steps?.length > 0
        ? t.steps.map((s) => ({
            key: String(s.id ?? crypto.randomUUID()),
            title: s.title ?? '',
            progress_range: formatProgressRange(
              s.progress_min ?? s.progress_total,
              s.progress_max ?? s.progress_total,
            ),
            check_command: s.check_command ?? '',
            check_interval_seconds:
              s.check_interval_seconds != null ? String(s.check_interval_seconds) : '',
            check_open: Boolean(String(s.check_command || '').trim()),
          }))
        : [blankStep()]
  }

  async function refresh() {
    loading = true
    error = ''
    try {
      const [tpls, cats, lines] = await Promise.all([
        listTemplates({}),
        listCategories(),
        listQuestlines(),
      ])
      templates = tpls
      categories = Array.isArray(cats) ? cats : []
      questlines = Array.isArray(lines) ? lines : []
    } catch (e) {
      error = e.message || String(e)
      templates = []
    } finally {
      loading = false
    }
  }

  // Reset list only when the modal opens (false → true). A plain
  // `if (open) { view = 'list' }` re-runs on parent re-renders and
  // immediately undoes "Новый шаблон" / edit.
  let wasOpen = false
  $effect(() => {
    const isOpen = open
    if (isOpen && !wasOpen) {
      view = 'list'
      editing = null
      void refresh()
    }
    wasOpen = isOpen
  })

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        if (view !== 'list') {
          view = 'list'
          editing = null
          return
        }
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  function openCreate() {
    editing = null
    view = 'create'
    resetForm(null)
  }

  function openEdit(t) {
    editing = t
    view = 'edit'
    resetForm(t)
  }

  function toggleDay(id) {
    const next = new Set(weekdays)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    if (next.size === 0) next.add(id)
    weekdays = next
  }

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

  function buildDurationSeconds() {
    const h = Number(durationHours)
    const m = Number(durationMinutes)
    if (!(Number.isFinite(h) || Number.isFinite(m))) return null
    const hours = Number.isFinite(h) ? Math.max(0, h) : 0
    const mins = Number.isFinite(m) ? Math.max(0, m) : 0
    const total = Math.round(hours * 3600 + mins * 60)
    return total > 0 ? total : null
  }

  function buildPayload() {
    const duration_seconds = buildDurationSeconds()
    const stepsPayload = steps
      .map((s, i) => {
        const cmd = String(s.check_command || '').trim()
        const intervalRaw = String(s.check_interval_seconds ?? '').trim()
        const interval = intervalRaw === '' ? null : Math.max(15, Number(intervalRaw) || 15)
        const range = parseProgressRange(s.progress_range)
        return {
          title: s.title.trim(),
          description: '',
          progress_min: range.progress_min,
          progress_max: range.progress_max,
          sort_order: i,
          check_command: cmd || null,
          check_interval_seconds: cmd ? interval : null,
        }
      })
      .filter((s) => s.title)

    if (isSurprise) {
      return {
        title: title.trim(),
        description: description.trim(),
        pinned,
        enabled,
        significance,
        freq,
        weekdays: [...weekdays].sort((a, b) => a - b).join(','),
        timezone: timezone.trim() || 'Europe/Moscow',
        emit_mode: 'surprise',
        emit_chance: Math.max(0, Math.min(100, Number(emitChancePct) || 0)) / 100,
        emit_window_start: `${windowStartHour}:${windowStartMinute}`,
        emit_window_end: `${windowEndHour}:${windowEndMinute}`,
        deadline_time: null,
        duration_seconds,
        category_id: categoryId === '' ? null : Number(categoryId),
        questline_id: questlineId === '' ? null : Number(questlineId),
        steps: stepsPayload,
      }
    }

    const deadline_time = hasDeadline ? `${deadlineHour}:${deadlineMinute}` : null
    return {
      title: title.trim(),
      description: description.trim(),
      pinned,
      enabled,
      significance,
      freq,
      weekdays: [...weekdays].sort((a, b) => a - b).join(','),
      timezone: timezone.trim() || 'Europe/Moscow',
      emit_mode: 'fixed',
      emit_chance: 1,
      emit_window_start: null,
      emit_window_end: null,
      deadline_time,
      duration_seconds: deadline_time ? duration_seconds : null,
      category_id: categoryId === '' ? null : Number(categoryId),
      questline_id: questlineId === '' ? null : Number(questlineId),
      steps: stepsPayload,
    }
  }

  async function onSubmit(event) {
    event.preventDefault()
    if (!title.trim()) {
      formError = 'Нужен заголовок'
      return
    }
    const payload = buildPayload()
    if (!payload.steps.length) {
      formError = 'Нужен хотя бы один шаг'
      return
    }
    saving = true
    formError = ''
    try {
      if (view === 'create') await createTemplate(payload)
      else await updateTemplate(editing.id, payload)
      onChanged()
      await refresh()
      view = 'list'
      editing = null
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      saving = false
    }
  }

  async function onToggleEnabled(t) {
    try {
      await updateTemplate(t.id, { enabled: !t.enabled })
      onChanged()
      await refresh()
    } catch (e) {
      error = e.message || String(e)
    }
  }

  async function onCopy(t, event) {
    event?.stopPropagation?.()
    try {
      await copyTemplate(t.id)
      onChanged()
      await refresh()
    } catch (e) {
      error = e.message || String(e)
    }
  }

  function requestDelete() {
    if (!editing?.id || deleting || saving) return
    deleteConfirmOpen = true
  }

  async function confirmDelete() {
    if (!editing?.id) return
    deleting = true
    formError = ''
    try {
      await deleteTemplate(editing.id)
      deleteConfirmOpen = false
      onChanged()
      await refresh()
      view = 'list'
      editing = null
    } catch (e) {
      formError = e.message || String(e)
    } finally {
      deleting = false
    }
  }

  function onBackdrop(event) {
    if (event.target === event.currentTarget) onClose()
  }

  function freqLabel(f) {
    return f === 'weekly' ? 'weekly' : 'daily'
  }

  function emitLabel(mode) {
    return mode === 'surprise' ? 'событие' : 'обычный'
  }

  function sigLabel(s) {
    return QUEST_SIGNIFICANCES.find((x) => x.id === s)?.label || 'обычное'
  }
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdrop}>
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="templates-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="templates-modal-title" class="modal__title">
          <Icon name="renew" size={18} />
          <span>
            {#if view === 'list'}
              Шаблоны
            {:else if view === 'create'}
              Новый шаблон
            {:else}
              Редактировать шаблон
            {/if}
          </span>
        </h2>
        <button type="button" class="btn btn--ghost btn--icon btn--close" onclick={onClose} aria-label="Закрыть">
          <Icon name="close" size={14} />
        </button>
      </header>

      {#if view === 'list'}
        <div class="modal__body">
          {#if error}
            <p class="modal__error">{error}</p>
          {/if}
          <div class="toolbar">
            <button type="button" class="btn btn--accent" onclick={openCreate}>
              <Icon name="add" size={14} />
              <span class="btn__text">Новый шаблон</span>
            </button>
          </div>
          {#if loading}
            <p class="empty">Загрузка…</p>
          {:else if templates.length === 0}
            <p class="empty">Пока нет шаблонов — создай дейлик или weekly.</p>
          {:else}
            <ul class="tpl-list">
              {#each templates as t (t.id)}
                <li class="tpl-row" class:tpl-row--off={!t.enabled}>
                  <button type="button" class="tpl-row__main" onclick={() => openEdit(t)}>
                    <span class="tpl-row__title">{t.title}</span>
                    <span class="tpl-row__meta">
                      {freqLabel(t.freq)}
                      · {emitLabel(t.emit_mode)}
                      {#if t.questline_title}· {t.questline_title}{/if}
                      {#if t.category_label}· {t.category_label}{/if}
                      · {sigLabel(t.significance)}
                      {#if t.pinned}· закреплён{/if}
                      · {t.steps?.length ?? 0} шаг.
                    </span>
                  </button>
                  <div class="tpl-row__actions">
                    <button
                      type="button"
                      class="btn btn--ghost btn--icon tpl-row__action"
                      onclick={() => openEdit(t)}
                      title="Редактировать"
                      aria-label="Редактировать шаблон"
                    >
                      <Icon name="edit" size={14} />
                    </button>
                    <button
                      type="button"
                      class="btn btn--ghost btn--icon tpl-row__action"
                      onclick={(e) => onCopy(t, e)}
                      title="Копировать (копия будет выключена)"
                      aria-label="Копировать шаблон"
                    >
                      <Icon name="copy" size={14} />
                    </button>
                    <button
                      type="button"
                      class="switch"
                      class:switch--on={t.enabled}
                      role="switch"
                      aria-checked={t.enabled}
                      onclick={() => onToggleEnabled(t)}
                      title={t.enabled ? 'Выключить' : 'Включить'}
                      aria-label={t.enabled ? 'Выключить шаблон' : 'Включить шаблон'}
                    >
                      <span class="switch__knob"></span>
                    </button>
                  </div>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      {:else}
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
            <textarea rows="2" bind:value={description}></textarea>
          </label>

          <div class="field">
            <span class="label">Частота</span>
            <div class="opt-slider" role="radiogroup" aria-label="Частота">
              {#each TEMPLATE_FREQS as f}
                <button
                  type="button"
                  class="opt-slider__opt"
                  class:opt-slider__opt--on={freq === f}
                  role="radio"
                  aria-checked={freq === f}
                  onclick={() => (freq = f)}
                >
                  {TEMPLATE_FREQ_LABELS[f] ?? f}
                </button>
              {/each}
            </div>
          </div>

          <div class="field">
            <span class="label">Тип</span>
            <div class="opt-slider" role="radiogroup" aria-label="Тип">
              {#each TEMPLATE_EMIT_MODES as m}
                <button
                  type="button"
                  class="opt-slider__opt"
                  class:opt-slider__opt--on={emitMode === m.id}
                  role="radio"
                  aria-checked={emitMode === m.id}
                  onclick={() => (emitMode = m.id)}
                >
                  {m.label}
                </button>
              {/each}
            </div>
          </div>

          <div class="field">
            <span class="label">Значимость</span>
            <div class="opt-slider opt-slider--wrap" role="radiogroup" aria-label="Значимость">
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

          <label class="field">
            <span class="label">Timezone</span>
            <input type="text" bind:value={timezone} placeholder="Europe/Moscow" />
          </label>

          {#if freq === 'weekly'}
            <div class="field">
              <span class="label">Дни недели</span>
              <div class="days">
                {#each WEEKDAY_LABELS as d}
                  <button
                    type="button"
                    class="day"
                    class:day--on={weekdays.has(d.id)}
                    onclick={() => toggleDay(d.id)}
                  >
                    {d.label}
                  </button>
                {/each}
              </div>
            </div>
          {/if}

          {#if isSurprise}
            <div class="deadline-block">
              <label class="field">
                <span class="label">Шанс появления (%)</span>
                <input type="number" min="0" max="100" step="1" bind:value={emitChancePct} />
              </label>
              <div class="deadline-row">
                <label class="field">
                  <span class="label">Окно с</span>
                  <div class="time-24">
                    <select bind:value={windowStartHour} aria-label="Начало окна, часы">
                      {#each HOURS_24 as h}
                        <option value={h}>{h}</option>
                      {/each}
                    </select>
                    <span class="time-24__sep">:</span>
                    <select bind:value={windowStartMinute} aria-label="Начало окна, минуты">
                      {#each MINUTES_60 as m}
                        <option value={m}>{m}</option>
                      {/each}
                    </select>
                  </div>
                </label>
                <label class="field">
                  <span class="label">Окно до</span>
                  <div class="time-24">
                    <select bind:value={windowEndHour} aria-label="Конец окна, часы">
                      {#each HOURS_24 as h}
                        <option value={h}>{h}</option>
                      {/each}
                    </select>
                    <span class="time-24__sep">:</span>
                    <select bind:value={windowEndMinute} aria-label="Конец окна, минуты">
                      {#each MINUTES_60 as m}
                        <option value={m}>{m}</option>
                      {/each}
                    </select>
                  </div>
                </label>
              </div>
              <div class="field">
                <span class="label">Длительность после появления</span>
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
              <p class="hint">
                Один бросок на день: шанс → случайное время в окне → квест. Дедлайн = момент
                появления + длительность (пусто = без срока).
              </p>
            </div>
          {:else}
            <div class="deadline-block">
              <div class="deadline-row">
                <label class="field">
                  <span class="label">Срок (время дня, 24ч)</span>
                  <div class="time-24" title="Часы:минуты — в timezone шаблона">
                    <select
                      bind:value={deadlineHour}
                      aria-label="Часы срока (пусто = без срока)"
                    >
                      <option value="">—</option>
                      {#each HOURS_24 as h}
                        <option value={h}>{h}</option>
                      {/each}
                    </select>
                    <span class="time-24__sep">:</span>
                    <select
                      bind:value={deadlineMinute}
                      aria-label="Минуты"
                      disabled={!hasDeadline}
                    >
                      {#each MINUTES_60 as m}
                        <option value={m}>{m}</option>
                      {/each}
                    </select>
                  </div>
                </label>
                <div class="field">
                  <span class="label">Длительность окна</span>
                  <div class="duration-row">
                    <input
                      type="number"
                      min="0"
                      placeholder="ч"
                      bind:value={durationHours}
                      disabled={!hasDeadline}
                    />
                    <span class="duration-row__sep">:</span>
                    <input
                      type="number"
                      min="0"
                      max="59"
                      placeholder="мин"
                      bind:value={durationMinutes}
                      disabled={!hasDeadline}
                    />
                  </div>
                </div>
              </div>
              <p class="hint">
                Время — на каждый день периода в timezone шаблона. Пусто = без срока. Пустая
                длительность = от полуночи до срока.
              </p>
            </div>
          {/if}

          <label class="check">
            <input type="checkbox" bind:checked={pinned} />
            Закрепить (в оверлее)
          </label>
          <label class="check">
            <input type="checkbox" bind:checked={enabled} />
            Включён (создавать инстансы)
          </label>

          <div class="steps">
            <div class="steps__head">
              <span class="label">Шаги</span>
              <button type="button" class="btn btn--ghost btn--add-step" onclick={addStep}>
                <Icon name="add" size={16} />
                <span class="btn__text">шаг</span>
              </button>
            </div>
            {#each steps as s (s.key)}
              <div class="step-block">
                <div class="step-row">
                  <input type="text" placeholder="Название шага" bind:value={s.title} />
                  <input
                    type="text"
                    inputmode="numeric"
                    title="Кол-во: n или n..m"
                    placeholder="1 или 5..10"
                    bind:value={s.progress_range}
                    class="step-row__total"
                  />
                  <button
                    type="button"
                    class="btn btn--ghost btn--icon"
                    class:btn--check-on={s.check_open}
                    onclick={() => (s.check_open = !s.check_open)}
                    aria-label="Команда проверки"
                    title="Команда проверки"
                  >
                    <Icon name="terminal" size={14} />
                  </button>
                  <button
                    type="button"
                    class="btn btn--ghost btn--icon btn--step-remove"
                    onclick={() => removeStep(s.key)}
                    aria-label="Удалить шаг"
                  >
                    <Icon name="delete" size={14} />
                  </button>
                </div>
                {#if s.check_open}
                  <div class="step-check">
                    <input
                      type="text"
                      class="step-check__cmd"
                      placeholder="команда проверки (опц.)"
                      bind:value={s.check_command}
                      spellcheck="false"
                    />
                    <input
                      type="number"
                      class="step-check__interval"
                      min="15"
                      step="15"
                      placeholder="сек"
                      title="Интервал (сек)"
                      bind:value={s.check_interval_seconds}
                      disabled={!String(s.check_command || '').trim()}
                    />
                  </div>
                {/if}
              </div>
            {/each}
            <p class="hint">Кол-во шага: <code>5</code> или диапазон <code>5..10</code> (рандом при появлении).</p>
          </div>

          <footer class="modal__foot">
            <div class="modal__foot-left">
              {#if view === 'edit'}
                <button
                  type="button"
                  class="btn btn--ghost"
                  onclick={() => onCopy(editing)}
                  disabled={saving || deleting}
                  title="Копировать (копия будет выключена)"
                >
                  <Icon name="copy" size={14} />
                  <span class="btn__text">Копировать</span>
                </button>
                <button
                  type="button"
                  class="btn btn--danger"
                  onclick={requestDelete}
                  disabled={saving || deleting}
                >
                  <Icon name="delete" size={14} />
                  <span class="btn__text">Удалить</span>
                </button>
              {/if}
              <button type="button" class="btn btn--ghost" onclick={() => (view = 'list')}>
                Назад
              </button>
            </div>
            <button type="submit" class="btn btn--accent" disabled={saving || deleting}>
              {#if saving}
                …
              {:else if view === 'create'}
                <Icon name="checkmark" size={15} />
                <span class="btn__text">Создать</span>
              {:else}
                <Icon name="save" size={15} />
                <span class="btn__text">Сохранить</span>
              {/if}
            </button>
          </footer>
        </form>
      {/if}
    </div>
  </div>
{/if}

<ConfirmModal
  open={deleteConfirmOpen}
  title="Удалить шаблон?"
  message={editing
    ? `Удалить шаблон «${editing.title}»? Инстансы останутся.`
    : ''}
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

  .modal__body,
  .modal__form {
    display: grid;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem);
  }

  .toolbar {
    display: flex;
    justify-content: flex-end;
  }

  .empty {
    margin: 0;
    color: var(--color-fg-muted, #9a9a9a);
    font-size: var(--text-sm, 0.875rem);
  }

  .tpl-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
  }

  .tpl-row {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    padding-right: 0.55rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: color-mix(in srgb, var(--color-bg, #121212) 70%, transparent);
  }

  .tpl-row--off {
    opacity: 0.55;
  }

  .tpl-row__main {
    flex: 1;
    min-width: 0;
    display: grid;
    gap: 0.15rem;
    text-align: left;
    padding: 0.55rem 0.75rem;
    border: 0;
    background: transparent;
    color: inherit;
    cursor: pointer;
    font: inherit;
  }

  .tpl-row__title {
    font-weight: 600;
  }

  .tpl-row__meta {
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .tpl-row__actions {
    display: inline-flex;
    align-items: center;
    gap: 0.2rem;
    flex-shrink: 0;
  }

  .tpl-row__action {
    flex-shrink: 0;
    width: 1.75rem;
    height: 1.75rem;
    padding: 0;
    border: 0;
    justify-content: center;
  }

  .switch {
    position: relative;
    flex-shrink: 0;
    width: 2.25rem;
    height: 1.25rem;
    margin: 0;
    padding: 0;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: 999px;
    background: var(--color-bg-muted, #242424);
    cursor: pointer;
    transition:
      background 0.15s ease,
      border-color 0.15s ease;
  }

  .switch__knob {
    position: absolute;
    top: 1px;
    left: 1px;
    width: calc(1.25rem - 4px);
    height: calc(1.25rem - 4px);
    border-radius: 999px;
    background: var(--color-fg-muted, #9a9a9a);
    transition:
      transform 0.15s ease,
      background 0.15s ease;
  }

  .switch--on {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 28%, var(--color-bg-muted, #242424));
  }

  .switch--on .switch__knob {
    transform: translateX(1rem);
    background: var(--color-accent, #c9a227);
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
  textarea,
  select {
    font: inherit;
    color: var(--color-fg, #e8e8e8);
    background: var(--color-bg, #121212);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    padding: 0.45rem 0.55rem;
  }

  .deadline-block {
    display: grid;
    gap: 0.35rem;
  }

  .deadline-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-3, 0.75rem);
    align-items: end;
  }

  .time-24,
  .duration-row {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
  }

  .time-24__sep,
  .duration-row__sep {
    color: var(--color-fg-muted, #9a9a9a);
  }

  .duration-row input {
    width: 4.5rem;
  }

  .hint {
    margin: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .check {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: var(--text-sm, 0.875rem);
  }

  .days {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .day {
    min-width: 2.2rem;
    padding: 0.3rem 0.45rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    cursor: pointer;
    font: inherit;
  }

  .day--on {
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
    background: color-mix(in srgb, var(--color-accent, #c9a227) 14%, transparent);
  }

  .steps {
    display: grid;
    gap: 0.45rem;
  }

  .steps__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .step-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 5.5rem auto auto;
    gap: 0.35rem;
    align-items: center;
  }

  .hint code {
    font-family: var(--font-mono, monospace);
  }

  .step-block {
    display: grid;
    gap: 0.35rem;
  }

  .step-check {
    display: grid;
    grid-template-columns: 1fr 4.5rem;
    gap: 0.35rem;
  }

  .step-check__cmd {
    font-family: var(--font-mono, monospace);
    font-size: 0.75rem;
  }

  .modal__foot {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.5rem;
  }

  .modal__foot-left {
    display: flex;
    gap: 0.35rem;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 80%, transparent);
    color: var(--color-fg, #e8e8e8);
    padding: 0.4rem 0.65rem;
    cursor: pointer;
    font: inherit;
  }

  .btn--accent {
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
  }

  .btn--ghost {
    border-color: transparent;
    background: transparent;
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

  .btn--close {
    border: 0;
    background: transparent;
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
    padding: 0.35rem;
  }

  .btn--step-remove:hover {
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 10%, transparent);
  }

  .opt-slider {
    display: flex;
    flex-wrap: nowrap;
    gap: 2px;
    padding: 3px;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    overflow: hidden;
    background: var(--color-bg-muted, #242424);
  }

  .opt-slider--wrap {
    flex-wrap: wrap;
  }

  .opt-slider__opt {
    flex: 1 1 auto;
    border: 0;
    border-radius: calc(var(--radius-lg, 12px) - 2px);
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

  .opt-slider__opt:hover {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 80%, transparent);
  }

  .opt-slider__opt--on {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 22%, var(--color-bg, #121212));
    color: var(--color-accent, #c9a227);
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

  .btn--check-on {
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
  }

  @media (max-width: 520px) {
    .deadline-row {
      grid-template-columns: 1fr;
    }
  }
</style>
