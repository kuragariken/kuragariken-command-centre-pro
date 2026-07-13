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
        w, h = self.width(), self.height()
        if w > 10 and h > 10:
            n = max(55, w * h // 900)
            self._stars = [Star(w, h) for _ in range(n)]

    def set_palette(self, p):
        self._pal = p; self.update()

    def _tick(self):
        self._t      += 0.008
        self._breath += 0.022 * self._bdir
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

        # ── Layer 2 — Dot grid (pulses with accent) ───────────
        pulse_a = int(8 + 6 * math.sin(t * 0.9))
        gc      = QColor(accent); gc.setAlpha(pulse_a)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(gc))
        step = 22
        for gx in range(0, w + step, step):
            for gy in range(0, h + step, step):
                p.drawEllipse(QRectF(gx-0.8, gy-0.8, 1.6, 1.6))

        # ── Layer 3 — Star field ───────────────────────────────
        for s in self._stars:
            a = s.alpha(t)
            if a < 6: continue
            sc = QColor(255, 255, 255, a)
            p.setBrush(QBrush(sc))
            p.drawEllipse(QRectF(s.x-s.r, s.y-s.r, s.r*2, s.r*2))

        # ── Layer 4 — 3 large aurora orbs ────────────────────
        orbs4 = [
            (0.12 + 0.10*math.sin(t*0.52),
             0.38 + 0.13*math.cos(t*0.35),  0.56, accent, 32),
            (0.80 + 0.08*math.cos(t*0.68),
             0.62 + 0.11*math.sin(t*0.43),  0.48, blue,   22),
            (0.46 + 0.12*math.sin(t*0.30+1.1),
             0.05 + 0.08*math.cos(t*0.59),  0.40, purple, 18),
        ]
        self._orbs(p, w, h, orbs4)

        # ── Layer 5 — 2 reactive pulse orbs ──────────────────
        pa = int(12 + 9 * math.sin(t * 1.4))
        orbs5 = [
            (0.68 + 0.06*math.sin(t*1.05),
             0.22 + 0.07*math.cos(t*0.88), 0.20, accent, max(0, pa)),
            (0.20 + 0.07*math.cos(t*0.77),
             0.80 + 0.06*math.sin(t*1.15), 0.16, blue,   max(0, pa-5)),
        ]
        self._orbs(p, w, h, orbs5)

        # ── Layer 6 — Corner vignettes ───────────────────────
        for (cx2, cy2, rad_f, col2, al2) in [
            (0,   0,   0.45, accent, 24),   # top-left accent
            (w,   h,   0.50, blue,   17),   # bottom-right blue
            (w,   0,   0.28, purple, 10),   # top-right purple
        ]:
            rg = QRadialGradient(QPointF(cx2, cy2), rad_f * max(w, h))
            ci = QColor(col2); ci.setAlpha(max(0, min(255, al2)))
            rg.setColorAt(0, ci)
            rg.setColorAt(1, QColor(0,0,0,0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(rg))
            p.drawRect(0, 0, w, h)

        # ── Layer 7 — Breathing border glow ──────────────────
        ba     = int(20 + 28 * self._breath)
        bpath  = QPainterPath()
        bpath.addRoundedRect(QRectF(1, 1, w-2, h-2), 10, 10)
        bc = QColor(accent); bc.setAlpha(ba)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(bc, 1.5)); p.drawPath(bpath)
        # Outer soft halo
        hc = QColor(accent); hc.setAlpha(max(0, int(ba * 0.35)))
        p.setPen(QPen(hc, 5)); p.drawPath(bpath)
        # Inner even softer glow
        ic = QColor(accent); ic.setAlpha(max(0, int(ba * 0.12)))
        p.setPen(QPen(ic, 10)); p.drawPath(bpath)

        # ── Layer 8 — Scanlines (CRT micro-texture) ──────────
        sc2 = QColor(0, 0, 0, 22)
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(QBrush(sc2))
        for sy in range(0, h, 4):
            p.drawRect(QRectF(0, sy, w, 1.5))

    def _orbs(self, p, w, h, orbs):
        p.setPen(Qt.PenStyle.NoPen)
        for xf, yf, rf, col, alpha in orbs:
            alpha = max(0, min(255, int(alpha)))  # CLAMP — never let Qt see negatives
            cx = xf * w; cy = yf * h; r = rf * min(w, h)
            g  = QRadialGradient(QPointF(cx, cy), r)
            ci = QColor(col); ci.setAlpha(alpha)
            cm = QColor(col); cm.setAlpha(max(0, alpha//3))
            g.setColorAt(0.00, ci)
            g.setColorAt(0.50, cm)
            g.setColorAt(1.00, QColor(0,0,0,0))
            p.setBrush(QBrush(g))
            p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))


# ── Surprise 1: CornerChrome ──────────────────────────────────────
# Glowing corner accent shapes painted on title bar edges
# Already part of AuroraBackground corner vignettes above
# ── Surprise 2: Constellation dots added to star field in Aurora
# Already done via twinkling stars above


