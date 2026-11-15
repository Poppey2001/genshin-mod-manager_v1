//! Analyse von Merge-/Master-INIs mit `[Key...]`-Sektionen
//! (Port von `app/services/ini_analyzer.py`).

use std::io::Read;
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use regex::Regex;
use serde::Serialize;

const MAX_DISCOVERED_INI_FILES: usize = 250;
const MAX_ANALYZED_INI_FILES: usize = 30;
const MAX_INI_FILE_SIZE: u64 = 2 * 1024 * 1024;
const MAX_SCAN_DEPTH: usize = 10;
const IGNORED_DIRECTORIES: &[&str] = &[".git", "__pycache__"];
const PREFERRED_INI_NAMES: &[&str] = &["master.ini", "merge.ini", "merged.ini"];
const CONTROL_PROPERTIES: &[&str] = &[
    "key",
    "back",
    "type",
    "condition",
    "smart",
    "wrap",
    "delay",
    "release_delay",
    "transition",
    "release_transition",
    "transition_type",
    "release_transition_type",
];

#[derive(Debug, Clone, Serialize)]
pub struct IniAssignment {
    pub name: String,
    pub raw_value: String,
    pub values: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct IniStateLabel {
    pub index: u32,
    pub label: String,
}

#[derive(Debug, Clone, Serialize)]
pub struct IniKeyBinding {
    pub section_name: String,
    pub keys: Vec<String>,
    pub back_keys: Vec<String>,
    pub key_type: String,
    pub condition: Option<String>,
    pub assignments: Vec<IniAssignment>,
    pub run_commands: Vec<String>,
    pub comments: Vec<String>,
    pub state_labels: Vec<IniStateLabel>,
    pub smart: Option<String>,
    pub wrap: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct IniFileAnalysis {
    pub path: PathBuf,
    pub namespace: Option<String>,
    pub merged_sources: Vec<String>,
    pub key_bindings: Vec<IniKeyBinding>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize)]
pub struct ModIniAnalysis {
    pub root_path: PathBuf,
    pub files: Vec<IniFileAnalysis>,
    pub warnings: Vec<String>,
    pub has_controls: bool,
}

fn regex(cell: &'static OnceLock<Regex>, pattern: &str) -> &'static Regex {
    cell.get_or_init(|| Regex::new(pattern).expect("gültiger Regex"))
}

fn section_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"^\s*\[([^\]]+)]\s*(?:[;#].*)?$")
}
fn property_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"^\s*([^=]+?)\s*=\s*(.*?)\s*$")
}
fn key_section_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"(?im)^\s*\[key[^\]]*]")
}
fn namespace_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"(?im)^\s*namespace\s*=\s*(.+?)\s*$")
}
fn merged_mod_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"(?im)^\s*[;#]\s*merged\s+mod\s*:\s*(.+?)\s*$")
}
fn state_label_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    regex(&RE, r"(?i)\b(?:cycle|state|option|preset)\s*(\d+)\s*[:=\-]\s*(.+)")
}

/// Analysiert Merge-, Master- und andere INI-Dateien mit `[Key...]`-Sektionen.
pub fn analyze_mod_ini(root: &Path) -> ModIniAnalysis {
    let root = crate::paths::expand_user(root);
    let empty = |warning: String| ModIniAnalysis {
        root_path: root.clone(),
        files: vec![],
        warnings: vec![warning],
        has_controls: false,
    };
    if !root.exists() {
        return empty(format!("Der Mod-Ordner existiert nicht: {}", root.display()));
    }
    if !root.is_dir() {
        return empty(format!("Der Mod-Pfad ist kein Ordner: {}", root.display()));
    }

    let (discovered, mut warnings) = discover_ini_files(&root);
    let mut preferred: Vec<PathBuf> = discovered.iter().filter(|p| is_preferred_ini(p)).cloned().collect();
    if preferred.is_empty() {
        preferred = discovered
            .iter()
            .filter(|path| read_ini_text(path, 256 * 1024).is_ok_and(|text| key_section_pattern().is_match(&text)))
            .cloned()
            .collect();
    }
    preferred.sort_by_key(|path| ini_sort_key(path));
    if preferred.len() > MAX_ANALYZED_INI_FILES {
        warnings.push(format!(
            "Es wurden mehr steuernde INI-Dateien gefunden, als analysiert werden können. Es werden nur die ersten \
             {MAX_ANALYZED_INI_FILES} angezeigt."
        ));
    }
    let mut files = Vec::new();
    for path in preferred.into_iter().take(MAX_ANALYZED_INI_FILES) {
        match analyze_ini_file(&path) {
            Ok(analysis) => files.push(analysis),
            Err(error) => warnings.push(format!("{}: {error}", path.display())),
        }
    }
    let has_controls = files.iter().any(|file| !file.key_bindings.is_empty());
    ModIniAnalysis { root_path: root, files, warnings, has_controls }
}

fn discover_ini_files(root: &Path) -> (Vec<PathBuf>, Vec<String>) {
    let mut found = Vec::new();
    let mut warnings = Vec::new();
    let walker = walkdir::WalkDir::new(root)
        .follow_links(false)
        .max_depth(MAX_SCAN_DEPTH + 1)
        .into_iter()
        .filter_entry(|entry| {
            if entry.depth() == 0 || !entry.file_type().is_dir() {
                return true;
            }
            let name = entry.file_name().to_string_lossy();
            entry.depth() <= MAX_SCAN_DEPTH && !name.starts_with('.') && !IGNORED_DIRECTORIES.contains(&name.as_ref())
        });
    for entry in walker {
        let entry = match entry {
            Ok(entry) => entry,
            Err(error) => {
                warnings.push(error.to_string());
                continue;
            }
        };
        if !entry.file_type().is_file() {
            continue;
        }
        let is_ini = entry.path().extension().is_some_and(|ext| ext.to_string_lossy().eq_ignore_ascii_case("ini"));
        if !is_ini {
            continue;
        }
        found.push(entry.into_path());
        if found.len() >= MAX_DISCOVERED_INI_FILES {
            warnings.push(format!(
                "Die INI-Suche wurde begrenzt, weil mehr als {MAX_DISCOVERED_INI_FILES} Dateien gefunden wurden."
            ));
            return (found, warnings);
        }
    }
    found.sort_by_key(|path| path.to_string_lossy().to_lowercase());
    (found, warnings)
}

fn is_preferred_ini(path: &Path) -> bool {
    let name = path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
    let stem = path.file_stem().unwrap_or_default().to_string_lossy().to_lowercase();
    PREFERRED_INI_NAMES.contains(&name.as_str()) || stem.contains("merge") || stem.contains("master")
}

fn ini_sort_key(path: &Path) -> (u8, String) {
    let name = path.file_name().unwrap_or_default().to_string_lossy().to_lowercase();
    let priority = match name.as_str() {
        "master.ini" => 0,
        "merge.ini" => 1,
        "merged.ini" => 2,
        _ => 3,
    };
    (priority, path.to_string_lossy().to_lowercase())
}

fn read_ini_text(path: &Path, limit: u64) -> std::io::Result<String> {
    let mut bytes = Vec::new();
    std::fs::File::open(path)?.take(limit + 1).read_to_end(&mut bytes)?;
    if bytes.len() as u64 > limit {
        return Err(std::io::Error::other("Die INI-Datei überschreitet das Leselimit."));
    }
    let text = String::from_utf8_lossy(&bytes).into_owned();
    Ok(text.strip_prefix('\u{feff}').map(str::to_string).unwrap_or(text))
}

fn analyze_ini_file(path: &Path) -> std::io::Result<IniFileAnalysis> {
    let size = path
        .metadata()
        .map_err(|error| std::io::Error::other(format!("Dateigröße konnte nicht gelesen werden: {error}")))?
        .len();
    if size > MAX_INI_FILE_SIZE {
        return Ok(IniFileAnalysis {
            path: path.to_path_buf(),
            namespace: None,
            merged_sources: vec![],
            key_bindings: vec![],
            warnings: vec!["Die Datei ist größer als 2 MiB und wurde aus Sicherheitsgründen nicht analysiert.".into()],
        });
    }
    let text = read_ini_text(path, MAX_INI_FILE_SIZE)?;
    let key_bindings: Vec<_> = split_sections(&text)
        .iter()
        .filter(|section| section.name.to_lowercase().starts_with("key"))
        .map(analyze_key_section)
        .collect();
    let warnings = if key_bindings.is_empty() {
        vec!["In dieser Datei wurden keine [Key...]-Sektionen gefunden.".to_string()]
    } else {
        vec![]
    };
    Ok(IniFileAnalysis {
        path: path.to_path_buf(),
        namespace: namespace_pattern()
            .captures(&text)
            .map(|c| remove_inline_comment(&c[1]).trim().to_string())
            .filter(|n| !n.is_empty()),
        merged_sources: merged_mod_pattern()
            .captures(&text)
            .map(|c| {
                split_value_list(&c[1]).into_iter().map(|v| v.trim().to_string()).filter(|v| !v.is_empty()).collect()
            })
            .unwrap_or_default(),
        key_bindings,
        warnings,
    })
}

struct ParsedSection {
    name: String,
    leading_comments: Vec<String>,
    lines: Vec<String>,
}

fn split_sections(text: &str) -> Vec<ParsedSection> {
    let mut sections = Vec::new();
    let mut current: Option<ParsedSection> = None;
    let mut pending = Vec::new();
    for raw in text.lines() {
        if let Some(header) = section_pattern().captures(raw) {
            if let Some(section) = current.take() {
                sections.push(section);
            }
            current = Some(ParsedSection {
                name: header[1].trim().to_string(),
                leading_comments: std::mem::take(&mut pending),
                lines: vec![],
            });
            continue;
        }
        let stripped = raw.trim();
        match current.as_mut() {
            None => {
                if stripped.starts_with(';') || stripped.starts_with('#') {
                    pending.push(clean_comment(stripped));
                } else if !stripped.is_empty() {
                    pending.clear();
                }
            }
            Some(section) => section.lines.push(raw.to_string()),
        }
    }
    if let Some(section) = current {
        sections.push(section);
    }
    sections
}

fn analyze_key_section(section: &ParsedSection) -> IniKeyBinding {
    let mut properties: Vec<(String, String, String)> = Vec::new();
    let mut comments = section.leading_comments.clone();
    for raw in &section.lines {
        let stripped = raw.trim();
        if stripped.is_empty() {
            continue;
        }
        if stripped.starts_with(';') || stripped.starts_with('#') {
            comments.push(clean_comment(stripped));
            continue;
        }
        let Some(captures) = property_pattern().captures(raw) else { continue };
        let original = captures[1].trim().to_string();
        let value = remove_inline_comment(&captures[2]).trim().to_string();
        properties.push((original.clone(), original.to_lowercase(), value));
    }
    let collect = |name: &str| -> Vec<String> {
        properties.iter().filter(|(_, n, v)| n == name && !v.is_empty()).map(|(_, _, v)| v.clone()).collect()
    };
    let first = |name: &str| -> Option<String> {
        properties.iter().find(|(_, n, _)| n == name).map(|(_, _, v)| v.clone()).filter(|v| !v.is_empty())
    };
    let assignments = properties
        .iter()
        .filter(|(_, n, _)| !CONTROL_PROPERTIES.contains(&n.as_str()) && n != "run")
        .map(|(original, _, value)| IniAssignment {
            name: original.clone(),
            raw_value: value.clone(),
            values: split_value_list(value),
        })
        .collect();
    let state_labels = comments
        .iter()
        .filter_map(|comment| {
            let captures = state_label_pattern().captures(comment)?;
            Some(IniStateLabel { index: captures[1].parse().ok()?, label: captures[2].trim().to_string() })
        })
        .collect();
    IniKeyBinding {
        section_name: section.name.clone(),
        keys: collect("key"),
        back_keys: collect("back"),
        key_type: first("type").unwrap_or_else(|| "activate".into()).to_lowercase(),
        condition: first("condition"),
        assignments,
        run_commands: collect("run"),
        comments: comments.into_iter().filter(|c| !c.is_empty()).collect(),
        state_labels,
        smart: first("smart"),
        wrap: first("wrap"),
    }
}

fn clean_comment(value: &str) -> String {
    value.trim_start_matches([';', '#']).trim().to_string()
}

/// Entfernt Kommentare, wenn vor `;` oder `#` ein Leerzeichen steht.
fn remove_inline_comment(value: &str) -> String {
    let mut value = value.to_string();
    for marker in [" ;", "\t;", " #", "\t#"] {
        if let Some(position) = value.find(marker) {
            value.truncate(position);
        }
    }
    value.trim_end().to_string()
}

/// Trennt Kommawerte, berücksichtigt aber Klammern und Anführungszeichen.
pub fn split_value_list(value: &str) -> Vec<String> {
    let mut values = Vec::new();
    let mut current = String::new();
    let mut depth = 0usize;
    let mut quote: Option<char> = None;
    for character in value.chars() {
        if let Some(q) = quote {
            current.push(character);
            if character == q {
                quote = None;
            }
            continue;
        }
        match character {
            '"' | '\'' => {
                quote = Some(character);
                current.push(character);
            }
            '(' | '[' | '{' => {
                depth += 1;
                current.push(character);
            }
            ')' | ']' | '}' => {
                depth = depth.saturating_sub(1);
                current.push(character);
            }
            ',' if depth == 0 => values.push(std::mem::take(&mut current).trim().to_string()),
            _ => current.push(character),
        }
    }
    values.push(current.trim().to_string());
    values.into_iter().filter(|v| !v.is_empty()).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const MERGED: &str = "\u{feff}; Merged Mod: Normal, Swimsuit (Beach), Winter\n\
namespace = Furina\\Outfits ; kommentar\n\
\n\
[Constants]\n\
global persist $swapvar = 0\n\
\n\
[KeySwap]\n\
; Option 0 = Normal\n\
; option 1: Swimsuit\n\
condition = $active == 1\n\
key = VK_DOWN\n\
back = VK_UP\n\
type = CYCLE\n\
$swapvar = 0,1,2\n\
run = CommandListReset\n\
\n\
[KeyToggle]\n\
key = ctrl alt F\n\
$hair = 0, func(1, 2)\n";

    #[test]
    fn analyzes_merged_ini() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(temp.path().join("merged.ini"), MERGED).unwrap();
        std::fs::create_dir(temp.path().join("Body")).unwrap();
        std::fs::write(temp.path().join("Body/body.ini"), "[TextureOverride]\n").unwrap();

        let analysis = analyze_mod_ini(temp.path());
        assert!(analysis.has_controls);
        assert_eq!(analysis.files.len(), 1);
        let file = &analysis.files[0];
        assert_eq!(file.namespace.as_deref(), Some("Furina\\Outfits"));
        assert_eq!(file.merged_sources, vec!["Normal", "Swimsuit (Beach)", "Winter"]);
        assert_eq!(file.key_bindings.len(), 2);

        let swap = &file.key_bindings[0];
        assert_eq!(swap.section_name, "KeySwap");
        assert_eq!(swap.keys, vec!["VK_DOWN"]);
        assert_eq!(swap.back_keys, vec!["VK_UP"]);
        assert_eq!(swap.key_type, "cycle");
        assert_eq!(swap.condition.as_deref(), Some("$active == 1"));
        assert_eq!(swap.assignments[0].values, vec!["0", "1", "2"]);
        assert_eq!(swap.run_commands, vec!["CommandListReset"]);
        assert_eq!(swap.state_labels.len(), 2);
        assert_eq!(swap.state_labels[1].label, "Swimsuit");

        let toggle = &file.key_bindings[1];
        assert_eq!(toggle.key_type, "activate");
        assert_eq!(toggle.assignments[0].values, vec!["0", "func(1, 2)"]);
    }

    #[test]
    fn falls_back_to_files_with_key_sections() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(temp.path().join("a.ini"), "[TextureOverride]\n").unwrap();
        std::fs::write(temp.path().join("b.ini"), "[KeyX]\nkey = x\n").unwrap();
        let analysis = analyze_mod_ini(temp.path());
        assert_eq!(analysis.files.len(), 1);
        assert!(analysis.files[0].path.ends_with("b.ini"));
    }
}
