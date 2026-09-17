<script>
  import { untrack } from 'svelte'
  import {
    createNote,
    deleteNote,
    getNote,
    updateNote,
  } from '../js/api.js'
  import { clearNoteDraft, getNoteDraft, noteDrafts, putNoteDraft } from '../js/noteDrafts.svelte.js'
  import { copyText } from '../js/clipboard.js'
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
  let ctxOpen = $state(false)
  let ctxX = $state(0)
  let ctxY = $state(0)
  let ctxNoteId = $state(/** @type {number | null} */ (null))
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
    } catch (e) {
      error = e.message || String(e)
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
    } catch (e) {
      error = e.message || String(e)
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
    } catch (e) {
      error = e.message || String(e)
    } finally {
      deleting = false
    }
  }

  function onKey(event) {
    if ((event.ctrlKey || event.metaKey) && event.key === 's') {
      event.preventDefault()
      if (dirty) save()
    }
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
      await copyText(`note=${id}`)
    } catch (e) {
      error = e?.message || String(e)
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

<div class="notes" onkeydown={onKey}>
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
        <div class="notes__title-wrap">
          <div class="notes__title-cluster">
            <span class="notes__title-grow">
              <span class="notes__title-sizer" aria-hidden="true">{title || '\u00a0'}</span>
              <input class="notes__title" size="1" bind:value={title} />
            </span>
            {#if dirty}<span class="notes__unsaved" title="Несохранено">*</span>{/if}
          </div>
        </div>
        {#if dirty}
          <button type="button" class="btn btn--ghost" onclick={revert}>Отменить</button>
        {/if}
        <button type="button" class="btn btn--accent" disabled={saving || !dirty} onclick={save}>
          <Icon name="save" />
          {saving ? '…' : 'Сохранить'}
        </button>
        <button
          type="button"
          class="btn btn--icon btn--danger"
          onclick={() => requestDelete(selectedId)}
          title="Удалить"
        >
          <Icon name="delete" />
        </button>
      </header>
      <div class="notes__meta">
        <label class="notes__check">
          <input type="checkbox" bind:checked={pinned} />
          Закрепить
        </label>
        <label class="notes__parent">
          Родитель
          <select bind:value={parentId}>
            <option value="">— корень —</option>
            {#each notes as n (n.id)}
              {#if n.id !== selectedId}
                <option value={String(n.id)}>{n.title}</option>
              {/if}
            {/each}
          </select>
        </label>
        {#if selectedId}
          <button type="button" class="btn btn--ghost" onclick={() => addNote(selectedId)}>
            Дочерняя
          </button>
        {/if}
      </div>
      <div class="notes__split">
        <MentionTextarea
          class="notes__edit"
          placement="inside"
          bind:value={description}
          {quests}
          {questlines}
          {notes}
          rows={16}
          placeholder="Markdown. @название — ссылка. Код и конфиг — в блоках ``` … ```"
        />
        <div class="notes__preview">
          <MarkdownBody source={description} {labels} {onRef} />
        </div>
      </div>
      {#if detail?.refs?.length}
        <div class="notes__links">
          <h3>Ссылки</h3>
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
        <div class="notes__links">
          <h3>Ссылаются</h3>
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
        <div class="notes__attach">
          <h3>Вложения этой страницы</h3>
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

  .notes__tree {
    display: flex;
    flex-direction: column;
    min-height: 0;
    border-right: 1px solid var(--color-border, #333);
    background: var(--color-bg-raised, #1a1a1a);
  }

  .notes__tools {
    display: flex;
    gap: 0.4rem;
    padding: 0.6rem;
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
    padding: 0.35rem 0;
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
    padding: 0.32rem 0.45rem 0.32rem 0.35rem;
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
    padding: 1rem 1.25rem 2rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
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
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .notes__title-wrap {
    flex: 1 1 auto;
    min-width: 0;
    display: flex;
    align-items: baseline;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .notes__title-cluster {
    display: inline-flex;
    align-items: baseline;
    max-width: 100%;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-xl, 1.4rem);
  }

  .notes__title-grow {
    position: relative;
    display: inline-grid;
    min-width: 1ch;
    max-width: 100%;
  }

  .notes__title-sizer,
  .notes__title {
    grid-area: 1 / 1;
    padding: 0.2rem 0;
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

  .notes__title-cluster .notes__unsaved {
    flex-shrink: 0;
    padding: 0.2rem 0;
  }

  .notes__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .notes__parent select {
    margin-left: 0.35rem;
  }

  .notes__split {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    min-height: 18rem;
    flex: 1 1 auto;
  }

  .notes__split :global(textarea.notes__edit) {
    width: 100%;
    min-height: 18rem;
    height: 100%;
    resize: vertical;
    padding: 0.75rem;
    border: 1px solid var(--color-border, #333);
    border-radius: 0;
    background: var(--color-bg, #121212);
    color: inherit;
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: 0.85rem;
    line-height: 1.45;
  }

  .notes__preview {
    border: 1px solid var(--color-border, #333);
    padding: 0.75rem 1rem;
    overflow: auto;
  }

  .notes__links h3,
  .notes__attach h3 {
    margin: 0 0 0.35rem;
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-subtle, #6e6e6e);
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
    border: 1px solid var(--color-border, #333);
    background: transparent;
    color: inherit;
    padding: 0.2rem 0.5rem;
    cursor: pointer;
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .notes__kind {
    margin-left: 0.35rem;
    color: var(--color-fg-subtle, #6e6e6e);
    font-family: var(--font-mono, monospace);
    font-size: 0.7rem;
  }

  @media (max-width: 720px) {
    .notes {
      grid-template-columns: 1fr;
    }
    .notes__split {
      grid-template-columns: 1fr;
    }
  }
</style>
