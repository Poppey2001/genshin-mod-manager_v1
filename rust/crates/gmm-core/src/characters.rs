//! Charakter-Erkennung (Port von `app/services/character_detector.py`).
//!
//! Reihenfolge: character(s).txt, JSON-Metadaten, INI-Kommentare, Ordnername.

use std::collections::HashSet;
use std::io::Read;
use std::path::Path;
use std::sync::OnceLock;

use regex::Regex;
use serde_json::Value;
use walkdir::WalkDir;

const METADATA_FILES: &[&str] = &["mod.json", "metadata.json", "info.json"];
const CHARACTER_TEXT_FILES: &[&str] = &["character.txt", "characters.txt"];
const CHARACTER_METADATA_KEYS: &[&str] =
    &["character", "characters", "target_character", "target_characters", "targetCharacter", "targetCharacters"];
const GENERIC_NAMES: &[&str] =
    &["mod", "mods", "character", "characters", "default", "unknown", "genshin", "skin", "outfit"];

fn ini_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?im)^[;#]\s*(?:character|characters|char|target|target_character)\s*[:=]\s*(.+?)\s*$").unwrap()
    })
}

fn bracket_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\[(?P<character>[^\]]{2,60})\]").unwrap())
}

fn separator_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^(?P<character>.{2,60}?)(?:__| -- )").unwrap())
}

fn split_pattern() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[,;\n|]+").unwrap())
}

fn whitespace() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\s+").unwrap())
}

pub fn detect_characters(mod_directory: &Path) -> Vec<String> {
    let mut characters = Vec::new();
    characters.extend(detect_from_text_files(mod_directory));
    characters.extend(detect_from_metadata_files(mod_directory));
    characters.extend(detect_from_ini_files(mod_directory));
    if characters.is_empty() {
        if let Some(name) = mod_directory.file_name() {
            characters.extend(detect_from_directory_name(&name.to_string_lossy()));
        }
    }
    remove_duplicates(characters)
}

fn read_limited(path: &Path, limit: u64) -> Option<String> {
    let file = std::fs::File::open(path).ok()?;
    let mut bytes = Vec::new();
    file.take(limit).read_to_end(&mut bytes).ok()?;
    Some(String::from_utf8_lossy(&bytes).into_owned())
}

fn detect_from_text_files(dir: &Path) -> Vec<String> {
    let mut result = Vec::new();
    for name in CHARACTER_TEXT_FILES {
        let path = dir.join(name);
        if !path.is_file() {
            continue;
        }
        if let Some(content) = read_limited(&path, 16_384) {
            let content: String = content.chars().take(4096).collect();
            result.extend(split_character_names(&content));
        }
    }
    result
}

fn detect_from_metadata_files(dir: &Path) -> Vec<String> {
    let mut result = Vec::new();
    for name in METADATA_FILES {
        let path = dir.join(name);
        if !path.is_file() || path.metadata().map(|m| m.len() > 256_000).unwrap_or(true) {
            continue;
        }
        let Some(content) = read_limited(&path, 256_000) else { continue };
        let Ok(data) = serde_json::from_str::<Value>(&content) else { continue };
        result.extend(extract_characters_from_json(&data));
    }
    result
}

fn extract_characters_from_json(data: &Value) -> Vec<String> {
    let Some(map) = data.as_object() else { return Vec::new() };
    let mut result = Vec::new();
    for key in CHARACTER_METADATA_KEYS {
        match map.get(*key) {
            Some(Value::String(text)) => result.extend(split_character_names(text)),
            Some(Value::Array(items)) => {
                for item in items {
                    if let Value::String(text) = item {
                        result.extend(split_character_names(text));
                    }
                }
            }
            _ => {}
        }
    }
    result
}

/// Durchsucht höchstens zehn INI-Dateien (schnell auch auf Netzlaufwerken).
fn detect_from_ini_files(dir: &Path) -> Vec<String> {
    let mut result = Vec::new();
    let ini_files = WalkDir::new(dir)
        .follow_links(false)
        .into_iter()
        .filter_map(|entry| entry.ok())
        .filter(|entry| {
            entry.file_type().is_file() && entry.file_name().to_string_lossy().to_lowercase().ends_with(".ini")
        })
        .take(10);
    for entry in ini_files {
        let Some(content) = read_limited(entry.path(), 128_000 * 4) else { continue };
        let content: String = content.chars().take(128_000).collect();
        for capture in ini_pattern().captures_iter(&content) {
            result.extend(split_character_names(&capture[1]));
        }
    }
    result
}

pub fn detect_from_directory_name(name: &str) -> Vec<String> {
    if let Some(captures) = bracket_pattern().captures(name) {
        return split_character_names(&captures["character"]);
    }
    if let Some(captures) = separator_pattern().captures(name) {
        return split_character_names(&captures["character"]);
    }
    Vec::new()
}

pub fn split_character_names(value: &str) -> Vec<String> {
    split_pattern().split(value).filter_map(normalize_character_name).collect()
}

fn normalize_character_name(value: &str) -> Option<String> {
    let name = value.trim().trim_matches(|c| "[](){}".contains(c));
    let name = whitespace().replace_all(name, " ").into_owned();
    let length = name.chars().count();
    if name.is_empty() || !(2..=60).contains(&length) {
        return None;
    }
    if GENERIC_NAMES.contains(&name.to_lowercase().as_str()) {
        return None;
    }
    Some(name)
}

fn remove_duplicates(characters: Vec<String>) -> Vec<String> {
    let mut seen = HashSet::new();
    let mut result: Vec<String> = characters.into_iter().filter(|name| seen.insert(name.to_lowercase())).collect();
    result.sort_by_key(|name| name.to_lowercase());
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn directory_name_patterns() {
        assert_eq!(detect_from_directory_name("[Furina] Summer"), vec!["Furina"]);
        assert_eq!(detect_from_directory_name("Nahida__Cute"), vec!["Nahida"]);
        assert!(detect_from_directory_name("[Mod] x").is_empty());
    }

    #[test]
    fn detects_from_files() {
        let temp = tempfile::tempdir().unwrap();
        std::fs::write(temp.path().join("characters.txt"), "Zhongli, Venti").unwrap();
        std::fs::write(temp.path().join("mod.json"), r#"{"targetCharacters": ["venti", "Xiao"]}"#).unwrap();
        std::fs::create_dir(temp.path().join("sub")).unwrap();
        std::fs::write(temp.path().join("sub/a.ini"), "; character: Ei\n[TextureOverride]\n").unwrap();
        assert_eq!(detect_characters(temp.path()), vec!["Ei", "Venti", "Xiao", "Zhongli"]);
    }
}
