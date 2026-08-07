<script>
  import Icon from '../ui/Icon.svelte'

  /** @type {{
   *   view: 'journal' | 'hero',
   *   liveStatus: string,
   *   health: { api: string, overlay: string, telegram: string },
   *   onViewChange: (v: 'journal' | 'hero') => void,
   *   onOpenSettings: () => void,
   *   onOpenTemplates: () => void,
   *   onOpenCreateQuestline: () => void,
   *   onOpenCreateQuest: () => void,
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
  } = $props()
</script>

<header class="journal__header">
  <div class="header-left">
    <div class="brand">
      <span class="brand__mark" aria-hidden="true">◈</span>
      <h1 class="brand__title">{view === 'hero' ? 'Лист' : 'Задачи'}</h1>
    </div>
    <span
      class="live"
      data-status={liveStatus}
      title={`Live sync: ${liveStatus}`}
      aria-label={`Live sync: ${liveStatus}`}
    >
      <span class="live__dot" aria-hidden="true"></span>
      <span class="live__text">{liveStatus}</span>
    </span>
    <div class="health" role="status" aria-label="Состояние сервисов">
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
      class:view-tab--on={view === 'hero'}
      role="tab"
      aria-selected={view === 'hero'}
      onclick={() => onViewChange('hero')}
    >
      Лист
    </button>
  </div>
  <div class="header-actions">
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
