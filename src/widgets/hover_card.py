"""
hover_card.py — Premium command button.
- Auto-scaling text so long labels are always fully visible and centred
- Animated glow border on hover
- Shimmer sweep left→right on enter
- 2px micro press-down on click
- Priority colour as top accent edge
- NO tooltip (removed per request)
"""
import math
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve,
                           pyqtProperty, QRectF, QPointF)
from PyQt6.QtGui import (QPainter, QColor, QLinearGradient, QBrush,
                          QPen, QPainterPath, QFont, QFontMetrics)


class HoverCard(QPushButton):
    def __init__(self, text: str, accent: str = "#00e87a",
                 bg: str = "#0f1620", border: str = "#1a2840",
                 priority_color: str = "", accent2: str = "", parent=None):
        super().__init__(text, parent)
        self._accent_col   = QColor(accent)
        self._accent2_col  = QColor(accent2) if accent2 else None
        self._bg_col       = QColor(bg)
        self._border_col   = QColor(border)
        self._priority_col = QColor(priority_color) if priority_color else None
        self._text_col     = QColor("#c8d8e8")
        self._hover        = False
        self._pressed      = False
        self._shimmer_x    = -1.0
        self._glow_alpha   = 0

        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Disable system tooltip entirely
        self.setToolTip("")

        self._glow_anim = QPropertyAnimation(self, b"glow_alpha")
        self._glow_anim.setDuration(200)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)

    def sizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(80, self.minimumHeight())

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(40, self.minimumHeight())

    @pyqtProperty(int)
    def glow_alpha(self):
        return self._glow_alpha

    @glow_alpha.setter
    def glow_alpha(self, v):
        self._glow_alpha = v
        self.update()

    def set_colours(self, accent: str, bg: str, border: str, text: str, accent2: str = ""):
        self._accent_col  = QColor(accent)
        self._accent2_col = QColor(accent2) if accent2 else None
        self._bg_col      = QColor(bg)
        self._border_col  = QColor(border)
        self._text_col    = QColor(text)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_alpha)
        self._glow_anim.setEndValue(200)
        self._glow_anim.start()
        self._shimmer_x = 0.0
        self._shimmer_timer.start(14)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_alpha)
        self._glow_anim.setEndValue(0)
        self._glow_anim.start()
        self._shimmer_timer.stop()
        self._shimmer_x = -1.0
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed = True
        self.update()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(e)

    def _tick_shimmer(self):
        self._shimmer_x += 0.045
        if self._shimmer_x > 1.5:
            self._shimmer_timer.stop()
            self._shimmer_x = -1.0
        self.update()

    def _base_font(self, size: int) -> QFont:
        f = QFont("Segoe UI Variable Text", size, 500)
        # NoSubpixelAntialias: grayscale AA looks cleaner on dark backgrounds
        # RGB fringing (subpixel) causes coloured halos on dark UI
        f.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias |
            QFont.StyleStrategy.NoSubpixelAntialias)
        f.setHintingPreference(QFont.HintingPreference.PreferDefaultHinting)
        return f

    def _best_split(self, text: str):
        """Split `text` into two lines at the word-boundary that keeps
        both lines as balanced as possible. Returns None if there's only
        one word (nothing to split on)."""
        words = text.split(" ")
        if len(words) < 2:
            return None
        best = None
        best_diff = None
        for i in range(1, len(words)):
            line1 = " ".join(words[:i])
            line2 = " ".join(words[i:])
            diff = abs(len(line1) - len(line2))
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best = (line1, line2)
        return best

    def _fit_font(self, painter: QPainter, text: str, max_w: float, max_h: float):
        """Return (font, lines) — the largest single line, or failing that
        a balanced two-line wrap, that fits within max_w x max_h. Only
        falls back to eliding a single line if nothing else fits."""
        avail_w = max_w - 10

        # Pass 1: single line, largest size that fits
        for size in range(10, 7, -1):
            f = self._base_font(size)
            fm = QFontMetrics(f)
            if fm.horizontalAdvance(text) <= avail_w:
                return f, [text]

        # Pass 2: balanced two-line wrap, largest size that fits both
        # lines' width and the pair's total height within max_h
        split = self._best_split(text)
        if split:
            for size in range(10, 7, -1):
                f = self._base_font(size)
                fm = QFontMetrics(f)
                line_h = fm.height()
                if (fm.horizontalAdvance(split[0]) <= avail_w and
                        fm.horizontalAdvance(split[1]) <= avail_w and
                        line_h * 2 <= max_h - 4):
                    return f, list(split)

        # Fallback: smallest single line, elided
        f = self._base_font(7)
        return f, [text]

    def paintEvent(self, event):
        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        r    = 10
        off  = 2 if self._pressed else 0

        # ── Background ────────────────────────────────────────
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, off, w, h - off), r, r)

        if self._hover:
            bg = self._bg_col
            ac = self._accent_col
            a2 = self._accent2_col if self._accent2_col else ac

            # Layer 1: Glass base with accent colour wash
            gl = QLinearGradient(0, off, w, h)
            b1 = QColor(min(255,bg.red()+22), min(255,bg.green()+22), min(255,bg.blue()+32))
            gl.setColorAt(0, b1); gl.setColorAt(1, bg)
            p.fillPath(path, QBrush(gl))

            # Layer 2: Diagonal accent refraction
            rg = QLinearGradient(0, off, w, h)
            rc1 = QColor(ac); rc1.setAlpha(40)
            rc2 = QColor(a2); rc2.setAlpha(22)
            rg.setColorAt(0, rc1); rg.setColorAt(1, rc2)
            p.fillPath(path, QBrush(rg))

            # Layer 3: Specular top edge — intense on hover
            sg = QLinearGradient(0, off, 0, off + h*0.15)
            sg.setColorAt(0, QColor(255,255,255,55))
            sg.setColorAt(1, QColor(255,255,255,0))
            p.fillPath(path, QBrush(sg))

            # Layer 4: Bottom accent glow
            bg2 = QLinearGradient(0, h*0.75, 0, h)
            bc = QColor(ac); bc.setAlpha(30)
            bg2.setColorAt(0, QColor(0,0,0,0)); bg2.setColorAt(1, bc)
            p.fillPath(path, QBrush(bg2))
        else:
            # Idle: Liquid Glass — layered glass material
            bg = self._bg_col

            # Layer 1: dark base
            p.fillPath(path, QBrush(bg))

            # Layer 2: specular top edge (light hitting top of glass)
            spec_grad = QLinearGradient(0, off, 0, off + h * 0.18)
            spec_top = QColor(255, 255, 255, 16)
            spec_mid = QColor(255, 255, 255, 6)
            spec_bot = QColor(255, 255, 255, 0)
            spec_grad.setColorAt(0.0, spec_top)
            spec_grad.setColorAt(0.5, spec_mid)
            spec_grad.setColorAt(1.0, spec_bot)
            p.fillPath(path, QBrush(spec_grad))

            # Layer 3: very subtle accent refraction tint at bottom
            tint = QColor(self._accent_col)
            tint.setAlpha(6)
            bot_grad = QLinearGradient(0, h * 0.7, 0, h)
            bot_grad.setColorAt(0, QColor(0,0,0,0))
            bot_grad.setColorAt(1, tint)
            p.fillPath(path, QBrush(bot_grad))

        # ── Priority top-edge accent line ─────────────────────
        if self._priority_col:
            top = QPainterPath()
            top.addRoundedRect(QRectF(0, off, w, 2), 1, 1)
            p.fillPath(top, QBrush(self._priority_col))

        # ── Border / glow ────────────────────────────────────
        if self._glow_alpha > 0:
            # Inner glow border
            gc = QColor(self._accent_col); gc.setAlpha(self._glow_alpha)
            p.setPen(QPen(gc, 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.6, off+0.6, w-1.2, h-off-1.2), r, r)
            # Outer soft halos
            for i, spread in enumerate([4, 8]):
                hc = QColor(self._accent_col)
                hc.setAlpha(int(self._glow_alpha * (0.12 - i*0.05)))
                p.setPen(QPen(hc, spread))
                p.drawRoundedRect(
                    QRectF(spread/2, off+spread/2, w-spread, h-off-spread), r, r)
        else:
            p.setPen(QPen(self._border_col, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.5, off+0.5, w-1, h-off-1), r, r)

        # ── Shimmer sweep ─────────────────────────────────────
        if self._shimmer_x >= 0:
            sx = self._shimmer_x * (w + 80) - 40
            sg = QLinearGradient(sx-40, 0, sx+40, 0)
            sg.setColorAt(0.0, QColor(255,255,255,0))
            sg.setColorAt(0.4, QColor(255,255,255,36))
            sg.setColorAt(0.6, QColor(255,255,255,36))
            sg.setColorAt(1.0, QColor(255,255,255,0))
            p.setClipPath(path)
            p.fillRect(QRectF(sx-40, off, 80, h), QBrush(sg))
            p.setClipping(False)

        # ── Auto-fit text — always centred, always visible ───
        label = self.text()
        pad   = 8   # horizontal padding each side
        max_w = w - pad * 2
        font, lines = self._fit_font(p, label, max_w, h - off)
        if self._hover:
            font.setWeight(700)
        p.setFont(font)

        text_col = QColor(self._accent_col) if self._hover else self._text_col
        p.setPen(text_col)

        fm = QFontMetrics(font)
        if len(lines) == 1:
            line = lines[0]
            # Absolute last-resort elide, only if even the smallest
            # single-line size still doesn't fit
            if fm.horizontalAdvance(line) > max_w:
                line = fm.elidedText(line, Qt.TextElideMode.ElideMiddle, int(max_w))
            p.drawText(QRectF(pad, off, max_w, h - off),
                       Qt.AlignmentFlag.AlignCenter, line)
        else:
            # Two balanced lines, stacked and vertically centred as a block
            line_h    = fm.height()
            block_h   = line_h * 2
            top       = off + (h - off - block_h) / 2
            p.drawText(QRectF(pad, top, max_w, line_h),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       lines[0])
            p.drawText(QRectF(pad, top + line_h, max_w, line_h),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                       lines[1])
