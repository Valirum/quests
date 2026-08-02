<script>
  import add from '../assets/icons/add.svg?raw'
  import checkmark from '../assets/icons/checkmark.svg?raw'
  import close from '../assets/icons/close.svg?raw'
  import deleteIcon from '../assets/icons/delete.svg?raw'
  import document from '../assets/icons/document.svg?raw'
  import edit from '../assets/icons/edit.svg?raw'
  import pin from '../assets/icons/pin.svg?raw'
  import pinFilled from '../assets/icons/pin-filled.svg?raw'
  import renew from '../assets/icons/renew.svg?raw'
  import save from '../assets/icons/save.svg?raw'
  import subtract from '../assets/icons/subtract.svg?raw'

  const ICONS = {
    add,
    checkmark,
    close,
    delete: deleteIcon,
    document,
    edit,
    pin,
    'pin-filled': pinFilled,
    renew,
    save,
    subtract,
  }

  /** @type {{ name: keyof typeof ICONS, size?: number, label?: string }} */
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
