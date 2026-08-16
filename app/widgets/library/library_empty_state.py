from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import (
    tr,
)


class LibraryEmptyState(
    QFrame
):
    import_requested = Signal()
    scan_requested = Signal()
    reset_filters_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self.setObjectName(
            "libraryEmptyState"
        )

        self.icon_label = QLabel(
            self
        )

        self.icon_label.setObjectName(
            "libraryEmptyIcon"
        )

        self.icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.title_label = QLabel(
            self
        )

        self.title_label.setObjectName(
            "libraryEmptyTitle"
        )

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label = QLabel(
            self
        )

        self.description_label.setObjectName(
            "libraryEmptyDescription"
        )

        self.description_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.description_label.setWordWrap(
            True
        )

        self.import_button = QPushButton(
            self
        )

        self.import_button.setObjectName(
            "libraryEmptyPrimaryButton"
        )

        self.scan_button = QPushButton(
            self
        )

        self.scan_button.setObjectName(
            "libraryEmptySecondaryButton"
        )

        self.reset_button = QPushButton(
            self
        )

        self.reset_button.setObjectName(
            "libraryEmptyPrimaryButton"
        )

        self._build_ui()
        self._connect_signals()

        self.show_library_empty()

    def _build_ui(
        self,
    ) -> None:
        root = QVBoxLayout(
            self
        )

        root.setContentsMargins(
            32,
            32,
            32,
            32,
        )

        root.setSpacing(
            10
        )

        root.addStretch(
            1
        )

        root.addWidget(
            self.icon_label
        )

        root.addSpacing(
            6
        )

        root.addWidget(
            self.title_label
        )

        root.addWidget(
            self.description_label
        )

        root.addSpacing(
            10
        )

        buttons = QHBoxLayout()

        buttons.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        buttons.setSpacing(
            8
        )

        buttons.addStretch(
            1
        )

        buttons.addWidget(
            self.scan_button
        )

        buttons.addWidget(
            self.import_button
        )

        buttons.addWidget(
            self.reset_button
        )

        buttons.addStretch(
            1
        )

        root.addLayout(
            buttons
        )

        root.addStretch(
            1
        )

    def _connect_signals(
        self,
    ) -> None:
        self.import_button.clicked.connect(
            self.import_requested.emit
        )

        self.scan_button.clicked.connect(
            self.scan_requested.emit
        )

        self.reset_button.clicked.connect(
            self.reset_filters_requested.emit
        )

    def show_library_empty(
        self,
    ) -> None:
        self.icon_label.setText(
            "◇"
        )

        self.title_label.setText(
            tr(
                "library.empty.title"
            )
        )

        self.description_label.setText(
            tr(
                "library.empty.description"
            )
        )

        self.import_button.setText(
            "＋  "
            + tr(
                "library.action.import"
            )
        )

        self.scan_button.setText(
            "↻  "
            + tr(
                "library.action.scan"
            )
        )

        self.import_button.show()
        self.scan_button.show()
        self.reset_button.hide()

    def show_no_results(
        self,
    ) -> None:
        self.icon_label.setText(
            "⌕"
        )

        self.title_label.setText(
            tr(
                "library.empty.no_results_title"
            )
        )

        self.description_label.setText(
            tr(
                "library.empty.no_results_description"
            )
        )

        self.reset_button.setText(
            tr(
                "library.filter.reset"
            )
        )

        self.import_button.hide()
        self.scan_button.hide()
        self.reset_button.show()