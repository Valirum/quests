<script>
  import { createTag } from '../js/api.js'
  import { buildSuggestIndex, suggestTags } from '../js/suggest.js'

  const MAX = 5

  /** @type {{
   *   catalog?: { id: number, slug: string, label: string, color?: string }[],
   *   value?: { id: number, slug: string, label: string, color?: string }[],
   *   title?: string,
   *   description?: string,
   *   quests?: any[],
   *   enabled?: boolean,
   *   onChange: (tags: { id: number, slug: string, label: string, color?: string }[]) => void,
   *   onCatalog?: (tags: { id: number, slug: string, label: string, color?: string }[]) => void,
   * }} */
  let {
    catalog = [],
    value = [],
    title = '',
    description = '',
    quests = [],
    enabled = true,
    onChange,
    onCatalog = null,
  } = $props()

  let draft = $state('')
  let busy = $state(false)
  let err = $state('')

  let selected = $derived(Array.isArray(value) ? value : [])
  let exclude = $derived(selected.map((t) => t.slug))

  let index = $derived(enabled ? buildSuggestIndex(quests) : null)
  let hints = $derived(
    enabled && index
      ? suggestTags(index, { title, description }, { excludeSlugs: exclude, limit: 5 })
      : [],
  )

  function normalizeSlug(raw) {
    return String(raw || '')
      .trim()
      .toLowerCase()
      .replace(/ё/g, 'е')
      .replace(/[\s_]+/g, '-')
      .replace(/[^a-z0-9а-яё-]+/gi, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '')
  }

  function findInCatalog(token) {
    const t = token.trim()
    if (!t) return null
    const slug = normalizeSlug(t)
    const bySlug = catalog.find((c) => c.slug === slug)
    if (bySlug) return bySlug
    const low = t.toLowerCase()
    return catalog.find((c) => String(c.label || '').toLowerCase() === low) || null
  }

  async function resolveToken(token) {
    const t = token.trim()
    if (!t) return null
    if (selected.length >= MAX) {
      err = `Не больше ${MAX} тегов`
      return null
    }
    let tag = findInCatalog(t)
    if (!tag) {
      busy = true
      try {
        tag = await createTag({ slug: normalizeSlug(t) || t, label: t })
        if (onCatalog && tag) {
          const next = [...catalog]
          if (!next.some((c) => c.id === tag.id)) next.push(tag)
          onCatalog(next)
        }
      } catch (e) {
        err = e.message || String(e)
        return null
      } finally {
        busy = false
      }
    }
    if (!tag) return null
    if (selected.some((s) => s.id === tag.id)) return null
    return tag
  }

  async function onInput(e) {
    err = ''
    const v = e.currentTarget.value
    if (!v.includes(',')) {
      draft = v
      return
    }
    const parts = v.split(',')
    const rest = parts.pop() ?? ''
    let next = [...selected]
    for (const part of parts) {
      if (next.length >= MAX) break
      const tag = await resolveToken(part)
      if (tag && !next.some((s) => s.id === tag.id)) next.push(tag)
    }
    draft = rest
    if (next.length !== selected.length) onChange(next)
  }

  async function onKeydown(e) {
    if (e.key === 'Enter') {
      e.preventDefault()
      const tag = await resolveToken(draft)
      if (tag) {
        onChange([...selected, tag])
        draft = ''
      }
    } else if (e.key === 'Backspace' && !draft && selected.length) {
      onChange(selected.slice(0, -1))
    }
  }

  function remove(id) {
    onChange(selected.filter((t) => t.id !== id))
  }

  function acceptHint(tag) {
    if (selected.length >= MAX) {
      err = `Не больше ${MAX} тегов`
      return
    }
    if (selected.some((s) => s.id === tag.id)) return
    onChange([...selected, tag])
  }
</script>

<div class="tag-field">
  <div class="tag-field__chips">
    {#each selected as t (t.id)}
      <button
        type="button"
        class="tag-chip"
        style:--tag={t.color || '#9a9a9a'}
        onclick={() => remove(t.id)}
        title="Убрать {t.slug}"
      >
        {t.slug}
        <span aria-hidden="true">×</span>
      </button>
    {/each}
    <input
      class="tag-field__input"
      type="text"
      placeholder={selected.length ? 'ещё тег…' : 'slug, через запятую'}
      bind:value={draft}
      oninput={onInput}
      onkeydown={onKeydown}
      disabled={busy || selected.length >= MAX}
      autocomplete="off"
    />
  </div>
  {#if err}
    <p class="tag-field__err">{err}</p>
  {/if}
  {#if hints.length}
    <div class="tag-field__hints" role="list">
      {#each hints as h (h.tag.id)}
        <button
          type="button"
          class="tag-hint"
          style:--tag={h.tag.color || '#9a9a9a'}
          role="listitem"
          onclick={() => acceptHint(h.tag)}
        >
          {h.tag.slug}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .tag-field {
    display: grid;
    gap: 0.35rem;
  }

  .tag-field__chips {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.3rem;
    min-height: 2rem;
    padding: 0.25rem 0.4rem;
    border: 1px solid var(--color-border, #333);
    border-radius: 4px;
    background: var(--color-bg, #121212);
  }

  .tag-chip {
    display: inline-flex;
    align-items: center;
    gap: 0.25rem;
    padding: 0.1rem 0.4rem;
    border: 1px solid color-mix(in srgb, var(--tag, #9a9a9a) 45%, var(--color-border, #333));
    border-radius: 3px;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    font-family: var(--font-mono, monospace);
    font-size: 0.7rem;
    cursor: pointer;
  }

  .tag-chip:hover {
    color: var(--color-fg, #e8e8e8);
  }

  .tag-field__input {
    flex: 1 1 6rem;
    min-width: 5rem;
    border: 0;
    background: transparent;
    color: var(--color-fg, #e8e8e8);
    font-family: var(--font-mono, monospace);
    font-size: 0.8rem;
    outline: none;
  }

  .tag-field__err {
    margin: 0;
    font-size: 0.75rem;
    color: var(--color-danger, #b54a3a);
  }

  .tag-field__hints {
    display: flex;
    flex-wrap: wrap;
    gap: 0.3rem;
  }

  .tag-hint {
    padding: 0.12rem 0.45rem;
    border: 1px dashed color-mix(in srgb, var(--tag, #9a9a9a) 40%, var(--color-border, #333));
    border-radius: 3px;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    font-family: var(--font-mono, monospace);
    font-size: 0.68rem;
    cursor: pointer;
  }

  .tag-hint:hover {
    color: var(--color-fg, #e8e8e8);
    border-style: solid;
  }
</style>
