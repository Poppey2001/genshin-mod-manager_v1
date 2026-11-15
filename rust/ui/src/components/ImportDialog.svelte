<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { listen, type UnlistenFn } from "@tauri-apps/api/event";
  import Modal from "./Modal.svelte";
  import { api, errorMessage, type ImportBatchResult, type ImportCheck } from "../lib/api";
  import { tr } from "../lib/i18n.svelte";

  let {
    gameId,
    paths,
    characters,
    modTypes,
    onclose,
  }: {
    gameId: string;
    paths: string[];
    characters: string[];
    modTypes: string[];
    onclose: (imported: boolean) => void;
  } = $props();

  type Stage = "checking" | "options" | "importing" | "done" | "error";

  let stage = $state<Stage>("checking");
  let checks = $state<ImportCheck[]>([]);
  let character = $state("");
  let modType = $state("");
  let conflictPolicy = $state<"rename" | "skip">("rename");
  let acceptWarnings = $state(false);
  let progress = $state<{ current: number; total: number; name: string } | null>(null);
  let result = $state<ImportBatchResult | null>(null);
  let failure = $state("");
  let unlisten: UnlistenFn | undefined;

  const usable = $derived(checks.filter((check) => check.supported && !check.error && !check.report?.blocked));
  const blocked = $derived(checks.filter((check) => check.report?.blocked || check.error));
  const unsupported = $derived(checks.filter((check) => !check.supported));
  const warned = $derived(usable.filter((check) => (check.report?.warning_files.length ?? 0) > 0));
  const missingCharacter = $derived(modType.trim() !== "" && character.trim() === "");
  const canStart = $derived(usable.length > 0 && !missingCharacter && (warned.length === 0 || acceptWarnings));

  function baseName(path: string): string {
    return path.split(/[\\/]/).filter(Boolean).pop() ?? path;
  }

  async function start(): Promise<void> {
    stage = "importing";
    try {
      result = await api.importMods(
        gameId,
        usable.map((check) => check.path),
        { character: character.trim() || null, mod_type: modType.trim() || null, conflict_policy: conflictPolicy },
      );
      stage = "done";
    } catch (error) {
      failure =
        (error as { kind?: string })?.kind === "cancelled" ? tr("library.status.import_cancelled") : errorMessage(error);
      stage = "error";
    }
  }

  onMount(async () => {
    unlisten = await listen<{ current: number; total: number; name: string }>("import-progress", (event) => {
      progress = event.payload;
    });
    try {
      checks = await api.checkImportSources(paths);
      stage = "options";
    } catch (error) {
      failure = errorMessage(error);
      stage = "error";
    }
  });

  onDestroy(() => unlisten?.());
</script>

<Modal
  eyebrow={tr("import.options.window_title")}
  title={stage === "done"
    ? tr("library.dialog.import.completed")
    : stage === "error"
      ? tr("library.dialog.import.failed")
      : tr("import.options.title", { count: paths.length })}
  width={640}
  closable={stage !== "importing"}
  onclose={() => onclose(stage === "done" && (result?.imported_count ?? 0) > 0)}
>
  {#if stage === "checking"}
    <p class="muted">{tr("library.status.scan_started")}</p>
    <progress></progress>
  {:else if stage === "options"}
    <ul class="sources">
      {#each usable.slice(0, 6) as check (check.path)}
        <li>{check.is_directory ? "📁" : "🗜️"} {baseName(check.path)}</li>
      {/each}
      {#if usable.length > 6}<li class="muted">{tr("import.options.more_sources", { count: usable.length - 6 })}</li>{/if}
    </ul>

    {#if blocked.length}
      <div class="box danger">
        <strong>{tr("archive.security.blocked.title")}</strong>
        <p>{tr("archive.security.blocked.message")}</p>
        {#each blocked as check (check.path)}
          <div class="file">{baseName(check.path)}</div>
          {#if check.error}<div class="detail">{check.error}</div>{/if}
          {#each check.report?.issues.filter((issue) => issue.severity === "block").slice(0, 5) ?? [] as issue, index (index)}
            <div class="detail">{issue.message}{issue.member ? ` – ${issue.member}` : ""}</div>
          {/each}
        {/each}
      </div>
    {/if}

    {#if unsupported.length}
      <div class="box">
        <strong>{tr("library.import.unsupported_title")}</strong>
        {#each unsupported as check (check.path)}<div class="file">{baseName(check.path)}</div>{/each}
      </div>
    {/if}

    {#if warned.length}
      <div class="box warning">
        <strong>{tr("archive.security.warning.title")}</strong>
        <p>{tr("archive.security.warning.message")}</p>
        {#each warned as check (check.path)}
          <div class="file">{baseName(check.path)}</div>
          {#each check.report?.warning_files ?? [] as file (file)}<div class="detail">{file}</div>{/each}
        {/each}
        <label class="check"><input type="checkbox" bind:checked={acceptWarnings} /> {tr("rust.import.accept_warnings")}</label>
      </div>
    {/if}

    {#if usable.length}
      <p class="muted">{tr("import.options.description")}</p>
      <div class="form">
        <label for="import-character">{tr("import.options.character_label")}</label>
        <input id="import-character" list="import-characters" placeholder={tr("import.options.character_placeholder")} bind:value={character} />
        <label for="import-type">{tr("import.options.mod_type_label")}</label>
        <input id="import-type" list="import-types" placeholder={tr("import.options.mod_type_placeholder")} bind:value={modType} />
        <label for="import-conflict">{tr("import.options.conflict_label")}</label>
        <select id="import-conflict" bind:value={conflictPolicy}>
          <option value="rename">{tr("import.options.conflict.rename")}</option>
          <option value="skip">{tr("import.options.conflict.skip")}</option>
        </select>
      </div>
      <datalist id="import-characters">{#each characters as name (name)}<option value={name}></option>{/each}</datalist>
      <datalist id="import-types">{#each modTypes as name (name)}<option value={name}></option>{/each}</datalist>
      {#if missingCharacter}<p class="error">{tr("import.options.character_missing.message")}</p>{/if}
    {/if}
  {:else if stage === "importing"}
    <p>{tr("library.status.import_started")} {progress?.name ?? ""}</p>
    <progress max={progress?.total || 1} value={progress?.current ?? 0}></progress>
  {:else if stage === "done" && result}
    <div class="summary">
      <span class="ok">{tr("library.import_result.imported", { count: result.imported_count })}</span>
      <span>{tr("library.import_result.skipped", { count: result.skipped_count })}</span>
      <span class="bad">{tr("library.import_result.failed", { count: result.failed_count })}</span>
      <span class="muted">{tr("library.import_result.duration", { seconds: result.duration_seconds })}</span>
    </div>
    <ul class="results">
      {#each result.items as item (item.source)}
        <li class={item.status}>
          <strong>{baseName(item.source)}</strong>
          <span>{item.message}</span>
          {#if item.destination}<span class="muted path">{item.destination}</span>{/if}
        </li>
      {/each}
    </ul>
  {:else if stage === "error"}
    <p class="error">{failure}</p>
  {/if}

  {#snippet footer()}
    {#if stage === "options"}
      <button class="btn" onclick={() => onclose(false)}>{tr("common.cancel")}</button>
      <button class="btn primary" disabled={!canStart} onclick={start}>{tr("import.options.start")}</button>
    {:else if stage === "importing"}
      <button class="btn" onclick={() => api.cancelImport()}>{tr("library.action.cancel_import")}</button>
    {:else}
      <button class="btn primary" onclick={() => onclose(stage === "done" && (result?.imported_count ?? 0) > 0)}>
        {tr("common.close")}
      </button>
    {/if}
  {/snippet}
</Modal>

<style>
  .muted {
    color: var(--text-muted);
    margin: 0;
  }

  .sources,
  .results {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .results li {
    display: flex;
    flex-direction: column;
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--bg-input);
    border-left: 3px solid var(--border-strong);
  }

  .results li.imported {
    border-left-color: var(--success);
  }
  .results li.failed {
    border-left-color: var(--danger);
  }
  .results li.skipped {
    border-left-color: var(--warning);
  }

  .path {
    font-size: 11px;
    word-break: break-all;
  }

  .box {
    padding: 10px 12px;
    border-radius: 9px;
    border: 1px solid var(--border-strong);
    background: var(--bg-input);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .box p {
    margin: 0;
    color: var(--text-muted);
  }

  .box.danger {
    border-color: #6b2a36;
    background: var(--danger-soft);
  }

  .box.warning {
    border-color: #5c4a20;
    background: var(--warning-soft);
  }

  .file {
    font-weight: 750;
    margin-top: 4px;
  }

  .detail {
    font-size: 12px;
    color: var(--text-muted);
    word-break: break-all;
  }

  .form {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 8px 12px;
    align-items: center;
  }

  .check {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-top: 6px;
  }

  .summary {
    display: flex;
    gap: 14px;
    flex-wrap: wrap;
    font-weight: 700;
  }

  .ok {
    color: var(--success);
  }
  .bad {
    color: #ff8fa0;
  }

  .error {
    color: #ffc2cb;
    white-space: pre-wrap;
    margin: 0;
  }

  progress {
    width: 100%;
    accent-color: var(--accent);
  }
</style>
