<script>
  /**
   * 24h HH:MM as two selects — no native time input, which follows the OS
   * 12h/24h setting. With `allowNone`, hour "—" means "no time" and the
   * minutes go inert.
   * @type {{ hour?: string, minute?: string, allowNone?: boolean, disabled?: boolean, label?: string }}
   */
  let {
    hour = $bindable('00'),
    minute = $bindable('00'),
    allowNone = false,
    disabled = false,
    label = 'Время',
  } = $props()

  const HOURS = Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0'))
  const MINUTES = Array.from({ length: 60 }, (_, i) => String(i).padStart(2, '0'))
</script>

<span class="time-24" role="group" aria-label={label}>
  <select bind:value={hour} {disabled} aria-label="{label}: часы">
    {#if allowNone}<option value="">—</option>{/if}
    {#each HOURS as h}
      <option value={h}>{h}</option>
    {/each}
  </select>
  <span class="time-24__sep" aria-hidden="true">:</span>
  <select bind:value={minute} disabled={disabled || (allowNone && !hour)} aria-label="{label}: минуты">
    {#each MINUTES as m}
      <option value={m}>{m}</option>
    {/each}
  </select>
</span>
