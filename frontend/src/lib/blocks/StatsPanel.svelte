<script>
  import { getStats } from '../js/api.js'
  import Icon from '../ui/Icon.svelte'

  /** @type {{ active?: boolean, nonce?: number }} */
  let { active = true, nonce = 0 } = $props()

  const PERIODS = [
    { days: 7, label: '7 дней' },
    { days: 30, label: '30 дней' },
    { days: 90, label: '90 дней' },
  ]

  const SERIES = [
    { key: 'issued', label: 'выдано', color: 'var(--color-info, #5a8a7a)' },
    { key: 'completed', label: 'закрыто', color: 'var(--color-success, #7a9e3a)' },
    { key: 'failed', label: 'провалено', color: 'var(--color-danger, #b54a3a)' },
  ]

  let loading = $state(false)
  let error = $state('')
  /** @type {any | null} */
  let stats = $state(null)
  let days = $state(30)
  /** @type {number | null} */
  let templateId = $state(null)

  async function refresh({ silent = false } = {}) {
    if (!silent) loading = true
    if (!silent) error = ''
    try {
      const params = { days }
      if (templateId != null) params.template_id = templateId
      stats = await getStats(params)
    } catch (e) {
      if (!silent) {
        error = e.message || String(e)
        stats = null
      }
    } finally {
      if (!silent) loading = false
    }
  }

  $effect(() => {
    if (!active) return
    const n = nonce
    const _days = days
    const _tid = templateId
    void _days
    void _tid
    refresh({ silent: n > 0 })
  })

  function onTemplateChange(e) {
    const v = e.currentTarget.value
    templateId = v === '' ? null : Number(v)
  }

  function onDaysChange(e) {
    days = Number(e.currentTarget.value) || 30
  }

  function shortDate(iso) {
    if (!iso || iso.length < 10) return iso || ''
    return iso.slice(5)
  }

  function pct(rate) {
    return `${Math.round((Number(rate) || 0) * 100)}%`
  }

  /** @param {any[]} daily */
  function buildLineChart(daily) {
    const rows = daily || []
    const n = rows.length
    const W = 640
    const H = 220
    const padL = 28
    const padR = 12
    const padT = 16
    const padB = 28
    const innerW = W - padL - padR
    const innerH = H - padT - padB
    let max = 1
    for (const row of rows) {
      max = Math.max(max, row.issued || 0, row.completed || 0, row.failed || 0)
    }

    /** @param {string} key */
    function series(key) {
      if (n === 0) return { points: '', dots: /** @type {{x:number,y:number,v:number}[]} */ ([]) }
      const dots = rows.map((row, i) => {
        const v = Number(row[key]) || 0
        const x = padL + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW)
        const y = padT + innerH - (v / max) * innerH
        return { x, y, v }
      })
      return {
        points: dots.map((d) => `${d.x.toFixed(1)},${d.y.toFixed(1)}`).join(' '),
        dots,
      }
    }

    const labelStep = Math.max(1, Math.ceil(n / 8))
    const xLabels = rows.map((row, i) => {
      const x = padL + (n === 1 ? innerW / 2 : (i / (n - 1)) * innerW)
      return {
        x,
        text: i % labelStep === 0 || i === n - 1 ? shortDate(row.date) : '',
      }
    })

    return {
      W,
      H,
      padL,
      padT,
      innerH,
      max,
      issued: series('issued'),
      completed: series('completed'),
      failed: series('failed'),
      xLabels,
      zeroY: padT + innerH,
    }
  }

  let line = $derived(buildLineChart(stats?.daily || []))
  let tmpl = $derived(stats?.template || null)
</script>

<section class="stats" aria-label="Статистика">
  <header class="stats__head">
    <div>
      <h2 class="stats__title">Статистика</h2>
      <p class="stats__sub">Выдача и закрытие · стрики периодики</p>
    </div>
    <div class="stats__controls">
      <label class="stats__field">
        <span class="stats__field-label">Период</span>
        <select class="stats__select" value={String(days)} onchange={onDaysChange}>
          {#each PERIODS as p}
            <option value={String(p.days)}>{p.label}</option>
          {/each}
        </select>
      </label>
      <button type="button" class="btn" onclick={() => refresh()} disabled={loading} aria-label="Обновить">
        <Icon name="renew" size={14} />
        <span class="btn__text">Обновить</span>
      </button>
    </div>
  </header>

  {#if error}
    <p class="stats__error" role="alert">{error}</p>
  {/if}

  {#if loading && !stats}
    <p class="stats__empty">Загрузка…</p>
  {:else if stats}
    <section class="panel" aria-labelledby="stats-daily-h">
      <div class="panel__head">
        <h3 id="stats-daily-h" class="panel__title">По дням</h3>
        <p class="panel__legend" aria-hidden="true">
          {#each SERIES as s}
            <span class="swatch" style:background={s.color}></span>{s.label}
          {/each}
        </p>
      </div>
      {#if !(stats.daily || []).length}
        <p class="stats__empty">Нет данных за период</p>
      {:else}
        <div class="panel__chart">
          <svg
            class="linechart"
            viewBox="0 0 {line.W} {line.H}"
            role="img"
            aria-label="Выдано, закрыто, провалено по дням"
          >
            <line
              class="linechart__axis"
              x1={line.padL}
              y1={line.zeroY}
              x2={line.W - 12}
              y2={line.zeroY}
            />
            {#each SERIES as s}
              {@const ser = line[s.key]}
              <polyline
                class="linechart__line"
                points={ser.points}
                style:stroke={s.color}
                fill="none"
              />
              {#each ser.dots as d}
                <circle
                  class="linechart__dot"
                  cx={d.x}
                  cy={d.y}
                  r="3.5"
                  style:fill={s.color}
                />
              {/each}
            {/each}
            {#each line.xLabels as lab}
              {#if lab.text}
                <text class="linechart__xlabel" x={lab.x} y={line.H - 8} text-anchor="middle"
                  >{lab.text}</text
                >
              {/if}
            {/each}
          </svg>
        </div>
      {/if}
    </section>

    <section class="panel" aria-labelledby="stats-tmpl-h">
      <div class="panel__head">
        <h3 id="stats-tmpl-h" class="panel__title">Шаблон</h3>
        <label class="stats__field">
          <span class="stats__field-label">Шаблон</span>
          <select
            class="stats__select"
            value={String(templateId ?? stats?.template?.id ?? '')}
            onchange={onTemplateChange}
          >
            {#if !(stats.templates || []).length}
              <option value="">Нет шаблонов</option>
            {:else}
              {#each stats.templates as t}
                <option value={String(t.id)}>{t.title}{t.enabled ? '' : ' (выкл.)'}</option>
              {/each}
            {/if}
          </select>
        </label>
      </div>

      {#if !tmpl}
        <p class="stats__empty">Выберите шаблон</p>
      {:else}
        <div class="stats__metrics">
          <div class="metric">
            <span class="metric__label">Стрик</span>
            <span class="metric__value">{tmpl.current_streak}</span>
          </div>
          <div class="metric">
            <span class="metric__label">Рекорд</span>
            <span class="metric__value">{tmpl.longest_streak}</span>
          </div>
          <div class="metric">
            <span class="metric__label">Закрыто</span>
            <span class="metric__value">{tmpl.closed}/{tmpl.total}</span>
            <span class="metric__pct">{pct(tmpl.close_rate)}</span>
          </div>
        </div>

        {#if !(tmpl.bars || []).length}
          <p class="stats__empty">Нет инстансов за период</p>
        {:else}
          <div class="panel__chart">
            <div class="outcome-row" role="img" aria-label="Исходы инстансов">
              {#each tmpl.bars as bar}
                <div class="outcome" data-outcome={bar.outcome}>
                  <span class="outcome__dot"></span>
                  <span class="outcome__label">{shortDate(bar.period_key)}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      {/if}
    </section>
  {/if}
</section>

<style>
  .stats {
    display: flex;
    flex-direction: column;
    gap: var(--space-5, 1.5rem);
    padding: var(--space-5, 1.5rem) var(--space-6, 2rem);
    min-height: 0;
    max-width: 56rem;
    margin: 0 auto;
    width: 100%;
    box-sizing: border-box;
  }

  .stats__head {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
  }

  .stats__title {
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-xl, 1.35rem);
    font-weight: 600;
    color: var(--color-fg, #e8e8e8);
  }

  .stats__sub {
    margin: 0.25rem 0 0;
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .stats__controls {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 0.65rem;
  }

  .stats__field {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .stats__field-label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .stats__select {
    min-width: 9rem;
    height: 2rem;
    padding: 0 0.5rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-sm, 2px);
    background: var(--color-bg-raised, #1a1a1a);
    color: var(--color-fg, #e8e8e8);
    font-family: var(--font-ui, sans-serif);
    font-size: var(--text-sm, 0.875rem);
  }

  .stats__error {
    margin: 0;
    color: var(--color-danger, #b54a3a);
    font-size: var(--text-sm, 0.875rem);
  }

  .stats__empty {
    margin: 0;
    color: var(--color-fg-subtle, #6e6e6e);
    font-size: var(--text-sm, 0.875rem);
    text-align: center;
  }

  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem) var(--space-5, 1.5rem);
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-md, 4px);
    background: color-mix(in srgb, var(--color-bg-raised, #1a1a1a) 92%, transparent);
  }

  .panel__head {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 0.65rem;
  }

  .panel__title {
    margin: 0;
    font-size: var(--text-sm, 0.875rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
    font-weight: 600;
  }

  .panel__legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.85rem;
    margin: 0;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .swatch {
    display: inline-block;
    width: 0.55rem;
    height: 0.55rem;
    margin-right: 0.3rem;
    vertical-align: 0.05rem;
    border-radius: 50%;
  }

  .panel__chart {
    display: flex;
    justify-content: center;
    width: 100%;
  }

  .linechart {
    width: 100%;
    max-width: 40rem;
    height: auto;
    display: block;
  }

  .linechart__axis {
    stroke: var(--color-border, #333);
    stroke-width: 1;
  }

  .linechart__line {
    stroke-width: 2;
    stroke-linejoin: round;
    stroke-linecap: round;
  }

  .linechart__dot {
    stroke: var(--color-bg-raised, #1a1a1a);
    stroke-width: 1.5;
  }

  .linechart__xlabel {
    fill: var(--color-fg-subtle, #6e6e6e);
    font-family: var(--font-mono, monospace);
    font-size: 9px;
  }

  .stats__metrics {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--space-5, 1.5rem);
  }

  .metric {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.15rem;
    min-width: 5rem;
  }

  .metric__label {
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .metric__value {
    font-family: var(--font-display, Georgia, serif);
    font-size: 1.75rem;
    line-height: 1;
    color: var(--color-fg, #e8e8e8);
    font-variant-numeric: tabular-nums;
  }

  .metric__pct {
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-accent, #c9a227);
  }

  .outcome-row {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 0.55rem 0.75rem;
    max-width: 40rem;
    padding: 0.35rem 0 0.15rem;
  }

  .outcome {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.35rem;
  }

  .outcome__dot {
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    background: color-mix(in srgb, var(--color-fg-muted, #9a9a9a) 55%, transparent);
  }

  .outcome[data-outcome='completed'] .outcome__dot {
    background: var(--color-success, #7a9e3a);
  }

  .outcome[data-outcome='miss'] .outcome__dot {
    background: var(--color-danger, #b54a3a);
  }

  .outcome[data-outcome='open'] .outcome__dot {
    background: color-mix(in srgb, var(--color-fg-muted, #9a9a9a) 55%, transparent);
    box-shadow: inset 0 0 0 1.5px var(--color-border, #333);
  }

  .outcome__label {
    font-family: var(--font-mono, monospace);
    font-size: 0.55rem;
    color: var(--color-fg-subtle, #6e6e6e);
  }
</style>
