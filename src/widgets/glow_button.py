"""
glow_button.py — Animated glow button for premium feel.
On hover: accent-coloured outer glow pulses in.
Uses QPainter + QPropertyAnimation on a custom alpha property.
"""
import math
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPainterPath, QPen


class GlowButton(QPushButton):
    """
    Premium button with animated glow on hover.
    Gradient fill, rounded, accent glow ring.
    """
    def __init__(self, text: str, accent: str = "#00e87a",
                 bg: str = "#111827", parent=None):
        super().__init__(text, parent)
        self._accent    = QColor(accent)
        self._bg        = QColor(bg)
        self._glow_a    = 0   # glow alpha 0-255
        self._hover     = False

        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._anim = QPropertyAnimation(self, b"glow_alpha")
        self._anim.setDuration(200)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(int)
    def glow_alpha(self):
        return self._glow_a

    @glow_alpha.setter
    def glow_alpha(self, v):
        self._glow_a = v
        self.update()

    def set_accent(self, color: str):
        self._accent = QColor(color)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self._anim.stop()
        self._anim.setStartValue(self._glow_a)
        self._anim.setEndValue(120)
        self._anim.start()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._anim.stop()
        self._anim.setStartValue(self._glow_a)
        self._anim.setEndValue(0)
        self._anim.start()
        super().leaveEvent(e)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r    = 8

        # Glow halo (renders behind button)
        if self._glow_a > 0:
            for spread in range(6, 0, -1):
                halo = QColor(self._accent)
                halo.setAlpha(int(self._glow_a * spread / 6 * 0.35))
                p.setBrush(QBrush(halo))
                p.setPen(Qt.PenStyle.NoPen)
                s = spread * 2
                p.drawRoundedRect(
                    QRectF(-s, -s, w + s*2, h + s*2), r + spread, r + spread)

        # Background fill — gradient
        grad = QLinearGradient(0, 0, 0, h)
        if self._hover:
            c1 = QColor(self._accent); c1.setAlpha(220)
            c2 = QColor(self._accent); c2.setAlpha(180)
            grad.setColorAt(0, c1)
            grad.setColorAt(1, c2)
            text_col = QColor(self._bg)
        else:
            bg2 = QColor(self._bg.red() + 8, self._bg.green() + 8,
                         self._bg.blue() + 8)
            grad.setColorAt(0, bg2)
            grad.setColorAt(1, self._bg)
            text_col = QColor(self._accent)

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), r, r)
        p.fillPath(path, QBrush(grad))

        # Border
        border_c = QColor(self._accent)
        border_c.setAlpha(80 if not self._hover else 200)
        p.setPen(QPen(border_c, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(0.5, 0.5, w-1, h-1), r, r)

        # Text
        p.setPen(text_col)
        font = self.font()
        font.setWeight(700 if self._hover else 600)
        p.setFont(font)
        p.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter, self.text())
