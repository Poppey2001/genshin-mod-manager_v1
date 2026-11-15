//! Plattform-Pfade und Pfadvergleiche.
//!
//! Die Verzeichnisse entsprechen exakt dem, was die Python-Version über
//! `platformdirs` (appname="genshin-mod-manager", appauthor=False) nutzt,
//! damit bestehende Konfigurationen und Bibliotheken weiterverwendet werden.

use std::path::{Component, Path, PathBuf};
use std::sync::OnceLock;

pub const APP_DIR_NAME: &str = "genshin-mod-manager";

#[derive(Debug, Clone)]
pub struct AppDirs {
    pub config_dir: PathBuf,
    pub data_dir: PathBuf,
    pub cache_dir: PathBuf,
}

impl AppDirs {
    pub fn config_file(&self) -> PathBuf {
        self.config_dir.join("config.json")
    }
    pub fn mod_library_dir(&self) -> PathBuf {
        self.data_dir.join("mods")
    }
    pub fn profile_dir(&self) -> PathBuf {
        self.data_dir.join("profiles")
    }
    pub fn preview_dir(&self) -> PathBuf {
        self.data_dir.join("previews")
    }
    pub fn backup_dir(&self) -> PathBuf {
        self.data_dir.join("backups")
    }
    pub fn fixed_mods_dir(&self) -> PathBuf {
        self.data_dir.join("fixed-mods")
    }

    /// Basisverzeichnisse für ein beliebiges Wurzelverzeichnis (Tests, portable Modus).
    pub fn rooted(root: &Path) -> Self {
        Self { config_dir: root.join("config"), data_dir: root.join("data"), cache_dir: root.join("cache") }
    }

    pub fn ensure(&self) -> std::io::Result<()> {
        for dir in [
            self.config_dir.clone(),
            self.data_dir.clone(),
            self.cache_dir.clone(),
            self.mod_library_dir(),
            self.profile_dir(),
            self.preview_dir(),
            self.backup_dir(),
            self.fixed_mods_dir(),
        ] {
            std::fs::create_dir_all(dir)?;
        }
        Ok(())
    }
}

fn env_path(name: &str) -> Option<PathBuf> {
    std::env::var_os(name).filter(|value| !value.is_empty()).map(PathBuf::from).filter(|path| path.is_absolute())
}

pub fn home_dir() -> PathBuf {
    #[cfg(windows)]
    let home = env_path("USERPROFILE");
    #[cfg(not(windows))]
    let home = env_path("HOME");
    home.unwrap_or_else(|| PathBuf::from("."))
}

/// Systemweite Standardverzeichnisse.
pub fn app_dirs() -> &'static AppDirs {
    static DIRS: OnceLock<AppDirs> = OnceLock::new();
    DIRS.get_or_init(|| {
        if let Some(root) = env_path("GMM_PORTABLE_ROOT") {
            return AppDirs::rooted(&root);
        }
        default_dirs()
    })
}

#[cfg(windows)]
fn default_dirs() -> AppDirs {
    // platformdirs (Windows, roaming=False): %LOCALAPPDATA%\<app>
    let local = env_path("LOCALAPPDATA").unwrap_or_else(|| home_dir().join("AppData").join("Local"));
    let base = local.join(APP_DIR_NAME);
    AppDirs { config_dir: base.clone(), data_dir: base.clone(), cache_dir: base.join("Cache") }
}

#[cfg(target_os = "macos")]
fn default_dirs() -> AppDirs {
    let home = home_dir();
    let support = home.join("Library").join("Application Support").join(APP_DIR_NAME);
    AppDirs {
        config_dir: support.clone(),
        data_dir: support,
        cache_dir: home.join("Library").join("Caches").join(APP_DIR_NAME),
    }
}

#[cfg(all(not(windows), not(target_os = "macos")))]
fn default_dirs() -> AppDirs {
    let home = home_dir();
    let xdg = |name: &str, fallback: PathBuf| env_path(name).unwrap_or(fallback);
    AppDirs {
        config_dir: xdg("XDG_CONFIG_HOME", home.join(".config")).join(APP_DIR_NAME),
        data_dir: xdg("XDG_DATA_HOME", home.join(".local").join("share")).join(APP_DIR_NAME),
        cache_dir: xdg("XDG_CACHE_HOME", home.join(".cache")).join(APP_DIR_NAME),
    }
}

/// `~` am Anfang eines Pfades expandieren (wie `Path.expanduser`).
pub fn expand_user(path: &Path) -> PathBuf {
    let mut components = path.components();
    match components.next() {
        Some(Component::Normal(first)) if first == "~" => home_dir().join(components.as_path()),
        _ => path.to_path_buf(),
    }
}

/// Absoluter Pfad ohne Symlinks aufzulösen (wie `Path.absolute()`).
pub fn absolute(path: &Path) -> PathBuf {
    let expanded = expand_user(path);
    if expanded.is_absolute() {
        expanded
    } else {
        std::env::current_dir().map(|cwd| cwd.join(&expanded)).unwrap_or(expanded)
    }
}

/// Lexikalische Normalisierung: entfernt `.` und löst `..` auf (wie `os.path.normpath`).
pub fn normalize(path: &Path) -> PathBuf {
    let mut result = PathBuf::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::ParentDir => {
                if !result.pop() {
                    result.push("..");
                }
            }
            other => result.push(other.as_os_str()),
        }
    }
    result
}

/// Entspricht `platform_support.normalized_path_key` der Python-Version.
///
/// Der Wert wird in den Manager-Markern (`source_key`) gespeichert und muss
/// deshalb byte-identisch zur Python-Implementierung bleiben.
pub fn normalized_path_key(path: &Path) -> String {
    let value = normalize(&absolute(path));
    let text = value.to_string_lossy().into_owned();
    if cfg!(windows) {
        text.replace('/', "\\").to_lowercase()
    } else {
        text
    }
}

pub fn paths_equal(first: &Path, second: &Path) -> bool {
    normalized_path_key(first) == normalized_path_key(second)
}

/// Prüft lexikalisch, ob `path` innerhalb von `parent` liegt (inklusive Gleichheit).
pub fn path_is_inside(path: &Path, parent: &Path) -> bool {
    let path = normalize(&absolute(path));
    let parent = normalize(&absolute(parent));
    if cfg!(windows) {
        let path = PathBuf::from(path.to_string_lossy().to_lowercase());
        let parent = PathBuf::from(parent.to_string_lossy().to_lowercase());
        path.starts_with(parent)
    } else {
        path.starts_with(parent)
    }
}

pub fn paths_overlap(first: &Path, second: &Path) -> bool {
    path_is_inside(first, second) || path_is_inside(second, first)
}

/// Existiert der Pfad oder ist er ein (ggf. defekter) Symlink?
pub fn path_exists(path: &Path) -> bool {
    path.symlink_metadata().is_ok()
}

pub fn is_symlink(path: &Path) -> bool {
    path.symlink_metadata().map(|meta| meta.file_type().is_symlink()).unwrap_or(false)
}

/// Unicode-Kleinschreibung als Ersatz für Pythons `str.casefold()`.
pub fn casefold(value: &str) -> String {
    value.to_lowercase()
}

/// Linux- und Windows-kompatibler Ordnername (Port von `sanitize_path_segment`).
///
/// Die Windows-Regeln gelten auf allen Plattformen, damit eine Bibliothek
/// später auch unter Windows funktioniert.
pub fn sanitize_path_segment(value: &str) -> String {
    sanitize_path_segment_with(value, "Imported Mod", 180)
}

pub fn sanitize_path_segment_with(value: &str, fallback: &str, maximum_length: usize) -> String {
    use unicode_normalization::UnicodeNormalization;
    let normalized: String = value.nfkc().collect();
    let replaced: String =
        normalized.chars().map(|c| if "<>:\"/\\|?*".contains(c) || (c as u32) < 0x20 { '_' } else { c }).collect();
    let collapsed = replaced.split_whitespace().collect::<Vec<_>>().join(" ");
    let mut cleaned = collapsed.trim_matches([' ', '.']).to_string();
    if cleaned.is_empty() {
        cleaned = fallback.to_string();
    }
    if crate::archive::is_windows_reserved(&cleaned) {
        cleaned = format!("_{cleaned}");
    }
    let truncated: String = cleaned.chars().take(maximum_length).collect();
    let result = truncated.trim_end_matches([' ', '.']).to_string();
    if result.is_empty() {
        fallback.to_string()
    } else {
        result
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_matches_python() {
        assert_eq!(sanitize_path_segment("  a<b>:c  d. "), "a_b__c d");
        assert_eq!(sanitize_path_segment("CON.txt"), "_CON.txt");
        assert_eq!(sanitize_path_segment(" .. "), "Imported Mod");
        assert_eq!(sanitize_path_segment("ｆｕｌｌ"), "full");
    }

    #[test]
    fn normalize_removes_dots() {
        assert_eq!(normalize(Path::new("/a/./b/../c")), PathBuf::from("/a/c"));
    }

    #[cfg(unix)]
    #[test]
    fn path_key_matches_python_normpath() {
        assert_eq!(normalized_path_key(Path::new("/mods//x/./y/")), "/mods/x/y");
    }

    #[test]
    fn inside_and_overlap() {
        let root = absolute(Path::new("lib"));
        assert!(path_is_inside(&root.join("a"), &root));
        assert!(!path_is_inside(&absolute(Path::new("library2")), &root));
        assert!(paths_overlap(&root, &root.join("x")));
    }
}
