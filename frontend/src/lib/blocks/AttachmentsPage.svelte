<script>
  import Icon from '../ui/Icon.svelte'
  import { attachmentDownloadUrl } from '../js/api.js'

  /** @type {{
   *   attachments?: any[],
   *   quests?: any[],
   *   questlines?: any[],
   *   notes?: any[],
   *   selectedId?: number | null,
   *   onSelect?: (id: number | null) => void,
   *   onOpenOwner?: (kind: string, id: number) => void,
   * }} */
  let {
    attachments = [],
    quests = [],
    questlines = [],
    notes = [],
    selectedId = null,
    onSelect,
    onOpenOwner,
  } = $props()

  let search = $state('')

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

  let filtered = $derived.by(() => {
    const q = search.trim().toLowerCase()
    const rows = [...attachments].sort((a, b) => {
      const ta = a.uploaded_at || ''
      const tb = b.uploaded_at || ''
      return tb.localeCompare(ta) || (b.id || 0) - (a.id || 0)
    })
    if (!q) return rows
    return rows.filter((a) => {
      const owner = ownerLabel(a).toLowerCase()
      return `${a.filename || ''} ${a.comment || ''} ${owner} ${a.owner_type || ''}`.toLowerCase().includes(q)
    })
  })

  $effect(() => {
    const id = selectedId
    if (id == null || typeof document === 'undefined') return
    const el = document.querySelector(`[data-att-id="${id}"]`)
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
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

  function ownerKindLabel(kind) {
    if (kind === 'questline') return 'квестлайн'
    if (kind === 'note') return 'заметка'
    return 'квест'
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
    <span class="attpage__count">{filtered.length}</span>
  </div>

  <div class="attpage__list" role="list">
    {#if attachments.length === 0}
      <p class="empty">Вложений пока нет — их вешают на квесты, квестлайны и заметки.</p>
    {:else if filtered.length === 0}
      <p class="empty">Ничего не найдено</p>
    {:else}
      {#each filtered as a (a.id)}
        <article
          class="attpage__row"
          class:attpage__row--on={a.id === selectedId}
          data-att-id={a.id}
          role="listitem"
          onclick={() => onSelect?.(a.id)}
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
              <button
                type="button"
                class="attpage__owner"
                title="Открыть владельца"
                onclick={(e) => {
                  e.stopPropagation()
                  onOpenOwner?.(ownerKind(a), Number(a.owner_id))
                }}
              >
                <span class="attpage__owner-kind">{ownerKindLabel(ownerKind(a))}</span>
                <span class="attpage__owner-title">{ownerLabel(a)}</span>
              </button>
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
    {/if}
  </div>
</div>

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
    padding: 0.5rem 0;
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

  .attpage__owner {
    display: inline-flex;
    align-items: baseline;
    gap: 0.3rem;
    border: 0;
    padding: 0;
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    text-align: left;
  }

  .attpage__owner:hover .attpage__owner-title {
    color: var(--color-accent, #c9a227);
  }

  .attpage__owner-kind {
    text-transform: uppercase;
    letter-spacing: 0.04em;
    opacity: 0.75;
  }

  .attpage__owner-title {
    color: var(--color-fg, #e8e8e8);
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
