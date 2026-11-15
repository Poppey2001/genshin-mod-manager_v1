//! Programmeinstellungen (Port von `app/config.py`).
//!
//! Das JSON-Format ist identisch zur Python-Version. Beide Versionen können
//! dieselbe `config.json` lesen und schreiben. Unbekannte Felder (z. B. von
//! neueren Versionen) bleiben beim Speichern erhalten.

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use crate::games::{all_games, find_game, get_game, GameDefinition, GENSHIN_IMPACT};
use crate::paths::{expand_user, AppDirs};
use crate::{Error, Result};

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct GameConfig {
    pub library_path: Option<String>,
    pub active_mods_path: Option<String>,
    pub launcher_path: Option<String>,
    pub enabled: bool,
}

impl Default for GameConfig {
    fn default() -> Self {
        Self { library_path: None, active_mods_path: None, launcher_path: None, enabled: true }
    }
}

impl GameConfig {
    fn new() -> Self {
        Self::default()
    }

    fn from_value(value: &Value) -> Self {
        let mut config = Self::new();
        let Some(map) = value.as_object() else { return config };
        let string_field = |name: &str| match map.get(name) {
            Some(Value::String(text)) => Some(Some(text.clone())),
            Some(Value::Null) => Some(None),
            _ => None,
        };
        if let Some(value) = string_field("library_path") {
            config.library_path = value;
        }
        if let Some(value) = string_field("active_mods_path") {
            config.active_mods_path = value;
        }
        if let Some(value) = string_field("launcher_path") {
            config.launcher_path = value;
        }
        if let Some(Value::Bool(enabled)) = map.get("enabled") {
            config.enabled = *enabled;
        }
        config
    }
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AppConfig {
    pub selected_game: String,
    pub games: BTreeMap<String, GameConfig>,
    pub selected_profile: String,
    pub use_symlinks: bool,
    pub create_backups: bool,
    pub theme: String,
    pub language: String,
    pub library_view_mode: String,
    pub auto_check_updates: bool,
    pub update_channel: String,
    pub window_width: i64,
    pub window_height: i64,
    pub first_start: bool,
    /// Neu in der Rust-Version: Fenster schließen minimiert in den Tray,
    /// damit im Hintergrund weiter nach Updates gesucht wird.
    #[serde(default = "default_true")]
    pub run_in_background: bool,
    /// Intervall der Hintergrund-Updateprüfung in Minuten.
    #[serde(default = "default_interval")]
    pub update_check_interval_minutes: u32,
    /// Vom Benutzer übersprungene Version.
    #[serde(default)]
    pub skipped_update_version: String,
    /// Felder, die diese Version nicht kennt, werden unverändert erhalten.
    #[serde(skip)]
    pub extra: Map<String, Value>,
}

fn default_true() -> bool {
    true
}

fn default_interval() -> u32 {
    60
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            selected_game: GENSHIN_IMPACT.to_string(),
            games: all_games().iter().map(|game| (game.id.to_string(), GameConfig::new())).collect(),
            selected_profile: "Default".into(),
            use_symlinks: false,
            create_backups: true,
            theme: "dark".into(),
            language: "de".into(),
            library_view_mode: "list".into(),
            auto_check_updates: true,
            update_channel: "prerelease".into(),
            window_width: 1200,
            window_height: 760,
            first_start: true,
            run_in_background: true,
            update_check_interval_minutes: default_interval(),
            skipped_update_version: String::new(),
            extra: Map::new(),
        }
    }
}

const KNOWN_KEYS: &[&str] = &[
    "selected_game",
    "games",
    "selected_profile",
    "use_symlinks",
    "create_backups",
    "theme",
    "language",
    "library_view_mode",
    "auto_check_updates",
    "update_channel",
    "window_width",
    "window_height",
    "first_start",
    "run_in_background",
    "update_check_interval_minutes",
    "skipped_update_version",
    // Legacy-Schlüssel, die nach der Migration nicht erneut geschrieben werden.
    "library_path",
    "active_mods_path",
    "launcher_path",
];

impl AppConfig {
    /// Entspricht `AppConfig.from_dict` inklusive Legacy-Migration.
    pub fn from_value(data: &Value, dirs: &AppDirs) -> Self {
        let mut config = Self::default();
        let Some(map) = data.as_object() else { return config };

        if let Some(Value::String(game)) = map.get("selected_game") {
            config.selected_game = game.clone();
        }

        match map.get("games") {
            Some(Value::Object(games)) => {
                for (game_id, raw) in games {
                    if find_game(game_id).is_none() || !raw.is_object() {
                        continue;
                    }
                    config.games.insert(game_id.clone(), GameConfig::from_value(raw));
                }
            }
            _ => {
                // Alte Single-Game-Konfiguration -> games["genshin-impact"]
                let genshin = config.games.entry(GENSHIN_IMPACT.to_string()).or_default();
                genshin.library_path = Some(dirs.mod_library_dir().to_string_lossy().into_owned());
                if let Some(Value::String(path)) = map.get("library_path") {
                    genshin.library_path = Some(path.clone());
                }
                match map.get("active_mods_path") {
                    Some(Value::String(path)) => genshin.active_mods_path = Some(path.clone()),
                    Some(Value::Null) | None => genshin.active_mods_path = None,
                    _ => {}
                }
                match map.get("launcher_path") {
                    Some(Value::String(path)) => genshin.launcher_path = Some(path.clone()),
                    Some(Value::Null) | None => genshin.launcher_path = None,
                    _ => {}
                }
                config.selected_game = GENSHIN_IMPACT.to_string();
            }
        }

        let string = |key: &str| map.get(key).and_then(Value::as_str).map(str::to_string);
        let boolean = |key: &str| map.get(key).and_then(Value::as_bool);
        let integer = |key: &str| map.get(key).and_then(Value::as_i64);

        if let Some(v) = string("selected_profile") {
            config.selected_profile = v;
        }
        if let Some(v) = string("theme") {
            config.theme = v;
        }
        if let Some(v) = string("language") {
            config.language = v;
        }
        if let Some(v) = string("library_view_mode") {
            config.library_view_mode = v;
        }
        if let Some(v) = string("update_channel") {
            config.update_channel = v;
        }
        if let Some(v) = string("skipped_update_version") {
            config.skipped_update_version = v;
        }
        if let Some(v) = boolean("use_symlinks") {
            config.use_symlinks = v;
        }
        if let Some(v) = boolean("create_backups") {
            config.create_backups = v;
        }
        if let Some(v) = boolean("first_start") {
            config.first_start = v;
        }
        if let Some(v) = boolean("auto_check_updates") {
            config.auto_check_updates = v;
        }
        if let Some(v) = boolean("run_in_background") {
            config.run_in_background = v;
        }
        if let Some(v) = integer("window_width") {
            config.window_width = v;
        }
        if let Some(v) = integer("window_height") {
            config.window_height = v;
        }
        if let Some(v) = integer("update_check_interval_minutes") {
            config.update_check_interval_minutes = v.clamp(1, 60 * 24 * 7) as u32;
        }

        config.extra = map
            .iter()
            .filter(|(key, _)| !KNOWN_KEYS.contains(&key.as_str()))
            .map(|(key, value)| (key.clone(), value.clone()))
            .collect();

        config.validate();
        config
    }

    pub fn validate(&mut self) {
        if !["dark", "light", "system"].contains(&self.theme.as_str()) {
            self.theme = "dark".into();
        }
        if !["de", "en"].contains(&self.language.as_str()) {
            self.language = "de".into();
        }
        if !["stable", "prerelease"].contains(&self.update_channel.as_str()) {
            self.update_channel = "prerelease".into();
        }
        self.window_width = self.window_width.max(800);
        self.window_height = self.window_height.max(500);
        if self.selected_profile.trim().is_empty() {
            self.selected_profile = "Default".into();
        }
        if find_game(&self.selected_game).is_none() {
            self.selected_game = GENSHIN_IMPACT.into();
        }
        for game in all_games() {
            self.games.entry(game.id.to_string()).or_default();
        }
        if !["list", "gallery"].contains(&self.library_view_mode.as_str()) {
            self.library_view_mode = "list".into();
        }
        self.update_check_interval_minutes = self.update_check_interval_minutes.clamp(1, 60 * 24 * 7);
    }

    pub fn to_value(&self) -> Value {
        let mut map = self.extra.clone();
        let mut games = Map::new();
        for (id, game) in &self.games {
            games.insert(id.clone(), serde_json::to_value(game).unwrap_or(Value::Null));
        }
        let entries: [(&str, Value); 16] = [
            ("selected_game", self.selected_game.clone().into()),
            ("games", Value::Object(games)),
            ("selected_profile", self.selected_profile.clone().into()),
            ("use_symlinks", self.use_symlinks.into()),
            ("create_backups", self.create_backups.into()),
            ("theme", self.theme.clone().into()),
            ("language", self.language.clone().into()),
            ("library_view_mode", self.library_view_mode.clone().into()),
            ("auto_check_updates", self.auto_check_updates.into()),
            ("update_channel", self.update_channel.clone().into()),
            ("window_width", self.window_width.into()),
            ("window_height", self.window_height.into()),
            ("first_start", self.first_start.into()),
            ("run_in_background", self.run_in_background.into()),
            ("update_check_interval_minutes", self.update_check_interval_minutes.into()),
            ("skipped_update_version", self.skipped_update_version.clone().into()),
        ];
        for (key, value) in entries {
            map.insert(key.to_string(), value);
        }
        Value::Object(map)
    }

    /// Lädt die Konfiguration; eine defekte Datei wird gesichert und ersetzt.
    pub fn load(dirs: &AppDirs) -> Self {
        let _ = dirs.ensure();
        let file = dirs.config_file();
        for game in all_games() {
            let _ = std::fs::create_dir_all(dirs.mod_library_dir().join(game.library_folder));
        }
        if !file.exists() {
            let config = Self::default();
            let _ = config.save(dirs);
            return config;
        }
        let parsed = std::fs::read_to_string(&file)
            .map_err(Error::from)
            .and_then(|text| serde_json::from_str::<Value>(&text).map_err(Error::from))
            .and_then(|value| {
                if value.is_object() {
                    Ok(value)
                } else {
                    Err(Error::Message("Die Konfigurationsdatei enthält kein JSON-Objekt.".into()))
                }
            });
        match parsed {
            Ok(value) => Self::from_value(&value, dirs),
            Err(error) => {
                log::error!("Konfiguration konnte nicht geladen werden: {error}");
                let stamp = chrono::Local::now().format("%Y%m%d-%H%M%S");
                let _ = std::fs::rename(&file, dirs.config_dir.join(format!("config-broken-{stamp}.json")));
                let config = Self::default();
                let _ = config.save(dirs);
                config
            }
        }
    }

    /// Atomar speichern (temporäre Datei + Rename), 4 Leerzeichen Einrückung wie Python.
    pub fn save(&self, dirs: &AppDirs) -> Result<()> {
        dirs.ensure()?;
        let mut config = self.clone();
        config.validate();
        let file = dirs.config_file();
        let temporary = file.with_extension("tmp");
        std::fs::write(&temporary, to_pretty_json(&config.to_value())?)?;
        std::fs::rename(&temporary, &file)?;
        Ok(())
    }

    pub fn current_game(&self) -> &'static GameDefinition {
        get_game(&self.selected_game)
    }

    pub fn game_config(&self, game_id: &str) -> GameConfig {
        self.games.get(get_game(game_id).id).cloned().unwrap_or_else(GameConfig::new)
    }

    pub fn game_config_mut(&mut self, game_id: &str) -> &mut GameConfig {
        self.games.entry(get_game(game_id).id.to_string()).or_default()
    }

    pub fn mod_library_directory_for(&self, game_id: &str, dirs: &AppDirs) -> PathBuf {
        let game = get_game(game_id);
        match self.game_config(game.id).library_path.filter(|p| !p.is_empty()) {
            Some(path) => expand_user(Path::new(&path)),
            None => dirs.mod_library_dir().join(game.library_folder),
        }
    }

    pub fn active_mods_directory_for(&self, game_id: &str) -> Option<PathBuf> {
        self.game_config(game_id).active_mods_path.filter(|p| !p.is_empty()).map(|path| expand_user(Path::new(&path)))
    }

    pub fn launcher_file_for(&self, game_id: &str) -> Option<PathBuf> {
        self.game_config(game_id).launcher_path.filter(|p| !p.is_empty()).map(|path| expand_user(Path::new(&path)))
    }
}

/// `json.dumps(..., indent=4, ensure_ascii=False)`-kompatible Ausgabe.
pub fn to_pretty_json(value: &Value) -> Result<String> {
    let mut buffer = Vec::new();
    let formatter = serde_json::ser::PrettyFormatter::with_indent(b"    ");
    let mut serializer = serde_json::Serializer::with_formatter(&mut buffer, formatter);
    value.serialize(&mut serializer)?;
    Ok(String::from_utf8(buffer).expect("serde_json schreibt UTF-8"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn migrates_legacy_config() {
        let dirs = AppDirs::rooted(Path::new("/tmp/gmm-test"));
        let config = AppConfig::from_value(
            &json!({"library_path": "/lib", "active_mods_path": "/active", "language": "en"}),
            &dirs,
        );
        let genshin = config.game_config(GENSHIN_IMPACT);
        assert_eq!(genshin.library_path.as_deref(), Some("/lib"));
        assert_eq!(genshin.active_mods_path.as_deref(), Some("/active"));
        assert_eq!(config.language, "en");
        assert_eq!(config.games.len(), all_games().len());
    }

    #[test]
    fn invalid_values_are_corrected_and_extras_kept() {
        let dirs = AppDirs::rooted(Path::new("/tmp/gmm-test"));
        let config = AppConfig::from_value(
            &json!({"games": {}, "theme": "pink", "selected_game": "nope", "window_width": 10, "future": 1}),
            &dirs,
        );
        assert_eq!(config.theme, "dark");
        assert_eq!(config.selected_game, GENSHIN_IMPACT);
        assert_eq!(config.window_width, 800);
        assert_eq!(config.to_value()["future"], json!(1));
    }

    #[test]
    fn save_and_load_roundtrip() {
        let temp = tempfile::tempdir().unwrap();
        let dirs = AppDirs::rooted(temp.path());
        let mut config = AppConfig::default();
        config.game_config_mut("wuthering-waves").active_mods_path = Some("/x".into());
        config.save(&dirs).unwrap();
        let text = std::fs::read_to_string(dirs.config_file()).unwrap();
        assert!(text.contains("\n    \"selected_game\""));
        assert_eq!(AppConfig::load(&dirs), config);
    }
}
