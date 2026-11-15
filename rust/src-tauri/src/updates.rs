//! Auto-Updater: ein Mechanismus für Linux (AppImage) und Windows (NSIS).
//!
//! Ablauf:
//! 1. Über die GitHub-API das neueste Release des gewählten Kanals
//!    (stable / prerelease) suchen, das ein `latest.json` enthält.
//! 2. `tauri-plugin-updater` prüft Version und Signatur (minisign) und
//!    lädt das passende Paket für die aktuelle Plattform.
//! 3. Installation: AppImage wird ersetzt bzw. der NSIS-Installer läuft
//!    im Passiv-Modus; danach startet die App neu.
//!
//! Die Prüfung läuft auch im Hintergrund, solange die App im Tray ist.

use std::sync::atomic::Ordering;
use std::time::Duration;

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager};
use tauri_plugin_notification::NotificationExt;
use tauri_plugin_updater::UpdaterExt;

use crate::state::AppState;

const GITHUB_OWNER: &str = "Poppey2001";
const GITHUB_REPOSITORY: &str = "genshin-mod-manager_v1";
const MANIFEST_ASSET: &str = "latest.json";
const INITIAL_DELAY: Duration = Duration::from_secs(20);

#[derive(Debug, Clone, Serialize)]
pub struct UpdateMeta {
    pub version: String,
    pub current_version: String,
    pub notes: String,
    pub date: Option<String>,
    pub release_url: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(tag = "event", rename_all = "snake_case")]
pub enum InstallProgress {
    Started { total: Option<u64> },
    Progress { downloaded: u64, total: Option<u64> },
    Installing,
}

#[derive(Debug, Deserialize)]
struct GithubAsset {
    name: String,
    browser_download_url: String,
}

#[derive(Debug, Deserialize)]
struct GithubRelease {
    tag_name: String,
    html_url: String,
    #[serde(default)]
    body: Option<String>,
    #[serde(default)]
    draft: bool,
    #[serde(default)]
    prerelease: bool,
    #[serde(default)]
    assets: Vec<GithubAsset>,
}

fn parse_version(tag: &str) -> Option<semver::Version> {
    semver::Version::parse(tag.trim().trim_start_matches(['v', 'V'])).ok()
}

/// Neuestes passendes Release mit `latest.json` (Version, Manifest-URL, Release-Seite, Notizen).
async fn find_release(channel: &str) -> Result<Option<(semver::Version, String, String, String)>, String> {
    let url = format!("https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPOSITORY}/releases?per_page=30");
    let releases: Vec<GithubRelease> = reqwest::Client::new()
        .get(url)
        .header("Accept", "application/vnd.github+json")
        .header("User-Agent", "GenshinModManager-Updater")
        .timeout(Duration::from_secs(20))
        .send()
        .await
        .and_then(|response| response.error_for_status())
        .map_err(|error| format!("GitHub nicht erreichbar: {error}"))?
        .json()
        .await
        .map_err(|error| format!("Ungültige Antwort von GitHub: {error}"))?;

    Ok(releases
        .into_iter()
        .filter(|release| !release.draft && (channel == "prerelease" || !release.prerelease))
        .filter_map(|release| {
            let version = parse_version(&release.tag_name)?;
            let manifest = release.assets.iter().find(|asset| asset.name == MANIFEST_ASSET)?;
            Some((version, manifest.browser_download_url.clone(), release.html_url, release.body.unwrap_or_default()))
        })
        .max_by(|a, b| a.0.cmp(&b.0)))
}

fn updater_configured(app: &AppHandle) -> bool {
    app.config()
        .plugins
        .0
        .get("updater")
        .and_then(|value| value.get("pubkey"))
        .and_then(|value| value.as_str())
        .is_some_and(|key| !key.trim().is_empty())
}

/// Prüft auf ein Update. `Ok(None)` bedeutet: aktuell.
pub async fn check(app: &AppHandle) -> Result<Option<UpdateMeta>, String> {
    if !updater_configured(app) {
        return Err("Der Updater ist in diesem Build nicht eingerichtet (kein Signatur-Schlüssel).".into());
    }
    let state = app.state::<AppState>();
    let channel = state.config().update_channel;
    let Some((version, manifest_url, release_url, release_notes)) = find_release(&channel).await? else {
        return Ok(None);
    };
    let current = app.package_info().version.clone();
    if version <= current {
        return Ok(None);
    }
    let endpoint = manifest_url.parse().map_err(|error| format!("Ungültige Update-URL: {error}"))?;
    let update = app
        .updater_builder()
        .endpoints(vec![endpoint])
        .map_err(|error| error.to_string())?
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|error| error.to_string())?
        .check()
        .await
        .map_err(|error| format!("Updateprüfung fehlgeschlagen: {error}"))?;
    let Some(update) = update else { return Ok(None) };
    let meta = UpdateMeta {
        version: update.version.clone(),
        current_version: update.current_version.clone(),
        notes: update.body.clone().filter(|b| !b.trim().is_empty()).unwrap_or(release_notes),
        date: update.date.map(|d| d.to_string()),
        release_url,
    };
    *state.pending_update.lock().expect("update lock") = Some(update);
    Ok(Some(meta))
}

/// Lädt und installiert das zuvor gefundene Update, danach Neustart.
pub async fn install(app: &AppHandle) -> Result<(), String> {
    let state = app.state::<AppState>();
    let update = state
        .pending_update
        .lock()
        .expect("update lock")
        .take()
        .ok_or_else(|| "Kein Update zum Installieren vorhanden.".to_string())?;
    if state.update_busy.swap(true, Ordering::SeqCst) {
        *state.pending_update.lock().expect("update lock") = Some(update);
        return Err("Es läuft bereits ein Update-Vorgang.".into());
    }
    let emitter = app.clone();
    let mut downloaded: u64 = 0;
    let mut started = false;
    let result = update
        .download_and_install(
            |chunk, total| {
                if !started {
                    started = true;
                    let _ = emitter.emit("update-progress", InstallProgress::Started { total });
                }
                downloaded += chunk as u64;
                let _ = emitter.emit("update-progress", InstallProgress::Progress { downloaded, total });
            },
            || {
                let _ = emitter.emit("update-progress", InstallProgress::Installing);
            },
        )
        .await;
    state.update_busy.store(false, Ordering::SeqCst);
    result.map_err(|error| format!("Update konnte nicht installiert werden: {error}"))?;
    // Unter Windows beendet der NSIS-Installer die App selbst; unter Linux
    // wurde das AppImage ersetzt und wir starten neu.
    app.restart();
}

/// Hintergrundschleife: prüft periodisch, auch wenn das Fenster im Tray ist.
pub fn spawn_background_checks(app: AppHandle) {
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(INITIAL_DELAY).await;
        loop {
            let config = app.state::<AppState>().config();
            if config.auto_check_updates {
                background_check_once(&app).await;
            }
            let minutes = u64::from(app.state::<AppState>().config().update_check_interval_minutes.max(1));
            tokio::time::sleep(Duration::from_secs(minutes * 60)).await;
        }
    });
}

async fn background_check_once(app: &AppHandle) {
    let state = app.state::<AppState>();
    if state.update_busy.swap(true, Ordering::SeqCst) {
        return;
    }
    let result = check(app).await;
    state.update_busy.store(false, Ordering::SeqCst);
    match result {
        Ok(Some(meta)) => {
            if state.config().skipped_update_version == meta.version {
                return;
            }
            crate::tray::set_update_available(app, Some(&meta.version));
            let _ = app.emit("update-available", &meta);
            let window_visible =
                app.get_webview_window("main").and_then(|window| window.is_visible().ok()).unwrap_or(false);
            if !window_visible {
                let german = state.config().language == "de";
                let _ = app
                    .notification()
                    .builder()
                    .title("Genshin Mod Manager")
                    .body(if german {
                        format!("Version {} ist verfügbar. Über das Tray-Symbol installieren.", meta.version)
                    } else {
                        format!("Version {} is available. Install it from the tray icon.", meta.version)
                    })
                    .show();
            }
        }
        Ok(None) => crate::tray::set_update_available(app, None),
        Err(error) => log::warn!("Hintergrund-Updateprüfung fehlgeschlagen: {error}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_tags() {
        assert_eq!(parse_version("v0.6.0").unwrap(), semver::Version::new(0, 6, 0));
        assert!(parse_version("0.6.0-alpha.2").unwrap() > parse_version("0.6.0-alpha.1").unwrap());
        assert!(parse_version("0.4.0a1").is_none());
    }
}
