<script>
  import Icon from '../ui/Icon.svelte'
  import ContextMenu from '../ui/ContextMenu.svelte'

  /** @type {{
   *   view: 'journal' | 'toc' | 'notes' | 'attachments' | 'calendar' | 'hero' | 'stats',
   *   liveStatus: string,
   *   health: { api: string, overlay: string, telegram: string, webdav?: string, db?: string, detail?: Record<string, any> },
   *   sidebarCollapsed?: boolean,
   *   onToggleSidebar?: (() => void) | null,
   *   onViewChange: (v: 'journal' | 'toc' | 'notes' | 'attachments' | 'calendar' | 'hero' | 'stats') => void,
   *   onOpenSettings: () => void,
   *   onOpenTemplates: () => void,
   *   onOpenSecrets: () => void,
   *   onOpenTags: () => void,
   *   onOpenCreateQuestline: () => void,
   *   onOpenCreateQuest: () => void,
   *   onOpenAssistant: () => void,
   * }} */
  let {
    view,
    liveStatus,
    health,
    sidebarCollapsed = false,
    onToggleSidebar = null,
    onViewChange,
    onOpenSettings,
    onOpenTemplates,
    onOpenSecrets,
    onOpenTags,
    onOpenCreateQuestline,
    onOpenCreateQuest,
    onOpenAssistant,
  } = $props()

  /** Only 'journal' and 'notes' have a collapsible sidebar. */
  let showSidebarToggle = $derived(view === 'journal' || view === 'notes')

  /** Map WS states onto the same chip palette as API/HUD/Bot. */
  let liveChip = $derived.by(() => {
    const s = String(liveStatus || 'off')
    if (s === 'live') return { status: 'ok', title: 'WebSocket: live' }
    if (s === 'connecting' || s === 'reconnect') {
      return { status: 'unknown', title: `WebSocket: ${s}` }
    }
    return { status: 'offline', title: `WebSocket: ${s}` }
  })

  function davTitle(status) {
    if (status === 'ok') return 'WebDAV / вложения: онлайн'
    if (status === 'offline') return 'WebDAV / вложения: офлайн'
    return 'WebDAV / вложения: не настроен'
  }

  function dbTitle(status) {
    const detail = health?.detail?.components?.db?.detail
    if (status === 'warn') return detail || 'БД: схема новее API — обнови образ'
    if (status === 'ok') return detail || 'БД: схема совпадает с API'
    return 'БД: статус неизвестен'
  }

  let menuOpen = $state(false)
  let menuX = $state(0)
  let menuY = $state(0)

  let showLowActions = $derived(view === 'journal' || view === 'toc' || view === 'notes')

  /** @type {'full' | 'icons' | 'icons-core' | 'icons-primary'} */
  let actionsMode = $state('full')

  /** Overflow menu lists only actions hidden behind ⋮ for the current stage. */
  let menuItems = $derived.by(() => {
    /** @type {{ id: string, label: string }[]} */
    const items = []
    if (actionsMode === 'icons-primary') {
      items.push({ id: 'settings', label: 'Настройки' })
    }
    if ((actionsMode === 'icons-core' || actionsMode === 'icons-primary') && showLowActions) {
      items.push(
        { id: 'templates', label: 'Шаблоны' },
        { id: 'secrets', label: 'Секреты' },
        { id: 'tags', label: 'Теги' },
        { id: 'questline', label: 'Новый квестлайн' },
      )
    }
    return items
  })

  function openMenu(event) {
    const rect = event.currentTarget.getBoundingClientRect()
    menuX = rect.right
    menuY = rect.bottom + 4
    menuOpen = true
  }

  function onMenuSelect(id) {
    if (id === 'assistant') onOpenAssistant()
    else if (id === 'settings') onOpenSettings()
    else if (id === 'templates') onOpenTemplates()
    else if (id === 'secrets') onOpenSecrets()
    else if (id === 'tags') onOpenTags()
    else if (id === 'questline') onOpenCreateQuestline()
  }

  /** Progressive collapse: pick the widest actions stage (full → icons →
   * icons-core → icons-primary) that still fits in headerSlots().right. */
  let headerEl = $state(null)
  let leftEl = $state(null)
  let tabsEl = $state(null)
  let measureFullEl = $state(null)
  let measureIconsEl = $state(null)
  let measureCoreEl = $state(null)
  let measurePrimaryEl = $state(null)
  let actionsEl = $state(null)

  const ACTION_STAGES = /** @type {const} */ (['full', 'icons', 'icons-core', 'icons-primary'])

  let showOverflow = $derived(actionsMode === 'icons-core' || actionsMode === 'icons-primary')
  let showSettingsBtn = $derived(
    actionsMode === 'full' || actionsMode === 'icons' || actionsMode === 'icons-core',
  )
  let showLowBtns = $derived((actionsMode === 'full' || actionsMode === 'icons') && showLowActions)

  // Same idea, independently, for the health chips: labeled by default,
  // dots-only only once the brand+health cluster actually doesn't fit.
  let brandEl = $state(null)
  let healthEl = $state(null)
  let healthMeasureEl = $state(null)
  let healthCollapsed = $state(false)

  /** Free width on each side of the tab block.
   *
   * The tabs are centred on the header itself, not on the space between the
   * clusters — so the room left over is not (header - tabs) / 2. With a 324px
   * brand cluster on the left and a 576px action row on the right, splitting
   * the remainder evenly says everything fits while the right-hand side is in
   * fact 19px short, and the labelled buttons slide under the tabs. Measure
   * the actual gaps beside the tab block instead.
   *
   * In portrait the CSS drops the tabs onto their own row; then the two
   * clusters share one line and only have to clear each other — and the
   * health chips, which portrait CSS pulls out of header-left and centers
   * on the header absolutely, so leftEl's width no longer accounts for them.
   * There each side gets whatever lies between its cluster and the header's
   * center, and health's own box is subtracted from the actions' side.
   */
  function headerSlots() {
    const cs = getComputedStyle(headerEl)
    const gap = parseFloat(cs.columnGap) || 12
    const rect = headerEl.getBoundingClientRect()
    const contentLeft = rect.left + (parseFloat(cs.paddingLeft) || 0)
    const contentRight = rect.right - (parseFloat(cs.paddingRight) || 0)

    if (getComputedStyle(tabsEl).position !== 'absolute') {
      const width = contentRight - contentLeft
      if (healthEl && getComputedStyle(healthEl).position === 'absolute') {
        const center = (rect.left + rect.right) / 2
        const health = healthEl.getBoundingClientRect()
        return {
          right: contentRight - health.right - gap,
          // Health is centered, so it needs room for half its width on
          // *both* sides of the center; report the tighter side, doubled.
          health:
            2 *
            Math.min(
              center - (contentLeft + leftEl.offsetWidth) - gap,
              contentRight - (actionsEl?.offsetWidth ?? 0) - center - gap,
            ),
        }
      }
      return {
        left: width - (actionsEl?.offsetWidth ?? 0) - gap,
        right: width - leftEl.offsetWidth - gap,
      }
    }
    const tabs = tabsEl.getBoundingClientRect()
    return {
      left: tabs.left - contentLeft - gap,
      right: contentRight - tabs.right - gap,
    }
  }

  function recomputeCollapse() {
    if (!headerEl || !leftEl || !tabsEl || !measureFullEl) return
    const available = headerSlots().right
    const widths = {
      full: measureFullEl.scrollWidth,
      icons: measureIconsEl?.scrollWidth ?? Infinity,
      'icons-core': measureCoreEl?.scrollWidth ?? Infinity,
      'icons-primary': measurePrimaryEl?.scrollWidth ?? Infinity,
    }
    for (const stage of ACTION_STAGES) {
      if (widths[stage] <= available) {
        actionsMode = stage
        return
      }
    }
    actionsMode = 'icons-primary'
  }

  function recomputeHealthCollapse() {
    if (!headerEl || !leftEl || !tabsEl || !brandEl || !healthMeasureEl) return
    const slots = headerSlots()
    const forHealth = slots.health ?? slots.left - brandEl.offsetWidth - 12 /* header-left gap */
    healthCollapsed = healthMeasureEl.scrollWidth > forHealth
  }

  function recomputeAll() {
    recomputeCollapse()
    recomputeHealthCollapse()
  }

  $effect(() => {
    // Re-run whenever the measurer's own content changes shape (e.g. the
    // Шаблоны/Квестлайн buttons appearing only on some views).
    void view
    recomputeAll()
    // First paint measures fallback-font widths: Literata and IBM Plex land
    // afterwards and widen both the tabs and the buttons, which is exactly
    // what this decision depends on. Re-measure once layout has settled and
    // again once the real fonts are in.
    const raf = requestAnimationFrame(recomputeAll)
    document.fonts?.ready.then(recomputeAll)
    const ro = new ResizeObserver(recomputeAll)
    if (headerEl) ro.observe(headerEl)
    if (leftEl) ro.observe(leftEl)
    if (tabsEl) ro.observe(tabsEl)
    if (measureFullEl) ro.observe(measureFullEl)
    if (measureIconsEl) ro.observe(measureIconsEl)
    if (measureCoreEl) ro.observe(measureCoreEl)
    if (measurePrimaryEl) ro.observe(measurePrimaryEl)
    if (brandEl) ro.observe(brandEl)
    if (healthEl) ro.observe(healthEl)
    if (healthMeasureEl) ro.observe(healthMeasureEl)
    if (actionsEl) ro.observe(actionsEl)
    window.addEventListener('resize', recomputeAll)
    return () => {
      cancelAnimationFrame(raf)
      ro.disconnect()
      window.removeEventListener('resize', recomputeAll)
    }
  })
</script>

<header class="journal__header" bind:this={headerEl}>
  <div class="header-left" bind:this={leftEl}>
    {#if showSidebarToggle}
      <button
        type="button"
        class="btn btn--ghost btn--icon sidebar-toggle"
        onclick={onToggleSidebar}
        title={sidebarCollapsed ? 'Показать боковую панель' : 'Скрыть боковую панель'}
        aria-label={sidebarCollapsed ? 'Показать боковую панель' : 'Скрыть боковую панель'}
        aria-pressed={sidebarCollapsed}
      >
        <Icon name="sidebar" size={16} />
      </button>
    {/if}
    <!-- No section label here: tabbed views show theirs via the tab
         highlight, and hero/stats open with their own page heading right
         below — a header copy just repeated it and, on a phone, collided
         with the health chips. -->
    <div class="brand" bind:this={brandEl}></div>

    {#snippet healthChips()}
      <span
        class="health__chip"
        data-status={liveChip.status}
        title={liveChip.title}
        aria-label={liveChip.title}
      >
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">Live</span>{/if}
      </span>
      <span class="health__chip" data-status={health.api} title="API" aria-label="API">
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">API</span>{/if}
      </span>
      <span
        class="health__chip"
        data-status={health.db || 'unknown'}
        title={dbTitle(health.db)}
        aria-label={dbTitle(health.db)}
      >
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">DB</span>{/if}
      </span>
      <span class="health__chip" data-status={health.overlay} title="HUD / оверлей" aria-label="HUD / оверлей">
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">HUD</span>{/if}
      </span>
      <span class="health__chip" data-status={health.telegram} title="Telegram-бот" aria-label="Telegram-бот">
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">Bot</span>{/if}
      </span>
      <span
        class="health__chip"
        data-status={health.webdav || 'unknown'}
        title={davTitle(health.webdav)}
        aria-label={davTitle(health.webdav)}
      >
        <span class="health__dot" aria-hidden="true"></span>
        {#if !healthCollapsed}<span class="health__label">DAV</span>{/if}
      </span>
    {/snippet}

    <div class="health" bind:this={healthEl} role="status" aria-label="Состояние сервисов">
      {@render healthChips()}
    </div>
  </div>

  <!-- Off-screen twin of the labeled health row, always at natural width,
       used only to decide whether the labels fit. -->
  <div class="health health--measure" bind:this={healthMeasureEl} aria-hidden="true" inert>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">Live</span>
    </span>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">API</span>
    </span>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">DB</span>
    </span>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">HUD</span>
    </span>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">Bot</span>
    </span>
    <span class="health__chip">
      <span class="health__dot" aria-hidden="true"></span>
      <span class="health__label">DAV</span>
    </span>
  </div>
  <div class="view-tabs" role="tablist" aria-label="Раздел" bind:this={tabsEl}>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'journal'}
      role="tab"
      aria-selected={view === 'journal'}
      title="Журнал"
      onclick={() => onViewChange('journal')}
    >
      <Icon name="scroll" size={15} />
      <span class="view-tab__label">Журнал</span>
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'toc'}
      role="tab"
      aria-selected={view === 'toc'}
      title="Оглавление"
      onclick={() => onViewChange('toc')}
    >
      <Icon name="list" size={15} />
      <span class="view-tab__label">Оглавление</span>
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'notes'}
      role="tab"
      aria-selected={view === 'notes'}
      title="Заметки"
      onclick={() => onViewChange('notes')}
    >
      <Icon name="document" size={15} />
      <span class="view-tab__label">Заметки</span>
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'attachments'}
      role="tab"
      aria-selected={view === 'attachments'}
      title="Вложения"
      onclick={() => onViewChange('attachments')}
    >
      <Icon name="attachment" size={15} />
      <span class="view-tab__label">Вложения</span>
    </button>
    <button
      type="button"
      class="view-tab"
      class:view-tab--on={view === 'calendar'}
      role="tab"
      aria-selected={view === 'calendar'}
      title="Календарь"
      onclick={() => onViewChange('calendar')}
    >
      <Icon name="calendar" size={15} />
      <span class="view-tab__label">Календарь</span>
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
    {#if view === 'journal' || view === 'toc' || view === 'notes'}
      <button type="button" class="btn" onclick={onOpenTemplates} aria-label="Шаблоны периодики">
        <Icon name="repeat" />
        <span class="btn__text">Шаблоны</span>
      </button>
      <button type="button" class="btn" onclick={onOpenSecrets} aria-label="Секреты">
        <Icon name="key" />
        <span class="btn__text">Секреты</span>
      </button>
      <button type="button" class="btn" onclick={onOpenTags} aria-label="Теги">
        <Icon name="pin" />
        <span class="btn__text">Теги</span>
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

  <div
    class="header-actions"
    class:header-actions--icons={actionsMode !== 'full'}
    bind:this={actionsEl}
  >
    <button type="button" class="btn" onclick={onOpenAssistant} aria-label="Командная строка журнала">
      <Icon name="terminal" />
      <span class="btn__text">Команда</span>
    </button>
    {#if showSettingsBtn}
      <button type="button" class="btn" onclick={onOpenSettings} aria-label="Настройки">
        <Icon name="settings" />
        <span class="btn__text">Настройки</span>
      </button>
    {/if}
    {#if showLowBtns}
      <button type="button" class="btn" onclick={onOpenTemplates} aria-label="Шаблоны периодики">
        <Icon name="repeat" />
        <span class="btn__text">Шаблоны</span>
      </button>
      <button type="button" class="btn" onclick={onOpenSecrets} aria-label="Секреты">
        <Icon name="key" />
        <span class="btn__text">Секреты</span>
      </button>
      <button type="button" class="btn" onclick={onOpenTags} aria-label="Теги">
        <Icon name="pin" />
        <span class="btn__text">Теги</span>
      </button>
      <button type="button" class="btn" onclick={onOpenCreateQuestline} aria-label="Новый квестлайн">
        <Icon name="flag" />
        <span class="btn__text">Квестлайн</span>
      </button>
    {/if}
    {#if showOverflow && (actionsMode === 'icons-primary' || showLowActions)}
      <button
        type="button"
        class="btn btn--overflow"
        onclick={openMenu}
        aria-haspopup="menu"
        aria-expanded={menuOpen}
        aria-label="Ещё действия"
      >
        <Icon name="more" />
      </button>
    {/if}
    <button type="button" class="btn btn--accent" onclick={onOpenCreateQuest} aria-label="Новый квест">
      <Icon name="add" />
      <span class="btn__text">Новый квест</span>
    </button>
  </div>

  <!-- Off-screen twins: one row per collapse stage, measured against headerSlots().right -->
  <div class="header-actions header-actions--measure" bind:this={measureFullEl} aria-hidden="true" inert>
    {@render fullActions()}
  </div>
  <div
    class="header-actions header-actions--measure header-actions--icons"
    bind:this={measureIconsEl}
    aria-hidden="true"
    inert
  >
    {@render fullActions()}
  </div>
  <div
    class="header-actions header-actions--measure header-actions--icons"
    bind:this={measureCoreEl}
    aria-hidden="true"
    inert
  >
    <button type="button" class="btn" tabindex="-1"><Icon name="terminal" /><span class="btn__text">Команда</span></button>
    <button type="button" class="btn" tabindex="-1"><Icon name="settings" /><span class="btn__text">Настройки</span></button>
    {#if showLowActions}
      <button type="button" class="btn btn--overflow" tabindex="-1"><Icon name="more" /></button>
    {/if}
    <button type="button" class="btn btn--accent" tabindex="-1"><Icon name="add" /><span class="btn__text">Новый квест</span></button>
  </div>
  <div
    class="header-actions header-actions--measure header-actions--icons"
    bind:this={measurePrimaryEl}
    aria-hidden="true"
    inert
  >
    <button type="button" class="btn" tabindex="-1"><Icon name="terminal" /><span class="btn__text">Команда</span></button>
    <button type="button" class="btn btn--overflow" tabindex="-1"><Icon name="more" /></button>
    <button type="button" class="btn btn--accent" tabindex="-1"><Icon name="add" /><span class="btn__text">Новый квест</span></button>
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
