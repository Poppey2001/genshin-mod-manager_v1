//! Tauri-Anwendung des Genshin Mod Managers.

mod commands;
mod state;
mod tray;
mod updates;

use tauri::{Manager, WindowEvent};

/// Kommandozeilen-Flag des Autostarts: nur im Tray starten.
const BACKGROUND_FLAG: &str = "--background";

pub fn run() {
    let start_in_background = std::env::args().any(|arg| arg == BACKGROUND_FLAG);

    tauri::Builder::default()
        // Zweiter Start: vorhandenes Fenster nach vorne holen statt neue Instanz.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| tray::show_main_window(app)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_process::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec![BACKGROUND_FLAG]),
        ))
        .manage(state::AppState::load())
        .setup(move |app| {
            let handle = app.handle().clone();
            let config = app.state::<state::AppState>().config();

            if let Some(window) = app.get_webview_window("main") {
                let _ =
                    window.set_size(tauri::LogicalSize::new(config.window_width as f64, config.window_height as f64));
                if !(start_in_background && config.run_in_background) {
                    let _ = window.show();
                }
            }
            if let Err(error) = tray::create(&handle) {
                // Ohne Tray (z. B. Desktop ohne StatusNotifier) wird das Fenster beim
                // Schließen normal beendet.
                log::warn!("Tray konnte nicht erstellt werden: {error}");
            }
            updates::spawn_background_checks(handle);
            Ok(())
        })
        .on_window_event(|window, event| match event {
            WindowEvent::CloseRequested { api, .. } => {
                let app = window.app_handle();
                let state = app.state::<state::AppState>();
                if state.config().run_in_background && app.tray_by_id("main-tray").is_some() {
                    // Im Tray weiterlaufen, damit Updates gefunden werden.
                    api.prevent_close();
                    let _ = window.hide();
                }
            }
            WindowEvent::Resized(size) => {
                let Ok(scale) = window.scale_factor() else { return };
                let logical = size.to_logical::<f64>(scale);
                if logical.width >= 800.0 && logical.height >= 500.0 && !window.is_maximized().unwrap_or(false) {
                    let state = window.app_handle().state::<state::AppState>();
                    if let Ok(mut config) = state.config.lock() {
                        config.window_width = logical.width as i64;
                        config.window_height = logical.height as i64;
                    };
                }
            }
            WindowEvent::Destroyed => {
                let state = window.app_handle().state::<state::AppState>();
                let _ = state.config().save(gmm_core::app_dirs());
            }
            _ => {}
        })
        .invoke_handler(tauri::generate_handler![
            commands::bootstrap,
            commands::save_config,
            commands::set_autostart,
            commands::scan_library,
            commands::cancel_scan,
            commands::apply_mod_action,
            commands::open_path,
            commands::reveal_path,
            commands::launch_game,
            commands::check_for_update,
            commands::install_update,
            commands::skip_update,
            commands::check_import_sources,
            commands::import_mods,
            commands::cancel_import,
            commands::analyze_mod,
            commands::scan_conflicts,
            commands::list_profiles,
            commands::save_profile,
            commands::rename_profile,
            commands::delete_profile,
            commands::apply_profile,
        ])
        .build(tauri::generate_context!())
        .expect("Tauri-Anwendung konnte nicht gestartet werden")
        .run(|app, event| {
            if let tauri::RunEvent::ExitRequested { .. } = event {
                let state = app.state::<state::AppState>();
                let _ = state.config().save(gmm_core::app_dirs());
            }
        });
}
