from __future__ import annotations

from PySide6.QtCore import (
    Signal,
)

from PySide6.QtGui import (
    QTextDocumentFragment,
)
from app.widgets.gamebanana.image_gallery import (
    GameBananaImageGallery,
)
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.gamebanana.models import (
    GameBananaFile,
    GameBananaMod,
)

from app.i18n import (
    tr,
    translation_manager,
)

from app.widgets.gamebanana.preview_image import (
    GameBananaPreviewImage,
)


class GameBananaModDetails(
    QScrollArea
):
    back_requested = Signal()

    open_requested = Signal()

    install_requested = Signal(
        object
    )

    cancel_requested = Signal()

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            parent
        )

        self._mod: (
            GameBananaMod
            | None
        ) = None

        self._download_running = (
            False
        )

        self.content = QWidget()

        self.back_button = QPushButton()

        self.gallery = (
            GameBananaImageGallery(
                parent=self.content
            )
        )

        self.name_label = QLabel()

        self.author_label = QLabel()

        self.meta_label = QLabel()

        self.stats_label = QLabel()

        self.description = (
            QTextBrowser()
        )

        self.file_label = QLabel()

        self.file_combo = (
            QComboBox()
        )

        self.open_button = QPushButton()

        self.install_button = QPushButton()

        self.cancel_button = QPushButton()

        self.progress = (
            QProgressBar()
        )

        self.status_label = QLabel()

        self._build_ui()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )

        self.retranslate_ui()
        self.clear_mod()

    def _build_ui(
        self,
    ) -> None:
        self.setWidgetResizable(
            True
        )

        self.setFrameShape(
            QFrame.Shape.NoFrame
        )

        self.setWidget(
            self.content
        )

        layout = QVBoxLayout(
            self.content
        )

        layout.setContentsMargins(
            10,
            4,
            18,
            24,
        )

        layout.setSpacing(
            12
        )

        layout.addWidget(
            self.back_button
        )

        layout.addWidget(
            self.gallery
        )

        self.name_label.setObjectName(
            "gameBananaDetailsTitle"
        )

        self.name_label.setWordWrap(
            True
        )

        self.author_label.setObjectName(
            "gameBananaDetailsAuthor"
        )

        self.meta_label.setObjectName(
            "gameBananaDetailsMeta"
        )

        self.stats_label.setObjectName(
            "gameBananaDetailsStats"
        )

        layout.addWidget(
            self.name_label
        )

        layout.addWidget(
            self.author_label
        )

        layout.addWidget(
            self.meta_label
        )

        layout.addWidget(
            self.stats_label
        )

        self.description.setMinimumHeight(
            180
        )

        layout.addWidget(
            self.description
        )

        layout.addWidget(
            self.file_label
        )

        layout.addWidget(
            self.file_combo
        )

        actions = QHBoxLayout()

        actions.addWidget(
            self.open_button
        )

        actions.addStretch(
            1
        )

        actions.addWidget(
            self.install_button
        )

        actions.addWidget(
            self.cancel_button
        )

        layout.addLayout(
            actions
        )

        layout.addWidget(
            self.progress
        )

        layout.addWidget(
            self.status_label
        )

        layout.addStretch(
            1
        )

        self.back_button.clicked.connect(
            self.back_requested
        )

        self.open_button.clicked.connect(
            self.open_requested
        )

        self.install_button.clicked.connect(
            self._emit_install
        )

        self.cancel_button.clicked.connect(
            self.cancel_requested
        )

        self.progress.hide()

        self.cancel_button.hide()

        self.setStyleSheet(
            """
            QLabel#gameBananaDetailsTitle {
                color: #ffffff;
                font-size: 26px;
                font-weight: 800;
            }

            QLabel#gameBananaDetailsAuthor {
                color: #aab1bd;
                font-size: 14px;
            }

            QLabel#gameBananaDetailsMeta {
                color: #8172e8;
                font-size: 13px;
                font-weight: 600;
            }

            QLabel#gameBananaDetailsStats {
                color: #828b9a;
                font-size: 12px;
            }

            QTextBrowser {
                background: #171b23;
                border: 1px solid #2c323d;
                border-radius: 8px;
                padding: 10px;
                color: #d3d7de;
            }

            QComboBox {
                min-height: 38px;
                background: #191e27;
                border: 1px solid #343b48;
                border-radius: 7px;
                padding: 0 10px;
            }
            """
        )

    # ========================================================
    # Translation
    # ========================================================

    def retranslate_ui(
        self,
        _language: str | None = None,
    ) -> None:
        self.back_button.setText(
            tr(
                "gamebanana.details.back"
            )
        )

        self.file_label.setText(
            tr(
                "gamebanana.files"
            )
        )

        self.open_button.setText(
            tr(
                "gamebanana.open_page"
            )
        )

        self.install_button.setText(
            tr(
                "gamebanana.download_install"
            )
        )

        self.cancel_button.setText(
            tr(
                "common.cancel"
            )
        )

        if self._mod is not None:
            self._refresh_mod_texts()

    def _refresh_mod_texts(
        self,
    ) -> None:
        mod = self._mod

        if mod is None:
            return

        self.name_label.setText(
            mod.name
        )

        self.author_label.setText(
            tr(
                "gamebanana.mod.author",
                author=(
                    mod.author
                    or tr(
                        "gamebanana.value.unknown"
                    )
                ),
            )
        )

        meta_parts: list[str] = []

        if mod.category:
            meta_parts.append(
                mod.category
            )

        if mod.game_name:
            meta_parts.append(
                mod.game_name
            )

        meta_parts.append(
            f"GameBanana #{mod.id}"
        )

        self.meta_label.setText(
            " • ".join(
                meta_parts
            )
        )

        self.stats_label.setText(
            tr(
                "gamebanana.mod.stats",
                downloads=self._format_count(
                    mod.downloads
                ),
                likes=self._format_count(
                    mod.likes
                ),
                views=self._format_count(
                    mod.views
                ),
            )
        )

        description = (
            mod.description
            or tr(
                "gamebanana.mod.no_description"
            )
        )

        plain_description = (
            QTextDocumentFragment
            .fromHtml(
                description
            )
            .toPlainText()
        )

        self.description.setPlainText(
            plain_description
        )

    # ========================================================
    # Mod
    # ========================================================

    def set_mod(
        self,
        mod: GameBananaMod,
    ) -> None:
        self._mod = mod

        image_urls = (
            mod.image_urls
        )

        if (
            not image_urls
            and mod.preview_url
        ):
            image_urls = (
                mod.preview_url,
            )

        self.gallery.set_urls(
            image_urls
        )

        self._refresh_mod_texts()

        self.file_combo.clear()

        for file in mod.files:
            self.file_combo.addItem(
                self._file_name(
                    file
                ),
                userData=file,
            )

        default_file = (
            mod.default_file()
        )

        if default_file:
            for index in range(
                self.file_combo.count()
            ):
                if (
                    self.file_combo.itemData(
                        index
                    )
                    == default_file
                ):
                    self.file_combo.setCurrentIndex(
                        index
                    )

                    break

        self.open_button.setEnabled(
            bool(
                mod.profile_url
            )
        )

        self.install_button.setEnabled(
            bool(
                mod.files
            )
        )

        self.progress.hide()

        self.cancel_button.hide()

        self.status_label.clear()

    def clear_mod(
        self,
    ) -> None:
        self._mod = None

        self.gallery.clear()

        self.name_label.clear()

        self.author_label.clear()

        self.meta_label.clear()

        self.stats_label.clear()

        self.description.clear()

        self.file_combo.clear()

        self.progress.hide()

        self.cancel_button.hide()

        self.status_label.clear()

    # ========================================================
    # Selected File
    # ========================================================

    def selected_file(
        self,
    ) -> GameBananaFile | None:
        value = (
            self.file_combo
            .currentData()
        )

        if isinstance(
            value,
            GameBananaFile,
        ):
            return value

        return None

    def _emit_install(
        self,
    ) -> None:
        file = (
            self.selected_file()
        )

        if file is not None:
            self.install_requested.emit(
                file
            )

    # ========================================================
    # Busy
    # ========================================================

    def set_busy(
        self,
        busy: bool,
    ) -> None:
        self.file_combo.setEnabled(
            not busy
        )

        self.open_button.setEnabled(
            (
                not busy
                and self._mod is not None
                and bool(
                    self._mod.profile_url
                )
            )
        )

        self.install_button.setEnabled(
            (
                not busy
                and self.selected_file()
                is not None
            )
        )

        self.back_button.setEnabled(
            not busy
        )

    # ========================================================
    # Download
    # ========================================================

    def start_download(
        self,
        file: GameBananaFile,
    ) -> None:
        self._download_running = (
            True
        )

        self.progress.show()

        self.progress.setRange(
            0,
            100,
        )

        self.progress.setValue(
            0
        )

        self.cancel_button.show()

        self.status_label.setText(
            tr(
                "gamebanana.status.downloading",
                file=file.name,
            )
        )

    def update_download(
        self,
        current: int,
        total: int,
    ) -> None:
        if total <= 0:
            self.progress.setRange(
                0,
                0,
            )

            self.status_label.setText(
                tr(
                    "gamebanana.status.download_bytes",
                    current=self._format_bytes(
                        current
                    ),
                )
            )

            return

        self.progress.setRange(
            0,
            100,
        )

        percentage = int(
            min(
                100,
                current
                * 100
                / total,
            )
        )

        self.progress.setValue(
            percentage
        )

        self.status_label.setText(
            tr(
                "gamebanana.status.download_progress",
                current=self._format_bytes(
                    current
                ),
                total=self._format_bytes(
                    total
                ),
            )
        )

    def finish_download(
        self,
    ) -> None:
        self._download_running = (
            False
        )

        self.progress.setRange(
            0,
            100,
        )

        self.progress.setValue(
            100
        )

        self.cancel_button.hide()

        self.status_label.setText(
            tr(
                "gamebanana.status.download_finished"
            )
        )

    def fail_download(
        self,
        message: str,
    ) -> None:
        self._download_running = (
            False
        )

        self.progress.hide()

        self.cancel_button.hide()

        self.status_label.setText(
            message
        )

    # ========================================================
    # Format
    # ========================================================

    @staticmethod
    def _format_count(
        value: int | None,
    ) -> str:
        if value is None:
            return "-"

        formatted = f"{value:,}"

        if (
            translation_manager.language
            == "de"
        ):
            return formatted.replace(
                ",",
                ".",
            )

        return formatted

    @staticmethod
    def _file_name(
        file: GameBananaFile,
    ) -> str:
        if file.size is None:
            return file.name

        return (
            f"{file.name} "
            f"({file.size / 1024 / 1024:.1f} MB)"
        )

    @staticmethod
    def _format_bytes(
        value: int,
    ) -> str:
        if value < 1024:
            return f"{value} B"

        if value < 1024 ** 2:
            return (
                f"{value / 1024:.1f} KB"
            )

        if value < 1024 ** 3:
            return (
                f"{value / 1024 ** 2:.1f} MB"
            )

        return (
            f"{value / 1024 ** 3:.2f} GB"
        )


__all__ = [
    "GameBananaModDetails",
]