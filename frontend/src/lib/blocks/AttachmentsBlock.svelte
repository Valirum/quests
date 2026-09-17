<script>
  import Icon from '../ui/Icon.svelte'
  import {
    deleteAttachment,
    listAttachments,
    updateAttachmentComment,
    uploadAttachment,
    attachmentDownloadUrl,
  } from '../js/api.js'
  import {
    peekAttachmentList,
    setAttachmentList,
    onAttachmentLiveInvalidate,
  } from '../js/attachmentCache.js'

  /** @type {{ ownerType: 'quest' | 'questline', ownerId: number }} */
  let { ownerType, ownerId } = $props()

  /** @type {any[]} */
  let items = $state([])
  let uploading = $state(false)
  let error = $state('')
  let dragOver = $state(false)
  let fileInput = $state(/** @type {HTMLInputElement | null} */ (null))
  /** @type {Record<number, string>} */
  let commentDraft = $state({})
  /** @type {number | null} */
  let commentBusy = $state(null)

  function draftsFrom(rows) {
    const drafts = /** @type {Record<number, string>} */ ({})
    for (const a of rows || []) drafts[a.id] = a.comment || ''
    return drafts
  }

  function applyRows(type, id, rows, { probed = false } = {}) {
    const next = rows || []
    setAttachmentList(type, id, next, { probed })
    if (type !== ownerType || id !== ownerId) return
    items = next
    commentDraft = draftsFrom(next)
  }

  // Paint from cache before the first DOM pass so switching quests does not
  // flash the previous owner's files (or an empty hole while we refetch).
  $effect.pre(() => {
    const type = ownerType
    const id = ownerId
    const hit = peekAttachmentList(type, id)
    const next = hit?.items ?? []
    error = ''
    items = next
    commentDraft = draftsFrom(next)
  })

  let liveNudge = $state(0)
  $effect(() => onAttachmentLiveInvalidate(() => {
    liveNudge += 1
  }))

  $effect(() => {
    const type = ownerType
    const id = ownerId
    void liveNudge
    let cancelled = false
    if (!id) return
    const hit = peekAttachmentList(type, id)
    if (hit?.probed) return
    listAttachments(type, id)
      .then((rows) => {
        setAttachmentList(type, id, rows || [], { probed: true })
        if (cancelled) return
        items = rows || []
        commentDraft = draftsFrom(items)
      })
      .catch((e) => {
        if (cancelled) return
        error = e?.message || String(e)
        if (!hit) applyRows(type, id, [], { probed: false })
      })
    return () => {
      cancelled = true
    }
  })

  function formatSize(n) {
    const bytes = Number(n) || 0
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  async function sendFiles(files) {
    const list = [...files].filter(Boolean)
    if (!list.length || uploading) return
    uploading = true
    error = ''
    try {
      for (const file of list) {
        await uploadAttachment(ownerType, ownerId, file)
      }
      applyRows(ownerType, ownerId, (await listAttachments(ownerType, ownerId)) || [], {
        probed: true,
      })
    } catch (e) {
      error = e?.message || String(e)
    } finally {
      uploading = false
      if (fileInput) fileInput.value = ''
    }
  }

  function onPick(event) {
    sendFiles(event.currentTarget.files || [])
  }

  function onDrop(event) {
    event.preventDefault()
    dragOver = false
    sendFiles(event.dataTransfer?.files || [])
  }

  async function saveComment(a) {
    const next = (commentDraft[a.id] ?? '').trim()
    if (next === (a.comment || '')) return
    commentBusy = a.id
    error = ''
    try {
      const updated = await updateAttachmentComment(ownerType, ownerId, a.id, next)
      applyRows(
        ownerType,
        ownerId,
        items.map((row) => (row.id === a.id ? { ...row, ...updated } : row)),
        { probed: peekAttachmentList(ownerType, ownerId)?.probed ?? true },
      )
    } catch (e) {
      error = e?.message || String(e)
    } finally {
      commentBusy = null
    }
  }

  async function remove(a) {
    error = ''
    try {
      await deleteAttachment(ownerType, ownerId, a.id)
      applyRows(
        ownerType,
        ownerId,
        items.filter((row) => row.id !== a.id),
        { probed: peekAttachmentList(ownerType, ownerId)?.probed ?? true },
      )
    } catch (e) {
      error = e?.message || String(e)
    }
  }
</script>

<div
  class="attach"
  class:attach--over={dragOver}
  role="region"
  aria-label="Вложения"
  ondragover={(e) => {
    e.preventDefault()
    dragOver = true
  }}
  ondragleave={() => (dragOver = false)}
  ondrop={onDrop}
>
  {#if error}
    <p class="attach__error">{error}</p>
  {/if}

  {#if items.length}
    <ul class="attach__list">
      {#each items as a (a.id)}
        {@const unavailable = a.available === false}
        <li class="attach__row" class:attach__row--off={unavailable}>
          <span class="attach__file">
            <span class="attach__name">{a.filename}</span>
            <span class="attach__meta">
              {formatSize(a.size_bytes)}
              {#if a.content_type_detected}
                · {a.content_type_detected}
              {/if}
              {#if a.scan_status && a.scan_status !== 'clean'}
                · {a.scan_status}
              {/if}
            </span>
            {#if a.source_updated}
              <span class="attach__flag">источник обновился</span>
            {/if}
            {#if unavailable}
              <span class="attach__flag attach__flag--muted">файл недоступен</span>
            {/if}
          </span>
          <input
            class="attach__comment"
            type="text"
            maxlength="500"
            placeholder="зачем этот файл"
            disabled={commentBusy === a.id}
            bind:value={commentDraft[a.id]}
            onblur={() => saveComment(a)}
            onkeydown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                e.currentTarget.blur()
              }
            }}
          />
          {#if unavailable}
            <span class="attach__dl attach__dl--off" title="WebDAV недоступен">скачать</span>
          {:else}
            <a
              class="attach__dl"
              href={attachmentDownloadUrl(ownerType, ownerId, a.id)}
              download={a.filename}
            >
              скачать
            </a>
          {/if}
          <button
            type="button"
            class="btn btn--icon btn--danger"
            title="Удалить"
            aria-label="Удалить вложение"
            onclick={() => remove(a)}
          >
            <Icon name="delete" size={14} />
          </button>
        </li>
      {/each}
    </ul>
  {/if}

  <!-- No "Вложений нет": an empty list already says that, and spelling it out
       cost a line above the quest itself. The attach affordance reads as one
       sentence — link plus its continuation — instead of a button. -->
  <div class="attach__drop">
    <button
      type="button"
      class="attach__pick"
      disabled={uploading}
      onclick={() => fileInput?.click()}
    >
      {uploading ? 'Сканирование…' : 'Прикрепить файл'}
    </button>
    <span class="attach__hint">или перетащить сюда</span>
    <input
      bind:this={fileInput}
      class="attach__input"
      type="file"
      multiple
      onchange={onPick}
    />
  </div>
</div>
