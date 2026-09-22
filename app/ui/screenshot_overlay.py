"""Full-screen *frozen-image* overlay for choosing a capture rectangle.

Displays a real screenshot of the desktop as the background, dims it lightly,
and lets the user drag a rectangle. The selected region is cropped straight from
that frozen image, so what the user sees is what is captured.

High-DPI correctness: mouse/drag coordinates and the widget rect are in the
screen's *logical* points, while the captured pixmap is in *physical* pixels.
The logical→physical scale is derived from the pixmap size vs. the screen's
logical geometry (a stable source, unlike the widget size which can vary), so
the crop lines up exactly at any Windows display-scaling setting.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..capture.region_selector import Region
from ..utils.logging import get_logger

log = get_logger("overlay")


class ScreenshotOverlay(QWidget):
    # (Region | None, cropped_image_path | None)
    selected = Signal(object, object)

    def __init__(self, pixmap: QPixmap, out_path: str) -> None:
        super().__init__()
        self._pix = pixmap
        self._out = out_path
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint
                            | Qt.WindowType.Tool)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._origin: Optional[QPoint] = None
        self._rubber = QRect()
        scr = QGuiApplication.primaryScreen()
        self._screen = scr.geometry()                 # logical points
        # physical pixels in the captured image per logical point
        self._scale_x = self._pix.width() / max(1, self._screen.width())
        self._scale_y = self._pix.height() / max(1, self._screen.height())
        self.setGeometry(self._screen)
        log.info("overlay: pix=%dx%d screen=%dx%d dpr=%.2f scale=%.3f/%.3f",
                 self._pix.width(), self._pix.height(),
                 self._screen.width(), self._screen.height(),
                 scr.devicePixelRatio(), self._scale_x, self._scale_y)

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.drawPixmap(self.rect(), self._pix)          # frozen desktop, scaled
        p.fillRect(self.rect(), QColor(0, 0, 0, 45))  # light dim
        if not self._rubber.isNull():
            src = QRect(int(self._rubber.x() * self._scale_x),
                        int(self._rubber.y() * self._scale_y),
                        int(self._rubber.width() * self._scale_x),
                        int(self._rubber.height() * self._scale_y))
            p.drawPixmap(self._rubber, self._pix, src)  # bright selection
            p.setPen(QPen(QColor(0, 170, 255), 2))
            p.drawRect(self._rubber)

    def mousePressEvent(self, e) -> None:  # noqa: N802
        self._origin = e.position().toPoint()
        self._rubber = QRect(self._origin, self._origin)
        self.update()

    def mouseMoveEvent(self, e) -> None:  # noqa: N802
        if self._origin is not None:
            self._rubber = QRect(self._origin,
                                 e.position().toPoint()).normalized()
            self.update()

    def mouseReleaseEvent(self, _e) -> None:  # noqa: N802
        r = self._rubber.normalized()
        self.close()
        if r.width() > 4 and r.height() > 4:
            path = self._crop_and_save(r)
            region = Region(self._screen.x() + r.x(), self._screen.y() + r.y(),
                            r.width(), r.height())
            self.selected.emit(region, path)
        else:
            self.selected.emit(None, None)

    def keyPressEvent(self, e) -> None:  # noqa: N802
        if e.key() == Qt.Key.Key_Escape:
            self.close()
            self.selected.emit(None, None)

    def _crop_and_save(self, r: QRect) -> Optional[str]:
        x = int(r.x() * self._scale_x)
        y = int(r.y() * self._scale_y)
        w = int(r.width() * self._scale_x)
        h = int(r.height() * self._scale_y)
        # clamp to the pixmap bounds so we never read outside it
        x = max(0, min(x, self._pix.width() - 1))
        y = max(0, min(y, self._pix.height() - 1))
        w = max(1, min(w, self._pix.width() - x))
        h = max(1, min(h, self._pix.height() - y))
        log.info("overlay crop: rubber=%s -> src=(%d,%d,%d,%d)",
                 (r.x(), r.y(), r.width(), r.height()), x, y, w, h)
        crop = self._pix.copy(x, y, w, h)
        return self._out if crop.save(self._out, "PNG") else None
