from __future__ import annotations

import logging
import os
import shutil
import subprocess

from pathlib import Path

from app.config import CACHE_DIR


logger = logging.getLogger(
    __name__
)


class AppImageUpdateError(
    RuntimeError
):
    pass


def current_appimage_path(
) -> Path | None:
    value = (
        os.environ.get(
            "APPIMAGE"
        )
    )

    if not value:
        return None

    path = Path(
        value
    ).expanduser()

    try:
        return path.resolve()

    except OSError:
        return path.absolute()


def is_appimage_runtime(
) -> bool:
    path = (
        current_appimage_path()
    )

    return (
        path is not None
        and path.is_file()
    )


def stage_update_and_launch_helper(
    downloaded_file: Path,
) -> Path:
    target = (
        current_appimage_path()
    )

    if target is None:
        raise AppImageUpdateError(
            (
                "Die Anwendung läuft "
                "nicht als AppImage."
            )
        )

    if not target.is_file():
        raise AppImageUpdateError(
            (
                "Die laufende AppImage-Datei "
                "wurde nicht gefunden."
            )
        )

    downloaded_file = (
        downloaded_file.resolve()
    )

    if not downloaded_file.is_file():
        raise AppImageUpdateError(
            (
                "Die heruntergeladene "
                "Update-Datei fehlt."
            )
        )

    target_directory = (
        target.parent
    )

    if not os.access(
        target_directory,
        os.W_OK,
    ):
        raise AppImageUpdateError(
            (
                "Der Ordner der AppImage-Datei "
                "ist nicht beschreibbar."
            )
        )

    staged_file = (
        target.with_name(
            f".{target.name}.update"
        )
    )

    try:
        shutil.copy2(
            downloaded_file,
            staged_file,
        )

        staged_file.chmod(
            staged_file.stat().st_mode
            | 0o111
        )

    except OSError as error:
        raise AppImageUpdateError(
            (
                "Das Update konnte nicht "
                "neben der AppImage-Datei "
                "vorbereitet werden."
            )
        ) from error

    helper_directory = (
        CACHE_DIR
        / "updates"
    )

    helper_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    helper_file = (
        helper_directory
        / "appimage-update-helper.sh"
    )

    helper_file.write_text(
        """#!/bin/sh
set -eu

PID="$1"
STAGED="$2"
TARGET="$3"
BACKUP="${TARGET}.old"

while kill -0 "$PID" 2>/dev/null; do
    sleep 0.25
done

rm -f -- "$BACKUP"

if [ -e "$TARGET" ]; then
    mv -- "$TARGET" "$BACKUP"
fi

if mv -- "$STAGED" "$TARGET"; then
    chmod +x "$TARGET"

    nohup "$TARGET" \
        >/dev/null \
        2>&1 &

    exit 0
fi

if [ -e "$BACKUP" ]; then
    mv -- "$BACKUP" "$TARGET"
fi

exit 1
""",
        encoding="utf-8",
    )

    helper_file.chmod(
        0o755
    )

    environment = (
        os.environ.copy()
    )

    original_library_path = (
        environment.get(
            "LD_LIBRARY_PATH_ORIG"
        )
    )

    if original_library_path:
        environment[
            "LD_LIBRARY_PATH"
        ] = original_library_path

    else:
        environment.pop(
            "LD_LIBRARY_PATH",
            None,
        )

    environment.pop(
        "PYTHONHOME",
        None,
    )

    try:
        subprocess.Popen(
            [
                "/bin/sh",
                str(helper_file),
                str(os.getpid()),
                str(staged_file),
                str(target),
            ],
            env=environment,
            start_new_session=True,
            close_fds=True,
        )

    except OSError as error:
        staged_file.unlink(
            missing_ok=True
        )

        raise AppImageUpdateError(
            (
                "Der Update-Helfer konnte "
                "nicht gestartet werden."
            )
        ) from error

    return target


def cleanup_previous_update_backup(
) -> None:
    target = (
        current_appimage_path()
    )

    if target is None:
        return

    backup = target.with_name(
        f"{target.name}.old"
    )

    if not backup.exists():
        return

    try:
        backup.unlink()

    except OSError:
        logger.warning(
            (
                "Altes AppImage-Backup "
                "konnte nicht entfernt "
                "werden: %s"
            ),
            backup,
        )