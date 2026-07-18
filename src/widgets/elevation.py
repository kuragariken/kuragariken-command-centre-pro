"""
elevation.py — Premium depth helpers.

Two things separate "flat dark UI" from "expensive dark UI": real soft
drop shadows under floating surfaces, and a faint light-catch on the top
edge of glass panels. Qt gives us both cheaply:

  • elevate(widget, level)  → attaches a soft QGraphicsDropShadowEffect.
        Levels 1–4 map to increasing blur/offset (cards → dialogs →
        popouts → the main window). Colours are pure black at low alpha,
        which reads as depth rather than a grey halo.

  • EdgeHighlight — a 1px gradient line you can drop at the top of any
        card so it looks like light grazing the bevel. Optional; use on
        hero surfaces (header cards, primary panels), not every widget.

Both are additive: they sit on top of the existing stylesheet without
changing any colours, so every theme keeps its identity.
"""
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QLinearGradient, QBrush


# blur radius, y-offset, alpha  — tuned so each level reads as one step up
_LEVELS = {
    1: (18,  4,  90),    # resting cards
    2: (28,  8, 110),    # dialogs / menus
    3: (40, 12, 130),    # floating popouts (Vault, Settings, Notepad)
    4: (60, 18, 150),    # the main window itself
}


def elevate(widget: QWidget, level: int = 1, color: str = "#000000"):
    """
    Attach a soft drop shadow to `widget`. Higher level = more lift.
    Returns the effect so callers can tweak or animate it later.

    Note: a widget can only hold one QGraphicsEffect at a time, so this
    replaces any existing effect on the widget.
    """
    blur, dy, alpha = _LEVELS.get(level, _LEVELS[1])
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setXOffset(0)
    eff.setYOffset(dy)
    c = QColor(color)
    c.setAlpha(alpha)
    eff.setColor(c)
    widget.setGraphicsEffect(eff)
    return eff


class EdgeHighlight(QWidget):
    """
    A 1px horizontal gradient — bright at the centre, fading to the sides —
    that mimics light catching the top bevel of a glass card. Place it as
    the first child at the very top of a card's layout, or position it
    manually at y=0.

    Fully transparent to mouse events, so it never interferes with clicks.
    """
    def __init__(self, accent: str = "#ffffff", parent=None):
        super().__init__(parent)
        self._accent = QColor(accent)
        self.setFixedHeight(1)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_accent(self, accent: str):
        self._accent = QColor(accent)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        grad = QLinearGradient(0, 0, w, 0)
        edge = QColor(self._accent); edge.setAlpha(0)
        mid  = QColor(self._accent); mid.setAlpha(60)
        grad.setColorAt(0.0, edge)
        grad.setColorAt(0.5, mid)
        grad.setColorAt(1.0, edge)
        p.fillRect(0, 0, w, 1, QBrush(grad))
