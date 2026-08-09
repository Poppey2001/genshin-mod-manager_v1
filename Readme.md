# Genshin Mod Manager

Ein moderner Desktop-Mod-Manager für **Genshin Impact**, geschrieben in Python mit **PySide6**.

Der Genshin Mod Manager verwaltet eine zentrale Mod-Bibliothek, scannt Mods asynchron, unterstützt Importe aus Ordnern und Archiven, erkennt Konflikte und ermöglicht das Aktivieren oder Deaktivieren von Mods über eine übersichtliche grafische Oberfläche.

> **Status:** Work in Progress  
> Das Projekt befindet sich aktiv in Entwicklung. Einzelne Bereiche wie Profile und die separate Konfliktseite sind noch nicht vollständig umgesetzt.

---

## Features

- Moderne Dark-Mode-Oberfläche mit PySide6
- Zentrale Mod-Bibliothek
- Asynchroner Bibliotheks-Scan
- Suche und Filter nach Charakter, Mod-Typ und Status
- Statistikübersicht für Mods, aktive Mods, Konflikte und Charaktere
- Detailansicht für ausgewählte Mods
- Aktivieren und Deaktivieren einzelner Mods
- Mehrfachauswahl und Bulk-Aktionen
- Konflikterkennung und Übernahme vorhandener Mod-Ordner
- Drag-and-Drop-Import
- Import aus Mod-Ordnern und Archiven
- Fortschrittsanzeige für Scan, Import und Bulk-Aktionen
- INI-Analyse für Merge-/Master-INI-Strukturen
- Konfigurierbarer Launcher-Pfad
- Unterstützung für lokale und eingehängte Netzwerkpfade
- Deutsche und englische Benutzeroberfläche
- Sprachwechsel zur Laufzeit
- Speicherung der gewählten Sprache
- Persistente Fenstergröße und Programmeinstellungen

---

## Unterstützte Importformate

```text
.zip
.7z
.rar
.tar
.tar.gz
.tgz
.tar.bz2
.tbz2
.tar.xz
.txz
```

Zusätzlich können vollständige Mod-Ordner direkt importiert werden.

---

## Installation

### Voraussetzungen

Empfohlen:

- Python 3.12 oder neuer
- Linux oder Windows
- Python Virtual Environment
- installierte Projektabhängigkeiten

Repository klonen:

```bash
git clone <DEIN-REPOSITORY>
cd genshin-mod-manager
```

Virtuelle Umgebung erstellen:

```bash
python -m venv .venv
```

Unter Linux aktivieren:

```bash
source .venv/bin/activate
```

Unter Windows:

```powershell
.venv\Scripts\activate
```

Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

Anwendung starten:

```bash
python main.py
```

Oder direkt mit der virtuellen Umgebung:

```bash
./.venv/bin/python main.py
```

---

## Erste Einrichtung

Nach dem ersten Start sollten unter **Einstellungen** mindestens die benötigten Pfade gesetzt werden.

### Mod-Bibliothek

Die Mod-Bibliothek ist der zentrale Speicherort für die vom Manager verwalteten Mods.

Unter Linux wird standardmäßig ein Verzeichnis unter folgendem Datenpfad verwendet:

```text
~/.local/share/genshin-mod-manager/mods
```

Es kann auch ein anderer lokaler oder eingehängter Netzwerkpfad verwendet werden.

### Aktiver Mods-Ordner

Hier wird der Ordner gewählt, aus dem der verwendete Genshin-Mod-Loader seine aktiven Mods lädt.

### Launcher

Optional kann ein Launcher oder Startprogramm hinterlegt werden, zum Beispiel ein AppImage, Shell-Skript, Wine-Programm oder Mod-Loader.

---

## Netzwerkpfade

Direkte Netzwerk-URLs wie:

```text
smb://server/share
nfs://server/share
```

werden nicht direkt als Mod-Pfad verwendet.

Das Netzlaufwerk sollte zuerst über das Betriebssystem oder den Dateimanager eingebunden werden, zum Beispiel unter:

```text
/mnt/...
/media/...
```

Anschließend kann der eingehängte Pfad im Mod Manager ausgewählt werden.

---

## Sprachen

Die Oberfläche unterstützt aktuell:

- Deutsch (`de`)
- English (`en`)

Die Sprache kann unter **Einstellungen** geändert werden. Der Sprachwechsel wird zur Laufzeit angewendet und in der Konfiguration gespeichert.

Neue Sprachen können über zusätzliche JSON-Dateien ergänzt werden:

```text
app/i18n/locales/
├── de.json
└── en.json
```

Das Übersetzungssystem befindet sich unter:

```text
app/i18n/
├── __init__.py
├── translator.py
└── locales/
```

---

## Konfiguration

Die Anwendung verwendet `platformdirs`, um Konfigurations-, Daten- und Cache-Verzeichnisse plattformgerecht zu verwalten.

Unter Linux liegt die Konfiguration standardmäßig hier:

```text
~/.config/genshin-mod-manager/config.json
```

Weitere Standardverzeichnisse:

```text
~/.local/share/genshin-mod-manager/
~/.cache/genshin-mod-manager/
```

Beispiel:

```json
{
    "library_path": null,
    "active_mods_path": null,
    "launcher_path": null,
    "selected_profile": "Default",
    "use_symlinks": false,
    "create_backups": true,
    "theme": "dark",
    "language": "de",
    "window_width": 1200,
    "window_height": 760,
    "first_start": false
}
```

---

## Projektstruktur

```text
genshin-mod-manager/
├── main.py
├── app/
│   ├── config.py
│   ├── main_window.py
│   ├── i18n/
│   │   ├── translator.py
│   │   └── locales/
│   │       ├── de.json
│   │       └── en.json
│   ├── pages/
│   │   ├── library_page.py
│   │   └── settings_page.py
│   ├── controllers/
│   ├── dialogs/
│   ├── models/
│   ├── services/
│   ├── utils/
│   ├── widgets/
│   │   └── library/
│   ├── workers/
│   ├── styles/
│   └── platform_support/
├── assets/
│   └── icons/
└── README.md
```

---

## Architektur

Die Anwendung ist in mehrere klar getrennte Bereiche aufgeteilt.

### Pages

Pages setzen die größeren Bereiche der Oberfläche zusammen, zum Beispiel `LibraryPage` und `SettingsPage`.

### Controllers

Controller koordinieren UI und Programmlogik. Dazu gehören unter anderem:

```text
LibraryScanController
LibraryImportController
LibraryBulkController
LibrarySelectionController
LibraryModActionController
LibraryHeaderController
```

### Services

Services übernehmen die eigentliche Mod- und Dateiverarbeitung, beispielsweise Scan, Mod-Verwaltung, Import und INI-Analyse.

### Workers

Längere Aufgaben laufen außerhalb des UI-Threads, damit die Oberfläche während Scan-, Import- und Bulk-Vorgängen bedienbar bleibt.

### Widgets

Die Library-Oberfläche besteht aus eigenständigen Widgets wie:

```text
LibraryHeader
LibraryFilterBar
LibraryStatsWidget
LibraryModListWidget
ModDetailsPanel
LibraryOperationStatusWidget
```

---

## Mod-Zustände

Mods können verschiedene Zustände besitzen:

```text
Enabled
Disabled
Conflict
Broken
Not configured
```

Die sichtbaren Bezeichnungen werden abhängig von der gewählten Sprache übersetzt.

---

## Konflikte

Der Manager soll vorhandene fremde Mod-Verzeichnisse nicht automatisch überschreiben.

Wenn am Ziel bereits ein nicht vom Manager verwalteter Mod-Ordner existiert, wird dieser als Konflikt erkannt. Ein vorhandener Ordner kann anschließend bewusst über **Konflikt übernehmen / Adopt conflict** in die Verwaltung übernommen werden.

---

## Bulk-Aktionen

Mehrere Mods können gleichzeitig ausgewählt werden.

Unterstützte Sammelaktionen:

```text
Aktivieren
Deaktivieren
Konflikte übernehmen
```

Bulk-Aktionen besitzen Fortschrittsanzeige, Ergebnisübersicht und Abbruchmöglichkeit.

---

## Entwicklung

Einzelne Datei prüfen:

```bash
./.venv/bin/python -m py_compile app/pages/library_page.py
```

Gesamtes `app`-Paket prüfen:

```bash
./.venv/bin/python -m compileall -q app
```

Translation-JSON prüfen:

```bash
./.venv/bin/python -m json.tool app/i18n/locales/de.json >/dev/null
./.venv/bin/python -m json.tool app/i18n/locales/en.json >/dev/null
```

Anwendung starten:

```bash
./.venv/bin/python main.py
```

---

## Geplante Funktionen

- Profile für unterschiedliche Mod-Zusammenstellungen
- Erweiterte Konfliktübersicht
- Weitere Sprachen
- Weitere Import- und Verwaltungsfunktionen
- Ausbau der Launcher-Integration
- Zusätzliche Mod-Metadaten
- Weitere INI-Analysefunktionen
- Packaging für eine einfachere Installation

---

## Hinweis

Dieses Projekt ist ein **inoffizielles Community-Projekt** und steht in keiner Verbindung zu HoYoverse.

Genshin Impact sowie zugehörige Namen und Marken gehören ihren jeweiligen Rechteinhabern.

Die Nutzung von Mods kann gegen Regeln oder Nutzungsbedingungen des jeweiligen Spiels oder Dienstes verstoßen. Die Verwendung erfolgt auf eigene Verantwortung.
