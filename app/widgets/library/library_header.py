from __future__ import annotations
from app.i18n import (
    tr,
    translation_manager,
)
from PySide6.QtCore import (
    Signal,
    Qt,
)
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
        self.refresh_button = QPushButton()
        self.cancel_import_button = QPushButton()

        self._configure_widgets()
        self._build_ui()
        self._connect_signals()
        
        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()

    def _configure_widgets(
        self,
    ) -> None:
        # ========================================================
        # IMPORT
        # ========================================================

        self.import_button.setObjectName(
            "importButton"
        )

        self.import_button.setMinimumWidth(
            138
        )

        self.import_button.setMinimumHeight(
            40
        )

        self.import_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.MenuButtonPopup
        )

        # --------------------------------------------------------
        # Import menu
        # --------------------------------------------------------

        self.import_menu = QMenu(
            self.import_button
        )

        self.import_menu.setObjectName(
            "libraryImportMenu"
        )

        self.archive_action = (
            self.import_menu.addAction(
                ""
            )
        )

        self.directory_action = (
            self.import_menu.addAction(
                ""
            )
        )

        self.archive_action.triggered.connect(
            lambda _checked=False:
            self.import_archives_requested.emit()
        )

        self.directory_action.triggered.connect(
            lambda _checked=False:
            self.import_directory_requested.emit()
        )

        self.import_button.setMenu(
            self.import_menu
        )

        # ========================================================
        # SCAN
        # ========================================================

        self.refresh_button.setObjectName(
            "refreshButton"
        )

        self.refresh_button.setMinimumWidth(
            112
        )

        self.refresh_button.setMinimumHeight(
            40
        )

        # ========================================================
        # CANCEL IMPORT
        # ========================================================

        self.cancel_import_button.setObjectName(
            "libraryCancelImportButton"
        )

        self.cancel_import_button.setMinimumHeight(
            40
        )

        self.cancel_import_button.setVisible(
            False
        )

    def _build_ui(
        self,
    ) -> None:
        # ========================================================
        # ROOT
        # ========================================================

        layout = QHBoxLayout(
            self
        )

        layout.setContentsMargins(
            2,
            2,
            2,
            4,
        )

        layout.setSpacing(
            18
        )

        # ========================================================
        # TITLE AREA
        # ========================================================

        title_layout = QVBoxLayout()

        title_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        title_layout.setSpacing(
            3
        )

        # --------------------------------------------------------
        # Title
        # --------------------------------------------------------

        self.title_label = QLabel()

        self.title_label.setObjectName(
            "pageTitle"
        )

        # --------------------------------------------------------
        # Description
        # --------------------------------------------------------

        self.description_label = QLabel()

        self.description_label.setObjectName(
            "pageDescription"
        )

        self.description_label.setWordWrap(
            True
        )

        # --------------------------------------------------------
        # Title layout
        # --------------------------------------------------------

        title_layout.addWidget(
            self.title_label
        )

        title_layout.addWidget(
            self.description_label
        )

        layout.addLayout(
            title_layout,
            stretch=1,
        )

        # ========================================================
        # ACTION AREA
        # ========================================================

        action_frame = QFrame(
            self
        )

        action_frame.setObjectName(
            "libraryHeaderActions"
        )

        action_layout = QHBoxLayout(
            action_frame
        )

        action_layout.setContentsMargins(
            4,
            4,
            4,
            4,
        )

        action_layout.setSpacing(
            6
        )

        # --------------------------------------------------------
        # Cancel import
        #
        # Normalerweise unsichtbar.
        # Wird vom LibraryHeaderController eingeblendet.
        # --------------------------------------------------------

        action_layout.addWidget(
            self.cancel_import_button
        )

        # --------------------------------------------------------
        # Scan
        # --------------------------------------------------------

        action_layout.addWidget(
            self.refresh_button
        )

        # --------------------------------------------------------
        # Import
        # --------------------------------------------------------

        action_layout.addWidget(
            self.import_button
        )

        layout.addWidget(
            action_frame,
            alignment=(
                Qt.AlignmentFlag.AlignRight
                | Qt.AlignmentFlag.AlignVCenter
            ),
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
        
    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        # ========================================================
        # TITLE
        # ========================================================

        self.title_label.setText(
            tr(
                "library.title"
            )
        )

        self.description_label.setText(
            tr(
                "library.description"
            )
        )

        # ========================================================
        # ACTIONS
        # ========================================================

        self.import_button.setText(
            "＋  "
            + tr(
                "library.action.import"
            )
        )

        self.refresh_button.setText(
            "↻  "
            + tr(
                "library.action.scan"
            )
        )

        self.cancel_import_button.setText(
            tr(
                "library.action.cancel_import"
            )
        )

        # ========================================================
        # IMPORT MENU
        # ========================================================

        self.archive_action.setText(
            tr(
                "library.import.archive"
            )
        )

        self.directory_action.setText(
            tr(
                "library.import.directory"
            )
        )