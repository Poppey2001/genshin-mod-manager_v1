from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translation_manager


class LibraryHeader(QFrame):
    """Moderner Library-Header mit wiederhergestelltem Import-Menü."""

    import_archives_requested = Signal()
    import_directory_requested = Signal()
    scan_requested = Signal()
    cancel_import_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("libraryHeader")

        self.title_label = QLabel(self)
        self.description_label = QLabel(self)

        self.import_button = QToolButton(self)
        self.refresh_button = QPushButton(self)
        self.cancel_import_button = QPushButton(self)

        self.import_menu = QMenu(self.import_button)
        self.archive_action = self.import_menu.addAction("")
        self.directory_action = self.import_menu.addAction("")

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )
        self.retranslate_ui()

    def _configure_widgets(self) -> None:
        self.title_label.setObjectName("pageTitle")

        self.description_label.setObjectName("pageDescription")
        self.description_label.setWordWrap(True)

        self.import_button.setObjectName("importButton")
        self.import_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )
        self.import_button.setMenu(self.import_menu)
        self.import_button.setMinimumHeight(38)

        self.refresh_button.setObjectName("refreshButton")
        self.refresh_button.setMinimumHeight(38)

        self.cancel_import_button.setObjectName("dangerButton")
        self.cancel_import_button.setMinimumHeight(38)
        self.cancel_import_button.hide()

        for button in (
            self.import_button,
            self.refresh_button,
            self.cancel_import_button,
        ):
            button.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(10)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(3)

        title_layout.addWidget(self.title_label)
        title_layout.addWidget(self.description_label)

        layout.addLayout(title_layout, stretch=1)
        layout.addWidget(self.cancel_import_button)
        layout.addWidget(self.refresh_button)
        layout.addWidget(self.import_button)

    def _connect_signals(self) -> None:
        # Klick auf die Hauptfläche = Archiv-Import.
        self.import_button.clicked.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )

        self.archive_action.triggered.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )

        self.directory_action.triggered.connect(
            lambda _checked=False:
            self.import_directory_requested.emit()
        )

        self.refresh_button.clicked.connect(
            lambda _checked=False:
            self.scan_requested.emit()
        )

        self.cancel_import_button.clicked.connect(
            lambda _checked=False:
            self.cancel_import_requested.emit()
        )

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.title_label.setText(
            tr("library.title")
        )
        self.description_label.setText(
            tr("library.description")
        )
        self.import_button.setText(
            "＋  " + tr("library.action.import")
        )
        self.refresh_button.setText(
            tr("library.action.scan")
        )
        self.cancel_import_button.setText(
            tr("library.action.cancel_import")
        )
        self.archive_action.setText(
            tr("library.import.archive")
        )
        self.directory_action.setText(
            tr("library.import.directory")
        )


__all__ = ["LibraryHeader"]
