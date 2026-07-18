"""Pomodoro timer — uses only QLabel widgets, no QWidget subclass background issues."""
from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QMenu
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont


class PomodoroWidget(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app       = app
        self._state    = "idle"
        self._remaining = 0
        self._cycles   = 0

        # Must set background explicitly — QWidget subclasses don't inherit QSS bg
        self.setStyleSheet("QWidget { background: transparent; }")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        self._lbl = QLabel("POMO")
        self._lbl.setStyleSheet(
            "background: transparent; color: #6e7d90; "
            "font-size: 10px; font-weight: 700; font-family: 'Segoe UI'; border: none;")
        lay.addWidget(self._lbl)

        self._time_lbl = QLabel("")
        self._time_lbl.setStyleSheet(
            "background: transparent; color: #6e7d90; "
            "font-size: 11px; font-family: 'JetBrains Mono','Cascadia Code','Fira Code','JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace; "
            "font-weight: 700; border: none;")
        self._time_lbl.setFixedWidth(0)
        lay.addWidget(self._time_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_accent(self, accent: str, dim: str = "#6e7d90"):
        self._accent = accent
        self._dim    = dim
        self._refresh_style()

    def _refresh_style(self):
        accent = getattr(self, "_accent", "#00e87a")
        dim    = getattr(self, "_dim",    "#6e7d90")
        if self._state == "focus":
            c = accent
        elif self._state == "break":
            c = "#38bdf8"
        else:
            c = dim
        for w in [self._lbl, self._time_lbl]:
            w.setStyleSheet(
                f"background: transparent; color: {c}; border: none; "
                f"font-family: 'Segoe UI'; font-weight: 700; font-size: 10px;")

    def toggle(self):
        if self._state == "idle":
            self._start_focus()
        else:
            self._stop()

    def _start_focus(self):
        self._state = "focus"
        self._remaining = self.app.data["settings"].get("pomo_focus", 25) * 60
        self._time_lbl.setFixedWidth(44)
        self._timer.start(1000)
        self._update_labels()
        self.app.toast.show_toast("Focus started")

    def _start_break(self):
        self._state = "break"
        self._remaining = self.app.data["settings"].get("pomo_break", 5) * 60
        self._time_lbl.setFixedWidth(44)
        self._timer.start(1000)
        self._update_labels()
        self.app.toast.show_toast("Break started")

    def _stop(self):
        self._state = "idle"
        self._timer.stop()
        self._remaining = 0
        self._lbl.setText("POMO")
        self._time_lbl.setText("")
        self._time_lbl.setFixedWidth(0)
        self._refresh_style()

    def _tick(self):
        self._remaining -= 1
        if self._remaining <= 0:
            if self._state == "focus":
                self._cycles += 1
                self.app.data["session_stats"]["pomo_sessions"] = \
                    self.app.data["session_stats"].get("pomo_sessions", 0) + 1
                from src import data as D
                D.save(self.app.data)
                self.app.toast.show_toast(f"Focus done — session {self._cycles}")
                self._start_break()
            else:
                self.app.toast.show_toast("Break over")
                self._stop()
            return
        self._update_labels()

    def _update_labels(self):
        m = self._remaining // 60
        s = self._remaining % 60
        self._lbl.setText("FOCUS" if self._state == "focus" else "BREAK")
        self._time_lbl.setText(f"{m:02d}:{s:02d}")
        self._refresh_style()

    def _show_menu(self, pos):
        m = QMenu(self)
        if self._state == "idle":
            m.addAction("Start Focus", self._start_focus)
        else:
            m.addAction("Start Break", self._start_break)
            m.addAction("Stop", self._stop)
        m.addSeparator()
        m.addAction(f"Sessions: {self._cycles}").setEnabled(False)
        m.exec(self.mapToGlobal(pos))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle()
        super().mousePressEvent(event)
