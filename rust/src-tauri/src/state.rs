use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};

use gmm_core::{app_dirs, AppConfig};
use tauri_plugin_updater::Update;

/// Gemeinsamer Zustand der App.
pub struct AppState {
    pub config: Mutex<AppConfig>,
    /// Abbruch-Flag des laufenden Bibliotheks-Scans.
    pub scan_cancel: Mutex<Option<Arc<AtomicBool>>>,
    /// Abbruch-Flag des laufenden Imports.
    pub import_cancel: Mutex<Option<Arc<AtomicBool>>>,
    /// Zuletzt gefundenes, noch nicht installiertes Update.
    pub pending_update: Mutex<Option<Update>>,
    /// Läuft gerade eine Updateprüfung oder Installation?
    pub update_busy: AtomicBool,
}

impl AppState {
    pub fn load() -> Self {
        Self {
            config: Mutex::new(AppConfig::load(app_dirs())),
            scan_cancel: Mutex::new(None),
            import_cancel: Mutex::new(None),
            pending_update: Mutex::new(None),
            update_busy: AtomicBool::new(false),
        }
    }

    pub fn config(&self) -> AppConfig {
        self.config.lock().expect("config lock").clone()
    }

    /// Ändert die Konfiguration und speichert sie sofort.
    pub fn update_config(&self, change: impl FnOnce(&mut AppConfig)) -> Result<AppConfig, String> {
        let mut guard = self.config.lock().expect("config lock");
        let mut next = guard.clone();
        change(&mut next);
        next.validate();
        next.save(app_dirs()).map_err(|error| error.to_string())?;
        *guard = next.clone();
        Ok(next)
    }
}
