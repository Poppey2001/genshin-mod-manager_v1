//! Aktivieren / Deaktivieren von Mods (Port von `app/services/mod_manager.py`).
//!
//! Strategie (unverändert zur Python-Version):
//! * Erste Aktivierung kopiert den Mod aus der Bibliothek in den aktiven
//!   Mods-Ordner und schreibt eine Markierung `.gmm-managed.json`.
//! * Deaktivieren benennt nur in `DISABLED <Name>` um, Aktivieren benennt zurück.
//! * Fremde Ordner (ohne passende Markierung) werden nie verändert.

use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::{to_pretty_json, AppConfig};
use crate::games::{get_game, GameDefinition, GENSHIN_IMPACT};
use crate::paths::{absolute, app_dirs, normalized_path_key, path_exists, paths_equal, paths_overlap, AppDirs};
use crate::{Error, Result};

pub const MANAGER_MARKER: &str = ".gmm-managed.json";
pub const NEXT_MANAGER_MARKER: &str = ".xxmimm-managed.json";
pub const MANAGER_ID: &str = "xxmi-mod-manager";
pub const LEGACY_MANAGER_ID: &str = "genshin-mod-manager";
pub const DISABLED_PREFIX: &str = "DISABLED ";
pub const DISABLED_PREFIX_ALIASES: &[&str] = &["DISABLED ", "DISABLED_", "DISABLED-"];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ModState {
    NotConfigured,
    Disabled,
    Enabled,
    Broken,
    Conflict,
}

impl ModState {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::NotConfigured => "not_configured",
            Self::Disabled => "disabled",
            Self::Enabled => "enabled",
            Self::Broken => "broken",
            Self::Conflict => "conflict",
        }
    }
}

#[derive(Debug, Serialize)]
struct Marker<'a> {
    manager: &'a str,
    game_id: &'a str,
    importer: &'a str,
    source: String,
    source_key: String,
    relative_path: String,
    created_at: String,
}

/// Spielbezogener Kontext: Bibliothek + aktiver Mods-Ordner.
#[derive(Debug, Clone)]
pub struct GameScope {
    pub game: &'static GameDefinition,
    pub library_dir: PathBuf,
    pub active_mods_dir: Option<PathBuf>,
}

impl GameScope {
    pub fn from_config(config: &AppConfig, game_id: &str, dirs: &AppDirs) -> Self {
        let game = get_game(game_id);
        Self {
            game,
            library_dir: config.mod_library_directory_for(game.id, dirs),
            active_mods_dir: config.active_mods_directory_for(game.id),
        }
    }
}

pub struct ModManager {
    scope: GameScope,
    last_enable_mode: Option<&'static str>,
}

impl ModManager {
    pub fn new(scope: GameScope) -> Self {
        Self { scope, last_enable_mode: None }
    }

    pub fn for_config(config: &AppConfig) -> Self {
        Self::new(GameScope::from_config(config, &config.selected_game, app_dirs()))
    }

    pub fn game_id(&self) -> &'static str {
        self.scope.game.id
    }

    /// Diagnose: wie die letzte `enable()`-Anfrage behandelt wurde.
    pub fn last_enable_mode(&self) -> Option<&'static str> {
        self.last_enable_mode
    }

    // ------------------------------------------------------------------
    // Öffentliche API
    // ------------------------------------------------------------------

    pub fn get_state(&self, mod_path: &Path) -> ModState {
        let Ok((source, relative)) = self.source_and_relative(mod_path, false) else {
            return ModState::Conflict;
        };
        let active_root = match self.active_root(false) {
            Ok(root) => root,
            Err(Error::NotConfigured(_)) => return ModState::NotConfigured,
            Err(_) => return ModState::Conflict,
        };
        let Ok((enabled, disabled)) = self.resolve_destination_paths(&active_root, &source, &relative) else {
            return ModState::Conflict;
        };
        let enabled_exists = path_exists(&enabled);
        let disabled_exists = path_exists(&disabled);
        if enabled_exists && disabled_exists {
            return ModState::Conflict;
        }
        if is_symlink(&enabled) {
            if !enabled.exists() {
                return ModState::Broken;
            }
            return if symlink_points_to(&enabled, &source) { ModState::Enabled } else { ModState::Conflict };
        }
        if is_symlink(&disabled) {
            return ModState::Conflict;
        }
        if enabled_exists {
            return if self.marker_matches(&enabled, &source) { ModState::Enabled } else { ModState::Conflict };
        }
        if disabled_exists {
            return if self.marker_matches(&disabled, &source) { ModState::Disabled } else { ModState::Conflict };
        }
        let managed = self.find_managed_destinations(&active_root, &source);
        match managed.as_slice() {
            [] => ModState::Disabled,
            [one] if is_disabled_destination(one) => ModState::Disabled,
            [_] => ModState::Enabled,
            _ => ModState::Conflict,
        }
    }

    /// Übernimmt einen bereits vorhandenen Ordner, ohne Dateien zu überschreiben.
    pub fn adopt_existing(&self, mod_path: &Path) -> Result<ModState> {
        let (source, relative) = self.source_and_relative(mod_path, true)?;
        let active_root = self.active_root(true)?;
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;
        let enabled_exists = path_exists(&enabled);
        let disabled_exists = path_exists(&disabled);
        if enabled_exists && disabled_exists {
            return Err(Error::Conflict(format!(
                "Der Konflikt kann nicht automatisch übernommen werden, weil eine aktive und eine \
                 deaktivierte Version existieren.\n\nAktiv:\n{}\n\nDeaktiviert:\n{}",
                enabled.display(),
                disabled.display()
            )));
        }
        if !enabled_exists && !disabled_exists {
            return Err(Error::Conflict(
                "Es wurde kein vorhandener Zielordner gefunden, der übernommen werden könnte.".into(),
            ));
        }
        let (destination, state) =
            if enabled_exists { (enabled, ModState::Enabled) } else { (disabled, ModState::Disabled) };
        if is_symlink(&destination) {
            return Err(Error::Conflict(format!(
                "Symbolische Verknüpfungen können nicht als bestehende Mod-Kopie übernommen werden.\n\nPfad: {}",
                destination.display()
            )));
        }
        if !destination.is_dir() {
            return Err(Error::Conflict(format!(
                "Das vorhandene Ziel ist kein Ordner.\n\nPfad: {}",
                destination.display()
            )));
        }
        if self.marker_matches(&destination, &source) {
            return Ok(state);
        }
        if has_any_manager_marker(&destination) {
            return Err(Error::Conflict(format!(
                "Der Ordner besitzt bereits eine Manager-Markierung, die zu einem anderen Mod oder \
                 Spiel gehört.\n\nPfad: {}",
                destination.display()
            )));
        }
        self.write_marker(&destination, &source, &relative).map_err(|error| {
            Error::Message(format!(
                "Der vorhandene Mod-Ordner konnte nicht übernommen werden.\n\nPfad: {}\n\n{error}",
                destination.display()
            ))
        })?;
        Ok(state)
    }

    /// Aktiviert einen Mod. Vorhandene Kopien werden nur umbenannt;
    /// kopiert wird ausschließlich bei der allerersten Aktivierung.
    pub fn enable(&mut self, mod_path: &Path) -> Result<PathBuf> {
        self.last_enable_mode = None;
        let (source, relative) = self.source_and_relative(mod_path, true)?;
        let active_root = self.active_root(true)?;
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;

        if path_exists(&enabled) && path_exists(&disabled) {
            return Err(Error::Conflict(format!(
                "Die aktive und die deaktivierte Version existieren gleichzeitig.\n\nAktiv: {}\nDeaktiviert: {}",
                enabled.display(),
                disabled.display()
            )));
        }
        if path_exists(&enabled) {
            if is_symlink(&enabled) {
                if symlink_points_to(&enabled, &source) {
                    self.last_enable_mode = Some("already_enabled_symlink");
                    return Ok(enabled);
                }
                return Err(Error::Conflict(format!(
                    "Am aktiven Ziel befindet sich eine fremde symbolische Verknüpfung.\n\nZiel: {}",
                    enabled.display()
                )));
            }
            if self.marker_matches(&enabled, &source) {
                self.last_enable_mode = Some("already_enabled");
                return Ok(enabled);
            }
            return Err(Error::Conflict(format!(
                "Am aktiven Ziel befindet sich ein nicht vom Manager verwalteter Ordner.\n\nZiel: {}",
                enabled.display()
            )));
        }
        if path_exists(&disabled) {
            return self.reactivate(&disabled, &enabled, &source, "rename_exact");
        }

        let managed = self.find_managed_destinations(&active_root, &source);
        if managed.len() > 1 {
            return Err(multiple_copies(&managed));
        }
        if let Some(existing) = managed.first() {
            if !is_disabled_destination(existing) {
                self.last_enable_mode = Some("already_enabled_discovered");
                return Ok(existing.clone());
            }
            let target = enabled_destination_from_disabled(existing);
            return self.reactivate(existing, &target, &source, "rename_discovered");
        }

        // Allererste Aktivierung: kopieren.
        let result = (|| -> Result<()> {
            if let Some(parent) = enabled.parent() {
                std::fs::create_dir_all(parent)?;
            }
            log::info!("First activation COPY: {} -> {}", source.display(), enabled.display());
            copy_tree(&source, &enabled)?;
            self.write_marker(&enabled, &source, &relative)?;
            Ok(())
        })();
        if let Err(error) = result {
            rollback_destination(&enabled);
            return Err(Error::Message(format!(
                "Der Mod konnte nicht kopiert werden.\n\nQuelle: {}\nZiel: {}\n\n{error}",
                source.display(),
                enabled.display()
            )));
        }
        self.last_enable_mode = Some("copy_first_activation");
        Ok(enabled)
    }

    /// Deaktiviert eine verwaltete Kopie ausschließlich per Umbenennen.
    /// Gibt `true` zurück, wenn etwas geändert wurde.
    pub fn disable(&self, mod_path: &Path) -> Result<bool> {
        let (source, relative) = self.source_and_relative(mod_path, false)?;
        let active_root = self.active_root(false)?;
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;

        if path_exists(&enabled) && path_exists(&disabled) {
            return Err(Error::Conflict(format!(
                "Die aktive und die deaktivierte Version existieren gleichzeitig.\n\nAktiv: {}\nDeaktiviert: {}",
                enabled.display(),
                disabled.display()
            )));
        }
        if path_exists(&disabled) {
            if !is_symlink(&disabled) && self.marker_matches(&disabled, &source) {
                return Ok(false);
            }
            return Err(Error::Conflict(format!(
                "Der deaktivierte Zielordner wird nicht vom Manager verwaltet.\n\nOrdner: {}",
                disabled.display()
            )));
        }
        if path_exists(&enabled) {
            if is_symlink(&enabled) {
                return Err(Error::Conflict(format!(
                    "Eine alte Symlink-Aktivierung wurde erkannt und wird nicht automatisch verändert.\n\nOrdner: {}",
                    enabled.display()
                )));
            }
            if !self.marker_matches(&enabled, &source) {
                return Err(Error::Conflict(format!(
                    "Der aktive Ordner besitzt keine gültige Manager-Markierung und wird nicht verändert.\n\nOrdner: {}",
                    enabled.display()
                )));
            }
            rename_to_disabled(&enabled)?;
            return Ok(true);
        }
        let managed = self.find_managed_destinations(&active_root, &source);
        if managed.len() > 1 {
            return Err(multiple_copies(&managed));
        }
        match managed.first() {
            Some(existing) if !is_disabled_destination(existing) => {
                rename_to_disabled(existing)?;
                Ok(true)
            }
            _ => Ok(false),
        }
    }

    pub fn destination_for(&self, mod_path: &Path) -> Result<PathBuf> {
        let (source, relative) = self.source_and_relative(mod_path, false)?;
        let active_root = self.active_root(false)?;
        Ok(self.resolve_destination_paths(&active_root, &source, &relative)?.0)
    }

    /// Bester Ordner für die INI-Analyse: aktive Kopie, deaktivierte Kopie, Original.
    pub fn inspection_path_for(&self, mod_path: &Path) -> Result<PathBuf> {
        let (source, relative) = self.source_and_relative(mod_path, false)?;
        let Ok(active_root) = self.active_root(false) else { return Ok(source) };
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;
        Ok(if enabled.is_dir() {
            enabled
        } else if disabled.is_dir() {
            disabled
        } else {
            source
        })
    }

    pub fn managed_copy_for(&self, mod_path: &Path) -> Result<(Option<PathBuf>, ModState)> {
        let (source, relative) = self.source_and_relative(mod_path, false)?;
        let active_root = match self.active_root(false) {
            Ok(root) => root,
            Err(Error::NotConfigured(_)) => return Ok((None, ModState::NotConfigured)),
            Err(error) => return Err(error),
        };
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;
        let enabled_exists = path_exists(&enabled);
        let disabled_exists = path_exists(&disabled);
        if enabled_exists && disabled_exists {
            return Err(Error::Conflict("Die aktive und die deaktivierte Version existieren gleichzeitig.".into()));
        }
        if enabled_exists {
            if is_symlink(&enabled) || !self.marker_matches(&enabled, &source) {
                return Err(Error::Conflict("Die aktive Mod-Kopie wird nicht sicher vom Manager verwaltet.".into()));
            }
            return Ok((Some(enabled), ModState::Enabled));
        }
        if disabled_exists {
            if is_symlink(&disabled) || !self.marker_matches(&disabled, &source) {
                return Err(Error::Conflict(
                    "Die deaktivierte Mod-Kopie wird nicht sicher vom Manager verwaltet.".into(),
                ));
            }
            return Ok((Some(disabled), ModState::Disabled));
        }
        let managed = self.find_managed_destinations(&active_root, &source);
        if managed.len() > 1 {
            return Err(Error::Conflict("Mehrere Manager-Kopien für denselben Mod wurden gefunden.".into()));
        }
        Ok(match managed.into_iter().next() {
            Some(destination) => {
                let state = if is_disabled_destination(&destination) { ModState::Disabled } else { ModState::Enabled };
                (Some(destination), state)
            }
            None => (None, ModState::Disabled),
        })
    }

    /// Ersetzt eine vorhandene verwaltete Kopie durch den aktuellen Bibliotheksstand.
    pub fn refresh_from_library(&self, mod_path: &Path) -> Result<ModState> {
        let (source, relative) = self.source_and_relative(mod_path, true)?;
        let (managed, state) = self.managed_copy_for(&source)?;
        if let Some(destination) = managed {
            self.replace_managed_copy(&source, &destination, &source, &relative)?;
        }
        Ok(state)
    }

    pub fn restore_managed_copy(&self, mod_path: &Path, backup: &Path, state: ModState) -> Result<ModState> {
        let (source, relative) = self.source_and_relative(mod_path, true)?;
        let backup = absolute(backup);
        if !backup.is_dir() {
            return Err(Error::Message(format!("Das Active-Mods-Backup existiert nicht: {}", backup.display())));
        }
        if !matches!(state, ModState::Enabled | ModState::Disabled) {
            return Ok(state);
        }
        let active_root = self.active_root(true)?;
        let (enabled, disabled) = self.resolve_destination_paths(&active_root, &source, &relative)?;
        let (destination, opposite) =
            if state == ModState::Enabled { (enabled, disabled) } else { (disabled, enabled) };
        if path_exists(&opposite) {
            if is_symlink(&opposite) || !self.marker_matches(&opposite, &source) {
                return Err(Error::Conflict("Die Active-Mods-Struktur enthält eine fremde Gegenkopie.".into()));
            }
            rollback_destination(&opposite);
        }
        if path_exists(&destination) && (is_symlink(&destination) || !self.marker_matches(&destination, &source)) {
            return Err(Error::Conflict("Die vorhandene Active-Mods-Kopie wird nicht vom Manager verwaltet.".into()));
        }
        self.replace_managed_copy(&backup, &destination, &source, &relative)?;
        Ok(state)
    }

    // ------------------------------------------------------------------
    // Intern
    // ------------------------------------------------------------------

    fn replace_managed_copy(
        &self,
        copy_source: &Path,
        destination: &Path,
        library_source: &Path,
        relative: &Path,
    ) -> Result<()> {
        let parent = destination.parent().unwrap_or(Path::new("."));
        std::fs::create_dir_all(parent)?;
        let name = destination.file_name().unwrap_or_default().to_string_lossy();
        let token = uuid::Uuid::new_v4().simple().to_string();
        let staging = parent.join(format!(".{name}.gmm-new-{token}"));
        let previous = parent.join(format!(".{name}.gmm-old-{token}"));
        let result = (|| -> Result<()> {
            copy_tree(copy_source, &staging)?;
            self.write_marker(&staging, library_source, relative)?;
            let had_previous = path_exists(destination);
            if had_previous {
                std::fs::rename(destination, &previous)?;
            }
            std::fs::rename(&staging, destination)?;
            if had_previous {
                rollback_destination(&previous);
            }
            Ok(())
        })();
        if let Err(error) = result {
            rollback_destination(&staging);
            if path_exists(&previous) && !path_exists(destination) {
                if let Err(rollback) = std::fs::rename(&previous, destination) {
                    log::error!("Active-Mods-Rollback fehlgeschlagen: {}: {rollback}", destination.display());
                }
            }
            return Err(Error::Message(format!(
                "Die verwaltete Mod-Kopie konnte nicht sicher ersetzt werden.\n\n{error}"
            )));
        }
        Ok(())
    }

    fn source_and_relative(&self, mod_path: &Path, require_exists: bool) -> Result<(PathBuf, PathBuf)> {
        let library_root = absolute(&self.scope.library_dir);
        let source = absolute(mod_path);
        let relative = source.strip_prefix(&library_root).map(Path::to_path_buf).map_err(|_| {
            Error::Message("Der ausgewählte Mod liegt nicht innerhalb der konfigurierten Mod-Bibliothek.".into())
        })?;
        if relative.as_os_str().is_empty() || relative == Path::new(".") {
            return Err(Error::Message("Die komplette Mod-Bibliothek kann nicht als Mod aktiviert werden.".into()));
        }
        if require_exists {
            if !source.exists() {
                return Err(Error::Message(format!(
                    "Der Mod-Ordner existiert nicht oder das Laufwerk ist nicht eingehängt.\n\nQuelle: {}",
                    source.display()
                )));
            }
            if !source.is_dir() {
                return Err(Error::Message(format!("Der Mod-Pfad ist kein Verzeichnis: {}", source.display())));
            }
        }
        Ok((source, relative))
    }

    fn active_root(&self, create: bool) -> Result<PathBuf> {
        let configured = self.scope.active_mods_dir.as_ref().ok_or_else(|| {
            Error::NotConfigured("Wähle unter Einstellungen zuerst den aktiven Mods-Ordner aus.".into())
        })?;
        let active_root = absolute(configured);
        if paths_overlap(&absolute(&self.scope.library_dir), &active_root) {
            return Err(Error::Message(
                "Mod-Bibliothek und aktiver Mods-Ordner dürfen nicht identisch oder ineinander verschachtelt sein."
                    .into(),
            ));
        }
        if create {
            std::fs::create_dir_all(&active_root).map_err(|error| {
                Error::Message(format!("Der aktive Mods-Ordner konnte nicht erstellt werden.\n\n{error}"))
            })?;
        }
        Ok(active_root)
    }

    /// Bevorzugt die relative Struktur, erkennt aber die alte flache Struktur.
    fn resolve_destination_paths(
        &self,
        active_root: &Path,
        source: &Path,
        relative: &Path,
    ) -> Result<(PathBuf, PathBuf)> {
        let preferred_enabled = active_root.join(relative);
        let preferred = (preferred_enabled.clone(), with_disabled_prefix(&preferred_enabled));
        let legacy_enabled = active_root.join(source.file_name().unwrap_or_default());
        let legacy = (legacy_enabled.clone(), with_disabled_prefix(&legacy_enabled));
        if preferred == legacy {
            return Ok(preferred);
        }
        let occupied: Vec<_> = [&preferred, &legacy]
            .into_iter()
            .filter(|(enabled, disabled)| path_exists(enabled) || path_exists(disabled))
            .collect();
        if occupied.len() > 1 {
            return Err(Error::Conflict(format!(
                "Der Mod wurde an mehreren Active-Mods-Speicherorten gefunden.\n\nRelative Struktur:\n{}\n{}\n\n\
                 Legacy-Struktur:\n{}\n{}",
                preferred.0.display(),
                preferred.1.display(),
                legacy.0.display(),
                legacy.1.display()
            )));
        }
        Ok(occupied.first().map(|pair| (*pair).clone()).unwrap_or(preferred))
    }

    fn write_marker(&self, destination: &Path, source: &Path, relative: &Path) -> Result<()> {
        let marker = Marker {
            manager: MANAGER_ID,
            game_id: self.scope.game.id,
            importer: self.scope.game.importer,
            source: source.to_string_lossy().into_owned(),
            source_key: normalized_path_key(source),
            relative_path: relative.to_string_lossy().into_owned(),
            created_at: chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Micros, false),
        };
        let temporary = destination.join(format!("{MANAGER_MARKER}.tmp"));
        std::fs::write(&temporary, to_pretty_json(&serde_json::to_value(&marker)?)?)?;
        std::fs::rename(&temporary, destination.join(MANAGER_MARKER))?;
        Ok(())
    }

    fn marker_matches(&self, destination: &Path, source: &Path) -> bool {
        marker_files(destination)
            .iter()
            .filter(|file| file.is_file())
            .filter_map(|file| load_marker(file))
            .any(|data| self.marker_data_matches(&data, source))
    }

    fn marker_data_matches(&self, data: &serde_json::Map<String, Value>, source: &Path) -> bool {
        match data.get("manager") {
            None | Some(Value::Null) => {}
            Some(Value::String(id)) if id == MANAGER_ID || id == LEGACY_MANAGER_ID => {}
            Some(_) => return false,
        }
        match data.get("game_id") {
            None | Some(Value::Null) => {
                if self.scope.game.id != GENSHIN_IMPACT {
                    return false;
                }
            }
            Some(Value::String(game)) if game == self.scope.game.id => {}
            Some(_) => return false,
        }
        if let Some(Value::String(key)) = data.get("source_key") {
            if *key == normalized_path_key(source) {
                return true;
            }
        }
        ["source", "source_path"].iter().any(|field| match data.get(*field) {
            Some(Value::String(stored)) => paths_equal(Path::new(stored), source),
            _ => false,
        })
    }

    fn find_managed_destinations(&self, active_root: &Path, source: &Path) -> Vec<PathBuf> {
        if !active_root.is_dir() {
            return Vec::new();
        }
        let mut seen = std::collections::HashSet::new();
        let mut results = Vec::new();
        for marker_name in [MANAGER_MARKER, NEXT_MANAGER_MARKER] {
            let markers = walkdir::WalkDir::new(active_root)
                .follow_links(false)
                .into_iter()
                .filter_map(|entry| entry.ok())
                .filter(|entry| entry.file_name() == marker_name);
            for marker in markers {
                let Some(destination) = marker.path().parent() else { continue };
                if is_symlink(destination) || !destination.is_dir() {
                    continue;
                }
                if !self.marker_matches(destination, source) {
                    continue;
                }
                if seen.insert(normalized_path_key(destination)) {
                    results.push(destination.to_path_buf());
                }
            }
        }
        results
    }

    fn reactivate(&mut self, disabled: &Path, enabled: &Path, source: &Path, mode: &'static str) -> Result<PathBuf> {
        if is_symlink(disabled) {
            return Err(Error::Conflict(format!(
                "Der deaktivierte Zielpfad ist eine symbolische Verknüpfung und wird nicht automatisch verändert.\n\nOrdner: {}",
                disabled.display()
            )));
        }
        if !self.marker_matches(disabled, source) {
            return Err(Error::Conflict(format!(
                "Der deaktivierte Ordner besitzt keine gültige Manager-Markierung.\n\nOrdner: {}",
                disabled.display()
            )));
        }
        if path_exists(enabled) {
            return Err(Error::Conflict(format!(
                "Das Reaktivierungsziel existiert bereits.\n\nQuelle: {}\nZiel: {}",
                disabled.display(),
                enabled.display()
            )));
        }
        let result = (|| -> std::io::Result<()> {
            if let Some(parent) = enabled.parent() {
                std::fs::create_dir_all(parent)?;
            }
            std::fs::rename(disabled, enabled)
        })();
        result.map_err(|error| {
            Error::Message(format!(
                "Der deaktivierte Mod konnte nicht aktiviert werden.\n\nQuelle: {}\nZiel: {}\n\n{error}",
                disabled.display(),
                enabled.display()
            ))
        })?;
        self.last_enable_mode = Some(mode);
        Ok(enabled.to_path_buf())
    }
}

fn multiple_copies(paths: &[PathBuf]) -> Error {
    Error::Conflict(format!(
        "Der Mod besitzt mehrere vom Manager verwaltete Kopien im Active-Mods-Ordner.\n\n{}",
        paths.iter().map(|p| p.display().to_string()).collect::<Vec<_>>().join("\n")
    ))
}

fn with_disabled_prefix(enabled: &Path) -> PathBuf {
    let name = enabled.file_name().unwrap_or_default().to_string_lossy();
    enabled.with_file_name(format!("{DISABLED_PREFIX}{name}"))
}

fn is_symlink(path: &Path) -> bool {
    crate::paths::is_symlink(path)
}

pub fn is_disabled_destination(path: &Path) -> bool {
    let name = path.file_name().unwrap_or_default().to_string_lossy();
    DISABLED_PREFIX_ALIASES.iter().any(|prefix| name.starts_with(prefix))
}

fn enabled_destination_from_disabled(disabled: &Path) -> PathBuf {
    let name = disabled.file_name().unwrap_or_default().to_string_lossy();
    for prefix in DISABLED_PREFIX_ALIASES {
        if let Some(rest) = name.strip_prefix(prefix) {
            if !rest.is_empty() {
                return disabled.with_file_name(rest);
            }
        }
    }
    disabled.to_path_buf()
}

fn rename_to_disabled(enabled: &Path) -> Result<PathBuf> {
    let disabled = with_disabled_prefix(enabled);
    if path_exists(&disabled) {
        return Err(Error::Conflict(format!(
            "Das deaktivierte Ziel existiert bereits.\n\nAktiv: {}\nDeaktiviert: {}",
            enabled.display(),
            disabled.display()
        )));
    }
    std::fs::rename(enabled, &disabled).map_err(|error| {
        Error::Message(format!(
            "Der Mod konnte nicht deaktiviert werden.\n\nQuelle: {}\nZiel: {}\n\n{error}",
            enabled.display(),
            disabled.display()
        ))
    })?;
    Ok(disabled)
}

fn marker_files(destination: &Path) -> [PathBuf; 2] {
    [destination.join(MANAGER_MARKER), destination.join(NEXT_MANAGER_MARKER)]
}

fn has_any_manager_marker(destination: &Path) -> bool {
    marker_files(destination).iter().any(|marker| marker.exists())
}

fn load_marker(file: &Path) -> Option<serde_json::Map<String, Value>> {
    let text = std::fs::read_to_string(file).ok()?;
    match serde_json::from_str(&text).ok()? {
        Value::Object(map) => Some(map),
        _ => None,
    }
}

fn symlink_points_to(destination: &Path, source: &Path) -> bool {
    let Ok(target) = std::fs::read_link(destination) else { return false };
    let target = if target.is_absolute() { target } else { destination.parent().unwrap_or(Path::new("")).join(target) };
    let resolve = |p: &Path| std::fs::canonicalize(p).unwrap_or_else(|_| crate::paths::normalize(&absolute(p)));
    resolve(&target) == resolve(source)
}

fn rollback_destination(destination: &Path) {
    let result = if is_symlink(destination) || destination.is_file() {
        std::fs::remove_file(destination)
    } else if destination.exists() {
        std::fs::remove_dir_all(destination)
    } else {
        Ok(())
    };
    if let Err(error) = result {
        log::error!("Rollback für Mod-Ziel fehlgeschlagen: {}: {error}", destination.display());
    }
}

fn is_ignored_copy_name(name: &str) -> bool {
    name == MANAGER_MARKER
        || name == NEXT_MANAGER_MARKER
        || name == format!("{MANAGER_MARKER}.tmp")
        || name == format!("{NEXT_MANAGER_MARKER}.tmp")
}

/// `shutil.copytree(symlinks=False, ignore=marker)`: Symlinks werden aufgelöst kopiert.
pub fn copy_tree(source: &Path, destination: &Path) -> std::io::Result<()> {
    if path_exists(destination) {
        return Err(std::io::Error::new(
            std::io::ErrorKind::AlreadyExists,
            format!("Ziel existiert bereits: {}", destination.display()),
        ));
    }
    std::fs::create_dir_all(destination)?;
    for entry in std::fs::read_dir(source)? {
        let entry = entry?;
        let name = entry.file_name();
        if is_ignored_copy_name(&name.to_string_lossy()) {
            continue;
        }
        let from = entry.path();
        let to = destination.join(&name);
        if std::fs::metadata(&from)?.is_dir() {
            copy_tree(&from, &to)?;
        } else {
            std::fs::copy(&from, &to)?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::games::find_game;

    struct Fixture {
        _temp: tempfile::TempDir,
        library: PathBuf,
        active: PathBuf,
    }

    fn fixture() -> Fixture {
        let temp = tempfile::tempdir().unwrap();
        let library = temp.path().join("library");
        let active = temp.path().join("active");
        let mod_dir = library.join("Furina/Character Skin/Summer");
        std::fs::create_dir_all(&mod_dir).unwrap();
        std::fs::write(mod_dir.join("mod.ini"), "[x]").unwrap();
        Fixture { _temp: temp, library, active }
    }

    fn manager(f: &Fixture, game: &str) -> ModManager {
        ModManager::new(GameScope {
            game: find_game(game).unwrap(),
            library_dir: f.library.clone(),
            active_mods_dir: Some(f.active.clone()),
        })
    }

    #[test]
    fn enable_disable_cycle_renames_only() {
        let f = fixture();
        let mut m = manager(&f, GENSHIN_IMPACT);
        let source = f.library.join("Furina/Character Skin/Summer");
        assert_eq!(m.get_state(&source), ModState::Disabled);

        let enabled = m.enable(&source).unwrap();
        assert_eq!(m.last_enable_mode(), Some("copy_first_activation"));
        assert_eq!(enabled, f.active.join("Furina/Character Skin/Summer"));
        assert!(enabled.join("mod.ini").is_file());
        let marker: Value =
            serde_json::from_str(&std::fs::read_to_string(enabled.join(MANAGER_MARKER)).unwrap()).unwrap();
        assert_eq!(marker["manager"], MANAGER_ID);
        assert_eq!(marker["importer"], "GIMI");
        assert_eq!(m.get_state(&source), ModState::Enabled);

        assert!(m.disable(&source).unwrap());
        assert!(f.active.join("Furina/Character Skin/DISABLED Summer").is_dir());
        assert_eq!(m.get_state(&source), ModState::Disabled);
        assert!(!m.disable(&source).unwrap());

        m.enable(&source).unwrap();
        assert_eq!(m.last_enable_mode(), Some("rename_exact"));
    }

    #[test]
    fn foreign_folder_is_conflict_and_can_be_adopted() {
        let f = fixture();
        let mut m = manager(&f, GENSHIN_IMPACT);
        let source = f.library.join("Furina/Character Skin/Summer");
        let foreign = f.active.join("Furina/Character Skin/Summer");
        std::fs::create_dir_all(&foreign).unwrap();
        assert_eq!(m.get_state(&source), ModState::Conflict);
        assert!(matches!(m.enable(&source), Err(Error::Conflict(_))));
        assert_eq!(m.adopt_existing(&source).unwrap(), ModState::Enabled);
        assert_eq!(m.get_state(&source), ModState::Enabled);
    }

    #[test]
    fn python_marker_without_game_id_is_genshin_only() {
        let f = fixture();
        let source = f.library.join("Furina/Character Skin/Summer");
        let copy = f.active.join("DISABLED Summer");
        std::fs::create_dir_all(&copy).unwrap();
        std::fs::write(
            copy.join(MANAGER_MARKER),
            format!(r#"{{"manager":"genshin-mod-manager","source":"{}"}}"#, source.display()),
        )
        .unwrap();
        assert_eq!(manager(&f, GENSHIN_IMPACT).get_state(&source), ModState::Disabled);
        // Wuthering Waves darf diese Kopie nicht für sich beanspruchen.
        let ww_source = f.library.join("Furina/Character Skin/Summer");
        assert_eq!(manager(&f, "wuthering-waves").get_state(&ww_source), ModState::Conflict);
    }

    #[test]
    fn discovers_copy_in_other_layout() {
        let f = fixture();
        let mut m = manager(&f, GENSHIN_IMPACT);
        let source = f.library.join("Furina/Character Skin/Summer");
        m.enable(&source).unwrap();
        // Kopie wird von Hand in einen anderen Ordner verschoben.
        std::fs::create_dir_all(f.active.join("Moved")).unwrap();
        std::fs::rename(f.active.join("Furina/Character Skin/Summer"), f.active.join("Moved/DISABLED_Summer")).unwrap();
        assert_eq!(m.get_state(&source), ModState::Disabled);
        let enabled = m.enable(&source).unwrap();
        assert_eq!(m.last_enable_mode(), Some("rename_discovered"));
        assert_eq!(enabled, f.active.join("Moved/Summer"));
    }

    #[test]
    fn overlapping_library_and_active_is_rejected() {
        let f = fixture();
        let mut m = ModManager::new(GameScope {
            game: find_game(GENSHIN_IMPACT).unwrap(),
            library_dir: f.library.clone(),
            active_mods_dir: Some(f.library.join("active")),
        });
        assert!(m.enable(&f.library.join("Furina/Character Skin/Summer")).is_err());
    }

    #[test]
    fn refresh_replaces_managed_copy() {
        let f = fixture();
        let mut m = manager(&f, GENSHIN_IMPACT);
        let source = f.library.join("Furina/Character Skin/Summer");
        m.enable(&source).unwrap();
        std::fs::write(source.join("new.ini"), "x").unwrap();
        assert_eq!(m.refresh_from_library(&source).unwrap(), ModState::Enabled);
        assert!(f.active.join("Furina/Character Skin/Summer/new.ini").is_file());
        assert_eq!(m.get_state(&source), ModState::Enabled);
    }
}
