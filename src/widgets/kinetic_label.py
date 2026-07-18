"""
kinetic_label.py — Kinetic typography label.
When text changes, letter-spacing animates from 0 → full in 300ms.
Also supports a count-up number animation.
"""
from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import QTimer, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont


class KineticLabel(QLabel):
    """
    Label whose text 'sweeps in' with expanding letter-spacing on change.
    """
    def __init__(self, text: str = "", parent=None,
                 base_style: str = "", target_spacing: float = 3.0):
        super().__init__(text, parent)
        self._base_style     = base_style
        self._target_spacing = target_spacing
        self._spacing        = target_spacing
        self._apply_style(target_spacing)

    def animate_in(self):
        """Trigger the letter-spacing sweep animation."""
        self._spacing = 0.0
        self._apply_style(0.0)
        steps = 18
        self._step = self._target_spacing / steps
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.start(16)   # 60fps

    def _tick(self):
        self._spacing += self._step
        if self._spacing >= self._target_spacing:
            self._spacing = self._target_spacing
            self._anim_timer.stop()
        self._apply_style(self._spacing)

    def _apply_style(self, spacing: float):
        self.setStyleSheet(
            f"{self._base_style} letter-spacing: {spacing:.2f}px;")
