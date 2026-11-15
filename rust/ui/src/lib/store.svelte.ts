// Globaler App-Zustand (Svelte-5-Runes).
import { listen } from "@tauri-apps/api/event";
import { api, errorMessage, type AppConfig, type Bootstrap, type InstallProgress, type UpdateMeta } from "./api";
import { setLanguage, tr } from "./i18n.svelte";

export type Page = "library" | "gamebanana" | "profiles" | "conflicts" | "icons" | "settings";

export type UpdatePhase =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "downloading"; percent: number | null }
  | { kind: "installing" }
  | { kind: "error"; message: string };

class AppStore {
  boot = $state<Bootstrap | null>(null);
  config = $state<AppConfig | null>(null);
  page = $state<Page>("library");
  toast = $state<{ text: string; error: boolean } | null>(null);

  update = $state<UpdateMeta | null>(null);
  updateDialogOpen = $state(false);
  updatePhase = $state<UpdatePhase>({ kind: "idle" });

  #toastTimer: ReturnType<typeof setTimeout> | undefined;

  get game() {
    const boot = this.boot;
    const config = this.config;
    if (!boot || !config) return null;
    return boot.games.find((game) => game.id === config.selected_game) ?? boot.games[0];
  }

  async init(): Promise<void> {
    const boot = await api.bootstrap();
    this.boot = boot;
    this.config = boot.config;
    setLanguage(boot.config.language);

    await listen<UpdateMeta>("update-available", (event) => {
      this.update = event.payload;
    });
    await listen("request-update-check", () => void this.checkForUpdate(true));
    await listen("request-update-dialog", () => {
      if (this.update) this.updateDialogOpen = true;
      else void this.checkForUpdate(true);
    });
    await listen<InstallProgress>("update-progress", (event) => {
      const progress = event.payload;
      if (progress.event === "installing") this.updatePhase = { kind: "installing" };
      else if (progress.event === "started") this.updatePhase = { kind: "downloading", percent: null };
      else {
        const percent = progress.total ? Math.min(100, (progress.downloaded / progress.total) * 100) : null;
        this.updatePhase = { kind: "downloading", percent };
      }
    });
  }

  showToast(text: string, error = false): void {
    this.toast = { text, error };
    clearTimeout(this.#toastTimer);
    this.#toastTimer = setTimeout(() => (this.toast = null), error ? 7000 : 3500);
  }

  async saveConfig(change: (config: AppConfig) => void, announce = false): Promise<void> {
    if (!this.config) return;
    const next = $state.snapshot(this.config) as AppConfig;
    change(next);
    try {
      this.config = await api.saveConfig(next);
      setLanguage(this.config.language);
      if (announce) this.showToast(tr("rust.settings.saved"));
    } catch (error) {
      this.showToast(errorMessage(error), true);
    }
  }

  async selectGame(gameId: string): Promise<void> {
    await this.saveConfig((config) => (config.selected_game = gameId));
  }

  async checkForUpdate(manual: boolean): Promise<void> {
    if (this.updatePhase.kind === "checking" || this.updatePhase.kind === "downloading") return;
    this.updatePhase = { kind: "checking" };
    try {
      const update = await api.checkForUpdate();
      this.updatePhase = { kind: "idle" };
      this.update = update;
      if (update) {
        if (manual || this.config?.skipped_update_version !== update.version) this.updateDialogOpen = true;
      } else if (manual) {
        this.showToast(tr("rust.updates.up_to_date", { version: this.boot?.version ?? "" }));
      }
    } catch (error) {
      this.updatePhase = { kind: "idle" };
      if (manual) this.showToast(`${tr("updates.check.failed")}\n${errorMessage(error)}`, true);
    }
  }

  async installUpdate(): Promise<void> {
    this.updatePhase = { kind: "downloading", percent: null };
    try {
      await api.installUpdate();
    } catch (error) {
      this.updatePhase = { kind: "error", message: errorMessage(error) };
    }
  }

  async skipUpdate(): Promise<void> {
    if (!this.update) return;
    await api.skipUpdate(this.update.version);
    if (this.config) this.config.skipped_update_version = this.update.version;
    this.update = null;
    this.updateDialogOpen = false;
  }
}

export const app = new AppStore();
