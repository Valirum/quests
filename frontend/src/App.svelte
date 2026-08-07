<script>
  // Quests web UI — orchestrator (state, load, overlays)
  import { onMount } from 'svelte'
  import {
    deleteQuest,
    deleteQuestline,
    listCategories,
    listQuestlines,
    listQuests,
    updateQuest,
    updateQuestStep,
    fetchHealth,
  } from './lib/js/api.js'
  import { subscribeQuestEvents } from './lib/js/live.js'
  import { applyTheme, loadSavedTheme } from './lib/js/theme.js'
  import { questMatchesQuery } from './lib/js/search.js'
  import { OPEN_STATUSES } from './lib/js/questFormat.js'
  import { groupQuestsByCategory } from './lib/js/questGroups.js'
  import QuestModal from './lib/modals/QuestModal.svelte'
  import QuestlineModal from './lib/modals/QuestlineModal.svelte'
  import TemplatesModal from './lib/modals/TemplatesModal.svelte'
  import SettingsModal from './lib/modals/SettingsModal.svelte'
  import ConfirmModal from './lib/modals/ConfirmModal.svelte'
  import ContextMenu from './lib/ui/ContextMenu.svelte'
  import HeroPanel from './lib/blocks/HeroPanel.svelte'
  import JournalHeader from './lib/blocks/JournalHeader.svelte'
  import QuestSidebar from './lib/blocks/QuestSidebar.svelte'
  import QuestDetail from './lib/blocks/QuestDetail.svelte'

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
  let nowMs = $state(Date.now())

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
  let byCategory = $derived(
    groupQuestsByCategory(listedQuests, categories, questlines),
  )
  let selected = $derived(quests.find((q) => q.id === selectedId) ?? null)

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
      typeof line === 'number' ? questlines.find((l) => l.id === line) : line
    if (!row) return
    lineModalMode = 'edit'
    lineModalTarget = row
    lineModalOpen = true
  }

  function openEdit(quest = selected) {
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
      const saved = await updateQuestStep(selected.id, step.id, {
        progress_current: next,
      })
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
  <JournalHeader
    {view}
    {liveStatus}
    {health}
    onViewChange={(v) => (view = v)}
    onOpenSettings={openSettings}
    onOpenTemplates={openTemplates}
    onOpenCreateQuestline={openCreateQuestline}
    onOpenCreateQuest={() => openCreate()}
  />

  {#if error}
    <p class="banner-error" role="alert">{error}</p>
  {/if}

  {#if view === 'hero'}
    <div class="journal__hero">
      <HeroPanel active={view === 'hero'} nonce={heroNonce} />
    </div>
  {:else}
    <div class="journal__body">
      <QuestSidebar
        {loading}
        {quests}
        {matchedQuests}
        {listedQuests}
        {byCategory}
        bind:searchQuery
        bind:showAllQuests
        {selectedId}
        {categoryOpen}
        {lineOpen}
        {nowMs}
        onSelect={(id) => (selectedId = id)}
        onTogglePin={togglePin}
        onQuestContextMenu={openQuestContextMenu}
        onLineContextMenu={openLineContextMenu}
        onToggleCategory={toggleCategory}
        onToggleLine={toggleLine}
      />
      <QuestDetail
        {selected}
        {nowMs}
        {statusBusy}
        {deleting}
        {stepBusyId}
        {stepEditId}
        {stepEditValue}
        onToggleCompleted={toggleCompleted}
        onOpenEdit={() => openEdit()}
        onRequestDelete={requestDeleteSelected}
        onBumpStep={bumpStep}
        onBeginEditStep={beginEditStep}
        onStepEditKeydown={onStepEditKeydown}
        onStepEditBlur={onStepEditBlur}
        onStepEditInput={(v) => (stepEditValue = v)}
      />
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
  {health}
  {liveStatus}
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
