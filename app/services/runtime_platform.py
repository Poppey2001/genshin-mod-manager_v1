from __future__ import annotations

import platform
import sys

from pathlib import Path


def is_windows(
) -> bool:
    return (
        platform.system()
        .casefold()
        == "windows"
    )


def is_frozen(
) -> bool:
    return bool(
        getattr(
            sys,
            "frozen",
            False,
        )
    )


def application_root(
) -> Path:
    """
    Installations-/Projektordner.

    PyInstaller:
        Ordner der EXE

    Python-Dev:
        Projektroot
    """

    if is_frozen():
        return (
            Path(
                sys.executable
            )
            .resolve()
            .parent
        )

    return (
        Path(
            __file__
        )
        .resolve()
        .parents[
            2
        ]
    )


def restart_executable(
) -> Path:
    return (
        Path(
            sys.executable
        )
        .resolve()
    )


def restart_arguments(
) -> tuple[
    str,
    ...,
]:
    if is_frozen():
        return ()

    return (
        str(
            application_root()
            / "main.py"
        ),
    )