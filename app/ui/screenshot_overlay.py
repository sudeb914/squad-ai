"""Full-screen *frozen-image* overlay for choosing a capture rectangle.

Instead of a translucent window (which renders as solid black on some macOS/Qt
setups), we display an actual screenshot of the desktop as the background, dim
it, and let the user drag a rectangle over it. The selected region is cropped
straight from that frozen image, so what the user sees is exactly what is
captured — and we also return the region coordinates (for the Lock-area
feature).
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget

from ..capture.region_selector import Region


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
        self._screen = QGuiApplication.primaryScreen().geometry()
        self.setGeometry(self._screen)

    # scale between widget points and the (possibly Retina) pixmap
    def _sx(self) -> float:
        return self._pix.width() / max(1, self.width())

    def _sy(self) -> float:
        return self._pix.height() / max(1, self.height())

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        # frozen desktop as background, scaled to fill
        p.drawPixmap(self.rect(), self._pix)
        # dim everything *lightly* so the desktop underneath stays clearly
        # readable (a heavy dim looked almost black and hid the page content).
        p.fillRect(self.rect(), QColor(0, 0, 0, 45))
        if not self._rubber.isNull():
            sx, sy = self._sx(), self._sy()
            src = QRect(int(self._rubber.x() * sx), int(self._rubber.y() * sy),
                        int(self._rubber.width() * sx),
                        int(self._rubber.height() * sy))
            # show the selected area un-dimmed (bright) so it's obvious
            p.drawPixmap(self._rubber, self._pix, src)
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
        sx, sy = self._sx(), self._sy()
        crop = self._pix.copy(int(r.x() * sx), int(r.y() * sy),
                              int(r.width() * sx), int(r.height() * sy))
        return self._out if crop.save(self._out, "PNG") else None
