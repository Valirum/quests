<script>
  import Icon from './Icon.svelte'

  /** @type {{
   *   icon?: string | null,
   *   iconUrl?: string | null,
   *   size?: 'sm' | 'md' | 'lg',
   *   alt?: string,
   * }} */
  let {
    icon = 'document',
    iconUrl = null,
    size = 'md',
    alt = '',
  } = $props()

  let custom = $derived(Boolean(iconUrl))
</script>

{#if custom}
  <span class="ql-icon ql-icon--custom ql-icon--{size}" aria-hidden={alt ? undefined : 'true'}>
    <img src={iconUrl} {alt} draggable="false" />
  </span>
{:else}
  <span class="ql-icon ql-icon--svg ql-icon--{size}" aria-hidden="true">
    <Icon name={icon || 'document'} size={size === 'sm' ? 12 : size === 'lg' ? 22 : 16} />
  </span>
{/if}

<style>
  .ql-icon {
    display: inline-flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: center;
  }

  .ql-icon--svg.ql-icon--md,
  .ql-icon--svg.ql-icon--lg {
    width: 2.25rem;
    height: 2.25rem;
    border-radius: 0.35rem;
    color: var(--line-color, #9a9a9a);
    background: color-mix(in srgb, var(--line-color, #9a9a9a) 18%, transparent);
  }

  .ql-icon--svg.ql-icon--lg {
    /* filled by parent stretch in detail head */
    width: auto;
    height: 100%;
    aspect-ratio: 1;
    min-height: 2.5rem;
  }

  .ql-icon--custom {
    line-height: 0;
  }

  .ql-icon--custom.ql-icon--sm img {
    width: 0.85rem;
    height: 0.85rem;
    object-fit: contain;
    border-radius: 0.15rem;
  }

  .ql-icon--custom.ql-icon--md img {
    width: 2.25rem;
    height: 2.25rem;
    object-fit: contain;
    border-radius: 0.35rem;
  }

  .ql-icon--custom.ql-icon--lg {
    align-self: stretch;
    height: auto;
    max-height: 100%;
  }

  .ql-icon--custom.ql-icon--lg img {
    display: block;
    height: 100%;
    width: auto;
    max-height: 100%;
    object-fit: contain;
    border-radius: 0.35rem;
  }
</style>
