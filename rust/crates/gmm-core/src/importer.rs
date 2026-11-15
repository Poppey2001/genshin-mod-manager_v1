//! Import von Mod-Ordnern und Archiven in die Bibliothek
//! (Port von `app/services/mod_importer.py`).
//!
//! Aus Ordnern und Archiven wird nur der eigentliche Mod-Ordner übernommen
//! (README, Screenshots usw. daneben bleiben draußen). Enthält eine Quelle
//! mehrere getrennte Mods, wird sie aus Sicherheitsgründen nicht kopiert.

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};
use std::time::Instant;

use serde::{Deserialize, Serialize};

use crate::archive::{archive_name_without_suffix, extract_archive_securely, is_supported_archive};
use crate::manager::{copy_tree, MANAGER_MARKER, NEXT_MANAGER_MARKER};
use crate::paths::{absolute, path_exists, paths_overlap, sanitize_path_segment};
use crate::{Error, Result};

const MOD_MARKER_FILES: &[&str] = &["mod.json", "metadata.json", "character.txt", "characters.txt"];
const MAX_CANDIDATE_DEPTH: usize = 6;

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ConflictPolicy {
    /// Bei gleichem Namen `Name (2)` usw. verwenden.
    #[default]
    Rename,
    /// Vorhandene Mods nicht anrühren und den Import überspringen.
    Skip,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ImportOptions {
    pub character: Option<String>,
    pub mod_type: Option<String>,
    #[serde(default)]
    pub conflict_policy: ConflictPolicy,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ImportStatus {
    Imported,
    Skipped,
    Failed,
}

#[derive(Debug, Clone, Serialize)]
pub struct ImportItemResult {
    pub source: PathBuf,
    pub destination: Option<PathBuf>,
    pub status: ImportStatus,
    pub message: String,
    /// Warnungen der Archivprüfung (z. B. enthaltene .exe-Dateien).
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ImportBatchResult {
    pub items: Vec<ImportItemResult>,
    pub duration_seconds: f64,
    pub imported_count: usize,
    pub skipped_count: usize,
    pub failed_count: usize,
}

pub type ImportProgress<'a> = &'a (dyn Fn(usize, usize, &str) + Sync);

pub struct ModImporter<'a> {
    cancel: Option<&'a AtomicBool>,
    temp_root: Option<PathBuf>,
}

impl<'a> Default for ModImporter<'a> {
    fn default() -> Self {
        Self::new()
    }
}

impl<'a> ModImporter<'a> {
    pub fn new() -> Self {
        Self { cancel: None, temp_root: None }
    }

    pub fn with_cancel(mut self, cancel: &'a AtomicBool) -> Self {
        self.cancel = Some(cancel);
        self
    }

    /// Ordner für temporäre Extraktionen (Standard: System-Temp).
    pub fn with_temp_root(mut self, root: PathBuf) -> Self {
        self.temp_root = Some(root);
        self
    }

    fn check_cancelled(&self) -> Result<()> {
        match self.cancel {
            Some(flag) if flag.load(Ordering::Relaxed) => Err(Error::Cancelled),
            _ => Ok(()),
        }
    }

    pub fn import_sources(
        &self,
        sources: &[PathBuf],
        library_root: &Path,
        options: &ImportOptions,
        progress: Option<ImportProgress<'_>>,
    ) -> Result<ImportBatchResult> {
        let started = Instant::now();
        let library = absolute(library_root);
        std::fs::create_dir_all(&library).map_err(|error| {
            Error::Message(format!(
                "Die Mod-Bibliothek konnte nicht erstellt werden.\n\nPfad: {}\n\n{error}",
                library.display()
            ))
        })?;
        let target_root = build_target_root(&library, options)?;
        std::fs::create_dir_all(&target_root).map_err(|error| {
            Error::Message(format!(
                "Der Import-Zielordner konnte nicht erstellt werden.\n\nPfad: {}\n\n{error}",
                target_root.display()
            ))
        })?;

        let total = sources.len();
        let mut items = Vec::with_capacity(total);
        for (index, source) in sources.iter().enumerate() {
            self.check_cancelled()?;
            let source = absolute(source);
            let name = source.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
            if let Some(report) = progress {
                report(index, total, &name);
            }
            let item = match self.import_source(&source, &library, &target_root, options) {
                Ok(item) => item,
                Err(Error::Cancelled) => return Err(Error::Cancelled),
                Err(error) => ImportItemResult {
                    source: source.clone(),
                    destination: None,
                    status: ImportStatus::Failed,
                    message: error.to_string(),
                    warnings: vec![],
                },
            };
            items.push(item);
            if let Some(report) = progress {
                report(index + 1, total, &name);
            }
        }
        let count = |status| items.iter().filter(|item| item.status == status).count();
        Ok(ImportBatchResult {
            imported_count: count(ImportStatus::Imported),
            skipped_count: count(ImportStatus::Skipped),
            failed_count: count(ImportStatus::Failed),
            duration_seconds: started.elapsed().as_secs_f64(),
            items,
        })
    }

    fn import_source(
        &self,
        source: &Path,
        library: &Path,
        target_root: &Path,
        options: &ImportOptions,
    ) -> Result<ImportItemResult> {
        let result = |status, destination: Option<PathBuf>, message: &str| ImportItemResult {
            source: source.to_path_buf(),
            destination,
            status,
            message: message.to_string(),
            warnings: vec![],
        };
        if !source.exists() {
            return Ok(result(ImportStatus::Failed, None, "Die Quelle existiert nicht."));
        }
        if source.is_dir() {
            if paths_overlap(source, library) {
                return Ok(result(
                    ImportStatus::Skipped,
                    None,
                    "Der Ordner liegt bereits innerhalb der Mod-Bibliothek oder enthält diese.",
                ));
            }
            let display = source.file_name().unwrap_or_default().to_string_lossy().into_owned();
            let mod_source = self.select_mod_source(source, &display)?;
            let name = mod_source.file_name().unwrap_or_default().to_string_lossy().into_owned();
            let Some(destination) = select_destination(target_root, &name, options.conflict_policy)? else {
                return Ok(result(ImportStatus::Skipped, None, "Ein gleichnamiger Mod existiert bereits."));
            };
            self.copy_tree_atomic(&mod_source, &destination)?;
            return Ok(result(ImportStatus::Imported, Some(destination), "Mod-Ordner wurde importiert."));
        }
        if source.is_file() && is_supported_archive(source) {
            return self.import_archive(source, target_root, options);
        }
        Ok(result(ImportStatus::Skipped, None, "Nicht unterstützter Dateityp."))
    }

    fn import_archive(&self, archive: &Path, target_root: &Path, options: &ImportOptions) -> Result<ImportItemResult> {
        self.check_cancelled()?;
        let temp_parent = self.temp_root.clone().unwrap_or_else(std::env::temp_dir);
        std::fs::create_dir_all(&temp_parent)?;
        let temp = TempDir::new(&temp_parent)?;
        let extraction_root = temp.path.join("extract");
        let report = extract_archive_securely(archive, &extraction_root, self.cancel)?;
        self.check_cancelled()?;

        let display = archive.file_name().unwrap_or_default().to_string_lossy().into_owned();
        let mod_source = self.select_mod_source(&extraction_root, &display)?;
        let requested = if mod_source == extraction_root {
            archive_name_without_suffix(archive)
        } else {
            sanitize_path_segment(&mod_source.file_name().unwrap_or_default().to_string_lossy())
        };
        let warnings = report.warnings().filter_map(|issue| issue.member.clone()).collect();
        let Some(destination) = select_destination(target_root, &requested, options.conflict_policy)? else {
            return Ok(ImportItemResult {
                source: archive.to_path_buf(),
                destination: None,
                status: ImportStatus::Skipped,
                message: "Ein gleichnamiger Mod existiert bereits.".into(),
                warnings,
            });
        };
        self.copy_tree_atomic(&mod_source, &destination)?;
        Ok(ImportItemResult {
            source: archive.to_path_buf(),
            destination: Some(destination),
            status: ImportStatus::Imported,
            message: "Archiv wurde importiert.".into(),
            warnings,
        })
    }

    /// Findet einen eindeutigen Mod-Ordner innerhalb von `root`.
    fn select_mod_source(&self, root: &Path, display_name: &str) -> Result<PathBuf> {
        if !root.is_dir() {
            return Err(Error::Message(format!("Die Mod-Quelle ist kein Ordner: {}", root.display())));
        }
        if has_direct_mod_marker(root) {
            return Ok(root.to_path_buf());
        }
        let mut candidates = Vec::new();
        self.find_candidates(root, root, 0, &mut candidates)?;
        match candidates.len() {
            0 => Err(Error::Message(format!(
                "Es wurde kein gültiger Mod-Ordner mit einer INI- oder Metadaten-Datei gefunden: {display_name}"
            ))),
            1 => Ok(candidates.remove(0)),
            _ => {
                if let Some(common) = common_parent(&candidates).filter(|common| common != root) {
                    return Ok(common);
                }
                let mut names: Vec<String> = candidates
                    .iter()
                    .take(8)
                    .map(|c| c.strip_prefix(root).unwrap_or(c).to_string_lossy().replace('\\', "/"))
                    .collect();
                if candidates.len() > 8 {
                    names.push("...".into());
                }
                Err(Error::Message(format!(
                    "Die Quelle enthält mehrere voneinander getrennte Mod-Ordner. Aus Sicherheitsgründen wird \
                     nicht der komplette Ordner kopiert. Importiere die Mods einzeln.\n\nGefunden: {}",
                    names.join(", ")
                )))
            }
        }
    }

    fn find_candidates(&self, root: &Path, directory: &Path, depth: usize, out: &mut Vec<PathBuf>) -> Result<()> {
        self.check_cancelled()?;
        if depth > MAX_CANDIDATE_DEPTH {
            return Ok(());
        }
        if directory != root && has_direct_mod_marker(directory) {
            out.push(directory.to_path_buf());
            return Ok(());
        }
        let Ok(entries) = std::fs::read_dir(directory) else { return Ok(()) };
        let mut children: Vec<PathBuf> = entries
            .flatten()
            .filter(|entry| {
                let name = entry.file_name().to_string_lossy().into_owned();
                entry.file_type().map(|t| t.is_dir()).unwrap_or(false) && !name.starts_with('.') && name != "__MACOSX"
            })
            .map(|entry| entry.path())
            .collect();
        children.sort_by_key(|p| p.file_name().map(|n| n.to_string_lossy().to_lowercase()));
        for child in children {
            self.find_candidates(root, &child, depth + 1, out)?;
        }
        Ok(())
    }

    fn copy_tree_atomic(&self, source: &Path, destination: &Path) -> Result<()> {
        self.check_cancelled()?;
        let parent = destination.parent().unwrap_or(Path::new("."));
        let name = destination.file_name().unwrap_or_default().to_string_lossy();
        let temporary = parent.join(format!(".{name}.xxmimm-import-{}.tmp", uuid::Uuid::new_v4().simple()));
        let result = (|| -> Result<()> {
            copy_tree(source, &temporary)?;
            for marker in [MANAGER_MARKER, NEXT_MANAGER_MARKER] {
                let _ = std::fs::remove_file(temporary.join(marker));
            }
            self.check_cancelled()?;
            if path_exists(destination) {
                return Err(Error::Message(
                    "Das Importziel wurde während des Imports von einem anderen Vorgang erstellt.".into(),
                ));
            }
            std::fs::rename(&temporary, destination)?;
            Ok(())
        })();
        if result.is_err() && path_exists(&temporary) {
            let _ = std::fs::remove_dir_all(&temporary);
        }
        result
    }
}

/// Temporärer Ordner, der beim Verlassen gelöscht wird.
struct TempDir {
    path: PathBuf,
}

impl TempDir {
    fn new(parent: &Path) -> Result<Self> {
        let path = parent.join(format!("xxmimm-import-{}", uuid::Uuid::new_v4().simple()));
        std::fs::create_dir_all(&path)?;
        Ok(Self { path })
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.path);
    }
}

pub fn is_supported_import_source(path: &Path) -> bool {
    path.is_dir() || (path.is_file() && is_supported_archive(path))
}

fn has_direct_mod_marker(directory: &Path) -> bool {
    let Ok(entries) = std::fs::read_dir(directory) else { return false };
    entries.flatten().any(|entry| {
        if !entry.path().is_file() {
            return false;
        }
        let name = entry.file_name().to_string_lossy().to_lowercase();
        name.ends_with(".ini") || MOD_MARKER_FILES.contains(&name.as_str())
    })
}

fn common_parent(paths: &[PathBuf]) -> Option<PathBuf> {
    let first: Vec<_> = paths.first()?.components().collect();
    let mut length = first.len();
    for path in &paths[1..] {
        length = first.iter().zip(path.components()).take(length).take_while(|(a, b)| **a == *b).count();
    }
    (length > 0).then(|| first[..length].iter().collect())
}

fn select_destination(target_root: &Path, requested: &str, policy: ConflictPolicy) -> Result<Option<PathBuf>> {
    let safe = sanitize_path_segment(requested);
    if safe.is_empty() {
        return Err(Error::Message("Für den Mod konnte kein gültiger Zielname erzeugt werden.".into()));
    }
    let destination = target_root.join(&safe);
    if !path_exists(&destination) {
        return Ok(Some(destination));
    }
    if policy == ConflictPolicy::Skip {
        return Ok(None);
    }
    Ok((2..).map(|counter| target_root.join(format!("{safe} ({counter})"))).find(|candidate| !path_exists(candidate)))
}

fn build_target_root(library: &Path, options: &ImportOptions) -> Result<PathBuf> {
    let character = options.character.as_deref().map(str::trim).unwrap_or("");
    let mod_type = options.mod_type.as_deref().map(str::trim).unwrap_or("");
    if !mod_type.is_empty() && character.is_empty() {
        return Err(Error::Message("Für einen Mod-Typ muss auch ein Charakter angegeben werden.".into()));
    }
    let mut root = library.to_path_buf();
    if !character.is_empty() {
        root.push(sanitize_path_segment(character));
    }
    if !mod_type.is_empty() {
        root.push(sanitize_path_segment(mod_type));
    }
    Ok(root)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    fn touch(path: &Path) {
        std::fs::create_dir_all(path.parent().unwrap()).unwrap();
        std::fs::write(path, b"x").unwrap();
    }

    #[test]
    fn imports_directory_and_archive_with_rename() {
        let temp = tempfile::tempdir().unwrap();
        let library = temp.path().join("lib");
        // Ordner mit Wrapper, README daneben wird ignoriert.
        touch(&temp.path().join("download/Readme.txt"));
        touch(&temp.path().join("download/Nice Mod/mod.ini"));
        // Archiv mit gleichem Mod-Namen.
        let archive = temp.path().join("Nice Mod.zip");
        let mut writer = zip::ZipWriter::new(std::fs::File::create(&archive).unwrap());
        writer.start_file("mod.ini", zip::write::SimpleFileOptions::default()).unwrap();
        writer.write_all(b"[x]").unwrap();
        writer.finish().unwrap();

        let options =
            ImportOptions { character: Some("Furina".into()), mod_type: Some("Skins".into()), ..Default::default() };
        let importer = ModImporter::new().with_temp_root(temp.path().join("tmp"));
        let result = importer
            .import_sources(
                &[temp.path().join("download"), archive.clone(), temp.path().join("missing")],
                &library,
                &options,
                None,
            )
            .unwrap();
        assert_eq!(result.imported_count, 2);
        assert_eq!(result.failed_count, 1);
        assert!(library.join("Furina/Skins/Nice Mod/mod.ini").is_file());
        assert!(!library.join("Furina/Skins/Nice Mod/Readme.txt").exists());
        assert!(library.join("Furina/Skins/Nice Mod (2)/mod.ini").is_file());
        assert!(std::fs::read_dir(temp.path().join("tmp")).unwrap().next().is_none());

        let skip = ImportOptions { conflict_policy: ConflictPolicy::Skip, ..options };
        let again = importer.import_sources(&[archive], &library, &skip, None).unwrap();
        assert_eq!(again.skipped_count, 1);
    }

    #[test]
    fn multiple_separate_mods_are_refused() {
        let temp = tempfile::tempdir().unwrap();
        touch(&temp.path().join("pack/A/a.ini"));
        touch(&temp.path().join("pack/B/b.ini"));
        let result = ModImporter::new()
            .import_sources(&[temp.path().join("pack")], &temp.path().join("lib"), &ImportOptions::default(), None)
            .unwrap();
        assert_eq!(result.failed_count, 1);
        assert!(result.items[0].message.contains("mehrere"));
    }

    #[test]
    fn mod_type_requires_character() {
        let options = ImportOptions { mod_type: Some("Skins".into()), ..Default::default() };
        assert!(build_target_root(Path::new("/lib"), &options).is_err());
    }
}
