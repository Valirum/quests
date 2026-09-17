<script>
  import Icon from '../ui/Icon.svelte'
  import ContextMenu from '../ui/ContextMenu.svelte'

  /** @type {{
   *   view: 'journal' | 'toc' | 'calendar' | 'hero' | 'stats',
   *   liveStatus: string,
   *   health: { api: string, overlay: string, telegram: string, webdav?: string },
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

  function davTitle(status) {
    if (status === 'ok') return 'WebDAV / вложения: онлайн'
    if (status === 'offline') return 'WebDAV / вложения: офлайн'
    return 'WebDAV / вложения: не настроен'
  }

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
    menuX = rect.right
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
  let actionsEl = $state(null)
  let collapsed = $state(false)

  // Same idea, independently, for the health chips: labeled by default,
  // dots-only only once the brand+health cluster actually doesn't fit.
  let brandEl = $state(null)
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
   * clusters share one line and only have to clear each other.
   */
  function headerSlots() {
    const cs = getComputedStyle(headerEl)
    const gap = parseFloat(cs.columnGap) || 12
    const rect = headerEl.getBoundingClientRect()
    const contentLeft = rect.left + (parseFloat(cs.paddingLeft) || 0)
    const contentRight = rect.right - (parseFloat(cs.paddingRight) || 0)

    if (getComputedStyle(tabsEl).position !== 'absolute') {
      const width = contentRight - contentLeft
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
    if (!headerEl || !leftEl || !tabsEl || !measureEl) return
    collapsed = measureEl.scrollWidth > headerSlots().right
  }

  function recomputeHealthCollapse() {
    if (!headerEl || !leftEl || !tabsEl || !brandEl || !healthMeasureEl) return
    const forHealth = headerSlots().left - brandEl.offsetWidth - 12 /* header-left gap */
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
    if (measureEl) ro.observe(measureEl)
    if (brandEl) ro.observe(brandEl)
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
    <div class="brand" bind:this={brandEl}>
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

    <div class="health" role="status" aria-label="Состояние сервисов">
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
    <div class="header-actions" bind:this={actionsEl}>
      {@render fullActions()}
    </div>
  {:else}
    <div class="header-actions" bind:this={actionsEl}>
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
