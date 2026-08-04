<script>
  import { getHero } from './api.js'
  import Icon from './Icon.svelte'

  /** @type {{ active?: boolean, nonce?: number }} */
  let { active = true, nonce = 0 } = $props()

  let loading = $state(false)
  let error = $state('')
  /** @type {any | null} */
  let hero = $state(null)

  const MOMENTUM_ZONES = [
    { max: 20, id: 'apathy', label: 'Апатия' },
    { max: 40, id: 'low', label: 'Спад' },
    { max: 60, id: 'steady', label: 'Ровно' },
    { max: 80, id: 'tempo', label: 'Темп' },
    { max: 100, id: 'mania', label: 'Накал' },
  ]

  function momentumZone(value) {
    const n = Math.max(0, Math.min(100, Number(value) || 0))
    return MOMENTUM_ZONES.find((z) => n <= z.max) || MOMENTUM_ZONES[MOMENTUM_ZONES.length - 1]
  }

  function formatDelta(d) {
    const n = Number(d) || 0
    if (n > 0) return `+${n}`
    return String(n)
  }

  function kindLabel(row) {
    if (row.kind === 'xp') return 'XP'
    if (row.kind === 'momentum') return 'Импульс'
    if (row.kind === 'attr') {
      const a = hero?.attributes?.find((x) => x.attr_id === row.attr_id)
      return a?.label || row.attr_id || 'Стат'
    }
    return row.kind
  }

  async function refresh({ silent = false } = {}) {
    if (!silent) loading = true
    if (!silent) error = ''
    try {
      hero = await getHero()
    } catch (e) {
      if (!silent) {
        error = e.message || String(e)
        hero = null
      }
    } finally {
      if (!silent) loading = false
    }
  }

  $effect(() => {
    if (!active) return
    const n = nonce
    refresh({ silent: n > 0 })
  })

  let zone = $derived(momentumZone(hero?.momentum ?? 50))
</script>

<section class="hero" aria-label="Лист героя">
  <header class="hero__head">
    <div>
      <h2 class="hero__title">Лист</h2>
      <p class="hero__sub">Опыт, импульс и характеристики</p>
    </div>
    <button type="button" class="btn" onclick={() => refresh()} disabled={loading} aria-label="Обновить">
      <Icon name="renew" size={14} />
      <span class="btn__text">Обновить</span>
    </button>
  </header>

  {#if error}
    <p class="hero__error" role="alert">{error}</p>
  {/if}

  {#if loading && !hero}
    <p class="hero__empty">Загрузка…</p>
  {:else if hero}
    <div class="hero__grid">
      <article class="stat-block stat-block--xp">
        <span class="stat-block__label">Опыт</span>
        <span class="stat-block__value">{hero.xp}</span>
        <span class="stat-block__hint">кумулятивно · только вверх</span>
      </article>

      <article class="stat-block stat-block--momentum" data-zone={zone.id}>
        <div class="stat-block__row">
          <span class="stat-block__label">Импульс</span>
          <span class="zone-pill" data-zone={zone.id}>{zone.label}</span>
        </div>
        <span class="stat-block__value">{hero.momentum}<span class="stat-block__max">/100</span></span>
        <div class="meter" aria-hidden="true">
          <div class="meter__fill" style:width="{Math.max(0, Math.min(100, hero.momentum))}%"></div>
        </div>
        <span class="stat-block__hint">−1/час бездействия · от середины до нуля ~2 суток</span>
      </article>
    </div>

    <div class="attrs">
      <h3 class="attrs__title">Характеристики</h3>
      <ul class="attrs__list">
        {#each hero.attributes || [] as attr (attr.attr_id)}
          {@const need = Math.max(1, Number(attr.progress_to_next) || 1)}
          {@const pct = Math.min(100, Math.round((100 * (Number(attr.progress) || 0)) / need))}
          <li class="attr">
            <div class="attr__top">
              <span class="attr__name">{attr.label}</span>
              <span class="attr__rank" title="Ранг">р.{attr.rank}</span>
            </div>
            <div class="meter meter--attr" aria-hidden="true">
              <div class="meter__fill" style:width="{pct}%"></div>
            </div>
            <div class="attr__meta">
              <span>{attr.progress} / {need}</span>
              <span class="attr__id">{attr.attr_id}</span>
            </div>
          </li>
        {/each}
      </ul>
    </div>

    <div class="ledger">
      <h3 class="attrs__title">Журнал наград</h3>
      {#if !hero.recent?.length}
        <p class="hero__empty">Пока пусто — закрой квест, и здесь появятся записи.</p>
      {:else}
        <ul class="ledger__list">
          {#each hero.recent as row (row.id)}
            <li class="ledger__row" data-kind={row.kind} data-sign={row.delta >= 0 ? 'up' : 'down'}>
              <span class="ledger__delta">{formatDelta(row.delta)}</span>
              <span class="ledger__body">
                <span class="ledger__kind">{kindLabel(row)}</span>
                {#if row.flavor}
                  <span class="ledger__flavor">{row.flavor}</span>
                {:else}
                  <span class="ledger__flavor">{row.reason}</span>
                {/if}
              </span>
            </li>
          {/each}
        </ul>
      {/if}
    </div>
  {/if}
</section>

<style>
  .hero {
    display: grid;
    gap: var(--space-5, 1.5rem);
    padding: var(--space-4, 1rem) var(--space-5, 1.5rem) var(--space-6, 2rem);
    max-width: 52rem;
    margin: 0 auto;
    width: 100%;
    font-family: var(--font-ui, sans-serif);
  }

  .hero__head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
  }

  .hero__title {
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-xl, 1.6rem);
    color: var(--color-accent, #c9a227);
    letter-spacing: 0.04em;
    text-transform: uppercase;
  }

  .hero__sub {
    margin: 0.2rem 0 0;
    color: var(--color-fg-muted, #9a9a9a);
    font-size: var(--text-sm, 0.875rem);
  }

  .hero__error {
    margin: 0;
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 14%, transparent);
    border: 1px solid color-mix(in srgb, var(--color-danger, #b54a3a) 35%, transparent);
    font-size: var(--text-sm, 0.875rem);
  }

  .hero__empty {
    margin: 0;
    color: var(--color-fg-muted, #9a9a9a);
    font-size: var(--text-sm, 0.875rem);
  }

  .hero__grid {
    display: grid;
    grid-template-columns: 1fr 1.4fr;
    gap: var(--space-3, 0.75rem);
  }

  .stat-block {
    display: grid;
    gap: 0.35rem;
    padding: var(--space-4, 1rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-md, 4px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 88%, transparent);
  }

  .stat-block__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .stat-block__label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .stat-block__value {
    font-family: var(--font-display, Georgia, serif);
    font-size: 2.25rem;
    line-height: 1;
    color: var(--color-fg, #e8e8e8);
    font-variant-numeric: tabular-nums;
  }

  .stat-block__max {
    font-size: 1rem;
    color: var(--color-fg-muted, #9a9a9a);
    margin-left: 0.15rem;
  }

  .stat-block__hint {
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .stat-block--xp .stat-block__value {
    color: var(--color-accent, #c9a227);
  }

  .zone-pill {
    font-size: var(--text-xs, 0.75rem);
    padding: 0.15rem 0.45rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .zone-pill[data-zone='apathy'],
  .stat-block--momentum[data-zone='apathy'] .meter__fill {
    color: var(--color-fg-subtle, #6e6e6e);
  }
  .stat-block--momentum[data-zone='apathy'] .meter__fill {
    background: var(--color-fg-subtle, #6e6e6e);
  }

  .zone-pill[data-zone='low'] {
    color: var(--color-danger, #b54a3a);
    border-color: color-mix(in srgb, var(--color-danger, #b54a3a) 45%, transparent);
  }
  .stat-block--momentum[data-zone='low'] .meter__fill {
    background: var(--color-danger, #b54a3a);
  }

  .zone-pill[data-zone='steady'] {
    color: var(--color-info, #5a8a7a);
    border-color: color-mix(in srgb, var(--color-info, #5a8a7a) 45%, transparent);
  }
  .stat-block--momentum[data-zone='steady'] .meter__fill {
    background: var(--color-info, #5a8a7a);
  }

  .zone-pill[data-zone='tempo'] {
    color: var(--color-accent, #c9a227);
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 45%, transparent);
  }
  .stat-block--momentum[data-zone='tempo'] .meter__fill {
    background: var(--color-accent, #c9a227);
  }

  .zone-pill[data-zone='mania'] {
    color: var(--color-warning, #c47a20);
    border-color: color-mix(in srgb, var(--color-warning, #c47a20) 50%, transparent);
  }
  .stat-block--momentum[data-zone='mania'] .meter__fill {
    background: var(--color-warning, #c47a20);
  }

  .meter {
    height: 0.45rem;
    border-radius: 999px;
    background: var(--color-bg-muted, #242424);
    overflow: hidden;
  }

  .meter__fill {
    height: 100%;
    background: var(--color-accent, #c9a227);
    transition: width 0.35s ease;
  }

  .meter--attr {
    height: 0.35rem;
  }

  .attrs__title {
    margin: 0 0 var(--space-3, 0.75rem);
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-md, 1rem);
    letter-spacing: 0.05em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .attrs__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--space-3, 0.75rem);
  }

  .attr {
    display: grid;
    gap: 0.35rem;
    padding: var(--space-3, 0.75rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
  }

  .attr__top {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    align-items: baseline;
  }

  .attr__name {
    font-weight: 600;
    color: var(--color-fg, #e8e8e8);
  }

  .attr__rank {
    font-family: var(--font-mono, monospace);
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-accent, #c9a227);
  }

  .attr__meta {
    display: flex;
    justify-content: space-between;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
    font-variant-numeric: tabular-nums;
  }

  .attr__id {
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .ledger__list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
    max-height: 18rem;
    overflow: auto;
  }

  .ledger__row {
    display: grid;
    grid-template-columns: 3.25rem 1fr;
    gap: 0.65rem;
    align-items: start;
    padding: 0.45rem 0.55rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 70%, transparent);
  }

  .ledger__delta {
    font-family: var(--font-mono, monospace);
    font-weight: 600;
    font-variant-numeric: tabular-nums;
  }

  .ledger__row[data-sign='up'] .ledger__delta {
    color: var(--color-success, #7a9e3a);
  }

  .ledger__row[data-sign='down'] .ledger__delta {
    color: var(--color-danger, #b54a3a);
  }

  .ledger__body {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }

  .ledger__kind {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .ledger__flavor {
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg, #e8e8e8);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 80%, transparent);
    color: var(--color-fg, #e8e8e8);
    padding: 0.4rem 0.65rem;
    cursor: pointer;
    font: inherit;
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: default;
  }

  @media (max-width: 720px) {
    .hero__grid,
    .attrs__list {
      grid-template-columns: 1fr;
    }
  }
</style>
