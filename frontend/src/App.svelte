<script>
  import { onMount } from 'svelte'
  import { deleteQuest, listQuests, updateQuest, updateQuestStep, QUEST_SIGNIFICANCES } from './lib/api.js'
  import { subscribeQuestEvents } from './lib/live.js'
  import { applyTheme, loadSavedTheme } from './lib/theme.js'
  import {
    formatLocal,
    formatRemaining,
    localTimeZone,
    remainingFromDeadline,
    timerTone,
  } from './lib/time.js'
  import QuestModal from './lib/QuestModal.svelte'
  import TemplatesModal from './lib/TemplatesModal.svelte'
  import ConfirmModal from './lib/ConfirmModal.svelte'
  import Icon from './lib/Icon.svelte'
  import { questMatchesQuery } from './lib/search.js'

  let quests = $state([])
  let selectedId = $state(null)
  let loading = $state(true)
  let error = $state('')
  let liveStatus = $state('off')
  let searchQuery = $state('')

  let modalOpen = $state(false)
  let modalMode = $state(/** @type {'create' | 'edit'} */ ('create'))
  let templatesOpen = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let statusBusy = $state(false)
  let pinBusyId = $state(/** @type {number | null} */ (null))
  let stepBusyId = $state(/** @type {number | null} */ (null))
  /** Prefer this id across in-flight load() (URL / HUD focus). */
  let pendingSelectId = $state(/** @type {number | null} */ (null))
  /** Open quests group (active / delayed). */
  let openQuestsOpen = $state(true)
  /** Closed quests group (completed / failed / archived). */
  let closedQuestsOpen = $state(false)

  const OPEN_STATUSES = new Set(['active', 'delayed'])
  const CLOSED_STATUSES = new Set(['completed', 'failed', 'archived'])

  let visibleQuests = $derived(
    quests.filter((q) => questMatchesQuery(q, searchQuery)),
  )
  let openQuests = $derived(
    visibleQuests.filter((q) => OPEN_STATUSES.has(q.status)),
  )
  let closedQuests = $derived(
    visibleQuests.filter((q) => CLOSED_STATUSES.has(q.status)),
  )
  let selected = $derived(quests.find((q) => q.id === selectedId) ?? null)
  let nowMs = $state(Date.now())

  function questTimer(q) {
    if (!q?.deadline_at) return null
    if (q.status === 'completed' || q.status === 'failed') return null
    const rem = remainingFromDeadline(q.deadline_at, nowMs)
    if (rem == null || rem <= 0) return null
    const tone = q.timer_tone || timerTone(rem, q.duration_seconds) || 'red'
    const remLabel = formatRemaining(rem)
    const durLabel =
      q.duration_seconds != null ? formatRemaining(q.duration_seconds) : null
    return {
      rem,
      label: remLabel,
      tone,
      detailLabel: durLabel ? `${remLabel} / ${durLabel}` : remLabel,
    }
  }

  let selectedTimer = $derived(questTimer(selected))

  function statusColor(status) {
    return `var(--color-status-${status}, var(--color-fg-muted, #9a9a9a))`
  }

  function formatDate(value) {
    return formatLocal(value)
  }

  const tzLabel = localTimeZone()

  async function load({ silent = false } = {}) {
    if (!silent) loading = true
    if (!silent) error = ''
    try {
      const next = await listQuests({})
      quests = next
      const prefer = pendingSelectId ?? selectedId ?? questIdFromUrl()
      if (prefer != null && next.some((q) => q.id === prefer)) {
        selectedId = prefer
        pendingSelectId = null
      } else if (!next.some((q) => q.id === selectedId)) {
        const visible = next.filter((q) => questMatchesQuery(q, searchQuery))
        selectedId = visible[0]?.id ?? next[0]?.id ?? null
      }
    } catch (e) {
      if (!silent) {
        error = e.message || String(e)
        quests = []
        selectedId = null
      }
    } finally {
      if (!silent) loading = false
    }
  }

  function openCreate() {
    modalMode = 'create'
    modalOpen = true
  }

  function openTemplates() {
    templatesOpen = true
  }

  function openEdit(quest = selected) {
    // `onclick={openEdit}` would pass MouseEvent as the first arg.
    const q = quest instanceof Event ? selected : quest || selected
    if (!q?.id) return
    selectedId = q.id
    modalMode = 'edit'
    modalOpen = true
  }

  function periodBadge(q) {
    if (!q?.template_id) return null
    const key = q.period_key || ''
    return key || 'цикл'
  }

  function significanceLabel(q) {
    const id = q?.significance || 'common'
    return QUEST_SIGNIFICANCES.find((s) => s.id === id)?.label || 'обычное'
  }

  function requestDeleteSelected() {
    if (!selected || deleting) return
    deleteConfirmOpen = true
  }

  async function confirmDeleteSelected() {
    if (!selected || deleting) return
    deleting = true
    error = ''
    try {
      const id = selected.id
      await deleteQuest(id)
      deleteConfirmOpen = false
      onDeleted(id)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      deleting = false
    }
  }

  async function toggleCompleted() {
    if (!selected || statusBusy) return
    statusBusy = true
    error = ''
    try {
      const next = selected.status === 'completed' ? 'active' : 'completed'
      const saved = await updateQuest(selected.id, { status: next })
      applyQuest(saved)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      statusBusy = false
    }
  }

  async function togglePin(quest, event) {
    event?.stopPropagation?.()
    event?.preventDefault?.()
    if (!quest || pinBusyId != null) return
    pinBusyId = quest.id
    error = ''
    try {
      const saved = await updateQuest(quest.id, { pinned: !quest.pinned })
      applyQuest(saved)
      // Keep selection / UI focus on the same card after unpin.
      selectQuestFromUi(saved.id, { pushUrl: false })
    } catch (e) {
      error = e.message || String(e)
    } finally {
      pinBusyId = null
    }
  }

  async function bumpStep(step, delta) {
    if (!selected || stepBusyId != null) return
    const next = Math.max(0, Math.min(step.progress_total, step.progress_current + delta))
    if (next === step.progress_current) return
    stepBusyId = step.id
    error = ''
    try {
      const saved = await updateQuestStep(selected.id, step.id, { progress_current: next })
      applyQuest(saved)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      stepBusyId = null
    }
  }

  function applyQuest(quest) {
    const idx = quests.findIndex((q) => q.id === quest.id)
    if (idx >= 0) {
      quests = quests.map((q) => (q.id === quest.id ? quest : q))
    } else {
      load({ silent: true })
    }
    selectedId = quest.id
  }

  function onSaved(quest) {
    selectedId = quest.id
    load({ silent: true })
  }

  function onDeleted(id) {
    if (selectedId === id) selectedId = null
    load({ silent: true })
  }

  function questIdFromUrl() {
    try {
      const raw = new URL(location.href).searchParams.get('quest')
      if (!raw) return null
      const id = Number(raw)
      return Number.isFinite(id) && id > 0 ? id : null
    } catch {
      return null
    }
  }

  function selectQuestFromUi(id, { pushUrl = true } = {}) {
    const n = Number(id)
    if (!Number.isFinite(n) || n <= 0) return
    pendingSelectId = n
    selectedId = n
    if (pushUrl) {
      const url = new URL(location.href)
      url.searchParams.set('quest', String(n))
      history.replaceState(null, '', url)
    }
    try {
      window.focus()
    } catch {
      /* browsers often block focus from background */
    }
  }

  onMount(() => {
    applyTheme(loadSavedTheme())
    const fromUrl = questIdFromUrl()
    if (fromUrl != null) {
      pendingSelectId = fromUrl
      selectedId = fromUrl
    }
    load()
    const tick = setInterval(() => {
      nowMs = Date.now()
    }, 1000)
    const stop = subscribeQuestEvents(
      (msg) => {
        if (msg?.type === 'hello' && msg.pending_focus != null) {
          selectQuestFromUi(msg.pending_focus)
          return
        }
        if (msg?.type === 'ui_focus_quest' && msg.quest_id != null) {
          selectQuestFromUi(msg.quest_id)
          return
        }
        if (msg?.type === 'quests_changed') {
          load({ silent: true })
        }
      },
      { onStatus: (s) => (liveStatus = s) },
    )
    return () => {
      clearInterval(tick)
      stop()
    }
  })
</script>

<div class="journal">
  <header class="journal__header">
    <div class="brand">
      <span class="brand__mark" aria-hidden="true">◈</span>
      <h1 class="brand__title">Задачи</h1>
    </div>
    <div class="header-actions">
      <span
        class="live"
        data-status={liveStatus}
        title={`Live sync: ${liveStatus}`}
        aria-label={`Live sync: ${liveStatus}`}
      >
        <span class="live__dot" aria-hidden="true"></span>
        <span class="live__text">{liveStatus}</span>
      </span>
      <input
        class="search"
        type="search"
        placeholder="Поиск…"
        bind:value={searchQuery}
        aria-label="Поиск по названию, описанию, шагам, статусу"
      />
      <button type="button" class="btn" onclick={openTemplates} aria-label="Шаблоны периодики">
        <Icon name="renew" />
        <span class="btn__text">Шаблоны</span>
      </button>
      <button type="button" class="btn btn--accent" onclick={openCreate} aria-label="Новый квест">
        <Icon name="add" />
        <span class="btn__text">Новый квест</span>
      </button>
    </div>
  </header>

  {#if error}
    <p class="banner-error" role="alert">{error}</p>
  {/if}

  <div class="journal__body">
    <aside class="sidebar">
      <div class="sidebar__list" aria-label="Список квестов">
        {#if loading}
          <p class="empty">Загрузка…</p>
        {:else if quests.length === 0}
          <p class="empty">Квестов нет</p>
        {:else if visibleQuests.length === 0}
          <p class="empty">Ничего не найдено</p>
        {:else}
          {#snippet questRow(q)}
            {@const rowTimer = questTimer(q)}
            <button
              type="button"
              class="quest-row"
              class:quest-row--active={q.id === selectedId}
              class:quest-row--pinned={q.pinned}
              onclick={() => (selectedId = q.id)}
              oncontextmenu={(e) => {
                e.preventDefault()
                openEdit(q)
              }}
            >
              <span class="quest-row__top">
                <span class="quest-row__title">{q.title}</span>
                <span
                  class="pin-btn"
                  class:pin-btn--on={q.pinned}
                  role="button"
                  tabindex="0"
                  title={q.pinned ? 'Открепить' : 'В избранное'}
                  aria-label={q.pinned ? 'Открепить' : 'В избранное'}
                  onclick={(e) => togglePin(q, e)}
                  onkeydown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') togglePin(q, e)
                  }}
                >
                  <Icon name={q.pinned ? 'pin-filled' : 'pin'} size={14} />
                </span>
              </span>
              {#if q.significance && q.significance !== 'common'}
                <span class="quest-row__sig">
                  <span class="sig-badge" data-sig={q.significance}>{significanceLabel(q)}</span>
                </span>
              {/if}
              <span class="quest-row__meta">
                <span class="quest-row__meta-left">
                  <span class="status" style:color={statusColor(q.status)}>{q.status}</span>
                  {#if periodBadge(q)}
                    <span class="period-badge" title="Периодический инстанс">{periodBadge(q)}</span>
                  {/if}
                  {#if rowTimer}
                    <span class="row-timer" data-tone={rowTimer.tone}>{rowTimer.label}</span>
                  {/if}
                </span>
                <span class="progress">{q.progress_label}</span>
              </span>
            </button>
          {/snippet}

          {#if openQuests.length > 0}
            <div class="quest-group">
              <button
                type="button"
                class="quest-group__toggle"
                aria-expanded={openQuestsOpen}
                onclick={() => (openQuestsOpen = !openQuestsOpen)}
              >
                <span class="quest-group__label">Активные</span>
                <span class="quest-group__hint">{openQuests.length}</span>
                <span class="quest-group__chevron" aria-hidden="true">
                  <Icon name={openQuestsOpen ? 'chevron-down' : 'chevron-right'} size={14} />
                </span>
              </button>
              {#if openQuestsOpen}
                <div class="quest-group__body">
                  {#each openQuests as q (q.id)}
                    {@render questRow(q)}
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          {#if closedQuests.length > 0}
            <div class="quest-group">
              <button
                type="button"
                class="quest-group__toggle"
                aria-expanded={closedQuestsOpen}
                onclick={() => (closedQuestsOpen = !closedQuestsOpen)}
              >
                <span class="quest-group__label">Завершённые</span>
                <span class="quest-group__hint">{closedQuests.length}</span>
                <span class="quest-group__chevron" aria-hidden="true">
                  <Icon name={closedQuestsOpen ? 'chevron-down' : 'chevron-right'} size={14} />
                </span>
              </button>
              {#if closedQuestsOpen}
                <div class="quest-group__body">
                  {#each closedQuests as q (q.id)}
                    {@render questRow(q)}
                  {/each}
                </div>
              {/if}
            </div>
          {/if}

          {#if openQuests.length === 0 && closedQuests.length === 0}
            <p class="empty">Ничего не найдено</p>
          {/if}
        {/if}
      </div>
    </aside>

    <section class="detail" aria-live="polite">
      {#if !selected}
        <div class="detail__empty">
          <p>Выбери квест слева — или создай новый.</p>
        </div>
      {:else}
        <header class="detail__head">
          <div class="detail__head-row">
            <p class="detail__eyebrow">
              <span class="status" style:color={statusColor(selected.status)}
                >{selected.status}</span
              >
              {#if selected.pinned}
                <span class="pinned-label">PINNED</span>
              {/if}
              {#if selected.significance}
                <span class="sig-badge" data-sig={selected.significance}
                  >{significanceLabel(selected)}</span
                >
              {/if}
              {#if periodBadge(selected)}
                <span class="period-badge" title="Период">{periodBadge(selected)}</span>
              {/if}
              <span class="progress">{selected.progress_label}</span>
            </p>
            <div class="detail__actions">
              <button
                type="button"
                class="btn"
                class:btn--done={selected.status !== 'completed'}
                class:btn--reactivate={selected.status === 'completed'}
                onclick={toggleCompleted}
                disabled={statusBusy}
                aria-label={
                  selected.status === 'completed' ? 'Сделать активным' : 'Отметить выполненным'
                }
              >
                <Icon name={selected.status === 'completed' ? 'renew' : 'checkmark'} />
                <span class="btn__text">
                  {#if statusBusy}
                    …
                  {:else if selected.status === 'completed'}
                    Активно
                  {:else}
                    Выполнено
                  {/if}
                </span>
              </button>
              <button
                type="button"
                class="btn btn--accent"
                onclick={() => openEdit()}
                aria-label="Править"
              >
                <Icon name="edit" />
                <span class="btn__text">Править</span>
              </button>
              <button
                type="button"
                class="btn btn--danger"
                onclick={requestDeleteSelected}
                disabled={deleting}
                aria-label={deleting ? 'Удаление…' : 'Удалить'}
              >
                <Icon name="delete" />
                <span class="btn__text">{deleting ? '…' : 'Удалить'}</span>
              </button>
            </div>
          </div>
          <h2 class="detail__title">{selected.title}</h2>
        </header>

        {#if selected.description}
          <div class="block">
            <h3 class="block__label">Описание</h3>
            <p class="block__body">{selected.description}</p>
          </div>
        {:else}
          <div class="block">
            <h3 class="block__label">Описание</h3>
            <p class="block__body block__body--muted">Нет описания</p>
          </div>
        {/if}

        <div class="block">
          <h3 class="block__label">Шаги</h3>
          {#if selected.steps?.length}
            <ol class="step-list">
              {#each selected.steps as step (step.id)}
                <li class="step" class:step--done={step.done}>
                  <span class="step__mark">{step.done ? '✓' : '○'}</span>
                  <span class="step__main">
                    <span class="step__title">{step.title}</span>
                    {#if step.check_command}
                      <span class="step__auto" title={step.check_command}
                        >auto {step.check_interval_seconds || '?'}s</span
                      >
                    {/if}
                  </span>
                  <div class="step__controls">
                    <button
                      type="button"
                      class="step__btn"
                      aria-label="Уменьшить прогресс"
                      disabled={stepBusyId != null || step.progress_current <= 0}
                      onclick={() => bumpStep(step, -1)}
                    >
                      <Icon name="subtract" size={14} />
                    </button>
                    <span class="step__progress"
                      >{step.progress_current}/{step.progress_total}</span
                    >
                    <button
                      type="button"
                      class="step__btn"
                      aria-label="Увеличить прогресс"
                      disabled={
                        stepBusyId != null || step.progress_current >= step.progress_total
                      }
                      onclick={() => bumpStep(step, 1)}
                    >
                      <Icon name="add" size={14} />
                    </button>
                  </div>
                  {#if step.description}
                    <p class="step__desc">{step.description}</p>
                  {/if}
                </li>
              {/each}
            </ol>
          {:else}
            <p class="block__body block__body--muted">Шагов нет</p>
          {/if}
        </div>

        <dl class="dates">
          <div>
            <dt>Создан ({tzLabel})</dt>
            <dd>{formatDate(selected.created_at)}</dd>
          </div>
          <div>
            <dt>Обновлён ({tzLabel})</dt>
            <dd>{formatDate(selected.updated_at)}</dd>
          </div>
          {#if selected.deadline_at}
            <div>
              <dt>Срок ({tzLabel})</dt>
              <dd>{formatDate(selected.deadline_at)}</dd>
            </div>
          {/if}
        </dl>

        {#if selectedTimer}
          <div class="deadline-timer" data-tone={selectedTimer.tone}>
            <span class="deadline-timer__label">До срока</span>
            <span class="deadline-timer__value">{selectedTimer.detailLabel}</span>
          </div>
        {/if}
      {/if}
    </section>
  </div>
</div>

<QuestModal
  open={modalOpen}
  mode={modalMode}
  quest={modalMode === 'edit' ? selected : null}
  onClose={() => (modalOpen = false)}
  onSaved={onSaved}
  onDeleted={onDeleted}
/>

<TemplatesModal
  open={templatesOpen}
  onClose={() => (templatesOpen = false)}
  onChanged={() => load({ silent: true })}
/>

<ConfirmModal
  open={deleteConfirmOpen}
  title="Удалить квест?"
  message={selected ? `Удалить квест «${selected.title}»?` : ''}
  busy={deleting}
  onCancel={() => {
    if (!deleting) deleteConfirmOpen = false
  }}
  onConfirm={confirmDeleteSelected}
/>

<style>
  .journal {
    display: grid;
    grid-template-rows: auto auto 1fr;
    height: 100%;
    min-height: 100%;
    background:
      radial-gradient(
        ellipse 80% 50% at 10% -10%,
        color-mix(in srgb, var(--color-accent, #c9a227) 8%, transparent),
        transparent 55%
      ),
      var(--color-bg, #121212);
  }

  .journal__header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    min-height: var(--header-height, 3.25rem);
    padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 92%, transparent);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    min-height: 2.25rem;
  }

  .brand__mark {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    color: var(--color-accent, #c9a227);
    font-size: 1.15rem;
    line-height: 1;
    transform: translateY(0.02em);
  }

  .brand__title {
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-xl, 1.6rem);
    font-weight: 700;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    line-height: 1;
    color: var(--color-accent, #c9a227);
  }

  .header-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font-family: var(--font-ui, sans-serif);
  }

  .live {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    height: 2.25rem;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    line-height: 1;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .live__dot {
    width: 0.55rem;
    height: 0.55rem;
    border-radius: 50%;
    background: currentColor;
    box-shadow: 0 0 0 1px color-mix(in srgb, currentColor 35%, transparent);
  }

  .live[data-status='live'] {
    color: var(--color-success, #7a9e3a);
  }

  .live[data-status='reconnect'],
  .live[data-status='connecting'] {
    color: var(--color-warning, #c47a20);
  }

  .live[data-status='off'] {
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .banner-error {
    margin: 0;
    padding: var(--space-2, 0.5rem) var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 18%, var(--color-bg, #121212));
    color: var(--color-danger, #b54a3a);
    border-bottom: 1px solid
      color-mix(in srgb, var(--color-danger, #b54a3a) 40%, var(--color-border, #333));
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .journal__body {
    display: grid;
    grid-template-columns: minmax(16rem, var(--sidebar-width, 20rem)) 1fr;
    min-height: 0;
    height: 100%;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-right: 1px solid var(--color-border, #333);
    background: var(--color-bg-raised, #1a1a1a);
  }

  .sidebar__list {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .search {
    box-sizing: border-box;
    height: 2.25rem;
    min-width: 12rem;
    max-width: 18rem;
    padding: 0 var(--space-3, 0.75rem);
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
    line-height: 1;
  }

  .search::placeholder {
    color: var(--color-fg-muted, #9a9a9a);
  }

  .search:focus {
    outline: 1px solid var(--color-accent, #c9a227);
    outline-offset: 1px;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2, 0.5rem);
    box-sizing: border-box;
    height: 2.25rem;
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
    padding: 0 var(--space-3, 0.75rem);
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    cursor: pointer;
  }

  .btn:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .btn--accent {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, var(--color-bg-muted, #242424));
    color: var(--color-accent, #c9a227);
  }

  .btn--accent:hover {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 28%, var(--color-bg-muted, #242424));
  }

  .btn--done {
    border-color: color-mix(in srgb, var(--color-success, #7a9e3a) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-success, #7a9e3a) 20%, var(--color-bg-muted, #242424));
    color: color-mix(in srgb, var(--color-success, #7a9e3a) 85%, var(--color-fg, #e8e8e8));
  }

  .btn--done:hover {
    background: color-mix(in srgb, var(--color-success, #7a9e3a) 32%, var(--color-bg-muted, #242424));
  }

  .btn--reactivate {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, var(--color-bg-muted, #242424));
    color: var(--color-accent, #c9a227);
  }

  .btn--reactivate:hover {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 28%, var(--color-bg-muted, #242424));
  }

  .quest-group {
    border-bottom: 1px solid var(--color-border, #333);
  }

  .quest-group + .quest-group {
    border-top: 0;
  }

  .quest-group__toggle {
    display: grid;
    grid-template-columns: 1fr auto auto;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    width: 100%;
    margin: 0;
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    border: 0;
    background: var(--color-bg-muted, #242424);
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .quest-group__toggle:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .quest-group__label {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .quest-group__hint {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    font-variant-numeric: tabular-nums;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-group__chevron {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.25rem;
    height: 1.25rem;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .quest-row {
    display: grid;
    gap: var(--space-1, 0.25rem);
    width: 100%;
    padding: var(--space-3, 0.75rem) var(--space-3, 0.75rem);
    border: 0;
    border-bottom: 1px solid var(--color-border, #333);
    border-left: 3px solid transparent;
    background: transparent;
    text-align: left;
    color: inherit;
    cursor: pointer;
  }

  .quest-row:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .quest-row--active {
    border-left-color: var(--color-accent, #c9a227);
    background: color-mix(in srgb, var(--color-accent, #c9a227) 10%, var(--color-bg-raised, #1a1a1a));
  }

  .quest-row__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2, 0.5rem);
  }

  .quest-row__title {
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
    font-weight: 600;
    color: var(--color-fg, #e8e8e8);
    min-width: 0;
  }

  .quest-row__sig {
    display: block;
  }

  .quest-row__meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-2, 0.5rem);
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .quest-row__meta-left {
    display: inline-flex;
    align-items: baseline;
    gap: var(--space-2, 0.5rem);
    min-width: 0;
  }

  .row-timer {
    font-variant-numeric: tabular-nums;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .row-timer[data-tone='green'] {
    color: #8ec07c;
  }

  .row-timer[data-tone='orange'] {
    color: #fabd2f;
  }

  .row-timer[data-tone='red'] {
    color: #fb4934;
  }

  .pin-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 1.25rem;
    height: 1.25rem;
    margin: 0;
    padding: 0;
    border: 0;
    background: transparent;
    color: var(--color-accent, #c9a227);
    opacity: 0;
    cursor: pointer;
  }

  .quest-row:hover .pin-btn,
  .pin-btn--on,
  .pin-btn:focus-visible {
    opacity: 1;
  }

  .pin-btn:hover {
    color: color-mix(in srgb, var(--color-accent, #c9a227) 80%, #fff);
  }

  .pinned-label {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent, #c9a227);
  }

  .period-badge {
    font-family: var(--font-mono, monospace);
    font-size: 0.65rem;
    letter-spacing: 0.04em;
    font-variant-numeric: tabular-nums;
    color: var(--color-fg-muted, #9a9a9a);
    border: 1px solid var(--color-border, #333);
    border-radius: 2px;
    padding: 0.05rem 0.35rem;
  }

  .sig-badge {
    font-family: var(--font-mono, monospace);
    font-size: 0.65rem;
    letter-spacing: 0.06em;
    text-transform: lowercase;
    border: 1px solid currentColor;
    border-radius: 2px;
    padding: 0.05rem 0.35rem;
  }

  .sig-badge[data-sig='common'] {
    color: #9a9a9a;
  }
  .sig-badge[data-sig='uncommon'] {
    color: #8ec07c;
  }
  .sig-badge[data-sig='epic'] {
    color: #d3869b;
  }
  .sig-badge[data-sig='legendary'] {
    color: #fe8019;
  }

  .progress {
    font-variant-numeric: tabular-nums;
  }

  .empty,
  .detail__empty {
    padding: var(--space-5, 1.5rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .detail {
    overflow-y: auto;
    min-height: 0;
    padding: var(--space-5, 1.5rem) var(--space-6, 2rem);
  }

  .detail__head {
    margin-bottom: var(--space-5, 1.5rem);
    padding-bottom: var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
  }

  .detail__head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    margin-bottom: var(--space-2, 0.5rem);
  }

  .detail__actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2, 0.5rem);
    flex-shrink: 0;
  }

  .btn--danger {
    border-color: color-mix(in srgb, var(--color-danger, #b54a3a) 50%, var(--color-border, #333));
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 12%, var(--color-bg-muted, #242424));
  }

  .btn--danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 22%, var(--color-bg-muted, #242424));
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .detail__eyebrow {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3, 0.75rem);
    margin: 0;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .detail__title {
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: clamp(1.4rem, 2.5vw, 2rem);
    font-weight: 700;
    line-height: 1.2;
    color: var(--color-fg, #e8e8e8);
  }

  .block {
    margin-bottom: var(--space-5, 1.5rem);
  }

  .block__label {
    margin: 0 0 var(--space-2, 0.5rem);
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-accent-dim, #9a7b1a);
  }

  .block__body {
    margin: 0;
    white-space: pre-wrap;
  }

  .block__body--muted {
    color: var(--color-fg-subtle, #6e6e6e);
    font-style: italic;
  }

  .step-list {
    margin: 0;
    padding: 0;
    list-style: none;
    display: grid;
    gap: var(--space-2, 0.5rem);
  }

  .step {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: var(--space-1, 0.25rem) var(--space-3, 0.75rem);
    padding: var(--space-3, 0.75rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-md, 4px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 80%, transparent);
  }

  .step--done .step__title {
    color: var(--color-fg-muted, #9a9a9a);
    text-decoration: line-through;
  }

  .step__mark {
    color: var(--color-accent, #c9a227);
    font-family: var(--font-mono, monospace);
  }

  .step__main {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem 0.5rem;
    min-width: 0;
  }

  .step__title {
    font-weight: 600;
  }

  .step__auto {
    flex-shrink: 0;
    font-family: var(--font-mono, monospace);
    font-size: 0.65rem;
    letter-spacing: 0.04em;
    color: var(--color-fg-muted, #9a9a9a);
    border: 1px solid var(--color-border, #333);
    border-radius: 2px;
    padding: 0.05rem 0.3rem;
  }

  .step__controls {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1, 0.25rem);
  }

  .step__btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.6rem;
    height: 1.6rem;
    padding: 0;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    cursor: pointer;
  }

  .step__btn:hover:not(:disabled) {
    background: var(--color-bg-hover, #2a2a2a);
    border-color: var(--color-accent, #c9a227);
    color: var(--color-accent, #c9a227);
  }

  .step__btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .step__progress {
    min-width: 2.75rem;
    text-align: center;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-variant-numeric: tabular-nums;
  }

  .step__desc {
    grid-column: 2 / -1;
    margin: 0;
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .dates {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: var(--space-4, 1rem);
    margin: var(--space-6, 2rem) 0 0;
    padding-top: var(--space-4, 1rem);
    border-top: 1px dashed var(--color-border, #333);
    font-family: var(--font-ui, sans-serif);
  }

  .dates dt {
    margin: 0 0 var(--space-1, 0.25rem);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .dates dd {
    margin: 0;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .deadline-timer {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    margin-top: var(--space-5, 1.5rem);
    padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-md, 4px);
    font-family: var(--font-mono, monospace);
    background: color-mix(in srgb, var(--tone, var(--color-fg-muted)) 12%, var(--color-bg-raised, #1a1a1a));
    border-color: color-mix(in srgb, var(--tone, var(--color-border)) 55%, var(--color-border, #333));
  }

  .deadline-timer[data-tone='green'] {
    --tone: var(--color-success, #7a9e3a);
  }

  .deadline-timer[data-tone='orange'] {
    --tone: var(--color-warning, #c47a20);
  }

  .deadline-timer[data-tone='red'] {
    --tone: var(--color-danger, #b54a3a);
  }

  .deadline-timer__label {
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .deadline-timer__value {
    font-size: var(--text-lg, 1.25rem);
    font-weight: 700;
    font-variant-numeric: tabular-nums;
    color: var(--tone, var(--color-fg));
  }

  @media (max-width: 760px) {
    .journal__body {
      grid-template-columns: 1fr;
      grid-template-rows: minmax(12rem, 40vh) 1fr;
    }

    .sidebar {
      border-right: 0;
      border-bottom: 1px solid var(--color-border, #333);
    }
  }

  @media (orientation: portrait) {
    .btn__text,
    .live__text {
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

    .btn {
      width: 2.25rem;
      padding: 0;
      gap: 0;
    }

    .live {
      width: 2.25rem;
      justify-content: center;
      gap: 0;
    }

    .live__dot {
      width: 0.65rem;
      height: 0.65rem;
    }

    .search {
      min-width: 0;
      flex: 1 1 8rem;
      max-width: none;
    }

    .header-actions {
      flex: 1 1 auto;
      justify-content: flex-end;
    }
  }
</style>
