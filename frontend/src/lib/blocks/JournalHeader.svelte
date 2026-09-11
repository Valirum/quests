<script>
  import Icon from '../ui/Icon.svelte'
  import ContextMenu from '../ui/ContextMenu.svelte'

  /** @type {{
   *   view: 'journal' | 'toc' | 'calendar' | 'hero' | 'stats',
   *   liveStatus: string,
   *   health: { api: string, overlay: string, telegram: string },
   *   onViewChange: (v: 'journal' | 'toc' | 'calendar' | 'hero' | 'stats') => void,
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

  let menuOpen = $state(false)
  let menuX = $state(0)
  let menuY = $state(0)

  let menuItems = $derived.by(() => {
    const items = [
      { id: 'assistant', label: 'Команда' },
      { id: 'settings', label: 'Настройки' },
    ]
    if (view === 'journal' || view === 'toc') {
      items.push(
        { id: 'templates', label: 'Шаблоны' },
        { id: 'questline', label: 'Новый квестлайн' },
      )
    }
    return items
  })

  function openMenu(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    menuX = Math.max(8, rect.right - 190)
    menuY = rect.bottom + 4
    menuOpen = true
  }

  function onMenuSelect(id) {
    if (id === 'assistant') onOpenAssistant()
    else if (id === 'settings') onOpenSettings()
    else if (id === 'templates') onOpenTemplates()
    else if (id === 'questline') onOpenCreateQuestline()
  }

  /** Actual overflow detection, not a guessed breakpoint: the labeled row
   * collapses to "…" + "+" exactly when it no longer fits next to the
   * brand/health cluster and the view tabs — whatever the window's actual
   * shape turns out to be. */
  let headerEl = $state(null)
  let leftEl = $state(null)
  let tabsEl = $state(null)
  let measureEl = $state(null)
  let collapsed = $state(false)

  function recomputeCollapse() {
    if (!headerEl || !leftEl || !tabsEl || !measureEl) return
    const styles = getComputedStyle(headerEl)
    const gap = (parseFloat(styles.columnGap) || 12) * 2
    const available = headerEl.clientWidth - leftEl.offsetWidth - tabsEl.offsetWidth - gap
    collapsed = measureEl.scrollWidth > available
  }

  $effect(() => {
    // Re-run whenever the measurer's own content changes shape (e.g. the
    // Шаблоны/Квестлайн buttons appearing only on some views).
    void view
    recomputeCollapse()
    const ro = new ResizeObserver(recomputeCollapse)
    if (headerEl) ro.observe(headerEl)
    if (leftEl) ro.observe(leftEl)
    if (tabsEl) ro.observe(tabsEl)
    if (measureEl) ro.observe(measureEl)
    window.addEventListener('resize', recomputeCollapse)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', recomputeCollapse)
    }
  })
</script>

<header class="journal__header" bind:this={headerEl}>
  <div class="header-left" bind:this={leftEl}>
    <div class="brand">
      <span class="brand__mark" aria-hidden="true">◈</span>
      <h1 class="brand__title">
        {#if view === 'hero'}
          Лист
        {:else if view === 'calendar'}
          Календарь
        {:else if view === 'stats'}
          Статистика
        {:else if view === 'toc'}
          Оглавление
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
      </span>
      <span class="health__chip" data-status={health.api} title="API" aria-label="API">
        <span class="health__dot" aria-hidden="true"></span>
      </span>
      <span class="health__chip" data-status={health.overlay} title="HUD / оверлей" aria-label="HUD / оверлей">
        <span class="health__dot" aria-hidden="true"></span>
      </span>
      <span class="health__chip" data-status={health.telegram} title="Telegram-бот" aria-label="Telegram-бот">
        <span class="health__dot" aria-hidden="true"></span>
      </span>
    </div>
  </div>
  <div class="view-tabs" role="tablist" aria-label="Раздел" bind:this={tabsEl}>
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
      class:view-tab--on={view === 'toc'}
      role="tab"
      aria-selected={view === 'toc'}
      onclick={() => onViewChange('toc')}
    >
      Оглавление
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
  {#snippet fullActions()}
    <button type="button" class="btn" onclick={onOpenAssistant} aria-label="Командная строка журнала">
      <Icon name="terminal" />
      <span class="btn__text">Команда</span>
    </button>
    <button type="button" class="btn" onclick={onOpenSettings} aria-label="Настройки">
      <Icon name="settings" />
      <span class="btn__text">Настройки</span>
    </button>
    {#if view === 'journal' || view === 'toc'}
      <button type="button" class="btn" onclick={onOpenTemplates} aria-label="Шаблоны периодики">
        <Icon name="renew" />
        <span class="btn__text">Шаблоны</span>
      </button>
      <button type="button" class="btn" onclick={onOpenCreateQuestline} aria-label="Новый квестлайн">
        <Icon name="flag" />
        <span class="btn__text">Квестлайн</span>
      </button>
    {/if}
    <button type="button" class="btn btn--accent" onclick={onOpenCreateQuest} aria-label="Новый квест">
      <Icon name="add" />
      <span class="btn__text">Новый квест</span>
    </button>
  {/snippet}

  {#if !collapsed}
    <div class="header-actions">
      {@render fullActions()}
    </div>
  {:else}
    <div class="header-actions">
      <button type="button" class="btn" onclick={openMenu} aria-haspopup="menu" aria-expanded={menuOpen} aria-label="Ещё действия">
        <Icon name="more" />
      </button>
      <button type="button" class="btn btn--accent btn--icon-only" onclick={() => onOpenCreateQuest()} aria-label="Новый квест">
        <Icon name="add" />
      </button>
    </div>
  {/if}

  <!-- Off-screen twin of the full row, always laid out at natural width
       (visibility:hidden keeps its box metrics, position:fixed keeps it
       out of the page) — the only way to know "would the labeled row fit"
       without guessing a breakpoint. -->
  <div class="header-actions header-actions--measure" bind:this={measureEl} aria-hidden="true" inert>
    {@render fullActions()}
  </div>
</header>

<ContextMenu
  open={menuOpen}
  x={menuX}
  y={menuY}
  items={menuItems}
  onSelect={onMenuSelect}
  onClose={() => (menuOpen = false)}
/>
