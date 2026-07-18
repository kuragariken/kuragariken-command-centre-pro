"""
particle_trail.py — Subtle cursor sparkle trail inside the main window.
Tiny accent-coloured particles bloom where you click and fade out.
60fps, transparent overlay, mouse-passthrough for everything else.
"""
import math, random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QBrush


class Spark:
    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 4.5)
        self.x    = x
        self.y    = y
        self.vx   = math.cos(angle) * speed
        self.vy   = math.sin(angle) * speed - 1.5   # slight upward bias
        self.life = 1.0
        self.decay= random.uniform(0.05, 0.12)
        self.r    = random.uniform(1.5, 3.5)
        self.col  = color

    def tick(self):
        self.x    += self.vx
        self.y    += self.vy
        self.vy   += 0.12     # gravity
        self.vx   *= 0.94     # air drag
        self.life -= self.decay
        return self.life > 0


class ParticleTrail(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")
        self._sparks  = []
        self._accent  = "#00e87a"
        self._timer   = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._active  = False

    def set_accent(self, color: str):
        self._accent = color

    def burst(self, pos: QPointF, count: int = 14):
        col = QColor(self._accent)
        for _ in range(count):
            self._sparks.append(Spark(pos.x(), pos.y(), col))
        if not self._active:
            self._active = True
            self._timer.start(16)
        self.resize(self.parent().size())
        self.raise_()
        self.show()

    def _tick(self):
        self._sparks = [s for s in self._sparks if s.tick()]
        if not self._sparks:
            self._timer.stop()
            self._active = False
            self.hide()
        else:
            self.update()

    def paintEvent(self, event):
        if not self._sparks:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for s in self._sparks:
            c = QColor(s.col)
            c.setAlphaF(min(1.0, s.life))
            p.setBrush(QBrush(c))
            p.drawEllipse(QRectF(s.x - s.r/2, s.y - s.r/2, s.r, s.r))
