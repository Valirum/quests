/**
 * Theme switcher. Themes live in styles/themes/<name>.css as [data-theme="…"].
 * Import extra theme CSS from main.js / app.css when you add one.
 */
export const DEFAULT_THEME = 'gruvbox-yellow'

export function applyTheme(name = DEFAULT_THEME) {
  document.documentElement.dataset.theme = name
  try {
    localStorage.setItem('quests.theme', name)
  } catch {
    /* ignore */
  }
}

export function loadSavedTheme() {
  try {
    return localStorage.getItem('quests.theme') || DEFAULT_THEME
  } catch {
    return DEFAULT_THEME
  }
}
