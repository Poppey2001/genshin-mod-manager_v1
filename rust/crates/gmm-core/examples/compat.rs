//! Kompatibilitätstest gegen die Python-Version: `compat <root> <state|enable|disable>`
use gmm_core::{find_game, GameScope, ModManager, ModScanner};
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let root = PathBuf::from(&args[1]);
    let mut manager = ModManager::new(GameScope {
        game: find_game("genshin-impact").unwrap(),
        library_dir: root.join("lib"),
        active_mods_dir: Some(root.join("active")),
    });
    let source = root.join("lib/Furina/Character Skin/Summer");
    match args[2].as_str() {
        "enable" => drop(manager.enable(&source).unwrap()),
        "disable" => drop(manager.disable(&source).unwrap()),
        _ => {}
    }
    let result = ModScanner::new().scan(&root.join("lib"), None).unwrap();
    let mods: Vec<_> = result
        .mods
        .iter()
        .map(|m| serde_json::json!([m.name, m.mod_type, m.characters, m.file_count, m.ini_file_count, m.relative_path]))
        .collect();
    println!("{}", serde_json::json!({"state": manager.get_state(&source).as_str(), "mods": mods}));
}
