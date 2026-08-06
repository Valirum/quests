<script>
  import add from '../assets/icons/add.svg?raw'
  import checkmark from '../assets/icons/checkmark.svg?raw'
  import chevronDown from '../assets/icons/chevron-down.svg?raw'
  import chevronRight from '../assets/icons/chevron-right.svg?raw'
  import close from '../assets/icons/close.svg?raw'
  import copy from '../assets/icons/copy.svg?raw'
  import deleteIcon from '../assets/icons/delete.svg?raw'
  import document from '../assets/icons/document.svg?raw'
  import edit from '../assets/icons/edit.svg?raw'
  import flag from '../assets/icons/flag.svg?raw'
  import layers from '../assets/icons/layers.svg?raw'
  import map from '../assets/icons/map.svg?raw'
  import pin from '../assets/icons/pin.svg?raw'
  import pinFilled from '../assets/icons/pin-filled.svg?raw'
  import renew from '../assets/icons/renew.svg?raw'
  import save from '../assets/icons/save.svg?raw'
  import scroll from '../assets/icons/scroll.svg?raw'
  import settings from '../assets/icons/settings.svg?raw'
  import subtract from '../assets/icons/subtract.svg?raw'
  import target from '../assets/icons/target.svg?raw'
  import terminal from '../assets/icons/terminal.svg?raw'

  const ICONS = {
    add,
    checkmark,
    'chevron-down': chevronDown,
    'chevron-right': chevronRight,
    close,
    copy,
    delete: deleteIcon,
    document,
    edit,
    flag,
    layers,
    map,
    pin,
    'pin-filled': pinFilled,
    renew,
    save,
    scroll,
    settings,
    subtract,
    target,
    terminal,
  }

  /** @type {{ name: string, size?: number, label?: string }} */
  let { name, size = 16, label = '' } = $props()

  let svg = $derived(ICONS[name] ?? '')
</script>

<span
  class="icon"
  style:--icon-size="{size}px"
  aria-hidden={label ? undefined : 'true'}
  aria-label={label || undefined}
  role={label ? 'img' : undefined}
>
  {@html svg}
</span>

<style>
  .icon {
    display: inline-flex;
    flex-shrink: 0;
    width: var(--icon-size, 16px);
    height: var(--icon-size, 16px);
    color: inherit;
  }

  .icon :global(svg) {
    width: 100%;
    height: 100%;
    display: block;
  }
</style>
