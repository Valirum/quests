<script>
  // Sign-in gate. Rendered instead of the journal whenever the instance
  // requires accounts and no valid session cookie is present.
  import { login } from '../js/api.js'

  /** @type {{ onAuthenticated: (username: string) => void }} */
  let { onAuthenticated } = $props()

  let username = $state('')
  let password = $state('')
  let busy = $state(false)
  let error = $state('')

  async function submit(event) {
    event.preventDefault()
    if (busy) return
    error = ''
    busy = true
    try {
      const res = await login(username.trim(), password)
      password = ''
      onAuthenticated(res?.username ?? username.trim())
    } catch (err) {
      error = err instanceof Error ? err.message : String(err)
      password = ''
    } finally {
      busy = false
    }
  }
</script>

<div class="login-shell">
  <form class="login-card" onsubmit={submit}>
    <h1>Quests</h1>
    <p class="hint">Журнал закрыт — войдите в аккаунт.</p>

    <label>
      <span>Логин</span>
      <!-- svelte-ignore a11y_autofocus -->
      <input
        type="text"
        autocomplete="username"
        autocapitalize="none"
        autocorrect="off"
        spellcheck="false"
        autofocus
        bind:value={username}
        disabled={busy}
      />
    </label>

    <label>
      <span>Пароль</span>
      <input
        type="password"
        autocomplete="current-password"
        bind:value={password}
        disabled={busy}
      />
    </label>

    {#if error}
      <p class="error" role="alert">{error}</p>
    {/if}

    <button type="submit" disabled={busy || !username.trim() || !password}>
      {busy ? 'Проверяем…' : 'Войти'}
    </button>
  </form>
</div>

<style>
  .login-shell {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: 24px;
    background: var(--color-bg);
  }

  .login-card {
    width: min(360px, 100%);
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding: 28px;
    background: var(--color-bg-raised);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
  }

  h1 {
    margin: 0;
    font-family: var(--font-display);
    font-size: 1.6rem;
    color: var(--color-fg);
  }

  .hint {
    margin: -6px 0 4px;
    font-family: var(--font-ui);
    font-size: 0.85rem;
    color: var(--color-fg-muted);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: 6px;
    font-family: var(--font-ui);
    font-size: 0.82rem;
    color: var(--color-fg-muted);
  }

  input {
    padding: 9px 11px;
    font-family: var(--font-body);
    font-size: 0.95rem;
    color: var(--color-fg);
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  button {
    margin-top: 4px;
    padding: 10px;
    font-family: var(--font-ui);
    font-size: 0.9rem;
    color: var(--color-accent-fg);
    background: var(--color-accent);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.55;
    cursor: default;
  }

  .error {
    margin: 0;
    font-family: var(--font-ui);
    font-size: 0.82rem;
    color: var(--color-danger);
  }
</style>
