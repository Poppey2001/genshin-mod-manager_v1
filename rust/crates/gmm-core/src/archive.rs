//! Sichere Archiv-Prüfung und -Extraktion
//! (Port von `app/services/archive_security.py` und `archive_extractor.py`).
//!
//! Jedes Archiv wird vor dem Entpacken vollständig geprüft. Blockiert werden
//! Pfad-Traversal, absolute Pfade, Links, Spezialdateien, verschlüsselte
//! Einträge, doppelte Ziele und Archiv-Bomben. Ausführbare Dateien und
//! Binärmodule erzeugen Warnungen. Nach dem Entpacken wird der Zielbaum noch
//! einmal geprüft.

use std::collections::HashSet;
use std::fs::File;
use std::io::{BufReader, Read, Write};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicBool, Ordering};

use serde::Serialize;

use crate::{Error, Result};

pub const MAX_ARCHIVE_ENTRIES: u64 = 100_000;
pub const MAX_TOTAL_UNCOMPRESSED: u64 = 32 * 1024 * 1024 * 1024;
pub const MAX_SINGLE_FILE_SIZE: u64 = 8 * 1024 * 1024 * 1024;
const MAX_PATH_LENGTH: usize = 1024;
const MAX_COMPONENT_LENGTH: usize = 255;
const MAX_COMPRESSION_RATIO: f64 = 1000.0;
const MIN_RATIO_CHECK_SIZE: u64 = 64 * 1024 * 1024;
const MAX_REPORTED_WARNING_FILES: usize = 25;

const EXECUTABLE_WARNING_SUFFIXES: &[&str] = &[
    "exe", "com", "bat", "cmd", "ps1", "vbs", "vbe", "js", "jse", "wsf", "wsh", "scr", "msi", "msp", "reg", "lnk",
    "jar", "sh", "desktop", "py",
];
const BINARY_REVIEW_SUFFIXES: &[&str] = &["dll", "asi", "so", "dylib"];

pub const SUPPORTED_ARCHIVE_SUFFIXES: &[&str] =
    &[".tar.bz2", ".tar.gz", ".tar.xz", ".tbz2", ".tgz", ".txz", ".zip", ".7z", ".rar", ".tar"];

const S_IFMT: u32 = 0o170000;
const S_IFREG: u32 = 0o100000;
const S_IFDIR: u32 = 0o040000;
const S_IFLNK: u32 = 0o120000;
const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
const FILE_ATTRIBUTE_UNIX_EXTENSION: u32 = 0x8000;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum TarCompression {
    None,
    Gzip,
    Bzip2,
    Xz,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum ArchiveKind {
    Zip,
    SevenZip,
    Rar,
    Tar(TarCompression),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Severity {
    Warning,
    Block,
}

#[derive(Debug, Clone, Serialize)]
pub struct ArchiveIssue {
    pub severity: Severity,
    pub code: &'static str,
    pub message: String,
    pub member: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct SecurityReport {
    pub source: PathBuf,
    pub kind: ArchiveKind,
    pub entry_count: u64,
    pub total_uncompressed: u64,
    pub issues: Vec<ArchiveIssue>,
    pub warning_files: Vec<String>,
    pub blocked: bool,
}

impl SecurityReport {
    fn new(source: PathBuf, kind: ArchiveKind) -> Self {
        Self {
            source,
            kind,
            entry_count: 0,
            total_uncompressed: 0,
            issues: vec![],
            warning_files: vec![],
            blocked: false,
        }
    }

    pub fn blocking_issues(&self) -> impl Iterator<Item = &ArchiveIssue> {
        self.issues.iter().filter(|issue| issue.severity == Severity::Block)
    }

    pub fn warnings(&self) -> impl Iterator<Item = &ArchiveIssue> {
        self.issues.iter().filter(|issue| issue.severity == Severity::Warning)
    }

    fn block(&mut self, code: &'static str, message: impl Into<String>, member: Option<&str>) {
        self.blocked = true;
        self.issues.push(ArchiveIssue {
            severity: Severity::Block,
            code,
            message: message.into(),
            member: member.map(str::to_string),
        });
    }

    fn warn_file(&mut self, path: &str, message: &str) {
        if self.warning_files.len() < MAX_REPORTED_WARNING_FILES {
            self.warning_files.push(path.to_string());
        }
        self.issues.push(ArchiveIssue {
            severity: Severity::Warning,
            code: "review_file",
            message: message.to_string(),
            member: Some(path.to_string()),
        });
    }
}

/// Ein Archiveintrag, wie er für die Prüfung benötigt wird.
struct Member {
    name: String,
    size: u64,
    compressed: Option<u64>,
    is_dir: bool,
    is_link: bool,
    is_special: bool,
    encrypted: bool,
}

fn lower_name(path: &Path) -> String {
    path.file_name().map(|n| n.to_string_lossy().to_lowercase()).unwrap_or_default()
}

pub fn is_supported_archive(path: &Path) -> bool {
    let name = lower_name(path);
    SUPPORTED_ARCHIVE_SUFFIXES.iter().any(|suffix| name.ends_with(suffix))
}

pub fn detect_archive_kind(path: &Path) -> Result<ArchiveKind> {
    let name = lower_name(path);
    let kind = if name.ends_with(".zip") {
        ArchiveKind::Zip
    } else if name.ends_with(".7z") {
        ArchiveKind::SevenZip
    } else if name.ends_with(".rar") {
        ArchiveKind::Rar
    } else if name.ends_with(".tar") {
        ArchiveKind::Tar(TarCompression::None)
    } else if name.ends_with(".tar.gz") || name.ends_with(".tgz") {
        ArchiveKind::Tar(TarCompression::Gzip)
    } else if name.ends_with(".tar.bz2") || name.ends_with(".tbz2") {
        ArchiveKind::Tar(TarCompression::Bzip2)
    } else if name.ends_with(".tar.xz") || name.ends_with(".txz") {
        ArchiveKind::Tar(TarCompression::Xz)
    } else {
        return Err(Error::Message(format!(
            "Nicht unterstütztes Archivformat: {}",
            path.file_name().unwrap_or_default().to_string_lossy()
        )));
    };
    Ok(kind)
}

/// Archivname ohne Endung, als sicherer Ordnername.
pub fn archive_name_without_suffix(path: &Path) -> String {
    let name = path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();
    let lower = name.to_lowercase();
    let mut suffixes = SUPPORTED_ARCHIVE_SUFFIXES.to_vec();
    suffixes.sort_by_key(|s| std::cmp::Reverse(s.len()));
    let stem = suffixes
        .iter()
        .find(|suffix| lower.ends_with(*suffix))
        .map(|suffix| name[..name.len() - suffix.len()].to_string())
        .unwrap_or(name);
    crate::paths::sanitize_path_segment(&stem)
}

fn archive_error(source: &Path, error: impl std::fmt::Display) -> Error {
    Error::Message(format!(
        "Archiv „{}“ konnte nicht untersucht werden.\n\n{error}",
        source.file_name().unwrap_or_default().to_string_lossy()
    ))
}

fn tar_reader(source: &Path, compression: TarCompression) -> std::io::Result<Box<dyn Read>> {
    let file = BufReader::new(File::open(source)?);
    Ok(match compression {
        TarCompression::None => Box::new(file),
        TarCompression::Gzip => Box::new(flate2::read::GzDecoder::new(file)),
        TarCompression::Bzip2 => Box::new(bzip2::read::BzDecoder::new(file)),
        TarCompression::Xz => Box::new(xz2::read::XzDecoder::new(file)),
    })
}

fn list_members(source: &Path, kind: ArchiveKind, report: &mut SecurityReport) -> Result<Vec<Member>> {
    let mut members = Vec::new();
    match kind {
        ArchiveKind::Zip => {
            let mut archive = zip::ZipArchive::new(File::open(source)?).map_err(|e| archive_error(source, e))?;
            for index in 0..archive.len() {
                let entry = archive.by_index_raw(index).map_err(|e| archive_error(source, e))?;
                let file_type = entry.unix_mode().unwrap_or(0) & S_IFMT;
                let is_link = file_type == S_IFLNK || entry.is_symlink();
                members.push(Member {
                    name: entry.name().map_err(|e| archive_error(source, e))?.into_owned(),
                    size: entry.size(),
                    compressed: Some(entry.compressed_size()),
                    is_dir: entry.is_dir(),
                    is_link,
                    is_special: !matches!(file_type, 0 | S_IFREG | S_IFDIR | S_IFLNK),
                    encrypted: entry.encrypted(),
                });
            }
        }
        ArchiveKind::Tar(compression) => {
            let mut archive = tar::Archive::new(tar_reader(source, compression)?);
            for entry in archive.entries().map_err(|e| archive_error(source, e))? {
                let entry = entry.map_err(|e| archive_error(source, e))?;
                let kind = entry.header().entry_type();
                let is_link = kind.is_symlink() || kind.is_hard_link();
                let is_file = kind.is_file() || kind == tar::EntryType::Continuous;
                // PAX/GNU-Metadaten sind keine eigenen Dateien.
                if kind.is_pax_global_extensions()
                    || kind.is_pax_local_extensions()
                    || kind.is_gnu_longname()
                    || kind.is_gnu_longlink()
                {
                    continue;
                }
                let name = entry.path().map_err(|e| archive_error(source, e))?.to_string_lossy().into_owned();
                members.push(Member {
                    name,
                    size: if is_file { entry.size() } else { 0 },
                    compressed: None,
                    is_dir: kind.is_dir(),
                    is_link,
                    is_special: !(is_file || kind.is_dir() || is_link),
                    encrypted: false,
                });
            }
        }
        ArchiveKind::SevenZip => {
            let archive = match sevenz_rust2::Archive::open(source) {
                Ok(archive) => archive,
                Err(sevenz_rust2::Error::PasswordRequired | sevenz_rust2::Error::MaybeBadPassword(_)) => {
                    report.block(
                        "encrypted_archive",
                        "Passwortgeschützte Archive werden derzeit nicht importiert.",
                        None,
                    );
                    return Ok(members);
                }
                Err(error) => return Err(archive_error(source, error)),
            };
            for (index, entry) in archive.files.iter().enumerate() {
                let attributes = if entry.has_windows_attributes { entry.windows_attributes } else { 0 };
                let unix_type =
                    if attributes & FILE_ATTRIBUTE_UNIX_EXTENSION != 0 { (attributes >> 16) & S_IFMT } else { 0 };
                let is_link = attributes & FILE_ATTRIBUTE_REPARSE_POINT != 0 || unix_type == S_IFLNK;
                members.push(Member {
                    name: entry.name.clone(),
                    size: entry.size,
                    compressed: (entry.compressed_size > 0).then_some(entry.compressed_size),
                    is_dir: entry.is_directory,
                    is_link,
                    is_special: entry.is_anti_item || !matches!(unix_type, 0 | S_IFREG | S_IFDIR | S_IFLNK),
                    encrypted: entry.has_stream && archive.is_file_encrypted(index),
                });
            }
        }
        ArchiveKind::Rar => {
            let listing = unrar::Archive::new(source).open_for_listing().map_err(|e| archive_error(source, e))?;
            if listing.has_encrypted_headers() {
                report.block("encrypted_archive", "Passwortgeschützte Archive werden derzeit nicht importiert.", None);
                return Ok(members);
            }
            for header in listing {
                let header = header.map_err(|e| archive_error(source, e))?;
                let attributes = header.file_attr;
                let unix_type = attributes & S_IFMT;
                let is_link = attributes & FILE_ATTRIBUTE_REPARSE_POINT != 0 || unix_type == S_IFLNK;
                members.push(Member {
                    name: header.filename.to_string_lossy().into_owned(),
                    size: header.unpacked_size,
                    compressed: None,
                    is_dir: header.is_directory(),
                    is_link,
                    is_special: header.is_split(),
                    encrypted: header.is_encrypted(),
                });
            }
        }
    }
    Ok(members)
}

/// Prüft ein Archiv, ohne es zu entpacken.
pub fn inspect_archive(path: &Path) -> Result<SecurityReport> {
    let source = crate::paths::absolute(path);
    if !source.is_file() {
        return Err(Error::Message(format!("Archiv wurde nicht gefunden:\n{}", source.display())));
    }
    let kind = detect_archive_kind(&source)?;
    let mut report = SecurityReport::new(source.clone(), kind);
    let members = list_members(&source, kind, &mut report)?;
    let mut seen = HashSet::new();
    for member in members {
        inspect_member(&mut report, &mut seen, &member);
        if report.entry_count > MAX_ARCHIVE_ENTRIES {
            break;
        }
    }
    let archive_size = source.metadata().map(|m| m.len()).unwrap_or(0);
    if archive_size > 0
        && report.total_uncompressed >= MIN_RATIO_CHECK_SIZE
        && report.total_uncompressed as f64 / archive_size as f64 > MAX_COMPRESSION_RATIO
    {
        report.block("total_compression_ratio", "Die Gesamt-Kompressionsrate des Archivs ist ungewöhnlich hoch.", None);
    }
    Ok(report)
}

fn inspect_member(report: &mut SecurityReport, seen: &mut HashSet<String>, member: &Member) {
    report.entry_count += 1;
    if report.entry_count > MAX_ARCHIVE_ENTRIES {
        report.block("too_many_entries", "Das Archiv enthält zu viele Dateien.", None);
        return;
    }
    let name = member.name.as_str();
    let relative = match safe_member_relative_path(name) {
        Ok(path) => path,
        Err(error) => {
            report.block("unsafe_path", error.to_string(), Some(name));
            return;
        }
    };
    let key = relative.to_string_lossy().replace('\\', "/").to_lowercase();
    if !seen.insert(key) {
        report.block("duplicate_path", "Mehrere Archiveinträge würden auf denselben Zielpfad geschrieben.", Some(name));
    }
    if member.is_link {
        report.block(
            "link",
            "Symbolische Links, Hardlinks und Junctions werden aus Sicherheitsgründen nicht importiert.",
            Some(name),
        );
    }
    if member.is_special {
        report.block("special_file", "Das Archiv enthält einen nicht unterstützten speziellen Dateityp.", Some(name));
    }
    if member.encrypted {
        report.block("encrypted_member", "Passwortgeschützte Dateien werden derzeit nicht importiert.", Some(name));
    }
    if member.is_dir {
        return;
    }
    report.total_uncompressed = report.total_uncompressed.saturating_add(member.size);
    if member.size > MAX_SINGLE_FILE_SIZE {
        report.block(
            "single_file_too_large",
            "Eine einzelne Datei überschreitet das erlaubte Größenlimit.",
            Some(name),
        );
    }
    if report.total_uncompressed > MAX_TOTAL_UNCOMPRESSED {
        report.block("archive_too_large", "Die entpackte Gesamtgröße überschreitet das Sicherheitslimit.", None);
    }
    if let Some(compressed) = member.compressed.filter(|c| *c > 0) {
        if member.size >= MIN_RATIO_CHECK_SIZE && member.size as f64 / compressed as f64 > MAX_COMPRESSION_RATIO {
            report.block(
                "compression_ratio",
                "Die Kompressionsrate ist ungewöhnlich hoch und könnte auf eine Archiv-Bombe hinweisen.",
                Some(name),
            );
        }
    }
    let display = relative.to_string_lossy().replace('\\', "/");
    let suffix = relative.extension().map(|e| e.to_string_lossy().to_lowercase()).unwrap_or_default();
    if EXECUTABLE_WARNING_SUFFIXES.contains(&suffix.as_str()) {
        report.warn_file(&display, "Das Archiv enthält eine ausführbare oder skriptbasierte Datei.");
    } else if BINARY_REVIEW_SUFFIXES.contains(&suffix.as_str()) {
        report.warn_file(
            &display,
            "Das Archiv enthält ein Binärmodul. Das kann bei XXMI-Mods legitim sein, sollte aber bewusst geprüft werden.",
        );
    }
}

const WINDOWS_RESERVED: &[&str] = &[
    "CON", "PRN", "AUX", "NUL", "CLOCK$", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

pub(crate) fn is_windows_reserved(component: &str) -> bool {
    let device = component.split('.').next().unwrap_or("").to_uppercase();
    WINDOWS_RESERVED.contains(&device.as_str())
}

/// Wandelt einen Archivpfad in einen sicheren relativen Pfad um.
pub fn safe_member_relative_path(name: &str) -> Result<PathBuf> {
    let fail = |message: &str| Err(Error::Message(message.to_string()));
    if name.contains('\0') {
        return fail("Archivpfad enthält ein Null-Zeichen.");
    }
    let normalized = name.replace('\\', "/");
    if normalized.chars().count() > MAX_PATH_LENGTH {
        return fail("Archivpfad ist zu lang.");
    }
    if normalized.starts_with('/') {
        return fail("Absoluter Archivpfad ist nicht erlaubt.");
    }
    let bytes = normalized.as_bytes();
    if bytes.len() >= 2 && bytes[0].is_ascii_alphabetic() && bytes[1] == b':' {
        return fail("Windows-Laufwerkspfade sind nicht erlaubt.");
    }
    let parts: Vec<&str> = normalized.split('/').filter(|part| !part.is_empty() && *part != ".").collect();
    if parts.is_empty() {
        return fail("Archivpfad ist leer.");
    }
    if parts.contains(&"..") {
        return fail("Archivpfad enthält '..'.");
    }
    let mut result = PathBuf::new();
    for component in parts {
        if component.chars().count() > MAX_COMPONENT_LENGTH {
            return fail("Ein Pfadbestandteil ist zu lang.");
        }
        if component.chars().any(|c| (c as u32) < 32) {
            return fail("Archivpfad enthält Steuerzeichen.");
        }
        if component.contains(':') {
            return fail("Doppelpunkte in Archivpfaden sind nicht erlaubt.");
        }
        if component.ends_with(' ') || component.ends_with('.') {
            return fail("Archivpfade mit abschließendem Punkt oder Leerzeichen sind nicht erlaubt.");
        }
        if is_windows_reserved(component) {
            return fail("Archivpfad verwendet einen reservierten Windows-Dateinamen.");
        }
        result.push(component);
    }
    Ok(result)
}

fn check_cancelled(cancel: Option<&AtomicBool>) -> Result<()> {
    match cancel {
        Some(flag) if flag.load(Ordering::Relaxed) => Err(Error::Cancelled),
        _ => Ok(()),
    }
}

/// Schreibt einen Stream mit Größenlimit und Abbruchprüfung.
fn copy_stream(reader: &mut dyn Read, target: &Path, cancel: Option<&AtomicBool>, total: &mut u64) -> Result<()> {
    if let Some(parent) = target.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let mut output = std::fs::OpenOptions::new().write(true).create_new(true).open(target)?;
    let mut buffer = vec![0u8; 1024 * 1024];
    let mut written: u64 = 0;
    loop {
        check_cancelled(cancel)?;
        let read = reader.read(&mut buffer)?;
        if read == 0 {
            break;
        }
        written += read as u64;
        *total += read as u64;
        if written > MAX_SINGLE_FILE_SIZE {
            return Err(Error::Message("Extrahierte Datei ist zu groß.".into()));
        }
        if *total > MAX_TOTAL_UNCOMPRESSED {
            return Err(Error::Message("Extrahierte Gesamtgröße überschreitet das Limit.".into()));
        }
        output.write_all(&buffer[..read])?;
    }
    Ok(())
}

/// Prüft und entpackt ein Archiv nach `destination` (muss leer sein oder fehlen).
pub fn extract_archive_securely(
    source: &Path,
    destination: &Path,
    cancel: Option<&AtomicBool>,
) -> Result<SecurityReport> {
    let source = crate::paths::absolute(source);
    let destination = crate::paths::absolute(destination);
    // Nie darauf vertrauen, dass die UI bereits geprüft hat.
    let report = inspect_archive(&source)?;
    if report.blocked {
        let messages: Vec<_> = report.blocking_issues().take(10).map(|issue| issue.message.clone()).collect();
        return Err(Error::Message(format!(
            "Das Archiv wurde aus Sicherheitsgründen blockiert.\n\n{}",
            messages.join("\n")
        )));
    }
    if destination.exists() && std::fs::read_dir(&destination)?.next().is_some() {
        return Err(Error::Message("Das Extraktionsziel ist nicht leer.".into()));
    }
    std::fs::create_dir_all(&destination)?;

    let result =
        extract_into(&source, report.kind, &destination, cancel).and_then(|_| verify_extracted_tree(&destination));
    if result.is_err() {
        let _ = std::fs::remove_dir_all(&destination);
    }
    result.map(|_| report)
}

fn extract_into(source: &Path, kind: ArchiveKind, destination: &Path, cancel: Option<&AtomicBool>) -> Result<()> {
    let mut total = 0u64;
    match kind {
        ArchiveKind::Zip => {
            let mut archive = zip::ZipArchive::new(File::open(source)?).map_err(|e| archive_error(source, e))?;
            for index in 0..archive.len() {
                check_cancelled(cancel)?;
                let mut entry = archive.by_index(index).map_err(|e| archive_error(source, e))?;
                let name = entry.name().map_err(|e| archive_error(source, e))?.into_owned();
                let target = destination.join(safe_member_relative_path(&name)?);
                if entry.is_dir() {
                    std::fs::create_dir_all(&target)?;
                } else {
                    copy_stream(&mut entry, &target, cancel, &mut total)?;
                }
            }
        }
        ArchiveKind::Tar(compression) => {
            let mut archive = tar::Archive::new(tar_reader(source, compression)?);
            for entry in archive.entries()? {
                check_cancelled(cancel)?;
                let mut entry = entry?;
                let kind = entry.header().entry_type();
                if kind.is_pax_global_extensions()
                    || kind.is_pax_local_extensions()
                    || kind.is_gnu_longname()
                    || kind.is_gnu_longlink()
                {
                    continue;
                }
                let name = entry.path()?.to_string_lossy().into_owned();
                let target = destination.join(safe_member_relative_path(&name)?);
                if kind.is_dir() {
                    std::fs::create_dir_all(&target)?;
                } else if kind.is_file() || kind == tar::EntryType::Continuous {
                    copy_stream(&mut entry, &target, cancel, &mut total)?;
                } else {
                    return Err(Error::Message(format!("TAR enthält einen nicht erlaubten Dateityp:\n{name}")));
                }
            }
        }
        ArchiveKind::SevenZip => {
            let mut reader = sevenz_rust2::ArchiveReader::open(source, sevenz_rust2::Password::empty())
                .map_err(|e| archive_error(source, e))?;
            let mut failure: Option<Error> = None;
            reader
                .for_each_entries(|entry, stream| {
                    let outcome = (|| -> Result<()> {
                        check_cancelled(cancel)?;
                        let target = destination.join(safe_member_relative_path(&entry.name)?);
                        if entry.is_directory {
                            std::fs::create_dir_all(&target)?;
                        } else {
                            copy_stream(stream, &target, cancel, &mut total)?;
                        }
                        Ok(())
                    })();
                    match outcome {
                        Ok(()) => Ok(true),
                        Err(error) => {
                            failure = Some(error);
                            Ok(false)
                        }
                    }
                })
                .map_err(|e| archive_error(source, e))?;
            if let Some(error) = failure {
                return Err(error);
            }
        }
        ArchiveKind::Rar => {
            let mut archive =
                unrar::Archive::new(source).open_for_processing().map_err(|e| archive_error(source, e))?;
            while let Some(header) = archive.read_header().map_err(|e| archive_error(source, e))? {
                check_cancelled(cancel)?;
                let entry = header.entry();
                let target = destination.join(safe_member_relative_path(&entry.filename.to_string_lossy())?);
                if entry.is_directory() {
                    std::fs::create_dir_all(&target)?;
                    archive = header.skip().map_err(|e| archive_error(source, e))?;
                } else if entry.is_file() {
                    if entry.unpacked_size > MAX_SINGLE_FILE_SIZE {
                        return Err(Error::Message("Extrahierte Datei ist zu groß.".into()));
                    }
                    total = total.saturating_add(entry.unpacked_size);
                    if total > MAX_TOTAL_UNCOMPRESSED {
                        return Err(Error::Message("Extrahierte Gesamtgröße überschreitet das Limit.".into()));
                    }
                    if let Some(parent) = target.parent() {
                        std::fs::create_dir_all(parent)?;
                    }
                    if crate::paths::path_exists(&target) {
                        return Err(Error::Message(format!("Doppelter Archivpfad: {}", target.display())));
                    }
                    archive = header.extract_to(&target).map_err(|e| archive_error(source, e))?;
                } else {
                    return Err(Error::Message(format!(
                        "RAR enthält einen nicht erlaubten Dateityp:\n{}",
                        entry.filename.display()
                    )));
                }
            }
        }
    }
    Ok(())
}

/// Nach dem Entpacken: keine Links, keine Spezialdateien, nichts außerhalb des Ziels.
fn verify_extracted_tree(root: &Path) -> Result<()> {
    let root_resolved = std::fs::canonicalize(root)?;
    let mut entries = 0u64;
    let mut total = 0u64;
    for entry in walkdir::WalkDir::new(root).follow_links(false).min_depth(1) {
        let entry =
            entry.map_err(|e| Error::Message(format!("Extrahierte Datei konnte nicht geprüft werden:\n{e}")))?;
        entries += 1;
        if entries > MAX_ARCHIVE_ENTRIES {
            return Err(Error::Message("Zu viele Dateien wurden extrahiert.".into()));
        }
        let file_type = entry.file_type();
        if file_type.is_symlink() {
            return Err(Error::Message(format!(
                "Nach der Extraktion wurde ein symbolischer Link gefunden:\n{}",
                entry.path().display()
            )));
        }
        if !(file_type.is_dir() || file_type.is_file()) {
            return Err(Error::Message(format!(
                "Nach der Extraktion wurde ein nicht erlaubter Dateityp gefunden:\n{}",
                entry.path().display()
            )));
        }
        if !std::fs::canonicalize(entry.path())?.starts_with(&root_resolved) {
            return Err(Error::Message("Extrahierter Pfad liegt außerhalb des Zielverzeichnisses.".into()));
        }
        if file_type.is_file() {
            let size = entry.metadata().map(|m| m.len()).unwrap_or(0);
            total += size;
            if size > MAX_SINGLE_FILE_SIZE {
                return Err(Error::Message("Extrahierte Datei ist zu groß.".into()));
            }
            if total > MAX_TOTAL_UNCOMPRESSED {
                return Err(Error::Message("Extrahierte Gesamtgröße überschreitet das Limit.".into()));
            }
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_zip(path: &Path, entries: &[(&str, &[u8])]) {
        let mut writer = zip::ZipWriter::new(File::create(path).unwrap());
        for (name, data) in entries {
            writer.start_file(*name, zip::write::SimpleFileOptions::default()).unwrap();
            writer.write_all(data).unwrap();
        }
        writer.finish().unwrap();
    }

    #[test]
    fn rejects_unsafe_paths() {
        for bad in ["../evil.ini", "/etc/passwd", "C:/x.ini", "a/../../b", "con.txt", "x:y", "dir/name. ", ""] {
            assert!(safe_member_relative_path(bad).is_err(), "{bad} sollte blockiert werden");
        }
        assert_eq!(safe_member_relative_path("./Mod\\a.ini").unwrap(), PathBuf::from("Mod").join("a.ini"));
    }

    #[test]
    fn zip_roundtrip_and_warnings() {
        let temp = tempfile::tempdir().unwrap();
        let archive = temp.path().join("Cool Mod.zip");
        make_zip(&archive, &[("Cool Mod/mod.ini", b"[x]"), ("Cool Mod/tool.exe", b"MZ")]);
        let report = inspect_archive(&archive).unwrap();
        assert!(!report.blocked);
        assert_eq!(report.entry_count, 2);
        assert_eq!(report.warning_files, vec!["Cool Mod/tool.exe"]);

        let out = temp.path().join("out");
        extract_archive_securely(&archive, &out, None).unwrap();
        assert_eq!(std::fs::read(out.join("Cool Mod/mod.ini")).unwrap(), b"[x]");
    }

    #[test]
    fn zip_traversal_is_blocked() {
        let temp = tempfile::tempdir().unwrap();
        let archive = temp.path().join("evil.zip");
        make_zip(&archive, &[("../../evil.ini", b"x"), ("ok/a.ini", b"x"), ("OK/A.ini", b"y")]);
        let report = inspect_archive(&archive).unwrap();
        assert!(report.blocked);
        let codes: Vec<_> = report.blocking_issues().map(|issue| issue.code).collect();
        assert!(codes.contains(&"unsafe_path"));
        assert!(codes.contains(&"duplicate_path"));
        assert!(extract_archive_securely(&archive, &temp.path().join("out"), None).is_err());
        assert!(!temp.path().join("out").exists());
    }

    #[test]
    fn tar_gz_with_symlink_is_blocked() {
        let temp = tempfile::tempdir().unwrap();
        let archive = temp.path().join("mod.tar.gz");
        let encoder = flate2::write::GzEncoder::new(File::create(&archive).unwrap(), flate2::Compression::default());
        let mut builder = tar::Builder::new(encoder);
        let mut header = tar::Header::new_gnu();
        header.set_entry_type(tar::EntryType::Symlink);
        header.set_size(0);
        builder.append_link(&mut header, "Mod/link", "/etc/passwd").unwrap();
        builder.into_inner().unwrap().finish().unwrap();
        let report = inspect_archive(&archive).unwrap();
        assert!(report.blocking_issues().any(|issue| issue.code == "link"));
    }

    #[test]
    fn seven_zip_roundtrip() {
        let temp = tempfile::tempdir().unwrap();
        let source = temp.path().join("src/Mod");
        std::fs::create_dir_all(&source).unwrap();
        std::fs::write(source.join("mod.ini"), "[x]").unwrap();
        let archive = temp.path().join("mod.7z");
        sevenz_rust2::compress_to_path(temp.path().join("src"), &archive).unwrap();
        assert!(!inspect_archive(&archive).unwrap().blocked);
        let out = temp.path().join("out");
        extract_archive_securely(&archive, &out, None).unwrap();
        assert!(out.join("Mod/mod.ini").is_file());
    }

    #[test]
    fn rar_extract_and_encryption_block() {
        let data = Path::new(env!("CARGO_MANIFEST_DIR")).join("testdata");
        let temp = tempfile::tempdir().unwrap();
        extract_archive_securely(&data.join("version.rar"), &temp.path().join("out"), None).unwrap();
        assert!(temp.path().join("out/VERSION").is_file());
        let report = inspect_archive(&data.join("crypted.rar")).unwrap();
        assert!(report.blocking_issues().any(|issue| issue.code == "encrypted_member"));
    }

    #[test]
    fn name_without_suffix() {
        assert_eq!(archive_name_without_suffix(Path::new("/x/My Mod.tar.gz")), "My Mod");
        assert_eq!(archive_name_without_suffix(Path::new("a.ZIP")), "a");
    }
}
