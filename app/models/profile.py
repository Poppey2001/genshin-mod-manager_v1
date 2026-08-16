from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


PROFILE_SCHEMA_VERSION = 1


@dataclass(
    frozen=True,
    slots=True,
)
class ProfileModEntry:
    """Gewünschter Zustand eines einzelnen Library-Mods."""

    relative_path: str
    name: str
    enabled: bool


@dataclass(
    frozen=True,
    slots=True,
)
class ModProfile:
    """Persistentes Mod-Profil für genau ein XXMI-Spiel."""

    name: str
    game_id: str
    created_at: str
    updated_at: str
    mods: tuple[ProfileModEntry, ...]
    schema_version: int = PROFILE_SCHEMA_VERSION

    @property
    def total_count(self) -> int:
        return len(self.mods)

    @property
    def enabled_count(self) -> int:
        return sum(
            entry.enabled
            for entry in self.mods
        )

    @property
    def disabled_count(self) -> int:
        return (
            self.total_count
            - self.enabled_count
        )


class ProfileApplyStatus(
    str,
    Enum,
):
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    MISSING = "missing"
    BLOCKED = "blocked"
    FAILED = "failed"


@dataclass(
    frozen=True,
    slots=True,
)
class ProfileApplyItem:
    relative_path: str
    name: str
    desired_enabled: bool
    status: ProfileApplyStatus
    message: str = ""


@dataclass(
    frozen=True,
    slots=True,
)
class ProfileApplyResult:
    profile_name: str
    game_id: str
    items: tuple[ProfileApplyItem, ...]
    duration_seconds: float
    cancelled: bool = False

    @property
    def changed_count(self) -> int:
        return sum(
            item.status == ProfileApplyStatus.CHANGED
            for item in self.items
        )

    @property
    def unchanged_count(self) -> int:
        return sum(
            item.status == ProfileApplyStatus.UNCHANGED
            for item in self.items
        )

    @property
    def missing_count(self) -> int:
        return sum(
            item.status == ProfileApplyStatus.MISSING
            for item in self.items
        )

    @property
    def blocked_count(self) -> int:
        return sum(
            item.status == ProfileApplyStatus.BLOCKED
            for item in self.items
        )

    @property
    def failed_count(self) -> int:
        return sum(
            item.status == ProfileApplyStatus.FAILED
            for item in self.items
        )

    @property
    def has_warnings(self) -> bool:
        return any(
            (
                self.missing_count,
                self.blocked_count,
                self.failed_count,
            )
        )


__all__ = [
    "PROFILE_SCHEMA_VERSION",
    "ModProfile",
    "ProfileApplyItem",
    "ProfileApplyResult",
    "ProfileApplyStatus",
    "ProfileModEntry",
]
