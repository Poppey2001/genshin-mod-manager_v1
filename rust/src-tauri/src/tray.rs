//! Tray-Symbol: hält die App im Hintergrund am Leben, damit auch bei
//! geschlossenem Fenster nach Updates gesucht wird.

use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{AppHandle, Emitter, Manager, Wry};

use crate::state::AppState;

const TRAY_ID: &str = "main-tray";

struct Labels {
    open: &'static str,
    check: &'static str,
    install: &'static str,
    quit: &'static str,
}

fn labels(app: &AppHandle) -> Labels {
    if app.state::<AppState>().config().language == "de" {
        Labels { open: "Öffnen", check: "Nach Updates suchen", install: "Update installieren", quit: "Beenden" }
    } else {
        Labels { open: "Open", check: "Check for updates", install: "Install update", quit: "Quit" }
    }
}

fn build_menu(app: &AppHandle, update_version: Option<&str>) -> tauri::Result<Menu<Wry>> {
    let labels = labels(app);
    let open = MenuItem::with_id(app, "open", labels.open, true, None::<&str>)?;
    let check = MenuItem::with_id(app, "check", labels.check, true, None::<&str>)?;
    let separator = PredefinedMenuItem::separator(app)?;
    let quit = MenuItem::with_id(app, "quit", labels.quit, true, None::<&str>)?;
    match update_version {
        Some(version) => {
            let install =
                MenuItem::with_id(app, "install", format!("{} ({version})", labels.install), true, None::<&str>)?;
            Menu::with_items(app, &[&open, &install, &check, &separator, &quit])
        }
        None => Menu::with_items(app, &[&open, &check, &separator, &quit]),
    }
}

pub fn show_main_window(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

pub fn create(app: &AppHandle) -> tauri::Result<()> {
    let mut builder = TrayIconBuilder::with_id(TRAY_ID)
        .tooltip("Genshin Mod Manager")
        .menu(&build_menu(app, None)?)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, event| match event.id.as_ref() {
            "open" => show_main_window(app),
            "check" => {
                show_main_window(app);
                let _ = app.emit("request-update-check", ());
            }
            "install" => {
                show_main_window(app);
                let _ = app.emit("request-update-dialog", ());
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                show_main_window(tray.app_handle());
            }
        });
    if let Some(icon) = app.default_window_icon() {
        builder = builder.icon(icon.clone());
    }
    builder.build(app)?;
    Ok(())
}

/// Tray-Menü und Tooltip an ein gefundenes Update anpassen.
pub fn set_update_available(app: &AppHandle, version: Option<&str>) {
    let Some(tray) = app.tray_by_id(TRAY_ID) else { return };
    if let Ok(menu) = build_menu(app, version) {
        let _ = tray.set_menu(Some(menu));
    }
    let tooltip = match version {
        Some(version) => format!("Genshin Mod Manager – Update {version}"),
        None => "Genshin Mod Manager".to_string(),
    };
    let _ = tray.set_tooltip(Some(tooltip));
}

/// Nach einem Sprachwechsel neu beschriften.
pub fn refresh(app: &AppHandle) {
    let pending = app
        .state::<AppState>()
        .pending_update
        .lock()
        .ok()
        .and_then(|guard| guard.as_ref().map(|update| update.version.clone()));
    set_update_available(app, pending.as_deref());
}
