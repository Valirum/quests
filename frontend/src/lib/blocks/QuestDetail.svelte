<script>
  import Icon from '../ui/Icon.svelte'
  import ActivityCalendar from './ActivityCalendar.svelte'
  import { formatLocal, localTimeZone } from '../js/time.js'
  import {
    periodBadge,
    questTimer,
    significanceLabel,
    statusColor,
  } from '../js/questFormat.js'

  /** @type {{
   *   selected: any | null,
   *   quests?: any[],
   *   nowMs: number,
   *   statusBusy: boolean,
   *   deleting: boolean,
   *   stepBusyId: number | null,
   *   stepEditId: number | null,
   *   stepEditValue: string,
   *   onToggleCompleted: () => void,
   *   onOpenEdit: () => void,
   *   onRequestDelete: () => void,
   *   onBumpStep: (step: any, delta: number) => void,
   *   onBeginEditStep: (step: any) => void,
   *   onStepEditKeydown: (event: KeyboardEvent, step: any) => void,
   *   onStepEditBlur: (step: any) => void,
   *   onStepEditInput: (value: string) => void,
   *   onSelectQuest?: (id: number) => void,
   * }} */
  let {
    selected,
    quests = [],
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
  } = $props()

  const tzLabel = localTimeZone()
  let selectedTimer = $derived(questTimer(selected, nowMs))
</script>

<section class="detail" aria-live="polite">
  {#if !selected}
    <div class="detail__empty detail__empty--cal">
      <ActivityCalendar {quests} {onSelectQuest} />
    </div>
  {:else}
    <header class="detail__head">
      <div class="detail__head-row">
        <p class="detail__eyebrow">
          <span class="status" style:color={statusColor(selected.status)}>{selected.status}</span>
          {#if selected.pinned}
            <span class="pinned-label">PINNED</span>
          {/if}
          {#if selected.significance}
            <span class="sig-badge" data-sig={selected.significance}
              >{significanceLabel(selected)}</span
            >
          {/if}
          {#if selected.category_label}
            <span class="period-badge" title="Раздел">{selected.category_label}</span>
          {/if}
          {#if periodBadge(selected)}
            <span class="period-badge" title="Период">{periodBadge(selected)}</span>
          {/if}
          <span class="progress">{selected.progress_label}</span>
        </p>
        <div class="detail__actions">
          <button
            type="button"
            class="btn"
            onclick={onToggleCompleted}
            disabled={statusBusy}
            aria-label={
              selected.status === 'completed' ? 'Сделать активным' : 'Отметить выполненным'
            }
          >
            <Icon name={selected.status === 'completed' ? 'renew' : 'checkmark'} />
            <span class="btn__text">
              {#if statusBusy}
                …
              {:else if selected.status === 'completed'}
                Активно
              {:else}
                Выполнено
              {/if}
            </span>
          </button>
          <button type="button" class="btn" onclick={onOpenEdit} aria-label="Править">
            <Icon name="edit" />
            <span class="btn__text">Править</span>
          </button>
          <button
            type="button"
            class="btn btn--danger"
            onclick={onRequestDelete}
            disabled={deleting}
            aria-label={deleting ? 'Удаление…' : 'Удалить'}
          >
            <Icon name="delete" />
            <span class="btn__text">{deleting ? '…' : 'Удалить'}</span>
          </button>
        </div>
      </div>
      <h2 class="detail__title">{selected.title}</h2>
    </header>

    {#if selected.description}
      <div class="block">
        <h3 class="block__label">Описание</h3>
        <p class="block__body">{selected.description}</p>
      </div>
    {:else}
      <div class="block">
        <h3 class="block__label">Описание</h3>
        <p class="block__body block__body--muted">Нет описания</p>
      </div>
    {/if}

    <div class="block">
      <h3 class="block__label">Шаги</h3>
      {#if selected.steps?.length}
        <ol class="step-list">
          {#each selected.steps as step (step.id)}
            <li class="step" class:step--done={step.done}>
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
                  onclick={() => onBumpStep(step, -1)}
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
                    ondblclick={() => onBeginEditStep(step)}
                  >
                    {step.progress_current}/{step.progress_total}
                  </button>
                {/if}
                <button
                  type="button"
                  class="step__btn"
                  aria-label="Увеличить прогресс"
                  disabled={stepBusyId != null || step.progress_current >= step.progress_total}
                  onclick={() => onBumpStep(step, 1)}
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
    </div>

    <dl class="dates">
      <div>
        <dt>Создан ({tzLabel})</dt>
        <dd>{formatLocal(selected.created_at)}</dd>
      </div>
      <div>
        <dt>Обновлён ({tzLabel})</dt>
        <dd>{formatLocal(selected.updated_at)}</dd>
      </div>
      {#if selected.deadline_at}
        <div>
          <dt>Срок ({tzLabel})</dt>
          <dd>{formatLocal(selected.deadline_at)}</dd>
        </div>
      {/if}
    </dl>

    {#if selectedTimer}
      <div class="deadline-timer" data-tone={selectedTimer.tone}>
        <span class="deadline-timer__label">До срока</span>
        <span class="deadline-timer__value">{selectedTimer.detailLabel}</span>
      </div>
    {/if}
  {/if}
</section>
