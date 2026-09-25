<script>
  // Quests web UI — orchestrator (state, load, overlays)
  import { onMount } from 'svelte'
  import { cubicOut } from 'svelte/easing'
  import {
    deleteQuest,
    deleteQuestline,
    listCategories,
    listQuestlines,
    listQuests,
    listNotes,
    listAllAttachments,
    updateQuest,
    updateQuestStep,
    fetchHealth,
    fetchAuthState,
    logout as apiLogout,
    setUnauthorizedHandler,
  } from './lib/js/api.js'
  import { subscribeQuestEvents } from './lib/js/live.js'
  import { seedAttachmentIndex, invalidateAttachmentLiveFlags, flattenAttachmentIndex } from './lib/js/attachmentCache.js'
  import { applyTheme, loadSavedTheme } from './lib/js/theme.js'
  import { questMatchesQuery } from './lib/js/search.js'
  import { OPEN_STATUSES } from './lib/js/questFormat.js'
  import { groupQuestsByCategory } from './lib/js/questGroups.js'
  import { copyText } from './lib/js/clipboard.js'
  import { statusToastLabel, toast } from './lib/js/toasts.svelte.js'
  import ActionAssistantModal from './lib/modals/ActionAssistantModal.svelte'
  import QuestModal from './lib/modals/QuestModal.svelte'
  import StepModal from './lib/modals/StepModal.svelte'
  import QuestlineModal from './lib/modals/QuestlineModal.svelte'
  import TemplatesModal from './lib/modals/TemplatesModal.svelte'
  import SettingsModal from './lib/modals/SettingsModal.svelte'
  import ConfirmModal from './lib/modals/ConfirmModal.svelte'
  import ContextMenu from './lib/ui/ContextMenu.svelte'
  import ToastHost from './lib/ui/ToastHost.svelte'
  import HeroPanel from './lib/blocks/HeroPanel.svelte'
  import StatsPanel from './lib/blocks/StatsPanel.svelte'
  import JournalHeader from './lib/blocks/JournalHeader.svelte'
  import QuestSidebar from './lib/blocks/QuestSidebar.svelte'
  import QuestDetail from './lib/blocks/QuestDetail.svelte'
  import ActivityCalendar from './lib/blocks/ActivityCalendar.svelte'
  import TocPage from './lib/blocks/TocPage.svelte'
  import NotesPage from './lib/blocks/NotesPage.svelte'
  import AttachmentsPage from './lib/blocks/AttachmentsPage.svelte'
  import LoginScreen from './lib/blocks/LoginScreen.svelte'

  /** Auth gate: null = still checking, true/false = decided. */
  let authed = $state(null)
  /** Whether this instance uses accounts at all (false on an open local one). */
  let authRequired = $state(false)
  let username = $state('')
  /** Cleanup for the live subscription + timers, so logout can tear them down. */
  let stopApp = null

  let quests = $state([])
  let notes = $state([])
  /** @type {Record<string, any> | null} */
  let attachmentIndex = $state(null)
  let selectedId = $state(null)
  let selectedNoteId = $state(/** @type {number | null} */ (null))
  let selectedAttachmentId = $state(/** @type {number | null} */ (null))
  let loading = $state(true)
  let error = $state('')
  let liveStatus = $state('off')
  /** @type {{ api: string, overlay: string, telegram: string, webdav: string, detail?: Record<string, any> }} */
  let health = $state({
    api: 'unknown',
    overlay: 'unknown',
    telegram: 'unknown',
    webdav: 'unknown',
  })
  let searchQuery = $state('')
  /** @type {'journal' | 'toc' | 'notes' | 'attachments' | 'calendar' | 'hero' | 'stats'} */
  let view = $state('journal')
  /** Sidebar visibility per view that has one — remembered across reloads. */
  let sidebarCollapsed = $state(loadSidebarCollapsed())

  function loadSidebarCollapsed() {
    try {
      const raw = JSON.parse(localStorage.getItem('quests.sidebarCollapsed') || '{}')
      return { journal: !!raw.journal, notes: !!raw.notes }
    } catch {
      return { journal: false, notes: false }
    }
  }

  function toggleSidebar(key) {
    setSidebarCollapsed(key, !sidebarCollapsed[key])
  }

  function setSidebarCollapsed(key, value) {
    if (sidebarCollapsed[key] === value) return
    sidebarCollapsed = { ...sidebarCollapsed, [key]: value }
    try {
      localStorage.setItem('quests.sidebarCollapsed', JSON.stringify(sidebarCollapsed))
    } catch {
      /* ignore */
    }
  }

  /** Below this, the sidebar/list takes the full screen instead of a side column. */
  const NARROW_SIDEBAR_BREAKPOINT = '(max-width: 480px)'

  function isNarrowViewport() {
    try {
      return window.matchMedia(NARROW_SIDEBAR_BREAKPOINT).matches
    } catch {
      return false
    }
  }

  /** On a full-screen sidebar, picking an item should reveal it, not leave the list covering it. */
  function revealDetailOnNarrow(key) {
    if (isNarrowViewport()) setSidebarCollapsed(key, true)
  }

  /** …and going back to the list should bring it back, not leave an empty detail pane. */
  function revealListOnNarrow(key) {
    if (isNarrowViewport()) setSidebarCollapsed(key, false)
  }
  /** Bump to refresh hero silently after quest events. */
  let heroNonce = $state(0)
  /** Bump to refresh stats silently after quest events. */
  let statsNonce = $state(0)
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
  let assistantOpen = $state(false)
  let lineModalOpen = $state(false)
  let lineModalMode = $state(/** @type {'create' | 'edit'} */ ('create'))
  let lineModalTarget = $state(/** @type {any | null} */ (null))
  let ctxOpen = $state(false)
  let ctxX = $state(0)
  let ctxY = $state(0)
  /** @type {'line' | 'quest' | 'step' | null} */
  let ctxKind = $state(null)
  let ctxLineId = $state(/** @type {number | null} */ (null))
  let ctxQuestId = $state(/** @type {number | null} */ (null))
  let ctxStepId = $state(/** @type {number | null} */ (null))
  let lineDeleteConfirmOpen = $state(false)
  let lineDeleting = $state(false)
  let deleting = $state(false)
  let deleteConfirmOpen = $state(false)
  let statusBusy = $state(false)
  let pinBusyId = $state(/** @type {number | null} */ (null))
  let stepBusyId = $state(/** @type {number | null} */ (null))
  let stepEditId = $state(/** @type {number | null} */ (null))
  let stepEditQuestId = $state(/** @type {number | null} */ (null))
  let stepEditValue = $state('')
  let stepModalOpen = $state(false)
  let stepModalQuestId = $state(/** @type {number | null} */ (null))
  let stepModalStep = $state(/** @type {any | null} */ (null))
  /** Prefer this id across in-flight load() (URL / HUD focus). */
  let pendingSelectId = $state(/** @type {number | null} */ (null))
  /** When false — only active/delayed; when true — all statuses. */
  let showAllQuests = $state(false)
  let nowMs = $state(Date.now())

  let ctxItems = $derived.by(() => {
    if (ctxKind === 'line') {
      return [
        { id: 'copy-id', label: `Копировать questline=${ctxLineId}` },
        { id: 'sep-copy', sep: true },
        { id: 'add', label: 'Добавить квест' },
        { id: 'edit', label: 'Редактировать' },
        { id: 'delete', label: 'Удалить', danger: true },
      ]
    }
    if (ctxKind === 'quest') {
      return [
        { id: 'copy-id', label: `Копировать quest=${ctxQuestId}` },
        { id: 'sep-copy', sep: true },
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
    if (ctxKind === 'step') {
      const found = findStepRef(ctxStepId)
      const total = Math.max(1, Number(found?.step?.progress_total) || 1)
      /** @type {{ id: string, label?: string, sep?: boolean, danger?: boolean }[]} */
      const items = [{ id: 'copy-id', label: `Копировать step=${ctxStepId}` }]
      if (total > 1) {
        items.push(
          { id: 'sep-bump', sep: true },
          { id: 'inc', label: '+1' },
          { id: 'dec', label: '−1' },
        )
      }
      items.push(
        { id: 'sep-done', sep: true },
        { id: 'complete', label: 'Выполнить' },
        { id: 'reset', label: 'Обнулить' },
        { id: 'sep-edit', sep: true },
        { id: 'edit', label: 'Редактировать' },
      )
      return items
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
  let attachments = $derived(flattenAttachmentIndex(attachmentIndex))
  let refLabels = $derived.by(() => {
    /** @type {Record<string, string>} */
    const m = {}
    for (const n of notes) m[`note:${n.id}`] = n.title || `note=${n.id}`
    for (const q of quests) {
      m[`quest:${q.id}`] = q.title || `quest=${q.id}`
      for (const s of q.steps || []) {
        m[`step:${s.id}`] = s.title || `step=${s.id}`
      }
    }
    for (const l of questlines) m[`questline:${l.id}`] = l.title || `questline=${l.id}`
    for (const a of attachments) {
      m[`attachment:${a.id}`] = a.filename || `attachment=${a.id}`
    }
    return m
  })

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
      const [next, cats, lines, nextNotes, attIndex] = await Promise.all([
        listQuests({}),
        listCategories(),
        listQuestlines(),
        listNotes().catch(() => []),
        listAllAttachments().catch(() => null),
      ])
      quests = next
      notes = Array.isArray(nextNotes) ? nextNotes : []
      attachmentIndex = attIndex && typeof attIndex === 'object' ? attIndex : null
      categories = Array.isArray(cats) ? cats : []
      questlines = Array.isArray(lines) ? lines : []
      if (attIndex) {
        seedAttachmentIndex(attIndex, {
          questIds: next.map((q) => q.id),
          questlineIds: questlines.map((l) => l.id),
          noteIds: notes.map((n) => n.id),
        })
      }
      const prefer = pendingSelectId ?? selectedId ?? questIdFromUrl()
      if (prefer != null && next.some((q) => q.id === prefer)) {
        selectedId = prefer
        pendingSelectId = null
      } else if (selectedId != null && !next.some((q) => q.id === selectedId)) {
        selectedId = null
      }
      const preferNote = selectedNoteId ?? noteIdFromUrl()
      if (preferNote != null && notes.some((n) => n.id === preferNote)) {
        selectedNoteId = preferNote
      } else if (selectedNoteId != null && !notes.some((n) => n.id === selectedNoteId)) {
        selectedNoteId = null
      }
      const flatAtt = flattenAttachmentIndex(attachmentIndex)
      const preferAtt = selectedAttachmentId ?? attachmentIdFromUrl()
      if (preferAtt != null && flatAtt.some((a) => a.id === preferAtt)) {
        selectedAttachmentId = preferAtt
      } else if (selectedAttachmentId != null && !flatAtt.some((a) => a.id === selectedAttachmentId)) {
        selectedAttachmentId = null
      }
    } catch (e) {
      if (!silent) {
        error = e.message || String(e)
        quests = []
        notes = []
        attachmentIndex = null
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
    ctxStepId = null
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
    ctxStepId = null
    selectedId = quest.id
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function openStepContextMenu(event, step) {
    event.preventDefault()
    event.stopPropagation()
    ctxKind = 'step'
    ctxStepId = step.id
    ctxQuestId = findQuestIdForStep(step.id) ?? selectedId
    ctxLineId = null
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function closeContextMenu() {
    ctxOpen = false
    ctxKind = null
  }

  async function copyIdToClipboard(kind, id) {
    if (id == null) return
    try {
      const text = `${kind}=${id}`
      await copyText(text)
      toast(`Скопировано ${text}`, { kind: 'success', ttl: 1600 })
    } catch (e) {
      error = e?.message || String(e)
      toast(error, { kind: 'error' })
    }
  }

  function onLineContextSelect(action) {
    if (action === 'copy-id') {
      copyIdToClipboard('questline', ctxLineId)
      return
    }
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
      toast(`Статус: ${statusToastLabel(status)}`, { kind: 'success' })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
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
      toast(`Отложен на ${minutes} мин`, { kind: 'success' })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
    } finally {
      statusBusy = false
    }
  }

  function onQuestContextSelect(action) {
    if (action === 'copy-id') {
      copyIdToClipboard('quest', ctxQuestId)
      return
    }
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
      return
    }
    if (ctxKind === 'step') {
      onStepContextSelect(action)
    }
  }

  async function onStepContextSelect(action) {
    if (action === 'copy-id') {
      copyIdToClipboard('step', ctxStepId)
      return
    }
    const found = findStepRef(ctxStepId)
    if (!found) return
    const { step, questId } = found
    if (action === 'inc') {
      await bumpStep(step, 1, questId)
      return
    }
    if (action === 'dec') {
      await bumpStep(step, -1, questId)
      return
    }
    if (action === 'complete') {
      await setStepProgress(step, step.progress_total, questId)
      return
    }
    if (action === 'reset') {
      await setStepProgress(step, 0, questId)
      return
    }
    if (action === 'edit') {
      stepModalQuestId = questId
      stepModalStep = step
      stepModalOpen = true
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
      toast('Квестлайн удалён', { kind: 'success' })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
    } finally {
      lineDeleting = false
    }
  }

  function onQuestlineSaved(_line, meta = {}) {
    load({ silent: true })
    if (meta.mode === 'create') toast('Квестлайн создан', { kind: 'success' })
  }

  function onQuestlineDeleted() {
    load({ silent: true })
    toast('Квестлайн удалён', { kind: 'success' })
  }

  function requestDeleteSelected(quest = selected) {
    const q = quest || selected
    if (!q || deleting) return
    if (q.id !== selectedId) selectedId = q.id
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
      toast(error, { kind: 'error' })
    } finally {
      deleting = false
    }
  }

  async function toggleCompleted(quest = selected) {
    const q = quest || selected
    if (!q || statusBusy) return
    statusBusy = true
    error = ''
    try {
      const next = q.status === 'completed' ? 'active' : 'completed'
      const saved = await updateQuest(q.id, { status: next })
      applyQuest(saved, { select: false })
      toast(
        next === 'completed' ? 'Отмечен выполненным' : 'Снова активен',
        { kind: 'success' },
      )
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
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
      applyQuest(saved, { select: false })
      selectQuestFromUi(saved.id, { pushUrl: false })
    } catch (e) {
      error = e.message || String(e)
    } finally {
      pinBusyId = null
    }
  }

  async function setStepProgress(step, value, questId = null) {
    const qid = questId ?? selected?.id
    if (qid == null || stepBusyId != null) return
    const total = Math.max(0, Number(step.progress_total) || 0)
    const next = Math.max(0, Math.min(total, Math.round(Number(value))))
    if (!Number.isFinite(next) || next === step.progress_current) {
      stepEditId = null
      stepEditQuestId = null
      return
    }
    stepBusyId = step.id
    error = ''
    try {
      const saved = await updateQuestStep(qid, step.id, {
        progress_current: next,
      })
      applyQuest(saved, { select: false })
    } catch (e) {
      error = e.message || String(e)
    } finally {
      stepBusyId = null
      stepEditId = null
      stepEditQuestId = null
    }
  }

  async function bumpStep(step, delta, questId = null) {
    await setStepProgress(step, step.progress_current + delta, questId)
  }

  function beginEditStep(step, questId = null) {
    if (stepBusyId != null) return
    stepEditId = step.id
    stepEditQuestId = questId ?? findQuestIdForStep(step.id) ?? selected?.id ?? null
    stepEditValue = String(step.progress_current)
  }

  function cancelEditStep() {
    stepEditId = null
    stepEditQuestId = null
  }

  function findQuestIdForStep(stepId) {
    for (const q of quests) {
      if (q.steps?.some((s) => s.id === stepId)) return q.id
    }
    return null
  }

  function findStepRef(stepId) {
    for (const q of quests) {
      const step = q.steps?.find((s) => s.id === stepId)
      if (step) return { step, questId: q.id }
    }
    return null
  }

  function onStepEditKeydown(event, step) {
    if (event.key === 'Enter') {
      event.preventDefault()
      setStepProgress(step, stepEditValue, stepEditQuestId)
    } else if (event.key === 'Escape') {
      event.preventDefault()
      cancelEditStep()
    }
  }

  function onStepEditBlur(step) {
    if (stepEditId !== step.id) return
    setStepProgress(step, stepEditValue, stepEditQuestId)
  }

  function applyQuest(quest, { select = true } = {}) {
    const idx = quests.findIndex((q) => q.id === quest.id)
    if (idx >= 0) {
      quests = quests.map((q) => (q.id === quest.id ? quest : q))
    } else {
      load({ silent: true })
    }
    if (select) selectedId = quest.id
  }

  function onSaved(quest, meta = {}) {
    selectedId = quest.id
    load({ silent: true })
    if (meta.mode === 'create') toast('Квест создан', { kind: 'success' })
  }

  function onDeleted(id) {
    if (selectedId === id) selectedId = null
    load({ silent: true })
    toast('Квест удалён', { kind: 'success' })
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

  function noteIdFromUrl() {
    try {
      const raw = new URL(location.href).searchParams.get('note')
      if (!raw) return null
      const id = Number(raw)
      return Number.isFinite(id) && id > 0 ? id : null
    } catch {
      return null
    }
  }

  function attachmentIdFromUrl() {
    try {
      const raw = new URL(location.href).searchParams.get('attachment')
      if (!raw) return null
      const id = Number(raw)
      return Number.isFinite(id) && id > 0 ? id : null
    } catch {
      return null
    }
  }

  function tabFromUrl() {
    try {
      const raw = new URL(location.href).searchParams.get('tab')
      if (
        raw === 'toc' ||
        raw === 'notes' ||
        raw === 'attachments' ||
        raw === 'calendar' ||
        raw === 'hero' ||
        raw === 'stats'
      ) {
        return raw
      }
    } catch {
      /* ignore */
    }
    return null
  }

  /** Rewrite the query from scratch — tab / quest= / note= / attachment= never share the bar. */
  function replaceSearch(params) {
    try {
      const qs = new URLSearchParams()
      for (const [key, value] of Object.entries(params)) {
        if (value != null && value !== '') qs.set(key, String(value))
      }
      const next = `${location.pathname}${qs.toString() ? `?${qs}` : ''}`
      if (next !== `${location.pathname}${location.search}`) {
        history.replaceState(null, '', next)
      }
    } catch {
      /* ignore */
    }
  }

  function searchForView(nextView) {
    if (nextView === 'journal') {
      return selectedId != null ? { quest: selectedId } : {}
    }
    if (nextView === 'notes') {
      return selectedNoteId != null ? { note: selectedNoteId } : { tab: 'notes' }
    }
    if (nextView === 'attachments') {
      return selectedAttachmentId != null
        ? { attachment: selectedAttachmentId }
        : { tab: 'attachments' }
    }
    return { tab: nextView }
  }

  // Header tab order; drives which way a tab switch slides.
  const TAB_ORDER = ['journal', 'toc', 'notes', 'attachments', 'calendar', 'hero', 'stats']
  let navDir = $state(1)

  /** Horizontal slide for tab switches: forward enters from the right, back from the left. */
  function slideTab(node, { dir, out = false }) {
    const sign = out ? -dir : dir
    return {
      duration: 220,
      easing: cubicOut,
      css: (t) => `transform: translateX(${(1 - t) * sign * 100}%)`,
    }
  }

  function setView(next) {
    const from = TAB_ORDER.indexOf(view)
    const to = TAB_ORDER.indexOf(next)
    if (from !== -1 && to !== -1 && from !== to) navDir = to > from ? 1 : -1
    view = next
    replaceSearch(searchForView(next))
  }

  function selectQuestFromUi(id, { pushUrl = true } = {}) {
    const n = Number(id)
    if (!Number.isFinite(n) || n <= 0) return
    pendingSelectId = n
    selectedId = n
    if (view !== 'journal') view = 'journal'
    if (pushUrl) replaceSearch({ quest: n })
    revealDetailOnNarrow('journal')
    try {
      window.focus()
    } catch {
      /* browsers often block focus from background */
    }
  }

  function selectNoteFromUi(id, { pushUrl = true } = {}) {
    const n = Number(id)
    if (!Number.isFinite(n) || n <= 0) {
      selectedNoteId = null
      if (pushUrl) replaceSearch(searchForView(view))
      revealListOnNarrow('notes')
      return
    }
    selectedNoteId = n
    if (view !== 'notes') view = 'notes'
    if (pushUrl) replaceSearch({ note: n })
    revealDetailOnNarrow('notes')
  }

  function selectAttachmentFromUi(id, { pushUrl = true } = {}) {
    const n = Number(id)
    if (!Number.isFinite(n) || n <= 0) {
      selectedAttachmentId = null
      if (pushUrl) replaceSearch(searchForView('attachments'))
      return
    }
    selectedAttachmentId = n
    if (view !== 'attachments') view = 'attachments'
    if (pushUrl) replaceSearch({ attachment: n })
  }

  function onJournalRef(kind, id) {
    if (kind === 'note') {
      selectNoteFromUi(id)
      return
    }
    if (kind === 'attachment') {
      selectAttachmentFromUi(id)
      return
    }
    if (kind === 'quest') {
      selectQuestFromUi(id)
      return
    }
    if (kind === 'questline') {
      const first = quests.find((q) => q.questline_id === id)
      if (first) selectQuestFromUi(first.id)
      else setView('journal')
      return
    }
    if (kind === 'step') {
      for (const q of quests) {
        if (q.steps?.some((s) => s.id === id)) {
          selectQuestFromUi(q.id)
          return
        }
      }
    }
  }

  function clearSelectedQuest({ pushUrl = true } = {}) {
    selectedId = null
    pendingSelectId = null
    if (pushUrl) replaceSearch(searchForView(view))
    revealListOnNarrow('journal')
  }

  async function refreshHealth() {
    try {
      const data = await fetchHealth()
      const comps = data?.components || {}
      const webdav = probeStatus(comps.webdav?.status)
      if (health.webdav !== 'unknown' && health.webdav !== webdav) {
        invalidateAttachmentLiveFlags()
      }
      health = {
        api: data?.api?.status === 'ok' ? 'ok' : 'offline',
        overlay: comps.overlay?.status === 'ok' ? 'ok' : 'offline',
        telegram: comps.telegram?.status === 'ok' ? 'ok' : 'offline',
        webdav,
        detail: data,
      }
    } catch {
      health = {
        api: 'offline',
        overlay: 'unknown',
        telegram: 'unknown',
        webdav: 'unknown',
      }
    }
  }

  function probeStatus(status) {
    if (status === 'ok') return 'ok'
    if (status === 'offline') return 'offline'
    return 'unknown'
  }

  /** Boots data loading and live updates. Only runs once authenticated. */
  function startApp() {
    const fromNote = noteIdFromUrl()
    const fromAtt = attachmentIdFromUrl()
    const fromTab = tabFromUrl()
    if (fromAtt != null) {
      selectedAttachmentId = fromAtt
      view = 'attachments'
    } else if (fromNote != null) {
      selectedNoteId = fromNote
      view = 'notes'
    } else if (fromTab) {
      view = fromTab
    }
    const fromUrl = questIdFromUrl()
    if (fromUrl != null && fromNote == null && fromAtt == null && fromTab == null) {
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
          if (view === 'stats') statsNonce += 1
        }
      },
      { onStatus: (s) => (liveStatus = s) },
    )
    return () => {
      clearInterval(tick)
      clearInterval(healthTick)
      stop()
    }
  }

  function onAuthenticated(name) {
    username = name
    authed = true
    stopApp = startApp()
  }

  async function doLogout() {
    try {
      await apiLogout()
    } catch {
      /* dropping the session locally is what matters */
    }
    if (stopApp) stopApp()
    stopApp = null
    quests = []
    notes = []
    attachmentIndex = null
    selectedId = null
    selectedNoteId = null
    selectedAttachmentId = null
    authed = false
  }

  onMount(() => {
    // Native swipe hosts (Android HubActivity, quest=192) drive tab switches
    // through this instead of a full page reload — keeps the header mounted
    // and lets setView()'s own transition animate the change.
    window.questsNav = {
      setTab: (name) => setView(name),
      currentTab: () => view,
    }

    applyTheme(loadSavedTheme())
    // A 401 from any later call means the session lapsed — fall back to login.
    setUnauthorizedHandler(() => {
      if (authed === false) return
      if (stopApp) stopApp()
      stopApp = null
      authed = false
    })

    let cancelled = false
    ;(async () => {
      let state
      try {
        state = await fetchAuthState()
      } catch {
        // Auth state is unreachable; treat as open so a local instance with a
        // temporarily unhappy API still renders its usual error banner.
        state = { auth_required: false, authenticated: true }
      }
      if (cancelled) return
      authRequired = !!state.auth_required
      if (state.auth_required && !state.authenticated) {
        authed = false
        loading = false
        return
      }
      username = state.username ?? ''
      authed = true
      stopApp = startApp()
    })()

    return () => {
      cancelled = true
      if (stopApp) stopApp()
      stopApp = null
    }
  })

  // Esc in journal (no modal): clear selection → empty detail prompt.
  $effect(() => {
    const onKey = (event) => {
      if (event.key !== 'Escape') return
      if (view !== 'journal') return
      if (modalOpen || lineModalOpen || templatesOpen || settingsOpen) return
      if (deleteConfirmOpen || lineDeleteConfirmOpen || ctxOpen) return
      if (view === 'notes') {
        if (selectedNoteId == null) return
        event.preventDefault()
        selectNoteFromUi(null)
        return
      }
      if (selectedId == null) return
      const t = event.target
      if (
        t instanceof HTMLElement &&
        (t.closest('input, textarea, select, [contenteditable="true"]') ||
          t.isContentEditable)
      ) {
        return
      }
      event.preventDefault()
      clearSelectedQuest()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })
</script>

{#if authed === false}
  <LoginScreen {onAuthenticated} />
{:else if authed === null}
  <div class="boot-gate"></div>
{:else}
<div class="journal">
  <JournalHeader
    {view}
    {liveStatus}
    {health}
    sidebarCollapsed={view === 'notes' ? sidebarCollapsed.notes : sidebarCollapsed.journal}
    onToggleSidebar={() => toggleSidebar(view === 'notes' ? 'notes' : 'journal')}
    onViewChange={(v) => setView(v)}
    onOpenSettings={openSettings}
    onOpenTemplates={openTemplates}
    onOpenCreateQuestline={openCreateQuestline}
    onOpenCreateQuest={() => openCreate()}
    onOpenAssistant={() => (assistantOpen = true)}
  />

  {#if error}
    <p class="banner-error" role="alert">{error}</p>
  {/if}

  <ToastHost />

  <div class="journal__stage">
  {#key view}
  <div
    class="journal__viewport"
    in:slideTab={{ dir: navDir }}
    out:slideTab={{ dir: navDir, out: true }}
  >
  {#if view === 'hero'}
    <div class="journal__hero">
      <HeroPanel active={view === 'hero'} nonce={heroNonce} />
    </div>
  {:else if view === 'stats'}
    <div class="journal__stats">
      <StatsPanel active={view === 'stats'} nonce={statsNonce} />
    </div>
  {:else if view === 'calendar'}
    <div class="journal__calendar">
      <ActivityCalendar {quests} onSelectQuest={selectQuestFromUi} />
    </div>
  {:else if view === 'toc'}
    <div class="journal__toc">
      <TocPage
        {matchedQuests}
        {categories}
        {questlines}
        bind:searchQuery
        {nowMs}
        onSelectQuest={selectQuestFromUi}
        onLineContextMenu={openLineContextMenu}
        onQuestContextMenu={openQuestContextMenu}
      />
    </div>
  {:else if view === 'notes'}
    <div class="journal__notes">
      <NotesPage
        {notes}
        {quests}
        {questlines}
        {attachments}
        selectedId={selectedNoteId}
        labels={refLabels}
        sidebarCollapsed={sidebarCollapsed.notes}
        onSelect={(id) => selectNoteFromUi(id)}
        onChanged={() => load({ silent: true })}
        onRef={onJournalRef}
      />
    </div>
  {:else if view === 'attachments'}
    <div class="journal__attachments">
      <AttachmentsPage
        {attachments}
        {quests}
        {questlines}
        {notes}
        selectedId={selectedAttachmentId}
        onSelect={(id) => selectAttachmentFromUi(id)}
        onOpenOwner={onJournalRef}
      />
    </div>
  {:else}
    <div class="journal__body" class:journal__body--sidebar-collapsed={sidebarCollapsed.journal}>
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
        onSelect={(id) => selectQuestFromUi(id)}
        onTogglePin={togglePin}
        onQuestContextMenu={openQuestContextMenu}
        onLineContextMenu={openLineContextMenu}
        onToggleCategory={toggleCategory}
        onToggleLine={toggleLine}
      />
      <QuestDetail
        {selected}
        {quests}
        {showAllQuests}
        {nowMs}
        {statusBusy}
        {deleting}
        {stepBusyId}
        {stepEditId}
        {stepEditValue}
        onToggleCompleted={toggleCompleted}
        onOpenEdit={(q) => openEdit(q)}
        onRequestDelete={requestDeleteSelected}
        onBumpStep={bumpStep}
        onBeginEditStep={beginEditStep}
        onStepEditKeydown={onStepEditKeydown}
        onStepEditBlur={onStepEditBlur}
        onStepEditInput={(v) => (stepEditValue = v)}
        onQuestTitleContextMenu={openQuestContextMenu}
        onLineHeadContextMenu={(e) => {
          const line = questlines.find((l) => l.id === selected?.questline_id)
          if (line) openLineContextMenu(e, line)
        }}
        onStepContextMenu={openStepContextMenu}
        onSelectQuest={(id) => selectQuestFromUi(id)}
        labels={refLabels}
        onRef={onJournalRef}
        notes={notes}
        {questlines}
      />
    </div>
  {/if}
  </div>
  {/key}
  </div>
</div>

<QuestModal
  open={modalOpen}
  mode={modalMode}
  quest={modalMode === 'edit' ? selected : null}
  defaults={modalMode === 'create' ? modalDefaults : null}
  {quests}
  {notes}
  {attachments}
  onClose={() => {
    modalOpen = false
    modalDefaults = null
  }}
  onSaved={onSaved}
  onDeleted={onDeleted}
/>

<StepModal
  open={stepModalOpen}
  questId={stepModalQuestId}
  step={stepModalStep}
  {quests}
  {questlines}
  {notes}
  {attachments}
  onClose={() => {
    stepModalOpen = false
    stepModalStep = null
    stepModalQuestId = null
  }}
  onSaved={(q) => applyQuest(q, { select: false })}
/>

<QuestlineModal
  open={lineModalOpen}
  mode={lineModalMode}
  line={lineModalMode === 'edit' ? lineModalTarget : null}
  {quests}
  {questlines}
  {notes}
  {attachments}
  onClose={() => {
    lineModalOpen = false
    lineModalTarget = null
  }}
  onSaved={onQuestlineSaved}
  onDeleted={onQuestlineDeleted}
/>

<TemplatesModal
  open={templatesOpen}
  {quests}
  {notes}
  {attachments}
  onClose={() => (templatesOpen = false)}
  onChanged={() => load({ silent: true })}
/>

<SettingsModal
  open={settingsOpen}
  onClose={() => (settingsOpen = false)}
  {health}
  {liveStatus}
  {username}
  onLogout={authRequired ? doLogout : null}
/>

<ActionAssistantModal
  open={assistantOpen}
  {quests}
  {questlines}
  notes={notes}
  {attachments}
  onClose={() => (assistantOpen = false)}
  onApplied={() => load({ silent: true })}
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
{/if}

<style>
  /* Blank canvas while the auth probe is in flight — avoids flashing either
     the login card or the journal before we know which one is right. */
  .boot-gate {
    min-height: 100vh;
    background: var(--color-bg);
  }
</style>
