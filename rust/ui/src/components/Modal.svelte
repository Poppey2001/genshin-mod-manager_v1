<script lang="ts">
  import type { Snippet } from "svelte";

  let {
    eyebrow = "",
    title,
    width = 640,
    closable = true,
    onclose,
    children,
    footer,
  }: {
    eyebrow?: string;
    title: string;
    width?: number;
    closable?: boolean;
    onclose: () => void;
    children: Snippet;
    footer?: Snippet;
  } = $props();

  function close(): void {
    if (closable) onclose();
  }
</script>

<svelte:window onkeydown={(event) => event.key === "Escape" && close()} />

<div class="backdrop" role="presentation" onclick={close}>
  <div
    class="dialog"
    style:width="min({width}px, calc(100vw - 40px))"
    role="dialog"
    aria-modal="true"
    tabindex="-1"
    onclick={(event) => event.stopPropagation()}
    onkeydown={() => {}}
  >
    {#if eyebrow}<div class="eyebrow">{eyebrow}</div>{/if}
    <h2>{title}</h2>
    <div class="body">{@render children()}</div>
    {#if footer}<div class="footer">{@render footer()}</div>{/if}
  </div>
</div>

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    background: rgb(5 7 10 / 0.7);
    display: grid;
    place-items: center;
    z-index: 40;
  }

  .dialog {
    max-height: calc(100vh - 60px);
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 22px 24px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-strong);
    border-radius: 14px;
    box-shadow: 0 20px 60px rgb(0 0 0 / 0.5);
  }

  h2 {
    margin: 0;
    color: var(--text-strong);
    font-size: 18px;
  }

  .body {
    display: flex;
    flex-direction: column;
    gap: 10px;
    overflow: auto;
    min-height: 0;
  }

  .footer {
    display: flex;
    gap: 8px;
    justify-content: flex-end;
    margin-top: 6px;
  }
</style>
