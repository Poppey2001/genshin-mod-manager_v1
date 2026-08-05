from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.config import AppConfig, BACKUP_DIR, FIXED_MODS_DIR
import hashlib
import logging
MANAGER_MARKER = ".gmm-managed.json"

DISABLED_PREFIX = "DISABLED "

class ModState(str, Enum):
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

logger = logging.getLogger(__name__)

class ModManagerError(Exception):
    """Grundfehler der Mod-Verwaltung."""


class ModNotConfiguredError(ModManagerError):
    """Der aktive Mods-Ordner wurde nicht eingestellt."""


class ModConflictError(ModManagerError):
    """Am Ziel existiert bereits eine fremde Datei oder ein fremder Ordner."""


class ModManager:
    """Aktiviert und deaktiviert Mods aus der zentralen Bibliothek."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def _destination_paths(
        self,
        active_root: Path,
        source: Path,
    ) -> tuple[Path, Path]:
        """Erzeugt den aktiven und deaktivierten Zielpfad."""
        enabled_path = active_root / source.name
        disabled_path = active_root / (
            f"{DISABLED_PREFIX}{source.name}"
        )

        return enabled_path, disabled_path

    def get_state(
        self,
        mod_path: Path | str,
    ) -> ModState:
        """Ermittelt den Zustand anhand der beiden Ordnernamen."""
        try:
            source, _relative_path = self._source_and_relative(
                mod_path,
                require_exists=False,
            )

            active_root = self._get_active_root(
                create=False,
            )

        except ModNotConfiguredError:
            return ModState.NOT_CONFIGURED

        except ModManagerError:
            return ModState.CONFLICT

        enabled_path, disabled_path = self._destination_paths(
            active_root=active_root,
            source=source,
        )

        enabled_exists = enabled_path.exists()
        disabled_exists = disabled_path.exists()

        if enabled_exists and disabled_exists:
            return ModState.CONFLICT

        if enabled_exists:
            if self._marker_matches(
                destination=enabled_path,
                source=source,
            ):
                return ModState.ENABLED

            return ModState.CONFLICT

        if disabled_exists:
            if self._marker_matches(
                destination=disabled_path,
                source=source,
            ):
                return ModState.DISABLED

            return ModState.CONFLICT

        return ModState.DISABLED

    @staticmethod
    def _copy_ignore(
        _directory: str,
        names: list[str],
    ) -> set[str]:
        """Schließt interne Manager-Dateien vom Mod-Inhalt aus."""
        ignored_names = {
            MANAGER_MARKER,
            f"{MANAGER_MARKER}.tmp",
        }

        return {
            name
            for name in names
            if name in ignored_names
        }

    def adopt_existing(
        self,
        mod_path: Path | str,
    ) -> ModState:
        """
        Übernimmt einen vorhandenen, bisher nicht verwalteten Mod-Ordner.

        Es werden keine Mod-Dateien überschrieben oder gelöscht.
        Der Manager legt lediglich seine Markierungsdatei an.
        """
        source, relative_path = self._source_and_relative(
            mod_path,
            require_exists=True,
        )

        active_root = self._get_active_root(
            create=True,
        )

        enabled_path, disabled_path = self._destination_paths(
            active_root=active_root,
            source=source,
        )

        enabled_exists = enabled_path.exists()
        disabled_exists = disabled_path.exists()

        if enabled_exists and disabled_exists:
            raise ModConflictError(
                "Der Konflikt kann nicht automatisch übernommen werden, "
                "weil eine aktive und eine deaktivierte Version existieren.\n\n"
                f"Aktiv:\n{enabled_path}\n\n"
                f"Deaktiviert:\n{disabled_path}"
            )

        if not enabled_exists and not disabled_exists:
            raise ModConflictError(
                "Es wurde kein vorhandener Zielordner gefunden, "
                "der übernommen werden könnte."
            )

        if enabled_exists:
            destination = enabled_path
            resulting_state = ModState.ENABLED
        else:
            destination = disabled_path
            resulting_state = ModState.DISABLED

        if destination.is_symlink():
            raise ModConflictError(
                "Symbolische Verknüpfungen können nicht als bestehende "
                "Mod-Kopie übernommen werden.\n\n"
                f"Pfad: {destination}"
            )

        if not destination.is_dir():
            raise ModConflictError(
                "Das vorhandene Ziel ist kein Ordner.\n\n"
                f"Pfad: {destination}"
            )

        marker_file = destination / MANAGER_MARKER

        if marker_file.exists():
            if self._marker_matches(
                destination=destination,
                source=source,
            ):
                return resulting_state

            raise ModConflictError(
                "Der Ordner besitzt bereits eine Manager-Markierung, "
                "die zu einem anderen Mod gehört.\n\n"
                f"Pfad: {destination}"
            )

        try:
            self._write_marker(
                destination=destination,
                source=source,
                relative_path=relative_path,
            )

        except OSError as error:
            raise ModManagerError(
                "Der vorhandene Mod-Ordner konnte nicht übernommen werden.\n\n"
                f"Pfad: {destination}\n\n"
                f"{error}"
            ) from error

        return resulting_state

    def enable(
        self,
        mod_path: Path | str,
    ) -> Path:
        """
        Aktiviert einen Mod.

        Eine vorhandene deaktivierte Kopie wird nur umbenannt.
        Andernfalls wird der Mod einmalig aus der Bibliothek kopiert.
        """
        source, relative_path = self._source_and_relative(
            mod_path,
            require_exists=True,
        )

        active_root = self._get_active_root(
            create=True,
        )

        enabled_path, disabled_path = self._destination_paths(
            active_root=active_root,
            source=source,
        )

        if enabled_path.exists() and disabled_path.exists():
            raise ModConflictError(
                "Die aktive und die deaktivierte Version existieren "
                "gleichzeitig.\n\n"
                f"Aktiv: {enabled_path}\n"
                f"Deaktiviert: {disabled_path}"
            )

        if enabled_path.exists():
            if self._marker_matches(
                destination=enabled_path,
                source=source,
            ):
                return enabled_path

            raise ModConflictError(
                "Am aktiven Ziel befindet sich ein nicht vom "
                "Manager verwalteter Ordner.\n\n"
                f"Ziel: {enabled_path}"
            )

        # Bereits vorhandene, reparierte Mod-Kopie reaktivieren.
        if disabled_path.exists():
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
                disabled_path.rename(
                    enabled_path
                )
            except OSError as error:
                raise ModManagerError(
                    "Der deaktivierte Mod konnte nicht aktiviert werden.\n\n"
                    f"{error}"
                ) from error

            return enabled_path

        # Erste Aktivierung: vollständige Kopie erstellen.
        try:
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
            self._rollback_destination(
                enabled_path
            )

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

        Die Dateien und alle Änderungen des Fixing-Tools bleiben erhalten.
        """
        source, _relative_path = self._source_and_relative(
            mod_path,
            require_exists=False,
        )

        active_root = self._get_active_root(
            create=False,
        )

        enabled_path, disabled_path = self._destination_paths(
            active_root=active_root,
            source=source,
        )

        if enabled_path.exists() and disabled_path.exists():
            raise ModConflictError(
                "Die aktive und die deaktivierte Version existieren "
                "gleichzeitig.\n\n"
                f"Aktiv: {enabled_path}\n"
                f"Deaktiviert: {disabled_path}"
            )

        if disabled_path.exists():
            if self._marker_matches(
                destination=disabled_path,
                source=source,
            ):
                return False

            raise ModConflictError(
                "Der deaktivierte Zielordner wird nicht vom "
                "Manager verwaltet.\n\n"
                f"Ordner: {disabled_path}"
            )

        if not enabled_path.exists():
            return False

        if not self._marker_matches(
            destination=enabled_path,
            source=source,
        ):
            raise ModConflictError(
                "Der aktive Ordner besitzt keine gültige "
                "Manager-Markierung und wird nicht verändert.\n\n"
                f"Ordner: {enabled_path}"
            )

        try:
            enabled_path.rename(
                disabled_path
            )
        except OSError as error:
            raise ModManagerError(
                "Der Mod konnte nicht deaktiviert werden.\n\n"
                "{error}"
            ) from error

        return True

    def destination_for(
        self,
        mod_path: Path | str,
    ) -> Path:
        """Gibt den aktiven Zielpfad zurück."""
        source, _relative_path = self._source_and_relative(
            mod_path,
            require_exists=False,
        )

        active_root = self._get_active_root(
            create=False,
        )

        enabled_path, _disabled_path = self._destination_paths(
            active_root=active_root,
            source=source,
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
        source, _relative_path = self._source_and_relative(
            mod_path,
            require_exists=False,
        )

        try:
            active_root = self._get_active_root(
                create=False,
            )
        except ModManagerError:
            return source

        enabled_path, disabled_path = (
            self._destination_paths(
                active_root=active_root,
                source=source,
            )
        )

        if enabled_path.is_dir():
            return enabled_path

        if disabled_path.is_dir():
            return disabled_path

        return source
    
    def _get_destination(
        self,
        active_root: Path,
        source: Path,
    ) -> Path:
        """
        Verwendet im aktiven Mods-Ordner nur den letzten
        Ordnernamen des Mods.
        """
        return active_root / source.name
    
    def _state_for(
        self,
        source: Path,
        destination: Path,
    ) -> ModState:
        if destination.is_symlink():
            if not self._symlink_points_to(
                destination=destination,
                source=source,
            ):
                return ModState.CONFLICT

            if not source.exists():
                return ModState.BROKEN

            return ModState.ENABLED

        if not destination.exists():
            return ModState.DISABLED

        if (
            destination.is_dir()
            and self._marker_matches(
                destination=destination,
                source=source,
            )
        ):
            return ModState.ENABLED

        return ModState.CONFLICT

    def _source_and_relative(
        self,
        mod_path: Path | str,
        require_exists: bool,
    ) -> tuple[Path, Path]:
        library_root = self._absolute_path(
            self.config.mod_library_directory
        )

        source = self._absolute_path(
            Path(mod_path)
        )

        try:
            relative_path = source.relative_to(
                library_root
            )
        except ValueError as error:
            raise ModManagerError(
                "Der ausgewählte Mod liegt nicht innerhalb "
                "der konfigurierten Mod-Bibliothek."
            ) from error

        if relative_path == Path("."):
            raise ModManagerError(
                "Die komplette Mod-Bibliothek kann nicht als Mod "
                "aktiviert werden."
            )

        if require_exists:
            if not source.exists():
                raise ModManagerError(
                    "Der Mod-Ordner existiert nicht oder das "
                    "Netzlaufwerk ist nicht eingehängt.\n\n"
                    f"Quelle: {source}"
                )

            if not source.is_dir():
                raise ModManagerError(
                    f"Der Mod-Pfad ist kein Verzeichnis: {source}"
                )

        return source, relative_path

    def _get_active_root(
        self,
        create: bool,
    ) -> Path:
        configured_path = (
            self.config.active_mods_directory
        )

        if configured_path is None:
            raise ModNotConfiguredError(
                "Wähle unter Einstellungen zuerst den "
                "aktiven Mods-Ordner aus."
            )

        active_root = self._absolute_path(
            configured_path
        )

        library_root = self._absolute_path(
            self.config.mod_library_directory
        )

        if self._paths_overlap(
            library_root,
            active_root,
        ):
            raise ModManagerError(
                "Mod-Bibliothek und aktiver Mods-Ordner dürfen "
                "nicht identisch oder ineinander verschachtelt sein."
            )

        if create:
            try:
                active_root.mkdir(
                    parents=True,
                    exist_ok=True,
                )
            except OSError as error:
                raise ModManagerError(
                    "Der aktive Mods-Ordner konnte nicht erstellt werden.\n\n"
                    f"{error}"
                ) from error

        return active_root

    def _write_marker(
        self,
        destination: Path,
        source: Path,
        relative_path: Path,
    ) -> None:
        marker_file = destination / MANAGER_MARKER
        temporary_file = destination / f"{MANAGER_MARKER}.tmp"

        marker_data = {
            "manager": "genshin-mod-manager",
            "source": str(source),
            "relative_path": str(relative_path),
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
        marker_file = destination / MANAGER_MARKER

        if not marker_file.is_file():
            return False

        try:
            data = json.loads(
                marker_file.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return False

        marker_source = data.get("source")

        if not isinstance(marker_source, str):
            return False

        return self._absolute_path(
            Path(marker_source)
        ) == self._absolute_path(source)

    def _symlink_points_to(
        self,
        destination: Path,
        source: Path,
    ) -> bool:
        try:
            link_target = destination.readlink()

            if not link_target.is_absolute():
                link_target = (
                    destination.parent
                    / link_target
                )

            return link_target.resolve(
                strict=False
            ) == source.resolve(
                strict=False
            )

        except OSError:
            return False

    def _backup_managed_copy(
        self,
        destination: Path,
        relative_path: Path,
    ) -> Path:
        timestamp = datetime.now().strftime(
            "%Y%m%d-%H%M%S-%f"
        )

        backup_destination = (
            BACKUP_DIR
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

    def _cleanup_empty_directories(
        self,
        start: Path,
        active_root: Path,
    ) -> None:
        current = start

        while (
            current != active_root
            and self._path_is_inside(
                current,
                active_root,
            )
        ):
            try:
                current.rmdir()
            except OSError:
                break

            current = current.parent

    @staticmethod
    def _rollback_destination(
        destination: Path,
    ) -> None:
        try:
            if destination.is_symlink():
                destination.unlink()
            elif destination.exists():
                shutil.rmtree(destination)
        except OSError:
            pass

    @staticmethod
    def _absolute_path(
        path: Path,
    ) -> Path:
        return Path(path).expanduser().absolute()

    @classmethod
    def _paths_overlap(
        cls,
        first: Path,
        second: Path,
    ) -> bool:
        return (
            first == second
            or cls._path_is_inside(first, second)
            or cls._path_is_inside(second, first)
        )

    @staticmethod
    def _path_is_inside(
        path: Path,
        parent: Path,
    ) -> bool:
        try:
            path.relative_to(parent)
            return True
        except ValueError:
            return False


def mod_state_label(
    state: ModState,
) -> str:
    return STATE_LABELS[state]