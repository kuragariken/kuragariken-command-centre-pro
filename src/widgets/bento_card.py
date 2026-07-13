"""
bento_card.py — Premium bento-style command button.
Fixed square tiles with large label, priority dot, usage count badge.
Animated glow border on hover, same shimmer + press as HoverCard.
"""
import math
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QRectF
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath, QFont, QFontMetrics


class BentoCard(QPushButton):
    """
    Square bento tile — 100×80px default.
    Label is auto-sized. Priority shown as coloured corner dot.
    Usage count shown as small badge top-right.
    """
    def __init__(self, label: str, priority_color: str = "",
                 accent: str = "#00e87a", bg: str = "#0d1520",
                 border: str = "#172338", uses: int = 0, parent=None):
        super().__init__(label, parent)
        self._accent        = QColor(accent)
        self._bg            = QColor(bg)
        self._border        = QColor(border)
        self._priority_col  = QColor(priority_color) if priority_color else None
        self._text_col      = QColor("#c8d8e8")
        self._uses          = uses
        self._hover         = False
        self._pressed       = False
        self._shimmer_x     = -1.0
        self._glow_alpha    = 0

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(70, 52)

        self._glow_anim = QPropertyAnimation(self, b"glow_alpha")
        self._glow_anim.setDuration(200)
        self._glow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._shimmer_timer = QTimer(self)
        self._shimmer_timer.timeout.connect(self._tick_shimmer)

    @pyqtProperty(int)
    def glow_alpha(self): return self._glow_alpha

    @glow_alpha.setter
    def glow_alpha(self, v):
        self._glow_alpha = max(0, min(255, v)); self.update()

    def set_colours(self, accent, bg, border, text):
        self._accent = QColor(accent); self._bg = QColor(bg)
        self._border = QColor(border); self._text_col = QColor(text)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_alpha)
        self._glow_anim.setEndValue(210); self._glow_anim.start()
        self._shimmer_x = 0.0; self._shimmer_timer.start(14)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._glow_anim.stop()
        self._glow_anim.setStartValue(self._glow_alpha)
        self._glow_anim.setEndValue(0); self._glow_anim.start()
        self._shimmer_timer.stop(); self._shimmer_x = -1.0; self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        self._pressed = True; self.update(); super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._pressed = False; self.update(); super().mouseReleaseEvent(e)

    def _tick_shimmer(self):
        self._shimmer_x += 0.05
        if self._shimmer_x > 1.5: self._shimmer_timer.stop(); self._shimmer_x = -1.0
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        w, h = self.width(), self.height()
        r = 12
        off = 2 if self._pressed else 0

        path = QPainterPath()
        path.addRoundedRect(QRectF(0, off, w, h-off), r, r)

        # Background
        if self._hover:
            grad = QLinearGradient(0, 0, w, h)
            bg2 = QColor(self._bg)
            bg2.setRed(min(255, bg2.red()+18))
            bg2.setGreen(min(255, bg2.green()+18))
            bg2.setBlue(min(255, bg2.blue()+28))
            grad.setColorAt(0, bg2); grad.setColorAt(1, self._bg)
            p.fillPath(path, QBrush(grad))
        else:
            grad = QLinearGradient(0, 0, w, h)
            bg3 = QColor(self._bg)
            bg3.setRed(min(255, bg3.red()+8))
            bg3.setBlue(min(255, bg3.blue()+8))
            grad.setColorAt(0, bg3); grad.setColorAt(1, self._bg)
            p.fillPath(path, QBrush(grad))

        # Glow / border
        if self._glow_alpha > 0:
            gc = QColor(self._accent); gc.setAlpha(self._glow_alpha)
            p.setPen(QPen(gc, 1.2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.6, off+0.6, w-1.2, h-off-1.2), r, r)
            for sp in [4, 8]:
                hc = QColor(self._accent); hc.setAlpha(int(self._glow_alpha*0.1))
                p.setPen(QPen(hc, sp))
                p.drawRoundedRect(QRectF(sp/2, off+sp/2, w-sp, h-off-sp), r, r)
        else:
            p.setPen(QPen(self._border, 1)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(0.5, off+0.5, w-1, h-off-1), r, r)

        # Shimmer
        if self._shimmer_x >= 0:
            sx = self._shimmer_x*(w+80)-40
            sg = QLinearGradient(sx-40, 0, sx+40, 0)
            sg.setColorAt(0, QColor(255,255,255,0))
            sg.setColorAt(0.5, QColor(255,255,255,40))
            sg.setColorAt(1, QColor(255,255,255,0))
            p.setClipPath(path)
            p.fillRect(QRectF(sx-40, off, 80, h), QBrush(sg))
            p.setClipping(False)

        # Priority corner dot (top-left)
        if self._priority_col:
            dot_r = 5
            p.setBrush(QBrush(self._priority_col))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(8, off+8, dot_r*2, dot_r*2))

        # Label — auto-fit font, centred
        label = self.text()
        text_col = QColor(self._accent) if self._hover else self._text_col
        p.setPen(text_col)
        best_font = QFont("Inter", 10, 600 if self._hover else 500)
        for size in range(10, 6, -1):
            best_font.setPointSize(size)
            fm2 = QFontMetrics(best_font)
            if fm2.horizontalAdvance(label) <= w - 16:
                break
        p.setFont(best_font)
        p.drawText(QRectF(8, off, w-16, h-off),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, label)
