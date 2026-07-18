"""
accent_line.py — Premium dual-colour accent shimmer line.

Three simultaneous layers:
  1. Base glow at 55% alpha
  2. Slow wide aurora sweep — accent → accent2 cross-fade
  3. Fast bright shimmer pulse in accent colour

The slow sweep makes the bar constantly shift between the two theme
colours (e.g. Blood Moon: red → gold, Cyberpunk: magenta → cyan).
"""
import math
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (QPainter, QColor, QLinearGradient,
                              QRadialGradient, QBrush)


class AccentLine(QWidget):
    def __init__(self, parent=None, accent: str = "#00e87a"):
        super().__init__(parent)
        self.setFixedHeight(3)
        self._accent  = accent
        self._accent2 = accent
        self._phase1  = 0.0   # fast shimmer
        self._phase2  = 0.0   # slow aurora sweep
        self._phase3  = 0.0   # colour cross-fade between accent and accent2
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(20)   # 50fps — smooth enough, light CPU

    def set_accent(self, accent: str, accent2: str = ""):
        self._accent  = accent
        self._accent2 = accent2 if accent2 else accent
        self.update()

    def _tick(self):
        self._phase1 = (self._phase1 + 0.008) % 1.0   # shimmer
        self._phase2 = (self._phase2 + 0.005) % 1.0   # slow aurora
        self._phase3 = (self._phase3 + 0.003) % 1.0   # colour fade
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        c1   = QColor(self._accent)
        c2   = QColor(self._accent2)

        # ── Layer 1: base glow — colour cross-fade ────────────
        t    = (math.sin(self._phase3 * math.tau) + 1) / 2
        base = QColor(
            int(c1.red()   * (1-t) + c2.red()   * t),
            int(c1.green() * (1-t) + c2.green() * t),
            int(c1.blue()  * (1-t) + c2.blue()  * t),
            70
        )
        p.fillRect(0, 0, w, h, base)

        # ── Layer 1b: Liquid Glass lensing — white peak ───────
        # Simulates light concentrating through curved glass
        lens_x = int((math.sin(self._phase2 * math.tau * 0.7) + 1) / 2 * w)
        lens_g = QLinearGradient(lens_x - 40, 0, lens_x + 40, 0)
        lens_g.setColorAt(0.0, QColor(255,255,255,0))
        lens_g.setColorAt(0.5, QColor(255,255,255,90))
        lens_g.setColorAt(1.0, QColor(255,255,255,0))
        p.fillRect(max(0, lens_x-40), 0, 80, h, QBrush(lens_g))

        # ── Layer 2: slow wide aurora sweep (accent → accent2) ─
        aw = int(w * 0.65)
        ax = int(self._phase2 * (w + aw)) - aw
        ag = QLinearGradient(ax, 0, ax + aw, 0)
        a0 = QColor(c1); a0.setAlpha(0)
        am = QColor(c2); am.setAlpha(130)
        ae = QColor(c1); ae.setAlpha(0)
        ag.setColorAt(0.0,  a0)
        ag.setColorAt(0.35, QColor(c1.red(), c1.green(), c1.blue(), 90))
        ag.setColorAt(0.65, am)
        ag.setColorAt(1.0,  ae)
        p.fillRect(ax, 0, aw, h, QBrush(ag))

        # ── Layer 3: fast bright shimmer ──────────────────────
        sw = int(w * 0.35)
        sx = int(self._phase1 * (w + sw)) - sw
        sg = QLinearGradient(sx, 0, sx + sw, 0)
        s0 = QColor(c1); s0.setAlpha(0)
        sm = QColor(c1); sm.setAlpha(255)
        sg.setColorAt(0.0,  s0)
        sg.setColorAt(0.40, sm)
        sg.setColorAt(0.60, sm)
        sg.setColorAt(1.0,  s0)
        p.fillRect(sx, 0, sw, h, QBrush(sg))
