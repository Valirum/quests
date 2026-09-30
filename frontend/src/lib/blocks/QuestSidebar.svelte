<script>
  import Icon from '../ui/Icon.svelte'
  import QuestlineIcon from '../ui/QuestlineIcon.svelte'
  import {
    isQuestInactive,
    periodBadge,
    questTimer,
    quantifiedProgress,
    significanceLabel,
    statusColor,
  } from '../js/questFormat.js'

  /** @type {{
   *   loading: boolean,
   *   quests: any[],
   *   matchedQuests: any[],
   *   listedQuests: any[],
   *   byCategory: any[],
   *   delayedQuests: any[],
   *   delayedOpen: boolean,
   *   selectedId: number | null,
   *   searchQuery: string,
   *   showAllQuests: boolean,
   *   categoryOpen: Record<string, boolean>,
   *   lineOpen: Record<string, boolean>,
   *   nowMs: number,
   *   onSelect: (id: number) => void,
   *   onTogglePin: (quest: any, event: Event) => void,
   *   onQuestContextMenu: (event: MouseEvent, quest: any) => void,
   *   onLineContextMenu: (event: MouseEvent, line: any) => void,
   *   onToggleCategory: (key: string) => void,
   *   onToggleLine: (catKey: string, lineKey: string) => void,
   *   onToggleDelayed: () => void,
   *   categories: any[],
   *   scopeCategoryId: number | null,
   *   scopeQuestlineId: number | null,
   *   scopeQuestlineOptions: any[],
   *   onScopeCategory: (id: number | null) => void,
   *   onScopeQuestline: (id: number | null) => void,
   * }} */
  let {
    loading,
    quests,
    matchedQuests,
    listedQuests,
    byCategory,
    delayedQuests,
    delayedOpen,
    selectedId,
    searchQuery = $bindable(''),
    showAllQuests = $bindable(false),
    categoryOpen,
    lineOpen,
    nowMs,
    onSelect,
    onTogglePin,
    onQuestContextMenu,
    onLineContextMenu,
    onToggleCategory,
    onToggleLine,
    onToggleDelayed,
    categories,
    scopeCategoryId,
    scopeQuestlineId,
    scopeQuestlineOptions,
    onScopeCategory,
    onScopeQuestline,
  } = $props()

  function onScopeCategoryChange(event) {
    const v = event.currentTarget.value
    onScopeCategory(v === '' ? null : Number(v))
  }
  function onScopeQuestlineChange(event) {
    const v = event.currentTarget.value
    onScopeQuestline(v === '' ? null : Number(v))
  }

  function isCategoryOpen(key) {
    return categoryOpen[key] !== false
  }

  function isLineOpen(catKey, lineKey) {
    return lineOpen[`${catKey}:${lineKey}`] !== false
  }
</script>

<aside class="sidebar">
  <div class="sidebar__tools">
    <input
      class="search"
      type="search"
      placeholder="Поиск…"
      bind:value={searchQuery}
      aria-label="Поиск по названию, разделу, квестлайну, описанию, шагам"
    />
    <label class="sidebar__filter">
      <input type="checkbox" bind:checked={showAllQuests} />
      <span>Показывать завершённые</span>
    </label>
    <div class="sidebar__scope">
      <select
        class="sidebar__scope-select"
        value={scopeCategoryId ?? ''}
        onchange={onScopeCategoryChange}
        aria-label="Сузить до раздела"
      >
        <option value="">Все разделы</option>
        {#each categories as cat (cat.id)}
          <option value={cat.id}>{cat.label}</option>
        {/each}
      </select>
      {#if scopeCategoryId != null}
        <select
          class="sidebar__scope-select"
          value={scopeQuestlineId ?? ''}
          onchange={onScopeQuestlineChange}
          aria-label="Сузить до квестлайна"
        >
          <option value="">Весь раздел</option>
          {#each scopeQuestlineOptions as line (line.id)}
            <option value={line.id}>{line.title}</option>
          {/each}
        </select>
      {/if}
    </div>
  </div>
  {#snippet questRow(q)}
    {@const rowTimer = questTimer(q, nowMs)}
    {@const frac = quantifiedProgress(q)}
    <button
      type="button"
      class="quest-row"
      class:quest-row--active={q.id === selectedId}
      class:quest-row--pinned={q.pinned}
      class:quest-row--inactive={isQuestInactive(q) && q.status !== 'delayed'}
      onclick={() => onSelect(q.id)}
      oncontextmenu={(e) => onQuestContextMenu(e, q)}
    >
      <span class="quest-row__top">
        <span class="quest-row__title">{q.title}</span>
        <span
          class="pin-btn"
          class:pin-btn--on={q.pinned}
          role="button"
          tabindex="0"
          title={q.pinned ? 'Открепить' : 'В избранное'}
          aria-label={q.pinned ? 'Открепить' : 'В избранное'}
          onclick={(e) => onTogglePin(q, e)}
          onkeydown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') onTogglePin(q, e)
          }}
        >
          <Icon name={q.pinned ? 'pin-filled' : 'pin'} size={14} />
        </span>
      </span>
      {#if q.significance && q.significance !== 'common'}
        <span class="quest-row__sig" data-sig={q.significance}>{significanceLabel(q)}</span>
      {/if}
      {#if q.status !== 'active' || periodBadge(q) || rowTimer || frac}
        <span class="quest-row__meta">
          <span class="quest-row__meta-left">
            {#if q.status !== 'active'}
              <span class="status" style:color={statusColor(q.status)}>{q.status}</span>
            {/if}
            {#if periodBadge(q)}
              <span class="period-badge" title="Периодический инстанс">{periodBadge(q)}</span>
            {/if}
            {#if rowTimer}
              <span class="row-timer" data-tone={rowTimer.tone}>{rowTimer.label}</span>
            {/if}
          </span>
          {#if frac}
            <span class="progress">{frac}</span>
          {/if}
        </span>
      {/if}
    </button>
  {/snippet}

  {#if delayedQuests.length > 0}
    <div class="sidebar__delayed">
      <button
        type="button"
        class="sidebar__delayed-toggle"
        aria-expanded={delayedOpen}
        onclick={onToggleDelayed}
      >
        <span class="sidebar__delayed-label">Отложено</span>
        <span class="sidebar__delayed-hint">{delayedQuests.length}</span>
        <span class="sidebar__delayed-chevron" aria-hidden="true">
          <Icon name={delayedOpen ? 'chevron-down' : 'chevron-right'} size={12} />
        </span>
      </button>
      {#if delayedOpen}
        <div class="sidebar__delayed-body">
          {#each delayedQuests as q (q.id)}
            {@render questRow(q)}
          {/each}
        </div>
      {/if}
    </div>
  {/if}
  <div class="sidebar__list" aria-label="Список квестов">
    {#if loading}
      <p class="empty">Загрузка…</p>
    {:else if quests.length === 0}
      <p class="empty">Квестов нет</p>
    {:else if matchedQuests.length === 0}
      <p class="empty">Ничего не найдено</p>
    {:else if listedQuests.length === 0}
      <p class="empty">Нет активных — включи «Показывать завершённые»</p>
    {:else}
      {#snippet categoryBody(g)}
        {#if g.lines.length === 0}
          {#each g.alone as q (q.id)}
            {@render questRow(q)}
          {/each}
        {:else}
          {#each g.lines as line (line.key)}
            <div class="quest-line" style="--line-color: {line.color || '#9a9a9a'}">
              <button
                type="button"
                class="quest-line__toggle"
                aria-expanded={isLineOpen(g.key, line.key)}
                onclick={() => onToggleLine(g.key, line.key)}
                oncontextmenu={(e) => onLineContextMenu(e, line)}
              >
                <span class="quest-line__icon" aria-hidden="true">
                  <QuestlineIcon
                    icon={line.icon || 'document'}
                    iconUrl={line.icon_url || null}
                    size="sm"
                  />
                </span>
                <span class="quest-line__label">{line.title}</span>
                <span class="quest-line__hint">{line.quests.length}</span>
                <span class="quest-line__chevron" aria-hidden="true">
                  <Icon
                    name={isLineOpen(g.key, line.key) ? 'chevron-down' : 'chevron-right'}
                    size={12}
                  />
                </span>
              </button>
              {#if isLineOpen(g.key, line.key)}
                <div class="quest-line__body">
                  {#each line.quests as q (q.id)}
                    {@render questRow(q)}
                  {/each}
                </div>
              {/if}
            </div>
          {/each}
          {#if g.alone.length > 0}
            <div class="quest-line quest-line--alone">
              <div class="quest-line__alone-label">Без квестлайна</div>
              <div class="quest-line__body">
                {#each g.alone as q (q.id)}
                  {@render questRow(q)}
                {/each}
              </div>
            </div>
          {/if}
        {/if}
      {/snippet}

      {#each byCategory as g (g.key)}
        <div
          class="quest-subgroup"
          class:quest-subgroup--plain={g.key === 'none'}
          style={g.color ? `--cat-color: ${g.color}` : undefined}
        >
          <button
            type="button"
            class="quest-subgroup__toggle"
            aria-expanded={isCategoryOpen(g.key)}
            onclick={() => onToggleCategory(g.key)}
          >
            <span class="quest-subgroup__swatch" aria-hidden="true"></span>
            <span class="quest-subgroup__label">{g.label}</span>
            <span class="quest-subgroup__hint">{g.questCount}</span>
            <span class="quest-subgroup__chevron" aria-hidden="true">
              <Icon
                name={isCategoryOpen(g.key) ? 'chevron-down' : 'chevron-right'}
                size={12}
              />
            </span>
          </button>
          {#if isCategoryOpen(g.key)}
            <div class="quest-subgroup__body">
              {@render categoryBody(g)}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</aside>
