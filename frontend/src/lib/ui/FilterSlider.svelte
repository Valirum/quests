<script>
  /**
   * @typedef {{
   *   id: string,
   *   label: string,
   *   kind?: 'status' | 'sig' | 'cat',
   *   color?: string,
   * }} FilterOpt
   * @type {{
   *   label: string,
   *   options: FilterOpt[],
   *   selected: Set<string>,
   *   wrap?: boolean,
   *   onToggle: (id: string) => void,
   * }}
   */
  let { label, options, selected, wrap = false, onToggle } = $props()
</script>

<div class="opt-group">
  <span class="opt-group__label">{label}</span>
  <div
    class="opt-slider"
    class:opt-slider--wrap={wrap}
    role="group"
    aria-label={label}
  >
    {#each options as opt (opt.id)}
      {@const on = selected.has(opt.id)}
      <button
        type="button"
        class="opt-slider__opt"
        class:opt-slider__opt--on={on}
        class:opt-slider__opt--sig={opt.kind === 'sig'}
        class:opt-slider__opt--cat={opt.kind === 'cat'}
        class:opt-slider__opt--status={opt.kind === 'status'}
        data-sig={opt.kind === 'sig' ? opt.id : undefined}
        data-status={opt.kind === 'status' ? opt.id : undefined}
        data-cat={opt.id === 'none' ? 'none' : undefined}
        style={opt.color ? `--opt-color: ${opt.color}` : undefined}
        aria-pressed={on}
        onclick={() => onToggle(opt.id)}
      >
        {opt.label}
      </button>
    {/each}
  </div>
</div>

<style>
  /* Which axis this row filters. It used to live only in aria-label, so on
     screen three different questions — section, status, rarity — looked like
     one undifferentiated wall of pills. */
  .opt-group {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    min-width: 0;
  }

  .opt-group__label {
    padding-left: 0.15rem;
    font-family: var(--font-ui, sans-serif);
    font-size: 0.65rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .opt-slider {
    display: flex;
    flex-direction: row;
    flex-wrap: nowrap;
    gap: 2px;
    padding: 3px;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-muted, #242424);
    overflow-x: auto;
  }

  .opt-slider--wrap {
    flex-wrap: wrap;
  }

  .opt-slider__opt {
    flex: 1 1 0;
    margin: 0;
    padding: 0.4rem 0.55rem;
    border: 0;
    border-radius: calc(var(--radius-lg, 12px) - 2px);
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    font: inherit;
    font-size: var(--text-xs, 0.75rem);
    letter-spacing: 0.02em;
    white-space: nowrap;
    cursor: pointer;
  }

  /* Colour per state (unpicked quiet, picked coloured) lives in
     styles/theme-accents.css, shared with the pickers in the modals. */
</style>
