<script>
  import HelpTip from './HelpTip.svelte'
  import OptionPills from './OptionPills.svelte'

  /** A step's auto-check: command, poll interval, mode, pipeline gate.
   * The mode/gate controls only appear once there is a command to run.
   * @type {{ command?: string, interval?: string, waitPrevious?: boolean, runMode?: string }} */
  let {
    command = $bindable(''),
    interval = $bindable(''),
    waitPrevious = $bindable(false),
    runMode = $bindable('poll'),
  } = $props()

  const MODES = [
    { id: 'poll', label: 'опрос' },
    { id: 'once', label: 'разово' },
  ]

  let hasCommand = $derived(Boolean(String(command || '').trim()))
</script>

<div class="autocheck">
  <div class="autocheck__row">
    <input
      type="text"
      class="mono autocheck__cmd"
      placeholder="команда автопроверки (необязательно)"
      aria-label="Команда автопроверки"
      bind:value={command}
      spellcheck="false"
    />
    {#if hasCommand && runMode !== 'once'}
      <input
        type="number"
        class="autocheck__interval"
        min="15"
        step="15"
        placeholder="сек"
        title="Интервал опроса, сек (мин. 15)"
        aria-label="Интервал опроса, сек"
        bind:value={interval}
      />
    {/if}
  </div>
  {#if hasCommand}
    <div class="autocheck__opts">
      <OptionPills options={MODES} bind:value={runMode} label="Режим автопроверки" compact />
      <label class="check">
        <input type="checkbox" bind:checked={waitPrevious} />
        ждать предыдущий
      </label>
      <HelpTip label="Как работает автопроверка">
        <p><b>Опрос</b> — команда запускается каждые N сек (по умолчанию 60), число из stdout становится прогрессом шага.</p>
        <p><b>Разово</b> — один запуск: код 0 закрывает шаг, иначе квест проваливается.</p>
        <p><b>Ждать предыдущий</b> — шаг стартует только после предыдущего: линейный пайплайн.</p>
      </HelpTip>
    </div>
  {/if}
</div>

<style>
  .autocheck {
    display: grid;
    gap: 0.4rem;
  }

  .autocheck__row {
    display: flex;
    gap: 0.4rem;
  }

  /* Two classes deep to outrank the shared .modal input rule. */
  .autocheck__row .autocheck__cmd {
    flex: 1 1 auto;
    font-size: var(--text-xs, 0.75rem);
  }

  .autocheck__row .autocheck__interval {
    flex: 0 0 4.5rem;
    width: 4.5rem;
  }

  .autocheck__opts {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.5rem 0.75rem;
  }
</style>
