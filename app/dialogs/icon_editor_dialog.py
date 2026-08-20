from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QBuffer,
    QIODevice,
    QPointF,
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QImage,
    QImageReader,
    QPainter,
    QPen,
    QTransform,
)
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr, translation_manager
from app.services.component_resources import resolve_component_path


EDITOR_CANVAS_SIZE = 400
OUTPUT_ICON_SIZE = 512


def _load_source_image(path: Path) -> QImage:
    suffix = path.suffix.casefold()

    if suffix == ".svg":
        try:
            from PySide6.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(str(path))
            if renderer.isValid():
                default_size = renderer.defaultSize()
                width = max(1, default_size.width())
                height = max(1, default_size.height())

                longest = max(width, height)
                factor = min(1.0, 2048.0 / float(longest)) if longest > 0 else 1.0
                width = max(1, round(width * factor))
                height = max(1, round(height * factor))

                image = QImage(
                    width,
                    height,
                    QImage.Format.Format_ARGB32_Premultiplied,
                )
                image.fill(Qt.GlobalColor.transparent)

                painter = QPainter(image)
                renderer.render(painter)
                painter.end()

                if not image.isNull():
                    return image.convertToFormat(
                        QImage.Format.Format_ARGB32_Premultiplied
                    )
        except (ImportError, RuntimeError):
            pass

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)
    image = reader.read()

    if image.isNull():
        image = QImage(str(path))

    if image.isNull():
        return QImage()

    return image.convertToFormat(
        QImage.Format.Format_ARGB32_Premultiplied
    )


class IconEditorCanvas(QWidget):
    zoom_step_requested = Signal(int)

    def __init__(
        self,
        image: QImage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._image = image
        self._zoom = 1.0
        self._offset = QPointF(0.0, 0.0)
        self._drag_start: QPointF | None = None
        self._offset_at_drag_start = QPointF(0.0, 0.0)

        self.setObjectName("iconEditorCanvas")
        self.setFixedSize(
            EDITOR_CANVAS_SIZE,
            EDITOR_CANVAS_SIZE,
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setMouseTracking(True)

    @property
    def image(self) -> QImage:
        return self._image

    def set_image(self, image: QImage) -> None:
        self._image = image
        self._offset = QPointF(0.0, 0.0)
        self.update()

    def set_zoom(self, zoom: float) -> None:
        self._zoom = max(0.10, min(float(zoom), 20.0))
        self.update()

    def zoom(self) -> float:
        return self._zoom

    def reset_position(self) -> None:
        self._offset = QPointF(0.0, 0.0)
        self.update()

    def fit_zoom(self) -> float:
        return 1.0

    def fill_zoom(self) -> float:
        if self._image.isNull():
            return 1.0

        source_width = max(1.0, float(self._image.width()))
        source_height = max(1.0, float(self._image.height()))
        canvas = float(EDITOR_CANVAS_SIZE)

        fit_scale = min(
            canvas / source_width,
            canvas / source_height,
        )
        fill_scale = max(
            canvas / source_width,
            canvas / source_height,
        )

        if fit_scale <= 0.0:
            return 1.0

        return max(0.10, min(fill_scale / fit_scale, 20.0))

    def rotate_left(self) -> None:
        transform = QTransform()
        transform.rotate(-90.0)
        self.set_image(
            self._image.transformed(
                transform,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def rotate_right(self) -> None:
        transform = QTransform()
        transform.rotate(90.0)
        self.set_image(
            self._image.transformed(
                transform,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _fit_scale(self) -> float:
        if self._image.isNull():
            return 1.0

        return min(
            float(self.width()) / max(1.0, float(self._image.width())),
            float(self.height()) / max(1.0, float(self._image.height())),
        )

    def _target_rect(self) -> QRectF:
        scale = self._fit_scale() * self._zoom
        width = float(self._image.width()) * scale
        height = float(self._image.height()) * scale

        center = QPointF(
            self.width() / 2.0,
            self.height() / 2.0,
        ) + self._offset

        return QRectF(
            center.x() - width / 2.0,
            center.y() - height / 2.0,
            width,
            height,
        )

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        tile = 20
        light = QColor("#202630")
        dark = QColor("#171c23")

        for y in range(0, self.height(), tile):
            for x in range(0, self.width(), tile):
                painter.fillRect(
                    x,
                    y,
                    tile,
                    tile,
                    light if ((x // tile) + (y // tile)) % 2 == 0 else dark,
                )

        painter.save()
        painter.setClipRect(self.rect())
        if not self._image.isNull():
            painter.drawImage(
                self._target_rect(),
                self._image,
                QRectF(self._image.rect()),
            )
        painter.restore()

        border = QPen(QColor("#7b66eb"))
        border.setWidth(2)
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(
            QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0),
            10.0,
            10.0,
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.position()
            self._offset_at_drag_start = QPointF(self._offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None:
            delta = event.position() - self._drag_start
            self._offset = self._offset_at_drag_start + delta
            self.update()
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return

        super().mouseReleaseEvent(event)

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y()
        if delta:
            self.zoom_step_requested.emit(10 if delta > 0 else -10)
            event.accept()
            return

        super().wheelEvent(event)

    def render_output(self, size: int = OUTPUT_ICON_SIZE) -> QImage:
        size = max(32, int(size))

        output = QImage(
            size,
            size,
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        output.fill(Qt.GlobalColor.transparent)

        if self._image.isNull():
            return output

        canvas_ratio = float(size) / float(EDITOR_CANVAS_SIZE)
        fit_scale = self._fit_scale() * self._zoom * canvas_ratio

        width = float(self._image.width()) * fit_scale
        height = float(self._image.height()) * fit_scale
        offset = QPointF(
            self._offset.x() * canvas_ratio,
            self._offset.y() * canvas_ratio,
        )
        center = QPointF(
            size / 2.0,
            size / 2.0,
        ) + offset

        target = QRectF(
            center.x() - width / 2.0,
            center.y() - height / 2.0,
            width,
            height,
        )

        painter = QPainter(output)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.drawImage(
            target,
            self._image,
            QRectF(self._image.rect()),
        )
        painter.end()

        return output


class IconEditorDialog(QDialog):
    def __init__(
        self,
        *,
        source_path: Path | str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.source_path = Path(source_path).expanduser()
        self._image = _load_source_image(self.source_path)
        self._result_png: bytes | None = None

        if self._image.isNull():
            raise ValueError(tr("icons.error.invalid_image"))

        self.setObjectName("iconEditorDialog")
        self.setModal(True)
        self.setMinimumSize(760, 610)
        self.resize(820, 650)

        self.title_label = QLabel(self)
        self.title_label.setObjectName("iconEditorTitle")
        self.description_label = QLabel(self)
        self.description_label.setObjectName("iconEditorDescription")
        self.description_label.setWordWrap(True)

        self.canvas = IconEditorCanvas(
            self._image,
            self,
        )

        self.zoom_title_label = QLabel(self)
        self.zoom_value_label = QLabel(self)
        self.zoom_value_label.setObjectName("iconEditorZoomValue")

        self.zoom_slider = QSlider(
            Qt.Orientation.Horizontal,
            self,
        )
        self.zoom_slider.setObjectName("iconEditorZoomSlider")
        self.zoom_slider.setRange(10, 2000)
        self.zoom_slider.setValue(100)

        self.fit_button = QPushButton(self)
        self.fill_button = QPushButton(self)
        self.center_button = QPushButton(self)
        self.rotate_left_button = QPushButton(self)
        self.rotate_right_button = QPushButton(self)
        self.reset_button = QPushButton(self)
        self.cancel_button = QPushButton(self)
        self.save_button = QPushButton(self)

        self.save_button.setObjectName("iconEditorPrimaryButton")
        self.cancel_button.setObjectName("iconEditorSecondaryButton")

        for button in (
            self.fit_button,
            self.fill_button,
            self.center_button,
            self.rotate_left_button,
            self.rotate_right_button,
            self.reset_button,
        ):
            button.setObjectName("iconEditorToolButton")

        self.output_label = QLabel(self)
        self.output_label.setObjectName("iconEditorOutputInfo")

        self._build_ui()
        self._connect_signals()
        self._apply_stylesheet()

        translation_manager.language_changed.connect(
            self.retranslate_ui
        )
        self.retranslate_ui()

        self._set_fit()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        root.addWidget(self.title_label)
        root.addWidget(self.description_label)

        body = QHBoxLayout()
        body.setSpacing(20)
        body.addWidget(
            self.canvas,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        controls_frame = QFrame(self)
        controls_frame.setObjectName("iconEditorControls")
        controls = QVBoxLayout(controls_frame)
        controls.setContentsMargins(16, 16, 16, 16)
        controls.setSpacing(11)

        zoom_header = QHBoxLayout()
        zoom_header.addWidget(self.zoom_title_label)
        zoom_header.addStretch(1)
        zoom_header.addWidget(self.zoom_value_label)
        controls.addLayout(zoom_header)
        controls.addWidget(self.zoom_slider)

        controls.addWidget(self.fit_button)
        controls.addWidget(self.fill_button)
        controls.addWidget(self.center_button)

        rotate_row = QHBoxLayout()
        rotate_row.setSpacing(8)
        rotate_row.addWidget(self.rotate_left_button)
        rotate_row.addWidget(self.rotate_right_button)
        controls.addLayout(rotate_row)

        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        controls.addWidget(self.output_label)

        body.addWidget(
            controls_frame,
            stretch=1,
        )
        root.addLayout(body, stretch=1)

        footer = QHBoxLayout()
        footer.addStretch(1)
        footer.addWidget(self.cancel_button)
        footer.addWidget(self.save_button)
        root.addLayout(footer)

    def _connect_signals(self) -> None:
        self.zoom_slider.valueChanged.connect(
            self._on_zoom_changed
        )
        self.canvas.zoom_step_requested.connect(
            self._adjust_zoom_slider
        )
        self.fit_button.clicked.connect(self._set_fit)
        self.fill_button.clicked.connect(self._set_fill)
        self.center_button.clicked.connect(self.canvas.reset_position)
        self.rotate_left_button.clicked.connect(self._rotate_left)
        self.rotate_right_button.clicked.connect(self._rotate_right)
        self.reset_button.clicked.connect(self._reset_editor)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._save_and_accept)

    def _on_zoom_changed(self, value: int) -> None:
        zoom = max(0.10, float(value) / 100.0)
        self.canvas.set_zoom(zoom)
        self.zoom_value_label.setText(f"{value}%")

    def _adjust_zoom_slider(self, amount: int) -> None:
        self.zoom_slider.setValue(
            max(
                self.zoom_slider.minimum(),
                min(
                    self.zoom_slider.maximum(),
                    self.zoom_slider.value() + int(amount),
                ),
            )
        )

    def _set_fit(self, _checked: bool = False) -> None:
        self.canvas.reset_position()
        self.zoom_slider.setValue(100)

    def _set_fill(self, _checked: bool = False) -> None:
        self.canvas.reset_position()
        value = round(self.canvas.fill_zoom() * 100.0)
        self.zoom_slider.setValue(
            max(
                self.zoom_slider.minimum(),
                min(self.zoom_slider.maximum(), value),
            )
        )

    def _rotate_left(self, _checked: bool = False) -> None:
        self.canvas.rotate_left()
        self._set_fill()

    def _rotate_right(self, _checked: bool = False) -> None:
        self.canvas.rotate_right()
        self._set_fill()

    def _reset_editor(self, _checked: bool = False) -> None:
        self._image = _load_source_image(self.source_path)
        self.canvas.set_image(self._image)
        self._set_fit()

    def _save_and_accept(self, _checked: bool = False) -> None:
        image = self.canvas.render_output(OUTPUT_ICON_SIZE)
        data = QByteArray()
        buffer = QBuffer(data)

        if not buffer.open(QIODevice.OpenModeFlag.WriteOnly):
            QMessageBox.critical(
                self,
                tr("icons.error.title"),
                tr("icons.editor.error.encode"),
            )
            return

        success = image.save(buffer, "PNG")
        buffer.close()

        if not success:
            QMessageBox.critical(
                self,
                tr("icons.error.title"),
                tr("icons.editor.error.encode"),
            )
            return

        self._result_png = bytes(data)
        self.accept()

    def png_data(self) -> bytes | None:
        return self._result_png

    def retranslate_ui(self, _language: str | None = None) -> None:
        self.setWindowTitle(tr("icons.editor.window_title"))
        self.title_label.setText(tr("icons.editor.title"))
        self.description_label.setText(
            tr(
                "icons.editor.description",
                file=self.source_path.name,
            )
        )
        self.zoom_title_label.setText(tr("icons.editor.zoom"))
        self.zoom_value_label.setText(f"{self.zoom_slider.value()}%")
        self.fit_button.setText(tr("icons.editor.fit"))
        self.fill_button.setText(tr("icons.editor.fill"))
        self.center_button.setText(tr("icons.editor.center"))
        self.rotate_left_button.setText(tr("icons.editor.rotate_left"))
        self.rotate_right_button.setText(tr("icons.editor.rotate_right"))
        self.reset_button.setText(tr("icons.editor.reset"))
        self.cancel_button.setText(tr("common.cancel"))
        self.save_button.setText(tr("icons.editor.save"))
        self.output_label.setText(
            tr(
                "icons.editor.output",
                size=OUTPUT_ICON_SIZE,
            )
        )

    def _apply_stylesheet(self) -> None:
        bundled_path = (
            Path(__file__).resolve().parents[1]
            / "styles"
            / "icons.qss"
        )
        style_path = resolve_component_path(
            "styles/icons.qss",
            bundled_path,
        )

        try:
            stylesheet = style_path.read_text(encoding="utf-8")
        except OSError as error:
            raise RuntimeError(
                f"Icons stylesheet could not be loaded: {style_path}"
            ) from error

        self.setStyleSheet(stylesheet)


__all__ = [
    "IconEditorDialog",
]
