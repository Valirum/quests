<script>
  import { tick } from 'svelte'
  import { parseApiDate } from '../js/time.js'
  import { QUEST_STATUS_LABELS } from '../js/api.js'
  import { statusColor } from '../js/questFormat.js'
  import Icon from '../ui/Icon.svelte'

  /** @type {{ quests?: any[], onSelectQuest?: (id: number) => void }} */
  let { quests = [], onSelectQuest } = $props()

  const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
  const HOUR_TICKS = [0, 6, 12, 18, 24]

  /** @type {string} YYYY-MM-DD — same picker as quest modal (`type=date`) */
  let rangeFrom = $state(monthStartKey(new Date()))
  /** @type {string} YYYY-MM-DD */
  let rangeTo = $state(monthEndKey(new Date()))
  /** @type {string | null} YYYY-MM-DD */
  let selectedKey = $state(null)
  /** @type {number | null} hovered quest id (timeline ↔ event list) */
  let hoveredId = $state(null)

  /** @type {HTMLElement | null} */
  let rootEl = $state(null)

  function monthKey(d) {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  }

  function dayKey(d) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  function monthStartKey(d = new Date()) {
    return dayKey(new Date(d.getFullYear(), d.getMonth(), 1))
  }

  function monthEndKey(d = new Date()) {
    return dayKey(new Date(d.getFullYear(), d.getMonth() + 1, 0))
  }

  /** @param {string} key */
  function parseDayKey(key) {
    const [y, m, d] = key.split('-').map(Number)
    return new Date(y, m - 1, d)
  }

  /** @param {string} key */
  function dayBounds(key) {
    const start = parseDayKey(key)
    start.setHours(0, 0, 0, 0)
    const end = new Date(start)
    end.setDate(end.getDate() + 1)
    return { start, end }
  }

  function formatTime(d) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  function formatDayTitle(key) {
    return parseDayKey(key).toLocaleDateString('ru-RU', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      year: 'numeric',
    })
  }

  function sigKey(q) {
    const s = String(q?.significance || 'common').toLowerCase()
    if (['common', 'uncommon', 'epic', 'legendary'].includes(s)) return s
    return 'common'
  }

  /**
   * Urgent window [deadline − duration, deadline]. Point if no duration.
   * @param {any} q
   * @returns {{ start: Date, end: Date } | null}
   */
  function questWindow(q) {
    const deadline = parseApiDate(q?.deadline_at)
    if (!deadline) return null
    const dur = Number(q.duration_seconds) || 0
    if (dur > 0) {
      return { start: new Date(deadline.getTime() - dur * 1000), end: deadline }
    }
    return { start: deadline, end: deadline }
  }

  /**
   * Planned urgent window, clipped to actual finish when completed/failed.
   * @param {any} q
   * @returns {{ start: Date, end: Date, finish: Date | null, markKind: 'completed' | 'failed' | null } | null}
   */
  function actualWindow(q) {
    const planned = questWindow(q)
    if (!planned) return null
    const status = String(q.status || '')
    /** @type {Date | null} */
    let finish = null
    /** @type {'completed' | 'failed' | null} */
    let markKind = null
    if (status === 'completed') {
      finish = parseApiDate(q.completed_at)
      if (finish) markKind = 'completed'
    } else if (status === 'failed') {
      finish = parseApiDate(q.updated_at)
      if (finish) markKind = 'failed'
    }
    if (!finish) {
      return { start: planned.start, end: planned.end, finish: null, markKind: null }
    }
    // Fact load: from window open to finish (shorten or extend past deadline).
    let start = planned.start
    let end = finish
    if (end.getTime() < start.getTime()) {
      start = finish
      end = finish
    }
    return { start, end, finish, markKind }
  }

  /**
   * @param {{ start: Date, end: Date }} win
   * @param {Date} dayStart
   * @param {Date} dayEnd
   */
  function clipToDay(win, dayStart, dayEnd) {
    const s = Math.max(win.start.getTime(), dayStart.getTime())
    const e = Math.min(win.end.getTime(), dayEnd.getTime())
    if (e < s) return null
    if (e === s) return { startMs: s, endMs: s, point: true }
    return { startMs: s, endMs: e, point: false }
  }

  /** Normalize from ≤ to. */
  let period = $derived.by(() => {
    let from = rangeFrom
    let to = rangeTo
    if (from > to) {
      const t = from
      from = to
      to = t
    }
    return { from, to }
  })

  /**
   * Cards on the month grid: deadline day, else created day.
   * @type {Record<string, { id: number, title: string, status: string, significance: string, timeMs: number, timeLabel: string, done: boolean }[]>}
   */
  let questsByDay = $derived.by(() => {
    /** @type {Record<string, any[]>} */
    const map = {}
    for (const q of quests) {
      const raw = q?.deadline_at || q?.created_at
      const d = parseApiDate(raw)
      if (!d || q?.id == null) continue
      const key = dayKey(d)
      const status = String(q.status || 'active')
      const entry = {
        id: Number(q.id),
        title: String(q.title || '?'),
        status,
        significance: sigKey(q),
        timeMs: d.getTime(),
        timeLabel: formatTime(d),
        done: status === 'completed',
      }
      if (!map[key]) map[key] = []
      map[key].push(entry)
    }
    for (const key of Object.keys(map)) {
      map[key].sort((a, b) => a.timeMs - b.timeMs || a.id - b.id)
    }
    return map
  })

  /**
   * @param {number} year
   * @param {number} month 0-based
   */
  function buildMonth(year, month) {
    const first = new Date(year, month, 1)
    const daysInMonth = new Date(year, month + 1, 0).getDate()
    const startPad = (first.getDay() + 6) % 7
    /** @type {({ key: string, day: number, items: typeof questsByDay[string] } | null)[]} */
    const cells = []
    for (let i = 0; i < startPad; i++) cells.push(null)
    for (let day = 1; day <= daysInMonth; day++) {
      const d = new Date(year, month, day)
      const key = dayKey(d)
      cells.push({ key, day, items: questsByDay[key] || [] })
    }
    while (cells.length % 7 !== 0) cells.push(null)
    const label = first.toLocaleDateString('ru-RU', {
      month: 'long',
      year: 'numeric',
    })
    return { key: monthKey(first), label, cells }
  }

  let months = $derived.by(() => {
    void questsByDay
    const fromD = parseDayKey(period.from)
    const toD = parseDayKey(period.to)
    const [fy, fm] = [fromD.getFullYear(), fromD.getMonth()]
    const [ty, tm] = [toD.getFullYear(), toD.getMonth()]
    /** @type {ReturnType<typeof buildMonth>[]} */
    const out = []
    let y = fy
    let m = fm
    while (y < ty || (y === ty && m <= tm)) {
      out.push(buildMonth(y, m))
      m += 1
      if (m > 11) {
        m = 0
        y += 1
      }
    }
    return out
  })

  let todayKey = $derived(dayKey(new Date()))

  /**
   * Timeline bars for selected day (full-height, overlapping).
   * Completed/failed: bar ends at finish moment (actual load).
   * Mark only at deadline (open) or finish (done/fail) when that falls on this day.
   */
  let dayLoad = $derived.by(() => {
    if (!selectedKey) return null
    const { start: dayStart, end: dayEnd } = dayBounds(selectedKey)
    const dayMs = dayEnd.getTime() - dayStart.getTime()

    /** @type {any[]} */
    const bars = []
    for (const q of quests) {
      const win = actualWindow(q)
      if (!win || q?.id == null) continue
      const clipped = clipToDay(win, dayStart, dayEnd)
      if (!clipped) continue

      const status = String(q.status || 'active')
      const fromPrev = win.start < dayStart
      const toNext = win.end >= dayEnd
      const endToday = win.end >= dayStart && win.end < dayEnd

      /** @type {number | null} */
      let markMs = null
      /** @type {'deadline' | 'completed' | 'failed' | null} */
      let markKind = null
      if (win.finish && win.finish >= dayStart && win.finish < dayEnd) {
        markMs = win.finish.getTime()
        markKind = win.markKind
      } else if (!win.finish && endToday) {
        markMs = win.end.getTime()
        markKind = 'deadline'
      }

      const left = (clipped.startMs - dayStart.getTime()) / dayMs
      const rawW = (clipped.endMs - clipped.startMs) / dayMs
      const width = clipped.point ? 0 : Math.max(rawW, 0.004)

      bars.push({
        id: Number(q.id),
        title: String(q.title || '?'),
        status,
        significance: sigKey(q),
        left,
        width,
        marker: markMs != null ? (markMs - dayStart.getTime()) / dayMs : null,
        markKind,
        point: clipped.point,
        fromPrev,
        toNext,
        caption: buildBarCaption(q, win, fromPrev, endToday, markKind),
        tip: buildBarTip(q, win, fromPrev, endToday),
      })
    }

    bars.sort((a, b) => a.left - b.left || b.width - a.width || a.id - b.id)

    /** @type {any[]} */
    const events = []
    for (const q of quests) {
      if (q?.id == null) continue
      const created = parseApiDate(q.created_at)
      if (created && created >= dayStart && created < dayEnd) {
        events.push({
          kind: 'issued',
          label: 'выдан',
          at: created,
          timeLabel: formatTime(created),
          quest: q,
        })
      }
      const completed = parseApiDate(q.completed_at)
      if (completed && completed >= dayStart && completed < dayEnd) {
        events.push({
          kind: 'completed',
          label: QUEST_STATUS_LABELS.completed ?? 'выполнен',
          at: completed,
          timeLabel: formatTime(completed),
          quest: q,
        })
      }
      const updated = parseApiDate(q.updated_at)
      const st = String(q.status || '')
      if (
        updated &&
        updated >= dayStart &&
        updated < dayEnd &&
        (st === 'failed' || st === 'delayed' || st === 'archived')
      ) {
        const sameCreate =
          created && Math.abs(created.getTime() - updated.getTime()) < 2000
        if (!sameCreate) {
          events.push({
            kind: st,
            label: QUEST_STATUS_LABELS[st] ?? st,
            at: updated,
            timeLabel: formatTime(updated),
            quest: q,
          })
        }
      }
    }
    events.sort(
      (a, b) => a.at.getTime() - b.at.getTime() || Number(a.quest.id) - Number(b.quest.id),
    )

    return {
      key: selectedKey,
      title: formatDayTitle(selectedKey),
      bars,
      events,
    }
  })

  let hoveredBar = $derived(
    dayLoad?.bars.find((b) => b.id === hoveredId) ?? null,
  )

  /**
   * @param {any} q
   * @param {{ start: Date, end: Date, finish: Date | null }} win
   * @param {boolean} fromPrev
   * @param {boolean} endToday
   * @param {string | null} markKind
   */
  function buildBarCaption(q, win, fromPrev, endToday, markKind) {
    const title = String(q.title || '?')
    const endLabel = formatTime(win.end)
    const span = fromPrev
      ? `${formatTime(win.start)} (${dayKey(win.start)}) → ${endLabel}${endToday ? '' : ` (${dayKey(win.end)})`}`
      : `${formatTime(win.start)} → ${endLabel}${endToday ? '' : ` (${dayKey(win.end)})`}`
    if (markKind === 'completed') return `${title} · выполнен · ${span}`
    if (markKind === 'failed') return `${title} · провален · ${span}`
    return `${title} · ${span}`
  }

  /**
   * @param {any} q
   * @param {{ start: Date, end: Date }} win
   * @param {boolean} fromPrev
   * @param {boolean} endToday
   */
  function buildBarTip(q, win, fromPrev, endToday) {
    const parts = [String(q.title || '?')]
    if (fromPrev) parts.push(`с ${formatTime(win.start)} (${dayKey(win.start)})`)
    else parts.push(`с ${formatTime(win.start)}`)
    parts.push(`до ${formatTime(win.end)}${endToday ? '' : ` (${dayKey(win.end)})`}`)
    return parts.join(' · ')
  }

  /** @param {string} key @returns {boolean} whether day is now selected */
  function selectDay(key) {
    const next = selectedKey === key ? null : key
    selectedKey = next
    hoveredId = null
    return next != null
  }

  /** @param {number} delta */
  async function shiftSelectedDay(delta) {
    if (!selectedKey) return
    const d = parseDayKey(selectedKey)
    d.setDate(d.getDate() + delta)
    const key = dayKey(d)
    selectedKey = key
    hoveredId = null
    if (key < rangeFrom) rangeFrom = key
    if (key > rangeTo) rangeTo = key
    await tick()
    scrollToSelectedDay()
  }

  function scrollToSelectedDay() {
    if (!selectedKey || !rootEl) return
    const cell = rootEl.querySelector(`[data-day-key="${selectedKey}"]`)
    cell?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  function scrollToDayPanel() {
    if (!rootEl) return
    const panel = rootEl.querySelector('.day-load')
    panel?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  /** @param {string} key @param {MouseEvent} e */
  async function onCellClick(key, e) {
    const t = /** @type {HTMLElement} */ (e.target)
    if (t.closest?.('.cal-card')) return
    const open = selectDay(key)
    if (open) {
      await tick()
      scrollToDayPanel()
    }
  }
</script>

<div class="activity-cal" aria-label="Календарь задач" bind:this={rootEl}>
  <header class="activity-cal__head">
    <div class="activity-cal__head-row">
      <h2 class="activity-cal__title">Календарь</h2>
      {#if selectedKey}
        <button
          type="button"
          class="btn activity-cal__jump"
          onclick={scrollToSelectedDay}
          title="Прокрутить к выбранному дню"
        >
          К выбранному дню
        </button>
      {/if}
    </div>
    <div class="activity-cal__period" role="group" aria-label="Период просмотра">
      <label class="activity-cal__period-field">
        <span>с</span>
        <input type="date" lang="ru-RU" bind:value={rangeFrom} />
      </label>
      <label class="activity-cal__period-field">
        <span>по</span>
        <input type="date" lang="ru-RU" bind:value={rangeTo} />
      </label>
    </div>
  </header>

  <div class="activity-cal__months">
    {#each months as month (month.key)}
      <section class="activity-cal__month">
        <h3 class="activity-cal__month-label">{month.label}</h3>
        <div class="activity-cal__weekdays" aria-hidden="true">
          {#each WEEKDAYS as w}
            <span>{w}</span>
          {/each}
        </div>
        <div class="activity-cal__grid" role="grid" aria-label={month.label}>
          {#each month.cells as cell}
            {#if cell}
              <div
                class="activity-cal__cell"
                class:activity-cal__cell--today={cell.key === todayKey}
                class:activity-cal__cell--selected={cell.key === selectedKey}
                role="gridcell"
                tabindex="0"
                data-day-key={cell.key}
                aria-label="{cell.key}: {cell.items.length} задач"
                aria-selected={cell.key === selectedKey}
                onclick={(e) => onCellClick(cell.key, e)}
                onkeydown={async (e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    const open = selectDay(cell.key)
                    if (open) {
                      await tick()
                      scrollToDayPanel()
                    }
                  }
                }}
              >
                <div class="activity-cal__cell-head">
                  <span class="activity-cal__daynum">{cell.day}</span>
                  {#if cell.items.length > 0}
                    <span class="activity-cal__count">{cell.items.length}</span>
                  {/if}
                </div>
                <div class="activity-cal__cards">
                  {#each cell.items as item (item.id)}
                    <button
                      type="button"
                      class="cal-card"
                      class:cal-card--done={item.done}
                      data-sig={item.significance}
                      data-status={item.status}
                      title={item.title}
                      onclick={() => onSelectQuest?.(item.id)}
                    >
                      <span
                        class="cal-card__status"
                        style:background={statusColor(item.status)}
                        aria-hidden="true"
                      ></span>
                      <span class="cal-card__title">{item.title}</span>
                      <span class="cal-card__time">{item.timeLabel}</span>
                    </button>
                  {/each}
                </div>
              </div>
            {:else}
              <div class="activity-cal__cell activity-cal__cell--empty" aria-hidden="true"></div>
            {/if}
          {/each}
        </div>
      </section>
    {/each}
  </div>

  {#if dayLoad}
    <section class="day-load" aria-label="Загрузка дня">
      <header class="day-load__head">
        <div class="day-load__nav">
          <button
            type="button"
            class="btn day-load__icon-btn"
            aria-label="Предыдущий день"
            onclick={() => shiftSelectedDay(-1)}
          >
            ‹
          </button>
          <h3 class="day-load__title">{dayLoad.title}</h3>
          <button
            type="button"
            class="btn day-load__icon-btn"
            aria-label="Следующий день"
            onclick={() => shiftSelectedDay(1)}
          >
            ›
          </button>
        </div>
        <div class="day-load__actions">
          <button
            type="button"
            class="btn day-load__icon-btn"
            onclick={scrollToSelectedDay}
            title="К дню в сетке"
            aria-label="К дню в сетке"
          >
            <Icon name="arrow-up" size={16} />
          </button>
          <button
            type="button"
            class="btn day-load__icon-btn"
            aria-label="Закрыть"
            onclick={() => {
              selectedKey = null
              hoveredId = null
            }}
          >
            <Icon name="close" size={14} />
          </button>
        </div>
      </header>

      <div class="day-load__body">
        <div class="day-tl" aria-label="Полоска времени">
          <div class="day-tl__hours" aria-hidden="true">
            {#each HOUR_TICKS as h}
              <span style:left="{(h / 24) * 100}%">{String(h).padStart(2, '0')}</span>
            {/each}
          </div>
          <div
            class="day-tl__track"
            role="group"
            aria-label={dayLoad.bars.length
              ? `${dayLoad.bars.length} интервалов`
              : 'Нет окон с дедлайном'}
            onmouseleave={() => (hoveredId = null)}
          >
            {#each HOUR_TICKS as h}
              <div class="day-tl__gridline" style:left="{(h / 24) * 100}%"></div>
            {/each}
            {#each dayLoad.bars as bar (bar.id)}
              <button
                type="button"
                class="day-tl__bar"
                class:day-tl__bar--point={bar.point}
                class:day-tl__bar--from-prev={bar.fromPrev}
                class:day-tl__bar--to-next={bar.toNext}
                class:day-tl__bar--hover={hoveredId === bar.id}
                data-sig={bar.significance}
                data-status={bar.status}
                style:left="{bar.left * 100}%"
                style:width="{Math.max(bar.width * 100, bar.point ? 0.15 : 0.4)}%"
                title={bar.tip}
                onmouseenter={() => (hoveredId = bar.id)}
                onclick={() => onSelectQuest?.(bar.id)}
              ></button>
              {#if bar.marker != null}
                <span
                  class="day-tl__mark"
                  class:day-tl__mark--hover={hoveredId === bar.id}
                  data-sig={bar.significance}
                  data-kind={bar.markKind}
                  style:left="{bar.marker * 100}%"
                  title={bar.tip}
                  aria-hidden="true"
                ></span>
              {/if}
            {/each}
            {#if dayLoad.bars.length === 0}
              <p class="day-tl__empty">Нет задач с окном/дедлайном в этот день</p>
            {/if}
          </div>
          <div class="day-tl__caption" aria-live="polite">
            {#if hoveredBar}
              {hoveredBar.caption}
            {:else}
              <span class="day-tl__caption-hint">наведите на область или событие</span>
            {/if}
          </div>
        </div>

        <div class="day-events">
          <h4 class="day-events__title">События дня</h4>
          {#if dayLoad.events.length === 0}
            <p class="day-events__empty">Нет выдач и смен статуса</p>
          {:else}
            <ul class="day-events__list">
              {#each dayLoad.events as ev (ev.kind + '-' + ev.quest.id + '-' + ev.at.getTime())}
                <li
                  class="day-events__item"
                  class:day-events__item--hover={hoveredId === Number(ev.quest.id)}
                  onmouseenter={() => (hoveredId = Number(ev.quest.id))}
                  onmouseleave={() => (hoveredId = null)}
                >
                  <time class="day-events__time">{ev.timeLabel}</time>
                  <span
                    class="day-events__kind"
                    data-kind={ev.kind}
                    style:--kind-color={statusColor(
                      ev.kind === 'issued' ? 'active' : ev.kind,
                    )}
                  >
                    {ev.label}
                  </span>
                  <button
                    type="button"
                    class="day-events__quest"
                    onclick={() => onSelectQuest?.(Number(ev.quest.id))}
                  >
                    {ev.quest.title || '?'}
                  </button>
                </li>
              {/each}
            </ul>
          {/if}
        </div>
      </div>
    </section>
  {/if}
</div>
