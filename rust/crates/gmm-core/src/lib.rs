//! Kernlogik des Genshin Mod Managers (ohne GUI).
//!
//! Dieses Crate ist der Rust-Port der Python-Services unter `app/`. Es ist
//! bewusst unabhängig von Tauri, damit es vollständig getestet werden kann.

pub mod characters;
pub mod config;
pub mod games;
pub mod manager;
pub mod network;
pub mod paths;
pub mod scanner;
pub mod structure;

pub use config::{AppConfig, GameConfig};
pub use games::{all_games, find_game, get_game, GameDefinition};
pub use manager::{GameScope, ModManager, ModState};
pub use paths::{app_dirs, AppDirs};
pub use scanner::{ModInfo, ModScanner, ScanResult};

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("{0}")]
    Message(String),
    /// Der aktive Mods-Ordner ist nicht eingestellt.
    #[error("{0}")]
    NotConfigured(String),
    /// Am Ziel liegt ein fremder Ordner / mehrdeutiger Zustand.
    #[error("{0}")]
    Conflict(String),
    #[error("Vorgang abgebrochen")]
    Cancelled,
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error(transparent)]
    Json(#[from] serde_json::Error),
}

impl Error {
    pub fn kind(&self) -> &'static str {
        match self {
            Self::Message(_) | Self::Io(_) | Self::Json(_) => "error",
            Self::NotConfigured(_) => "not_configured",
            Self::Conflict(_) => "conflict",
            Self::Cancelled => "cancelled",
        }
    }
}

pub type Result<T, E = Error> = std::result::Result<T, E>;
