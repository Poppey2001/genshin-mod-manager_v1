<script lang="ts">
  import { onMount } from "svelte";
  import { api, errorMessage, type ConflictItem, type GameDefinition } from "../lib/api";
  import { app } from "../lib/store.svelte";
  import { tr } from "../lib/i18n.svelte";
  import ImportDialog from "../components/ImportDialog.svelte";

  let { game }: { game: GameDefinition } = $props();

  let items = $state<ConflictItem[] | null>(null);
  let loading = $state(false);
  let failure = $state("");
  let busy = $state(false);
  let importPath = $state<string | null>(null);

  const TYPE_KEYS: Record<ConflictItem["kind"], string> = {
    library: "library",
    unmanaged_active: "unmanaged",
    invalid_marker: "invalid_marker",
    orphaned_managed: "orphaned",
  };

  async function refresh(): Promise<void> {
    loading = true;
    failure = "";
    try {
      items = await api.scanConflicts(game.id);
      app.conflictCount = items.length;
    } catch (error) {
      failure = errorMessage(error);
    } finally {
      loading = false;
    }
  }

  async function adopt(item: ConflictItem): Promise<void> {
    if (!item.library_mod_path) return;
    busy = true;
    try {
      const [result] = await api.applyModAction(game.id, [item.library_mod_path], "adopt");
      if (result?.error) app.showToast(result.error.message, true);
      await refresh();
    } finally {
      busy = false;
    }
  }

  onMount(refresh);
</script>

<div class="conflicts">
  {#if importPath}
    <ImportDialog
      gameId={game.id}
      paths={[importPath]}
      characters={[]}
      modTypes={[]}
      onclose={(imported) => {
        importPath = null;
        if (imported) void refresh();
      }}
    />
  {/if}

  <header>
    <div>
      <h1>{tr("conflicts.title")}</h1>
      <p class="muted">{tr("conflicts.description")}</p>
    </div>
    <button class="btn primary" disabled={loading} onclick={refresh}>{tr("conflicts.refresh")}</button>
  </header>

  {#if items}
    <div class="summary" class:clean={items.length === 0}>
      <strong>{items.length ? tr("conflicts.summary.attention_title") : tr("conflicts.summary.clean_title")}</strong>
      <span>
        {items.length
          ? `${tr("conflicts.count", { count: items.length })} · ${tr("conflicts.summary.attention_description")}`
          : tr("conflicts.summary.clean_description")}
      </span>
    </div>
  {/if}

  {#if failure}
    <p class="error">{failure}</p>
  {:else if loading && !items}
    <progress></progress>
  {:else if items}
    <div class="list">
      {#each items as item (item.path)}
        <article class="card {item.kind}">
          <div class="head">
            <span class="badge {item.kind === 'library' ? 'conflict' : item.kind === 'unmanaged_active' ? 'disabled' : 'broken'}">
              {tr(`conflicts.type.${TYPE_KEYS[item.kind]}`)}
            </span>
            <h3>{item.title}</h3>
          </div>
          {#if item.kind !== "library"}
            <!-- Der Bibliothekstext verweist auf die (noch nicht portierte) Duplikatprüfung. -->
            <p class="message">{tr(`conflicts.message.${TYPE_KEYS[item.kind]}`)}</p>
          {/if}
          <p class="detail">{item.message}</p>
          <code>{item.path}</code>
          <div class="actions">
            {#if item.can_adopt}
              <button class="btn primary" disabled={busy} title={tr("library.details.action.adopt_tooltip")} onclick={() => adopt(item)}>
                {tr("conflicts.action.adopt")}
              </button>
            {/if}
            {#if item.kind === "unmanaged_active"}
              <button class="btn" onclick={() => (importPath = item.path)}>{tr("conflicts.action.copy_to_library")}</button>
            {/if}
            <button class="btn" onclick={() => api.revealPath(item.path)}>{tr("conflicts.action.open")}</button>
          </div>
        </article>
      {:else}
        <p class="muted empty">{tr("conflicts.empty")}</p>
      {/each}
    </div>
  {/if}
</div>

<style>
  .conflicts {
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

  .summary {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 12px 16px;
    border-radius: 10px;
    border: 1px solid #5c4a20;
    background: var(--warning-soft);
    color: #ffe1ad;
  }

  .summary.clean {
    border-color: #1f5a41;
    background: var(--success-soft);
    color: #b9f3d6;
  }

  .list {
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-left: 3px solid var(--warning);
    border-radius: 10px;
    padding: 14px 16px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .card.unmanaged_active {
    border-left-color: var(--text-muted);
  }
  .card.invalid_marker,
  .card.orphaned_managed {
    border-left-color: var(--danger);
  }

  .head {
    display: flex;
    gap: 10px;
    align-items: center;
  }

  h3 {
    margin: 0;
    font-size: 15px;
    color: var(--text-strong);
  }

  .message {
    margin: 0;
  }

  .detail {
    margin: 0;
    color: var(--text-muted);
    font-size: 12px;
  }

  code {
    color: #c9bfff;
    font-size: 12px;
    word-break: break-all;
    user-select: text;
  }

  .actions {
    display: flex;
    gap: 8px;
    margin-top: 4px;
  }

  .error {
    color: #ffc2cb;
  }

  .empty {
    text-align: center;
    padding: 30px;
  }

  progress {
    width: 100%;
    accent-color: var(--accent);
  }
</style>
