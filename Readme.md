# Genshin Mod Manager

Ein unter Linux entwickelter Mod Manager zur Verwaltung von Genshin-Mods.

## Aktueller Entwicklungsstand

- PySide6-Benutzeroberfläche
- Linux-XDG-Konfiguration
- Auswahl eines lokalen Mods-Ordners
- Unterstützung eingehängter Netzlaufwerke
- Asynchroner Mod-Ordner-Scanner
- Erkennung von INI-Dateien und Symlinks

## Voraussetzungen

- Python 3.12 oder neuer
- PySide6
- platformdirs

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python main.py