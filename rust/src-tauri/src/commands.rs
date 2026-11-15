//! Befehle, die das Frontend über `invoke` aufruft.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use gmm_core::{all_games, app_dirs, AppConfig, GameDefinition, GameScope, ModInfo, ModManager, ModScanner, ModState};
use serde::Serialize;
use serde_json::Value;
use tauri::{AppHandle, Emitter, Manager, State};
use tauri_plugin_autostart::ManagerExt as _;
use tauri_plugin_opener::OpenerExt;

use crate::state::AppState;
use crate::updates::{self, UpdateMeta};

/// Fehler für das Frontend: Art + Text.
#[derive(Debug, Serialize)]
pub struct CommandError {
    pub kind: &'static str,
    pub message: String,
}

impl From<gmm_core::Error> for CommandError {
    fn from(error: gmm_core::Error) -> Self {
        Self { kind: error.kind(), message: error.to_string() }
    }
}

impl From<String> for CommandError {
    fn from(message: String) -> Self {
        Self { kind: "error", message }
    }
}

type CommandResult<T> = Result<T, CommandError>;

#[derive(Serialize)]
pub struct Bootstrap {
    pub version: String,
    pub platform: &'static str,
    pub config: Value,
    pub games: &'static [GameDefinition],
    pub config_dir: PathBuf,
    pub data_dir: PathBuf,
    pub autostart: bool,
    pub updater_available: bool,
}

#[tauri::command]
pub fn bootstrap(app: AppHandle, state: State<'_, AppState>) -> Bootstrap {
    let dirs = app_dirs();
    Bootstrap {
        version: app.package_info().version.to_string(),
        platform: std::env::consts::OS,
        config: state.config().to_value(),
        games: all_games(),
        config_dir: dirs.config_dir.clone(),
        data_dir: dirs.data_dir.clone(),
        autostart: app.autolaunch().is_enabled().unwrap_or(false),
        updater_available: cfg!(any(windows, target_os = "linux")),
    }
}

/// Komplette Konfiguration speichern (Format wie `config.json`).
#[tauri::command]
pub fn save_config(app: AppHandle, state: State<'_, AppState>, config: Value) -> CommandResult<Value> {
    let parsed = AppConfig::from_value(&config, app_dirs());
    let language_changed = state.config().language != parsed.language;
    let saved = state.update_config(|current| *current = parsed)?;
    if language_changed {
        crate::tray::refresh(&app);
    }
    Ok(saved.to_value())
}

#[tauri::command]
pub fn set_autostart(app: AppHandle, enabled: bool) -> CommandResult<bool> {
    let launcher = app.autolaunch();
    let result = if enabled { launcher.enable() } else { launcher.disable() };
    result.map_err(|error| CommandError::from(error.to_string()))?;
    Ok(launcher.is_enabled().unwrap_or(false))
}

#[derive(Serialize, Clone)]
pub struct ModEntry {
    #[serde(flatten)]
    pub info: ModInfo,
    pub state: ModState,
}

#[derive(Serialize, Clone)]
pub struct LibraryScan {
    pub game_id: String,
    pub library_dir: PathBuf,
    pub active_mods_dir: Option<PathBuf>,
    pub is_network: bool,
    pub duration_seconds: f64,
    pub mods: Vec<ModEntry>,
}

#[derive(Serialize, Clone)]
struct ScanProgress {
    current: usize,
    total: usize,
    name: String,
}

fn scope_for(state: &AppState, game_id: &str) -> GameScope {
    GameScope::from_config(&state.config(), game_id, app_dirs())
}

#[tauri::command]
pub async fn scan_library(app: AppHandle, game_id: String) -> CommandResult<LibraryScan> {
    let state = app.state::<AppState>();
    let cancel = Arc::new(AtomicBool::new(false));
    if let Some(previous) = state.scan_cancel.lock().expect("scan lock").replace(cancel.clone()) {
        previous.store(true, Ordering::Relaxed);
    }
    let scope = scope_for(&state, &game_id);
    // Vorschaubilder der Bibliothek für das Frontend freigeben.
    let _ = app.asset_protocol_scope().allow_directory(&scope.library_dir, true);

    let emitter = app.clone();
    let task_cancel = cancel.clone();
    let result = tauri::async_runtime::spawn_blocking(move || -> gmm_core::Result<LibraryScan> {
        std::fs::create_dir_all(&scope.library_dir).ok();
        let scanner = ModScanner::new().with_cancel(&task_cancel);
        let progress = |current: usize, total: usize, name: &str| {
            let _ = emitter.emit("scan-progress", ScanProgress { current, total, name: name.to_string() });
        };
        let result = scanner.scan(&scope.library_dir, Some(&progress))?;
        let manager = ModManager::new(scope.clone());
        let mods =
            result.mods.into_iter().map(|info| ModEntry { state: manager.get_state(&info.path), info }).collect();
        Ok(LibraryScan {
            game_id: scope.game.id.to_string(),
            library_dir: scope.library_dir,
            active_mods_dir: scope.active_mods_dir,
            is_network: result.is_network,
            duration_seconds: result.duration_seconds,
            mods,
        })
    })
    .await
    .map_err(|error| CommandError::from(error.to_string()))?;

    let mut guard = state.scan_cancel.lock().expect("scan lock");
    if guard.as_ref().is_some_and(|current| Arc::ptr_eq(current, &cancel)) {
        *guard = None;
    }
    Ok(result?)
}

#[tauri::command]
pub fn cancel_scan(state: State<'_, AppState>) {
    if let Some(flag) = state.scan_cancel.lock().expect("scan lock").as_ref() {
        flag.store(true, Ordering::Relaxed);
    }
}

#[derive(Serialize)]
pub struct BulkItemResult {
    pub path: PathBuf,
    pub state: Option<ModState>,
    pub error: Option<CommandError>,
}

/// Aktiviert/deaktiviert/übernimmt einen oder mehrere Mods.
/// `action`: "enable" | "disable" | "adopt"
#[tauri::command]
pub async fn apply_mod_action(
    app: AppHandle,
    game_id: String,
    paths: Vec<PathBuf>,
    action: String,
) -> CommandResult<Vec<BulkItemResult>> {
    let scope = scope_for(&app.state::<AppState>(), &game_id);
    tauri::async_runtime::spawn_blocking(move || {
        let mut manager = ModManager::new(scope);
        paths
            .into_iter()
            .map(|path| {
                let outcome = match action.as_str() {
                    "enable" => manager.enable(&path).map(|_| ()),
                    "disable" => manager.disable(&path).map(|_| ()),
                    "adopt" => manager.adopt_existing(&path).map(|_| ()),
                    other => Err(gmm_core::Error::Message(format!("Unbekannte Aktion: {other}"))),
                };
                let state = manager.get_state(&path);
                BulkItemResult { path, state: Some(state), error: outcome.err().map(CommandError::from) }
            })
            .collect()
    })
    .await
    .map_err(|error| CommandError::from(error.to_string()))
}

#[tauri::command]
pub fn open_path(app: AppHandle, path: PathBuf) -> CommandResult<()> {
    app.opener().open_path(path.to_string_lossy(), None::<&str>).map_err(|error| CommandError::from(error.to_string()))
}

#[tauri::command]
pub fn reveal_path(app: AppHandle, path: PathBuf) -> CommandResult<()> {
    app.opener().reveal_item_in_dir(&path).map_err(|error| CommandError::from(error.to_string()))
}

#[tauri::command]
pub fn launch_game(app: AppHandle, state: State<'_, AppState>, game_id: String) -> CommandResult<()> {
    let launcher = state
        .config()
        .launcher_file_for(&game_id)
        .ok_or_else(|| CommandError { kind: "not_configured", message: "Kein Launcher eingestellt.".into() })?;
    if !Path::new(&launcher).is_file() {
        return Err(format!("Launcher nicht gefunden: {}", launcher.display()).into());
    }
    app.opener()
        .open_path(launcher.to_string_lossy(), None::<&str>)
        .map_err(|error| CommandError::from(error.to_string()))
}

// ---------------------------------------------------------------------------
// Updates
// ---------------------------------------------------------------------------

#[tauri::command]
pub async fn check_for_update(app: AppHandle) -> CommandResult<Option<UpdateMeta>> {
    let state = app.state::<AppState>();
    if state.update_busy.swap(true, Ordering::SeqCst) {
        return Err("Es läuft bereits eine Updateprüfung.".to_string().into());
    }
    let result = updates::check(&app).await;
    state.update_busy.store(false, Ordering::SeqCst);
    let meta = result?;
    crate::tray::set_update_available(&app, meta.as_ref().map(|m| m.version.as_str()));
    Ok(meta)
}

#[tauri::command]
pub async fn install_update(app: AppHandle) -> CommandResult<()> {
    Ok(updates::install(&app).await?)
}

#[tauri::command]
pub fn skip_update(app: AppHandle, state: State<'_, AppState>, version: String) -> CommandResult<()> {
    state.update_config(|config| config.skipped_update_version = version)?;
    state.pending_update.lock().expect("update lock").take();
    crate::tray::set_update_available(&app, None);
    Ok(())
}
