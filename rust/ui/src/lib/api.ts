// Typisierte Aufrufe der Rust-Befehle (src-tauri/src/commands.rs).
import { invoke } from "@tauri-apps/api/core";

export type ModState = "not_configured" | "disabled" | "enabled" | "broken" | "conflict";

export interface GameDefinition {
  id: string;
  name: string;
  short_name: string;
  importer: string;
  library_folder: string;
  gamebanana_game_id: number;
}

export interface GameConfig {
  library_path: string | null;
  active_mods_path: string | null;
  launcher_path: string | null;
  enabled: boolean;
}

export interface AppConfig {
  selected_game: string;
  games: Record<string, GameConfig>;
  language: "de" | "en";
  library_view_mode: "list" | "gallery";
  auto_check_updates: boolean;
  update_channel: "stable" | "prerelease";
  run_in_background: boolean;
  update_check_interval_minutes: number;
  skipped_update_version: string;
  [key: string]: unknown;
}

export interface Bootstrap {
  version: string;
  platform: string;
  config: AppConfig;
  games: GameDefinition[];
  config_dir: string;
  data_dir: string;
  autostart: boolean;
  updater_available: boolean;
}

export interface ModEntry {
  name: string;
  path: string;
  is_symlink: boolean;
  is_network: boolean;
  file_count: number;
  ini_file_count: number;
  total_size: number | null;
  modified_at: number | null;
  preview_path: string | null;
  error: string | null;
  characters: string[];
  mod_type: string;
  relative_path: string;
  state: ModState;
}

export interface LibraryScan {
  game_id: string;
  library_dir: string;
  active_mods_dir: string | null;
  is_network: boolean;
  duration_seconds: number;
  mods: ModEntry[];
}

export interface CommandError {
  kind: "error" | "not_configured" | "conflict" | "cancelled";
  message: string;
}

export interface BulkItemResult {
  path: string;
  state: ModState | null;
  error: CommandError | null;
}

export interface UpdateMeta {
  version: string;
  current_version: string;
  notes: string;
  date: string | null;
  release_url: string;
}

export type InstallProgress =
  | { event: "started"; total: number | null }
  | { event: "progress"; downloaded: number; total: number | null }
  | { event: "installing" };

export function errorMessage(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) return String((error as CommandError).message);
  return String(error);
}

export const api = {
  bootstrap: () => invoke<Bootstrap>("bootstrap"),
  saveConfig: (config: AppConfig) => invoke<AppConfig>("save_config", { config }),
  setAutostart: (enabled: boolean) => invoke<boolean>("set_autostart", { enabled }),
  scanLibrary: (gameId: string) => invoke<LibraryScan>("scan_library", { gameId }),
  cancelScan: () => invoke<void>("cancel_scan"),
  applyModAction: (gameId: string, paths: string[], action: "enable" | "disable" | "adopt") =>
    invoke<BulkItemResult[]>("apply_mod_action", { gameId, paths, action }),
  openPath: (path: string) => invoke<void>("open_path", { path }),
  revealPath: (path: string) => invoke<void>("reveal_path", { path }),
  launchGame: (gameId: string) => invoke<void>("launch_game", { gameId }),
  checkForUpdate: () => invoke<UpdateMeta | null>("check_for_update"),
  installUpdate: () => invoke<void>("install_update"),
  skipUpdate: (version: string) => invoke<void>("skip_update", { version }),
};
