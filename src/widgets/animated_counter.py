"""
animated_counter.py — Numbers count up when they change. Premium feel.
Used for analytics stat cards.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty


class AnimatedCounter(QLabel):
    def __init__(self, parent=None):
        super().__init__("0", parent)
        self._current = 0.0
        self._target  = 0
        self._timer   = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def set_value(self, value: int, duration_ms: int = 800):
        self._target = value
        if value == 0:
            self._current = 0
            self.setText("0")
            return
        self._timer.stop()
        steps = max(1, duration_ms // 16)
        self._step = (value - self._current) / steps
        self._timer.start(16)

    def _tick(self):
        self._current += self._step
        if (self._step > 0 and self._current >= self._target) or \
           (self._step < 0 and self._current <= self._target):
            self._current = self._target
            self._timer.stop()
        self.setText(str(int(self._current)))
