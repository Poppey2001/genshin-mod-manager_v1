from __future__ import annotations

import json
import logging
import shutil

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.config import (
    AppConfig,
    BACKUP_DIR,
)

from app.games.game_definition import (
    GameId,
)

from app.games.game_scope import (
    GameScope,
)

from app.platform_support import (
    normalized_path_key,
    paths_equal,
)


logger = logging.getLogger(
    __name__
)


# ============================================================
# Marker / IDs
# ============================================================

# Bestehenden Dateinamen bewusst weiterverwenden, damit bereits
# aktivierte Mods nicht "verloren" gehen.
MANAGER_MARKER = ".gmm-managed.json"

# Wird zusätzlich erkannt und ignoriert, falls wir später auf den
# neuen Dateinamen wechseln.
NEXT_MANAGER_MARKER = ".xxmimm-managed.json"

MANAGER_ID = "xxmi-mod-manager"
LEGACY_MANAGER_ID = "genshin-mod-manager"

DISABLED_PREFIX = "DISABLED "


# ============================================================
# Status
# ============================================================

class ModState(
    str,
    Enum,
):
    """Aktueller Aktivierungszustand eines Mods."""

    NOT_CONFIGURED = "not_configured"
    DISABLED = "disabled"
    ENABLED = "enabled"
    BROKEN = "broken"
    CONFLICT = "conflict"


STATE_LABELS = {
    ModState.NOT_CONFIGURED: "Nicht konfiguriert",
    ModState.DISABLED: "Deaktiviert",
    ModState.ENABLED: "Aktiviert",
    ModState.BROKEN: "Defekte Verknüpfung",
    ModState.CONFLICT: "Konflikt",
}


# ============================================================
# Exceptions
# ============================================================

class ModManagerError(
    Exception
):
    """Grundfehler der Mod-Verwaltung."""


class ModNotConfiguredError(
    ModManagerError
):
    """Der aktive Mods-Ordner wurde nicht eingestellt."""


class ModConflictError(
    ModManagerError
):
    """Am Ziel existiert bereits eine fremde Datei oder ein fremder Ordner."""


# ============================================================
# ModManager
# ============================================================

class ModManager:
    """
    Aktiviert und deaktiviert Mods aus der Bibliothek
    des aktuell ausgewählten XXMI-Spiels.

    Der Manager arbeitet primär mit GameScope.

    Aus Kompatibilitätsgründen kann auch AppConfig direkt
    übergeben werden. In diesem Fall wird automatisch ein
    GameScope für config.selected_game erzeugt.
    """

    def __init__(
        self,
        config: GameScope | AppConfig,
    ) -> None:
        if isinstance(
            config,
            GameScope,
        ):
            self.config = config
        else:
            self.config = GameScope(
                config=config,
                game_id=config.selected_game,
            )

    # ========================================================
    # Spielinformationen
    # ========================================================

    @property
    def game_id(
        self,
    ) -> str:
        return self.config.game_id

    @property
    def importer(
        self,
    ) -> str:
        return self.config.importer

    # ========================================================
    # Öffentliche API
    # ========================================================

    def get_state(
        self,
        mod_path: Path | str,
    ) -> ModState:
        """
        Ermittelt den aktuellen Aktivierungszustand.

        Unterstützt:
        - neue relative Active-Mod-Struktur
        - alte flache Manager-Struktur
        - alte Symlink-Aktivierungen
        - nicht verwaltete Ordner
        """

        try:
            (
                source,
                relative_path,
            ) = (
                self._source_and_relative(
                    mod_path,
                    require_exists=False,
                )
            )

            active_root = (
                self._get_active_root(
                    create=False
                )
            )

            (
                enabled_path,
                disabled_path,
            ) = (
                self._resolve_destination_paths(
                    active_root=active_root,
                    source=source,
                    relative_path=relative_path,
                )
            )

        except ModNotConfiguredError:
            return (
                ModState.NOT_CONFIGURED
            )

        except ModManagerError:
            return (
                ModState.CONFLICT
            )

        enabled_exists = (
            self._path_exists(
                enabled_path
            )
        )

        disabled_exists = (
            self._path_exists(
                disabled_path
            )
        )

        # ----------------------------------------------------
        # Beide Varianten gleichzeitig
        # ----------------------------------------------------

        if (
            enabled_exists
            and disabled_exists
        ):
            return (
                ModState.CONFLICT
            )

        # ----------------------------------------------------
        # Legacy Symlink
        # ----------------------------------------------------

        if enabled_path.is_symlink():
            if not enabled_path.exists():
                return (
                    ModState.BROKEN
                )

            if self._symlink_points_to(
                destination=enabled_path,
                source=source,
            ):
                return (
                    ModState.ENABLED
                )

            return (
                ModState.CONFLICT
            )

        if disabled_path.is_symlink():
            return (
                ModState.CONFLICT
            )

        # ----------------------------------------------------
        # Aktiver Ordner
        # ----------------------------------------------------

        if enabled_exists:
            if self._marker_matches(
                destination=enabled_path,
                source=source,
            ):
                return (
                    ModState.ENABLED
                )

            # Ordner existiert, gehört aber nicht
            # zu diesem Library-Mod.
            return (
                ModState.CONFLICT
            )

        # ----------------------------------------------------
        # Deaktivierter Ordner
        # ----------------------------------------------------

        if disabled_exists:
            if self._marker_matches(
                destination=disabled_path,
                source=source,
            ):
                return (
                    ModState.DISABLED
                )

            return (
                ModState.CONFLICT
            )

        # ----------------------------------------------------
        # Weder aktiv noch deaktiviert vorhanden
        # ----------------------------------------------------

        return (
            ModState.DISABLED
        )

    def adopt_existing(
        self,
        mod_path: Path | str,
    ) -> ModState:
        """
        Übernimmt einen bereits vorhandenen Mod-Ordner,
        ohne dessen Dateien zu überschreiben.
        """

        source, relative_path = (
            self._source_and_relative(
                mod_path,
                require_exists=True,
            )
        )

        active_root = (
            self._get_active_root(
                create=True,
            )
        )

        (
            enabled_path,
            disabled_path,
        ) = (
            self._resolve_destination_paths(
                active_root=active_root,
                source=source,
                relative_path=relative_path,
            )
        )

        enabled_exists = (
            enabled_path.exists()
            or enabled_path.is_symlink()
        )

        disabled_exists = (
            disabled_path.exists()
            or disabled_path.is_symlink()
        )

        if (
            enabled_exists
            and disabled_exists
        ):
            raise ModConflictError(
                (
                    "Der Konflikt kann nicht automatisch "
                    "übernommen werden, weil eine aktive "
                    "und eine deaktivierte Version existieren."
                    "\n\n"
                    f"Aktiv:\n{enabled_path}\n\n"
                    f"Deaktiviert:\n{disabled_path}"
                )
            )

        if (
            not enabled_exists
            and not disabled_exists
        ):
            raise ModConflictError(
                (
                    "Es wurde kein vorhandener Zielordner "
                    "gefunden, der übernommen werden könnte."
                )
            )

        if enabled_exists:
            destination = enabled_path
            resulting_state = ModState.ENABLED
        else:
            destination = disabled_path
            resulting_state = ModState.DISABLED

        if destination.is_symlink():
            raise ModConflictError(
                (
                    "Symbolische Verknüpfungen können nicht "
                    "als bestehende Mod-Kopie übernommen werden."
                    "\n\n"
                    f"Pfad: {destination}"
                )
            )

        if not destination.is_dir():
            raise ModConflictError(
                (
                    "Das vorhandene Ziel ist kein Ordner."
                    "\n\n"
                    f"Pfad: {destination}"
                )
            )

        if self._marker_matches(
            destination=destination,
            source=source,
        ):
            return resulting_state

        if self._has_any_manager_marker(
            destination
        ):
            raise ModConflictError(
                (
                    "Der Ordner besitzt bereits eine "
                    "Manager-Markierung, die zu einem "
                    "anderen Mod oder Spiel gehört."
                    "\n\n"
                    f"Pfad: {destination}"
                )
            )

        try:
            self._write_marker(
                destination=destination,
                source=source,
                relative_path=relative_path,
            )

        except OSError as error:
            raise ModManagerError(
                (
                    "Der vorhandene Mod-Ordner konnte "
                    "nicht übernommen werden."
                    "\n\n"
                    f"Pfad: {destination}\n\n"
                    f"{error}"
                )
            ) from error

        return resulting_state

    def enable(
        self,
        mod_path: Path | str,
    ) -> Path:
        """
        Aktiviert genau einen Mod aus der Bibliothek.

        Neue Aktivierungen werden flach direkt unterhalb des
        Active-Mods-Ordners abgelegt. Eine bereits vorhandene alte
        relative Manager-Struktur wird aus Kompatibilitätsgründen
        weiterhin erkannt.

        Eine deaktivierte, vom Manager verwaltete Kopie wird nur
        umbenannt. Dadurch bleiben Änderungen an der aktiven Kopie
        erhalten und es wird keine zweite Kopie erzeugt.
        """
        source, relative_path = self._source_and_relative(
            mod_path,
            require_exists=True,
        )

        active_root = self._get_active_root(
            create=True,
        )

        enabled_path, disabled_path = self._resolve_destination_paths(
            active_root=active_root,
            source=source,
            relative_path=relative_path,
        )

        enabled_exists = self._path_exists(enabled_path)
        disabled_exists = self._path_exists(disabled_path)

        if enabled_exists and disabled_exists:
            raise ModConflictError(
                "Die aktive und die deaktivierte Version existieren "
                "gleichzeitig.\n\n"
                f"Aktiv: {enabled_path}\n"
                f"Deaktiviert: {disabled_path}"
            )

        # Bereits aktiv.
        if enabled_exists:
            if enabled_path.is_symlink():
                if self._symlink_points_to(
                    destination=enabled_path,
                    source=source,
                ):
                    return enabled_path

                raise ModConflictError(
                    "Am aktiven Ziel befindet sich eine fremde "
                    "symbolische Verknüpfung.\n\n"
                    f"Ziel: {enabled_path}"
                )

            if self._marker_matches(
                destination=enabled_path,
                source=source,
            ):
                return enabled_path

            raise ModConflictError(
                "Am aktiven Ziel befindet sich ein nicht vom Manager "
                "verwalteter Ordner.\n\n"
                f"Ziel: {enabled_path}"
            )

        # Bereits deaktivierte Manager-Kopie reaktivieren.
        if disabled_exists:
            if disabled_path.is_symlink():
                raise ModConflictError(
                    "Der deaktivierte Zielpfad ist eine symbolische "
                    "Verknüpfung und wird nicht automatisch verändert."
                    "\n\n"
                    f"Ordner: {disabled_path}"
                )

            if not self._marker_matches(
                destination=disabled_path,
                source=source,
            ):
                raise ModConflictError(
                    "Der deaktivierte Ordner besitzt keine gültige "
                    "Manager-Markierung.\n\n"
                    f"Ordner: {disabled_path}"
                )

            try:
                enabled_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                disabled_path.rename(enabled_path)
            except OSError as error:
                raise ModManagerError(
                    "Der deaktivierte Mod konnte nicht aktiviert werden."
                    "\n\n"
                    f"Quelle: {disabled_path}\n"
                    f"Ziel: {enabled_path}\n\n"
                    f"{error}"
                ) from error

            return enabled_path

        # Erste Aktivierung: nur den vom Scanner gelieferten Mod-Ordner
        # kopieren, niemals seine Library-Eltern (Charakter/Typ/etc.).
        try:
            enabled_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            shutil.copytree(
                source,
                enabled_path,
                symlinks=False,
                ignore=self._copy_ignore,
            )
            self._write_marker(
                destination=enabled_path,
                source=source,
                relative_path=relative_path,
            )
        except OSError as error:
            self._rollback_destination(enabled_path)
            raise ModManagerError(
                "Der Mod konnte nicht kopiert werden.\n\n"
                f"Quelle: {source}\n"
                f"Ziel: {enabled_path}\n\n"
                f"{error}"
            ) from error

        return enabled_path
    def disable(
        self,
        mod_path: Path | str,
    ) -> bool:
        """
        Deaktiviert einen Mod durch Umbenennen.

        Alle Änderungen, die ein Fixing-Tool an der aktiven
        Kopie vorgenommen hat, bleiben dadurch erhalten.
        """

        source, relative_path = (
            self._source_and_relative(
                mod_path,
                require_exists=False,
            )
        )

        active_root = (
            self._get_active_root(
                create=False,
            )
        )

        (
            enabled_path,
            disabled_path,
        ) = (
            self._resolve_destination_paths(
                active_root=active_root,
                source=source,
                relative_path=relative_path,
            )
        )

        if (
            self._path_exists(
                enabled_path
            )
            and self._path_exists(
                disabled_path
            )
        ):
            raise ModConflictError(
                (
                    "Die aktive und die deaktivierte "
                    "Version existieren gleichzeitig."
                    "\n\n"
                    f"Aktiv: {enabled_path}\n"
                    f"Deaktiviert: {disabled_path}"
                )
            )

        if self._path_exists(
            disabled_path
        ):
            if (
                not disabled_path.is_symlink()
                and self._marker_matches(
                    destination=disabled_path,
                    source=source,
                )
            ):
                return False

            raise ModConflictError(
                (
                    "Der deaktivierte Zielordner wird "
                    "nicht vom Manager verwaltet."
                    "\n\n"
                    f"Ordner: {disabled_path}"
                )
            )

        if not self._path_exists(
            enabled_path
        ):
            return False

        if enabled_path.is_symlink():
            raise ModConflictError(
                (
                    "Eine alte Symlink-Aktivierung wurde erkannt. "
                    "Sie wird nicht automatisch in eine verwaltete "
                    "Kopie umgewandelt."
                    "\n\n"
                    f"Ordner: {enabled_path}"
                )
            )

        if not self._marker_matches(
            destination=enabled_path,
            source=source,
        ):
            raise ModConflictError(
                (
                    "Der aktive Ordner besitzt keine gültige "
                    "Manager-Markierung und wird nicht verändert."
                    "\n\n"
                    f"Ordner: {enabled_path}"
                )
            )

        try:
            enabled_path.rename(
                disabled_path
            )

        except OSError as error:
            raise ModManagerError(
                (
                    "Der Mod konnte nicht deaktiviert werden."
                    "\n\n"
                    f"{error}"
                )
            ) from error

        return True

    def destination_for(
        self,
        mod_path: Path | str,
    ) -> Path:
        """
        Gibt den aktiven Zielpfad zurück.
        """

        source, relative_path = (
            self._source_and_relative(
                mod_path,
                require_exists=False,
            )
        )

        active_root = (
            self._get_active_root(
                create=False,
            )
        )

        (
            enabled_path,
            _disabled_path,
        ) = (
            self._resolve_destination_paths(
                active_root=active_root,
                source=source,
                relative_path=relative_path,
            )
        )

        return enabled_path

    def inspection_path_for(
        self,
        mod_path: Path | str,
    ) -> Path:
        """
        Gibt den besten Ordner für die INI-Analyse zurück.

        Reihenfolge:
        1. aktive Mod-Kopie
        2. deaktivierte Mod-Kopie
        3. Original in der Bibliothek
        """

        source, relative_path = (
            self._source_and_relative(
                mod_path,
                require_exists=False,
            )
        )

        try:
            active_root = (
                self._get_active_root(
                    create=False,
                )
            )

        except ModManagerError:
            return source

        (
            enabled_path,
            disabled_path,
        ) = (
            self._resolve_destination_paths(
                active_root=active_root,
                source=source,
                relative_path=relative_path,
            )
        )

        if enabled_path.is_dir():
            return enabled_path

        if disabled_path.is_dir():
            return disabled_path

        return source

    # ========================================================
    # Zielpfade
    # ========================================================

    @staticmethod
    def _destination_paths(
        active_root: Path,
        source: Path,
    ) -> tuple[
        Path,
        Path,
    ]:
        """
        Legacy-Zielpfade.

        Ältere Versionen des Managers haben Mods direkt
        unterhalb des Active-Mods-Ordners abgelegt:

            Mods/My Mod
            Mods/DISABLED My Mod

        Diese Struktur muss weiterhin erkannt werden.
        """

        enabled_path = (
            active_root
            / source.name
        )

        disabled_path = (
            active_root
            / (
                f"{DISABLED_PREFIX}"
                f"{source.name}"
            )
        )

        return (
            enabled_path,
            disabled_path,
        )

    @staticmethod
    def _relative_destination_paths(
        active_root: Path,
        relative_path: Path,
    ) -> tuple[
        Path,
        Path,
    ]:
        """
        Neue bevorzugte Zielstruktur.

        Beispiel:

            Library:
            Characters/Arlecchino/My Mod

            Active:
            Characters/Arlecchino/My Mod

        Die deaktivierte Variante liegt daneben:

            Characters/Arlecchino/DISABLED My Mod
        """

        enabled_path = (
            active_root
            / relative_path
        )

        disabled_path = (
            enabled_path.parent
            / (
                f"{DISABLED_PREFIX}"
                f"{enabled_path.name}"
            )
        )

        return (
            enabled_path,
            disabled_path,
        )

    def _resolve_destination_paths(
        self,
        *,
        active_root: Path,
        source: Path,
        relative_path: Path,
    ) -> tuple[
        Path,
        Path,
    ]:
        """
        Ermittelt den tatsächlich verwendeten Zielpfad.

        Neue Mods werden flach abgelegt:

            Library/Arlecchino/Character Skin/My Mod
            -> Active Mods/My Mod

        Bereits existierende Installationen im alten relativen Layout
        werden weiterhin erkannt, damit bestehende Nutzer nichts
        verlieren. Existieren relative und flache Variante gleichzeitig,
        wird aus Sicherheitsgründen ein Konflikt gemeldet.
        """
        relative_layout = self._relative_destination_paths(
            active_root=active_root,
            relative_path=relative_path,
        )
        flat_layout = self._destination_paths(
            active_root=active_root,
            source=source,
        )

        if relative_layout == flat_layout:
            return flat_layout

        occupied: list[tuple[Path, Path]] = []
        for enabled_path, disabled_path in (
            relative_layout,
            flat_layout,
        ):
            if (
                self._path_exists(enabled_path)
                or self._path_exists(disabled_path)
            ):
                occupied.append((enabled_path, disabled_path))

        if len(occupied) > 1:
            raise ModConflictError(
                "Der Mod wurde an mehreren Active-Mods-Speicherorten "
                "gefunden.\n\n"
                "Relative Struktur:\n"
                f"{relative_layout[0]}\n"
                f"{relative_layout[1]}\n\n"
                "Flache Struktur:\n"
                f"{flat_layout[0]}\n"
                f"{flat_layout[1]}"
            )

        if occupied:
            return occupied[0]

        # Für neue Mods immer die flache XXMI-Struktur verwenden.
        return flat_layout
    def _source_and_relative(
        self,
        mod_path: Path | str,
        require_exists: bool,
    ) -> tuple[
        Path,
        Path,
    ]:
        library_root = (
            self._absolute_path(
                self.config.mod_library_directory
            )
        )

        source = (
            self._absolute_path(
                Path(
                    mod_path
                )
            )
        )

        try:
            relative_path = (
                source.relative_to(
                    library_root
                )
            )

        except ValueError as error:
            raise ModManagerError(
                (
                    "Der ausgewählte Mod liegt nicht "
                    "innerhalb der konfigurierten "
                    "Mod-Bibliothek."
                )
            ) from error

        if relative_path == Path(
            "."
        ):
            raise ModManagerError(
                (
                    "Die komplette Mod-Bibliothek "
                    "kann nicht als Mod aktiviert werden."
                )
            )

        if require_exists:
            if not source.exists():
                raise ModManagerError(
                    (
                        "Der Mod-Ordner existiert nicht "
                        "oder das Laufwerk ist nicht "
                        "eingehängt."
                        "\n\n"
                        f"Quelle: {source}"
                    )
                )

            if not source.is_dir():
                raise ModManagerError(
                    (
                        "Der Mod-Pfad ist kein "
                        f"Verzeichnis: {source}"
                    )
                )

        return (
            source,
            relative_path,
        )

    def _get_active_root(
        self,
        create: bool,
    ) -> Path:
        configured_path = (
            self.config.active_mods_directory
        )

        if configured_path is None:
            raise ModNotConfiguredError(
                (
                    "Wähle unter Einstellungen zuerst "
                    "den aktiven Mods-Ordner aus."
                )
            )

        active_root = (
            self._absolute_path(
                configured_path
            )
        )

        library_root = (
            self._absolute_path(
                self.config.mod_library_directory
            )
        )

        if self._paths_overlap(
            library_root,
            active_root,
        ):
            raise ModManagerError(
                (
                    "Mod-Bibliothek und aktiver Mods-Ordner "
                    "dürfen nicht identisch oder ineinander "
                    "verschachtelt sein."
                )
            )

        if create:
            try:
                active_root.mkdir(
                    parents=True,
                    exist_ok=True,
                )

            except OSError as error:
                raise ModManagerError(
                    (
                        "Der aktive Mods-Ordner konnte "
                        "nicht erstellt werden."
                        "\n\n"
                        f"{error}"
                    )
                ) from error

        return active_root

    # ========================================================
    # Marker
    # ========================================================

    def _write_marker(
        self,
        destination: Path,
        source: Path,
        relative_path: Path,
    ) -> None:
        marker_file = (
            destination
            / MANAGER_MARKER
        )

        temporary_file = (
            destination
            / (
                f"{MANAGER_MARKER}"
                ".tmp"
            )
        )

        marker_data = {
            "manager": MANAGER_ID,
            "game_id": self.game_id,
            "importer": self.importer,
            "source": str(
                source
            ),
            "source_key": normalized_path_key(
                source
            ),
            "relative_path": str(
                relative_path
            ),
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

        temporary_file.write_text(
            json.dumps(
                marker_data,
                indent=4,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        temporary_file.replace(
            marker_file
        )

    def _marker_matches(
        self,
        destination: Path,
        source: Path,
    ) -> bool:
        for marker_file in (
            self._marker_files(
                destination
            )
        ):
            if not marker_file.is_file():
                continue

            marker_data = (
                self._load_marker(
                    marker_file
                )
            )

            if marker_data is None:
                continue

            if self._marker_data_matches(
                marker_data=marker_data,
                source=source,
            ):
                return True

        return False

    def _marker_data_matches(
        self,
        marker_data: dict,
        source: Path,
    ) -> bool:
        # ----------------------------------------------------
        # Manager
        # ----------------------------------------------------

        marker_manager = (
            marker_data.get(
                "manager"
            )
        )

        if (
            marker_manager is not None
            and marker_manager
            not in {
                MANAGER_ID,
                LEGACY_MANAGER_ID,
            }
        ):
            return False

        # ----------------------------------------------------
        # Spiel
        # ----------------------------------------------------

        marker_game_id = (
            marker_data.get(
                "game_id"
            )
        )

        if marker_game_id is None:
            # Alte Marker ohne game_id können nur von der
            # ursprünglichen Genshin-Version stammen.
            if (
                self.game_id
                != GameId.GENSHIN_IMPACT.value
            ):
                return False

        elif (
            not isinstance(
                marker_game_id,
                str,
            )
            or marker_game_id
            != self.game_id
        ):
            return False

        # ----------------------------------------------------
        # Neuer Source-Key
        # ----------------------------------------------------

        stored_source_key = (
            marker_data.get(
                "source_key"
            )
        )

        if isinstance(
            stored_source_key,
            str,
        ):
            if (
                stored_source_key
                == normalized_path_key(
                    source
                )
            ):
                return True

        # ----------------------------------------------------
        # Alte Marker
        # ----------------------------------------------------

        for field_name in (
            "source",
            "source_path",
        ):
            stored_source = (
                marker_data.get(
                    field_name
                )
            )

            if not isinstance(
                stored_source,
                str,
            ):
                continue

            if paths_equal(
                stored_source,
                source,
            ):
                return True

        return False

    @staticmethod
    def _load_marker(
        marker_file: Path,
    ) -> dict | None:
        try:
            marker_data = json.loads(
                marker_file.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
            TypeError,
        ):
            return None

        if not isinstance(
            marker_data,
            dict,
        ):
            return None

        return marker_data

    @staticmethod
    def _marker_files(
        destination: Path,
    ) -> tuple[
        Path,
        Path,
    ]:
        return (
            destination
            / MANAGER_MARKER,
            destination
            / NEXT_MANAGER_MARKER,
        )

    def _has_any_manager_marker(
        self,
        destination: Path,
    ) -> bool:
        return any(
            marker.exists()
            for marker in self._marker_files(
                destination
            )
        )

    # ========================================================
    # Copy / Backup
    # ========================================================

    @staticmethod
    def _copy_ignore(
        _directory: str,
        names: list[str],
    ) -> set[str]:
        ignored_names = {
            MANAGER_MARKER,
            f"{MANAGER_MARKER}.tmp",
            NEXT_MANAGER_MARKER,
            f"{NEXT_MANAGER_MARKER}.tmp",
        }

        return {
            name
            for name in names
            if name in ignored_names
        }

    def _backup_managed_copy(
        self,
        destination: Path,
        relative_path: Path,
    ) -> Path:
        """
        Erstellt bei Bedarf ein spielbezogenes Backup.

        Die Methode bleibt als interne API erhalten, auch wenn
        die aktuelle Enable/Disable-Strategie durch Umbenennen
        normalerweise kein Backup benötigt.
        """

        timestamp = (
            datetime.now()
            .strftime(
                "%Y%m%d-%H%M%S-%f"
            )
        )

        backup_destination = (
            BACKUP_DIR
            / self.game_id
            / timestamp
            / relative_path
        )

        backup_destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copytree(
            destination,
            backup_destination,
            symlinks=True,
        )

        return backup_destination

    # ========================================================
    # Legacy Symlink-Erkennung
    # ========================================================

    @staticmethod
    def _symlink_points_to(
        destination: Path,
        source: Path,
    ) -> bool:
        try:
            link_target = (
                destination.readlink()
            )

            if not link_target.is_absolute():
                link_target = (
                    destination.parent
                    / link_target
                )

            return (
                link_target.resolve(
                    strict=False
                )
                == source.resolve(
                    strict=False
                )
            )

        except OSError:
            return False

    # ========================================================
    # Hilfsmethoden
    # ========================================================

    @staticmethod
    def _path_exists(
        path: Path,
    ) -> bool:
        return (
            path.exists()
            or path.is_symlink()
        )

    @staticmethod
    def _rollback_destination(
        destination: Path,
    ) -> None:
        try:
            if destination.is_symlink():
                destination.unlink()

            elif destination.exists():
                shutil.rmtree(
                    destination
                )

        except OSError:
            logger.exception(
                (
                    "Rollback für Mod-Ziel "
                    "fehlgeschlagen: %s"
                ),
                destination,
            )

    @staticmethod
    def _absolute_path(
        path: Path | str,
    ) -> Path:
        return (
            Path(
                path
            )
            .expanduser()
            .absolute()
        )

    @classmethod
    def _paths_overlap(
        cls,
        first: Path,
        second: Path,
    ) -> bool:
        return (
            first == second
            or cls._path_is_inside(
                first,
                second,
            )
            or cls._path_is_inside(
                second,
                first,
            )
        )

    @staticmethod
    def _path_is_inside(
        path: Path,
        parent: Path,
    ) -> bool:
        try:
            path.relative_to(
                parent
            )

            return True

        except ValueError:
            return False


# ============================================================
# UI Helper
# ============================================================

def mod_state_label(
    state: ModState,
) -> str:
    return STATE_LABELS.get(
        state,
        state.value,
    )


__all__ = [
    "ModState",
    "ModManager",
    "ModManagerError",
    "ModNotConfiguredError",
    "ModConflictError",
    "mod_state_label",
]