# Genshin Mod Manager – Rust-Port (Tauri 2)

Dieser Ordner enthält den Port des Mod Managers von Python/PySide6 nach **Rust + Tauri 2**.
Er entsteht **parallel**: Ausgeliefert wird weiterhin die Python-Version, bis der Port
alle Funktionen hat. Erst dann stellt die Release-CI auf Rust um.

## Aufbau

```text
rust/
├── crates/gmm-core/   Kernlogik ohne GUI (Config, Scanner, Mod-Manager, …) + Tests
├── src-tauri/         Tauri-App: Befehle, Tray, Auto-Updater
└── ui/                Oberfläche (Svelte 5 + TypeScript)
```

Übersetzungen und Icons werden **nicht kopiert**: Die UI liest direkt
`app/i18n/locales/*.json` und `assets/`. Nur neue Texte stehen in `ui/src/lib/locales/`.

## Kompatibilität mit der Python-Version

Beide Versionen können nebeneinander genutzt werden:

- gleiche `config.json` (gleicher Ort, gleiches Format; unbekannte Felder bleiben erhalten),
- gleiche Bibliotheks- und Aktiv-Ordner,
- gleiche Manager-Marker (`.gmm-managed.json`) und `DISABLED `-Umbenennung.

Ein von Python aktivierter Mod wird von Rust erkannt und umgekehrt
(getestet mit `cargo run -p gmm-core --example compat`).

## Portierungsstand

| Bereich | Status |
| --- | --- |
| Config inkl. Legacy-Migration | ✅ |
| Spiele-Registry (6 XXMI-Spiele) | ✅ |
| Bibliotheks-Scan, Struktur- & Charakter-Erkennung, Netzlaufwerke | ✅ |
| Aktivieren / Deaktivieren / Konflikt übernehmen (einzeln & Sammelaktion) | ✅ |
| Bibliothek: Liste, Filter, Suche, Details, Vorschau | ✅ |
| Einstellungen: Pfade pro Spiel, Sprache, Updates, Hintergrund, Autostart | ✅ |
| **Auto-Updater** (Linux AppImage + Windows, signiert, Tray, Hintergrund) | ✅ |
| Import (Ordner/Archive inkl. Sicherheitsprüfung) | ⏳ |
| INI-Analyse, Galerie-Ansicht | ⏳ |
| Konflikte-Seite | ⏳ |
| Profile | ⏳ |
| GameBanana (Suche, Download, Mod-Updates, Backups) | ⏳ |
| Icons-Seite | ⏳ |

## Entwickeln

Voraussetzungen: Rust (stable), Node.js 22, unter Linux zusätzlich
`libwebkit2gtk-4.1-dev libgtk-3-dev libayatana-appindicator3-dev librsvg2-dev`.

```bash
cd rust
npm install
npx tauri dev
```

Tests und Lint:

```bash
cargo test --workspace
cargo clippy --workspace --all-targets -- -D warnings
npm run check
```

Mit `GMM_PORTABLE_ROOT=/pfad` nutzt die App statt der echten Benutzerordner
`/pfad/config`, `/pfad/data` und `/pfad/cache` (praktisch zum Testen).

## Auto-Updater

Der neue Updater ersetzt die bisherigen Wege (In-App-Updater, Tray-Agents, Inno-Handoff,
Source-Build-Fallback) durch **einen** Mechanismus, der auf Linux und Windows gleich funktioniert:

1. Die App sucht über die GitHub-API das neueste Release des gewählten Kanals
   (Stable/Pre-release), das eine `latest.json` enthält.
2. `tauri-plugin-updater` prüft Version und **Signatur** und lädt das Paket der Plattform.
3. Linux: Die AppImage wird ersetzt und neu gestartet. Windows: Der NSIS-Installer läuft im
   Passiv-Modus (nur Fortschrittsbalken) und startet die App neu.

Beim Schließen läuft die App im **Tray** weiter (abschaltbar) und prüft im eingestellten
Intervall. Mit Autostart startet sie direkt im Tray. Ein separater Update-Agent ist nicht mehr nötig.

### Einmalig einrichten: Signatur-Schlüssel

Updates müssen signiert sein, sonst installiert der Updater sie nicht.

1. Schlüssel lokal erzeugen (den privaten Schlüssel niemals committen):

   ```bash
   cd rust
   npx tauri signer generate -w ~/.tauri/gmm-updater.key
   ```

2. Den Inhalt von `~/.tauri/gmm-updater.key.pub` in `src-tauri/tauri.conf.json` unter
   `plugins.updater.pubkey` eintragen.
3. Im GitHub-Repository unter *Settings → Secrets and variables → Actions* anlegen:
   `TAURI_SIGNING_PRIVATE_KEY` (Inhalt von `gmm-updater.key`) und
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`.

Solange kein Schlüssel eingetragen ist, meldet die App bei der Prüfung
„Der Updater ist in diesem Build nicht eingerichtet“. Die CI baut dann ohne Update-Pakete.
