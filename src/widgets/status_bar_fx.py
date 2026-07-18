"""
status_bar_fx.py — Animated copy count ticker in the status bar.
When copies_today increments, the number ticks up with a flash effect.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QFont


class FlashLabel(QLabel):
    """Label that flashes accent colour briefly when value changes."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self._flash_alpha = 0
        self._accent = QColor("#00e87a")

    @pyqtProperty(int)
    def flash_alpha(self): return self._flash_alpha

    @flash_alpha.setter
    def flash_alpha(self, v):
        self._flash_alpha = max(0, min(255, v))
        self.update()

    def flash(self, accent: str = "#00e87a"):
        self._accent = QColor(accent)
        anim = QPropertyAnimation(self, b"flash_alpha")
        anim.setStartValue(180)
        anim.setEndValue(0)
        anim.setDuration(600)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._flash_anim = anim

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._flash_alpha > 0:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            c = QColor(self._accent)
            c.setAlpha(self._flash_alpha)
            p.fillRect(self.rect(), c)
