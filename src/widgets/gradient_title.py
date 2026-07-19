"""
gradient_title.py — Smooth flowing gradient title, no stutter.
Uses a continuous sin wave for smooth infinite loop instead of phase reset.
"""
import math
from PyQt6.QtWidgets import QWidget, QSizePolicy
from PyQt6.QtCore    import Qt, QTimer, QRectF
from PyQt6.QtGui     import (QPainter, QColor, QLinearGradient,
                              QFont, QFontMetrics, QBrush, QPainterPath)


class GradientTitle(QWidget):
    def __init__(self, text: str = "COMMAND CENTRE PRO",
                 accent: str = "#00e87a", accent2: str = "#38bdf8",
                 parent=None):
        super().__init__(parent)
        self._text    = text
        self._accent  = accent
        self._accent2 = accent2
        self._t       = 0.0   # continuous time, never resets → no stutter
        self.setStyleSheet("background:transparent;")
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

        self._font = QFont("Segoe UI Variable Text", 10, QFont.Weight.ExtraBold)
        self._font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 3.0)
        self._font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias |
            QFont.StyleStrategy.NoSubpixelAntialias)

        fm = QFontMetrics(self._font)
        self.setMinimumSize(fm.horizontalAdvance(text) + 24, fm.height() + 6)
        self.setMaximumHeight(fm.height() + 8)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(20)   # 50fps — smooth

    def set_accent(self, accent: str, accent2: str = ""):
        self._accent  = accent
        self._accent2 = accent2 if accent2 else accent
        self.update()

    def _tick(self):
        self._t += 0.008   # never resets — smooth infinite loop
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        c1   = QColor(self._accent)
        c2   = QColor(self._accent2)

        # Smooth continuous sweep using sin — no jump at loop boundary
        # offset moves 0→w→0→w... infinitely without ever resetting
        offset = (math.sin(self._t) + 1) / 2  # 0→1→0→1 smoothly
        shift  = offset * w * 1.5 - w * 0.25

        grad = QLinearGradient(shift, 0, shift + w * 1.2, 0)
        grad.setColorAt(0.00, c1)
        grad.setColorAt(0.35, QColor(c1.red(), c1.green(), c1.blue(), 160))
        grad.setColorAt(0.50, QColor(255, 255, 255, 230))  # bright centre
        grad.setColorAt(0.65, QColor(c2.red(), c2.green(), c2.blue(), 160))
        grad.setColorAt(1.00, c2)

        fm   = QFontMetrics(self._font)
        path = QPainterPath()
        path.addText(4, h - fm.descent() - 1, self._font, self._text)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(path, QBrush(grad))
