<script>
  import QuestlineIcon from '../ui/QuestlineIcon.svelte'
  import { questTimer, significanceLabel, statusColor } from '../js/questFormat.js'

  /** @type {{
   *   byCategory: any[],
   *   searchQuery: string,
   *   showAllQuests: boolean,
   *   nowMs: number,
   *   onSelectQuest: (id: number) => void,
   *   onLineContextMenu: (event: MouseEvent, line: any) => void,
   *   onQuestContextMenu: (event: MouseEvent, quest: any) => void,
   * }} */
  let {
    byCategory,
    searchQuery = $bindable(''),
    showAllQuests = $bindable(false),
    nowMs,
    onSelectQuest,
    onLineContextMenu,
    onQuestContextMenu,
  } = $props()

  function selectLine(line) {
    const first = line.quests?.[0]
    if (first) onSelectQuest(first.id)
  }
</script>

<div class="toc">
  <div class="toc__tools">
    <input
      class="toc__search"
      type="search"
      placeholder="Поиск…"
      bind:value={searchQuery}
      aria-label="Поиск по названию, разделу, квестлайну, описанию, шагам"
    />
    <label class="toc__filter">
      <input type="checkbox" bind:checked={showAllQuests} />
      <span>Показывать завершённые</span>
    </label>
  </div>

  <div class="toc__scroll">
    <div class="toc__content">
    {#if byCategory.length === 0}
      <p class="toc__empty">Ничего не найдено</p>
    {:else}
      {#each byCategory as g (g.key)}
        <section class="chapter">
          <h2 class="chapter__head" style={g.color ? `--cat-color: ${g.color}` : undefined}>
            <span class="chapter__mark" aria-hidden="true">◈</span>
            <span class="chapter__title">{g.label}</span>
            <span class="chapter__rule" aria-hidden="true"></span>
            <span class="chapter__count">{g.questCount}</span>
          </h2>

          {#snippet questRow(q)}
            {@const rowTimer = questTimer(q, nowMs)}
            <li>
              <button
                type="button"
                class="toc-quest"
                data-sig={q.significance || 'common'}
                data-timer-tone={rowTimer?.tone || undefined}
                onclick={() => onSelectQuest(q.id)}
                oncontextmenu={(e) => onQuestContextMenu?.(e, q)}
              >
                <span class="toc-quest__bullet" aria-hidden="true"></span>
                <span class="toc-quest__title">{q.title}</span>
                <span class="toc-quest__leader" aria-hidden="true"></span>
                {#if q.significance && q.significance !== 'common'}
                  <span class="toc-quest__sig">{significanceLabel(q)}</span>
                {/if}
                {#if rowTimer}
                  <span class="toc-quest__timer" data-tone={rowTimer.tone}>{rowTimer.label}</span>
                {/if}
                <span class="toc-quest__status" style:color={statusColor(q.status)}>{q.status}</span>
                <span class="toc-quest__progress">{q.progress_label}</span>
              </button>
            </li>
          {/snippet}

          <div class="chapter__body">
            {#each g.lines as line (line.key)}
              <div class="toc-line" style="--line-color: {line.color || '#9a9a9a'}">
                <button
                  type="button"
                  class="toc-line__head"
                  onclick={() => selectLine(line)}
                  oncontextmenu={(e) => onLineContextMenu?.(e, line)}
                >
                  <QuestlineIcon icon={line.icon} iconUrl={line.icon_url} size="sm" />
                  <span class="toc-line__title">{line.title}</span>
                  <span class="toc-line__leader" aria-hidden="true"></span>
                  <span class="toc-line__count">{line.quests.length}</span>
                </button>
                <ul class="toc-quests">
                  {#each line.quests as q (q.id)}
                    {@render questRow(q)}
                  {/each}
                </ul>
              </div>
            {/each}

            {#if g.alone.length > 0}
              <ul class="toc-quests toc-quests--alone">
                {#each g.alone as q (q.id)}
                  {@render questRow(q)}
                {/each}
              </ul>
            {/if}
          </div>
        </section>
      {/each}
    {/if}
    </div>
  </div>
</div>

<style>
  .toc {
    height: 100%;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  .toc__tools {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    gap: var(--space-4, 1rem);
    padding: var(--space-4, 1rem) var(--space-6, 2rem);
    border-bottom: 1px solid var(--color-border);
  }

  .toc__search {
    flex: 0 1 20rem;
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    background: var(--color-bg-muted);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-fg);
    font-family: var(--font-ui);
    font-size: var(--text-sm);
  }

  .toc__filter {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font-family: var(--font-ui);
    font-size: var(--text-sm);
    color: var(--color-fg-muted);
    white-space: nowrap;
  }

  .toc__scroll {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    background: var(--color-bg);
  }

  .toc__content {
    padding: var(--space-6, 2rem) max(var(--space-6, 2rem), calc(50% - 34rem));
  }

  .toc__empty {
    color: var(--color-fg-muted);
    font-family: var(--font-body);
    padding: var(--space-6, 2rem) 0;
  }

  .chapter + .chapter {
    margin-top: var(--space-6, 2rem);
  }

  .chapter__head {
    display: flex;
    align-items: baseline;
    gap: var(--space-3, 0.75rem);
    margin: 0 0 var(--space-4, 1rem);
  }

  .chapter__mark {
    color: var(--cat-color, var(--color-accent));
    font-size: var(--text-lg);
  }

  .chapter__title {
    font-family: var(--font-display);
    font-size: var(--text-xl);
    letter-spacing: 0.02em;
    color: var(--color-fg);
    text-transform: uppercase;
  }

  .chapter__rule {
    flex: 1 1 auto;
    border-bottom: 1px solid var(--color-border-strong);
    align-self: center;
    margin-top: 0.2em;
  }

  .chapter__count {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--color-fg-subtle);
  }

  .chapter__body {
    display: flex;
    flex-direction: column;
    gap: var(--space-4, 1rem);
  }

  .toc-line__head {
    display: flex;
    align-items: baseline;
    gap: var(--space-2, 0.5rem);
    width: 100%;
    background: none;
    border: 0;
    padding: 0;
    cursor: pointer;
    text-align: left;
  }

  .toc-line__head:hover .toc-line__title {
    color: var(--line-color, var(--color-accent));
  }

  .toc-line__title {
    font-family: var(--font-display);
    font-size: var(--text-lg);
    color: var(--color-fg);
  }

  .toc-line__leader {
    flex: 1 1 auto;
    border-bottom: 1px dotted var(--color-border-strong);
    align-self: center;
    margin-top: 0.5em;
  }

  .toc-line__count {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-fg-subtle);
  }

  .toc-quests {
    list-style: none;
    margin: var(--space-2, 0.5rem) 0 0;
    padding: 0 0 0 var(--space-6, 2rem);
    display: flex;
    flex-direction: column;
  }

  .toc-quests--alone {
    padding-left: 0;
  }

  .toc-quest {
    display: flex;
    align-items: baseline;
    gap: var(--space-2, 0.5rem);
    width: 100%;
    background: none;
    border: 0;
    padding: 0.3em 0;
    cursor: pointer;
    text-align: left;
  }

  .toc-quest__bullet {
    flex-shrink: 0;
    width: 0.4em;
    height: 0.4em;
    border-radius: 50%;
    background: var(--color-sig-common);
    align-self: center;
  }

  .toc-quest[data-sig="uncommon"] .toc-quest__bullet {
    background: var(--color-sig-uncommon);
  }
  .toc-quest[data-sig="epic"] .toc-quest__bullet {
    background: var(--color-sig-epic);
  }
  .toc-quest[data-sig="legendary"] .toc-quest__bullet {
    background: var(--color-sig-legendary);
  }

  .toc-quest__title {
    font-size: var(--text-md);
    color: var(--color-fg-muted);
  }

  .toc-quest[data-sig="uncommon"] .toc-quest__title {
    color: var(--color-sig-uncommon-on);
  }
  .toc-quest[data-sig="epic"] .toc-quest__title {
    color: var(--color-sig-epic-on);
  }
  .toc-quest[data-sig="legendary"] .toc-quest__title {
    color: var(--color-sig-legendary-on);
    font-weight: 600;
  }

  .toc-quest:hover .toc-quest__title {
    color: var(--color-fg);
  }

  .toc-quest__leader {
    flex: 1 1 auto;
    border-bottom: 1px dotted var(--color-border);
    align-self: center;
    margin-top: 0.3em;
  }

  .toc-quest__sig {
    font-family: var(--font-ui);
    font-size: var(--text-xs);
    color: var(--color-fg-subtle);
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .toc-quest__status {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    text-transform: uppercase;
  }

  .toc-quest__progress {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-fg-subtle);
    min-width: 2.5em;
    text-align: right;
  }

  /* Deadline timer — the one deliberate break from the page's otherwise
     static typography: a ticking quest needs to read as ticking. */
  .toc-quest__timer {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-variant-numeric: tabular-nums;
    padding: 0.05em 0.4em;
    border-radius: var(--radius-sm);
    border: 1px solid color-mix(in srgb, var(--tone, var(--color-fg-muted)) 55%, var(--color-border));
    background: color-mix(in srgb, var(--tone, var(--color-fg-muted)) 14%, transparent);
    color: var(--tone, var(--color-fg-muted));
  }

  .toc-quest__timer[data-tone="green"] {
    --tone: var(--color-timer-ok);
  }

  .toc-quest__timer[data-tone="orange"] {
    --tone: var(--color-timer-warn);
  }

  .toc-quest__timer[data-tone="red"] {
    --tone: var(--color-timer-urgent);
    animation: toc-timer-pulse 1.4s ease-in-out infinite;
  }

  .toc-quest[data-timer-tone="red"] .toc-quest__title {
    animation: toc-title-jitter 2.2s ease-in-out infinite;
  }

  @keyframes toc-timer-pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.45; }
  }

  @keyframes toc-title-jitter {
    0%, 92%, 100% { transform: translate(0, 0); }
    93% { transform: translate(-0.4px, 0.4px); }
    94% { transform: translate(0.4px, -0.3px); }
    95% { transform: translate(-0.3px, -0.4px); }
    96% { transform: translate(0.4px, 0.3px); }
    97% { transform: translate(0, 0); }
  }

  @media (prefers-reduced-motion: reduce) {
    .toc-quest__timer[data-tone="red"],
    .toc-quest[data-timer-tone="red"] .toc-quest__title {
      animation: none;
    }
  }
</style>
