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

<style>
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

  .opt-slider__opt:hover {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 80%, transparent);
  }

  .opt-slider__opt--on {
    background: color-mix(in srgb, var(--color-accent, #c9a227) 22%, var(--color-bg, #121212));
    color: var(--color-accent, #c9a227);
    font-weight: 600;
  }

  .opt-slider__opt--cat {
    color: var(--opt-color, var(--color-fg-muted, #9a9a9a));
    background: color-mix(in srgb, var(--opt-color, #9a9a9a) 12%, transparent);
  }

  .opt-slider__opt--cat[data-cat='none'] {
    color: var(--color-fg-muted, #9a9a9a);
    background: transparent;
  }

  .opt-slider__opt--cat.opt-slider__opt--on {
    color: color-mix(in srgb, var(--opt-color, #e8e8e8) 85%, #fff);
    background: color-mix(
      in srgb,
      var(--opt-color, #9a9a9a) 34%,
      var(--color-bg, #121212)
    );
  }

  .opt-slider__opt--cat[data-cat='none'].opt-slider__opt--on {
    color: var(--color-fg, #e8e8e8);
    background: color-mix(in srgb, var(--color-bg-hover, #2a2a2a) 80%, transparent);
  }
</style>
