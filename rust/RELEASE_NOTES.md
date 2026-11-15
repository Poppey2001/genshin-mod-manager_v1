**Vorschau der neuen Rust-Version (Tauri).** Die bisherige Python-Version bleibt die Hauptversion und wird von diesem Release nicht automatisch ersetzt.

### Neu
- Komplett neuer Auto-Updater für Linux (AppImage) und Windows (Installer): signierte Updates, Kanal Stable/Pre-release, läuft im Tray weiter und sucht auch bei geschlossenem Fenster nach Updates.
- Bibliothek: Scan, Suche, Filter, Details, Vorschaubild, Aktivieren/Deaktivieren, Sammelaktionen, Konflikte übernehmen.
- Import von Ordnern und Archiven (ZIP, 7z, RAR, TAR) per Dialog oder Drag & Drop, inklusive Sicherheitsprüfung.
- INI-Analyse (Tasten, Zustände, Werte von Merge-/Master-INIs).
- Konflikte-Seite (Bibliothekskonflikte, manuell kopierte Mods, defekte/verwaiste Markierungen).
- Profile: speichern, anwenden, umbenennen, löschen.

### Kompatibel mit der Python-Version
Gleiche `config.json`, Bibliothek, Aktiv-Ordner, Manager-Markierungen und Profile. Beide Versionen können parallel verwendet werden.

### Noch nicht enthalten
GameBanana, Icons-Seite, Galerie-Ansicht, Duplikatprüfung, Mod-Updates/Backups. Diese Funktionen gibt es weiterhin in der Python-Version.

### Installation
- **Windows:** `…_x64-setup.exe` herunterladen und ausführen.
- **Linux:** `….AppImage` herunterladen, ausführbar machen (`chmod +x`) und starten.
