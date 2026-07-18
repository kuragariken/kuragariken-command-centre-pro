"""
shortcuts_overlay.py — Keyboard shortcuts reference (independent popout).

Research (2025-2026 UX sources on command palettes / power-user tools) is
unanimous: keyboard shortcuts and command palettes are the top efficiency
pattern for professional tools, BUT they're only useful if users know they
exist. The fix: a discoverable reference (press ? or F1) plus a status-bar
hint.

Implemented as its own frameless top-level window, centered over the app, so
it is NEVER clipped by the main window bounds and always shows every row.
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QApplication
)
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPainterPath, QBrush

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"
MONO = "'JetBrains Mono','Cascadia Code','Consolas',monospace"

SHORTCUTS = [
    ("Global", [
        ("Alt + C",       "Show / hide Command Centre"),
        ("Alt + Space",   "Open command palette"),
        ("Win / Alt + Q", "Quick Launch"),
        ("Win / Alt + T", "Pomodoro timer"),
        ("Win / Alt + V", "Paste last copied command"),
    ]),
    ("In-app", [
        ("?  or  F1",     "Show this shortcuts list"),
        ("Esc",           "Close popouts / this list"),
        ("Click KEEP-ALIVE", "Toggle POS GUI keep-alive"),
    ]),
    ("Team Analytics", [
        ("R",             "Refresh now"),
        ("1 / 2 / 3",     "Today / Week / Month"),
        ("Ctrl + E",      "Export CSV"),
    ]),
]


class ShortcutsOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(None)          # top-level, not a child — never clipped
        self._app = parent
        self._accent = "#00e87a"
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.hide()
        self._build()

    def set_accent(self, accent: str):
        self._accent = accent
        if hasattr(self, "_title_mark"):
            self._title_mark.setStyleSheet(
                f"background:{accent};border-radius:1px;")

    def _build(self):
        # The whole window IS the card (with a small transparent margin so the
        # rounded corners + soft edge read cleanly).
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)

        self._card = QWidget()
        self._card.setObjectName("ShortcutsCard")
        self._card.setStyleSheet(
            "#ShortcutsCard{background:#0d1520;"
            "border:1px solid #24374f;"
            "border-top:1px solid rgba(255,255,255,0.12);"
            "border-radius:16px;}")
        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(28, 22, 28, 26)
        cl.setSpacing(4)

        head = QHBoxLayout(); head.setSpacing(10)
        self._title_mark = QLabel(); self._title_mark.setFixedSize(3, 18)
        self._title_mark.setStyleSheet(f"background:{self._accent};border-radius:1px;")
        head.addWidget(self._title_mark)
        title = QLabel("KEYBOARD SHORTCUTS")
        title.setStyleSheet(
            f"background:transparent;color:#e8eef5;font-size:13px;"
            f"font-weight:800;letter-spacing:2px;border:none;font-family:{MONO};")
        head.addWidget(title)
        head.addStretch()
        hint = QLabel("Esc to close")
        hint.setStyleSheet(
            "background:transparent;color:#6b83a0;font-size:10px;border:none;")
        head.addWidget(hint)
        cl.addLayout(head)
        cl.addSpacing(16)

        for group, items in SHORTCUTS:
            g = QLabel(group.upper())
            g.setStyleSheet(
                f"background:transparent;color:{self._accent};font-size:10px;"
                f"font-weight:700;letter-spacing:1.5px;border:none;")
            cl.addWidget(g)
            cl.addSpacing(6)

            grid = QGridLayout()
            grid.setHorizontalSpacing(18)
            grid.setVerticalSpacing(8)
            grid.setColumnStretch(1, 1)
            grid.setColumnMinimumWidth(0, 140)
            for i, (keys, desc) in enumerate(items):
                kb = QLabel(keys)
                kb.setStyleSheet(
                    "background:rgba(255,255,255,0.07);color:#e2e8f0;"
                    "border:1px solid #2a3f5c;border-radius:8px;"
                    "padding:4px 10px;font-size:11px;font-weight:700;"
                    f"font-family:{MONO};")
                kb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                d = QLabel(desc)
                d.setStyleSheet(
                    "background:transparent;color:#9fb0c4;font-size:12px;border:none;")
                grid.addWidget(kb, i, 0)
                grid.addWidget(d,  i, 1)
            cl.addLayout(grid)
            cl.addSpacing(16)

        outer.addWidget(self._card)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Question, Qt.Key.Key_F1):
            self.hide_overlay()
        else:
            super().keyPressEvent(e)

    def show_overlay(self):
        # Size to content, then centre over the main app window.
        self.adjustSize()
        app = self._app
        if app:
            geo = app.frameGeometry()
            x = geo.center().x() - self.width() // 2
            y = geo.center().y() - self.height() // 2
        else:
            scr = QApplication.primaryScreen().availableGeometry()
            x = scr.center().x() - self.width() // 2
            y = scr.center().y() - self.height() // 2
        self.move(max(0, x), max(0, y))
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._fade(0.0, 1.0)

    def hide_overlay(self):
        self._fade(self.windowOpacity(), 0.0, on_done=self.hide)

    def _fade(self, a, b, on_done=None):
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(140)
        anim.setStartValue(a); anim.setEndValue(b)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        if on_done:
            anim.finished.connect(on_done)
        anim.start()
        self._anim = anim
