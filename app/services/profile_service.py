from __future__ import annotations

import json
import re
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from app.config import PROFILE_DIR
from app.models.mod import ModInfo
from app.models.profile import (
    PROFILE_SCHEMA_VERSION,
    ModProfile,
    ProfileModEntry,
)
from app.services.mod_manager import ModState


StateProvider = Callable[[Path], ModState]


class ProfileError(Exception):
    """Basisfehler der Profilverwaltung."""


class ProfileAlreadyExistsError(ProfileError):
    pass


class ProfileNotFoundError(ProfileError):
    pass


class ProfileDataError(ProfileError):
    pass


class ProfileService:
    """Speichert und lädt Mod-Profile als atomare JSON-Dateien."""

    def __init__(
        self,
        *,
        root: Path | None = None,
    ) -> None:
        self.root = Path(
            root or PROFILE_DIR
        ).expanduser().absolute()

        self.root.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ========================================================
    # Public API
    # ========================================================

    def list_profiles(
        self,
        game_id: str,
    ) -> tuple[ModProfile, ...]:
        profiles: list[ModProfile] = []

        for path in sorted(
            self.root.glob("*.json")
        ):
            try:
                profile = self._load_path(
                    path
                )
            except ProfileError:
                # Eine beschädigte Profildatei soll nicht die
                # komplette Profile-Seite unbrauchbar machen.
                continue

            if profile.game_id == game_id:
                profiles.append(
                    profile
                )

        profiles.sort(
            key=lambda profile: (
                profile.name.casefold(),
                profile.updated_at,
            )
        )

        return tuple(
            profiles
        )

    def load_profile(
        self,
        *,
        game_id: str,
        name: str,
    ) -> ModProfile:
        path = self._profile_path(
            game_id=game_id,
            name=name,
        )

        if not path.is_file():
            raise ProfileNotFoundError(
                f"Profil nicht gefunden: {name}"
            )

        return self._load_path(
            path
        )

    def capture_profile(
        self,
        *,
        name: str,
        game_id: str,
        mods: Iterable[ModInfo],
        state_provider: StateProvider,
        overwrite: bool = False,
    ) -> ModProfile:
        normalized_name = self._validate_name(
            name
        )

        path = self._profile_path(
            game_id=game_id,
            name=normalized_name,
        )

        existing: ModProfile | None = None

        if path.is_file():
            if not overwrite:
                raise ProfileAlreadyExistsError(
                    normalized_name
                )

            existing = self._load_path(
                path
            )

        entries: list[ProfileModEntry] = []

        for mod in mods:
            state = state_provider(
                Path(mod.path)
            )

            # Unmanaged Konflikte und nicht konfigurierte Mods
            # werden nicht in ein Profil übernommen. Profile
            # sollen niemals fremde Ordner adoptieren.
            if state in {
                ModState.CONFLICT,
                ModState.NOT_CONFIGURED,
            }:
                continue

            relative_path = self._relative_mod_path(
                mod
            )

            entries.append(
                ProfileModEntry(
                    relative_path=relative_path,
                    name=str(
                        getattr(
                            mod,
                            "name",
                            Path(mod.path).name,
                        )
                    ),
                    enabled=(
                        state == ModState.ENABLED
                    ),
                )
            )

        entries.sort(
            key=lambda entry: (
                entry.relative_path.casefold(),
                entry.name.casefold(),
            )
        )

        now = self._now_iso()

        profile = ModProfile(
            name=normalized_name,
            game_id=str(game_id),
            created_at=(
                existing.created_at
                if existing is not None
                else now
            ),
            updated_at=now,
            mods=tuple(entries),
        )

        self.save_profile(
            profile,
            overwrite=True,
        )

        return profile

    def save_profile(
        self,
        profile: ModProfile,
        *,
        overwrite: bool = True,
    ) -> Path:
        name = self._validate_name(
            profile.name
        )

        path = self._profile_path(
            game_id=profile.game_id,
            name=name,
        )

        if (
            path.exists()
            and not overwrite
        ):
            raise ProfileAlreadyExistsError(
                name
            )

        payload = {
            "schema_version": profile.schema_version,
            "name": profile.name,
            "game_id": profile.game_id,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "mods": [
                asdict(entry)
                for entry in profile.mods
            ],
        }

        temporary = path.with_suffix(
            ".json.tmp"
        )

        try:
            temporary.write_text(
                json.dumps(
                    payload,
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            temporary.replace(
                path
            )

        except OSError as error:
            try:
                temporary.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

            raise ProfileError(
                str(error)
            ) from error

        return path

    def rename_profile(
        self,
        *,
        game_id: str,
        old_name: str,
        new_name: str,
    ) -> ModProfile:
        profile = self.load_profile(
            game_id=game_id,
            name=old_name,
        )

        normalized_new_name = self._validate_name(
            new_name
        )

        old_path = self._profile_path(
            game_id=game_id,
            name=old_name,
        )

        new_path = self._profile_path(
            game_id=game_id,
            name=normalized_new_name,
        )

        if (
            new_path != old_path
            and new_path.exists()
        ):
            raise ProfileAlreadyExistsError(
                normalized_new_name
            )

        renamed = ModProfile(
            name=normalized_new_name,
            game_id=profile.game_id,
            created_at=profile.created_at,
            updated_at=self._now_iso(),
            mods=profile.mods,
            schema_version=profile.schema_version,
        )

        self.save_profile(
            renamed,
            overwrite=True,
        )

        if old_path != new_path:
            try:
                old_path.unlink(
                    missing_ok=True
                )
            except OSError as error:
                raise ProfileError(
                    str(error)
                ) from error

        return renamed

    def delete_profile(
        self,
        *,
        game_id: str,
        name: str,
    ) -> None:
        path = self._profile_path(
            game_id=game_id,
            name=name,
        )

        if not path.exists():
            raise ProfileNotFoundError(
                name
            )

        try:
            path.unlink()
        except OSError as error:
            raise ProfileError(
                str(error)
            ) from error

    # ========================================================
    # Parsing
    # ========================================================

    def _load_path(
        self,
        path: Path,
    ) -> ModProfile:
        try:
            data = json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise ProfileDataError(
                f"{path}: {error}"
            ) from error

        if not isinstance(
            data,
            dict,
        ):
            raise ProfileDataError(
                f"Ungültige Profildatei: {path}"
            )

        schema_version = data.get(
            "schema_version",
            1,
        )

        if schema_version != PROFILE_SCHEMA_VERSION:
            raise ProfileDataError(
                (
                    "Nicht unterstützte Profilversion "
                    f"{schema_version}: {path}"
                )
            )

        name = data.get("name")
        game_id = data.get("game_id")
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        raw_mods = data.get("mods")

        if not all(
            isinstance(value, str)
            and value.strip()
            for value in (
                name,
                game_id,
                created_at,
                updated_at,
            )
        ):
            raise ProfileDataError(
                f"Ungültige Profil-Metadaten: {path}"
            )

        if not isinstance(
            raw_mods,
            list,
        ):
            raise ProfileDataError(
                f"Ungültige Mod-Liste: {path}"
            )

        entries: list[ProfileModEntry] = []

        for raw_entry in raw_mods:
            if not isinstance(
                raw_entry,
                dict,
            ):
                raise ProfileDataError(
                    f"Ungültiger Mod-Eintrag: {path}"
                )

            relative_path = raw_entry.get(
                "relative_path"
            )
            entry_name = raw_entry.get(
                "name"
            )
            enabled = raw_entry.get(
                "enabled"
            )

            if not (
                isinstance(relative_path, str)
                and relative_path.strip()
                and isinstance(entry_name, str)
                and isinstance(enabled, bool)
            ):
                raise ProfileDataError(
                    f"Ungültiger Mod-Eintrag: {path}"
                )

            entries.append(
                ProfileModEntry(
                    relative_path=self._normalize_relative_path(
                        relative_path
                    ),
                    name=entry_name,
                    enabled=enabled,
                )
            )

        return ModProfile(
            name=name.strip(),
            game_id=game_id.strip(),
            created_at=created_at,
            updated_at=updated_at,
            mods=tuple(entries),
            schema_version=schema_version,
        )

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _now_iso() -> str:
        return (
            datetime.now(
                timezone.utc
            )
            .replace(microsecond=0)
            .isoformat()
        )

    @staticmethod
    def _validate_name(
        name: str,
    ) -> str:
        normalized = " ".join(
            str(name).split()
        ).strip()

        if not normalized:
            raise ProfileError(
                "Profilname darf nicht leer sein."
            )

        if len(normalized) > 80:
            raise ProfileError(
                "Profilname ist zu lang."
            )

        return normalized

    @staticmethod
    def _slug(
        value: str,
    ) -> str:
        slug = re.sub(
            r"[^A-Za-z0-9._-]+",
            "-",
            value.strip(),
        ).strip("-._")

        return slug or "profile"

    def _profile_path(
        self,
        *,
        game_id: str,
        name: str,
    ) -> Path:
        return self.root / (
            f"{self._slug(game_id)}__"
            f"{self._slug(name)}.json"
        )

    @classmethod
    def _relative_mod_path(
        cls,
        mod: ModInfo,
    ) -> str:
        relative_path = getattr(
            mod,
            "relative_path",
            None,
        )

        if relative_path:
            return cls._normalize_relative_path(
                str(relative_path)
            )

        return cls._normalize_relative_path(
            Path(mod.path).name
        )

    @staticmethod
    def _normalize_relative_path(
        value: str,
    ) -> str:
        normalized = str(value).replace(
            "\\",
            "/",
        ).strip("/")

        parts = [
            part
            for part in normalized.split("/")
            if part not in {
                "",
                ".",
            }
        ]

        if any(
            part == ".."
            for part in parts
        ):
            raise ProfileDataError(
                "Profil enthält einen unsicheren relativen Pfad."
            )

        result = "/".join(
            parts
        )

        if not result:
            raise ProfileDataError(
                "Profil enthält einen leeren Mod-Pfad."
            )

        return result


__all__ = [
    "ProfileAlreadyExistsError",
    "ProfileDataError",
    "ProfileError",
    "ProfileNotFoundError",
    "ProfileService",
]
