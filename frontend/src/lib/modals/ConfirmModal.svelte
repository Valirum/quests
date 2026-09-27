<script>
  import Icon from '../ui/Icon.svelte'
  import ModalShell from './ModalShell.svelte'

  let {
    open = false,
    title = 'Подтверждение',
    message = '',
    confirmLabel = 'Удалить',
    cancelLabel = 'Отмена',
    busy = false,
    onConfirm = () => {},
    onCancel = () => {},
  } = $props()
</script>

<ModalShell {open} onClose={onCancel} labelledby="confirm-modal-title" zIndex={60} maxWidth="24rem" closeDisabled={busy}>
  <header class="modal__head">
    <h2 id="confirm-modal-title" class="modal__title">{title}</h2>
    <button
      type="button"
      class="btn btn--ghost btn--icon"
      onclick={onCancel}
      disabled={busy}
      aria-label="Закрыть"
    >
      <Icon name="close" size={14} />
    </button>
  </header>

  <p class="modal__body">{message}</p>

  <footer class="modal__foot">
    <button type="button" class="btn" onclick={onCancel} disabled={busy} aria-label={cancelLabel}>
      <Icon name="close" size={12} />
      <span class="btn__text">{cancelLabel}</span>
    </button>
    <button
      type="button"
      class="btn btn--danger"
      onclick={onConfirm}
      disabled={busy}
      aria-label={busy ? `${confirmLabel}…` : confirmLabel}
    >
      <Icon name="delete" size={14} />
      <span class="btn__text">{busy ? '…' : confirmLabel}</span>
    </button>
  </footer>
</ModalShell>

<style>
  .modal__head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3, 0.75rem);
    padding: var(--space-4, 1rem);
    border-bottom: 1px solid var(--color-border, #333);
  }

  .modal__title {
    margin: 0;
    font-family: var(--font-display, Georgia, serif);
    font-size: var(--text-lg, 1.25rem);
    color: var(--color-accent, #c9a227);
  }

  .modal__body {
    margin: 0;
    padding: var(--space-4, 1rem);
    font-family: var(--font-body, Georgia, serif);
    font-size: var(--text-sm, 0.875rem);
    line-height: 1.45;
    color: var(--color-fg, #e8e8e8);
  }

  .modal__foot {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2, 0.5rem);
    padding: var(--space-3, 0.75rem) var(--space-4, 1rem) var(--space-4, 1rem);
  }

  .btn {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2, 0.5rem);
    font: inherit;
    font-size: var(--text-sm, 0.875rem);
    padding: var(--space-2, 0.5rem) var(--space-3, 0.75rem);
    border: 1px solid var(--color-border-strong, #4a4a4a);
    border-radius: var(--radius-lg, 12px);
    background: var(--color-bg-muted, #242424);
    color: var(--color-fg, #e8e8e8);
    cursor: pointer;
  }

  .btn:hover {
    background: var(--color-bg-hover, #2a2a2a);
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: wait;
  }

  .btn--ghost {
    border-color: transparent;
    background: transparent;
    color: var(--color-fg-muted, #9a9a9a);
  }

  .btn--ghost:hover {
    color: var(--color-fg, #e8e8e8);
    background: var(--color-bg-hover, #2a2a2a);
  }

  .btn--icon {
    padding: var(--space-2, 0.5rem);
  }

  .btn--danger {
    border-color: transparent;
    background: transparent;
    color: color-mix(in srgb, var(--color-danger, #b54a3a) 78%, var(--color-fg, #e8e8e8));
  }

  .btn--danger:hover:not(:disabled) {
    color: var(--color-danger, #b54a3a);
    background: color-mix(in srgb, var(--color-danger, #b54a3a) 10%, transparent);
  }
</style>
