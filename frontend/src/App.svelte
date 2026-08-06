<script>
  // Quests web UI
  import { onMount } from 'svelte'
  import { deleteQuest, deleteQuestline, listCategories, listQuestlines, listQuests, updateQuest, updateQuestStep, fetchHealth, QUEST_SIGNIFICANCES } from './lib/api.js'
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
  import QuestlineModal from './lib/QuestlineModal.svelte'
  import TemplatesModal from './lib/TemplatesModal.svelte'
  import SettingsModal from './lib/SettingsModal.svelte'
  import ConfirmModal from './lib/ConfirmModal.svelte'
  import ContextMenu from './lib/ContextMenu.svelte'
  import HeroPanel from './lib/HeroPanel.svelte'
  import Icon from './lib/Icon.svelte'
  import { questMatchesQuery } from './lib/search.js'

  let quests = $state([])
  let selectedId = $state(null)
  let loading = $state(true)
  let error = $state('')
  let liveStatus = $state('off')
  /** @type {{ api: string, overlay: string, telegram: string, detail?: Record<string, any> }} */
  let health = $state({ api: 'unknown', overlay: 'unknown', telegram: 'unknown' })
  let searchQuery = $state('')
  /** @type {'journal' | 'hero'} */
  let view = $state('journal')
  /** Bump to refresh hero silently after quest events. */
  let heroNonce = $state(0)
  /** @type {{ id: number, slug: string, label: string, sort_order: number, color?: string }[]} */
  let categories = $state([])
  /** @type {{ id: number, title: string, category_id?: number | null, color?: string, icon?: string }[]} */
  let questlines = $state([])
  /** Open state for category subgroups: `${bucket}:${key}` → boolean (default true). */
  let categoryOpen = $state(/** @type {Record<string, boolean>} */ ({}))
  /** Open state for questline subgroups: `${bucket}:${catKey}:${lineKey}` → boolean. */
  let lineOpen = $state(/** @type {Record<string, boolean>} */ ({}))

  let modalOpen = $state(false)
  let modalMode = $state(/** @type {'create' | 'edit'} */ ('create'))
  /** Prefill when creating from questline context menu. */
  let modalDefaults = $state(
    /** @type {{ questline_id?: number | null, category_id?: number | null } | null} */ (null),
  )
  let templatesOpen = $state(false)
  let settingsOpen = $state(false)
  let lineModalOpen = $state(false)
  let lineModalMode = $state(/** @type {'create' | 'edit'} */ ('create'))
  let lineModalTarget = $state(/** @type {any | null} */ (null))
  let ctxOpen = $state(false)
  let ctxX = $state(0)
  let ctxY = $state(0)
  /** @type {'line' | 'quest' | null} */
  let ctxKind = $state(null)
  let ctxLineId = $state(/** @type {number | null} */ (null))
  let ctxQuestId = $state(/** @type {number | null} */ (null))
  let lineDeleteConfirmOpen = $state(false)
  let lineDeleting = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let statusBusy = $state(false)
  let pinBusyId = $state(/** @type {number | null} */ (null))
  let stepBusyId = $state(/** @type {number | null} */ (null))
  let stepEditId = $state(/** @type {number | null} */ (null))
  let stepEditValue = $state('')
  /** Prefer this id across in-flight load() (URL / HUD focus). */
  let pendingSelectId = $state(/** @type {number | null} */ (null))
  /** When false — only active/delayed; when true — all statuses. */
  let showAllQuests = $state(false)

  const OPEN_STATUSES = new Set(['active', 'delayed'])

  let ctxItems = $derived.by(() => {
    if (ctxKind === 'line') {
      return [
        { id: 'add', label: 'Добавить квест' },
        { id: 'edit', label: 'Редактировать' },
        { id: 'delete', label: 'Удалить', danger: true },
      ]
    }
    if (ctxKind === 'quest') {
      return [
        { id: 'edit', label: 'Редактировать' },
        { id: 'sep-delay', sep: true },
        { id: 'delay-15', label: 'Отложить на 15 мин' },
        { id: 'delay-30', label: 'Отложить на 30 мин' },
        { id: 'delay-60', label: 'Отложить на 60 мин' },
        { id: 'sep-status', sep: true },
        { id: 'complete', label: 'Выполнено' },
        { id: 'fail', label: 'Провалено' },
        { id: 'sep-danger', sep: true },
        { id: 'delete', label: 'Удалить', danger: true },
      ]
    }
    return []
  })

  let matchedQuests = $derived(
    quests.filter((q) => questMatchesQuery(q, searchQuery)),
  )
  let listedQuests = $derived(
    showAllQuests
      ? matchedQuests
      : matchedQuests.filter((q) => OPEN_STATUSES.has(q.status)),
  )
  let byCategory = $derived(groupQuestsByCategory(listedQuests))
  let selected = $derived(quests.find((q) => q.id === selectedId) ?? null)
  let nowMs = $state(Date.now())

  function isQuestInactive(q) {
    return !OPEN_STATUSES.has(q?.status)
  }

  function groupQuestsByCategory(list) {
    /** @type {Map<string, any[]>} */
    const buckets = new Map()
    for (const q of list) {
      const key = q.category_id != null ? `c${q.category_id}` : 'none'
      if (!buckets.has(key)) buckets.set(key, [])
      buckets.get(key).push(q)
    }
    const ordered = []
    const sortedCats = [...categories].sort(
      (a, b) => (a.sort_order ?? 0) - (b.sort_order ?? 0) || a.id - b.id,
    )
    for (const c of sortedCats) {
      const key = `c${c.id}`
      if (!buckets.has(key)) continue
      ordered.push({
        key,
        label: c.label,
        color: c.color || '#9a9a9a',
        ...partitionByQuestline(buckets.get(key)),
      })
      buckets.delete(key)
    }
    for (const [key, items] of buckets) {
      if (key === 'none') continue
      ordered.push({
        key,
        label: items[0]?.category_label || 'Раздел',
        color: items[0]?.category_color || '#9a9a9a',
        ...partitionByQuestline(items),
      })
    }
    if (buckets.has('none')) {
      ordered.push({
        key: 'none',
        label: 'Без раздела',
        color: null,
        ...partitionByQuestline(buckets.get('none')),
      })
    }
    return ordered
  }

  function partitionByQuestline(items) {
    /** @type {Map<number, any[]>} */
    const byLine = new Map()
    const alone = []
    for (const q of items) {
      if (q.questline_id != null) {
        const id = Number(q.questline_id)
        if (!byLine.has(id)) byLine.set(id, [])
        byLine.get(id).push(q)
      } else {
        alone.push(q)
      }
    }
    const lineById = new Map(questlines.map((l) => [l.id, l]))
    const lines = []
    for (const [id, quests] of byLine) {
      const meta = lineById.get(id)
      const sorted = [...quests].sort((a, b) => {
        const ta = a.created_at || ''
        const tb = b.created_at || ''
        if (ta !== tb) return ta < tb ? -1 : 1
        return (a.id || 0) - (b.id || 0)
      })
      lines.push({
        key: `ql${id}`,
        id,
        title: meta?.title || quests[0]?.questline_title || 'Квестлайн',
        color: meta?.color || quests[0]?.questline_color || '#9a9a9a',
        icon: meta?.icon || quests[0]?.questline_icon || 'document',
        category_id: meta?.category_id ?? quests[0]?.category_id ?? null,
        quests: sorted,
      })
    }
    lines.sort((a, b) => a.title.localeCompare(b.title, 'ru') || a.id - b.id)
    alone.sort((a, b) => {
      const ta = a.created_at || ''
      const tb = b.created_at || ''
      if (ta !== tb) return ta < tb ? -1 : 1
      return (a.id || 0) - (b.id || 0)
    })
    return { lines, alone, questCount: items.length }
  }

  function isCategoryOpen(key) {
    return categoryOpen[key] !== false
  }

  function toggleCategory(key) {
    categoryOpen = { ...categoryOpen, [key]: !isCategoryOpen(key) }
  }

  function isLineOpen(catKey, lineKey) {
    const id = `${catKey}:${lineKey}`
    return lineOpen[id] !== false
  }

  function toggleLine(catKey, lineKey) {
    const id = `${catKey}:${lineKey}`
    lineOpen = { ...lineOpen, [id]: !isLineOpen(catKey, lineKey) }
  }

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
      const [next, cats, lines] = await Promise.all([
        listQuests({}),
        listCategories(),
        listQuestlines(),
      ])
      quests = next
      categories = Array.isArray(cats) ? cats : []
      questlines = Array.isArray(lines) ? lines : []
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

  function openCreate(defaults = null) {
    modalMode = 'create'
    modalDefaults =
      defaults && !(defaults instanceof Event)
        ? {
            questline_id: defaults.questline_id ?? null,
            category_id: defaults.category_id ?? null,
          }
        : null
    modalOpen = true
  }

  function openTemplates() {
    templatesOpen = true
  }

  function openSettings() {
    settingsOpen = true
  }

  function openCreateQuestline() {
    lineModalMode = 'create'
    lineModalTarget = null
    lineModalOpen = true
  }

  function openEditQuestline(line) {
    const row =
      typeof line === 'number'
        ? questlines.find((l) => l.id === line)
        : line
    if (!row) return
    lineModalMode = 'edit'
    lineModalTarget = row
    lineModalOpen = true
  }

  function openEdit(quest = selected) {
    // `onclick={openEdit}` would pass MouseEvent as the first arg.
    const q = quest instanceof Event ? selected : quest || selected
    if (!q?.id) return
    selectedId = q.id
    modalMode = 'edit'
    modalDefaults = null
    modalOpen = true
  }

  function openLineContextMenu(event, line) {
    event.preventDefault()
    event.stopPropagation()
    ctxKind = 'line'
    ctxLineId = line.id
    ctxQuestId = null
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function openQuestContextMenu(event, quest) {
    event.preventDefault()
    event.stopPropagation()
    ctxKind = 'quest'
    ctxQuestId = quest.id
    ctxLineId = null
    selectedId = quest.id
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function closeContextMenu() {
    ctxOpen = false
    ctxKind = null
  }

  function onLineContextSelect(action) {
    const line = questlines.find((l) => l.id === ctxLineId)
    if (!line && action !== 'delete') return
    if (action === 'add') {
      openCreate({
        questline_id: ctxLineId,
        category_id: line?.category_id ?? null,
      })
      return
    }
    if (action === 'edit') {
      openEditQuestline(line)
      return
    }
    if (action === 'delete') {
      lineDeleteConfirmOpen = true
    }
  }

  async function patchQuestStatus(quest, status) {
    if (!quest || statusBusy) return
    statusBusy = true
    error = ''
    try {
      const saved = await updateQuest(quest.id, { status })
      applyQuest(saved)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      statusBusy = false
    }
  }

  async function postponeQuest(quest, minutes) {
    if (!quest || statusBusy) return
    statusBusy = true
    error = ''
    try {
      const secs = Math.max(60, Math.round(Number(minutes) * 60))
      const deadline = new Date(Date.now() + secs * 1000).toISOString()
      const saved = await updateQuest(quest.id, {
        status: 'active',
        deadline_at: deadline,
        duration_seconds: secs,
      })
      applyQuest(saved)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      statusBusy = false
    }
  }

  function onQuestContextSelect(action) {
    const quest = quests.find((q) => q.id === ctxQuestId)
    if (!quest) return
    if (action === 'edit') {
      openEdit(quest)
      return
    }
    if (action === 'delay-15') {
      postponeQuest(quest, 15)
      return
    }
    if (action === 'delay-30') {
      postponeQuest(quest, 30)
      return
    }
    if (action === 'delay-60') {
      postponeQuest(quest, 60)
      return
    }
    if (action === 'complete') {
      patchQuestStatus(quest, 'completed')
      return
    }
    if (action === 'fail') {
      patchQuestStatus(quest, 'failed')
      return
    }
    if (action === 'delete') {
      selectedId = quest.id
      deleteConfirmOpen = true
    }
  }

  function onContextSelect(action) {
    if (ctxKind === 'line') {
      onLineContextSelect(action)
      return
    }
    if (ctxKind === 'quest') {
      onQuestContextSelect(action)
    }
  }

  async function confirmDeleteQuestline() {
    if (ctxLineId == null || lineDeleting) return
    lineDeleting = true
    error = ''
    try {
      await deleteQuestline(ctxLineId)
      lineDeleteConfirmOpen = false
      ctxLineId = null
      await load({ silent: true })
    } catch (e) {
      error = e.message || String(e)
    } finally {
      lineDeleting = false
    }
  }

  function onQuestlineSaved() {
    load({ silent: true })
  }

  function onQuestlineDeleted() {
    load({ silent: true })
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

  async function setStepProgress(step, value) {
    if (!selected || stepBusyId != null) return
    const total = Math.max(0, Number(step.progress_total) || 0)
    const next = Math.max(0, Math.min(total, Math.round(Number(value))))
    if (!Number.isFinite(next) || next === step.progress_current) {
      stepEditId = null
      return
    }
    stepBusyId = step.id
    error = ''
    try {
      const saved = await updateQuestStep(selected.id, step.id, { progress_current: next })
      applyQuest(saved)
    } catch (e) {
      error = e.message || String(e)
    } finally {
      stepBusyId = null
      stepEditId = null
    }
  }

  async function bumpStep(step, delta) {
    await setStepProgress(step, step.progress_current + delta)
  }

  function beginEditStep(step) {
    if (stepBusyId != null) return
    stepEditId = step.id
    stepEditValue = String(step.progress_current)
  }

  function cancelEditStep() {
    stepEditId = null
  }

  function onStepEditKeydown(event, step) {
    if (event.key === 'Enter') {
      event.preventDefault()
      setStepProgress(step, stepEditValue)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      cancelEditStep()
    }
  }

  function onStepEditBlur(step) {
    if (stepEditId !== step.id) return
    setStepProgress(step, stepEditValue)
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

  async function refreshHealth() {
    try {
      const data = await fetchHealth()
      const comps = data?.components || {}
      health = {
        api: data?.api?.status === 'ok' ? 'ok' : 'offline',
        overlay: comps.overlay?.status === 'ok' ? 'ok' : 'offline',
        telegram: comps.telegram?.status === 'ok' ? 'ok' : 'offline',
        detail: data,
      }
    } catch {
      health = { api: 'offline', overlay: 'unknown', telegram: 'unknown' }
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
    refreshHealth()
    const tick = setInterval(() => {
      nowMs = Date.now()
    }, 1000)
    const healthTick = setInterval(refreshHealth, 5000)
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
          if (view === 'hero') heroNonce += 1
        }
      },
      { onStatus: (s) => (liveStatus = s) },
    )
    return () => {
      clearInterval(tick)
      clearInterval(healthTick)
      stop()
    }
  })
</script>

<div class="journal">
  <header class="journal__header">
    <div class="header-left">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true">◈</span>
        <h1 class="brand__title">{view === 'hero' ? 'Лист' : 'Задачи'}</h1>
      </div>
      <span
        class="live"
        data-status={liveStatus}
        title={`Live sync: ${liveStatus}`}
        aria-label={`Live sync: ${liveStatus}`}
      >
        <span class="live__dot" aria-hidden="true"></span>
        <span class="live__text">{liveStatus}</span>
      </span>
      <div class="health" role="status" aria-label="Состояние сервисов">
        <span class="health__chip" data-status={health.api} title="API">
          <span class="health__dot" aria-hidden="true"></span>
          <span class="health__label">API</span>
        </span>
        <span class="health__chip" data-status={health.overlay} title="HUD / оверлей">
          <span class="health__dot" aria-hidden="true"></span>
          <span class="health__label">HUD</span>
        </span>
        <span class="health__chip" data-status={health.telegram} title="Telegram-бот">
          <span class="health__dot" aria-hidden="true"></span>
          <span class="health__label">Bot</span>
        </span>
      </div>
    </div>
    <div class="view-tabs" role="tablist" aria-label="Раздел">
      <button
        type="button"
        class="view-tab"
        class:view-tab--on={view === 'journal'}
        role="tab"
        aria-selected={view === 'journal'}
        onclick={() => (view = 'journal')}
      >
        Журнал
      </button>
      <button
        type="button"
        class="view-tab"
        class:view-tab--on={view === 'hero'}
        role="tab"
        aria-selected={view === 'hero'}
        onclick={() => (view = 'hero')}
      >
        Лист
      </button>
    </div>
    <div class="header-actions">
      <button type="button" class="btn" onclick={openSettings} aria-label="Настройки">
        <Icon name="settings" />
        <span class="btn__text">Настройки</span>
      </button>
      {#if view === 'journal'}
        <button type="button" class="btn" onclick={openTemplates} aria-label="Шаблоны периодики">
          <Icon name="renew" />
          <span class="btn__text">Шаблоны</span>
        </button>
        <button type="button" class="btn" onclick={openCreateQuestline} aria-label="Новый квестлайн">
          <Icon name="flag" />
          <span class="btn__text">Квестлайн</span>
        </button>
        <button type="button" class="btn btn--accent" onclick={() => openCreate()} aria-label="Новый квест">
          <Icon name="add" />
          <span class="btn__text">Новый квест</span>
        </button>
      {/if}
    </div>
  </header>

  {#if error}
    <p class="banner-error" role="alert">{error}</p>
  {/if}

  {#if view === 'hero'}
    <div class="journal__hero">
      <HeroPanel active={view === 'hero'} nonce={heroNonce} />
    </div>
  {:else}
  <div class="journal__body">
    <aside class="sidebar">
      <div class="sidebar__tools">
        <input
          class="search"
          type="search"
          placeholder="Поиск…"
          bind:value={searchQuery}
          aria-label="Поиск по названию, разделу, квестлайну, описанию, шагам"
        />
        <label class="sidebar__filter">
          <input type="checkbox" bind:checked={showAllQuests} />
          <span>Показывать завершённые</span>
        </label>
      </div>
      <div class="sidebar__list" aria-label="Список квестов">
        {#if loading}
          <p class="empty">Загрузка…</p>
        {:else if quests.length === 0}
          <p class="empty">Квестов нет</p>
        {:else if matchedQuests.length === 0}
          <p class="empty">Ничего не найдено</p>
        {:else if listedQuests.length === 0}
          <p class="empty">Нет активных — включи «Показывать завершённые»</p>
        {:else}
          {#snippet questRow(q)}
            {@const rowTimer = questTimer(q)}
            <button
              type="button"
              class="quest-row"
              class:quest-row--active={q.id === selectedId}
              class:quest-row--pinned={q.pinned}
              class:quest-row--inactive={isQuestInactive(q)}
              onclick={() => (selectedId = q.id)}
              oncontextmenu={(e) => openQuestContextMenu(e, q)}
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

          {#snippet categoryBody(g)}
            {#if g.lines.length === 0}
              {#each g.alone as q (q.id)}
                {@render questRow(q)}
              {/each}
            {:else}
              {#each g.lines as line (line.key)}
                <div
                  class="quest-line"
                  style="--line-color: {line.color || '#9a9a9a'}"
                >
                  <button
                    type="button"
                    class="quest-line__toggle"
                    aria-expanded={isLineOpen(g.key, line.key)}
                    onclick={() => toggleLine(g.key, line.key)}
                    oncontextmenu={(e) => openLineContextMenu(e, line)}
                  >
                    <span class="quest-line__icon" aria-hidden="true">
                      <Icon name={line.icon || 'document'} size={12} />
                    </span>
                    <span class="quest-line__label">{line.title}</span>
                    <span class="quest-line__hint">{line.quests.length}</span>
                    <span class="quest-line__chevron" aria-hidden="true">
                      <Icon
                        name={isLineOpen(g.key, line.key) ? 'chevron-down' : 'chevron-right'}
                        size={12}
                      />
                    </span>
                  </button>
                  {#if isLineOpen(g.key, line.key)}
                    <div class="quest-line__body">
                      {#each line.quests as q (q.id)}
                        {@render questRow(q)}
                      {/each}
                    </div>
                  {/if}
                </div>
              {/each}
              {#if g.alone.length > 0}
                <div class="quest-line quest-line--alone">
                  <div class="quest-line__alone-label">Без квестлайна</div>
                  <div class="quest-line__body">
                    {#each g.alone as q (q.id)}
                      {@render questRow(q)}
                    {/each}
                  </div>
                </div>
              {/if}
            {/if}
          {/snippet}

          {#each byCategory as g (g.key)}
            <div
              class="quest-subgroup"
              class:quest-subgroup--plain={g.key === 'none'}
              style={g.color ? `--cat-color: ${g.color}` : undefined}
            >
              <button
                type="button"
                class="quest-subgroup__toggle"
                aria-expanded={isCategoryOpen(g.key)}
                onclick={() => toggleCategory(g.key)}
              >
                <span class="quest-subgroup__swatch" aria-hidden="true"></span>
                <span class="quest-subgroup__label">{g.label}</span>
                <span class="quest-subgroup__hint">{g.questCount}</span>
                <span class="quest-subgroup__chevron" aria-hidden="true">
                  <Icon
                    name={isCategoryOpen(g.key) ? 'chevron-down' : 'chevron-right'}
                    size={12}
                  />
                </span>
              </button>
              {#if isCategoryOpen(g.key)}
                <div class="quest-subgroup__body">
                  {@render categoryBody(g)}
                </div>
              {/if}
            </div>
          {/each}
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
              {#if selected.category_label}
                <span class="period-badge" title="Раздел">{selected.category_label}</span>
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
                class="btn"
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
                    {#if stepEditId === step.id}
                      <input
                        class="step__progress-input"
                        type="number"
                        min="0"
                        max={step.progress_total}
                        step="1"
                        value={stepEditValue}
                        disabled={stepBusyId != null}
                        aria-label="Прогресс шага"
                        autofocus
                        oninput={(e) => (stepEditValue = e.currentTarget.value)}
                        onkeydown={(e) => onStepEditKeydown(e, step)}
                        onblur={() => onStepEditBlur(step)}
                        onfocus={(e) => e.currentTarget.select()}
                      />
                      <span class="step__progress-total">/{step.progress_total}</span>
                    {:else}
                      <button
                        type="button"
                        class="step__progress"
                        title="Двойной клик — задать значение"
                        disabled={stepBusyId != null}
                        ondblclick={() => beginEditStep(step)}
                      >
                        {step.progress_current}/{step.progress_total}
                      </button>
                    {/if}
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
  {/if}
</div>

<QuestModal
  open={modalOpen}
  mode={modalMode}
  quest={modalMode === 'edit' ? selected : null}
  defaults={modalMode === 'create' ? modalDefaults : null}
  onClose={() => {
    modalOpen = false
    modalDefaults = null
  }}
  onSaved={onSaved}
  onDeleted={onDeleted}
/>

<QuestlineModal
  open={lineModalOpen}
  mode={lineModalMode}
  line={lineModalMode === 'edit' ? lineModalTarget : null}
  onClose={() => {
    lineModalOpen = false
    lineModalTarget = null
  }}
  onSaved={onQuestlineSaved}
  onDeleted={onQuestlineDeleted}
/>

<TemplatesModal
  open={templatesOpen}
  onClose={() => (templatesOpen = false)}
  onChanged={() => load({ silent: true })}
/>

<SettingsModal
  open={settingsOpen}
  onClose={() => (settingsOpen = false)}
  health={health}
  liveStatus={liveStatus}
/>

<ContextMenu
  open={ctxOpen}
  x={ctxX}
  y={ctxY}
  items={ctxItems}
  onSelect={onContextSelect}
  onClose={closeContextMenu}
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

<ConfirmModal
  open={lineDeleteConfirmOpen}
  title="Удалить квестлайн?"
  message="Квесты останутся, но отвяжутся от линии."
  busy={lineDeleting}
  onCancel={() => {
    if (!lineDeleting) lineDeleteConfirmOpen = false
  }}
  onConfirm={confirmDeleteQuestline}
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
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
    align-items: center;
    gap: var(--space-3, 0.75rem);
    min-height: var(--header-height, 3.25rem);
    padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 92%, transparent);
  }

  .header-left {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3, 0.75rem);
    min-width: 0;
    justify-self: start;
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
    justify-content: flex-end;
    gap: var(--space-2, 0.5rem);
    justify-self: end;
    font-family: var(--font-ui, sans-serif);
  }

  .view-tabs {
    display: inline-flex;
    justify-self: center;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    overflow: hidden;
    background: var(--color-bg-muted, #242424);
  }

  .view-tab {
    border: 0;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.45rem 0.95rem;
    cursor: pointer;
    font: inherit;
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .view-tab + .view-tab {
    border-left: 1px solid var(--color-border, #333);
  }

  .view-tab--on {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 16%, transparent);
    color: var(--color-accent, #c9a227);
  }

  .journal__hero {
    min-height: 0;
    overflow: auto;
  }

  .live {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    height: 2.25rem;
    flex-shrink: 0;
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

  .health {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    flex-shrink: 0;
  }

  .health__chip {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    height: 1.65rem;
    padding: 0 0.45rem;
    border: 1px solid var(--color-border, #333);
    border-radius: 999px;
    font-family: var(--font-mono, monospace);
    font-size: 0.65rem;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .health__dot {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 50%;
    background: currentColor;
  }

  .health__chip[data-status='ok'] {
    color: var(--color-success, #7a9e3a);
    border-color: color-mix(in srgb, var(--color-success, #7a9e3a) 40%, var(--color-border, #333));
  }

  .health__chip[data-status='offline'] {
    color: var(--color-danger, #b54a3a);
    border-color: color-mix(in srgb, var(--color-danger, #b54a3a) 40%, var(--color-border, #333));
  }

  .health__chip[data-status='unknown'] {
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

  .sidebar__tools {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    flex-shrink: 0;
    padding: 0.55rem 0.75rem 0.45rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .sidebar__filter {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    margin: 0;
    padding: 0.1rem 0.05rem 0.15rem;
    border: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    cursor: pointer;
    user-select: none;
  }

  .sidebar__filter input {
    accent-color: var(--color-accent, #c9a227);
  }

  .sidebar__list {
    flex: 1;
    overflow-y: auto;
    min-height: 0;
  }

  .search {
    box-sizing: border-box;
    width: 100%;
    height: 2.25rem;
    padding: 0 var(--space-3, 0.75rem);
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
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
    border-radius: var(--radius-lg, 12px);
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

  /* Detail header actions: text-only, less color noise */
  .detail__actions .btn {
    background: transparent;
    border-color: transparent;
    color: var(--color-fg, #e8e8e8);
  }

  .detail__actions .btn:hover:not(:disabled) {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .detail__actions .btn--danger {
    color: var(--color-danger, #b54a3a);
    background: transparent;
    border-color: transparent;
  }

  .detail__actions .btn--danger:hover:not(:disabled) {
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 14%, transparent);
  }

  .quest-subgroup {
    display: grid;
    gap: 0.15rem;
    border-left: 2px solid var(--cat-color, var(--color-border-strong, #4a4a4a));
    background: color-mix(
      in srgb,
      var(--cat-color, var(--color-bg-muted, #242424)) 10%,
      transparent
    );
    border-radius: 0 var(--radius-sm, 2px) var(--radius-sm, 2px) 0;
    padding: 0.15rem 0 0.2rem;
  }

  .quest-subgroup--plain {
    border-left-color: var(--color-border, #333);
    background: color-mix(in srgb, var(--color-bg-muted, #242424) 55%, transparent);
  }

  .quest-subgroup + .quest-subgroup {
    margin-top: 0.45rem;
  }

  .quest-subgroup__toggle {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    gap: 0.35rem;
    width: 100%;
    border: 0;
    background: transparent;
    color: inherit;
    padding: 0.25rem 0.55rem;
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .quest-subgroup__swatch {
    width: 0.45rem;
    height: 0.45rem;
    border-radius: 1px;
    background: var(--cat-color, var(--color-fg-subtle, #6e6e6e));
    flex-shrink: 0;
  }

  .quest-subgroup--plain .quest-subgroup__swatch {
    background: var(--color-fg-subtle, #6e6e6e);
    opacity: 0.55;
  }

  .quest-subgroup__label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: color-mix(in srgb, var(--cat-color, var(--color-fg-muted, #9a9a9a)) 70%, #e8e8e8);
  }

  .quest-subgroup--plain .quest-subgroup__label {
    color: var(--color-fg-muted, #9a9a9a);
  }

  .quest-subgroup__hint {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-subgroup__chevron {
    display: inline-flex;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-subgroup__body {
    display: grid;
  }

  .quest-line {
    display: grid;
    gap: 0.1rem;
    margin: 0.15rem 0.2rem 0.25rem;
    border-left: 2px solid var(--line-color, var(--color-border, #333));
    background: color-mix(in srgb, var(--line-color, #9a9a9a) 8%, transparent);
    border-radius: 0 var(--radius-sm, 2px) var(--radius-sm, 2px) 0;
  }

  .quest-line + .quest-line {
    margin-top: 0.35rem;
  }

  .quest-line--alone {
    border-left-color: var(--color-border, #333);
    background: transparent;
  }

  .quest-line__toggle {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    gap: 0.3rem;
    width: 100%;
    border: 0;
    background: transparent;
    color: inherit;
    padding: 0.22rem 0.45rem;
    cursor: pointer;
    font: inherit;
    text-align: left;
  }

  .quest-line__icon {
    display: inline-flex;
    color: var(--line-color, var(--color-fg-muted, #9a9a9a));
  }

  .quest-line__label {
    font-size: var(--text-xs, 0.75rem);
    color: color-mix(in srgb, var(--line-color, #9a9a9a) 55%, #e8e8e8);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .quest-line__hint {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-line__chevron {
    display: inline-flex;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-line__alone-label {
    padding: 0.2rem 0.45rem;
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .quest-line__body {
    display: grid;
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

  .quest-row--inactive {
    opacity: 0.62;
  }

  .quest-row--inactive .quest-row__title {
    text-decoration: line-through;
    color: var(--color-fg-muted, #9a9a9a);
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
    padding: 0;
    border: none;
    background: transparent;
    cursor: text;
  }

  .step__progress:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .step__progress-input {
    width: 3.25rem;
    min-width: 0;
    text-align: center;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    font-variant-numeric: tabular-nums;
    color: var(--color-fg, #e8e8e8);
    background: var(--color-bg-muted, #242424);
    border: 1px solid var(--color-accent, #c9a227);
    border-radius: var(--radius-sm, 2px);
    padding: 0.1rem 0.2rem;
  }

  .step__progress-input:focus {
    outline: none;
  }

  .step__progress-total {
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
    align-items: center;
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
    .journal__header {
      grid-template-columns: minmax(0, 1fr) auto;
      grid-template-areas:
        "left actions"
        "tabs tabs";
    }

    .header-left {
      grid-area: left;
    }

    .header-actions {
      grid-area: actions;
      gap: var(--space-1, 0.25rem);
    }

    .view-tabs {
      grid-area: tabs;
      display: flex;
      width: 100%;
      justify-self: stretch;
    }

    .view-tab {
      flex: 1 1 0;
      text-align: center;
    }

    .btn__text,
    .live__text,
    .health__label {
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

    .health__chip {
      padding: 0 0.35rem;
    }
  }
</style>
