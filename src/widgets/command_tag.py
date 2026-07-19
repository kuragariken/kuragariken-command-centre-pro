"""
command_tag.py — a deliberately different silhouette for command buttons
than HoverCard's card+icon design: a solid colour "cap" fused to a compact
pill, real depth via layered shadow + inset top highlight, and press physics
(a quick visual compress on click) rather than an instant flat state change.

Kept as its OWN widget rather than modifying HoverCard, since HoverCard is
shared with the Upgrade Tracker and bento_card.py — this only replaces the
button used in the main Commands grid.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QPen


class CommandTag(QPushButton):
    def __init__(self, text: str, accent: str = "#00e87a",
                 bg: str = "#0f1620", border: str = "#1a2840",
                 priority_color: str = "", accent2: str = "", parent=None):
        super().__init__(text, parent)
        self._accent_col   = QColor(accent)
        self._bg_col       = QColor(bg)
        self._border_col   = QColor(border)
        self._priority_col = QColor(priority_color) if priority_color else None
        self._hover   = False
        self._pressed = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)

    def set_colours(self, accent: str, bg: str, border: str, text: str, accent2: str = ""):
        """Kept for API parity with HoverCard so a theme switch can update
        every command tag the same way it updates HoverCards elsewhere."""
        self._accent_col = QColor(accent)
        self._bg_col     = QColor(bg)
        self._border_col = QColor(border)
        self.update()

    def enterEvent(self, e):
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover = False
        self._pressed = False
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

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()

        # Press = a small inset, simulating a physical compress rather than
        # an instant flat colour swap.
        inset = 2 if self._pressed else 0
        rect = QRectF(r.x() + inset, r.y() + inset,
                       r.width() - inset * 2, r.height() - inset * 2)
        radius = min(10.0, rect.height() * 0.32)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)

        bg = QColor(self._bg_col)
        if self._hover:
            bg = bg.lighter(114)
        p.fillPath(path, bg)

        border_col = self._accent_col if self._hover else self._border_col
        pen_w = 1.4 if self._hover else 1.0
        p.setPen(QPen(border_col, pen_w))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # Inset top highlight for depth — a raised surface, not a flat tile.
        hl = QColor(255, 255, 255)
        hl.setAlpha(30 if self._hover else 16)
        p.setPen(QPen(hl, 1))
        p.drawLine(int(rect.left() + radius * 0.7), int(rect.top() + 1.5),
                   int(rect.right() - radius * 0.7), int(rect.top() + 1.5))

        # The cap — a solid colour block fused to the left edge, rounded to
        # match the pill's own corners. This is the button's identity mark;
        # replaces a floating dot with real structural weight.
        cap_w = max(6.0, rect.height() * 0.18)
        cap_path = QPainterPath()
        cap_full = QRectF(rect.left(), rect.top(), cap_w + radius, rect.height())
        cap_path.addRoundedRect(cap_full, radius, radius)
        clip = QPainterPath()
        clip.addRect(QRectF(rect.left(), rect.top(), cap_w, rect.height()))
        cap_path = cap_path.intersected(clip)
        p.fillPath(cap_path, self._accent_col)

        # Priority ring, kept for feature parity with HoverCard's priority
        # marking — a thin outline in the priority colour, subtle.
        if self._priority_col:
            p.setPen(QPen(self._priority_col, 1.3))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)

        # Label
        text_col = QColor("#ffffff") if self._hover else QColor("#dce6ee")
        p.setPen(text_col)
        p.setFont(self.font())
        text_rect = QRectF(rect.left() + cap_w + 12, rect.top(),
                            rect.width() - cap_w - 22, rect.height())
        p.drawText(text_rect,
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   self.text())
