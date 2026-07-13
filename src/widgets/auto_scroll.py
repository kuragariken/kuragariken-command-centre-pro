"""
auto_scroll.py — Auto-hiding scrollbar overlay.
Fades in on scroll, fades out after 1.5s idle.
Painted as a custom widget over the scroll area — no QSS hacks needed.
"""
from PyQt6.QtWidgets import QWidget, QScrollArea, QAbstractScrollArea
from PyQt6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, pyqtProperty
from PyQt6.QtGui     import QPainter, QColor, QBrush, QPainterPath


class AutoHideScrollBar(QWidget):
    """
    Transparent overlay on top of a QScrollArea.
    Draws a slim accent-coloured scrollbar that fades in/out.
    """
    def __init__(self, scroll_area: QScrollArea, accent: str = "#00e87a"):
        super().__init__(scroll_area)
        self._scroll  = scroll_area
        self._accent  = accent
        self._accent2 = accent
        self._opacity = 0.0
        self._w       = 4   # bar width px

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")
        self.raise_()

        # Hide timer — starts when scrolling stops
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.setInterval(1500)
        self._hide_timer.timeout.connect(self._fade_out)

        # Opacity animation
        self._anim = None

        # Watch the scroll bar for value changes
        sb = scroll_area.verticalScrollBar()
        if sb:
            sb.valueChanged.connect(self._on_scroll)
            sb.rangeChanged.connect(self._update_geometry)

        scroll_area.installEventFilter(self)

    def set_accent(self, accent: str, accent2: str = ""):
        self._accent  = accent
        self._accent2 = accent2 if accent2 else accent
        self.update()

    @pyqtProperty(float)
    def bar_opacity(self) -> float:
        return self._opacity

    @bar_opacity.setter
    def bar_opacity(self, v: float):
        self._opacity = max(0.0, min(1.0, v))
        self.update()

    def _on_scroll(self, _=None):
        self._hide_timer.stop()
        self._fade_in()
        self._hide_timer.start()

    def _fade_in(self):
        if self._anim: self._anim.stop()
        self._anim = QPropertyAnimation(self, b"bar_opacity")
        self._anim.setDuration(120)
        self._anim.setStartValue(self._opacity)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.start()
        self._update_geometry()
        self.show()

    def _fade_out(self):
        if self._anim: self._anim.stop()
        self._anim = QPropertyAnimation(self, b"bar_opacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(self._opacity)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.start()

    def _update_geometry(self):
        p = self._scroll
        self.setGeometry(p.width() - self._w - 2, 0, self._w + 4, p.height())
        self.raise_()

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if obj == self._scroll and event.type() == QEvent.Type.Resize:
            self._update_geometry()
        return False

    def paintEvent(self, event):
        if self._opacity < 0.01:
            return
        sb = self._scroll.verticalScrollBar()
        if not sb or sb.maximum() == 0:
            return

        p   = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        h   = self.height()
        rng = sb.maximum() - sb.minimum() + sb.pageStep()
        if rng <= 0:
            return

        bar_h    = max(24, int(h * sb.pageStep() / rng))
        bar_y    = int((h - bar_h) * (sb.value() - sb.minimum()) / max(1, sb.maximum() - sb.minimum()))
        bar_x    = 2

        # Glow behind bar
        gc = QColor(self._accent)
        gc.setAlpha(int(30 * self._opacity))
        path = QPainterPath()
        path.addRoundedRect(QRectF(bar_x - 2, bar_y - 4, self._w + 4, bar_h + 8), 4, 4)
        p.fillPath(path, gc)

        # Bar with theme gradient
        from PyQt6.QtGui import QLinearGradient
        bg2 = QLinearGradient(0, bar_y, 0, bar_y + bar_h)
        bc1 = QColor(self._accent);  bc1.setAlpha(int(220 * self._opacity))
        bc2 = QColor(self._accent2); bc2.setAlpha(int(180 * self._opacity))
        bg2.setColorAt(0, bc1); bg2.setColorAt(1, bc2)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(QRectF(bar_x, bar_y, self._w, bar_h), 2, 2)
        p.fillPath(bar_path, QBrush(bg2))
