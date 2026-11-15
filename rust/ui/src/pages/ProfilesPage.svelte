<script lang="ts">
  import { onDestroy, onMount } from "svelte";
  import { listen, type UnlistenFn } from "@tauri-apps/api/event";
  import { api, errorMessage, type GameDefinition, type ModProfile } from "../lib/api";
  import { app } from "../lib/store.svelte";
  import { currentLanguage, tr } from "../lib/i18n.svelte";
  import AskDialog from "../components/AskDialog.svelte";

  let { game }: { game: GameDefinition } = $props();

  type Ask = {
    title: string;
    message?: string;
    label?: string;
    value?: string;
    confirmText: string;
    danger?: boolean;
    run: (value: string) => Promise<void>;
  };

  let profiles = $state<ModProfile[]>([]);
  let loading = $state(true);
  let applying = $state<{ name: string; current: number; total: number } | null>(null);
  let ask = $state<Ask | null>(null);
  let unlisten: UnlistenFn | undefined;

  const active = $derived(app.config?.selected_profile ?? "");
  const activeExists = $derived(profiles.some((profile) => profile.name === active));

  async function refresh(): Promise<void> {
    loading = true;
    try {
      profiles = await api.listProfiles(game.id);
    } catch (error) {
      app.showToast(errorMessage(error), true);
    } finally {
      loading = false;
    }
  }

  function setActive(name: string): void {
    if (app.config) app.config.selected_profile = name;
  }

  async function guarded(action: () => Promise<void>): Promise<void> {
    try {
      await action();
    } catch (error) {
      app.showToast(errorMessage(error), true);
    }
    await refresh();
  }

  function createProfile(): void {
    ask = {
      title: tr("profiles.dialog.create.title"),
      label: tr("profiles.dialog.create.label"),
      confirmText: tr("profiles.action.save_current"),
      run: (name) =>
        guarded(async () => {
          if (profiles.some((profile) => profile.name.toLowerCase() === name.toLowerCase())) {
            app.showToast(tr("profiles.warning.name_exists", { name }), true);
            return;
          }
          const profile = await api.saveProfile(game.id, name, false);
          setActive(profile.name);
        }),
    };
  }

  function overwrite(profile: ModProfile): void {
    ask = {
      title: tr("profiles.dialog.overwrite.title"),
      message: tr("profiles.dialog.overwrite.message", { name: profile.name }),
      confirmText: tr("profiles.action.save_current"),
      run: () =>
        guarded(async () => {
          await api.saveProfile(game.id, profile.name, true);
          setActive(profile.name);
        }),
    };
  }

  function rename(profile: ModProfile): void {
    ask = {
      title: tr("profiles.dialog.rename.title"),
      label: tr("profiles.dialog.rename.label"),
      value: profile.name,
      confirmText: tr("profiles.action.rename"),
      run: (name) =>
        guarded(async () => {
          const renamed = await api.renameProfile(game.id, profile.name, name);
          if (active === profile.name) setActive(renamed.name);
        }),
    };
  }

  function remove(profile: ModProfile): void {
    ask = {
      title: tr("profiles.dialog.delete.title"),
      message: tr("profiles.dialog.delete.message", { name: profile.name }),
      confirmText: tr("profiles.action.delete"),
      danger: true,
      run: () => guarded(() => api.deleteProfile(game.id, profile.name)),
    };
  }

  function activate(profile: ModProfile): void {
    const enabled = profile.mods.filter((mod) => mod.enabled).length;
    ask = {
      title: tr("profiles.dialog.activate.title"),
      message: tr("profiles.dialog.activate.message", {
        name: profile.name,
        total: profile.mods.length,
        enabled,
        disabled: profile.mods.length - enabled,
      }),
      confirmText: tr("profiles.action.activate"),
      run: async () => {
        applying = { name: profile.name, current: 0, total: profile.mods.length };
        try {
          const result = await api.applyProfile(game.id, profile.name);
          const complete = result.missing_count + result.blocked_count + result.failed_count === 0;
          if (complete) {
            setActive(profile.name);
            app.showToast(
              tr("profiles.result.success", {
                name: profile.name,
                changed: result.changed_count,
                unchanged: result.unchanged_count,
              }),
            );
          } else {
            app.showToast(
              tr("profiles.result.warning", {
                changed: result.changed_count,
                unchanged: result.unchanged_count,
                missing: result.missing_count,
                blocked: result.blocked_count,
                failed: result.failed_count,
              }),
              true,
            );
          }
        } catch (error) {
          app.showToast(tr("profiles.error.apply_failed", { error: errorMessage(error) }), true);
        } finally {
          applying = null;
        }
      },
    };
  }

  function formatDate(value: string): string {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? value
      : date.toLocaleString(currentLanguage(), { dateStyle: "medium", timeStyle: "short" });
  }

  onMount(async () => {
    unlisten = await listen<{ current: number; total: number; name: string }>("profile-progress", (event) => {
      if (applying) applying = { ...applying, current: event.payload.current, total: event.payload.total };
    });
    await refresh();
  });

  onDestroy(() => unlisten?.());
</script>

<div class="profiles">
  {#if ask}
    <AskDialog
      title={ask.title}
      message={ask.message}
      label={ask.label}
      value={ask.value}
      confirmText={ask.confirmText}
      danger={ask.danger}
      onresult={(value) => {
        const current = ask;
        ask = null;
        if (value !== null && current) void current.run(value);
      }}
    />
  {/if}

  <header>
    <div>
      <h1>{tr("profiles.title")}</h1>
      <p class="muted">{tr("profiles.description")}</p>
    </div>
    <div class="actions">
      <button class="btn" disabled={!!applying} onclick={refresh}>{tr("profiles.action.refresh")}</button>
      <button class="btn primary" disabled={!!applying} onclick={createProfile}>{tr("profiles.action.new")}</button>
    </div>
  </header>

  <div class="summary">
    <div class="eyebrow">{tr("profiles.summary.title")}</div>
    <strong>{activeExists ? tr("profiles.summary.active", { name: active }) : tr("profiles.summary.none")}</strong>
    <span class="muted">{tr("profiles.summary.count", { count: profiles.length })}</span>
  </div>

  {#if applying}
    <div class="applying">
      <span>{tr("profiles.status.applying", { name: applying.name })}</span>
      <progress max={applying.total || 1} value={applying.current}></progress>
    </div>
  {/if}

  {#if !loading && profiles.length === 0}
    <div class="empty">
      <h3>{tr("profiles.empty.title")}</h3>
      <p class="muted">{tr("profiles.empty.description")}</p>
      <button class="btn primary" onclick={createProfile}>{tr("profiles.action.new")}</button>
    </div>
  {:else}
    <div class="grid">
      {#each profiles as profile (profile.name)}
        <article class="card" class:active={profile.name === active}>
          <div class="card-head">
            <h3>{profile.name}</h3>
            {#if profile.name === active}<span class="badge enabled">{tr("profiles.card.active")}</span>{/if}
          </div>
          <p class="muted">
            {tr("profiles.card.stats", { total: profile.mods.length, enabled: profile.mods.filter((m) => m.enabled).length })}
          </p>
          <p class="muted small">{tr("profiles.card.updated", { value: formatDate(profile.updated_at) })}</p>
          <div class="card-actions">
            <button class="btn primary" disabled={!!applying} onclick={() => activate(profile)}>{tr("profiles.action.activate")}</button>
            <button class="btn" disabled={!!applying} onclick={() => overwrite(profile)}>{tr("profiles.action.save_current")}</button>
            <button class="btn quiet" disabled={!!applying} onclick={() => rename(profile)}>{tr("profiles.action.rename")}</button>
            <button class="btn quiet" disabled={!!applying} onclick={() => remove(profile)}>{tr("profiles.action.delete")}</button>
          </div>
        </article>
      {/each}
    </div>
  {/if}
</div>

<style>
  .profiles {
    height: 100%;
    overflow-y: auto;
    padding: 20px 22px 30px;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }

  header {
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

  .muted {
    color: var(--text-muted);
    margin: 4px 0 0;
  }

  .small {
    font-size: 12px;
  }

  .actions,
  .card-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }

  .summary,
  .applying {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px;
    border-radius: 10px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
  }

  .summary strong {
    font-size: 16px;
    color: var(--text-strong);
  }

  .applying {
    border-color: var(--accent-border);
    background: var(--accent-soft);
  }

  progress {
    width: 100%;
    accent-color: var(--accent);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 12px;
  }

  .card {
    padding: 16px;
    border-radius: 12px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .card.active {
    border-color: var(--accent-border);
    box-shadow: inset 0 0 0 1px var(--accent-border);
  }

  .card-head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
  }

  .card h3 {
    margin: 0;
    font-size: 16px;
    color: var(--text-strong);
    word-break: break-word;
  }

  .card-actions {
    margin-top: 10px;
  }

  .empty {
    margin: 40px auto;
    text-align: center;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
  }

  .empty h3 {
    margin: 0;
  }
</style>
