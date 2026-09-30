<script>
  import Icon from '../ui/Icon.svelte'
  import ContextMenu from '../ui/ContextMenu.svelte'
  import { attachmentDownloadUrl, deleteAttachment } from '../js/api.js'
  import { copyText } from '../js/clipboard.js'
  import { toast } from '../js/toasts.svelte.js'

  /** @type {{
   *   attachments?: any[],
   *   quests?: any[],
   *   questlines?: any[],
   *   notes?: any[],
   *   selectedId?: number | null,
   *   onSelect?: (id: number | null) => void,
   *   onOpenOwner?: (kind: string, id: number) => void,
   *   onChanged?: () => void,
   * }} */
  let {
    attachments = [],
    quests = [],
    questlines = [],
    notes = [],
    selectedId = null,
    onSelect,
    onOpenOwner,
    onChanged,
  } = $props()

  let search = $state('')
  let ctxOpen = $state(false)
  let ctxX = $state(0)
  let ctxY = $state(0)
  let ctxAtt = $state(/** @type {any | null} */ (null))

  let ctxItems = $derived.by(() => {
    const a = ctxAtt
    if (!a) return []
    return [
      { id: 'download', label: 'Скачать', disabled: a.available === false },
      { id: 'open', label: 'Открыть владельца' },
      { id: 'copy-id', label: `Копировать attachment=${a.id}` },
      { id: 'sep-danger', sep: true },
      { id: 'delete', label: 'Удалить', danger: true },
    ]
  })

  /** @param {MouseEvent} event @param {any} a */
  function openAttMenu(event, a) {
    const target = event.target
    if (target instanceof Element && target.closest('a, button, input, textarea')) return
    event.preventDefault()
    event.stopPropagation()
    ctxAtt = a
    ctxX = event.clientX
    ctxY = event.clientY
    ctxOpen = true
  }

  function downloadAtt(a) {
    const link = document.createElement('a')
    link.href = attachmentDownloadUrl(ownerKind(a), a.owner_id, a.id)
    link.download = a.filename || ''
    link.rel = 'noopener'
    document.body.appendChild(link)
    link.click()
    link.remove()
  }

  async function onAttSelect(action) {
    const a = ctxAtt
    if (!a) return
    if (action === 'download') {
      if (a.available === false) return
      downloadAtt(a)
      return
    }
    if (action === 'open') {
      onOpenOwner?.(ownerKind(a), Number(a.owner_id))
      return
    }
    if (action === 'copy-id') {
      try {
        const text = `attachment=${a.id}`
        await copyText(text)
        toast(`Скопировано ${text}`, { kind: 'success', ttl: 1600 })
      } catch (e) {
        toast(e?.message || String(e), { kind: 'error' })
      }
      return
    }
    if (action === 'delete') {
      try {
        await deleteAttachment(ownerKind(a), a.owner_id, a.id)
        if (selectedId === a.id) onSelect?.(null)
        toast('Вложение удалено', { kind: 'success' })
        onChanged?.()
      } catch (e) {
        toast(e?.message || String(e), { kind: 'error' })
      }
    }
  }

  let questTitle = $derived.by(() => {
    /** @type {Map<number, string>} */
    const m = new Map()
    for (const q of quests) m.set(q.id, q.title || `quest=${q.id}`)
    return m
  })
  let lineTitle = $derived.by(() => {
    /** @type {Map<number, string>} */
    const m = new Map()
    for (const l of questlines) m.set(l.id, l.title || `questline=${l.id}`)
    return m
  })
  let noteTitle = $derived.by(() => {
    /** @type {Map<number, string>} */
    const m = new Map()
    for (const n of notes) m.set(n.id, n.title || `note=${n.id}`)
    return m
  })

  const TYPE_ORDER = ['quest', 'questline', 'note']
  const TYPE_LABEL = { quest: 'Квесты', questline: 'Квестлайны', note: 'Заметки' }

  /** @type {Set<string>} */
  let collapsedTypes = $state(new Set())
  /** @type {Set<string>} */
  let collapsedOwners = $state(new Set())

  function ownerKey(kind, id) {
    return `${kind}:${id}`
  }

  function matchesSearch(a, q) {
    if (!q) return true
    const owner = ownerLabel(a).toLowerCase()
    return `${a.filename || ''} ${a.comment || ''} ${owner} ${a.owner_type || ''}`.toLowerCase().includes(q)
  }

  let tree = $derived.by(() => {
    const q = search.trim().toLowerCase()
    /** @type {Map<string, Map<number, any[]>>} */
    const byType = new Map(TYPE_ORDER.map((kind) => [kind, new Map()]))
    for (const a of attachments) {
      if (!matchesSearch(a, q)) continue
      const kind = TYPE_ORDER.includes(ownerKind(a)) ? ownerKind(a) : 'quest'
      const id = Number(a.owner_id)
      const owners = byType.get(kind)
      const files = owners.get(id) || []
      files.push(a)
      owners.set(id, files)
    }
    return TYPE_ORDER.map((kind) => {
      const owners = [...byType.get(kind).entries()]
        .map(([id, files]) => {
          files.sort((a, b) => (b.uploaded_at || '').localeCompare(a.uploaded_at || '') || (b.id || 0) - (a.id || 0))
          return {
            id,
            kind,
            title: ownerLabel({ owner_type: kind, owner_id: id }),
            files,
          }
        })
        .sort((a, b) => a.title.localeCompare(b.title, 'ru'))
      return {
        kind,
        label: TYPE_LABEL[kind],
        owners,
        count: owners.reduce((n, owner) => n + owner.files.length, 0),
      }
    }).filter((group) => group.count > 0)
  })

  let filteredCount = $derived(tree.reduce((n, group) => n + group.count, 0))
  let searching = $derived(search.trim().length > 0)

  function branchHasSelection(kind, ownerId = null) {
    if (selectedId == null) return false
    return tree.some((group) => {
      if (group.kind !== kind) return false
      return group.owners.some((owner) => {
        if (ownerId != null && owner.id !== ownerId) return false
        return owner.files.some((file) => file.id === selectedId)
      })
    })
  }

  function typeOpen(kind) {
    if (searching || branchHasSelection(kind)) return true
    return !collapsedTypes.has(kind)
  }

  function ownerOpen(kind, id) {
    if (searching || branchHasSelection(kind, id)) return true
    return !collapsedOwners.has(ownerKey(kind, id))
  }

  function toggleType(kind) {
    if (searching) return
    const next = new Set(collapsedTypes)
    if (next.has(kind)) next.delete(kind)
    else next.add(kind)
    collapsedTypes = next
  }

  function toggleOwner(kind, id) {
    if (searching) return
    const key = ownerKey(kind, id)
    const next = new Set(collapsedOwners)
    if (next.has(key)) next.delete(key)
    else next.add(key)
    collapsedOwners = next
  }

  $effect(() => {
    const id = selectedId
    search
    tree
    if (id == null || typeof document === 'undefined') return
    queueMicrotask(() => {
      document.querySelector(`[data-att-id="${id}"]`)?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    })
  })

  function ownerKind(a) {
    return a.owner_type || 'quest'
  }

  function ownerLabel(a) {
    const kind = ownerKind(a)
    const id = Number(a.owner_id)
    if (kind === 'questline') return lineTitle.get(id) || `questline=${id}`
    if (kind === 'note') return noteTitle.get(id) || `note=${id}`
    return questTitle.get(id) || `quest=${id}`
  }

  function formatSize(n) {
    const bytes = Number(n) || 0
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  function formatWhen(iso) {
    if (!iso) return '—'
    try {
      return new Date(iso).toLocaleString('ru-RU', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      })
    } catch {
      return iso
    }
  }

  function mimeLabel(a) {
    return a.content_type_detected || a.content_type_declared || '—'
  }
</script>

<div class="attpage">
  <div class="attpage__tools">
    <input
      class="search"
      type="search"
      placeholder="Поиск по имени, комментарию, владельцу…"
      bind:value={search}
      aria-label="Поиск вложений"
    />
    <span class="attpage__count">{filteredCount}</span>
  </div>

  <div class="attpage__list">
    {#if attachments.length === 0}
      <p class="empty">Вложений пока нет — их вешают на квесты, квестлайны и заметки.</p>
    {:else if filteredCount === 0}
      <p class="empty">Ничего не найдено</p>
    {:else}
      {#each tree as group (group.kind)}
        <section class="attpage__type">
          <button
            type="button"
            class="attpage__fold"
            aria-expanded={typeOpen(group.kind)}
            onclick={() => toggleType(group.kind)}
          >
            <Icon name={typeOpen(group.kind) ? 'chevron-down' : 'chevron-right'} size={14} />
            <span class="attpage__type-label">{group.label}</span>
            <span class="attpage__type-count">{group.count}</span>
          </button>
          {#if typeOpen(group.kind)}
            {#each group.owners as owner (`${owner.kind}:${owner.id}`)}
              <div class="attpage__owner">
                <div class="attpage__owner-head">
                  <button
                    type="button"
                    class="attpage__chev"
                    aria-expanded={ownerOpen(owner.kind, owner.id)}
                    aria-label={ownerOpen(owner.kind, owner.id) ? 'Свернуть файлы' : 'Развернуть файлы'}
                    onclick={() => toggleOwner(owner.kind, owner.id)}
                  >
                    <Icon name={ownerOpen(owner.kind, owner.id) ? 'chevron-down' : 'chevron-right'} size={14} />
                  </button>
                  <button
                    type="button"
                    class="attpage__owner-open"
                    title="Открыть владельца"
                    onclick={() => onOpenOwner?.(owner.kind, owner.id)}
                  >
                    <span class="attpage__owner-title">{owner.title}</span>
                    <span class="attpage__type-count">{owner.files.length}</span>
                  </button>
                </div>
                {#if ownerOpen(owner.kind, owner.id)}
                  <div class="attpage__files" role="list">
                    {#each owner.files as a (a.id)}
                      <article
                        class="attpage__row"
                        class:attpage__row--on={a.id === selectedId}
                        data-att-id={a.id}
                        role="listitem"
                        onclick={() => onSelect?.(a.id)}
                        oncontextmenu={(e) => openAttMenu(e, a)}
                      >
                        <div class="attpage__main">
                          <div class="attpage__name">
                            <Icon name="document" size={14} />
                            <span class="attpage__file">{a.filename || `attachment=${a.id}`}</span>
                            <span class="attpage__id">attachment={a.id}</span>
                          </div>
                          {#if a.comment}
                            <p class="attpage__comment">{a.comment}</p>
                          {/if}
                          <div class="attpage__meta">
                            <span>{formatSize(a.size_bytes)}</span>
                            <span class="attpage__mime" title={mimeLabel(a)}>{mimeLabel(a)}</span>
                            <span title="Загружено">{formatWhen(a.uploaded_at)}</span>
                            {#if a.scan_status && a.scan_status !== 'ok'}
                              <span class="attpage__scan" data-status={a.scan_status}>{a.scan_status}</span>
                            {/if}
                            {#if a.available === false}
                              <span class="attpage__warn">DAV offline</span>
                            {/if}
                            {#if a.source_updated}
                              <span class="attpage__fresh">файл новее карточки</span>
                            {/if}
                          </div>
                        </div>
                        <div class="attpage__actions">
                          {#if a.available === false}
                            <span class="attpage__dl attpage__dl--off" title="WebDAV недоступен">скачать</span>
                          {:else}
                            <a
                              class="attpage__dl"
                              href={attachmentDownloadUrl(ownerKind(a), a.owner_id, a.id)}
                              download={a.filename}
                              onclick={(e) => e.stopPropagation()}
                            >
                              скачать
                            </a>
                          {/if}
                        </div>
                      </article>
                    {/each}
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </section>
      {/each}
    {/if}
  </div>
</div>

<ContextMenu
  open={ctxOpen}
  x={ctxX}
  y={ctxY}
  items={ctxItems}
  onSelect={onAttSelect}
  onClose={() => (ctxOpen = false)}
/>

<style>
  .attpage {
    display: flex;
    flex-direction: column;
    min-height: 0;
    height: 100%;
  }

  .attpage__tools {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.75rem 1rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .attpage__tools .search {
    flex: 1 1 auto;
    min-width: 0;
  }

  .attpage__count {
    flex: 0 0 auto;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-variant-numeric: tabular-nums;
  }

  .attpage__list {
    flex: 1 1 auto;
    overflow: auto;
    padding: 0.35rem 0 1rem;
  }

  .attpage__type {
    margin: 0.15rem 0 0.35rem;
  }

  .attpage__fold,
  .attpage__owner-open,
  .attpage__chev {
    border: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }

  .attpage__fold {
    display: flex;
    align-items: center;
    gap: 0.35rem;
    width: 100%;
    padding: 0.45rem 1rem 0.3rem;
  }

  .attpage__fold:hover .attpage__type-label {
    color: var(--color-fg, #e8e8e8);
  }

  .attpage__type-label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .attpage__type-count {
    margin-left: auto;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-variant-numeric: tabular-nums;
  }

  .attpage__owner {
    margin-left: 0.85rem;
  }

  .attpage__owner-head {
    display: flex;
    align-items: stretch;
    min-width: 0;
  }

  .attpage__chev {
    flex: 0 0 1.6rem;
    display: flex;
    align-items: center;
    justify-content: center;
    color: color-mix(in srgb, var(--color-fg, #e8e8e8) 55%, transparent);
  }

  .attpage__chev:hover {
    color: var(--color-fg, #e8e8e8);
  }

  .attpage__owner-open {
    display: flex;
    align-items: baseline;
    gap: 0.6rem;
    flex: 1 1 auto;
    min-width: 0;
    padding: 0.28rem 1rem 0.28rem 0.15rem;
  }

  .attpage__owner-open:hover .attpage__owner-title {
    color: var(--color-accent, #c9a227);
  }

  .attpage__owner-title {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg, #e8e8e8);
  }

  .attpage__files {
    margin-left: 1.35rem;
  }

  @media (max-width: 600px) {
    .attpage__owner {
      margin-left: 0.25rem;
    }
    .attpage__files {
      margin-left: 0.85rem;
    }
    .attpage__row {
      padding-right: 0.75rem;
    }
  }

  .empty {
    margin: 1.5rem 1rem;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .attpage__row {
    display: flex;
    align-items: flex-start;
    gap: 0.75rem;
    padding: 0.65rem 1rem;
    border-left: 2px solid transparent;
    cursor: default;
  }

  .attpage__row:hover {
    background: color-mix(in srgb, var(--color-fg, #e8e8e8) 4%, transparent);
  }

  .attpage__row--on {
    background: color-mix(in srgb, var(--color-fg, #e8e8e8) 6%, var(--color-bg-raised, #1a1a1a));
    border-left-color: var(--color-accent, #c9a227);
  }

  .attpage__main {
    flex: 1 1 auto;
    min-width: 0;
    display: grid;
    gap: 0.25rem;
  }

  .attpage__name {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    min-width: 0;
  }

  .attpage__file {
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .attpage__id {
    flex-shrink: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-variant-numeric: tabular-nums;
  }

  .attpage__comment {
    margin: 0;
    font-size: var(--text-sm, 0.875rem);
    color: color-mix(in srgb, var(--color-fg, #e8e8e8) 78%, transparent);
  }

  .attpage__meta {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 0.75rem;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .attpage__mime {
    max-width: 12rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .attpage__scan {
    color: var(--color-danger, #b54a3a);
  }

  .attpage__warn {
    color: var(--color-danger, #b54a3a);
  }

  .attpage__fresh {
    color: var(--color-accent, #c9a227);
  }

  .attpage__actions {
    flex: 0 0 auto;
    padding-top: 0.1rem;
  }

  .attpage__dl {
    color: var(--color-accent, #c9a227);
    text-decoration: none;
    font-size: var(--text-sm, 0.875rem);
  }

  .attpage__dl:hover {
    text-decoration: underline;
  }

  .attpage__dl--off {
    color: var(--color-fg-muted, #9a9a9a);
    opacity: 0.6;
  }
</style>
