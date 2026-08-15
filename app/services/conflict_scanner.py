from __future__ import annotations

import json

from dataclasses import (
    dataclass,
)

from enum import Enum

from pathlib import Path

from collections.abc import (
    Iterable,
)

from app.games import (
    GameScope,
)

from app.models.mod import (
    ModInfo,
)

from app.platform_support import (
    normalized_path_key,
)

from app.services.mod_manager import (
    ModManager,
    ModState,
)


MANAGER_MARKERS = (
    ".gmm-managed.json",
    ".xxmimm-managed.json",
)

KNOWN_MANAGER_IDS = {
    "genshin-mod-manager",
    "xxmi-mod-manager",
}

DISABLED_PREFIX = (
    "DISABLED "
)


# ============================================================
# Types
# ============================================================

class ConflictKind(
    str,
    Enum,
):
    LIBRARY = (
        "library"
    )

    UNMANAGED_ACTIVE = (
        "unmanaged_active"
    )

    INVALID_MARKER = (
        "invalid_marker"
    )

    ORPHANED_MANAGED = (
        "orphaned_managed"
    )


@dataclass(
    frozen=True,
    slots=True,
)
class ConflictItem:
    kind: ConflictKind

    title: str

    path: Path

    message: str

    library_mod_path: (
        Path
        | None
    ) = None

    can_adopt: bool = False

    @property
    def key(
        self,
    ) -> str:
        return (
            normalized_path_key(
                self.path
            )
        )


@dataclass(
    frozen=True,
    slots=True,
)
class ConflictReport:
    items: tuple[
        ConflictItem,
        ...,
    ] = ()

    @property
    def count(
        self,
    ) -> int:
        return len(
            self.items
        )

    @property
    def library_count(
        self,
    ) -> int:
        return sum(
            item.kind
            == ConflictKind.LIBRARY
            for item
            in self.items
        )

    @property
    def unmanaged_count(
        self,
    ) -> int:
        return sum(
            item.kind
            == ConflictKind.UNMANAGED_ACTIVE
            for item
            in self.items
        )


# ============================================================
# Scanner
# ============================================================

class ConflictScanner:
    """
    Untersucht sowohl Library-Mods als auch
    den echten Active-Mods-Ordner.

    Dadurch werden auch Mods erkannt, die
    außerhalb des Managers manuell nach XXMI
    kopiert wurden.
    """

    def __init__(
        self,
        *,
        game_scope: GameScope,
        mod_manager: ModManager,
    ) -> None:
        self.game_scope = (
            game_scope
        )

        self.mod_manager = (
            mod_manager
        )

    # ========================================================
    # Public
    # ========================================================

    def scan(
        self,
        mods: Iterable[
            ModInfo
        ],
    ) -> ConflictReport:
        library_mods = tuple(
            mods
        )

        conflicts: list[
            ConflictItem
        ] = []

        known_paths: set[
            str
        ] = set()

        library_keys = {
            normalized_path_key(
                mod.path
            ): mod
            for mod
            in library_mods
        }

        # ----------------------------------------------------
        # 1. Konflikte bekannter Library-Mods
        # ----------------------------------------------------

        self._scan_library_conflicts(
            library_mods=library_mods,
            conflicts=conflicts,
            known_paths=known_paths,
        )

        # ----------------------------------------------------
        # 2. Active-Mods unabhängig von der Library scannen
        # ----------------------------------------------------

        active_root = (
            self.game_scope
            .active_mods_directory
        )

        if (
            active_root is None
            or not active_root.is_dir()
        ):
            return ConflictReport(
                items=tuple(
                    conflicts
                )
            )

        self._scan_active_directory(
            directory=active_root,
            active_root=active_root,
            library_keys=library_keys,
            conflicts=conflicts,
            known_paths=known_paths,
        )

        # ----------------------------------------------------
        # Stabil sortieren
        # ----------------------------------------------------

        conflicts.sort(
            key=lambda item: (
                item.kind.value,
                item.title.casefold(),
                str(
                    item.path
                ).casefold(),
            )
        )

        return ConflictReport(
            items=tuple(
                conflicts
            )
        )

    # ========================================================
    # Library
    # ========================================================

    def _scan_library_conflicts(
        self,
        *,
        library_mods: tuple[
            ModInfo,
            ...,
        ],
        conflicts: list[
            ConflictItem
        ],
        known_paths: set[
            str
        ],
    ) -> None:
        for mod in library_mods:
            state = (
                self.mod_manager
                .get_state(
                    mod.path
                )
            )

            if (
                state
                != ModState.CONFLICT
            ):
                continue

            conflict_path = (
                self._best_conflict_path(
                    mod
                )
            )

            key = (
                normalized_path_key(
                    conflict_path
                )
            )

            if key in known_paths:
                continue

            known_paths.add(
                key
            )

            conflicts.append(
                ConflictItem(
                    kind=(
                        ConflictKind
                        .LIBRARY
                    ),
                    title=mod.name,
                    path=(
                        conflict_path
                    ),
                    library_mod_path=(
                        mod.path
                    ),
                    can_adopt=True,
                    message=(
                        "Am erwarteten Active-Mod-Ziel "
                        "existieren Daten, die nicht "
                        "eindeutig diesem Library-Mod "
                        "zugeordnet werden können."
                    ),
                )
            )

    def _best_conflict_path(
        self,
        mod: ModInfo,
    ) -> Path:
        try:
            destination = (
                self.mod_manager
                .destination_for(
                    mod.path
                )
            )

            return destination

        except Exception:
            return mod.path

    # ========================================================
    # Active Tree
    # ========================================================

    def _scan_active_directory(
        self,
        *,
        directory: Path,
        active_root: Path,
        library_keys: dict[
            str,
            ModInfo,
        ],
        conflicts: list[
            ConflictItem
        ],
        known_paths: set[
            str
        ],
    ) -> None:
        try:
            entries = tuple(
                sorted(
                    directory.iterdir(),
                    key=lambda path: (
                        path.name
                        .casefold()
                    ),
                )
            )

        except OSError:
            return

        for entry in entries:
            # ------------------------------------------------
            # Einzelne Dateien auf Kategorieebene interessieren
            # uns hier nicht.
            # ------------------------------------------------

            if (
                not entry.is_dir()
                and not entry.is_symlink()
            ):
                continue

            # ------------------------------------------------
            # Symlink
            # ------------------------------------------------

            if entry.is_symlink():
                self._inspect_symlink(
                    path=entry,
                    active_root=active_root,
                    conflicts=conflicts,
                    known_paths=known_paths,
                )

                continue

            # ------------------------------------------------
            # Manager-Marker?
            # ------------------------------------------------

            marker = (
                self._find_marker(
                    entry
                )
            )

            if marker is not None:
                result = (
                    self._inspect_marker(
                        directory=entry,
                        marker=marker,
                        library_keys=(
                            library_keys
                        ),
                    )
                )

                if result is not None:
                    self._append_unique(
                        item=result,
                        conflicts=conflicts,
                        known_paths=known_paths,
                    )

                # Ein markierter Mod ist ein eigener Mod-Root.
                # Nicht weiter hineinlaufen.
                continue

            # ------------------------------------------------
            # Sieht dieser Ordner selbst wie ein Mod aus?
            #
            # Vor allem wichtig für manuell kopierte
            # Waffen-Skins.
            # ------------------------------------------------

            if self._looks_like_mod_root(
                entry
            ):
                item = (
                    ConflictItem(
                        kind=(
                            ConflictKind
                            .UNMANAGED_ACTIVE
                        ),
                        title=(
                            self._display_name(
                                entry
                            )
                        ),
                        path=entry,
                        message=(
                            "Dieser Mod befindet sich im "
                            "XXMI-Active-Mods-Ordner, besitzt "
                            "aber keine gültige Manager-"
                            "Markierung. Er wurde vermutlich "
                            "manuell hinzugefügt."
                        ),
                        can_adopt=False,
                    )
                )

                self._append_unique(
                    item=item,
                    conflicts=conflicts,
                    known_paths=known_paths,
                )

                # Nicht in Unterordner eines bereits
                # erkannten Mods hineinlaufen.
                continue

            # ------------------------------------------------
            # Kategorieordner:
            #
            # z. B.
            # Weapons/
            #   Sword/
            #     MySkin/
            #
            # Weapons selbst hat keine INI und wird daher
            # nicht als Mod behandelt.
            # ------------------------------------------------

            self._scan_active_directory(
                directory=entry,
                active_root=active_root,
                library_keys=library_keys,
                conflicts=conflicts,
                known_paths=known_paths,
            )

    # ========================================================
    # Mod Root Detection
    # ========================================================

    @staticmethod
    def _looks_like_mod_root(
        directory: Path,
    ) -> bool:
        """
        Wir nehmen nicht einfach jeden Ordner im
        Active-Mods-Verzeichnis als Mod.

        Ein XXMI/3DMigoto-Mod besitzt normalerweise
        mindestens eine INI-Datei auf seiner eigenen
        Ebene.

        Dadurch werden reine Kategorieordner wie
        Weapons/ oder Characters/ nicht als Konflikt
        gezählt.
        """

        try:
            for entry in directory.iterdir():
                if not entry.is_file():
                    continue

                if (
                    entry.suffix
                    .casefold()
                    == ".ini"
                ):
                    return True

        except OSError:
            return False

        return False

    # ========================================================
    # Marker
    # ========================================================

    @staticmethod
    def _find_marker(
        directory: Path,
    ) -> Path | None:
        for filename in (
            MANAGER_MARKERS
        ):
            marker = (
                directory
                / filename
            )

            if marker.is_file():
                return marker

        return None

    def _inspect_marker(
        self,
        *,
        directory: Path,
        marker: Path,
        library_keys: dict[
            str,
            ModInfo,
        ],
    ) -> ConflictItem | None:
        try:
            data = json.loads(
                marker.read_text(
                    encoding="utf-8"
                )
            )

        except (
            OSError,
            json.JSONDecodeError,
        ):
            return ConflictItem(
                kind=(
                    ConflictKind
                    .INVALID_MARKER
                ),
                title=(
                    self._display_name(
                        directory
                    )
                ),
                path=directory,
                message=(
                    "Der Manager-Marker dieses Mods "
                    "ist beschädigt oder nicht lesbar."
                ),
            )

        if not isinstance(
            data,
            dict,
        ):
            return ConflictItem(
                kind=(
                    ConflictKind
                    .INVALID_MARKER
                ),
                title=(
                    self._display_name(
                        directory
                    )
                ),
                path=directory,
                message=(
                    "Der Manager-Marker besitzt "
                    "ein ungültiges Format."
                ),
            )

        # ----------------------------------------------------
        # Manager
        # ----------------------------------------------------

        manager_id = (
            data.get(
                "manager"
            )
        )

        if (
            manager_id is not None
            and manager_id
            not in KNOWN_MANAGER_IDS
        ):
            return ConflictItem(
                kind=(
                    ConflictKind
                    .INVALID_MARKER
                ),
                title=(
                    self._display_name(
                        directory
                    )
                ),
                path=directory,
                message=(
                    "Der vorhandene Manager-Marker "
                    "gehört zu einer unbekannten "
                    "Anwendung."
                ),
            )

        # ----------------------------------------------------
        # Game
        # ----------------------------------------------------

        marker_game = (
            data.get(
                "game_id"
            )
        )

        if (
            isinstance(
                marker_game,
                str,
            )
            and marker_game
            != self.game_scope.game_id
        ):
            return ConflictItem(
                kind=(
                    ConflictKind
                    .INVALID_MARKER
                ),
                title=(
                    self._display_name(
                        directory
                    )
                ),
                path=directory,
                message=(
                    "Der Manager-Marker gehört "
                    "zu einem anderen Spiel."
                ),
            )

        # ----------------------------------------------------
        # Source-Key
        # ----------------------------------------------------

        source_key = (
            data.get(
                "source_key"
            )
        )

        if isinstance(
            source_key,
            str,
        ):
            if (
                source_key
                in library_keys
            ):
                return None

        # ----------------------------------------------------
        # Alter Source-Pfad
        # ----------------------------------------------------

        for field_name in (
            "source",
            "source_path",
        ):
            source_value = (
                data.get(
                    field_name
                )
            )

            if not isinstance(
                source_value,
                str,
            ):
                continue

            source_path = (
                Path(
                    source_value
                )
                .expanduser()
                .absolute()
            )

            source_path_key = (
                normalized_path_key(
                    source_path
                )
            )

            if (
                source_path_key
                in library_keys
            ):
                return None

            if source_path.exists():
                # Quelle existiert zwar, gehört aber nicht zur
                # aktuellen Game-Library.
                return ConflictItem(
                    kind=(
                        ConflictKind
                        .INVALID_MARKER
                    ),
                    title=(
                        self._display_name(
                            directory
                        )
                    ),
                    path=directory,
                    message=(
                        "Der aktive Mod verweist auf "
                        "eine Quelle außerhalb der "
                        "aktuellen Library."
                    ),
                )

        # ----------------------------------------------------
        # Marker gehört grundsätzlich uns,
        # aber Quelle existiert nicht mehr.
        # ----------------------------------------------------

        return ConflictItem(
            kind=(
                ConflictKind
                .ORPHANED_MANAGED
            ),
            title=(
                self._display_name(
                    directory
                )
            ),
            path=directory,
            message=(
                "Dieser aktive Mod wurde früher vom "
                "Manager verwaltet, aber der zugehörige "
                "Library-Mod wurde nicht gefunden."
            ),
        )

    # ========================================================
    # Symlink
    # ========================================================

    def _inspect_symlink(
        self,
        *,
        path: Path,
        active_root: Path,
        conflicts: list[
            ConflictItem
        ],
        known_paths: set[
            str
        ],
    ) -> None:
        try:
            target = (
                path.resolve(
                    strict=False
                )
            )

        except OSError:
            target = None

        library_root = (
            self.game_scope
            .mod_library_directory
            .expanduser()
            .absolute()
        )

        # Alte Manager-Symlinks zur eigenen Library
        # nicht pauschal als manuell eingefügten Mod melden.
        if target is not None:
            try:
                target.relative_to(
                    library_root
                )

                return

            except ValueError:
                pass

        item = ConflictItem(
            kind=(
                ConflictKind
                .UNMANAGED_ACTIVE
            ),
            title=(
                self._display_name(
                    path
                )
            ),
            path=path,
            message=(
                "Im Active-Mods-Ordner befindet "
                "sich eine nicht vom Manager "
                "verwaltete symbolische Verknüpfung."
            ),
        )

        self._append_unique(
            item=item,
            conflicts=conflicts,
            known_paths=known_paths,
        )

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _display_name(
        path: Path,
    ) -> str:
        name = (
            path.name
        )

        if name.startswith(
            DISABLED_PREFIX
        ):
            name = (
                name[
                    len(
                        DISABLED_PREFIX
                    ):
                ]
            )

        return (
            name
            or str(
                path
            )
        )

    @staticmethod
    def _append_unique(
        *,
        item: ConflictItem,
        conflicts: list[
            ConflictItem
        ],
        known_paths: set[
            str
        ],
    ) -> None:
        key = item.key

        if key in known_paths:
            return

        known_paths.add(
            key
        )

        conflicts.append(
            item
        )


__all__ = [
    "ConflictItem",
    "ConflictKind",
    "ConflictReport",
    "ConflictScanner",
]