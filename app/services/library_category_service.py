from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable
from uuid import uuid4


DOCUMENT_VERSION = 1
UNCATEGORIZED_FILTER_ID = "__uncategorized__"
MAX_CATEGORY_NAME_LENGTH = 80


class LibraryCategoryError(RuntimeError):
    """Raised when category data cannot be changed safely."""


@dataclass(frozen=True, slots=True)
class LibraryCategory:
    id: str
    name: str


def default_library_categories_path() -> Path:
    """Return the per-user JSON path without depending on the install folder."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA")
        root = (
            Path(base)
            if base
            else Path.home() / "AppData" / "Local"
        )
        return root / "Genshin Mod Manager" / "library_categories.json"

    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Genshin Mod Manager"
            / "library_categories.json"
        )

    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    root = (
        Path(xdg_data_home).expanduser()
        if xdg_data_home
        else Path.home() / ".local" / "share"
    )
    return root / "genshin-mod-manager" / "library_categories.json"


class LibraryCategoryService:
    """
    Stores user-defined Library categories in one JSON document.

    Categories are scoped per game. Mod assignments use a normalized relative
    Library path, so changing the absolute Library directory does not break
    the assignment.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = (
            Path(path).expanduser()
            if path is not None
            else default_library_categories_path()
        )
        self._lock = threading.RLock()
        self.last_recovery_backup: Path | None = None
        self._cached_document: dict[str, Any] | None = None
        self._cached_mtime_ns: int | None = None

    @staticmethod
    def normalize_game_id(game_id: str) -> str:
        value = str(game_id).strip()
        if not value:
            raise LibraryCategoryError("game_id must not be empty")
        return value

    @staticmethod
    def normalize_mod_key(mod_key: str | Path) -> str:
        text = str(mod_key).strip().replace("\\", "/")
        if not text:
            raise LibraryCategoryError("mod key must not be empty")

        parts = [
            part
            for part in PurePosixPath(text).parts
            if part not in {"", ".", "/"}
        ]
        if not parts or any(part == ".." for part in parts):
            raise LibraryCategoryError("mod key is not a safe relative path")
        return "/".join(parts)

    @staticmethod
    def _normalize_name(name: str) -> str:
        value = " ".join(str(name).strip().split())
        if not value:
            raise LibraryCategoryError("category name must not be empty")
        if len(value) > MAX_CATEGORY_NAME_LENGTH:
            raise LibraryCategoryError(
                f"category name may contain at most {MAX_CATEGORY_NAME_LENGTH} characters"
            )
        return value

    @staticmethod
    def _new_document() -> dict[str, Any]:
        return {
            "version": DOCUMENT_VERSION,
            "games": {},
        }

    def _backup_broken_file(self) -> None:
        if not self.path.is_file():
            return
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        backup = self.path.with_name(
            f"{self.path.stem}.broken-{stamp}{self.path.suffix}"
        )
        try:
            self.path.replace(backup)
        except OSError:
            return
        self.last_recovery_backup = backup

    def _read_document(self) -> dict[str, Any]:
        if not self.path.is_file():
            if self._cached_document is None:
                self._cached_document = self._new_document()
            self._cached_mtime_ns = None
            return self._cached_document

        try:
            mtime_ns = self.path.stat().st_mtime_ns
        except OSError:
            mtime_ns = None

        if (
            self._cached_document is not None
            and mtime_ns is not None
            and self._cached_mtime_ns == mtime_ns
        ):
            return self._cached_document

        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            self._backup_broken_file()
            self._cached_document = self._new_document()
            self._cached_mtime_ns = None
            return self._cached_document

        if not isinstance(raw, dict):
            self._backup_broken_file()
            self._cached_document = self._new_document()
            self._cached_mtime_ns = None
            return self._cached_document

        games = raw.get("games")
        if not isinstance(games, dict):
            games = {}

        self._cached_document = {
            "version": DOCUMENT_VERSION,
            "games": games,
        }
        self._cached_mtime_ns = mtime_ns
        return self._cached_document

    def _write_document(self, document: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            document,
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        ) + "\n"

        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
                temporary_path = Path(handle.name)

            temporary_path.replace(self.path)
            self._cached_document = document
            try:
                self._cached_mtime_ns = self.path.stat().st_mtime_ns
            except OSError:
                self._cached_mtime_ns = None
        except OSError as error:
            self._cached_document = None
            self._cached_mtime_ns = None
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
            raise LibraryCategoryError(str(error)) from error

    @staticmethod
    def _game_bucket(
        document: dict[str, Any],
        game_id: str,
        *,
        create: bool,
    ) -> dict[str, Any] | None:
        games = document.setdefault("games", {})
        if not isinstance(games, dict):
            games = {}
            document["games"] = games

        bucket = games.get(game_id)
        if not isinstance(bucket, dict):
            if not create:
                return None
            bucket = {
                "categories": [],
                "assignments": {},
            }
            games[game_id] = bucket

        if not isinstance(bucket.get("categories"), list):
            bucket["categories"] = []
        if not isinstance(bucket.get("assignments"), dict):
            bucket["assignments"] = {}
        return bucket

    @staticmethod
    def _categories_from_bucket(bucket: dict[str, Any] | None) -> tuple[LibraryCategory, ...]:
        if bucket is None:
            return ()

        result: list[LibraryCategory] = []
        seen_ids: set[str] = set()
        for entry in bucket.get("categories", []):
            if not isinstance(entry, dict):
                continue
            category_id = str(entry.get("id", "")).strip()
            name = str(entry.get("name", "")).strip()
            if not category_id or not name or category_id in seen_ids:
                continue
            seen_ids.add(category_id)
            result.append(LibraryCategory(id=category_id, name=name))
        return tuple(result)

    def categories(self, game_id: str) -> tuple[LibraryCategory, ...]:
        game_id = self.normalize_game_id(game_id)
        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            return self._categories_from_bucket(bucket)

    def create_category(self, game_id: str, name: str) -> LibraryCategory:
        game_id = self.normalize_game_id(game_id)
        name = self._normalize_name(name)

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=True)
            assert bucket is not None
            categories = self._categories_from_bucket(bucket)
            if any(item.name.casefold() == name.casefold() for item in categories):
                raise LibraryCategoryError("category name already exists")

            category = LibraryCategory(
                id=uuid4().hex,
                name=name,
            )
            bucket["categories"].append({
                "id": category.id,
                "name": category.name,
            })
            self._write_document(document)
            return category

    def rename_category(self, game_id: str, category_id: str, name: str) -> LibraryCategory:
        game_id = self.normalize_game_id(game_id)
        category_id = str(category_id).strip()
        name = self._normalize_name(name)

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            if bucket is None:
                raise LibraryCategoryError("category does not exist")

            categories = self._categories_from_bucket(bucket)
            if any(
                item.id != category_id
                and item.name.casefold() == name.casefold()
                for item in categories
            ):
                raise LibraryCategoryError("category name already exists")

            for entry in bucket["categories"]:
                if isinstance(entry, dict) and str(entry.get("id", "")) == category_id:
                    entry["name"] = name
                    self._write_document(document)
                    return LibraryCategory(id=category_id, name=name)

            raise LibraryCategoryError("category does not exist")

    def delete_category(self, game_id: str, category_id: str) -> None:
        game_id = self.normalize_game_id(game_id)
        category_id = str(category_id).strip()

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            if bucket is None:
                return

            before = len(bucket["categories"])
            bucket["categories"] = [
                entry
                for entry in bucket["categories"]
                if not (
                    isinstance(entry, dict)
                    and str(entry.get("id", "")) == category_id
                )
            ]
            if len(bucket["categories"]) == before:
                return

            assignments = bucket["assignments"]
            for mod_key in tuple(assignments):
                raw_ids = assignments.get(mod_key)
                if not isinstance(raw_ids, list):
                    assignments.pop(mod_key, None)
                    continue
                filtered = [
                    str(value)
                    for value in raw_ids
                    if str(value) != category_id
                ]
                if filtered:
                    assignments[mod_key] = filtered
                else:
                    assignments.pop(mod_key, None)

            self._write_document(document)

    def category_ids_for_mod(self, game_id: str, mod_key: str | Path) -> tuple[str, ...]:
        game_id = self.normalize_game_id(game_id)
        mod_key = self.normalize_mod_key(mod_key)

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=False)
            if bucket is None:
                return ()

            known_ids = {item.id for item in self._categories_from_bucket(bucket)}
            raw = bucket["assignments"].get(mod_key, [])
            if not isinstance(raw, list):
                return ()
            return tuple(
                value
                for value in (str(item) for item in raw)
                if value in known_ids
            )

    def category_names_for_mod(self, game_id: str, mod_key: str | Path) -> tuple[str, ...]:
        selected = set(self.category_ids_for_mod(game_id, mod_key))
        return tuple(
            category.name
            for category in self.categories(game_id)
            if category.id in selected
        )

    def set_categories_for_mod(
        self,
        game_id: str,
        mod_key: str | Path,
        category_ids: Iterable[str],
    ) -> tuple[str, ...]:
        game_id = self.normalize_game_id(game_id)
        mod_key = self.normalize_mod_key(mod_key)
        requested = {str(value).strip() for value in category_ids if str(value).strip()}

        with self._lock:
            document = self._read_document()
            bucket = self._game_bucket(document, game_id, create=True)
            assert bucket is not None
            categories = self._categories_from_bucket(bucket)
            ordered = [item.id for item in categories if item.id in requested]

            if ordered:
                bucket["assignments"][mod_key] = ordered
            else:
                bucket["assignments"].pop(mod_key, None)

            self._write_document(document)
            return tuple(ordered)

    def toggle_category_for_mod(
        self,
        game_id: str,
        mod_key: str | Path,
        category_id: str,
        enabled: bool,
    ) -> tuple[str, ...]:
        current = set(self.category_ids_for_mod(game_id, mod_key))
        if enabled:
            current.add(str(category_id))
        else:
            current.discard(str(category_id))
        return self.set_categories_for_mod(game_id, mod_key, current)

    def is_uncategorized(self, game_id: str, mod_key: str | Path) -> bool:
        return not self.category_ids_for_mod(game_id, mod_key)


__all__ = [
    "DOCUMENT_VERSION",
    "UNCATEGORIZED_FILTER_ID",
    "LibraryCategory",
    "LibraryCategoryError",
    "LibraryCategoryService",
    "default_library_categories_path",
]
