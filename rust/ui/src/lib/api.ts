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
  selected_profile: string;
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

export interface ArchiveIssue {
  severity: "warning" | "block";
  code: string;
  message: string;
  member: string | null;
}

export interface SecurityReport {
  source: string;
  entry_count: number;
  total_uncompressed: number;
  issues: ArchiveIssue[];
  warning_files: string[];
  blocked: boolean;
}

export interface ImportCheck {
  path: string;
  is_directory: boolean;
  supported: boolean;
  report: SecurityReport | null;
  error: string | null;
}

export interface ImportOptions {
  character: string | null;
  mod_type: string | null;
  conflict_policy: "rename" | "skip";
}

export interface ImportItemResult {
  source: string;
  destination: string | null;
  status: "imported" | "skipped" | "failed";
  message: string;
  warnings: string[];
}

export interface ImportBatchResult {
  items: ImportItemResult[];
  duration_seconds: number;
  imported_count: number;
  skipped_count: number;
  failed_count: number;
}

export interface IniKeyBinding {
  section_name: string;
  keys: string[];
  back_keys: string[];
  key_type: string;
  condition: string | null;
  assignments: { name: string; raw_value: string; values: string[] }[];
  run_commands: string[];
  comments: string[];
  state_labels: { index: number; label: string }[];
  smart: string | null;
  wrap: string | null;
}

export interface ModIniAnalysis {
  root_path: string;
  files: {
    path: string;
    namespace: string | null;
    merged_sources: string[];
    key_bindings: IniKeyBinding[];
    warnings: string[];
  }[];
  warnings: string[];
  has_controls: boolean;
}

export interface ConflictItem {
  kind: "library" | "unmanaged_active" | "invalid_marker" | "orphaned_managed";
  title: string;
  path: string;
  message: string;
  library_mod_path: string | null;
  can_adopt: boolean;
}

export interface ModProfile {
  schema_version: number;
  name: string;
  game_id: string;
  created_at: string;
  updated_at: string;
  mods: { relative_path: string; name: string; enabled: boolean }[];
}

export interface ProfileApplyResult {
  profile_name: string;
  items: { relative_path: string; name: string; desired_enabled: boolean; status: string; message: string }[];
  cancelled: boolean;
  changed_count: number;
  unchanged_count: number;
  missing_count: number;
  blocked_count: number;
  failed_count: number;
}

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
  checkImportSources: (paths: string[]) => invoke<ImportCheck[]>("check_import_sources", { paths }),
  importMods: (gameId: string, paths: string[], options: ImportOptions) =>
    invoke<ImportBatchResult>("import_mods", { gameId, paths, options }),
  cancelImport: () => invoke<void>("cancel_import"),
  analyzeMod: (gameId: string, path: string) => invoke<ModIniAnalysis>("analyze_mod", { gameId, path }),
  scanConflicts: (gameId: string) => invoke<ConflictItem[]>("scan_conflicts", { gameId }),
  listProfiles: (gameId: string) => invoke<ModProfile[]>("list_profiles", { gameId }),
  saveProfile: (gameId: string, name: string, overwrite: boolean) =>
    invoke<ModProfile>("save_profile", { gameId, name, overwrite }),
  renameProfile: (gameId: string, oldName: string, newName: string) =>
    invoke<ModProfile>("rename_profile", { gameId, oldName, newName }),
  deleteProfile: (gameId: string, name: string) => invoke<void>("delete_profile", { gameId, name }),
  applyProfile: (gameId: string, name: string) => invoke<ProfileApplyResult>("apply_profile", { gameId, name }),
};
