//! Mod-Profile: gespeicherte Aktivierungszustände pro Spiel
//! (Port von `app/services/profile_service.py` und `profile_apply_worker.py`).
//!
//! Dateiformat und Dateinamen (`<spiel>__<profil>.json`) sind identisch zur
//! Python-Version, Profile sind also zwischen beiden Versionen austauschbar.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::OnceLock;
use std::time::Instant;

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::Value;

use crate::config::to_pretty_json;
use crate::manager::{ModManager, ModState};
use crate::scanner::ModInfo;
use crate::{Error, Result};

pub const PROFILE_SCHEMA_VERSION: i64 = 1;

/// Fortschritt: (aktuell, gesamt, Name)
pub type ApplyProgress<'a> = &'a (dyn Fn(usize, usize, &str) + Sync);

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ProfileModEntry {
    pub relative_path: String,
    pub name: String,
    pub enabled: bool,
}

#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ModProfile {
    pub schema_version: i64,
    pub name: String,
    pub game_id: String,
    pub created_at: String,
    pub updated_at: String,
    pub mods: Vec<ProfileModEntry>,
}

impl ModProfile {
    pub fn enabled_count(&self) -> usize {
        self.mods.iter().filter(|entry| entry.enabled).count()
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ApplyStatus {
    Changed,
    Unchanged,
    Missing,
    Blocked,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
pub struct ApplyItem {
    pub relative_path: String,
    pub name: String,
    pub desired_enabled: bool,
    pub status: ApplyStatus,
    pub message: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ApplyResult {
    pub profile_name: String,
    pub game_id: String,
    pub items: Vec<ApplyItem>,
    pub duration_seconds: f64,
    pub cancelled: bool,
    pub changed_count: usize,
    pub unchanged_count: usize,
    pub missing_count: usize,
    pub blocked_count: usize,
    pub failed_count: usize,
}

pub struct ProfileService {
    root: PathBuf,
}

fn now_iso() -> String {
    chrono::Utc::now().to_rfc3339_opts(chrono::SecondsFormat::Secs, false)
}

fn slug(value: &str) -> String {
    static RE: OnceLock<Regex> = OnceLock::new();
    let re = RE.get_or_init(|| Regex::new(r"[^A-Za-z0-9._-]+").unwrap());
    let slug = re.replace_all(value.trim(), "-");
    let slug = slug.trim_matches(|c| c == '-' || c == '.' || c == '_');
    if slug.is_empty() {
        "profile".into()
    } else {
        slug.to_string()
    }
}

pub fn validate_name(name: &str) -> Result<String> {
    let normalized = name.split_whitespace().collect::<Vec<_>>().join(" ");
    if normalized.is_empty() {
        return Err(Error::Message("Profilname darf nicht leer sein.".into()));
    }
    if normalized.chars().count() > 80 {
        return Err(Error::Message("Profilname ist zu lang.".into()));
    }
    Ok(normalized)
}

fn normalize_relative_path(value: &str) -> Result<String> {
    let normalized = value.replace('\\', "/");
    let parts: Vec<&str> = normalized.trim_matches('/').split('/').filter(|p| !p.is_empty() && *p != ".").collect();
    if parts.contains(&"..") {
        return Err(Error::Message("Profil enthält einen unsicheren relativen Pfad.".into()));
    }
    if parts.is_empty() {
        return Err(Error::Message("Profil enthält einen leeren Mod-Pfad.".into()));
    }
    Ok(parts.join("/"))
}

fn mod_key(value: &str) -> String {
    value.replace('\\', "/").trim_matches('/').to_lowercase()
}

fn relative_of(info: &ModInfo) -> String {
    if info.relative_path.is_empty() {
        info.path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default()
    } else {
        info.relative_path.clone()
    }
}

impl ProfileService {
    pub fn new(root: &Path) -> Result<Self> {
        let root = crate::paths::absolute(root);
        std::fs::create_dir_all(&root)?;
        Ok(Self { root })
    }

    fn profile_path(&self, game_id: &str, name: &str) -> PathBuf {
        self.root.join(format!("{}__{}.json", slug(game_id), slug(name)))
    }

    pub fn list_profiles(&self, game_id: &str) -> Vec<ModProfile> {
        let Ok(entries) = std::fs::read_dir(&self.root) else { return vec![] };
        let mut paths: Vec<PathBuf> =
            entries.flatten().map(|e| e.path()).filter(|p| p.extension().is_some_and(|ext| ext == "json")).collect();
        paths.sort();
        let mut profiles: Vec<ModProfile> =
            paths.iter().filter_map(|path| load_path(path).ok()).filter(|p| p.game_id == game_id).collect();
        profiles.sort_by(|a, b| (a.name.to_lowercase(), &a.updated_at).cmp(&(b.name.to_lowercase(), &b.updated_at)));
        profiles
    }

    pub fn load_profile(&self, game_id: &str, name: &str) -> Result<ModProfile> {
        let path = self.profile_path(game_id, name);
        if !path.is_file() {
            return Err(Error::Message(format!("Profil nicht gefunden: {name}")));
        }
        load_path(&path)
    }

    /// Hält die aktuellen Zustände der Bibliothek als Profil fest.
    pub fn capture_profile(
        &self,
        name: &str,
        game_id: &str,
        mods: &[ModInfo],
        manager: &ModManager,
        overwrite: bool,
    ) -> Result<ModProfile> {
        let name = validate_name(name)?;
        let path = self.profile_path(game_id, &name);
        let existing = if path.is_file() {
            if !overwrite {
                return Err(Error::Conflict(format!("Ein Profil mit dem Namen „{name}“ existiert bereits.")));
            }
            load_path(&path).ok()
        } else {
            None
        };
        let mut entries = Vec::new();
        for info in mods {
            let state = manager.get_state(&info.path);
            if matches!(state, ModState::Conflict | ModState::NotConfigured) {
                continue;
            }
            entries.push(ProfileModEntry {
                relative_path: normalize_relative_path(&relative_of(info))?,
                name: info.name.clone(),
                enabled: state == ModState::Enabled,
            });
        }
        entries.sort_by_key(|e| (e.relative_path.to_lowercase(), e.name.to_lowercase()));
        let now = now_iso();
        let profile = ModProfile {
            schema_version: PROFILE_SCHEMA_VERSION,
            name,
            game_id: game_id.to_string(),
            created_at: existing.map(|p| p.created_at).unwrap_or_else(|| now.clone()),
            updated_at: now,
            mods: entries,
        };
        self.save_profile(&profile)?;
        Ok(profile)
    }

    pub fn save_profile(&self, profile: &ModProfile) -> Result<PathBuf> {
        let name = validate_name(&profile.name)?;
        let path = self.profile_path(&profile.game_id, &name);
        let temporary = path.with_extension("json.tmp");
        let json = to_pretty_json(&serde_json::to_value(profile)?)?;
        if let Err(error) = std::fs::write(&temporary, json).and_then(|_| std::fs::rename(&temporary, &path)) {
            let _ = std::fs::remove_file(&temporary);
            return Err(error.into());
        }
        Ok(path)
    }

    pub fn rename_profile(&self, game_id: &str, old_name: &str, new_name: &str) -> Result<ModProfile> {
        let profile = self.load_profile(game_id, old_name)?;
        let new_name = validate_name(new_name)?;
        let old_path = self.profile_path(game_id, old_name);
        let new_path = self.profile_path(game_id, &new_name);
        if new_path != old_path && new_path.exists() {
            return Err(Error::Conflict(format!("Ein Profil mit dem Namen „{new_name}“ existiert bereits.")));
        }
        let renamed = ModProfile { name: new_name, updated_at: now_iso(), ..profile };
        self.save_profile(&renamed)?;
        if old_path != new_path {
            std::fs::remove_file(&old_path)?;
        }
        Ok(renamed)
    }

    pub fn delete_profile(&self, game_id: &str, name: &str) -> Result<()> {
        let path = self.profile_path(game_id, name);
        if !path.exists() {
            return Err(Error::Message(format!("Profil nicht gefunden: {name}")));
        }
        std::fs::remove_file(path)?;
        Ok(())
    }
}

fn load_path(path: &Path) -> Result<ModProfile> {
    let invalid = |what: &str| Error::Message(format!("{what}: {}", path.display()));
    let data: Value = serde_json::from_str(&std::fs::read_to_string(path)?)?;
    let map = data.as_object().ok_or_else(|| invalid("Ungültige Profildatei"))?;
    let schema = map.get("schema_version").and_then(Value::as_i64).unwrap_or(1);
    if schema != PROFILE_SCHEMA_VERSION {
        return Err(Error::Message(format!("Nicht unterstützte Profilversion {schema}: {}", path.display())));
    }
    let text = |key: &str| map.get(key).and_then(Value::as_str).filter(|v| !v.trim().is_empty()).map(str::to_string);
    let (Some(name), Some(game_id), Some(created_at), Some(updated_at)) =
        (text("name"), text("game_id"), text("created_at"), text("updated_at"))
    else {
        return Err(invalid("Ungültige Profil-Metadaten"));
    };
    let raw_mods = map.get("mods").and_then(Value::as_array).ok_or_else(|| invalid("Ungültige Mod-Liste"))?;
    let mut mods = Vec::with_capacity(raw_mods.len());
    for raw in raw_mods {
        let (Some(relative), Some(entry_name), Some(enabled)) = (
            raw.get("relative_path").and_then(Value::as_str).filter(|v| !v.trim().is_empty()),
            raw.get("name").and_then(Value::as_str),
            raw.get("enabled").and_then(Value::as_bool),
        ) else {
            return Err(invalid("Ungültiger Mod-Eintrag"));
        };
        mods.push(ProfileModEntry {
            relative_path: normalize_relative_path(relative)?,
            name: entry_name.into(),
            enabled,
        });
    }
    Ok(ModProfile {
        schema_version: schema,
        name: name.trim().into(),
        game_id: game_id.trim().into(),
        created_at,
        updated_at,
        mods,
    })
}

/// Wendet ein Profil an: aktiviert/deaktiviert nur, was abweicht.
/// Konflikte werden nie automatisch aufgelöst.
pub fn apply_profile(
    profile: &ModProfile,
    mods: &[ModInfo],
    manager: &mut ModManager,
    cancel: Option<&AtomicBool>,
    progress: Option<ApplyProgress<'_>>,
) -> ApplyResult {
    let started = Instant::now();
    let by_key: std::collections::HashMap<String, &ModInfo> =
        mods.iter().map(|m| (mod_key(&relative_of(m)), m)).collect();
    let total = profile.mods.len();
    let mut items = Vec::with_capacity(total);
    let mut cancelled = false;
    for (index, entry) in profile.mods.iter().enumerate() {
        if cancel.is_some_and(|flag| flag.load(Ordering::Relaxed)) {
            cancelled = true;
            break;
        }
        if let Some(report) = progress {
            report(index, total, &entry.name);
        }
        let item = |status, message: String, name: &str| ApplyItem {
            relative_path: entry.relative_path.clone(),
            name: name.to_string(),
            desired_enabled: entry.enabled,
            status,
            message,
        };
        let Some(info) = by_key.get(&mod_key(&entry.relative_path)) else {
            items.push(item(ApplyStatus::Missing, "Mod ist nicht mehr in der Library vorhanden.".into(), &entry.name));
            continue;
        };
        let outcome = apply_entry(manager, &info.path, entry.enabled);
        items.push(match outcome {
            Ok((status, message)) => item(status, message, &info.name),
            Err(error) => item(ApplyStatus::Failed, error.to_string(), &info.name),
        });
        if let Some(report) = progress {
            report(index + 1, total, &entry.name);
        }
    }
    let count = |status| items.iter().filter(|item: &&ApplyItem| item.status == status).count();
    ApplyResult {
        profile_name: profile.name.clone(),
        game_id: profile.game_id.clone(),
        changed_count: count(ApplyStatus::Changed),
        unchanged_count: count(ApplyStatus::Unchanged),
        missing_count: count(ApplyStatus::Missing),
        blocked_count: count(ApplyStatus::Blocked),
        failed_count: count(ApplyStatus::Failed),
        duration_seconds: started.elapsed().as_secs_f64(),
        cancelled,
        items,
    }
}

fn apply_entry(manager: &mut ModManager, path: &Path, enable: bool) -> Result<(ApplyStatus, String)> {
    let state = manager.get_state(path);
    match state {
        ModState::NotConfigured => {
            return Ok((ApplyStatus::Blocked, "Aktiver Mods-Ordner ist nicht konfiguriert.".into()));
        }
        ModState::Conflict => {
            return Ok((ApplyStatus::Blocked, "Konflikt: fremde Daten werden nicht automatisch übernommen.".into()));
        }
        ModState::Enabled if enable => return Ok((ApplyStatus::Unchanged, String::new())),
        ModState::Disabled if !enable => return Ok((ApplyStatus::Unchanged, String::new())),
        _ => {}
    }
    if enable {
        if state == ModState::Broken {
            manager.disable(path)?;
        }
        manager.enable(path)?;
    } else {
        manager.disable(path)?;
    }
    let expected = if enable { ModState::Enabled } else { ModState::Disabled };
    let final_state = manager.get_state(path);
    if final_state != expected {
        return Ok((ApplyStatus::Failed, format!("Unerwarteter Endzustand: {}", final_state.as_str())));
    }
    Ok((ApplyStatus::Changed, String::new()))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::games::find_game;
    use crate::manager::GameScope;
    use crate::scanner::ModScanner;

    #[test]
    fn capture_apply_rename_delete() {
        let temp = tempfile::tempdir().unwrap();
        let library = temp.path().join("lib");
        for name in ["A/Skins/One", "A/Skins/Two", "B/Three"] {
            std::fs::create_dir_all(library.join(name)).unwrap();
            std::fs::write(library.join(name).join("mod.ini"), "[x]").unwrap();
        }
        let scope = GameScope {
            game: find_game("genshin-impact").unwrap(),
            library_dir: library.clone(),
            active_mods_dir: Some(temp.path().join("active")),
        };
        let mut manager = ModManager::new(scope);
        let mods = ModScanner::new().scan(&library, None).unwrap().mods;
        manager.enable(&library.join("A/Skins/One")).unwrap();

        let service = ProfileService::new(&temp.path().join("profiles")).unwrap();
        let profile = service.capture_profile("  Mein   Profil ", "genshin-impact", &mods, &manager, false).unwrap();
        assert_eq!(profile.name, "Mein Profil");
        assert_eq!(profile.enabled_count(), 1);
        assert!(temp.path().join("profiles/genshin-impact__Mein-Profil.json").is_file());
        assert!(service.capture_profile("Mein Profil", "genshin-impact", &mods, &manager, false).is_err());

        // Zustand ändern und Profil wieder anwenden.
        manager.disable(&library.join("A/Skins/One")).unwrap();
        manager.enable(&library.join("B/Three")).unwrap();
        let result = apply_profile(&profile, &mods, &mut manager, None, None);
        assert_eq!((result.changed_count, result.unchanged_count), (2, 1));
        assert_eq!(manager.get_state(&library.join("A/Skins/One")), ModState::Enabled);
        assert_eq!(manager.get_state(&library.join("B/Three")), ModState::Disabled);

        let renamed = service.rename_profile("genshin-impact", "Mein Profil", "Abend").unwrap();
        assert_eq!(service.list_profiles("genshin-impact"), vec![renamed]);
        assert!(service.list_profiles("wuthering-waves").is_empty());
        service.delete_profile("genshin-impact", "Abend").unwrap();
        assert!(service.list_profiles("genshin-impact").is_empty());
    }

    #[test]
    fn reads_python_profile() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(
            temp.path().join("genshin-impact__x.json"),
            r#"{"schema_version": 1, "name": "x", "game_id": "genshin-impact", "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00", "mods": [{"relative_path": "A\\B", "name": "B", "enabled": true}]}"#,
        )
        .unwrap();
        let service = ProfileService::new(temp.path()).unwrap();
        let profiles = service.list_profiles("genshin-impact");
        assert_eq!(profiles[0].mods[0].relative_path, "A/B");
    }
}
