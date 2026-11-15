<script lang="ts">
  import { tr } from "../lib/i18n.svelte";

  let { titleKey }: { titleKey: string } = $props();
</script>

<section class="placeholder">
  <div class="eyebrow">{tr(titleKey)}</div>
  <h2>{tr("rust.nav.not_ported_title")}</h2>
  <p>{tr("rust.nav.not_ported_body")}</p>
</section>

<style>
  .placeholder {
    height: 100%;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 6px;
    text-align: center;
    padding: 40px;
  }

  h2 {
    margin: 4px 0;
    color: var(--text-strong);
  }

  p {
    max-width: 460px;
    color: var(--text-muted);
    line-height: 1.5;
  }
</style>
