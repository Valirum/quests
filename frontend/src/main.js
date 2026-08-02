import { mount } from 'svelte'
import './app.css'
import App from './App.svelte'
import { applyTheme, loadSavedTheme } from './lib/theme.js'

applyTheme(loadSavedTheme())

const app = mount(App, {
  target: document.getElementById('app'),
})

export default app
