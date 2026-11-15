//! Bibliotheks-Scan (Port von `app/services/mod_scanner.py`).

use std::collections::BTreeMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::{Instant, UNIX_EPOCH};

use serde::Serialize;
use walkdir::WalkDir;

use crate::characters::detect_characters;
use crate::network::MountTable;
use crate::structure::{detect_mod_structure, known_type, normalize_key};
use crate::{Error, Result};

const IGNORED_DIRECTORIES: &[&str] = &[".git", "__pycache__"];
pub const PREVIEW_FILENAMES: &[&str] = &[
    "preview.png",
    "preview.jpg",
    "preview.jpeg",
    "thumbnail.png",
    "thumbnail.jpg",
    "cover.png",
    "cover.jpg",
    "icon.png",
    "icon.jpg",
];
const MOD_MARKER_FILES: &[&str] = &["mod.json", "metadata.json", "character.txt", "characters.txt"];
const MAX_SCAN_DEPTH: usize = 4;

#[derive(Debug, Clone, Serialize)]
pub struct ModInfo {
    pub name: String,
    pub path: PathBuf,
    pub is_symlink: bool,
    pub is_network: bool,
    pub file_count: u64,
    pub ini_file_count: u64,
    pub total_size: Option<u64>,
    /// Unix-Zeitstempel in Sekunden.
    pub modified_at: Option<f64>,
    pub preview_path: Option<PathBuf>,
    pub error: Option<String>,
    pub characters: Vec<String>,
    pub mod_type: String,
    pub relative_path: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct ScanResult {
    pub root_path: PathBuf,
    pub is_network: bool,
    pub mods: Vec<ModInfo>,
    pub duration_seconds: f64,
}

/// Fortschritt: (aktuell, gesamt, Name)
pub type Progress<'a> = &'a (dyn Fn(usize, usize, &str) + Sync);

pub struct ModScanner<'a> {
    pub calculate_network_sizes: bool,
    pub cancel: Option<&'a AtomicBool>,
    mounts: MountTable,
}

impl<'a> Default for ModScanner<'a> {
    fn default() -> Self {
        Self::new()
    }
}

impl<'a> ModScanner<'a> {
    pub fn new() -> Self {
        Self { calculate_network_sizes: false, cancel: None, mounts: MountTable::load() }
    }

    pub fn with_cancel(mut self, cancel: &'a AtomicBool) -> Self {
        self.cancel = Some(cancel);
        self
    }

    fn check_cancelled(&self) -> Result<()> {
        match self.cancel {
            Some(flag) if flag.load(Ordering::Relaxed) => Err(Error::Cancelled),
            _ => Ok(()),
        }
    }

    pub fn scan(&self, root: &Path, progress: Option<Progress<'_>>) -> Result<ScanResult> {
        let started = Instant::now();
        if root.to_string_lossy().contains("://") {
            return Err(Error::Message(
                "Netzwerkadressen wie smb:// werden nicht direkt unterstützt. Binde das Netzlaufwerk \
                 zuerst unter /mnt, /media oder über GVFS ein."
                    .into(),
            ));
        }
        let root = crate::paths::expand_user(root);
        if !root.exists() {
            return Err(Error::Message(format!("Der Mods-Ordner existiert nicht: {}", root.display())));
        }
        if !root.is_dir() {
            return Err(Error::Message(format!("Der Mods-Pfad ist kein Verzeichnis: {}", root.display())));
        }

        let directories = self.find_mod_directories(&root)?;
        let total = directories.len();
        if let Some(report) = progress {
            report(0, total, "");
        }
        let mut mods = Vec::with_capacity(total);
        for (index, directory) in directories.iter().enumerate() {
            self.check_cancelled()?;
            let info = self.scan_mod_directory(&root, directory)?;
            if let Some(report) = progress {
                report(index + 1, total, &info.name);
            }
            mods.push(info);
        }
        Ok(ScanResult {
            is_network: self.mounts.is_network_path(&root),
            root_path: root,
            mods,
            duration_seconds: started.elapsed().as_secs_f64(),
        })
    }

    fn is_marker_file(name: &str) -> bool {
        let lower = name.to_lowercase();
        lower.ends_with(".ini") || MOD_MARKER_FILES.contains(&lower.as_str())
    }

    /// Findet tatsächliche Mod-Roots: Ordner mit direkter INI-/Metadaten-Datei.
    /// Tiefe INI-Pfade werden auf den logischen Mod-Root hochgezogen.
    pub fn find_mod_directories(&self, root: &Path) -> Result<Vec<PathBuf>> {
        let mut marker_dirs = Vec::new();
        let entries = match std::fs::read_dir(root) {
            Ok(entries) => entries,
            Err(error) if error.kind() == std::io::ErrorKind::PermissionDenied => {
                return Err(Error::Message(format!("Keine Leseberechtigung für: {}", root.display())))
            }
            Err(_) => return Ok(Vec::new()),
        };
        let mut root_dirs = child_directories(entries);
        root_dirs.sort_by_key(|p| file_name_key(p));
        for dir in root_dirs {
            self.scan_directory(&dir, 1, &mut marker_dirs)?;
        }

        let mut found: BTreeMap<String, PathBuf> = BTreeMap::new();
        for marker_dir in marker_dirs {
            let logical = logical_mod_root(root, &marker_dir);
            let key =
                std::fs::canonicalize(&logical).unwrap_or_else(|_| logical.clone()).to_string_lossy().to_lowercase();
            found.insert(key, logical);
        }
        let mut result: Vec<PathBuf> = found.into_values().collect();
        result.sort_by_key(|p| p.to_string_lossy().to_lowercase());
        result.dedup();
        Ok(result)
    }

    fn scan_directory(&self, directory: &Path, depth: usize, out: &mut Vec<PathBuf>) -> Result<()> {
        self.check_cancelled()?;
        if depth > MAX_SCAN_DEPTH + 3 {
            return Ok(());
        }
        let Ok(entries) = std::fs::read_dir(directory) else { return Ok(()) };
        let mut has_marker = false;
        let mut children = Vec::new();
        for entry in entries.flatten() {
            let name = entry.file_name().to_string_lossy().into_owned();
            if name.starts_with('.') {
                continue;
            }
            let Ok(file_type) = entry.file_type() else { continue };
            if file_type.is_file() {
                if Self::is_marker_file(&name) {
                    has_marker = true;
                }
            } else if file_type.is_dir() && !IGNORED_DIRECTORIES.contains(&name.as_str()) {
                children.push(entry.path());
            }
        }
        if has_marker {
            out.push(directory.to_path_buf());
            return Ok(());
        }
        children.sort_by_key(|p| file_name_key(p));
        for child in children {
            self.scan_directory(&child, depth + 1, out)?;
        }
        Ok(())
    }

    pub fn scan_mod_directory(&self, library_root: &Path, mod_directory: &Path) -> Result<ModInfo> {
        let mut errors: Vec<String> = Vec::new();
        let is_network = self.mounts.is_network_path(mod_directory);
        let calculate_size = !is_network || self.calculate_network_sizes;
        let structure = detect_mod_structure(library_root, mod_directory);

        let mut characters = detect_characters(mod_directory);
        if let Some(character) = &structure.character {
            if !characters.iter().any(|c| c.to_lowercase() == character.to_lowercase()) {
                characters.insert(0, character.clone());
            }
        }

        let modified_at = match std::fs::metadata(mod_directory).and_then(|m| m.modified()) {
            Ok(time) => time.duration_since(UNIX_EPOCH).ok().map(|d| d.as_secs_f64()),
            Err(error) => {
                errors.push(error.to_string());
                None
            }
        };

        let mut file_count = 0;
        let mut ini_file_count = 0;
        let mut total_size = 0;
        let mut preview_path = None;
        let walker = WalkDir::new(mod_directory).follow_links(false).into_iter().filter_entry(|entry| {
            entry.depth() == 0
                || !entry.file_type().is_dir()
                || !IGNORED_DIRECTORIES.contains(&entry.file_name().to_string_lossy().as_ref())
        });
        for entry in walker {
            self.check_cancelled()?;
            let entry = match entry {
                Ok(entry) => entry,
                Err(error) => {
                    errors.push(error.to_string());
                    continue;
                }
            };
            if entry.file_type().is_dir() {
                continue;
            }
            file_count += 1;
            let lower = entry.file_name().to_string_lossy().to_lowercase();
            if lower.ends_with(".ini") {
                ini_file_count += 1;
            }
            if preview_path.is_none() && PREVIEW_FILENAMES.contains(&lower.as_str()) {
                preview_path = Some(entry.path().to_path_buf());
            }
            if calculate_size {
                // Python nutzt stat() (folgt Symlinks).
                match std::fs::metadata(entry.path()) {
                    Ok(meta) => total_size += meta.len(),
                    Err(error) if errors.len() < 5 => errors.push(error.to_string()),
                    Err(_) => {}
                }
            }
        }

        let mut unique = Vec::new();
        for error in errors {
            if !unique.contains(&error) {
                unique.push(error);
            }
        }
        let error = (!unique.is_empty()).then(|| unique.into_iter().take(3).collect::<Vec<_>>().join("; "));

        Ok(ModInfo {
            name: mod_directory.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default(),
            path: mod_directory.to_path_buf(),
            is_symlink: crate::paths::is_symlink(mod_directory),
            is_network,
            file_count,
            ini_file_count,
            total_size: calculate_size.then_some(total_size),
            modified_at,
            preview_path,
            error,
            characters,
            mod_type: structure.mod_type,
            relative_path: structure.relative_path,
        })
    }
}

fn child_directories(entries: std::fs::ReadDir) -> Vec<PathBuf> {
    entries
        .flatten()
        .filter(|entry| {
            let name = entry.file_name().to_string_lossy().into_owned();
            !name.starts_with('.')
                && !IGNORED_DIRECTORIES.contains(&name.as_str())
                && entry.file_type().map(|t| t.is_dir()).unwrap_or(false)
        })
        .map(|entry| entry.path())
        .collect()
}

fn file_name_key(path: &Path) -> String {
    path.file_name().map(|n| n.to_string_lossy().to_lowercase()).unwrap_or_default()
}

/// Hebt `Charakter / Character Skin / Mod / Body / mod.ini` auf `.../Mod` an.
pub fn logical_mod_root(library_root: &Path, marker_dir: &Path) -> PathBuf {
    let Ok(relative) = marker_dir.strip_prefix(library_root) else { return marker_dir.to_path_buf() };
    let parts: Vec<_> = relative.components().collect();
    if parts.len() < 2 {
        return marker_dir.to_path_buf();
    }
    for (index, part) in parts[..parts.len() - 1].iter().enumerate() {
        if known_type(&normalize_key(&part.as_os_str().to_string_lossy())).is_none() {
            continue;
        }
        let mut root = library_root.to_path_buf();
        for component in &parts[..=index + 1] {
            root.push(component.as_os_str());
        }
        return root;
    }
    marker_dir.to_path_buf()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn touch(path: &Path) {
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, b"x").unwrap();
    }

    #[test]
    fn finds_logical_roots() {
        let temp = tempfile::tempdir().unwrap();
        let lib = temp.path();
        touch(&lib.join("Furina/Character Skin/Summer/Body/mod.ini"));
        touch(&lib.join("Furina/Character Skin/Summer/Hair/hair.ini"));
        touch(&lib.join("Furina/Character Skin/Summer/preview.png"));
        touch(&lib.join("Loose Mod/merged.ini"));
        touch(&lib.join(".hidden/x.ini"));
        touch(&lib.join("NoMod/readme.txt"));

        let scanner = ModScanner::new();
        let result = scanner.scan(lib, None).unwrap();
        let names: Vec<_> = result.mods.iter().map(|m| m.name.as_str()).collect();
        assert_eq!(names, vec!["Summer", "Loose Mod"]);
        let summer = &result.mods[0];
        assert_eq!(summer.ini_file_count, 2);
        assert_eq!(summer.file_count, 3);
        assert_eq!(summer.mod_type, "Character Skin");
        assert_eq!(summer.characters, vec!["Furina"]);
        assert!(summer.preview_path.is_some());
        assert_eq!(summer.total_size, Some(3));
    }

    #[test]
    fn cancel_stops_scan() {
        let temp = tempfile::tempdir().unwrap();
        touch(&temp.path().join("A/a.ini"));
        let flag = AtomicBool::new(true);
        let scanner = ModScanner::new().with_cancel(&flag);
        assert!(matches!(scanner.scan(temp.path(), None), Err(Error::Cancelled)));
    }
}
