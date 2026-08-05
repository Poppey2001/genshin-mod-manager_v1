Genshin Mod Manager

Ein unter Linux entwickelter Desktop-Mod-Manager zur übersichtlichen Verwaltung von Genshin-Impact-Mods.

Der Manager verwaltet eine zentrale Mod-Bibliothek, erkennt Charaktere und Mod-Typen anhand der Ordnerstruktur und kann Mods durch vollständiges Kopieren aktivieren. Beim Deaktivieren wird der Mod-Ordner nicht gelöscht, sondern mit dem Präfix DISABLED  umbenannt. Dadurch bleiben Änderungen durch Fixing-Tools erhalten.

Hinweis: Dieses Projekt ist ein unabhängiges Community-Projekt und steht in keiner Verbindung zu HoYoverse. Die Verwendung von Mods erfolgt auf eigene Verantwortung. Prüfe vor der Nutzung die aktuellen Regeln des Spiels und der verwendeten Mod-Tools.

Funktionen

Moderne Linux-Oberfläche mit PySide6

Lokale Mod-Bibliotheken

Unterstützung eingehängter Netzlaufwerke

Asynchroner Ordner-Scanner

Erkennung verschachtelter Mod-Strukturen

Charakterfilter

Mod-Typ-Filter

Aktivieren und Deaktivieren von Mods

Vollständiges Kopieren statt Symlinks

Deaktivieren über das Präfix DISABLED 

Übernahme bereits vorhandener Mods

Konflikterkennung

Analyse von Merge.ini, Merged.ini und Master.ini

Anzeige erkannter Tasten, Variablen und Zustände

Speicherung der Programmeinstellungen über XDG-Verzeichnisse

Automatisches Speichern der Fenstergröße

Unterstützte Ordnerstruktur

Der Scanner unterstützt einfache Mod-Ordner:

Mod-Bibliothek/
└── Office Chiori/
    ├── mod.ini
    ├── Textures/
    └── Buffers/

Außerdem werden verschachtelte Strukturen erkannt:

Mod-Bibliothek/
└── Chiori/
    └── Character Skin/
        └── Office Chiori/
            ├── mod.ini
            ├── Textures/
            └── Buffers/

Daraus erkennt der Manager automatisch:

Charakter: Chiori
Mod-Typ:   Character Skin
Mod:       Office Chiori

Aktivieren und Deaktivieren

Beim ersten Aktivieren wird nur der eigentliche Mod-Ordner vollständig in den aktiven Mods-Ordner kopiert.

Bibliothek:
Chiori/Character Skin/Office Chiori/

Aktiver Mods-Ordner:
Office Chiori/

Beim Deaktivieren wird der Ordner nicht gelöscht:

Aktiv:
Office Chiori/

Deaktiviert:
DISABLED Office Chiori/

Beim erneuten Aktivieren wird der Ordner wieder zurückbenannt. Dadurch bleiben bereits reparierte oder durch Fixing-Tools veränderte Dateien erhalten.

Damit deaktivierte Mods vom verwendeten Loader ignoriert werden, sollte die Konfiguration eine passende Ausschlussregel besitzen, beispielsweise:

exclude_recursive = DISABLED*

Nach dem Umschalten eines Mods kann ein Reload über die dafür vorgesehene Funktion des verwendeten Loaders erforderlich sein.

Konflikte übernehmen

Existiert im aktiven Mods-Ordner bereits ein Mod, der noch nicht vom Manager verwaltet wird, erscheint der Status:

Konflikt

Über Konflikt übernehmen kann der vorhandene Ordner in die Verwaltung aufgenommen werden.

Dabei werden keine bestehenden Mod-Dateien überschrieben oder gelöscht. Der Manager legt lediglich eine interne Markierungsdatei an:

.gmm-managed.json

Existieren gleichzeitig eine aktive und eine deaktivierte Version desselben Mods, wird die automatische Übernahme aus Sicherheitsgründen abgelehnt.

INI-Analyse

Über den ?-Button hinter einem Mod kann der Manager steuernde INI-Dateien analysieren.

Unterstützt werden unter anderem:

Merge.ini
Merged.ini
Master.ini
CharacterMerge.ini
SkinMaster.ini

Erkannt und angezeigt werden beispielsweise:

[Key...]-Sektionen

belegte Tasten

Rückwärts-Tasten

cycle

toggle

hold

Bedingungen

Variablen

mögliche Zustände

CommandLists

zusammengeführte Mods

Kommentare aus der INI-Datei

Beispiel:

[KeySwap]
condition = $active == 1
key = h
type = cycle
$swapvar = 0, 1, 2

Der Manager zeigt daraus:

Taste: H
Typ: Wechsel zwischen mehreren Zuständen
Bedingung: $active == 1
Zustände: 0, 1 und 2

Die Analyse verändert keine INI-Dateien.

Voraussetzungen

Linux

Python 3.12 oder neuer

PySide6

platformdirs

Optional:

Git

ein bereits eingerichteter Mods-Ordner

ein eingehängtes SMB-, CIFS-, NFS-, SSHFS- oder GVFS-Netzlaufwerk

Installation

Repository klonen:

git clone https://github.com/DEIN-BENUTZERNAME/genshin-mod-manager.git
cd genshin-mod-manager

Virtuelle Umgebung erstellen:

python3 -m venv .venv
source .venv/bin/activate

Abhängigkeiten installieren:

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

Anwendung starten:

python main.py

Entwicklungsversion starten

cd /pfad/zum/genshin-mod-manager
source .venv/bin/activate
python main.py

Syntaxprüfung:

python -m compileall app main.py

Konfigurationspfade

Der Manager verwendet die XDG-Standardverzeichnisse unter Linux.

Konfiguration

~/.config/genshin-mod-manager/config.json

Programmdaten

~/.local/share/genshin-mod-manager/

Cache

~/.cache/genshin-mod-manager/

Die Mod-Bibliothek und der aktive Mods-Ordner können in den Einstellungen frei gewählt werden.

Netzwerk-Bibliotheken

Netzlaufwerke werden unterstützt, sofern sie bereits in das Linux-Dateisystem eingehängt wurden.

Beispiele:

/mnt/nas/genshin-mods
/media/martin/mods
/run/user/1000/gvfs/smb-share:server=nas,share=mods

Direkte Netzwerkadressen wie diese werden nicht verwendet:

smb://nas/mods
nfs://server/mods

Das Laufwerk muss zuerst über den Dateimanager oder das Betriebssystem eingebunden werden.

Zugriff prüfen:

test -r /mnt/nas/genshin-mods && echo "Lesbar"
test -w /mnt/nas/genshin-mods && echo "Beschreibbar"

Projektstruktur

genshin-mod-manager/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── main_window.py
│   ├── dialogs/
│   │   ├── __init__.py
│   │   └── mod_info_dialog.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── ini_analysis.py
│   │   └── mod.py
│   ├── pages/
│   │   ├── __init__.py
│   │   ├── library_page.py
│   │   └── settings_page.py
│   └── services/
│       ├── __init__.py
│       ├── character_detector.py
│       ├── ini_analyzer.py
│       ├── mod_manager.py
│       ├── mod_scanner.py
│       └── mod_structure_detector.py
└── assets/
    └── icons/

Aktueller Entwicklungsstand

Bereits umgesetzt:

PySide6-Hauptfenster

Linux-XDG-Konfiguration

Mod-Bibliothek

Netzwerkpfade

Asynchroner Scanner

Charaktererkennung

Mod-Typ-Erkennung

Charakter- und Mod-Typ-Filter

Aktivieren durch vollständiges Kopieren

Deaktivieren durch Umbenennen

Konfliktübernahme

Merge-/Master-INI-Analyse

Geplant:

Mehrfachauswahl für Mods

Mehrere Mod-Profile

Suchfeld

Vorschaubilder

Drag-and-drop-Import

ZIP- und Archiv-Import

Erweiterte Konfliktanalyse

Backup-Verwaltung

AppImage- oder Flatpak-Paket

Automatisierte Tests

Übersetzungen

Sicherheit

Der Manager versucht, fremde Ordner nicht automatisch zu überschreiben oder zu löschen.

Beim Deaktivieren werden nur Ordner umbenannt, die über eine gültige Manager-Markierung verfügen. Bereits vorhandene Mods müssen zuerst ausdrücklich übernommen werden.

Empfehlungen:

vor größeren Änderungen ein Backup erstellen

Bibliothek und aktiven Mods-Ordner getrennt halten

keine wichtigen Dateien direkt im aktiven Mods-Ordner ablegen

bei Netzlaufwerken auf eine stabile Verbindung achten

Änderungen zu GitHub hochladen

git status
git add .
git commit -m "Describe your changes"
git push

Mitwirken

Fehlerberichte, Verbesserungsvorschläge und Pull Requests sind willkommen.

Bei einem Fehlerbericht sind folgende Informationen hilfreich:

Linux-Distribution

Python-Version

PySide6-Version

verwendete Ordnerstruktur

vollständige Fehlermeldung

Schritte zum Reproduzieren

Lizenz

Für dieses Projekt ist derzeit noch keine Lizenz festgelegt.

Ohne eine hinzugefügte Lizenz bleiben alle Rechte beim jeweiligen Urheber. Vor einer öffentlichen Weiterverwendung oder Veröffentlichung sollte eine passende Open-Source-Lizenz ausgewählt werden.