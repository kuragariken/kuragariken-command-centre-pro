"""
copy_burst.py — Animated copy feedback.
A ripple + particle burst that plays on the button that was just clicked.
Uses QPainter + QTimer at 60fps. No external dependencies.
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath
import random, math


class Particle:
    def __init__(self, x, y, color):
        angle   = random.uniform(0, math.tau)
        speed   = random.uniform(2, 6)
        self.x  = x
        self.y  = y
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.life   = 1.0
        self.decay  = random.uniform(0.04, 0.09)
        self.radius = random.uniform(2, 5)
        self.color  = color

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.vy   += 0.15          # gravity
        self.vx   *= 0.95          # drag
        self.life -= self.decay
        return self.life > 0


class CopyBurst(QWidget):
    """
    Transparent overlay that sits over the entire commands panel.
    Shows a ripple + particles at the position of the copied button.
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        self._particles  = []
        self._ripples    = []   # (cx, cy, radius, max_r, alpha, color)
        self._tick_timer = QTimer(self)
        self._tick_timer.timeout.connect(self._tick)
        self._active     = False

    def fire(self, widget_pos_in_parent, accent="#00e87a"):
        """
        widget_pos_in_parent: QPoint of the centre of the clicked button
                               in this overlay's coordinate space.
        """
        cx = widget_pos_in_parent.x()
        cy = widget_pos_in_parent.y()
        c  = QColor(accent)

        # Particles
        for _ in range(22):
            self._particles.append(Particle(cx, cy, c))

        # Ripple ring
        self._ripples.append([cx, cy, 4, 60, 1.0, c])

        if not self._active:
            self._active = True
            self._tick_timer.start(16)   # 60fps

        self.resize(self.parent().size())
        self.raise_()
        self.show()

    def _tick(self):
        self._particles = [p for p in self._particles if p.update()]
        new_ripples = []
        for r in self._ripples:
            r[2] += 3.5        # grow radius
            r[4] -= 0.055      # fade alpha
            if r[4] > 0:
                new_ripples.append(r)
        self._ripples = new_ripples

        if not self._particles and not self._ripples:
            self._tick_timer.stop()
            self._active = False
            self.hide()
        else:
            self.update()

    def paintEvent(self, event):
        if not (self._particles or self._ripples):
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ripple rings
        for cx, cy, r, max_r, alpha, color in self._ripples:
            from PyQt6.QtGui import QPen
            ring_c = QColor(color)
            ring_c.setAlphaF(min(1.0, alpha * 0.8))
            p.setPen(QPen(ring_c, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QRectF(cx - r, cy - r, r * 2, r * 2))

        # Particles
        p.setPen(Qt.PenStyle.NoPen)
        for pt in self._particles:
            c = QColor(pt.color)
            c.setAlphaF(min(1.0, pt.life))
            p.setBrush(c)
            p.drawEllipse(QRectF(pt.x - pt.radius/2,
                                 pt.y - pt.radius/2,
                                 pt.radius, pt.radius))
