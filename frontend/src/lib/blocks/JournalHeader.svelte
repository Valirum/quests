<script>
  import Icon from '../ui/Icon.svelte'

  /** @type {{
   *   view: 'journal' | 'calendar' | 'hero' | 'stats',
   *   liveStatus: string,
   *   health: { api: string, overlay: string, telegram: string },
   *   onViewChange: (v: 'journal' | 'calendar' | 'hero' | 'stats') => void,
   *   onOpenSettings: () => void,
   *   onOpenTemplates: () => void,
   *   onOpenCreateQuestline: () => void,
   *   onOpenCreateQuest: () => void,
   *   onOpenAssistant: () => void,
   * }} */
  let {
    view,
    liveStatus,
    health,
    onViewChange,
    onOpenSettings,
    onOpenTemplates,
    onOpenCreateQuestline,
    onOpenCreateQuest,
    onOpenAssistant,
  } = $props()

  /** Map WS states onto the same chip palette as API/HUD/Bot. */
  let liveChip = $derived.by(() => {
    const s = String(liveStatus || 'off')
    if (s === 'live') return { status: 'ok', title: 'WebSocket: live' }
    if (s === 'connecting' || s === 'reconnect') {
      return { status: 'unknown', title: `WebSocket: ${s}` }
    }
    return { status: 'offline', title: `WebSocket: ${s}` }
  })
</script>

<header class="journal__header">
  <div class="header-left">
    <div class="brand">
      <span class="brand__mark" aria-hidden="true">◈</span>
      <h1 class="brand__title">
        {#if view === 'hero'}
          Лист
        {:else if view === 'calendar'}
          Календарь
        {:else if view === 'stats'}
          Статистика
        {:else}
          Задачи
        {/if}
      </h1>
    </div>
    <div class="health" role="status" aria-label="Состояние сервисов">
      <span
        class="health__chip"
        data-status={liveChip.status}
        title={liveChip.title}
        aria-label={liveChip.title}
      >
        <span class="health__dot" aria-hidden="true"></span>
        <span class="health__label">Live</span>
      </span>
      <span class="health__chip" data-status={health.api} title="API">
        <span class="health__dot" aria-hidden="true"></span>
        <span class="health__label">API</span>
      </span>
      <span class="health__chip" data-status={health.overlay} title="HUD / оверлей">
        <span class="health__dot" aria-hidden="true"></span>
        <span class="health__label">HUD</span>
      </span>
      <span class="health__chip" data-status={health.telegram} title="Telegram-бот">
        <span class="health__dot" aria-hidden="true"></span>
        <span class="health__label">Bot</span>
      </span>
    </div>
  </div>
  <div class="view-tabs" role="tablist" aria-label="Раздел">
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'journal'}
      role="tab"
      aria-selected={view === 'journal'}
      onclick={() => onViewChange('journal')}
    >
      Журнал
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'calendar'}
      role="tab"
      aria-selected={view === 'calendar'}
      onclick={() => onViewChange('calendar')}
    >
      Календарь
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'hero'}
      role="tab"
      aria-selected={view === 'hero'}
      onclick={() => onViewChange('hero')}
    >
      Лист
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'stats'}
      role="tab"
      aria-selected={view === 'stats'}
      onclick={() => onViewChange('stats')}
    >
      Статистика
    </button>
  </div>
  <div class="header-actions">
    <button type="button" class="btn" onclick={onOpenAssistant} aria-label="Командная строка журнала">
      <Icon name="terminal" />
      <span class="btn__text">Команда</span>
    </button>
    <button type="button" class="btn" onclick={onOpenSettings} aria-label="Настройки">
      <Icon name="settings" />
      <span class="btn__text">Настройки</span>
    </button>
    {#if view === 'journal'}
      <button type="button" class="btn" onclick={onOpenTemplates} aria-label="Шаблоны периодики">
        <Icon name="renew" />
        <span class="btn__text">Шаблоны</span>
      </button>
      <button type="button" class="btn" onclick={onOpenCreateQuestline} aria-label="Новый квестлайн">
        <Icon name="flag" />
        <span class="btn__text">Квестлайн</span>
      </button>
      <button type="button" class="btn btn--accent" onclick={onOpenCreateQuest} aria-label="Новый квест">
        <Icon name="add" />
        <span class="btn__text">Новый квест</span>
      </button>
    {/if}
  </div>
</header>
