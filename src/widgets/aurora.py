"""
aurora.py — NUCLEAR BEAUTY BACKGROUND.

8 simultaneous render layers at 36fps:
  1. Deep space gradient (radial, not linear — more depth)
  2. Dot grid that pulses with the accent colour
  3. 50+ twinkling stars with individual phase offsets
  4. 3 massive aurora orbs drifting sinusoidally
  5. 2 fast reactive pulse orbs
  6. Radial corner vignettes (accent top-left, blue bottom-right)
  7. Animated breathing border glow with outer halo
  8. CRT scanline texture (every 4px)
"""
import math, random
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore    import Qt, QTimer, QRectF, QPointF
from PyQt6.QtGui     import (QPainter, QColor, QRadialGradient,
                              QLinearGradient, QBrush, QPen, QPainterPath)


class Star:
    __slots__ = ("x","y","r","phase","speed","base_a")
    def __init__(self, w, h):
        self.x       = random.uniform(0, w)
        self.y       = random.uniform(0, h)
        self.r       = random.uniform(0.4, 1.6)
        self.phase   = random.uniform(0, math.tau)
        self.speed   = random.uniform(0.3, 2.2)
        self.base_a  = random.uniform(0.25, 1.0)

    def alpha(self, t):
        v = self.base_a * (0.45 + 0.55 * math.sin(self.speed * t + self.phase))
        return max(0, min(255, int(v * 180)))


class AuroraBackground(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")
        self._t       = 0.0
        self._breath  = 0.0
        self._bdir    = 1
        self._pal     = {}
        self._stars   = []
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(28)   # ~36 fps

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # Stars removed — nothing to regenerate on resize.

    def set_palette(self, p):
        self._pal = p; self.update()

    def _tick(self):
        self._t      += 0.005
        self._breath += 0.016 * self._bdir
        if self._breath >= 1: self._bdir = -1
        if self._breath <= 0: self._bdir =  1
        self.update()

    # ─────────────────────────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w < 4 or h < 4: return
        t  = self._t
        pl = self._pal

        accent = QColor(pl.get("accent","#00e87a"))
        blue   = QColor(pl.get("blue",  "#38bdf8"))
        purple = QColor(pl.get("purple","#a78bfa"))
        bg     = QColor(pl.get("bg",    "#050810"))

        # ── Layer 1 — Deep radial space base ──────────────────
        base = QRadialGradient(QPointF(w*0.35, h*0.4), max(w,h)*0.9)
        c0   = QColor(bg); c0.setAlpha(255)
        c1   = QColor(bg)
        # slight blue tint at edges
        c1.setBlue(min(255, c1.blue() + 18)); c1.setAlpha(255)
        base.setColorAt(0.0, c0)
        base.setColorAt(1.0, c1)
        p.fillRect(0, 0, w, h, QBrush(base))

        # ── Layer 2 — Dot grid: REMOVED (patterned texture read as busy) ──

        # ── Layer 3 — Star field: REMOVED (visual noise over content) ──

        # ── Layer 4 — 3 large aurora orbs (softened, larger, slower) ──
        orbs4 = [
            (0.12 + 0.08*math.sin(t*0.40),
             0.38 + 0.10*math.cos(t*0.28),  0.72, accent, 16),
            (0.80 + 0.06*math.cos(t*0.52),
             0.62 + 0.09*math.sin(t*0.34),  0.64, blue,   12),
            (0.46 + 0.09*math.sin(t*0.24+1.1),
             0.05 + 0.06*math.cos(t*0.45),  0.54, purple,  9),
        ]
        self._orbs(p, w, h, orbs4)

        # ── Layer 5 — 2 reactive pulse orbs (softened) ───────
        pa = int(6 + 4 * math.sin(t * 1.0))
        orbs5 = [
            (0.68 + 0.05*math.sin(t*0.80),
             0.22 + 0.05*math.cos(t*0.66), 0.26, accent, max(0, pa)),
            (0.20 + 0.05*math.cos(t*0.58),
             0.80 + 0.05*math.sin(t*0.86), 0.22, blue,   max(0, pa-2)),
        ]
        self._orbs(p, w, h, orbs5)

        # ── Layer 6 — Corner vignettes (softened) ────────────
        for (cx2, cy2, rad_f, col2, al2) in [
            (0,   0,   0.50, accent, 14),   # top-left accent
            (w,   h,   0.55, blue,   10),   # bottom-right blue
            (w,   0,   0.30, purple,  6),   # top-right purple
        ]:
            rg = QRadialGradient(QPointF(cx2, cy2), rad_f * max(w, h))
            ci = QColor(col2); ci.setAlpha(max(0, min(255, al2)))
            rg.setColorAt(0, ci)
            rg.setColorAt(1, QColor(0,0,0,0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rg))
            p.drawRect(0, 0, w, h)

        # ── Layer 7 — Breathing border glow (whisper) ────────
        ba     = int(6 + 10 * self._breath)
        bpath  = QPainterPath()
        bpath.addRoundedRect(QRectF(1, 1, w-2, h-2), 10, 10)
        bc = QColor(accent); bc.setAlpha(ba)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(bc, 1.0)); p.drawPath(bpath)
        # Outer soft halo
        hc = QColor(accent); hc.setAlpha(max(0, int(ba * 0.25)))
        p.setPen(QPen(hc, 4)); p.drawPath(bpath)

        # ── Layer 8 — Scanlines: REMOVED (screen-door texture over cards) ──

    def _orbs(self, p, w, h, orbs):
        p.setPen(Qt.PenStyle.NoPen)
        for xf, yf, rf, col, alpha in orbs:
            alpha = max(0, min(255, int(alpha)))  # CLAMP — never let Qt see negatives
            cx = xf * w; cy = yf * h; r = rf * min(w, h)
            g  = QRadialGradient(QPointF(cx, cy), r)
            ci = QColor(col); ci.setAlpha(alpha)
            cm = QColor(col); cm.setAlpha(max(0, int(alpha * 0.45)))
            cq = QColor(col); cq.setAlpha(max(0, int(alpha * 0.15)))
            # softer, more gradual falloff → diffuse glow, not a hard blob
            g.setColorAt(0.00, ci)
            g.setColorAt(0.35, cm)
            g.setColorAt(0.65, cq)
            g.setColorAt(1.00, QColor(0,0,0,0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))


# ── Surprise 1: CornerChrome ──────────────────────────────────────
# Glowing corner accent shapes painted on title bar edges
# Already part of AuroraBackground corner vignettes above
# ── Surprise 2: Constellation dots added to star field in Aurora
# Already done via twinkling stars above


