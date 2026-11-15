<script lang="ts">
  import { open } from "@tauri-apps/plugin-dialog";
  import { api, errorMessage, type GameConfig } from "../lib/api";
  import { app } from "../lib/store.svelte";
  import { tr } from "../lib/i18n.svelte";

  type PathField = "library_path" | "active_mods_path" | "launcher_path";

  const game = $derived(app.game!);
  const gameConfig = $derived<GameConfig>(
    app.config!.games[game.id] ?? { library_path: null, active_mods_path: null, launcher_path: null, enabled: true },
  );
  let autostart = $state(app.boot?.autostart ?? false);

  const pathFields: { field: PathField; label: string; description: string; placeholder: string; directory: boolean }[] = [
    {
      field: "library_path",
      label: "rust.settings.library.label",
      description: "settings.library.description",
      placeholder: "settings.library.placeholder",
      directory: true,
    },
    {
      field: "active_mods_path",
      label: "settings.active_mods.label",
      description: "settings.active_mods.description",
      placeholder: "settings.active_mods.placeholder",
      directory: true,
    },
    {
      field: "launcher_path",
      label: "settings.launcher.label",
      description: "settings.launcher.description",
      placeholder: "settings.launcher.placeholder",
      directory: false,
    },
  ];

  async function setPath(field: PathField, value: string | null): Promise<void> {
    await app.saveConfig((config) => {
      config.games[game.id] = { ...config.games[game.id], [field]: value || null };
    }, true);
  }

  async function browse(field: PathField, directory: boolean): Promise<void> {
    const current = gameConfig[field] ?? undefined;
    const result = await open({ directory, multiple: false, defaultPath: current });
    if (typeof result === "string") await setPath(field, result);
  }

  async function toggleAutostart(enabled: boolean): Promise<void> {
    try {
      autostart = await api.setAutostart(enabled);
    } catch (error) {
      app.showToast(errorMessage(error), true);
    }
  }
</script>

<div class="settings">
  <h1>{tr("settings.title")}</h1>

  <section>
    <h2>{tr("rust.settings.game_paths", { game: game.name })}</h2>
    {#each pathFields as item (item.field)}
      <div class="field">
        <div class="label">{tr(item.label)}</div>
        <p class="description">{tr(item.description)}</p>
        <div class="path-row">
          <input
            value={gameConfig[item.field] ?? ""}
            placeholder={tr(item.placeholder)}
            onchange={(event) => setPath(item.field, event.currentTarget.value.trim())}
          />
          <button class="btn" onclick={() => browse(item.field, item.directory)}>{tr("rust.settings.browse")}</button>
          {#if gameConfig[item.field]}
            <button class="btn quiet" onclick={() => setPath(item.field, null)}>{tr("rust.settings.clear")}</button>
          {/if}
        </div>
      </div>
    {/each}
  </section>

  <section>
    <h2>{tr("rust.settings.general")}</h2>
    <div class="field inline">
      <div class="label">{tr("settings.language.label")}</div>
      <select
        value={app.config!.language}
        onchange={(event) => app.saveConfig((config) => (config.language = event.currentTarget.value as "de" | "en"))}
      >
        <option value="de">{tr("settings.language.de")}</option>
        <option value="en">{tr("settings.language.en")}</option>
      </select>
    </div>
    <label class="check">
      <input
        type="checkbox"
        checked={app.config!.run_in_background}
        onchange={(event) => app.saveConfig((config) => (config.run_in_background = event.currentTarget.checked))}
      />
      {tr("rust.settings.background")}
    </label>
    <label class="check">
      <input type="checkbox" checked={autostart} onchange={(event) => toggleAutostart(event.currentTarget.checked)} />
      {tr("rust.settings.autostart")}
    </label>
    <p class="description">{tr("rust.settings.data_dir")}: <code>{app.boot?.data_dir}</code></p>
  </section>

  <section>
    <h2>{tr("updates.settings.title")}</h2>
    <p class="description">{tr("updates.settings.version")}: <strong>{app.boot?.version}</strong></p>
    <label class="check">
      <input
        type="checkbox"
        checked={app.config!.auto_check_updates}
        onchange={(event) => app.saveConfig((config) => (config.auto_check_updates = event.currentTarget.checked))}
      />
      {tr("updates.settings.auto_check")}
    </label>
    <div class="field inline">
      <div class="label">{tr("updates.settings.channel")}</div>
      <select
        value={app.config!.update_channel}
        onchange={(event) =>
          app.saveConfig((config) => (config.update_channel = event.currentTarget.value as "stable" | "prerelease"))}
      >
        <option value="stable">{tr("updates.channel.stable")}</option>
        <option value="prerelease">{tr("updates.channel.prerelease")}</option>
      </select>
    </div>
    <div class="field inline">
      <div class="label">{tr("rust.settings.interval")}</div>
      <input
        type="number"
        min="1"
        max="10080"
        value={app.config!.update_check_interval_minutes}
        onchange={(event) =>
          app.saveConfig((config) => (config.update_check_interval_minutes = Number(event.currentTarget.value) || 60))}
      />
    </div>
    <div class="field inline">
      {#if app.config!.skipped_update_version}
        <span class="description">{tr("updates.settings.skipped_version", { version: app.config!.skipped_update_version })}</span>
        <button class="btn quiet" onclick={() => app.saveConfig((config) => (config.skipped_update_version = ""))}>
          {tr("updates.settings.reset_skipped")}
        </button>
      {:else}
        <span class="description">{tr("updates.settings.no_skipped_version")}</span>
      {/if}
    </div>
    <div>
      <button class="btn primary" disabled={app.updatePhase.kind === "checking"} onclick={() => app.checkForUpdate(true)}>
        {app.updatePhase.kind === "checking" ? tr("rust.updates.checking") : tr("updates.settings.check_now")}
      </button>
    </div>
  </section>
</div>

<style>
  .settings {
    height: 100%;
    overflow-y: auto;
    padding: 22px 26px 40px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    max-width: 920px;
  }

  h1 {
    margin: 0;
    font-size: 22px;
    color: var(--text-strong);
  }

  section {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px 20px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  h2 {
    margin: 0;
    font-size: 15px;
    color: var(--text-strong);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .field.inline {
    flex-direction: row;
    align-items: center;
    gap: 12px;
  }

  .field.inline .label {
    min-width: 200px;
  }

  .label {
    font-weight: 750;
  }

  .description {
    margin: 0;
    color: var(--text-muted);
    line-height: 1.45;
  }

  code {
    user-select: text;
    color: #c9bfff;
  }

  .path-row {
    display: flex;
    gap: 8px;
  }

  .path-row input {
    flex: 1;
  }

  .check {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
  }

  .check input {
    width: 16px;
    height: 16px;
    accent-color: var(--accent);
  }

  input[type="number"] {
    width: 110px;
  }
</style>
