from __future__ import annotations

from PySide6.QtCore import Signal
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


class LibraryHeader(QFrame):
    """
    Kopfbereich der Mod-Bibliothek.

    Das Widget enthält nur die sichtbare Oberfläche.
    Scan- und Importlogik bleiben in LibraryPage.
    """

    import_archives_requested = Signal()
    import_directory_requested = Signal()
    scan_requested = Signal()
    cancel_import_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName(
            "libraryHeader"
        )

        self.import_button = QToolButton()
        self.refresh_button = QPushButton(
            "Neu scannen"
        )
        self.cancel_import_button = QPushButton(
            "Import abbrechen"
        )

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()

    def _configure_widgets(self) -> None:
        self.import_button.setObjectName(
            "importButton"
        )
        self.import_button.setText(
            "＋  Importieren"
        )
        self.import_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

        import_menu = QMenu(
            self.import_button
        )

        archive_action = import_menu.addAction(
            "ZIP oder Archiv auswählen"
        )

        directory_action = import_menu.addAction(
            "Mod-Ordner auswählen"
        )

        archive_action.triggered.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )

        directory_action.triggered.connect(
            lambda _checked=False:
            self.import_directory_requested.emit()
        )

        self.import_button.setMenu(
            import_menu
        )

        self.refresh_button.setObjectName(
            "refreshButton"
        )

        self.cancel_import_button.setObjectName(
            "dangerButton"
        )
        self.cancel_import_button.setVisible(
            False
        )

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            2,
            0,
            2,
            0,
        )
        layout.setSpacing(
            16
        )

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        title_layout.setSpacing(
            4
        )

        title_label = QLabel(
            "Mod-Bibliothek"
        )
        title_label.setObjectName(
            "pageTitle"
        )

        description_label = QLabel(
            "Verwalte, filtere und organisiere "
            "deine Genshin-Mods."
        )
        description_label.setObjectName(
            "pageDescription"
        )

        title_layout.addWidget(
            title_label
        )
        title_layout.addWidget(
            description_label
        )

        layout.addLayout(
            title_layout,
            stretch=1,
        )
        layout.addWidget(
            self.cancel_import_button
        )
        layout.addWidget(
            self.refresh_button
        )
        layout.addWidget(
            self.import_button
        )

    def _connect_signals(self) -> None:
        self.import_button.clicked.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )

        self.refresh_button.clicked.connect(
            lambda _checked=False:
            self.scan_requested.emit()
        )

        self.cancel_import_button.clicked.connect(
            lambda _checked=False:
            self.cancel_import_requested.emit()
        )