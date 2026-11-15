<script lang="ts">
  import { onMount } from "svelte";
  import Modal from "./Modal.svelte";
  import { api, errorMessage, type IniKeyBinding, type ModEntry, type ModIniAnalysis } from "../lib/api";
  import { tr } from "../lib/i18n.svelte";

  let { gameId, mod, onclose }: { gameId: string; mod: ModEntry; onclose: () => void } = $props();

  let analysis = $state<ModIniAnalysis | null>(null);
  let failure = $state("");

  const KNOWN_TYPES = ["cycle", "toggle", "hold", "activate"];

  function typeLabel(type: string): string {
    return KNOWN_TYPES.includes(type) ? tr(`mod_info.type.${type}`) : tr("mod_info.type.unknown", { key_type: type });
  }

  function interpretation(name: string, values: string[]): string {
    if (values.length > 1) return tr("mod_info.assignment.multiple", { count: values.length });
    return name.startsWith("$") ? tr("mod_info.assignment.mod_variable") : tr("mod_info.assignment.3dmigoto_setting");
  }

  /** Zustände: Werte der Zyklus-Variablen mit Kommentar-Labels verbinden. */
  function states(binding: IniKeyBinding): { index: number; label: string; values: string }[] {
    const count = Math.max(0, ...binding.assignments.map((a) => a.values.length));
    if (count < 2) return [];
    return Array.from({ length: count }, (_, index) => ({
      index,
      label:
        binding.state_labels.find((label) => label.index === index)?.label ??
        tr("mod_info.html.technical_state", { index }),
      values: binding.assignments
        .filter((a) => a.values.length > index)
        .map((a) => `${a.name} = ${a.values[index]}`)
        .join(", "),
    }));
  }

  function fileName(path: string): string {
    return path.split(/[\\/]/).pop() ?? path;
  }

  onMount(async () => {
    try {
      analysis = await api.analyzeMod(gameId, mod.path);
    } catch (error) {
      failure = errorMessage(error);
    }
  });
</script>

<Modal eyebrow={tr("library.details.action.info")} title={tr("mod_info.title", { mod_name: mod.name })} width={820} {onclose}>
  {#if failure}
    <p class="error">{tr("mod_info.analysis_failed.title")}: {failure}</p>
  {:else if !analysis}
    <progress></progress>
  {:else}
    {#if analysis.warnings.length}
      <div class="note">
        <strong>{tr("mod_info.html.warnings")}</strong>
        {#each analysis.warnings as warning, index (index)}<div>{warning}</div>{/each}
      </div>
    {/if}
    {#if analysis.files.length === 0}
      <p class="muted">{tr("mod_info.html.no_control_ini")}</p>
    {:else}
      <p class="muted">{tr("mod_info.html.technical_note")}</p>
    {/if}

    {#each analysis.files as file (file.path)}
      <section class="file">
        <h3>{fileName(file.path)}</h3>
        <div class="meta">
          {#if file.namespace}<span><b>{tr("mod_info.html.namespace")}:</b> {file.namespace}</span>{/if}
          {#if file.merged_sources.length}
            <span><b>{tr("mod_info.html.merged_mods")}:</b> {file.merged_sources.join(", ")}</span>
          {/if}
        </div>
        {#each file.warnings as warning, index (index)}<p class="muted">{warning}</p>{/each}

        {#each file.key_bindings as binding (binding.section_name)}
          <div class="binding">
            <div class="binding-head">
              <span class="keys">
                {#if binding.keys.length}
                  {#each binding.keys as key (key)}<kbd>{key}</kbd>{/each}
                {:else}
                  <span class="muted">{tr("mod_info.html.no_key")}</span>
                {/if}
                {#if binding.back_keys.length}
                  <span class="muted">{tr("mod_info.html.reverse")}:</span>
                  {#each binding.back_keys as key (key)}<kbd>{key}</kbd>{/each}
                {/if}
              </span>
              <span class="section">[{binding.section_name}]</span>
            </div>
            <div class="type">{typeLabel(binding.key_type)}</div>
            {#if binding.condition}<div class="muted">{tr("mod_info.html.condition")}: <code>{binding.condition}</code></div>{/if}

            {#if states(binding).length}
              <table>
                <thead><tr><th>{tr("mod_info.html.state")}</th><th>{tr("mod_info.html.description")}</th><th>{tr("mod_info.html.set_values")}</th></tr></thead>
                <tbody>
                  {#each states(binding) as state (state.index)}
                    <tr><td>{state.index}</td><td>{state.label}</td><td><code>{state.values}</code></td></tr>
                  {/each}
                </tbody>
              </table>
            {:else if binding.assignments.length}
              <table>
                <thead><tr><th>{tr("mod_info.html.assignment")}</th><th>{tr("mod_info.html.values")}</th><th>{tr("mod_info.html.interpretation")}</th></tr></thead>
                <tbody>
                  {#each binding.assignments as assignment, index (index)}
                    <tr>
                      <td><code>{assignment.name}</code></td>
                      <td><code>{assignment.raw_value}</code></td>
                      <td>{interpretation(assignment.name, assignment.values)}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            {/if}
            {#if binding.run_commands.length}
              <div class="muted">{tr("mod_info.html.command_lists")}: <code>{binding.run_commands.join(", ")}</code></div>
            {/if}
            {#if binding.comments.length}
              <div class="comments">{binding.comments.join(" · ")}</div>
            {/if}
          </div>
        {/each}
      </section>
    {/each}
  {/if}

  {#snippet footer()}
    <button class="btn" onclick={() => api.revealPath(analysis?.root_path ?? mod.path)}>{tr("mod_info.open_folder")}</button>
    <button class="btn primary" onclick={onclose}>{tr("common.close")}</button>
  {/snippet}
</Modal>

<style>
  .muted {
    color: var(--text-muted);
    margin: 0;
  }

  .error {
    color: #ffc2cb;
  }

  .note {
    padding: 10px 12px;
    border-radius: 9px;
    border: 1px solid #5c4a20;
    background: var(--warning-soft);
  }

  .file {
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding: 12px 14px;
    background: var(--bg-input);
    border: 1px solid var(--border);
    border-radius: 10px;
  }

  h3 {
    margin: 0;
    font-size: 14px;
    color: var(--text-strong);
  }

  .meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    color: var(--text-muted);
  }

  .binding {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 10px 12px;
    border-radius: 9px;
    background: var(--bg-card);
    border: 1px solid var(--border);
  }

  .binding-head {
    display: flex;
    justify-content: space-between;
    gap: 10px;
    align-items: center;
  }

  .keys {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
  }

  kbd {
    font-family: inherit;
    font-weight: 800;
    padding: 2px 8px;
    border-radius: 6px;
    background: var(--accent-soft);
    border: 1px solid var(--accent-border);
    color: #e6e0ff;
  }

  .section {
    color: var(--text-faint);
    font-size: 11px;
  }

  .type {
    font-weight: 700;
  }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
  }

  th {
    text-align: left;
    color: var(--text-faint);
    padding: 4px 6px;
    border-bottom: 1px solid var(--border);
  }

  td {
    padding: 4px 6px;
    border-bottom: 1px solid #1d2229;
    vertical-align: top;
  }

  code {
    color: #c9bfff;
    word-break: break-word;
    user-select: text;
  }

  .comments {
    font-size: 12px;
    color: var(--text-muted);
    font-style: italic;
  }
</style>
