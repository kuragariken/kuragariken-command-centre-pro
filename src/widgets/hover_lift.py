"""
hover_lift.py — Premium hover-lift micro-interaction.

Qt stylesheets can't animate on :hover (no CSS transitions), so a card
that should "rise toward you" when hovered needs a QPropertyAnimation
driving a drop shadow.

IMPORTANT — why the shadow is created on hover, not at rest:
    A persistent QGraphicsDropShadowEffect on a child widget gets its
    cached pixmap invalidated when the parent window re-polishes its
    stylesheet (which happens on every theme change). That invalidation
    can leave the widget — and sometimes the whole window — rendered
    blank until the next manual repaint. To avoid that entirely, this
    helper attaches the shadow only while the pointer is over the widget
    and removes it on leave. At rest the widget has NO graphics effect,
    so theme switches never touch a cached effect pixmap.

Usage:
    from src.widgets.hover_lift import add_hover_lift
    add_hover_lift(my_card, lift=3)

No-op if lift <= 0 (reduced-motion friendly).
"""
from PyQt6.QtWidgets import QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import QObject, QEvent, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor


class _HoverLift(QObject):
    """Event filter that adds an animated shadow only while hovered."""

    def __init__(self, widget: QWidget, lift: int, shadow_color: str):
        super().__init__(widget)
        self._w = widget
        self._lift = lift
        self._shadow_color = shadow_color
        self._eff = None
        self._anim = None
        widget.installEventFilter(self)

    @pyqtProperty(float)
    def blur(self):
        return self._eff.blurRadius() if self._eff else 0.0

    @blur.setter
    def blur(self, v):
        if self._eff:
            self._eff.setBlurRadius(v)

    def _on_enter(self):
        # Create a fresh shadow effect for this hover only.
        eff = QGraphicsDropShadowEffect(self._w)
        eff.setBlurRadius(6)
        eff.setXOffset(0)
        eff.setYOffset(self._lift)
        c = QColor(self._shadow_color); c.setAlpha(120)
        eff.setColor(c)
        self._w.setGraphicsEffect(eff)
        self._eff = eff

        anim = QPropertyAnimation(self, b"blur")
        anim.setDuration(140)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(6)
        anim.setEndValue(24)
        anim.start()
        self._anim = anim

    def _on_leave(self):
        # Remove the effect entirely so nothing persists to blank on
        # a later stylesheet re-polish.
        if self._anim:
            self._anim.stop()
            self._anim = None
        self._w.setGraphicsEffect(None)
        self._eff = None

    def eventFilter(self, obj, event):
        t = event.type()
        if t == QEvent.Type.Enter:
            self._on_enter()
        elif t == QEvent.Type.Leave:
            self._on_leave()
        return False


def add_hover_lift(widget: QWidget, lift: int = 3, shadow_color: str = "#000000"):
    """
    Make `widget` deepen a soft shadow on hover. No-op if lift<=0.
    Returns the controller (kept alive as a child of the widget).
    The widget carries NO graphics effect at rest — safe across theme
    switches (which re-polish stylesheets and would otherwise blank a
    persistent effect's cached pixmap).
    """
    if lift <= 0:
        return None
    return _HoverLift(widget, lift, shadow_color)

