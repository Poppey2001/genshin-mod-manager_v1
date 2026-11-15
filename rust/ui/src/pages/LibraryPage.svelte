<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { listen, type UnlistenFn } from "@tauri-apps/api/event";
  import { convertFileSrc } from "@tauri-apps/api/core";
  import { api, errorMessage, type GameDefinition, type LibraryScan, type ModEntry, type ModState } from "../lib/api";
  import { app } from "../lib/store.svelte";
  import { tr } from "../lib/i18n.svelte";
  import { formatDate, formatSize } from "../lib/format";

  let { game }: { game: GameDefinition } = $props();

  let scan = $state<LibraryScan | null>(null);
  let scanning = $state(false);
  let progress = $state<{ current: number; total: number } | null>(null);
  let scanError = $state<string | null>(null);
  let busy = $state(false);

  let search = $state("");
  let character = $state("");
  let modType = $state("");
  let status = $state<"" | ModState>("");

  let selected = $state<Set<string>>(new Set());
  let focused = $state<string | null>(null);

  let unlisten: UnlistenFn | undefined;

  const mods = $derived(scan?.mods ?? []);
  const characters = $derived([...new Set(mods.flatMap((mod) => mod.characters))].sort(collator));
  const modTypes = $derived([...new Set(mods.map((mod) => mod.mod_type))].sort(collator));

  const visible = $derived.by(() => {
    const needle = search.trim().toLowerCase();
    return mods.filter((mod) => {
      if (character && !mod.characters.includes(character)) return false;
      if (modType && mod.mod_type !== modType) return false;
      if (status && mod.state !== status) return false;
      if (!needle) return true;
      return [mod.name, mod.relative_path, mod.mod_type, ...mod.characters].some((value) =>
        value.toLowerCase().includes(needle),
      );
    });
  });

  const stats = $derived({
    total: mods.length,
    enabled: mods.filter((mod) => mod.state === "enabled").length,
    conflicts: mods.filter((mod) => mod.state === "conflict").length,
    characters: characters.length,
  });

  const selectedMods = $derived(mods.filter((mod) => selected.has(mod.path)));
  const detail = $derived(
    selectedMods.length === 1 ? selectedMods[0] : (mods.find((mod) => mod.path === focused) ?? null),
  );

  function collator(a: string, b: string): number {
    return a.localeCompare(b, undefined, { sensitivity: "base" });
  }

  async function runScan(): Promise<void> {
    scanning = true;
    scanError = null;
    progress = null;
    try {
      scan = await api.scanLibrary(game.id);
      const known = new Set(scan.mods.map((mod) => mod.path));
      selected = new Set([...selected].filter((path) => known.has(path)));
      app.showToast(tr("library.status.scan_result", { count: scan.mods.length, seconds: scan.duration_seconds }));
    } catch (error) {
      const message = errorMessage(error);
      if (!(error as { kind?: string })?.kind?.includes("cancelled")) scanError = message;
    } finally {
      scanning = false;
      progress = null;
    }
  }

  async function runAction(targets: ModEntry[], action: "enable" | "disable" | "adopt"): Promise<void> {
    if (!targets.length || busy) return;
    busy = true;
    try {
      const results = await api.applyModAction(
        game.id,
        targets.map((mod) => mod.path),
        action,
      );
      const states = new Map(results.map((result) => [result.path, result.state]));
      if (scan) {
        scan.mods = scan.mods.map((mod) => {
          const state = states.get(mod.path);
          return state ? { ...mod, state } : mod;
        });
      }
      const failures = results.filter((result) => result.error);
      if (failures.length === 1) app.showToast(failures[0].error!.message, true);
      else if (failures.length > 1)
        app.showToast(
          `${tr("rust.library.action_failed", { count: failures.length })}\n${failures[0].error!.message}`,
          true,
        );
    } catch (error) {
      app.showToast(errorMessage(error), true);
    } finally {
      busy = false;
    }
  }

  function toggleSelection(mod: ModEntry, event: MouseEvent): void {
    const next = new Set(selected);
    if (event.shiftKey && focused) {
      const paths = visible.map((item) => item.path);
      const [from, to] = [paths.indexOf(focused), paths.indexOf(mod.path)].sort((a, b) => a - b);
      if (from >= 0) paths.slice(from, to + 1).forEach((path) => next.add(path));
    } else if (event.ctrlKey || event.metaKey) {
      if (next.has(mod.path)) next.delete(mod.path);
      else next.add(mod.path);
    } else {
      next.clear();
      next.add(mod.path);
    }
    selected = next;
    focused = mod.path;
  }

  function toggleAll(): void {
    selected = selected.size === visible.length ? new Set() : new Set(visible.map((mod) => mod.path));
  }

  function resetFilters(): void {
    search = "";
    character = "";
    modType = "";
    status = "";
  }

  function stateLabel(state: ModState): string {
    return tr(`rust.state.${state}`);
  }

  async function launch(): Promise<void> {
    try {
      await api.launchGame(game.id);
    } catch (error) {
      app.showToast(errorMessage(error), true);
    }
  }

  onMount(async () => {
    unlisten = await listen<{ current: number; total: number }>("scan-progress", (event) => {
      progress = event.payload;
    });
    void runScan();
  });

  onDestroy(() => {
    unlisten?.();
    if (scanning) void api.cancelScan();
  });
</script>

<div class="library">
  <header class="header">
    <div>
      <h1>{tr("library.title")}</h1>
      <p class="subtitle">
        {scan?.library_dir ?? tr("library.description")}
        {#if scan}
          · {scan.is_network ? tr("library.location.network") : tr("library.location.local")}
        {/if}
      </p>
    </div>
    <div class="header-actions">
      {#if app.config?.games[game.id]?.launcher_path}
        <button class="btn" onclick={launch}>{tr("rust.library.launch")}</button>
      {/if}
      {#if scanning}
        <button class="btn" onclick={() => api.cancelScan()}>{tr("common.cancel")}</button>
      {:else}
        <button class="btn primary" onclick={runScan}>{tr("library.action.scan")}</button>
      {/if}
    </div>
  </header>

  <div class="stats">
    <div class="stat"><span>{stats.total}</span>{tr("rust.library.stat.mods")}</div>
    <div class="stat"><span class="ok">{stats.enabled}</span>{tr("rust.state.enabled")}</div>
    <div class="stat"><span class="warn">{stats.conflicts}</span>{tr("rust.state.conflict")}</div>
    <div class="stat"><span>{stats.characters}</span>{tr("rust.library.stat.characters")}</div>
  </div>

  {#if scan && !scan.active_mods_dir}
    <div class="notice">
      {tr("rust.library.no_active_dir")}
      <button class="btn" onclick={() => (app.page = "settings")}>{tr("navigation.settings")}</button>
    </div>
  {/if}

  <div class="filters">
    <input class="search" placeholder={tr("library.filter.search_placeholder")} bind:value={search} />
    <select bind:value={character}>
      <option value="">{tr("library.filter.all_characters")}</option>
      {#each characters as name (name)}<option value={name}>{name}</option>{/each}
    </select>
    <select bind:value={modType}>
      <option value="">{tr("library.filter.all_mod_types")}</option>
      {#each modTypes as name (name)}<option value={name}>{name}</option>{/each}
    </select>
    <select bind:value={status}>
      <option value="">{tr("library.filter.all_statuses")}</option>
      {#each ["enabled", "disabled", "conflict", "broken", "not_configured"] as const as state (state)}
        <option value={state}>{stateLabel(state)}</option>
      {/each}
    </select>
    <button class="btn quiet" onclick={resetFilters}>{tr("library.filter.reset")}</button>
  </div>

  {#if selected.size > 1}
    <div class="bulk">
      <span>{tr("rust.library.selected", { count: selected.size })}</span>
      <button class="btn" disabled={busy} onclick={() => runAction(selectedMods, "enable")}>
        {tr("library.list.enable_selected")}
      </button>
      <button class="btn" disabled={busy} onclick={() => runAction(selectedMods, "disable")}>
        {tr("library.list.disable_selected")}
      </button>
      <button
        class="btn"
        disabled={busy}
        onclick={() =>
          runAction(
            selectedMods.filter((mod) => mod.state === "conflict"),
            "adopt",
          )}
      >
        {tr("library.list.adopt_selected")}
      </button>
    </div>
  {/if}

  <div class="body">
    <div class="list">
      {#if scanning}
        <div class="state-panel">
          <div class="spinner"></div>
          <p>{tr("library.status.scan_started")}</p>
          {#if progress && progress.total > 0}
            <progress max={progress.total} value={progress.current}></progress>
            <p class="muted">{progress.current} / {progress.total}</p>
          {/if}
        </div>
      {:else if scanError}
        <div class="state-panel error">
          <h3>{tr("library.status.scan_failed")}</h3>
          <p>{scanError}</p>
        </div>
      {:else if mods.length === 0}
        <div class="state-panel">
          <h3>{tr("rust.library.empty_title")}</h3>
          <p class="muted">{tr("rust.library.empty_body")}</p>
          {#if scan}<button class="btn" onclick={() => api.openPath(scan!.library_dir)}>{tr("rust.library.open_folder")}</button>{/if}
        </div>
      {:else}
        <table>
          <thead>
            <tr>
              <th class="check">
                <input
                  type="checkbox"
                  checked={selected.size > 0 && selected.size === visible.length}
                  onchange={toggleAll}
                />
              </th>
              <th>{tr("library.column.mod")}</th>
              <th>{tr("library.column.character")}</th>
              <th>{tr("library.column.mod_type")}</th>
              <th>{tr("library.column.status")}</th>
              <th class="num">{tr("library.column.size")}</th>
              <th class="action"></th>
            </tr>
          </thead>
          <tbody>
            {#each visible as mod (mod.path)}
              <tr class:selected={selected.has(mod.path)} onclick={(event) => toggleSelection(mod, event)}>
                <td class="check">
                  <input
                    type="checkbox"
                    checked={selected.has(mod.path)}
                    onclick={(event) => {
                      event.stopPropagation();
                      const next = new Set(selected);
                      if (next.has(mod.path)) next.delete(mod.path);
                      else next.add(mod.path);
                      selected = next;
                      focused = mod.path;
                    }}
                  />
                </td>
                <td>
                  <div class="mod-name">{mod.name}</div>
                  <div class="mod-path">{mod.relative_path}</div>
                </td>
                <td>{mod.characters.join(", ") || "–"}</td>
                <td>{mod.mod_type}</td>
                <td><span class="badge {mod.state}">{stateLabel(mod.state)}</span></td>
                <td class="num">{formatSize(mod.total_size)}</td>
                <td class="action">
                  {#if mod.state === "enabled"}
                    <button class="btn small" disabled={busy} onclick={(event) => (event.stopPropagation(), runAction([mod], "disable"))}>
                      {tr("library.details.action.disable")}
                    </button>
                  {:else if mod.state === "disabled"}
                    <button class="btn small primary" disabled={busy} onclick={(event) => (event.stopPropagation(), runAction([mod], "enable"))}>
                      {tr("library.details.action.enable")}
                    </button>
                  {/if}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
        <div class="footer muted">{tr("library.status.filter_result", { visible: visible.length, total: mods.length })}</div>
      {/if}
    </div>

    <aside class="details">
      {#if selectedMods.length > 1}
        <div class="eyebrow">{tr("library.details.eyebrow")}</div>
        <h2>{tr("library.details.multiple_title", { count: selectedMods.length })}</h2>
        <p class="muted">{tr("library.details.multiple_description")}</p>
      {:else if detail}
        {#if detail.preview_path}
          <img class="preview" src={convertFileSrc(detail.preview_path)} alt={tr("library.details.preview")} />
        {/if}
        <div class="eyebrow">{tr("library.details.eyebrow")}</div>
        <h2>{detail.name}</h2>
        <span class="badge {detail.state}">{stateLabel(detail.state)}</span>
        {#if detail.error}<p class="detail-error">{detail.error}</p>{/if}
        <dl>
          <dt>{tr("library.details.character")}</dt>
          <dd>{detail.characters.join(", ") || "–"}</dd>
          <dt>{tr("library.details.mod_type")}</dt>
          <dd>{detail.mod_type}</dd>
          <dt>{tr("library.details.location")}</dt>
          <dd>{detail.is_network ? tr("common.network") : tr("common.local")}{detail.is_symlink ? ` · ${tr("common.symlink")}` : ""}</dd>
          <dt>{tr("library.details.files")}</dt>
          <dd>{detail.file_count} · {tr("library.details.ini_files")}: {detail.ini_file_count}</dd>
          <dt>{tr("library.details.size")}</dt>
          <dd>{formatSize(detail.total_size)}</dd>
          <dt>{tr("library.details.modified")}</dt>
          <dd>{formatDate(detail.modified_at)}</dd>
          <dt>{tr("library.details.path")}</dt>
          <dd class="path">{detail.path}</dd>
        </dl>
        <div class="eyebrow">{tr("library.details.actions")}</div>
        <div class="detail-actions">
          {#if detail.state === "enabled"}
            <button class="btn" disabled={busy} onclick={() => runAction([detail!], "disable")}>{tr("library.details.action.disable")}</button>
          {:else if detail.state === "disabled"}
            <button class="btn primary" disabled={busy} onclick={() => runAction([detail!], "enable")}>{tr("library.details.action.enable")}</button>
          {:else if detail.state === "conflict"}
            <button class="btn" disabled={busy} title={tr("library.details.action.adopt_tooltip")} onclick={() => runAction([detail!], "adopt")}>
              {tr("library.details.action.adopt")}
            </button>
          {:else if detail.state === "not_configured"}
            <button class="btn" onclick={() => (app.page = "settings")}>{tr("library.details.action.not_configured")}</button>
          {/if}
          <button class="btn" onclick={() => api.revealPath(detail!.path)}>{tr("rust.library.open_folder")}</button>
        </div>
      {:else}
        <div class="empty-detail">
          <h3>{tr("library.details.empty_title")}</h3>
          <p class="muted">{tr("library.details.empty_description")}</p>
        </div>
      {/if}
    </aside>
  </div>
</div>

<style>
  .library {
    height: 100%;
    display: flex;
    flex-direction: column;
    padding: 20px 22px 16px;
    gap: 14px;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
  }

  h1 {
    margin: 0;
    font-size: 22px;
    color: var(--text-strong);
  }

  .subtitle {
    margin: 4px 0 0;
    color: var(--text-muted);
    user-select: text;
    word-break: break-all;
  }

  .header-actions {
    display: flex;
    gap: 8px;
  }

  .stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
  }

  .stat {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 14px;
    color: var(--text-muted);
    font-weight: 650;
    display: flex;
    align-items: baseline;
    gap: 8px;
  }

  .stat span {
    font-size: 20px;
    font-weight: 850;
    color: var(--text-strong);
  }

  .stat .ok {
    color: var(--success);
  }

  .stat .warn {
    color: var(--warning);
  }

  .notice {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 10px 14px;
    border: 1px solid #5c4a20;
    background: var(--warning-soft);
    color: #ffe1ad;
    border-radius: var(--radius);
  }

  .filters,
  .bulk {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
  }

  .search {
    flex: 1;
    min-width: 220px;
  }

  .bulk {
    padding: 8px 12px;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    border-radius: var(--radius);
  }

  .bulk span {
    font-weight: 750;
    margin-right: auto;
  }

  .body {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: minmax(0, 1fr) 320px;
    gap: 14px;
  }

  .list,
  .details {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: auto;
  }

  .details {
    padding: 18px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  table {
    width: 100%;
    border-collapse: collapse;
  }

  th {
    position: sticky;
    top: 0;
    background: var(--bg-elevated);
    text-align: left;
    font-size: 11px;
    color: var(--text-faint);
    font-weight: 800;
    padding: 10px 12px;
    border-bottom: 1px solid var(--border);
    z-index: 1;
  }

  td {
    padding: 9px 12px;
    border-bottom: 1px solid #1d2229;
    vertical-align: middle;
  }

  tbody tr {
    cursor: default;
  }

  tbody tr:hover {
    background: #181d24;
  }

  tbody tr.selected {
    background: #1e1b31;
  }

  .check {
    width: 34px;
  }

  .num {
    text-align: right;
    white-space: nowrap;
  }

  .action {
    width: 1%;
    text-align: right;
  }

  .mod-name {
    font-weight: 750;
    color: var(--text-strong);
  }

  .mod-path {
    color: var(--text-faint);
    font-size: 11px;
    margin-top: 2px;
  }

  .btn.small {
    padding: 5px 10px;
    font-size: 12px;
  }

  .footer {
    padding: 10px 12px;
  }

  .muted {
    color: var(--text-muted);
  }

  .state-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 30px;
    text-align: center;
  }

  .state-panel h3 {
    margin: 0;
  }

  .state-panel.error p {
    color: #ffc2cb;
    white-space: pre-wrap;
  }

  progress {
    width: 260px;
    accent-color: var(--accent);
  }

  .spinner {
    width: 28px;
    height: 28px;
    border: 3px solid var(--border-strong);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  .preview {
    width: 100%;
    max-height: 200px;
    object-fit: cover;
    border-radius: 10px;
    border: 1px solid var(--border);
  }

  .details h2 {
    margin: 0;
    font-size: 17px;
    color: var(--text-strong);
    word-break: break-word;
  }

  .details .badge {
    align-self: flex-start;
  }

  dl {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 6px 12px;
    margin: 6px 0;
  }

  dt {
    color: var(--text-faint);
    font-weight: 700;
  }

  dd {
    margin: 0;
    user-select: text;
  }

  dd.path {
    word-break: break-all;
    color: var(--text-muted);
    font-size: 12px;
  }

  .detail-error {
    color: #ffc2cb;
    font-size: 12px;
    margin: 0;
  }

  .detail-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .empty-detail {
    margin: auto;
    text-align: center;
  }

  @media (max-width: 1050px) {
    .body {
      grid-template-columns: 1fr;
    }
    .details {
      display: none;
    }
  }
</style>
