<script lang="ts">
  import { openUrl } from "@tauri-apps/plugin-opener";
  import type { UpdateMeta } from "../lib/api";
  import { app } from "../lib/store.svelte";
  import { tr } from "../lib/i18n.svelte";

  let { update }: { update: UpdateMeta } = $props();

  const phase = $derived(app.updatePhase);
  const working = $derived(phase.kind === "downloading" || phase.kind === "installing");

  function close(): void {
    if (!working) app.updateDialogOpen = false;
  }
</script>

<div class="backdrop" role="presentation" onclick={close}>
  <div class="dialog" role="dialog" aria-modal="true" tabindex="-1" onclick={(event) => event.stopPropagation()} onkeydown={(event) => event.key === "Escape" && close()}>
    <div class="eyebrow">{tr("updates.dialog.window_title")}</div>
    <h2>{tr("updates.dialog.available")}: {update.version}</h2>
    <p class="muted">{tr("updates.dialog.version", { current: update.current_version })}</p>

    <div class="eyebrow">{tr("updates.dialog.release_notes")}</div>
    <pre class="notes">{update.notes.trim() || tr("updates.dialog.no_notes")}</pre>

    {#if phase.kind === "downloading"}
      <p>{tr("rust.updates.downloading", { percent: phase.percent === null ? "" : `${phase.percent.toFixed(0)} %` })}</p>
      <progress max="100" value={phase.percent ?? undefined}></progress>
    {:else if phase.kind === "installing"}
      <p>{tr("rust.updates.installing")}</p>
      <progress></progress>
    {:else if phase.kind === "error"}
      <p class="error">{phase.message}</p>
    {/if}

    <div class="buttons">
      <button class="btn quiet" disabled={working} onclick={() => app.skipUpdate()}>{tr("rust.updates.skip")}</button>
      <button class="btn quiet" onclick={() => openUrl(update.release_url)}>{tr("updates.dialog.open_release")}</button>
      <div class="spacer"></div>
      <button class="btn" disabled={working} onclick={close}>{tr("updates.dialog.later")}</button>
      <button class="btn primary" disabled={working} onclick={() => app.installUpdate()}>{tr("updates.dialog.install")}</button>
    </div>
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
    width: min(640px, calc(100vw - 40px));
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
  }

  .muted {
    margin: 0;
    color: var(--text-muted);
  }

  .notes {
    margin: 0;
    flex: 1;
    min-height: 120px;
    max-height: 320px;
    overflow: auto;
    padding: 12px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 8px;
    white-space: pre-wrap;
    font-family: var(--font);
    user-select: text;
  }

  progress {
    width: 100%;
    accent-color: var(--accent);
  }

  .error {
    color: #ffc2cb;
    white-space: pre-wrap;
    user-select: text;
  }

  .buttons {
    display: flex;
    gap: 8px;
    margin-top: 6px;
  }

  .spacer {
    flex: 1;
  }
</style>
