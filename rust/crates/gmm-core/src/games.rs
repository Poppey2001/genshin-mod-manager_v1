//! Unterstützte XXMI-Spiele (Port von `app/games/registry.py`).

use serde::Serialize;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize)]
pub struct GameDefinition {
    /// Stabile ID, identisch mit der Python-Version (`genshin-impact`, ...).
    pub id: &'static str,
    pub name: &'static str,
    pub short_name: &'static str,
    /// XXMI-Importer (GIMI, SRMI, ...).
    pub importer: &'static str,
    /// Ordnername unterhalb von `<DATA_DIR>/mods`.
    pub library_folder: &'static str,
    pub gamebanana_game_id: u32,
}

pub const GENSHIN_IMPACT: &str = "genshin-impact";

pub const SUPPORTED_GAMES: &[GameDefinition] = &[
    GameDefinition {
        id: GENSHIN_IMPACT,
        name: "Genshin Impact",
        short_name: "Genshin",
        importer: "GIMI",
        library_folder: "genshin-impact",
        gamebanana_game_id: 8552,
    },
    GameDefinition {
        id: "honkai-star-rail",
        name: "Honkai: Star Rail",
        short_name: "Star Rail",
        importer: "SRMI",
        library_folder: "honkai-star-rail",
        gamebanana_game_id: 18366,
    },
    GameDefinition {
        id: "zenless-zone-zero",
        name: "Zenless Zone Zero",
        short_name: "ZZZ",
        importer: "ZZMI",
        library_folder: "zenless-zone-zero",
        gamebanana_game_id: 19567,
    },
    GameDefinition {
        id: "wuthering-waves",
        name: "Wuthering Waves",
        short_name: "Wuthering Waves",
        importer: "WWMI",
        library_folder: "wuthering-waves",
        gamebanana_game_id: 20357,
    },
    GameDefinition {
        id: "honkai-impact-3rd",
        name: "Honkai Impact 3rd",
        short_name: "Honkai Impact 3rd",
        importer: "HIMI",
        library_folder: "honkai-impact-3rd",
        gamebanana_game_id: 10349,
    },
    GameDefinition {
        id: "arknights-endfield",
        name: "Arknights: Endfield",
        short_name: "Endfield",
        importer: "EFMI",
        library_folder: "arknights-endfield",
        gamebanana_game_id: 24320,
    },
];

pub fn all_games() -> &'static [GameDefinition] {
    SUPPORTED_GAMES
}

pub fn find_game(id: &str) -> Option<&'static GameDefinition> {
    let id = id.trim();
    SUPPORTED_GAMES.iter().find(|game| game.id.eq_ignore_ascii_case(id))
}

/// Wie `find_game`, fällt aber auf Genshin Impact zurück.
pub fn get_game(id: &str) -> &'static GameDefinition {
    find_game(id).unwrap_or(&SUPPORTED_GAMES[0])
}
