<script>
  import OptionPills from './OptionPills.svelte'

  /**
   * Labeled multi-select pill row for the TOC filters.
   * @type {{
   *   label: string,
   *   options: import('./OptionPills.svelte').PillOption[],
   *   selected: Set<string>,
   *   wrap?: boolean,
   *   onToggle: (id: string) => void,
   * }}
   */
  let { label, options, selected, wrap = false, onToggle } = $props()

  // The TOC's "no section" option is id 'none'.
  let pillOptions = $derived(options.map((o) => (o.id === 'none' ? { ...o, none: true } : o)))
</script>

<div class="opt-group">
  <span class="opt-group__label">{label}</span>
  <OptionPills options={pillOptions} {selected} {onToggle} {label} {wrap} />
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
</style>
