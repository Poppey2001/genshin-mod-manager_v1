//! Struktur-Erkennung `Bibliothek / Charakter / Mod-Typ / Mod`
//! (Port von `app/services/mod_structure_detector.py`).

use std::path::Path;
use std::sync::OnceLock;

use regex::Regex;

pub const UNKNOWN_TYPE: &str = "Unbekannt";

pub const MOD_TYPE_ALIASES: &[(&str, &str)] = &[
    ("character skin", "Character Skin"),
    ("character skins", "Character Skin"),
    ("characterskin", "Character Skin"),
    ("skin", "Character Skin"),
    ("skins", "Character Skin"),
    ("weapon skin", "Weapon Skin"),
    ("weapon skins", "Weapon Skin"),
    ("weapons", "Weapon Skin"),
    ("effects", "Effects"),
    ("effect", "Effects"),
    ("visual effects", "Effects"),
    ("vfx", "Effects"),
    ("ui", "UI"),
    ("interface", "UI"),
    ("shader", "Shader"),
    ("shaders", "Shader"),
    ("other", "Sonstiges"),
    ("misc", "Sonstiges"),
    ("sonstiges", "Sonstiges"),
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ModStructure {
    pub character: Option<String>,
    pub mod_type: String,
    pub mod_name: String,
    pub relative_path: String,
}

fn whitespace() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\s+").unwrap())
}

pub fn normalize_key(value: &str) -> String {
    let value = value.replace(['_', '-'], " ");
    whitespace().replace_all(&value, " ").trim().to_lowercase()
}

pub fn normalize_folder_name(value: &str) -> String {
    let value = value.replace('_', " ");
    whitespace().replace_all(&value, " ").trim().to_string()
}

pub fn known_type(key: &str) -> Option<&'static str> {
    MOD_TYPE_ALIASES.iter().find(|(alias, _)| *alias == key).map(|(_, name)| *name)
}

pub fn normalize_mod_type(folder_name: &str) -> String {
    known_type(&normalize_key(folder_name)).map(str::to_string).unwrap_or_else(|| normalize_folder_name(folder_name))
}

pub fn detect_mod_structure(library_root: &Path, mod_directory: &Path) -> ModStructure {
    let relative = mod_directory
        .strip_prefix(library_root)
        .map(Path::to_path_buf)
        .unwrap_or_else(|_| mod_directory.file_name().map(Into::into).unwrap_or_default());
    let parts: Vec<String> = relative.components().map(|c| c.as_os_str().to_string_lossy().into_owned()).collect();
    let dir_name = mod_directory.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_default();

    let mut character = None;
    let mut mod_type = UNKNOWN_TYPE.to_string();
    let mut mod_name = dir_name;

    match parts.len() {
        0 => {}
        1 => mod_name = normalize_folder_name(&parts[0]),
        2 => {
            let normalized_type = normalize_mod_type(&parts[0]);
            // In Python liefert normalize_mod_type für unbekannte Typen den
            // Ordnernamen zurück, deshalb ist "Unbekannt" nur bei genau
            // diesem Namen möglich. Wir bilden das Verhalten 1:1 nach.
            if normalized_type != UNKNOWN_TYPE {
                mod_type = normalized_type;
            } else {
                character = Some(normalize_folder_name(&parts[0]));
            }
            mod_name = normalize_folder_name(&parts[1]);
        }
        _ => {
            character = Some(normalize_folder_name(&parts[0]));
            mod_type = normalize_mod_type(&parts[1]);
            mod_name = normalize_folder_name(parts.last().unwrap());
        }
    }

    ModStructure { character, mod_type, mod_name, relative_path: relative.to_string_lossy().into_owned() }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn three_level_structure() {
        let s = detect_mod_structure(Path::new("/lib"), Path::new("/lib/Raiden_Shogun/skins/Cool_Mod"));
        assert_eq!(s.character.as_deref(), Some("Raiden Shogun"));
        assert_eq!(s.mod_type, "Character Skin");
        assert_eq!(s.mod_name, "Cool Mod");
        assert_eq!(s.relative_path, "Raiden_Shogun/skins/Cool_Mod");
    }

    #[test]
    fn two_level_structure_uses_type() {
        let s = detect_mod_structure(Path::new("/lib"), Path::new("/lib/VFX/Glow"));
        assert_eq!(s.character, None);
        assert_eq!(s.mod_type, "Effects");
    }

    #[test]
    fn normalize_key_matches_python() {
        assert_eq!(normalize_key("  Character__Skin-x "), "character skin x");
    }
}
