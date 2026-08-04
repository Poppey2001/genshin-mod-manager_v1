from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from app.config import AppConfig, BACKUP_DIR


MANAGER_MARKER = ".gmm-managed.json"


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

    def get_state(
        self,
        mod_path: Path | str,
    ) -> ModState:
        """Ermittelt den Aktivierungszustand eines Mods."""
        try:
            source, relative_path = self._source_and_relative(
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

        destination = self._get_destination(
            active_root=active_root,
            source=source,
        )

        return self._state_for(
            source=source,
            destination=destination,
        )

    def enable(
        self,
        mod_path: Path | str,
    ) -> Path:
        """Aktiviert einen Mod per Symlink oder Kopie."""
        source, relative_path = self._source_and_relative(
            mod_path,
            require_exists=True,
        )

        active_root = self._get_active_root(
            create=True,
        )

        destination = self._get_destination(
            active_root=active_root,
            source=source,
        )

        state = self._state_for(
            source=source,
            destination=destination,
        )

        if state == ModState.ENABLED:
            return destination

        if state != ModState.DISABLED:
            raise ModConflictError(
                "Der Mod kann nicht aktiviert werden, weil am Ziel "
                "bereits eine andere Datei, ein anderer Ordner oder "
                "eine fremde Verknüpfung existiert.\n\n"
                f"Ziel: {destination}"
            )

        try:
            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            shutil.copytree(
                source,
                destination,
                symlinks=False,
            )
            
            self._write_marker(
                destination=destination,
                source=source,
                relative_path=relative_path,
            )
            
        except OSError as error:
            self._rollback_destination(
                destination
            )

            mode_name = (
                "symbolische Verknüpfung"
                if self.config.use_symlinks
                else "Kopie"
            )

            raise ModManagerError(
                f"Der Mod konnte nicht als {mode_name} aktiviert werden.\n\n"
                f"{error}"
            ) from error

        return destination

    def disable(
        self,
        mod_path: Path | str,
    ) -> bool:
        """Deaktiviert einen vom Manager aktivierten Mod."""
        source, relative_path = self._source_and_relative(
            mod_path,
            require_exists=False,
        )

        active_root = self._get_active_root(
            create=False,
        )

        destination = self._get_destination(
            active_root=active_root,
            source=source,
        )

        state = self._state_for(
            source=source,
            destination=destination,
        )

        if state == ModState.DISABLED:
            return False

        if state == ModState.NOT_CONFIGURED:
            raise ModNotConfiguredError(
                "Es wurde noch kein aktiver Mods-Ordner eingestellt."
            )

        if state == ModState.CONFLICT:
            raise ModConflictError(
                "Der Zielordner gehört offenbar nicht zu diesem Mod. "
                "Er wird aus Sicherheitsgründen nicht gelöscht.\n\n"
                f"Ziel: {destination}"
            )

        try:
            if destination.is_symlink():
                destination.unlink()

            elif destination.is_dir():
                if not self._marker_matches(
                    destination=destination,
                    source=source,
                ):
                    raise ModConflictError(
                        "Der Zielordner besitzt keine gültige "
                        "Genshin-Mod-Manager-Markierung."
                    )

                if self.config.create_backups:
                    self._backup_managed_copy(
                        destination=destination,
                        relative_path=Path(source.name),
                    )

                shutil.rmtree(destination)

            else:
                raise ModConflictError(
                    "Das Mod-Ziel ist weder eine verwaltete Kopie "
                    "noch eine symbolische Verknüpfung."
                )

        except ModManagerError:
            raise

        except OSError as error:
            raise ModManagerError(
                "Der Mod konnte nicht deaktiviert werden.\n\n"
                f"{error}"
            ) from error

        self._cleanup_empty_directories(
            start=destination.parent,
            active_root=active_root,
        )

        return True

    def destination_for(
        self,
        mod_path: Path | str,
    ) -> Path:
        """Gibt den flachen Zielpfad eines Mods zurück."""
        source, _relative_path = self._source_and_relative(
            mod_path,
            require_exists=False,
        )

        active_root = self._get_active_root(
            create=False,
        )

        return self._get_destination(
            active_root=active_root,
            source=source,
        )
    
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