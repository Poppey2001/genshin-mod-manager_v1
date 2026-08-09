from __future__ import annotations

from pathlib import Path
from typing import Callable, cast

from PySide6.QtCore import (
    QEvent,
    QObject,
)

from PySide6.QtGui import (
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
)

from PySide6.QtWidgets import QWidget

from app.utils.library_drop_paths import (
    extract_import_paths,
)


ImportCallback = Callable[
    [list[Path]],
    None,
]


class LibraryDropHandler(QObject):
    def __init__(
        self,
        *,
        import_callback: ImportCallback,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._import_callback = (
            import_callback
        )

    def install_on(
        self,
        widget: QWidget,
    ) -> None:
        """
        Aktiviert Drag & Drop auf dem Widget
        und installiert diesen Handler als
        Event-Filter.
        """

        widget.setAcceptDrops(
            True
        )

        widget.installEventFilter(
            self
        )

    def eventFilter(
        self,
        watched: QObject,
        event: QEvent,
    ) -> bool:
        event_type = event.type()

        if (
            event_type
            == QEvent.Type.DragEnter
        ):
            self._handle_drag_enter(
                cast(
                    QDragEnterEvent,
                    event,
                )
            )
            return True

        if (
            event_type
            == QEvent.Type.DragMove
        ):
            self._handle_drag_move(
                cast(
                    QDragMoveEvent,
                    event,
                )
            )
            return True

        if (
            event_type
            == QEvent.Type.Drop
        ):
            self._handle_drop(
                cast(
                    QDropEvent,
                    event,
                )
            )
            return True

        return super().eventFilter(
            watched,
            event,
        )

    def _handle_drag_enter(
        self,
        event: QDragEnterEvent,
    ) -> None:
        paths = extract_import_paths(
            event.mimeData()
        )

        if paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def _handle_drag_move(
        self,
        event: QDragMoveEvent,
    ) -> None:
        paths = extract_import_paths(
            event.mimeData()
        )

        if paths:
            event.acceptProposedAction()
            return

        event.ignore()

    def _handle_drop(
        self,
        event: QDropEvent,
    ) -> None:
        paths = extract_import_paths(
            event.mimeData()
        )

        if not paths:
            event.ignore()
            return

        event.acceptProposedAction()

        self._import_callback(
            paths
        )