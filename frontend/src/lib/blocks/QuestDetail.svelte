<script>
  import { tick } from 'svelte'
  import Icon from '../ui/Icon.svelte'
  import QuestlineIcon from '../ui/QuestlineIcon.svelte'
  import ActivityCalendar from './ActivityCalendar.svelte'
  import { formatLocal, localTimeZone } from '../js/time.js'
  import {
    OPEN_STATUSES,
    periodBadge,
    questTimer,
    significanceLabel,
    statusColor,
  } from '../js/questFormat.js'

  /** @type {{
   *   selected: any | null,
   *   quests?: any[],
   *   showAllQuests?: boolean,
   *   nowMs: number,
   *   statusBusy: boolean,
   *   deleting: boolean,
   *   stepBusyId: number | null,
   *   stepEditId: number | null,
   *   stepEditValue: string,
   *   onToggleCompleted: (quest?: any) => void,
   *   onOpenEdit: (quest?: any) => void,
   *   onRequestDelete: (quest?: any) => void,
   *   onBumpStep: (step: any, delta: number, questId?: number | null) => void,
   *   onBeginEditStep: (step: any, questId?: number | null) => void,
   *   onStepEditKeydown: (event: KeyboardEvent, step: any) => void,
   *   onStepEditBlur: (step: any) => void,
   *   onStepEditInput: (value: string) => void,
   *   onSelectQuest?: (id: number) => void,
   *   onQuestTitleContextMenu?: (event: MouseEvent, quest: any) => void,
   *   onLineHeadContextMenu?: (event: MouseEvent) => void,
   *   onStepContextMenu?: (event: MouseEvent, step: any) => void,
   * }} */
  let {
    selected,
    quests = [],
    showAllQuests = false,
    nowMs,
    statusBusy,
    deleting,
    stepBusyId,
    stepEditId,
    stepEditValue,
    onToggleCompleted,
    onOpenEdit,
    onRequestDelete,
    onBumpStep,
    onBeginEditStep,
    onStepEditKeydown,
    onStepEditBlur,
    onStepEditInput,
    onSelectQuest,
    onQuestTitleContextMenu,
    onLineHeadContextMenu,
    onStepContextMenu,
  } = $props()

  const tzLabel = localTimeZone()

  let lineQuests = $derived.by(() => {
    if (!selected?.questline_id) return []
    const lid = Number(selected.questline_id)
    const selectedId = selected.id
    const pool = showAllQuests
      ? quests
      : quests.filter((q) => OPEN_STATUSES.has(q.status) || q.id === selectedId)
    return pool
      .filter((q) => q.questline_id != null && Number(q.questline_id) === lid)
      .sort((a, b) => {
        const ta = a.created_at || ''
        const tb = b.created_at || ''
        if (ta !== tb) return ta > tb ? -1 : 1
        return (b.id || 0) - (a.id || 0)
      })
  })

  let inQuestline = $derived(Boolean(selected?.questline_id))

  let lineMeta = $derived({
    title: selected?.questline_title || 'Квестлайн',
    color: selected?.questline_color || '#9a9a9a',
    icon: selected?.questline_icon || 'document',
    iconUrl: selected?.questline_icon_url || null,
  })

  $effect(() => {
    const id = selected?.id
    if (!id || !inQuestline) return
    tick().then(() => {
      const el = document.getElementById(`quest-${id}`)
      el?.scrollIntoView({ block: 'start', behavior: 'smooth' })
    })
  })
</script>

{#snippet questActions(q)}
  <div class="detail__actions">
    <button
      type="button"
      class="btn"
      onclick={() => onToggleCompleted(q)}
      disabled={statusBusy}
      aria-label={q.status === 'completed' ? 'Сделать активным' : 'Отметить выполненным'}
    >
      <Icon name={q.status === 'completed' ? 'renew' : 'checkmark'} />
      <span class="btn__text">
        {#if statusBusy}
          …
        {:else if q.status === 'completed'}
          Активно
        {:else}
          Выполнено
        {/if}
      </span>
    </button>
    <button type="button" class="btn" onclick={() => onOpenEdit(q)} aria-label="Править">
      <Icon name="edit" />
      <span class="btn__text">Править</span>
    </button>
    <button
      type="button"
      class="btn btn--danger"
      onclick={() => onRequestDelete(q)}
      disabled={deleting}
      aria-label={deleting ? 'Удаление…' : 'Удалить'}
    >
      <Icon name="delete" />
      <span class="btn__text">{deleting ? '…' : 'Удалить'}</span>
    </button>
  </div>
{/snippet}

{#snippet questEyebrow(q)}
  <p class="detail__eyebrow">
    <span class="status" style:color={statusColor(q.status)}>{q.status}</span>
    {#if q.pinned}
      <span class="pinned-label">PINNED</span>
    {/if}
    {#if q.significance}
      <span class="sig-badge" data-sig={q.significance}>{significanceLabel(q)}</span>
    {/if}
    {#if q.category_label}
      <span class="period-badge" title="Раздел">{q.category_label}</span>
    {/if}
    {#if periodBadge(q)}
      <span class="period-badge" title="Период">{periodBadge(q)}</span>
    {/if}
    <span class="progress">{q.progress_label}</span>
  </p>
{/snippet}

{#snippet stepList(q)}
  {#if q.steps?.length}
    <ol class="step-list">
      {#each q.steps as step (step.id)}
        <li
          class="step"
          class:step--done={step.done}
          oncontextmenu={(e) => onStepContextMenu?.(e, step)}
        >
          <span class="step__mark">{step.done ? '✓' : '○'}</span>
          <span class="step__main">
            <span class="step__title">{step.title}</span>
            {#if step.check_command}
              <span class="step__auto" title={step.check_command}
                >auto {step.check_interval_seconds || '?'}s</span
              >
            {/if}
          </span>
          <div class="step__controls">
            <button
              type="button"
              class="step__btn"
              aria-label="Уменьшить прогресс"
              disabled={stepBusyId != null || step.progress_current <= 0}
              onclick={() => onBumpStep(step, -1, q.id)}
            >
              <Icon name="subtract" size={14} />
            </button>
            {#if stepEditId === step.id}
              <input
                class="step__progress-input"
                type="number"
                min="0"
                max={step.progress_total}
                step="1"
                value={stepEditValue}
                disabled={stepBusyId != null}
                aria-label="Прогресс шага"
                autofocus
                oninput={(e) => onStepEditInput(e.currentTarget.value)}
                onkeydown={(e) => onStepEditKeydown(e, step)}
                onblur={() => onStepEditBlur(step)}
                onfocus={(e) => e.currentTarget.select()}
              />
              <span class="step__progress-total">/{step.progress_total}</span>
            {:else}
              <button
                type="button"
                class="step__progress"
                title="Двойной клик — задать значение"
                disabled={stepBusyId != null}
                ondblclick={() => onBeginEditStep(step, q.id)}
              >
                {step.progress_current}/{step.progress_total}
              </button>
            {/if}
            <button
              type="button"
              class="step__btn"
              aria-label="Увеличить прогресс"
              disabled={stepBusyId != null || step.progress_current >= step.progress_total}
              onclick={() => onBumpStep(step, 1, q.id)}
            >
              <Icon name="add" size={14} />
            </button>
          </div>
          {#if step.description}
            <p class="step__desc">{step.description}</p>
          {/if}
        </li>
      {/each}
    </ol>
  {:else}
    <p class="block__body block__body--muted">Шагов нет</p>
  {/if}
{/snippet}

{#snippet questBody(q)}
  {@const timer = questTimer(q, nowMs)}
  {#if q.description}
    <div class="block">
      <h3 class="block__label">Описание</h3>
      <p class="block__body">{q.description}</p>
    </div>
  {/if}

  <div class="block">
    <h3 class="block__label">Шаги</h3>
    {@render stepList(q)}
  </div>

  <dl class="dates">
    <div>
      <dt>Создан ({tzLabel})</dt>
      <dd>{formatLocal(q.created_at)}</dd>
    </div>
    <div>
      <dt>Обновлён ({tzLabel})</dt>
      <dd>{formatLocal(q.updated_at)}</dd>
    </div>
    {#if q.deadline_at}
      <div>
        <dt>Срок ({tzLabel})</dt>
        <dd>{formatLocal(q.deadline_at)}</dd>
      </div>
    {/if}
  </dl>

  {#if timer}
    <div class="deadline-timer" data-tone={timer.tone}>
      <span class="deadline-timer__label">До срока</span>
      <span class="deadline-timer__value">{timer.detailLabel}</span>
    </div>
  {/if}
{/snippet}

<section class="detail" aria-live="polite">
  {#if !selected}
    <div class="detail__empty detail__empty--cal">
      <ActivityCalendar {quests} {onSelectQuest} />
    </div>
  {:else if inQuestline}
    <header
      class="detail__line-head"
      class:detail__line-head--custom={Boolean(lineMeta.iconUrl)}
      style="--line-color: {lineMeta.color}"
      oncontextmenu={(e) => onLineHeadContextMenu?.(e)}
    >
      <span
        class="detail__line-icon"
        class:detail__line-icon--custom={Boolean(lineMeta.iconUrl)}
        aria-hidden="true"
      >
        <QuestlineIcon
          icon={lineMeta.icon}
          iconUrl={lineMeta.iconUrl}
          size="lg"
        />
      </span>
      <div class="detail__line-text">
        <p class="detail__line-eyebrow">Квестлайн</p>
        <h2 class="detail__line-title">{lineMeta.title}</h2>
      </div>
      <span class="detail__line-count">{lineQuests.length}</span>
    </header>

    <div class="detail__line-quests">
      {#each lineQuests as q (q.id)}
        <article id="quest-{q.id}" class="detail__quest">
          <header class="detail__head detail__head--nested">
            <div class="detail__head-row">
              {@render questEyebrow(q)}
              {@render questActions(q)}
            </div>
            <h3
              class="detail__subtitle"
              oncontextmenu={(e) => onQuestTitleContextMenu?.(e, q)}
            >{q.title}</h3>
          </header>
          {@render questBody(q)}
        </article>
      {/each}
    </div>
  {:else}
    <header class="detail__head">
      <div class="detail__head-row">
        {@render questEyebrow(selected)}
        {@render questActions(selected)}
      </div>
      <h2
        class="detail__title"
        oncontextmenu={(e) => onQuestTitleContextMenu?.(e, selected)}
      >{selected.title}</h2>
    </header>
    {@render questBody(selected)}
  {/if}
</section>
