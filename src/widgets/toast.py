"""widgets/toast.py — Premium toast with slide-up + gradient fill."""
from PyQt6.QtWidgets import QLabel, QApplication, QWidget, QHBoxLayout
from PyQt6.QtCore    import Qt, QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty, QPoint
from PyQt6.QtGui     import QFont, QColor, QPainter, QPainterPath, QLinearGradient, QBrush, QPen


class Toast(QWidget):
    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedHeight(32)
        self._parent_ref = parent
        self._accent     = "#00e87a"
        self._accent2    = "#38bdf8"

        lay = QHBoxLayout(self)
        lay.setContentsMargins(18, 0, 18, 0)
        self._label = QLabel()
        self._label.setFont(QFont("Inter", 10, QFont.Weight.Medium))
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("background:transparent;color:#060a10;border:none;")
        lay.addWidget(self._label)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._slide_out)

        self._anim = None
        self._pos_anim = None

    def set_accent(self, accent: str, accent2: str = ""):
        self._accent  = accent
        self._accent2 = accent2 if accent2 else accent

    def show_toast(self, msg: str, duration: int = 1600):
        # Don't show if main window is hidden or minimised
        if self._parent_ref:
            pw = self._parent_ref
            if pw.isMinimized() or not pw.isVisible():
                return
        self._label.setText(msg)
        self._label.adjustSize()
        w = max(160, self._label.sizeHint().width() + 36)
        self.setFixedWidth(w)
        self.update()

        # Position: bottom-centre of parent window
        if self._parent_ref:
            pw = self._parent_ref
            cx = pw.x() + pw.width() // 2 - w // 2
            end_y   = pw.y() + pw.height() - 60
            start_y = end_y + 30
        else:
            screen = QApplication.primaryScreen().availableGeometry()
            cx      = screen.center().x() - w // 2
            end_y   = screen.bottom() - 80
            start_y = end_y + 30

        self.move(cx, start_y)
        self.setWindowOpacity(0.0)
        self.show(); self.raise_()

        # Slide up + fade in
        self._pos_anim = QPropertyAnimation(self, b"pos")
        self._pos_anim.setDuration(220)
        self._pos_anim.setStartValue(QPoint(cx, start_y))
        self._pos_anim.setEndValue(QPoint(cx, end_y))
        self._pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pos_anim.start()

        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(180)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(0.88)
        self._anim.start()

        self._hide_timer.start(duration)

    def _slide_out(self):
        if self._pos_anim:
            self._pos_anim.stop()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(200)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InCubic)
        self._anim.finished.connect(self.hide)
        self._anim.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 12, 12)

        # Gradient fill accent → accent2
        grad = QLinearGradient(0, 0, w, h)
        grad.setColorAt(0, QColor(self._accent))
        grad.setColorAt(1, QColor(self._accent2))
        p.fillPath(path, QBrush(grad))

        # Inner highlight
        hi = QColor(255, 255, 255, 45)
        p.setPen(QPen(hi, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(1, 1, w-2, h-2, 11, 11)


# Alias so app.py import works
ToastManager = Toast
