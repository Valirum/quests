<script>
  import Icon from './Icon.svelte'
  import {
    isQuestInactive,
    periodBadge,
    questTimer,
    significanceLabel,
    statusColor,
  } from './questFormat.js'

  /** @type {{
   *   loading: boolean,
   *   quests: any[],
   *   matchedQuests: any[],
   *   listedQuests: any[],
   *   byCategory: any[],
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
   * }} */
  let {
    loading,
    quests,
    matchedQuests,
    listedQuests,
    byCategory,
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
  } = $props()

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
  </div>
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
      {#snippet questRow(q)}
        {@const rowTimer = questTimer(q, nowMs)}
        <button
          type="button"
          class="quest-row"
          class:quest-row--active={q.id === selectedId}
          class:quest-row--pinned={q.pinned}
          class:quest-row--inactive={isQuestInactive(q)}
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
            <span class="quest-row__sig">
              <span class="sig-badge" data-sig={q.significance}>{significanceLabel(q)}</span>
            </span>
          {/if}
          <span class="quest-row__meta">
            <span class="quest-row__meta-left">
              <span class="status" style:color={statusColor(q.status)}>{q.status}</span>
              {#if periodBadge(q)}
                <span class="period-badge" title="Периодический инстанс">{periodBadge(q)}</span>
              {/if}
              {#if rowTimer}
                <span class="row-timer" data-tone={rowTimer.tone}>{rowTimer.label}</span>
              {/if}
            </span>
            <span class="progress">{q.progress_label}</span>
          </span>
        </button>
      {/snippet}

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
                  <Icon name={line.icon || 'document'} size={12} />
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
