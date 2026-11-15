//! Konflikt-Prüfung für Bibliothek und Active-Mods-Ordner
//! (Port von `app/services/conflict_scanner.py`).
//!
//! Erkennt auch Mods, die außerhalb des Managers von Hand in den
//! XXMI-Ordner kopiert wurden.

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};

use serde::Serialize;
use serde_json::Value;

use crate::manager::{
    GameScope, ModManager, ModState, DISABLED_PREFIX, LEGACY_MANAGER_ID, MANAGER_ID, MANAGER_MARKER,
    NEXT_MANAGER_MARKER,
};
use crate::paths::{absolute, is_symlink, normalized_path_key};
use crate::scanner::ModInfo;

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictKind {
    Library,
    UnmanagedActive,
    InvalidMarker,
    OrphanedManaged,
}

impl ConflictKind {
    fn sort_key(self) -> &'static str {
        match self {
            Self::Library => "library",
            Self::UnmanagedActive => "unmanaged_active",
            Self::InvalidMarker => "invalid_marker",
            Self::OrphanedManaged => "orphaned_managed",
        }
    }
}

#[derive(Debug, Clone, Serialize)]
pub struct ConflictItem {
    pub kind: ConflictKind,
    pub title: String,
    pub path: PathBuf,
    pub message: String,
    pub library_mod_path: Option<PathBuf>,
    pub can_adopt: bool,
}

pub struct ConflictScanner<'a> {
    scope: &'a GameScope,
    manager: &'a ModManager,
}

impl<'a> ConflictScanner<'a> {
    pub fn new(scope: &'a GameScope, manager: &'a ModManager) -> Self {
        Self { scope, manager }
    }

    pub fn scan(&self, mods: &[ModInfo]) -> Vec<ConflictItem> {
        let mut conflicts = Vec::new();
        let mut known = HashSet::new();
        let library_keys: HashMap<String, &ModInfo> = mods.iter().map(|m| (normalized_path_key(&m.path), m)).collect();

        for info in mods {
            if self.manager.get_state(&info.path) != ModState::Conflict {
                continue;
            }
            let path = self.manager.destination_for(&info.path).unwrap_or_else(|_| info.path.clone());
            if known.insert(normalized_path_key(&path)) {
                conflicts.push(ConflictItem {
                    kind: ConflictKind::Library,
                    title: info.name.clone(),
                    path,
                    message: "Am erwarteten Active-Mod-Ziel existieren Daten, die nicht eindeutig diesem Library-Mod \
                              zugeordnet werden können."
                        .into(),
                    library_mod_path: Some(info.path.clone()),
                    can_adopt: true,
                });
            }
        }

        if let Some(active_root) = self.scope.active_mods_dir.as_ref().filter(|dir| dir.is_dir()) {
            self.scan_active_directory(active_root, &library_keys, &mut conflicts, &mut known);
        }
        conflicts.sort_by_key(|item| {
            (item.kind.sort_key(), item.title.to_lowercase(), item.path.to_string_lossy().to_lowercase())
        });
        conflicts
    }

    fn scan_active_directory(
        &self,
        directory: &Path,
        library_keys: &HashMap<String, &ModInfo>,
        conflicts: &mut Vec<ConflictItem>,
        known: &mut HashSet<String>,
    ) {
        let Ok(entries) = std::fs::read_dir(directory) else { return };
        let mut entries: Vec<PathBuf> = entries.flatten().map(|entry| entry.path()).collect();
        entries.sort_by_key(|path| path.file_name().map(|n| n.to_string_lossy().to_lowercase()));
        for entry in entries {
            if is_symlink(&entry) {
                self.inspect_symlink(&entry, conflicts, known);
                continue;
            }
            if !entry.is_dir() {
                continue;
            }
            if let Some(marker) = find_marker(&entry) {
                if let Some(item) = self.inspect_marker(&entry, &marker, library_keys) {
                    append_unique(item, conflicts, known);
                }
                continue;
            }
            if looks_like_mod_root(&entry) {
                append_unique(
                    ConflictItem {
                        kind: ConflictKind::UnmanagedActive,
                        title: display_name(&entry),
                        path: entry.clone(),
                        message: "Dieser Mod befindet sich im XXMI-Active-Mods-Ordner, besitzt aber keine gültige \
                                  Manager-Markierung. Er wurde vermutlich manuell hinzugefügt."
                            .into(),
                        library_mod_path: None,
                        can_adopt: false,
                    },
                    conflicts,
                    known,
                );
                continue;
            }
            self.scan_active_directory(&entry, library_keys, conflicts, known);
        }
    }

    fn inspect_marker(
        &self,
        directory: &Path,
        marker: &Path,
        library_keys: &HashMap<String, &ModInfo>,
    ) -> Option<ConflictItem> {
        let invalid = |message: &str| ConflictItem {
            kind: ConflictKind::InvalidMarker,
            title: display_name(directory),
            path: directory.to_path_buf(),
            message: message.into(),
            library_mod_path: None,
            can_adopt: false,
        };
        let data: Value = match std::fs::read_to_string(marker).ok().and_then(|text| serde_json::from_str(&text).ok()) {
            Some(value) => value,
            None => return Some(invalid("Der Manager-Marker dieses Mods ist beschädigt oder nicht lesbar.")),
        };
        let Some(data) = data.as_object() else {
            return Some(invalid("Der Manager-Marker besitzt ein ungültiges Format."));
        };
        match data.get("manager") {
            None | Some(Value::Null) => {}
            Some(Value::String(id)) if id == MANAGER_ID || id == LEGACY_MANAGER_ID => {}
            Some(_) => return Some(invalid("Der vorhandene Manager-Marker gehört zu einer unbekannten Anwendung.")),
        }
        if let Some(Value::String(game)) = data.get("game_id") {
            if game != self.scope.game.id {
                return Some(invalid("Der Manager-Marker gehört zu einem anderen Spiel."));
            }
        }
        if let Some(Value::String(key)) = data.get("source_key") {
            if library_keys.contains_key(key) {
                return None;
            }
        }
        for field in ["source", "source_path"] {
            let Some(Value::String(value)) = data.get(field) else { continue };
            let source = absolute(Path::new(value));
            if library_keys.contains_key(&normalized_path_key(&source)) {
                return None;
            }
            if source.exists() {
                return Some(invalid("Der aktive Mod verweist auf eine Quelle außerhalb der aktuellen Library."));
            }
        }
        Some(ConflictItem {
            kind: ConflictKind::OrphanedManaged,
            title: display_name(directory),
            path: directory.to_path_buf(),
            message: "Dieser aktive Mod wurde früher vom Manager verwaltet, aber der zugehörige Library-Mod wurde \
                      nicht gefunden."
                .into(),
            library_mod_path: None,
            can_adopt: false,
        })
    }

    fn inspect_symlink(&self, path: &Path, conflicts: &mut Vec<ConflictItem>, known: &mut HashSet<String>) {
        let library_root = crate::paths::normalize(&absolute(&self.scope.library_dir));
        let target = std::fs::read_link(path).ok().map(|target| {
            let joined =
                if target.is_absolute() { target } else { path.parent().unwrap_or(Path::new("")).join(target) };
            std::fs::canonicalize(&joined).unwrap_or_else(|_| crate::paths::normalize(&joined))
        });
        let library_canonical = std::fs::canonicalize(&library_root).unwrap_or(library_root.clone());
        if target.is_some_and(|t| t.starts_with(&library_root) || t.starts_with(&library_canonical)) {
            return;
        }
        append_unique(
            ConflictItem {
                kind: ConflictKind::UnmanagedActive,
                title: display_name(path),
                path: path.to_path_buf(),
                message:
                    "Im Active-Mods-Ordner befindet sich eine nicht vom Manager verwaltete symbolische Verknüpfung."
                        .into(),
                library_mod_path: None,
                can_adopt: false,
            },
            conflicts,
            known,
        );
    }
}

fn find_marker(directory: &Path) -> Option<PathBuf> {
    [MANAGER_MARKER, NEXT_MANAGER_MARKER].iter().map(|name| directory.join(name)).find(|marker| marker.is_file())
}

/// Nur Ordner mit eigener INI gelten als Mod (Kategorieordner nicht).
fn looks_like_mod_root(directory: &Path) -> bool {
    std::fs::read_dir(directory)
        .map(|entries| {
            entries.flatten().any(|entry| {
                entry.path().is_file()
                    && entry.path().extension().is_some_and(|ext| ext.to_string_lossy().eq_ignore_ascii_case("ini"))
            })
        })
        .unwrap_or(false)
}

fn display_name(path: &Path) -> String {
    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let name = name.strip_prefix(DISABLED_PREFIX).map(str::to_string).unwrap_or(name);
    if name.is_empty() {
        path.display().to_string()
    } else {
        name
    }
}

fn append_unique(item: ConflictItem, conflicts: &mut Vec<ConflictItem>, known: &mut HashSet<String>) {
    if known.insert(normalized_path_key(&item.path)) {
        conflicts.push(item);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::games::find_game;
    use crate::scanner::ModScanner;

    #[test]
    fn detects_all_conflict_kinds() {
        let temp = tempfile::tempdir().unwrap();
        let library = temp.path().join("lib");
        let active = temp.path().join("active");
        let write = |path: PathBuf, content: &str| {
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, content).unwrap();
        };
        write(library.join("Furina/Skins/Summer/mod.ini"), "[x]");
        write(library.join("Furina/Skins/Winter/mod.ini"), "[x]");
        // Bibliothekskonflikt: fremder Ordner am Ziel von Summer.
        write(active.join("Furina/Skins/Summer/mod.ini"), "[x]");
        // Manuell kopierter Mod in einer Kategorie.
        write(active.join("Manual/Hand Mod/a.ini"), "[x]");
        // Defekter Marker.
        write(active.join("Broken/b.ini"), "[x]");
        write(active.join("Broken").join(MANAGER_MARKER), "{kaputt");
        // Verwaiste Kopie.
        write(active.join("DISABLED Gone/c.ini"), "[x]");
        write(
            active.join("DISABLED Gone").join(MANAGER_MARKER),
            r#"{"manager":"xxmi-mod-manager","game_id":"genshin-impact","source":"/does/not/exist"}"#,
        );

        let scope = GameScope {
            game: find_game("genshin-impact").unwrap(),
            library_dir: library.clone(),
            active_mods_dir: Some(active.clone()),
        };
        let mut manager = ModManager::new(scope.clone());
        manager.enable(&library.join("Furina/Skins/Winter")).unwrap(); // sauber verwaltet -> kein Konflikt
        let mods = ModScanner::new().scan(&library, None).unwrap().mods;

        let items = ConflictScanner::new(&scope, &manager).scan(&mods);
        let summary: Vec<_> = items.iter().map(|item| (item.kind, item.title.as_str())).collect();
        assert_eq!(
            summary,
            vec![
                (ConflictKind::InvalidMarker, "Broken"),
                (ConflictKind::Library, "Summer"),
                (ConflictKind::OrphanedManaged, "Gone"),
                (ConflictKind::UnmanagedActive, "Hand Mod"),
            ]
        );
        assert!(items[1].can_adopt);
    }
}
