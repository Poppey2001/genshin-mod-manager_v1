<script lang="ts">
  import { untrack } from "svelte";
  import Modal from "./Modal.svelte";
  import { tr } from "../lib/i18n.svelte";

  /** Bestätigung (ohne `label`) oder Texteingabe (mit `label`). */
  let {
    title,
    message = "",
    label = "",
    value = "",
    confirmText,
    danger = false,
    onresult,
  }: {
    title: string;
    message?: string;
    label?: string;
    value?: string;
    confirmText: string;
    danger?: boolean;
    onresult: (value: string | null) => void;
  } = $props();

  // Startwert einmalig übernehmen; danach gehört der Text dem Eingabefeld.
  let text = $state(untrack(() => value));
  const valid = $derived(!label || text.trim().length > 0);

  function submit(): void {
    if (valid) onresult(label ? text.trim() : "");
  }
</script>

<Modal {title} width={480} onclose={() => onresult(null)}>
  {#if message}<p class="message">{message}</p>{/if}
  {#if label}
    <label for="ask-input">{label}</label>
    <!-- svelte-ignore a11y_autofocus -->
    <input id="ask-input" bind:value={text} autofocus onkeydown={(event) => event.key === "Enter" && submit()} />
  {/if}
  {#snippet footer()}
    <button class="btn" onclick={() => onresult(null)}>{tr("common.cancel")}</button>
    <button class="btn {danger ? 'danger' : 'primary'}" disabled={!valid} onclick={submit}>{confirmText}</button>
  {/snippet}
</Modal>

<style>
  .message {
    margin: 0;
    white-space: pre-line;
    color: var(--text-muted);
    line-height: 1.5;
  }

  label {
    font-weight: 700;
  }
</style>
