<script lang="ts">
  import { onMount } from "svelte";
  import { app, type Page } from "./lib/store.svelte";
  import { tr } from "./lib/i18n.svelte";
  import { errorMessage } from "./lib/api";
  import LibraryPage from "./pages/LibraryPage.svelte";
  import SettingsPage from "./pages/SettingsPage.svelte";
  import NotPortedPage from "./pages/NotPortedPage.svelte";
  import UpdateDialog from "./components/UpdateDialog.svelte";
  import libraryIcon from "@assets/icons/navigation/library.svg?raw";
  import gamebananaIcon from "@assets/icons/navigation/gamebanana.svg?raw";
  import profilesIcon from "@assets/icons/navigation/profiles.svg?raw";
  import conflictsIcon from "@assets/icons/navigation/conflicts.svg?raw";
  import settingsIcon from "@assets/icons/navigation/settings.svg?raw";

  const gameIcons = import.meta.glob<string>("@assets/icons/games/*.png", {
    eager: true,
    import: "default",
    query: "?url",
  });

  function gameIcon(id: string): string | undefined {
    return Object.entries(gameIcons).find(([path]) => path.endsWith(`/${id}.png`))?.[1];
  }

  const navigation: { page: Page; key: string; icon: string }[] = [
    { page: "library", key: "navigation.library", icon: libraryIcon },
    { page: "gamebanana", key: "navigation.gamebanana", icon: gamebananaIcon },
    { page: "profiles", key: "navigation.profiles", icon: profilesIcon },
    { page: "conflicts", key: "navigation.conflicts", icon: conflictsIcon },
  ];

  let startupError = $state<string | null>(null);

  onMount(() => {
    app.init().catch((error) => (startupError = errorMessage(error)));
  });
</script>

{#if startupError}
  <div class="startup-error">{startupError}</div>
{:else if app.boot && app.config && app.game}
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">GMM</div>
      <div class="eyebrow sidebar-title">XXMI</div>
      <nav class="games">
        {#each app.boot.games as game (game.id)}
          <button
            class="game-button"
            class:active={game.id === app.config.selected_game}
            title={game.name}
            onclick={() => app.selectGame(game.id)}
          >
            {#if gameIcon(game.id)}
              <img src={gameIcon(game.id)} alt={game.short_name} />
            {:else}
              <span>{game.short_name.slice(0, 2)}</span>
            {/if}
          </button>
        {/each}
      </nav>
      <div class="version">v{app.boot.version}</div>
    </aside>

    <div class="workspace">
      <header class="topbar">
        <div class="current-game">
          {#if gameIcon(app.game.id)}<img src={gameIcon(app.game.id)} alt="" />{/if}
          <div>
            <div class="game-name">{app.game.name}</div>
            <div class="importer">{app.game.importer}</div>
          </div>
        </div>

        <nav class="top-nav">
          {#each navigation as item (item.page)}
            <button class:active={app.page === item.page} onclick={() => (app.page = item.page)}>
              <span class="icon">{@html item.icon}</span>
              {tr(item.key)}
            </button>
          {/each}
        </nav>

        <div class="spacer"></div>

        {#if app.update}
          <button class="update-pill" onclick={() => (app.updateDialogOpen = true)}>
            {tr("rust.updates.available_banner", { version: app.update.version })}
          </button>
        {/if}

        <button class="settings-button" class:active={app.page === "settings"} onclick={() => (app.page = "settings")}>
          <span class="icon">{@html settingsIcon}</span>
          {tr("navigation.settings")}
        </button>
      </header>

      <main class="content">
        {#if app.page === "library"}
          {#key app.game.id}
            <LibraryPage game={app.game} />
          {/key}
        {:else if app.page === "settings"}
          <SettingsPage />
        {:else}
          <NotPortedPage titleKey={`navigation.${app.page}`} />
        {/if}
      </main>
    </div>
  </div>

  {#if app.updateDialogOpen && app.update}
    <UpdateDialog update={app.update} />
  {/if}

  {#if app.toast}
    <div class="toast" class:error={app.toast.error}>{app.toast.text}</div>
  {/if}
{/if}

<style>
  .shell {
    display: flex;
    height: 100%;
  }

  .sidebar {
    width: 76px;
    flex: none;
    background: var(--bg-elevated);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 16px 0 12px;
    gap: 10px;
  }

  .brand {
    color: var(--text-strong);
    font-size: 18px;
    font-weight: 900;
    letter-spacing: 1px;
  }

  .sidebar-title {
    font-size: 9px;
  }

  .games {
    display: flex;
    flex-direction: column;
    gap: 8px;
    flex: 1;
    overflow-y: auto;
  }

  .game-button {
    width: 52px;
    height: 52px;
    padding: 7px;
    border-radius: 13px;
    border: 1px solid transparent;
    background: transparent;
    display: grid;
    place-items: center;
  }

  .game-button:hover {
    background: var(--bg-hover);
    border-color: #303843;
  }

  .game-button.active {
    background: var(--accent-soft);
    border-color: #7864e8;
  }

  .game-button img {
    width: 36px;
    height: 36px;
    border-radius: 9px;
    object-fit: cover;
  }

  .version {
    color: var(--text-faint);
    font-size: 10px;
  }

  .workspace {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
  }

  .topbar {
    height: 70px;
    flex: none;
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 0 18px;
    background: var(--bg-elevated);
    border-bottom: 1px solid var(--border);
  }

  .current-game {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 7px 14px 7px 8px;
    background: var(--bg-card);
    border: 1px solid #2c333e;
    border-radius: var(--radius);
    min-width: 170px;
  }

  .current-game img {
    width: 30px;
    height: 30px;
    border-radius: 7px;
  }

  .game-name {
    color: #f4f5f7;
    font-weight: 850;
  }

  .importer {
    color: #7f8997;
    font-size: 11px;
  }

  .top-nav {
    display: flex;
    gap: 4px;
    padding: 4px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  .top-nav button,
  .settings-button {
    display: flex;
    align-items: center;
    gap: 7px;
    height: 40px;
    padding: 0 12px;
    background: transparent;
    color: var(--text-muted);
    border: 1px solid transparent;
    border-radius: 7px;
    font-weight: 750;
  }

  .top-nav button:hover {
    background: var(--bg-hover);
    color: #e8ebef;
  }

  .top-nav button.active,
  .settings-button.active {
    background: var(--accent-soft);
    color: #fff;
    border-color: var(--accent-border);
  }

  .settings-button {
    background: #1b2027;
    border-color: var(--border-strong);
    color: #a7afbb;
    border-radius: 8px;
  }

  .icon {
    display: inline-flex;
  }

  .icon :global(svg) {
    width: 17px;
    height: 17px;
  }

  .spacer {
    flex: 1;
  }

  .update-pill {
    border: 1px solid var(--accent-border);
    background: var(--accent-soft);
    color: #d9d2ff;
    border-radius: 999px;
    padding: 6px 12px;
    font-weight: 750;
  }

  .content {
    flex: 1;
    min-height: 0;
  }

  .toast {
    position: fixed;
    right: 20px;
    bottom: 20px;
    max-width: 420px;
    padding: 12px 16px;
    background: var(--bg-card);
    border: 1px solid var(--border-strong);
    border-radius: 10px;
    box-shadow: 0 10px 30px rgb(0 0 0 / 0.4);
    white-space: pre-line;
    z-index: 50;
  }

  .toast.error {
    border-color: #6b2a36;
    color: #ffc2cb;
  }

  .startup-error {
    padding: 40px;
    color: #ffc2cb;
    white-space: pre-wrap;
  }

  @media (max-width: 1000px) {
    .current-game {
      display: none;
    }
  }
</style>
