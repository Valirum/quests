<script>
  import { previewActionBatch, applyActionBatch } from '../js/api.js'
  import { buildPreviewTree } from '../js/actionsPreview.js'
  import { activeMentionToken, applyMention, matchMentions } from '../js/mentionSuggest.js'
  import Icon from '../ui/Icon.svelte'

  /** @type {{
   *   open: boolean,
   *   quests: any[],
   *   questlines: any[],
   *   onClose: () => void,
   *   onApplied: () => void,
   * }} */
  let { open = false, quests = [], questlines = [], onClose, onApplied } = $props()

  let text = $state('')
  /** @type {'input' | 'loading' | 'preview' | 'applying'} */
  let phase = $state('input')
  let clarifyQuestion = $state('')
  let batch = $state(/** @type {any | null} */ (null))
  let preview = $state(/** @type {any[]} */ ([]))
  let errorMsg = $state('')
  let textareaEl = $state(/** @type {HTMLTextAreaElement | null} */ (null))

  let mentionOpen = $state(false)
  let mentionItems = $state(/** @type {any[]} */ ([]))
  let mentionIndex = $state(0)
  let mentionToken = $state(/** @type {{ query: string, start: number } | null} */ (null))

  let tree = $derived(
    phase === 'preview'
      ? buildPreviewTree(preview, { quests, questlines })
      : { questlines: [], looseQuests: [] },
  )

  $effect(() => {
    if (!open) return
    text = ''
    phase = 'input'
    clarifyQuestion = ''
    batch = null
    preview = []
    errorMsg = ''
    mentionOpen = false
    queueMicrotask(() => textareaEl?.focus())
  })

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        if (mentionOpen) return
        event.preventDefault()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  async function generate() {
    const t = text.trim()
    if (!t || phase === 'loading') return
    phase = 'loading'
    errorMsg = ''
    try {
      const res = await previewActionBatch(t)
      if (res?.needs_clarification) {
        clarifyQuestion = res.clarify_question || 'Уточни, пожалуйста, запрос.'
        phase = 'input'
        return
      }
      clarifyQuestion = ''
      batch = res.batch
      preview = res.preview || []
      phase = 'preview'
    } catch (e) {
      errorMsg = e.message || String(e)
      phase = 'input'
    }
  }

  async function apply() {
    if (!batch || phase === 'applying') return
    phase = 'applying'
    errorMsg = ''
    try {
      await applyActionBatch(batch)
      onApplied?.()
      onClose()
    } catch (e) {
      errorMsg = e.message || String(e)
      phase = 'preview'
    }
  }

  function backToEdit() {
    phase = 'input'
    batch = null
    preview = []
  }

  function onPromptInput(event) {
    const el = /** @type {HTMLTextAreaElement} */ (event.currentTarget)
    text = el.value
    const caret = el.selectionStart ?? text.length
    const token = activeMentionToken(text, caret)
    if (!token) {
      mentionOpen = false
      mentionToken = null
      return
    }
    mentionToken = token
    mentionItems = matchMentions(token.query, { quests, questlines })
    mentionIndex = 0
    mentionOpen = mentionItems.length > 0
  }

  function pickMention(item) {
    if (!item || !mentionToken) return
    const { text: nextText, caret } = applyMention(text, mentionToken, item)
    text = nextText
    mentionOpen = false
    mentionToken = null
    queueMicrotask(() => {
      textareaEl?.focus()
      textareaEl?.setSelectionRange(caret, caret)
    })
  }

  function onPromptKeydown(event) {
    if (mentionOpen) {
      if (event.key === 'ArrowDown') {
        event.preventDefault()
        mentionIndex = (mentionIndex + 1) % mentionItems.length
        return
      }
      if (event.key === 'ArrowUp') {
        event.preventDefault()
        mentionIndex = (mentionIndex - 1 + mentionItems.length) % mentionItems.length
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        pickMention(mentionItems[mentionIndex])
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        mentionOpen = false
        return
      }
    }
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault()
      generate()
    }
  }

  function onBackdrop(event) {
    if (event.target === event.currentTarget) onClose()
  }

  function fmtVal(v) {
    if (v === null || v === undefined || v === '') return '—'
    if (typeof v === 'boolean') return v ? 'да' : 'нет'
    return String(v)
  }
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdrop}>
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="aa-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="aa-modal-title">
          <Icon name="terminal" size={16} />
          Командная строка журнала
        </h2>
        <button type="button" class="icon-btn" aria-label="Закрыть" onclick={onClose}>
          <Icon name="close" />
        </button>
      </header>

      {#if errorMsg}
        <p class="modal__error">{errorMsg}</p>
      {/if}

      {#if phase !== 'preview'}
        <div class="prompt-area">
          {#if clarifyQuestion}
            <p class="clarify">{clarifyQuestion}</p>
          {/if}
          <div class="prompt-input">
            <textarea
              bind:this={textareaEl}
              bind:value={text}
              rows="3"
              placeholder="Например: создай квестлайн Бэкапы и закинь туда @Про…"
              oninput={onPromptInput}
              onkeydown={onPromptKeydown}
              disabled={phase === 'loading'}
            ></textarea>
            {#if mentionOpen}
              <ul class="mentions" role="listbox">
                {#each mentionItems as item, i (item.kind + ':' + item.id)}
                  <li>
                    <button
                      type="button"
                      class="mentions__opt"
                      class:mentions__opt--on={i === mentionIndex}
                      role="option"
                      aria-selected={i === mentionIndex}
                      onmousedown={(e) => e.preventDefault()}
                      onclick={() => pickMention(item)}
                    >
                      <span class="mentions__kind">{item.label}</span>
                      <span class="mentions__title">{item.title}</span>
                      {#if item.hint}<span class="mentions__hint">{item.hint}</span>{/if}
                    </button>
                  </li>
                {/each}
              </ul>
            {/if}
          </div>
          <p class="hint">
            @ + название — подставить существующий квест/квестлайн/шаг. Ctrl/Cmd+Enter — сгенерировать план.
            Ничего не запишется без подтверждения.
          </p>
          <footer class="modal__foot">
            <button type="button" class="btn btn--ghost" onclick={onClose}>Отмена</button>
            <button
              type="button"
              class="btn btn--accent"
              onclick={generate}
              disabled={phase === 'loading' || !text.trim()}
            >
              {phase === 'loading' ? 'Думаю…' : 'Сгенерировать'}
            </button>
          </footer>
        </div>
      {:else}
        <div class="preview-area">
          <p class="hint">Проверь план перед применением — можно вернуться и переформулировать.</p>
          <ul class="tree">
            {#each tree.questlines as line (line.id)}
              <li class="node node--questline">
                <span class="node__row">
                  {#if line.isNew}<span class="badge badge--new">NEW</span>{/if}
                  <Icon name="flag" size={13} />
                  <span class="node__label">{line.label}</span>
                </span>
                {#if line.quests.length}
                  <ul class="tree">
                    {#each line.quests as q (q.id)}
                      <li class="node node--quest">
                        <span class="node__row">
                          {#if q.isNew}<span class="badge badge--new">NEW</span>{/if}
                          <span class="node__label">{q.label}</span>
                        </span>
                        {#if q.changes.length}
                          <ul class="changes">
                            {#each q.changes as c}
                              <li>
                                <span class="change__field">{c.field}:</span>
                                {fmtVal(c.from)} → <strong>{fmtVal(c.to)}</strong>
                              </li>
                            {/each}
                          </ul>
                        {/if}
                        {#if q.steps.length}
                          <ul class="tree">
                            {#each q.steps as s (s.id)}
                              <li class="node node--step">
                                <span class="node__row">
                                  {#if s.isNew}<span class="badge badge--new">NEW</span>{/if}
                                  {#if s.deleted}<span class="badge badge--danger">DEL</span>{/if}
                                  <span class="node__label" class:node__label--deleted={s.deleted}>{s.label}</span>
                                </span>
                                {#if s.changes.length}
                                  <ul class="changes">
                                    {#each s.changes as c}
                                      <li>
                                        <span class="change__field">{c.field}:</span>
                                        {fmtVal(c.from)} → <strong>{fmtVal(c.to)}</strong>
                                      </li>
                                    {/each}
                                  </ul>
                                {/if}
                              </li>
                            {/each}
                          </ul>
                        {/if}
                      </li>
                    {/each}
                  </ul>
                {/if}
              </li>
            {/each}

            {#each tree.looseQuests as q (q.id)}
              <li class="node node--quest">
                <span class="node__row">
                  {#if q.isNew}<span class="badge badge--new">NEW</span>{/if}
                  <span class="node__label">{q.label}</span>
                </span>
                {#if q.changes.length}
                  <ul class="changes">
                    {#each q.changes as c}
                      <li>
                        <span class="change__field">{c.field}:</span>
                        {fmtVal(c.from)} → <strong>{fmtVal(c.to)}</strong>
                      </li>
                    {/each}
                  </ul>
                {/if}
                {#if q.steps.length}
                  <ul class="tree">
                    {#each q.steps as s (s.id)}
                      <li class="node node--step">
                        <span class="node__row">
                          {#if s.isNew}<span class="badge badge--new">NEW</span>{/if}
                          {#if s.deleted}<span class="badge badge--danger">DEL</span>{/if}
                          <span class="node__label">{s.label}</span>
                        </span>
                      </li>
                    {/each}
                  </ul>
                {/if}
              </li>
            {/each}
          </ul>

          <footer class="modal__foot">
            <button type="button" class="btn btn--ghost" onclick={backToEdit} disabled={phase === 'applying'}>
              Назад
            </button>
            <button type="button" class="btn btn--accent" onclick={apply} disabled={phase === 'applying'}>
              {phase === 'applying' ? 'Применяю…' : 'Применить'}
            </button>
          </footer>
        </div>
      {/if}
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    place-items: center;
    padding: 1rem;
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
  }

  .modal {
    width: min(34rem, 100%);
    max-height: min(90vh, 42rem);
    overflow: auto;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 16px 48px color-mix(in srgb, #000 45%, transparent);
  }

  .modal__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.85rem 1rem;
    border-bottom: 1px solid var(--color-border, #333);
  }

  .modal__head h2 {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0;
    font-size: var(--text-lg, 1.1rem);
    color: var(--color-accent, #c9a227);
  }

  .icon-btn {
    display: inline-flex;
    border: 0;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    padding: 0.35rem;
    cursor: pointer;
  }

  .modal__error {
    margin: 0.75rem 1rem 0;
    color: var(--color-danger, #b54a3a);
  }

  .prompt-area,
  .preview-area {
    display: grid;
    gap: 0.6rem;
    padding: 1rem;
  }

  .clarify {
    margin: 0;
    padding: 0.5rem 0.65rem;
    border: 1px solid color-mix(in srgb, var(--color-accent, #c9a227) 45%, var(--color-border, #333));
    border-radius: var(--radius-sm, 2px);
    background: color-mix(in srgb, var(--color-accent, #c9a227) 10%, transparent);
    color: var(--color-fg, #e8e8e8);
    font-size: var(--text-sm, 0.875rem);
  }

  .prompt-input {
    position: relative;
  }

  textarea {
    width: 100%;
    resize: vertical;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg, #121212);
    color: var(--color-fg, #e8e8e8);
    padding: 0.55rem 0.65rem;
    font: inherit;
  }

  .mentions {
    position: absolute;
    z-index: 5;
    top: 100%;
    left: 0;
    right: 0;
    margin-top: 0.25rem;
    max-height: 12rem;
    overflow-y: auto;
    list-style: none;
    padding: 0.25rem;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-raised, #1a1a1a);
    box-shadow: 0 8px 24px color-mix(in srgb, #000 45%, transparent);
  }

  .mentions__opt {
    display: flex;
    align-items: baseline;
    gap: 0.4rem;
    width: 100%;
    border: 0;
    border-radius: var(--radius-sm, 2px);
    background: transparent;
    color: var(--color-fg, #e8e8e8);
    padding: 0.3rem 0.4rem;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .mentions__opt--on {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, transparent);
  }

  .mentions__kind {
    flex-shrink: 0;
    font-size: 0.65rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .mentions__title {
    flex: 1 1 auto;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-size: var(--text-sm, 0.875rem);
  }

  .mentions__hint {
    flex-shrink: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .hint {
    margin: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .tree,
  .changes {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  .tree .tree,
  .tree .changes {
    margin-top: 0.3rem;
    padding-left: 1.1rem;
    border-left: 1px dashed var(--color-border, #333);
  }

  .node {
    margin-bottom: 0.4rem;
  }

  .node__row {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg, #e8e8e8);
  }

  .node--questline .node__row {
    font-weight: 600;
    color: var(--color-accent, #c9a227);
  }

  .node__label--deleted {
    text-decoration: line-through;
    color: var(--color-danger, #b54a3a);
  }

  .badge {
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.03em;
    padding: 0.05rem 0.35rem;
    border-radius: var(--radius-sm, 2px);
  }

  .badge--new {
    color: #1a1a1a;
    background: var(--color-accent, #c9a227);
  }

  .badge--danger {
    color: #fff;
    background: var(--color-danger, #b54a3a);
  }

  .changes {
    margin-top: 0.15rem;
  }

  .changes li {
    font-size: var(--text-xs, 0.8rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .change__field {
    color: var(--color-fg, #e8e8e8);
  }

  .modal__foot {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
    margin-top: 0.25rem;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    padding: 0.4rem 0.65rem;
    cursor: pointer;
    font: inherit;
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: wait;
  }

  .btn--accent {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 18%, var(--color-bg-muted, #242424));
    color: var(--color-accent, #c9a227);
  }

  .btn--ghost {
    border-color: transparent;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
  }
</style>
