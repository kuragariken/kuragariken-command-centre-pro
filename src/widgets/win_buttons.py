"""
win_buttons.py — Custom painted window control buttons.
macOS-inspired coloured circles with hover reveal of symbol.
Uses QPainter + QPropertyAnimation for smooth hover effects.
"""
from PyQt6.QtWidgets import QPushButton
from PyQt6.QtCore import (Qt, QPropertyAnimation, QEasingCurve,
                           pyqtProperty, QRectF)
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QFont, QPen


class WinButton(QPushButton):
    """
    Coloured circle button that reveals its symbol on hover.
    Painted entirely with QPainter — no QSS, no black blocks.
    """
    def __init__(self, symbol: str, color: str, hover_color: str,
                 tip: str, slot, parent=None):
        super().__init__(parent)
        self._symbol     = symbol
        self._color      = QColor(color)
        self._hover_col  = QColor(hover_color)
        self._base_color = QColor(color)
        self._hover      = False
        self._symbol_alpha = 0   # 0=hidden, 255=visible

        self.setFixedSize(14, 14)
        self.setToolTip(tip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(slot)

        # Smooth symbol fade animation
        self._anim = QPropertyAnimation(self, b"symbol_alpha")
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(int)
    def symbol_alpha(self):
        return self._symbol_alpha

    @symbol_alpha.setter
    def symbol_alpha(self, v):
        self._symbol_alpha = v
        self.update()

    def enterEvent(self, event):
        self._hover = True
        self._anim.stop()
        self._anim.setStartValue(self._symbol_alpha)
        self._anim.setEndValue(255)
        self._anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hover = False
        self._anim.stop()
        self._anim.setStartValue(self._symbol_alpha)
        self._anim.setEndValue(0)
        self._anim.start()
        super().leaveEvent(event)

    def set_active_color(self, color: str):
        """Call when pinned state changes."""
        self._color = QColor(color)
        self.update()

    def reset_color(self):
        self._color = QColor(self._base_color)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer glow when hovered
        if self._hover:
            glow = QColor(self._color)
            glow.setAlpha(40)
            p.setBrush(glow)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(0, 0, 14, 14))

        # Main circle
        p.setBrush(self._color)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(2, 2, 10, 10))

        # Symbol (fades in on hover)
        if self._symbol_alpha > 0:
            sym_color = QColor(0, 0, 0, self._symbol_alpha)
            p.setPen(QPen(sym_color, 1.5, Qt.PenStyle.SolidLine,
                          Qt.PenCapStyle.RoundCap))
            p.setFont(QFont("Inter", 6, QFont.Weight.Bold))
            p.drawText(QRectF(2, 2, 10, 10),
                       Qt.AlignmentFlag.AlignCenter, self._symbol)


class WinButtonGroup(QPushButton):
    """Container that holds three WinButtons side by side with spacing."""
    pass
