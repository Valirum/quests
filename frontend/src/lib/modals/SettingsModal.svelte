<script>
  import { THEMES, applyTheme, currentThemeId } from '../js/theme.js'
  import Icon from '../ui/Icon.svelte'

  /** @type {{ open?: boolean, onClose: () => void, health?: { api: string, overlay: string, telegram: string, detail?: any }, liveStatus?: string }} */
  let {
    open = false,
    onClose,
    health = { api: 'unknown', overlay: 'unknown', telegram: 'unknown' },
    liveStatus = 'off',
  } = $props()

  let themeId = $state(currentThemeId())

  $effect(() => {
    if (open) themeId = currentThemeId()
  })

  $effect(() => {
    if (!open) return
    const onKey = (event) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        event.stopPropagation()
        onClose()
      }
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  })

  function onBackdrop(event) {
    if (event.target === event.currentTarget) onClose()
  }

  function selectTheme(id) {
    themeId = applyTheme(id)
  }

  function statusLabel(s) {
    if (s === 'ok' || s === 'live') return 'онлайн'
    if (s === 'offline' || s === 'off') return 'офлайн'
    if (s === 'connecting' || s === 'reconnect') return 'переподключение'
    return 'неизвестно'
  }

  function ageLabel(comp) {
    const age = health?.detail?.components?.[comp]?.age_seconds
    if (age == null) return 'нет heartbeat'
    if (age < 2) return 'только что'
    return `${age} с назад`
  }
</script>

{#if open}
  <div class="backdrop" role="presentation" onclick={onBackdrop}>
    <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
    <div
      class="modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-modal-title"
      tabindex="-1"
      onclick={(e) => e.stopPropagation()}
    >
      <header class="modal__head">
        <h2 id="settings-modal-title" class="modal__title">
          <Icon name="settings" size={18} />
          <span>Настройки</span>
        </h2>
        <button type="button" class="btn btn--ghost btn--icon btn--close" onclick={onClose} aria-label="Закрыть">
          <Icon name="close" size={14} />
        </button>
      </header>

      <div class="modal__body">
        <section class="block">
          <h3 class="block__title">Сервисы</h3>
          <p class="block__hint">API отвечает сам; HUD и бот шлют heartbeat раз в несколько секунд.</p>
          <ul class="svc-list">
            <li class="svc" data-status={health.api}>
              <span class="svc__dot" aria-hidden="true"></span>
              <span class="svc__name">API</span>
              <span class="svc__status">{statusLabel(health.api)}</span>
              <span class="svc__meta">HTTP · WS {statusLabel(liveStatus)}</span>
            </li>
            <li class="svc" data-status={health.overlay}>
              <span class="svc__dot" aria-hidden="true"></span>
              <span class="svc__name">HUD</span>
              <span class="svc__status">{statusLabel(health.overlay)}</span>
              <span class="svc__meta">{ageLabel('overlay')}</span>
            </li>
            <li class="svc" data-status={health.telegram}>
              <span class="svc__dot" aria-hidden="true"></span>
              <span class="svc__name">Telegram</span>
              <span class="svc__status">{statusLabel(health.telegram)}</span>
              <span class="svc__meta">{ageLabel('telegram')}</span>
            </li>
          </ul>
        </section>

        <section class="block">
          <h3 class="block__title">Тема приложения</h3>
          <p class="block__hint">Выбор палитры интерфейса. Сохраняется в этом браузере.</p>
          <ul class="theme-list" role="listbox" aria-label="Тема приложения">
            {#each THEMES as t (t.id)}
              <li>
                <button
                  type="button"
                  class="theme-row"
                  class:theme-row--on={themeId === t.id}
                  role="option"
                  aria-selected={themeId === t.id}
                  onclick={() => selectTheme(t.id)}
                >
                  <span class="theme-row__swatches" aria-hidden="true">
                    {#each t.swatches as hex}
                      <span class="theme-row__swatch" style="background: {hex}"></span>
                    {/each}
                  </span>
                  <span class="theme-row__meta">
                    <span class="theme-row__label">{t.label}</span>
                    <span class="theme-row__scheme">{t.scheme === 'dark' ? 'тёмная' : 'светлая'}</span>
                  </span>
                  {#if themeId === t.id}
                    <Icon name="checkmark" size={14} />
                  {/if}
                </button>
              </li>
            {/each}
          </ul>
        </section>
      </div>
    </div>
  </div>
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 55;
    display: grid;
    place-items: center;
    padding: var(--space-4, 1rem);
    background: color-mix(in srgb, var(--color-bg, #121212) 55%, transparent);
    backdrop-filter: blur(2px);
  }

  .modal {
    width: min(26rem, 100%);
    max-height: min(90vh, 40rem);
    overflow: auto;
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: color-mix(in srgb, var(--color-bg, #121212) 88%, var(--color-bg-raised, #1a1a1a));
    box-shadow: 0 16px 48px color-mix(in srgb, #000 45%, transparent);
    font-family: var(--font-ui, sans-serif);
  }

  .modal__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
  }

  .modal__title {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-lg, 1.25rem);
    color: var(--color-accent, #c9a227);
  }

  .modal__body {
    padding: var(--space-4, 1rem);
    display: grid;
    gap: var(--space-5, 1.5rem);
  }

  .block__title {
    margin: 0 0 var(--space-1, 0.25rem);
    font-size: var(--text-sm, 0.875rem);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .block__hint {
    margin: 0 0 var(--space-3, 0.75rem);
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .svc-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
  }

  .svc {
    display: grid;
    grid-template-columns: auto 1fr auto;
    grid-template-areas:
      "dot name status"
      "dot meta meta";
    column-gap: 0.55rem;
    row-gap: 0.1rem;
    align-items: center;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    background: color-mix(in srgb, var(--color-bg, #121212) 70%, transparent);
  }

  .svc__dot {
    grid-area: dot;
    width: 0.5rem;
    height: 0.5rem;
    border-radius: 50%;
    background: currentColor;
  }

  .svc__name {
    grid-area: name;
    font-weight: 600;
    font-size: var(--text-sm, 0.875rem);
  }

  .svc__status {
    grid-area: status;
    font-family: var(--font-mono, monospace);
    font-size: var(--text-xs, 0.75rem);
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .svc__meta {
    grid-area: meta;
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .svc[data-status='ok'] {
    color: var(--color-success, #7a9e3a);
  }

  .svc[data-status='offline'] {
    color: var(--color-danger, #b54a3a);
  }

  .svc[data-status='unknown'] {
    color: var(--color-fg-subtle, #6e6e6e);
  }

  .svc[data-status='ok'] .svc__name,
  .svc[data-status='offline'] .svc__name,
  .svc[data-status='unknown'] .svc__name {
    color: var(--color-fg, #e8e8e8);
  }

  .theme-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 0.35rem;
  }

  .theme-row {
    width: 100%;
    display: grid;
    grid-template-columns: auto 1fr auto;
    align-items: center;
    gap: 0.75rem;
    padding: 0.55rem 0.7rem;
    border: 1px solid var(--color-border, #333);
    border-radius: var(--radius-lg, 12px);
    background: color-mix(in srgb, var(--color-bg, #121212) 70%, transparent);
    color: var(--color-fg, #e8e8e8);
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .theme-row:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .theme-row--on {
    border-color: color-mix(in srgb, var(--color-accent, #c9a227) 55%, var(--color-border, #333));
    background: color-mix(in srgb, var(--color-accent, #c9a227) 14%, var(--color-bg, #121212));
  }

  .theme-row__swatches {
    display: inline-flex;
    gap: 0;
    border-radius: 999px;
    overflow: hidden;
    border: 1px solid var(--color-border, #333);
  }

  .theme-row__swatch {
    width: 0.7rem;
    height: 1.15rem;
  }

  .theme-row__meta {
    display: grid;
    gap: 0.1rem;
    min-width: 0;
  }

  .theme-row__label {
    font-weight: 600;
    font-size: var(--text-sm, 0.875rem);
  }

  .theme-row__scheme {
    font-size: var(--text-xs, 0.75rem);
    color: var(--color-fg-muted, #9a9a9a);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font: inherit;
    padding: var(--space-2, 0.5rem);
    border: 1px solid transparent;
    border-radius: var(--radius-lg, 12px);
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
    cursor: pointer;
  }

  .btn--close {
    border: 0;
  }

  .btn--ghost:hover {
    color: var(--color-fg, #e8e8e8);
    background: var(--color-bg-hover, #2a2a2a);
  }
</style>
