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
| Import: Ordner & Archive (ZIP/7z/RAR/TAR), Sicherheitsprüfung, Drag & Drop | ✅ |
| INI-Analyse (Tasten, Zustände, Werte) | ✅ |
| Konflikte-Seite | ✅ (ohne Duplikatprüfung per Hash) |
| Profile (speichern, anwenden, umbenennen, löschen) | ✅ |
| Einstellungen: Pfade pro Spiel, Sprache, Updates, Hintergrund, Autostart | ✅ |
| **Auto-Updater** (Linux AppImage + Windows, signiert, Tray, Hintergrund) | ✅ |
| Galerie-Ansicht | ⏳ |
| Duplikatprüfung (CRC32/SHA256) | ⏳ |
| GameBanana (Suche, Download, Mod-Updates, Backups) | ⏳ |
| Icons-Seite | ⏳ |

## Releases

Der Workflow `.github/workflows/rust.yml` veröffentlicht automatisch ein **Pre-Release**,
sobald auf `main` eine neue Version in `rust/Cargo.toml` (`[workspace.package] version`)
landet. Das Tag lautet `rust-v<version>` – der Updater der Python-Version ignoriert solche
Tags, Python-Nutzer werden also nicht automatisch umgestellt. Text des Releases:
`rust/RELEASE_NOTES.md`.

Für ein neues Release: Version in `rust/Cargo.toml` und `rust/package.json` erhöhen,
Release-Notes anpassen, auf `main` pushen.

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

Der öffentliche Schlüssel ist bereits in `src-tauri/tauri.conf.json`
(`plugins.updater.pubkey`) eingetragen. Der private Schlüssel gehört **nur** als Secret
ins GitHub-Repository (*Settings → Secrets and variables → Actions*):

- `TAURI_SIGNING_PRIVATE_KEY`: Inhalt der privaten Schlüsseldatei
- `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`: leer lassen bzw. nicht anlegen (Schlüssel ohne Passwort)

Neuen Schlüssel erzeugen (nur falls der alte verloren geht – dann können bestehende
Installationen nicht mehr automatisch aktualisieren):

```bash
cd rust
npx tauri signer generate -w ~/.tauri/gmm-updater.key
```

Fehlt das Secret, baut die CI das Release trotzdem, aber ohne Update-Pakete (`latest.json`).
