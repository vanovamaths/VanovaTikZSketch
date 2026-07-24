
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QColor, QImage
from PyQt5.QtWidgets import QWidget

from render import paint_shapes, shapes_bbox


class PreviewWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(220)
        self.setStyleSheet("background-color: white; border-radius: 6px;")
        self.shapes = []

    def set_shapes(self, shapes):
        self.shapes = shapes
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("white"))

        if not self.shapes:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(self.rect(), Qt.AlignCenter, "Live preview will appear here")
            painter.end()
            return

        bbox = shapes_bbox(self.shapes)
        if bbox is None:
            painter.end()
            return
        x0, y0, x1, y1 = bbox
        w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
        margin = 28
        avail_w, avail_h = max(self.width() - 2 * margin, 10), max(self.height() - 2 * margin, 10)
        scale = min(avail_w / w, avail_h / h)
        scale = min(scale, 4.0)
        cx_shape, cy_shape = (x0 + x1) / 2, (y0 + y1) / 2

        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(scale, scale)
        painter.translate(-cx_shape, -cy_shape)
        paint_shapes(painter, self.shapes)

        painter.end()

    def render_to_image(self, scale: float = 3.0) -> QImage:
        """
        High-resolution snapshot of exactly what the preview currently shows
        -- for exporting a publication-quality image (not a screen grab),
        e.g. to include as a figure in a scientific article.
        """
        w, h = max(self.width(), 1), max(self.height(), 1)
        img = QImage(int(w * scale), int(h * scale), QImage.Format_ARGB32)
        img.fill(QColor("white"))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.scale(scale, scale)

        if self.shapes:
            bbox = shapes_bbox(self.shapes)
            if bbox is not None:
                x0, y0, x1, y1 = bbox
                ww, hh = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
                margin = 28
                avail_w, avail_h = max(w - 2 * margin, 10), max(h - 2 * margin, 10)
                sc = min(avail_w / ww, avail_h / hh)
                sc = min(sc, 4.0)
                cx_shape, cy_shape = (x0 + x1) / 2, (y0 + y1) / 2
                painter.translate(w / 2, h / 2)
                painter.scale(sc, sc)
                painter.translate(-cx_shape, -cy_shape)
                paint_shapes(painter, self.shapes)

        painter.end()
        return img
