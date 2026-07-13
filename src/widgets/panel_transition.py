"""
panel_transition.py — Flash-fade between panels using a proper pyqtProperty.
"""
from PyQt6.QtWidgets import QWidget, QStackedWidget
from PyQt6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui     import QPainter, QColor


class FadeOverlay(QWidget):
    """Dark overlay that flashes to mask the panel swap."""
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self._alpha = 0
        self._color = QColor(5, 8, 16)
        self.setStyleSheet("background:transparent;")
        self.hide()

    @pyqtProperty(int)
    def alpha(self) -> int:
        return self._alpha

    @alpha.setter
    def alpha(self, value: int):
        self._alpha = max(0, min(255, value))
        self.update()

    def set_bg(self, color: str):
        self._color = QColor(color)

    def paintEvent(self, e):
        if self._alpha <= 0:
            return
        p = QPainter(self)
        c = QColor(self._color)
        c.setAlpha(self._alpha)
        p.fillRect(self.rect(), c)


class PanelTransition:
    """Attach to the QStackedWidget. Call switch(index) to animate."""

    def __init__(self, stack: QStackedWidget, parent: QWidget):
        self._stack   = stack
        self._parent  = parent
        self._overlay = FadeOverlay(parent)
        self._overlay.resize(parent.size())
        self._overlay.raise_()
        self._busy    = False
        self._anim_in  = None
        self._anim_out = None

    def resize(self, size):
        self._overlay.resize(size)

    def set_bg_color(self, color: str):
        self._overlay.set_bg(color)

    def switch(self, index: int):
        # Safety: if stuck, force reset after 500ms
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self._safety_reset)
        # Skip animation if same panel or already animating
        if self._stack.currentIndex() == index:
            return
        if self._busy:
            self._stack.setCurrentIndex(index)
            return

        self._busy = True
        self._overlay.resize(self._stack.size())
        self._overlay.raise_()
        self._overlay.show()

        # Fade IN (overlay covers screen)
        a_in = QPropertyAnimation(self._overlay, b"alpha", self._overlay)
        a_in.setDuration(60)
        a_in.setStartValue(0)
        a_in.setEndValue(160)
        a_in.setEasingCurve(QEasingCurve.Type.OutCubic)
        a_in.finished.connect(lambda: self._do_swap(index))
        a_in.start()
        self._anim_in = a_in   # keep reference

    def _do_swap(self, index: int):
        self._stack.setCurrentIndex(index)

        # Fade OUT (overlay reveals new panel)
        a_out = QPropertyAnimation(self._overlay, b"alpha", self._overlay)
        a_out.setDuration(120)
        a_out.setStartValue(160)
        a_out.setEndValue(0)
        a_out.setEasingCurve(QEasingCurve.Type.InCubic)
        a_out.finished.connect(self._done)
        a_out.start()
        self._anim_out = a_out

    def _safety_reset(self):
        """Force-complete any stuck transition."""
        if self._busy:
            self._overlay.alpha = 0
            self._overlay.hide()
            self._busy = False

    def _done(self):
        self._overlay.hide()
        self._busy = False
        self._overlay.alpha = 0
