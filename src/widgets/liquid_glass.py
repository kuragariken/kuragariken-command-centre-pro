"""
liquid_glass.py — Liquid Glass material widget.

Simulates iOS 26 Liquid Glass:
  - Multi-layer translucency with real depth
  - Specular caustic highlight (bright lensing peak)
  - Chromatic refraction tint (colour bleeding)
  - Breathing border glow
  - Dynamic shimmer that responds to a continuous phase
  - Used as the title bar background and nav dropdown
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (QPainter, QColor, QLinearGradient,
                              QRadialGradient, QBrush, QPen,
                              QPainterPath, QConicalGradient)


class LiquidGlassBar(QWidget):
    """
    Horizontal glass bar — used for title bar.
    Renders 6 simultaneous glass layers at 45fps.
    """
    def __init__(self, parent=None, accent="#00e87a", accent2="#38bdf8",
                 height=46):
        super().__init__(parent)
        self.setFixedHeight(height)
        self._accent  = accent
        self._accent2 = accent2
        self._t       = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background:transparent;")
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(22)  # 45fps

    def set_accent(self, a: str, a2: str = ""):
        self._accent  = a
        self._accent2 = a2 if a2 else a
        self.update()

    def _tick(self):
        self._t += 0.007
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        c1   = QColor(self._accent)
        c2   = QColor(self._accent2)

        # ── Layer 1: Deep glass base ──────────────────────────
        base = QLinearGradient(0, 0, 0, h)
        base.setColorAt(0.00, QColor(14, 20, 34, 252))
        base.setColorAt(0.40, QColor(8,  13, 24, 248))
        base.setColorAt(1.00, QColor(5,  8,  16, 244))
        p.fillRect(0, 0, w, h, QBrush(base))

        # ── Layer 2: Chromatic refraction — accent colour bleed
        refract_x = (math.sin(self._t * 0.7) + 1) / 2 * w * 0.8 + w * 0.1
        rg = QRadialGradient(QPointF(refract_x, h * 0.5), w * 0.5)
        rc = QColor(c1); rc.setAlpha(28)
        rc2 = QColor(c2); rc2.setAlpha(14)
        rg.setColorAt(0.0, rc)
        rg.setColorAt(0.5, rc2)
        rg.setColorAt(1.0, QColor(0,0,0,0))
        p.fillRect(0, 0, w, h, QBrush(rg))

        # ── Layer 3: Top specular edge — sharp glass highlight ─
        spec = QLinearGradient(0, 0, 0, h * 0.08)
        spec.setColorAt(0.0, QColor(255, 255, 255, 55))
        spec.setColorAt(0.6, QColor(255, 255, 255, 18))
        spec.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(0, 0, w, int(h * 0.08) + 1, QBrush(spec))

        # ── Layer 4: Caustic lensing peak — moves like light ───
        # Simulates real glass lensing: concentrated bright spot
        lx   = (math.sin(self._t * 1.1) + 1) / 2 * w
        lw   = int(w * 0.28)
        lens = QLinearGradient(lx - lw//2, 0, lx + lw//2, 0)
        lens.setColorAt(0.00, QColor(255, 255, 255, 0))
        lens.setColorAt(0.35, QColor(255, 255, 255, 8))
        lens.setColorAt(0.50, QColor(255, 255, 255, 28))
        lens.setColorAt(0.65, QColor(255, 255, 255, 8))
        lens.setColorAt(1.00, QColor(255, 255, 255, 0))
        p.fillRect(max(0, int(lx)-lw//2), 0, lw, h, QBrush(lens))

        # ── Layer 5: Bottom inner glow — reflected floor light ─
        bot = QLinearGradient(0, h * 0.75, 0, h)
        bc  = QColor(c1); bc.setAlpha(12)
        bot.setColorAt(0.0, QColor(0,0,0,0))
        bot.setColorAt(1.0, bc)
        p.fillRect(0, int(h * 0.75), w, int(h * 0.25) + 1, QBrush(bot))

        # ── Layer 6: Top border — glass edge line ─────────────
        ec = QColor(255, 255, 255, 35)
        p.setPen(QPen(ec, 1))
        p.drawLine(0, 0, w, 0)

        # ── Layer 7: Bottom border ────────────────────────────
        bc2 = QColor(255, 255, 255, 8)
        p.setPen(QPen(bc2, 1))
        p.drawLine(0, h-1, w, h-1)
