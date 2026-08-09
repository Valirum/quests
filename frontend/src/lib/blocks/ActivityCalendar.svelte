<script>
  import { parseApiDate } from '../js/time.js'
  import { statusColor } from '../js/questFormat.js'

  /** @type {{ quests?: any[], onSelectQuest?: (id: number) => void }} */
  let { quests = [], onSelectQuest } = $props()

  const WEEKDAYS = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']

  function dayKey(d) {
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  }

  function formatTime(d) {
    return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  }

  function sigKey(q) {
    const s = String(q?.significance || 'common').toLowerCase()
    if (['common', 'uncommon', 'epic', 'legendary'].includes(s)) return s
    return 'common'
  }

  /** @type {Record<string, { id: number, title: string, status: string, significance: string, timeMs: number, timeLabel: string, done: boolean }[]>} */
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
    return { label, cells }
  }

  let months = $derived.by(() => {
    const now = new Date()
    const y = now.getFullYear()
    const m = now.getMonth()
    const next = m === 11 ? { y: y + 1, m: 0 } : { y, m: m + 1 }
    // touch questsByDay so months recompute
    void questsByDay
    return [buildMonth(y, m), buildMonth(next.y, next.m)]
  })

  let todayKey = $derived(dayKey(new Date()))
</script>

<div class="activity-cal" aria-label="Календарь задач">
  <header class="activity-cal__head">
    <h2 class="activity-cal__title">Календарь</h2>
  </header>

  <div class="activity-cal__months">
    {#each months as month}
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
                role="gridcell"
                aria-label="{cell.key}: {cell.items.length} задач"
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
</div>
