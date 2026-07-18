"""
upgrade_tracker_panel.py — thin stack placeholder that opens the Upgrade
Tracker as an independent popout window (mirrors the Teams/Settings pattern).

The heavy lifting lives in upgrade_tracker.py (UpgradeTrackerWindow); this just
launches it and snaps the main stack back to Commands so the invisible
placeholder page never shows.
"""
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import QTimer


class UpgradeTrackerPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app  = app
        self._win = None
        self.setStyleSheet("background:transparent;")

    def refresh(self):
        if self._win is None:
            from src.panels.upgrade_tracker import UpgradeTrackerWindow
            self._win = UpgradeTrackerWindow()
        self._win.show_fullscreen()
        # Return the main window to Commands so the empty placeholder never shows.
        QTimer.singleShot(50, lambda: self._to_commands())

    def _to_commands(self):
        try:
            keys = list(self.app._panels.keys())
            self.app._stack.setCurrentIndex(keys.index('commands'))
        except Exception:
            pass

    def set_palette(self, p):
        pass
