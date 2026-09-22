<script>
  import { untrack, tick } from 'svelte'
  import {
    createNote,
    deleteNote,
    getNote,
    updateNote,
  } from '../js/api.js'
  import { clearNoteDraft, getNoteDraft, noteDrafts, putNoteDraft } from '../js/noteDrafts.svelte.js'
  import { copyText } from '../js/clipboard.js'
  import {
    caretOffsetFromPoint,
    mapRenderedOffsetToSource,
    mapSourceOffsetToRendered,
    placeTextareaCaret,
    scrollRootToTextOffset,
  } from '../js/mdCaretMap.js'
  import { downloadNoteMarkdown, downloadNotePdf } from '../js/noteExport.js'
  import { toast, toastDone, toastProgress } from '../js/toasts.svelte.js'
  import Icon from '../ui/Icon.svelte'
  import MarkdownBody from '../ui/MarkdownBody.svelte'
  import MentionTextarea from '../ui/MentionTextarea.svelte'
  import AttachmentsBlock from './AttachmentsBlock.svelte'
  import ConfirmModal from '../modals/ConfirmModal.svelte'
  import NoteIconModal from '../modals/NoteIconModal.svelte'
  import ContextMenu from '../ui/ContextMenu.svelte'
  import QuestlineIcon from '../ui/QuestlineIcon.svelte'

  /** @type {{
   *   notes: any[],
   *   selectedId: number | null,
   *   labels?: Record<string, string>,
   *   quests?: any[],
   *   questlines?: any[],
   *   attachments?: any[],
   *   onSelect: (id: number | null) => void,
   *   onChanged: () => void,
   *   onRef?: (kind: string, id: number) => void,
   * }} */
  let {
    notes = [],
    selectedId = null,
    labels = {},
    quests = [],
    questlines = [],
    attachments = [],
    sidebarCollapsed = false,
    onSelect,
    onChanged,
    onRef,
  } = $props()

  let search = $state('')
  /** @type {Record<string, boolean>} — false = свёрнуто; по умолчанию развёрнуто */
  let treeOpen = $state({})
  let detail = $state(/** @type {any | null} */ (null))
  let title = $state('')
  let description = $state('')
  let parentId = $state('')
  let pinned = $state(false)
  let saving = $state(false)
  let deleting = $state(false)
  let deleteOpen = $state(false)
  let deleteTargetId = $state(/** @type {number | null} */ (null))
  let error = $state('')
  let saved = $state({ title: '', description: '', parentId: '', pinned: false })
  /** @type {'raw' | 'combined' | 'formatted'} */
  let viewMode = $state(loadViewMode())
  let ctxOpen = $state(false)
  let ctxX = $state(0)
  let ctxY = $state(0)
  let ctxNoteId = $state(/** @type {number | null} */ (null))
  let parentMenuOpen = $state(false)
  let parentMenuX = $state(0)
  let parentMenuY = $state(0)
  let exportMenuOpen = $state(false)
  let exportMenuX = $state(0)
  let exportMenuY = $state(0)
  let exportBusy = $state(false)
  let iconModalOpen = $state(false)
  let iconModalNoteId = $state(/** @type {number | null} */ (null))

  let dirty = $derived(
    title !== saved.title ||
      description !== saved.description ||
      parentId !== saved.parentId ||
      pinned !== saved.pinned,
  )

  let filtered = $derived.by(() => {
    const q = search.trim().toLowerCase()
    if (!q) return notes
    const byId = new Map(notes.map((n) => [n.id, n]))
    /** @type {Set<number>} */
    const visible = new Set()
    for (const n of notes) {
      if (!`${n.title || ''} ${n.description || ''}`.toLowerCase().includes(q)) continue
      visible.add(n.id)
      let cur = n
      while (cur.parent_id != null) {
        const parent = byId.get(cur.parent_id)
        if (!parent) break
        visible.add(parent.id)
        cur = parent
      }
    }
    return notes.filter((n) => visible.has(n.id))
  })

  let searchActive = $derived(search.trim().length > 0)

  let byParent = $derived.by(() => {
    /** @type {Map<string, any[]>} */
    const m = new Map()
    for (const n of filtered) {
      const key = n.parent_id == null ? 'root' : String(n.parent_id)
      if (!m.has(key)) m.set(key, [])
      m.get(key).push(n)
    }
    for (const list of m.values()) {
      list.sort(
        (a, b) =>
          Number(b.pinned) - Number(a.pinned) ||
          (a.sort_order || 0) - (b.sort_order || 0) ||
          a.id - b.id,
      )
    }
    return m
  })

  let roots = $derived(byParent.get('root') || [])

  let loadedId = $state(/** @type {number | null} */ (null))

  const VIEW_MODES = /** @type {const} */ ([
    { id: 'raw', label: 'Текст' },
    { id: 'combined', label: 'Оба' },
    { id: 'formatted', label: 'Просмотр' },
  ])

  function loadViewMode() {
    try {
      const v = localStorage.getItem('quests.notes.viewMode')
      if (v === 'raw' || v === 'combined' || v === 'formatted') return v
    } catch {
      /* ignore */
    }
    return 'combined'
  }

  /** @param {'raw' | 'combined' | 'formatted'} mode */
  function setViewMode(mode) {
    viewMode = mode
    try {
      localStorage.setItem('quests.notes.viewMode', mode)
    } catch {
      /* ignore */
    }
  }

  function fromRow(row) {
    return {
      title: row.title || '',
      description: row.description || '',
      parentId: row.parent_id != null ? String(row.parent_id) : '',
      pinned: !!row.pinned,
    }
  }

  function applyForm(src) {
    title = src.title
    description = src.description
    parentId = src.parentId
    pinned = src.pinned
  }

  function formDraft() {
    return { title, description, parentId, pinned }
  }

  function draftsEqual(a, b) {
    return (
      a.title === b.title &&
      a.description === b.description &&
      a.parentId === b.parentId &&
      a.pinned === b.pinned
    )
  }

  function syncDraft(id) {
    if (id == null) return
    const form = formDraft()
    if (draftsEqual(form, saved)) clearNoteDraft(id)
    else putNoteDraft(id, form)
  }

  function revert() {
    applyForm(saved)
    if (selectedId != null) clearNoteDraft(selectedId)
  }

  function rowTitle(n) {
    return noteDrafts[String(n.id)]?.title || n.title
  }

  function rowDirty(n) {
    return n.id === selectedId ? dirty : noteDrafts[String(n.id)] != null
  }

  $effect(() => {
    const id = selectedId
    untrack(() => {
      if (loadedId != null && loadedId !== id) syncDraft(loadedId)
    })
    if (id == null) {
      detail = null
      const empty = { title: '', description: '', parentId: '', pinned: false }
      applyForm(empty)
      saved = empty
      loadedId = null
      return
    }
    let cancelled = false
    getNote(id)
      .then((row) => {
        if (cancelled) return
        detail = row
        const next = fromRow(row)
        const draft = getNoteDraft(id)
        applyForm(draft || next)
        saved = next
        loadedId = id
        error = ''
      })
      .catch((e) => {
        if (cancelled) return
        error = e.message || String(e)
      })
    return () => {
      cancelled = true
      untrack(() => syncDraft(id))
    }
  })

  $effect(() => {
    const id = selectedId
    const loaded = loadedId
    if (id == null || loaded !== id) return
    const form = { title, description, parentId, pinned }
    untrack(() => {
      if (draftsEqual(form, saved)) clearNoteDraft(id)
      else putNoteDraft(id, form)
    })
  })

  async function save() {
    if (selectedId == null || saving) return
    const t = title.trim()
    if (!t) {
      error = 'Нужен заголовок'
      toast(error, { kind: 'error' })
      return
    }
    saving = true
    error = ''
    try {
      const savedRow = await updateNote(selectedId, {
        title: t,
        description,
        pinned,
        parent_id: parentId === '' ? null : Number(parentId),
      })
      detail = savedRow
      saved = fromRow(savedRow)
      applyForm(saved)
      clearNoteDraft(selectedId)
      onChanged()
      toast('Сохранено', { kind: 'success', ttl: 1400 })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
    } finally {
      saving = false
    }
  }

  async function addNote(parent = null) {
    error = ''
    try {
      const created = await createNote({
        title: 'Новая заметка',
        description: '',
        parent_id: parent,
      })
      await onChanged()
      onSelect(created.id)
      toast('Заметка создана', { kind: 'success' })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
    }
  }

  async function confirmDelete() {
    const id = deleteTargetId ?? selectedId
    if (id == null || deleting) return
    deleting = true
    error = ''
    try {
      await deleteNote(id)
      clearNoteDraft(id)
      deleteOpen = false
      deleteTargetId = null
      if (id === selectedId) onSelect(null)
      onChanged()
      toast('Заметка удалена', { kind: 'success' })
    } catch (e) {
      error = e.message || String(e)
      toast(error, { kind: 'error' })
    } finally {
      deleting = false
    }
  }

  function onKey(event) {
    if (!(event.ctrlKey || event.metaKey)) return
    // code=KeyS — раскладконезависимо (ru: Ctrl+ы); key оставляем как запасной.
    const isSave =
      event.code === 'KeyS' || event.key.toLowerCase() === 's' || event.key === 'ы' || event.key === 'Ы'
    if (!isSave) return
    // Перехват браузерного «Сохранить страницу» — keydown + preventDefault.
    event.preventDefault()
    event.stopPropagation()
    if (dirty && selectedId != null) save()
  }

  $effect(() => {
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  })

  let editEl = $state(/** @type {HTMLTextAreaElement | null} */ (null))
  let titleEl = $state(/** @type {HTMLInputElement | null} */ (null))
  let previewEl = $state(/** @type {HTMLDivElement | null} */ (null))
  let titleEditing = $state(false)

  let titleReadonly = $derived(viewMode === 'formatted' && !titleEditing)

  $effect(() => {
    if (viewMode !== 'formatted') titleEditing = false
  })

  function previewMdRoot() {
    return previewEl?.querySelector?.('.md') ?? previewEl
  }

  /** @param {MouseEvent} [event] */
  async function startBodyEdit(event) {
    if (viewMode !== 'formatted') return
    event?.preventDefault?.()
    let offset = description.length
    const mdRoot = previewMdRoot()
    if (event && mdRoot) {
      const rendered = mdRoot.textContent ?? ''
      const renOff = caretOffsetFromPoint(mdRoot, event.clientX, event.clientY)
      offset = mapRenderedOffsetToSource(description, rendered, renOff)
    }
    setViewMode('raw')
    await tick()
    if (editEl) placeTextareaCaret(editEl, offset)
  }

  async function startTitleEdit() {
    if (!titleReadonly) return
    titleEditing = true
    await tick()
    titleEl?.focus()
    titleEl?.select()
  }

  /** Esc в сыром/оба при фокусе в textarea → режим просмотра около каретки. */
  async function onEditKeydown(event) {
    if (event.key !== 'Escape') return
    if (viewMode === 'formatted') return
    event.preventDefault()
    const caret = editEl?.selectionStart ?? 0
    const src = description
    setViewMode('formatted')
    await tick()
    await tick()
    requestAnimationFrame(() => {
      const mdRoot = previewMdRoot()
      if (!mdRoot) return
      const rendered = mdRoot.textContent ?? ''
      const renOff = mapSourceOffsetToRendered(src, rendered, caret)
      scrollRootToTextOffset(mdRoot, renOff)
    })
  }

  function childrenOf(id) {
    return byParent.get(String(id)) || []
  }

  function hasChildren(id) {
    return childrenOf(id).length > 0
  }

  function isTreeOpen(id) {
    return treeOpen[String(id)] !== false
  }

  /** @param {MouseEvent} event */
  function toggleTree(id, event) {
    event.stopPropagation()
    event.preventDefault()
    const key = String(id)
    treeOpen = { ...treeOpen, [key]: treeOpen[key] === false }
  }

  function showChildren(id) {
    if (!hasChildren(id)) return false
    if (searchActive) return true
    return isTreeOpen(id)
  }

  function noteById(id) {
    return notes.find((n) => n.id === id) ?? null
  }

  /** candidate is under ancestor (cannot become its parent). */
  function isUnder(candidateId, ancestorId) {
    if (candidateId == null || ancestorId == null) return false
    let cur = noteById(candidateId)
    const seen = new Set()
    while (cur?.parent_id != null && !seen.has(cur.id)) {
      seen.add(cur.id)
      if (cur.parent_id === ancestorId) return true
      cur = noteById(cur.parent_id)
    }
    return false
  }

  let crumbs = $derived.by(() => {
    /** @type {{ id: number | null, title: string }[]} */
    const out = [{ id: null, title: 'Корень' }]
    const pid = parentId === '' ? null : Number(parentId)
    if (pid == null || Number.isNaN(pid)) return out
    /** @type {{ id: number, title: string }[]} */
    const chain = []
    let cur = noteById(pid)
    const seen = new Set()
    while (cur && !seen.has(cur.id)) {
      seen.add(cur.id)
      chain.unshift({ id: cur.id, title: cur.title || `note=${cur.id}` })
      cur = cur.parent_id != null ? noteById(cur.parent_id) : null
    }
    return out.concat(chain)
  })

  let parentMenuItems = $derived.by(() => {
    /** @type {{ id: string, label: string }[]} */
    const items = [{ id: 'root', label: '— корень —' }]
    if (selectedId == null) return items
    for (const n of notes) {
      if (n.id === selectedId) continue
      if (isUnder(n.id, selectedId)) continue
      items.push({ id: String(n.id), label: n.title || `note=${n.id}` })
    }
    return items
  })

  /** @param {MouseEvent} event */
  function openParentPicker(event) {
    event.preventDefault()
    event.stopPropagation()
    const el = /** @type {HTMLElement} */ (event.currentTarget)
    const rect = el.getBoundingClientRect()
    parentMenuX = rect.left
    parentMenuY = rect.bottom + 4
    parentMenuOpen = true
  }

  function setParentFromMenu(action) {
    if (action === 'root') parentId = ''
    else parentId = action
  }

  /** @param {number | null} id */
  function setParentCrumb(id) {
    parentId = id == null ? '' : String(id)
  }

  /** @param {MouseEvent} event */
  function openExportMenu(event) {
    event.preventDefault()
    event.stopPropagation()
    const el = /** @type {HTMLElement} */ (event.currentTarget)
    const rect = el.getBoundingClientRect()
    exportMenuX = rect.left
    exportMenuY = rect.bottom + 4
    exportMenuOpen = true
  }

  async function onExportSelect(action) {
    if (selectedId == null || exportBusy) return
    const payload = {
      id: selectedId,
      title: title.trim() || detail?.title || `note=${selectedId}`,
      description,
    }
    exportBusy = true
    error = ''
    try {
      if (action === 'md') {
        downloadNoteMarkdown(payload)
        toast('Markdown сохранён', { kind: 'success' })
      } else if (action === 'pdf') {
        const tid = 'pdf-note'
        toastProgress(tid, 'Генерация PDF…')
        try {
          await downloadNotePdf(payload, { labels })
          toastDone(tid, 'PDF сохранён')
        } catch (e) {
          toastDone(tid, e?.message || 'Не удалось сохранить PDF', 'error')
          throw e
        }
      }
    } catch (e) {
      if (action !== 'pdf') {
        error = e?.message || String(e)
        toast(error, { kind: 'error' })
      } else {
        error = e?.message || String(e)
      }
    } finally {
      exportBusy = false
    }
  }

  let exportMenuItems = $derived([
    { id: 'md', label: 'Markdown (.md)' },
    { id: 'pdf', label: exportBusy ? 'PDF…' : 'PDF' },
  ])

  let ctxNote = $derived(ctxNoteId == null ? null : noteById(ctxNoteId))

  let ctxItems = $derived.by(() => {
    if (ctxNoteId == null) return []
    const items = [
      { id: 'copy-id', label: `Копировать note=${ctxNoteId}` },
      { id: 'sep-copy', sep: true },
      { id: 'add-child', label: 'Добавить дочернюю' },
    ]
    if (ctxNote?.parent_id != null) {
      items.push({ id: 'move-up', label: 'На уровень вверх' })
    }
    items.push({ id: 'sep-icon', sep: true })
    items.push({ id: 'icon', label: 'Иконка' })
    items.push({ id: 'sep-danger', sep: true })
    items.push({ id: 'delete', label: 'Удалить', danger: true })
    return items
  })

  function openNoteMenu(event, note) {
    if (!note?.id) return
    event.preventDefault()
    event.stopPropagation()
    ctxNoteId = note.id
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function closeNoteMenu() {
    ctxOpen = false
  }

  async function copyNoteRef(id) {
    if (id == null) return
    try {
      const text = `note=${id}`
      await copyText(text)
      toast(`Скопировано ${text}`, { kind: 'success', ttl: 1600 })
    } catch (e) {
      error = e?.message || String(e)
      toast(error, { kind: 'error' })
    }
  }

  async function moveNoteUp(id) {
    const n = noteById(id)
    if (!n?.parent_id) return
    const parent = noteById(n.parent_id)
    const next = parent?.parent_id ?? null
    error = ''
    try {
      const savedRow = await updateNote(id, { parent_id: next })
      const pid = next == null ? '' : String(next)
      if (id === selectedId) {
        saved = { ...saved, parentId: pid }
        parentId = pid
        detail = savedRow
        const draft = getNoteDraft(id)
        if (draft) putNoteDraft(id, { ...draft, parentId: pid })
      }
      onChanged()
    } catch (e) {
      error = e.message || String(e)
    }
  }

  function requestDelete(id) {
    if (id == null) return
    deleteTargetId = id
    deleteOpen = true
  }

  async function onCtxSelect(action) {
    const id = ctxNoteId
    if (action === 'copy-id') {
      await copyNoteRef(id)
      return
    }
    if (action === 'add-child') {
      await addNote(id)
      return
    }
    if (action === 'move-up') {
      await moveNoteUp(id)
      return
    }
    if (action === 'icon') {
      iconModalNoteId = id
      iconModalOpen = true
      return
    }
    if (action === 'delete') {
      requestDelete(id)
    }
  }

  let iconModalNote = $derived(
    iconModalNoteId == null ? null : noteById(iconModalNoteId),
  )

  function onIconSaved(row) {
    if (selectedId === row?.id) {
      detail = row
    }
    onChanged()
  }

  let deleteTargetTitle = $derived(
    deleteTargetId == null ? '' : rowTitle(noteById(deleteTargetId) || { id: deleteTargetId, title: '' }),
  )
</script>

<div class="notes" class:notes--sidebar-collapsed={sidebarCollapsed}>
  <aside class="notes__tree">
    <div class="notes__tools">
      <input class="search" type="search" placeholder="Поиск…" bind:value={search} />
      <button
        type="button"
        class="btn btn--accent notes__add"
        aria-label="Новая заметка"
        onclick={() => addNote(null)}
      >
        +
      </button>
    </div>
    <div class="notes__list">
      {#if notes.length === 0}
        <p class="empty">Пока пусто — это хранилище знания, не список дел.</p>
      {:else if roots.length === 0 && search}
        <p class="empty">Ничего не найдено</p>
      {:else}
        {#snippet tree(nodes, depth)}
          {#each nodes as n (n.id)}
            <div class="notes__node" style:--notes-depth="{depth}">
              {#if hasChildren(n.id)}
                <button
                  type="button"
                  class="notes__fold"
                  aria-expanded={showChildren(n.id)}
                  aria-label={showChildren(n.id) ? 'Свернуть' : 'Развернуть'}
                  onclick={(e) => toggleTree(n.id, e)}
                >
                  <Icon
                    name={showChildren(n.id) ? 'chevron-down' : 'chevron-right'}
                    size={12}
                  />
                </button>
              {:else}
                <span class="notes__fold notes__fold--spacer" aria-hidden="true"></span>
              {/if}
              <button
                type="button"
                class="notes__row"
                class:notes__row--on={n.id === selectedId}
                class:notes__row--pin={n.pinned}
                onclick={() => onSelect(n.id)}
                oncontextmenu={(e) => openNoteMenu(e, n)}
              >
                <span class="notes__row-icon" style="--line-color: {n.color || '#9a9a9a'}">
                  <QuestlineIcon
                    icon={n.icon || 'document'}
                    iconUrl={n.icon_url}
                    size="sm"
                  />
                </span>
                <span class="notes__row-label">
                  <span class="notes__row-title">{rowTitle(n)}</span>{#if rowDirty(n)}<span
                      class="notes__unsaved"
                      title="Несохранено">*</span>{/if}
                </span>
              </button>
            </div>
            {#if showChildren(n.id)}
              {@render tree(childrenOf(n.id), depth + 1)}
            {/if}
          {/each}
        {/snippet}
        {@render tree(roots, 0)}
      {/if}
    </div>
  </aside>

  <section class="notes__page">
    {#if error}
      <p class="notes__error">{error}</p>
    {/if}
    {#if selectedId == null}
      <p class="notes__empty">Выберите заметку или создайте новую</p>
    {:else}
      <header
        class="notes__head"
        oncontextmenu={(e) => {
          const n = noteById(selectedId)
          if (n) openNoteMenu(e, n)
        }}
      >
        <div class="notes__head-row">
          <div class="notes__title-cluster">
            <span class="notes__title-grow">
              <span class="notes__title-sizer" aria-hidden="true">{title || '\u00a0'}</span>
              <input
                class="notes__title"
                class:notes__title--locked={titleReadonly}
                size="1"
                bind:this={titleEl}
                bind:value={title}
                readonly={titleReadonly}
                title={titleReadonly ? 'Двойной клик — править заголовок' : undefined}
                ondblclick={startTitleEdit}
              />
            </span>
            {#if dirty}<span class="notes__unsaved" title="Несохранено">*</span>{/if}
          </div>
          <div class="detail__actions notes__actions">
            <button
              type="button"
              class="btn btn--icon"
              class:notes__pin--on={pinned}
              onclick={() => (pinned = !pinned)}
              title={pinned ? 'Открепить' : 'Закрепить'}
              aria-label={pinned ? 'Открепить' : 'Закрепить'}
              aria-pressed={pinned}
            >
              <Icon name={pinned ? 'pin-filled' : 'pin'} />
            </button>
            {#if dirty}
              <button
                type="button"
                class="btn btn--icon"
                onclick={revert}
                title="Отменить правки"
                aria-label="Отменить правки"
              >
                <Icon name="renew" />
              </button>
            {/if}
            <button
              type="button"
              class="btn btn--icon"
              disabled={saving || !dirty}
              onclick={save}
              title={saving ? 'Сохранение…' : 'Сохранить (Ctrl+S)'}
              aria-label={saving ? 'Сохранение…' : 'Сохранить'}
            >
              {#if saving}…{:else}<Icon name="save" />{/if}
            </button>
            <button
              type="button"
              class="btn btn--icon"
              disabled={exportBusy}
              onclick={openExportMenu}
              title={exportBusy ? 'Выгрузка…' : 'Скачать'}
              aria-label={exportBusy ? 'Выгрузка…' : 'Скачать заметку'}
              aria-haspopup="menu"
            >
              {#if exportBusy}…{:else}<Icon name="document" />{/if}
            </button>
            <button
              type="button"
              class="btn btn--icon btn--danger"
              onclick={() => requestDelete(selectedId)}
              title="Удалить"
              aria-label="Удалить"
            >
              <Icon name="delete" />
            </button>
          </div>
        </div>
        <div class="notes__colophon">
          <nav class="notes__crumbs" aria-label="Родитель">
            {#each crumbs as c, i (c.id ?? 'root')}
              {#if i > 0}<span class="notes__crumb-sep" aria-hidden="true">/</span>{/if}
              <button
                type="button"
                class="notes__crumb"
                class:notes__crumb--here={i === crumbs.length - 1}
                onclick={(e) => {
                  if (i === crumbs.length - 1) openParentPicker(e)
                  else setParentCrumb(c.id)
                }}
                title={i === crumbs.length - 1 ? 'Сменить родителя' : `Вложить в «${c.title}»`}
              >
                {c.title}
              </button>
            {/each}
          </nav>
          <div class="notes__modes" role="radiogroup" aria-label="Режим просмотра">
            {#each VIEW_MODES as mode (mode.id)}
              <button
                type="button"
                class="notes__mode"
                class:notes__mode--on={viewMode === mode.id}
                role="radio"
                aria-checked={viewMode === mode.id}
                onclick={() => setViewMode(mode.id)}
              >
                {mode.label}
              </button>
            {/each}
          </div>
        </div>
      </header>
      <div
        class="notes__split"
        class:notes__split--raw={viewMode === 'raw'}
        class:notes__split--combined={viewMode === 'combined'}
        class:notes__split--formatted={viewMode === 'formatted'}
      >
        {#if viewMode !== 'formatted'}
          <MentionTextarea
            class="notes__edit"
            placement="inside"
            bind:value={description}
            bind:el={editEl}
            {quests}
            {questlines}
            {notes}
            {attachments}
            rows={16}
            placeholder="Markdown. @название — ссылка. Код и конфиг — в блоках ``` … ```"
            onkeydown={onEditKeydown}
          />
        {/if}
        {#if viewMode !== 'raw'}
          <div
            class="notes__preview block--prose"
            class:notes__preview--doc={viewMode === 'formatted'}
            bind:this={previewEl}
            title={viewMode === 'formatted' ? 'Двойной клик — править' : undefined}
            ondblclick={startBodyEdit}
          >
            <MarkdownBody source={description} {labels} {onRef} />
          </div>
        {/if}
      </div>
      {#if detail?.refs?.length}
        <div class="block notes__links">
          <h3 class="block__label">Ссылки</h3>
          <ul>
            {#each detail.refs as ref (`${ref.kind}-${ref.id}`)}
              <li>
                <button type="button" class="notes__link" onclick={() => onRef?.(ref.kind, ref.id)}>
                  {ref.title || `${ref.kind}=${ref.id}`}
                  <span class="notes__kind">{ref.kind}={ref.id}</span>
                </button>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
      {#if detail?.backlinks?.length}
        <div class="block notes__links">
          <h3 class="block__label">Ссылаются</h3>
          <ul>
            {#each detail.backlinks as ref (`b-${ref.kind}-${ref.id}`)}
              <li>
                <button type="button" class="notes__link" onclick={() => onRef?.(ref.kind, ref.id)}>
                  {ref.title || `${ref.kind}=${ref.id}`}
                  <span class="notes__kind">{ref.kind}={ref.id}</span>
                </button>
              </li>
            {/each}
          </ul>
        </div>
      {/if}
      {#if selectedId}
        <div class="block notes__attach">
          <h3 class="block__label">Вложения</h3>
          <AttachmentsBlock ownerType="note" ownerId={selectedId} />
        </div>
      {/if}
    {/if}
  </section>
</div>

<ContextMenu
  open={ctxOpen}
  x={ctxX}
  y={ctxY}
  items={ctxItems}
  onSelect={onCtxSelect}
  onClose={closeNoteMenu}
/>

<ContextMenu
  open={parentMenuOpen}
  x={parentMenuX}
  y={parentMenuY}
  items={parentMenuItems}
  onSelect={setParentFromMenu}
  onClose={() => (parentMenuOpen = false)}
/>

<ContextMenu
  open={exportMenuOpen}
  x={exportMenuX}
  y={exportMenuY}
  items={exportMenuItems}
  onSelect={onExportSelect}
  onClose={() => (exportMenuOpen = false)}
/>

<NoteIconModal
  open={iconModalOpen}
  note={iconModalNote}
  onClose={() => {
    iconModalOpen = false
    iconModalNoteId = null
  }}
  onSaved={onIconSaved}
/>

<ConfirmModal
  open={deleteOpen}
  title="Удалить заметку?"
  message={deleteTargetTitle
    ? `Удалить «${deleteTargetTitle}»? Дочерние поднимутся в корень. Ссылки note=N в других текстах останутся.`
    : 'Дочерние поднимутся в корень. Ссылки note=N в других текстах останутся.'}
  busy={deleting}
  onCancel={() => {
    if (!deleting) {
      deleteOpen = false
      deleteTargetId = null
    }
  }}
  onConfirm={confirmDelete}
/>

<style>
  .notes {
    flex: 1 1 auto;
    display: grid;
    grid-template-columns: minmax(14rem, var(--sidebar-width, 16.5rem)) 1fr;
    min-height: 0;
    overflow: hidden;
  }

  .notes--sidebar-collapsed {
    grid-template-columns: 0 1fr;
  }

  .notes--sidebar-collapsed .notes__tree {
    border-right: 0;
  }

  .notes__tree {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
    border-right: 1px solid var(--color-border, #333);
    background: var(--color-bg-raised, #1a1a1a);
  }

  .notes__tools {
    display: flex;
    gap: 0.4rem;
    padding: 0.55rem 0.6rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .notes__tools .search {
    flex: 1 1 auto;
    min-width: 0;
  }

  .notes__add {
    flex: 0 0 auto;
    min-width: 2rem;
    padding-inline: 0.55rem;
    font-size: 1.1rem;
    line-height: 1;
  }

  .notes__list {
    flex: 1 1 auto;
    overflow: auto;
    padding: 0.25rem 0;
  }

  .notes__node {
    display: flex;
    align-items: stretch;
    padding-left: calc(0.35rem + var(--notes-depth, 0) * 0.85rem);
  }

  .notes__fold {
    flex: 0 0 1.35rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border: 0;
    padding: 0;
    margin: 0;
    background: transparent;
    color: color-mix(in srgb, var(--color-fg, #e8e8e8) 55%, transparent);
    cursor: pointer;
    border-radius: 2px;
  }

  .notes__fold:hover {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-fg, #e8e8e8) 6%, transparent);
  }

  .notes__fold--spacer {
    pointer-events: none;
  }

  .notes__row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    flex: 1 1 auto;
    min-width: 0;
    border: 0;
    border-left: 2px solid transparent;
    background: transparent;
    color: inherit;
    text-align: left;
    padding: 0.28rem 0.45rem 0.28rem 0.35rem;
    cursor: pointer;
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .notes__row:hover {
    background: color-mix(in srgb, var(--color-fg, #e8e8e8) 4%, transparent);
  }

  .notes__row--on {
    background: color-mix(in srgb, var(--color-fg, #e8e8e8) 6%, var(--color-bg-raised, #1a1a1a));
    border-left-color: var(--color-fg, #e8e8e8);
  }

  .notes__row-icon {
    flex-shrink: 0;
    display: inline-flex;
    color: var(--line-color, #9a9a9a);
  }

  .notes__row-label {
    display: inline-flex;
    align-items: baseline;
    flex: 1 1 auto;
    min-width: 0;
    max-width: 100%;
  }

  .notes__row-title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .notes__unsaved {
    flex-shrink: 0;
    color: var(--color-accent, #c9a227);
    font-weight: 700;
    line-height: 1;
    animation: notes-unsaved-glow 1.8s cubic-bezier(0.37, 0, 0.63, 1) infinite;
  }

  @keyframes notes-unsaved-glow {
    0%,
    100% {
      opacity: 0.28;
      text-shadow: 0 0 0.05em color-mix(in srgb, var(--color-accent, #c9a227) 15%, transparent);
    }
    50% {
      opacity: 1;
      text-shadow:
        0 0 0.12em var(--color-accent, #c9a227),
        0 0 0.45em color-mix(in srgb, var(--color-accent, #c9a227) 85%, transparent);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .notes__unsaved {
      animation: none;
      opacity: 1;
    }
  }

  .notes__page {
    min-height: 0;
    overflow: auto;
    padding: var(--space-5, 1.5rem) var(--space-6, 2rem) 2rem;
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 1rem);
  }

  .notes__empty,
  .empty {
    color: var(--color-fg-muted, #9a9a9a);
    padding: 1rem;
  }

  .notes__error {
    margin: 0;
    color: var(--color-danger, #b54a3a);
  }

  .notes__head {
    margin: 0 0 var(--space-2, 0.5rem);
    padding: 0 0 var(--space-3, 0.75rem);
    border-bottom: 1px solid var(--color-border, #333);
  }

  .notes__head-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
  }

  .notes__actions {
    flex-shrink: 0;
  }

  .notes__pin--on {
    color: var(--color-accent, #c9a227);
  }

  .notes__title-cluster {
    display: inline-flex;
    align-items: baseline;
    flex: 1 1 auto;
    min-width: 0;
    max-width: 100%;
    font-family: var(--font-display, Georgia, serif);
    font-size: clamp(1.35rem, 2.4vw, 1.85rem);
    font-weight: 700;
    line-height: 1.15;
  }

  .notes__title-grow {
    position: relative;
    display: inline-grid;
    /* Flex items default to min-width:auto (= their content's min-content),
       and the sizer's white-space:pre makes that the full title width —
       without an explicit 0 here a long title refuses to shrink and
       overlaps the pin/save buttons instead of clipping. */
    min-width: 0;
    max-width: 100%;
    overflow: hidden;
  }

  .notes__title-sizer,
  .notes__title {
    grid-area: 1 / 1;
    /* Same min-width:auto trap applies to grid items sizing their track —
       without this the track still grows to the sizer's full-text
       min-content width even though the container above is now capped. */
    min-width: 0;
    padding: 0.15rem 0;
    font: inherit;
  }

  .notes__title-sizer {
    visibility: hidden;
    white-space: pre;
    pointer-events: none;
  }

  .notes__title {
    width: 100%;
    min-width: 0;
    border: 0;
    background: transparent;
    color: inherit;
    box-sizing: border-box;
  }

  .notes__title--locked {
    cursor: default;
    caret-color: transparent;
  }

  .notes__title--locked:focus {
    outline: none;
  }

  .notes__title-cluster .notes__unsaved {
    flex-shrink: 0;
    padding: 0.15rem 0;
  }

  .notes__colophon {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.35rem 0.85rem;
    margin: 0.45rem 0 0;
    font-family: var(--font-ui, sans-serif);
    font-size: 0.72rem;
    letter-spacing: 0.02em;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .notes__crumbs {
    display: inline-flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 0.25rem 0.35rem;
    min-width: 0;
  }

  .notes__crumb {
    border: 0;
    padding: 0;
    margin: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    max-width: 12rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .notes__crumb:hover {
    color: var(--color-fg, #e8e8e8);
  }

  .notes__crumb--here {
    color: var(--color-fg, #e8e8e8);
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }

  .notes__crumb-sep {
    opacity: 0.45;
    user-select: none;
  }

  .notes__modes {
    margin-left: auto;
    display: flex;
    flex-wrap: wrap;
    gap: 0.65rem;
    align-items: baseline;
  }

  .notes__mode {
    border: 0;
    padding: 0;
    margin: 0;
    background: transparent;
    color: var(--color-fg-subtle, #6e6e6e);
    font: inherit;
    letter-spacing: 0.02em;
    cursor: pointer;
  }

  .notes__mode:hover {
    color: var(--color-fg-muted, #9a9a9a);
  }

  .notes__mode--on {
    color: var(--color-fg, #e8e8e8);
    box-shadow: 0 1px 0 currentColor;
  }

  .notes__split {
    display: grid;
    gap: 0;
    min-height: 18rem;
    flex: 1 1 auto;
  }

  .notes__split--combined {
    grid-template-columns: 1fr 1fr;
    gap: 0 1.1rem;
    background: linear-gradient(
      to right,
      transparent calc(50% - 0.5px),
      var(--color-border, #333) calc(50% - 0.5px),
      var(--color-border, #333) calc(50% + 0.5px),
      transparent calc(50% + 0.5px)
    );
  }

  .notes__split--combined :global(textarea.notes__edit) {
    border-right: 0;
    padding-right: 0.25rem;
  }

  .notes__split--combined .notes__preview {
    padding-left: 0.25rem;
  }

  .notes__split--raw,
  .notes__split--formatted {
    grid-template-columns: 1fr;
  }

  .notes__split :global(textarea.notes__edit) {
    width: 100%;
    min-height: 18rem;
    height: 100%;
    resize: vertical;
    padding: 0.15rem 0.1rem 0.75rem;
    border: 0;
    border-radius: 0;
    background: transparent;
    color: inherit;
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: 0.85rem;
    line-height: 1.5;
  }

  .notes__preview {
    padding: 0.15rem 0.25rem 0.75rem 0.85rem;
    overflow: auto;
    min-height: 18rem;
  }

  .notes__split--formatted .notes__preview {
    padding-left: 0.1rem;
  }

  .notes__preview--doc {
    cursor: text;
  }

  .notes__split--raw :global(textarea.notes__edit) {
    padding-left: 0.1rem;
  }

  .notes__links ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .notes__link {
    border: 0;
    border-bottom: 1px solid color-mix(in srgb, var(--color-border, #333) 80%, transparent);
    background: transparent;
    color: inherit;
    padding: 0.15rem 0;
    cursor: pointer;
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .notes__link:hover {
    border-bottom-color: var(--color-fg-muted, #9a9a9a);
  }

  .notes__kind {
    margin-left: 0.35rem;
    color: var(--color-fg-subtle, #6e6e6e);
    font-family: var(--font-mono, monospace);
    font-size: 0.7rem;
  }

  .notes__attach {
    margin-top: 0.25rem;
    padding-top: var(--space-4, 1rem);
    border-top: 1px solid var(--color-border, #333);
  }

  @media (max-width: 720px) {
    .notes {
      grid-template-columns: 1fr;
    }
    .notes__page {
      padding: 1rem 1rem 2rem;
    }
    .notes__split--combined {
      grid-template-columns: 1fr;
      gap: 0.85rem;
      background: none;
    }
    .notes__split--combined :global(textarea.notes__edit) {
      border-bottom: 1px solid var(--color-border, #333);
      padding-bottom: 0.85rem;
      padding-right: 0.1rem;
    }
    .notes__split--combined .notes__preview {
      padding-left: 0.1rem;
    }
    .notes__modes {
      margin-left: 0;
      width: 100%;
    }
  }
</style>
