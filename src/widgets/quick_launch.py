"""widgets/quick_launch.py — Floating quick launch bar"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel, QApplication
)
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QFont


class QuickLaunchBar(QWidget):
    def __init__(self, app):
        super().__init__(None)
        self.app = app
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._drag_pos = QPoint()
        self._build_ui()
        self._position()

    def _build_ui(self):
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(6, 4, 6, 4)
        self._lay.setSpacing(4)

    def refresh(self):
        # Clear
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        ql   = self.app.data.get("quick_launch", [])
        cmds = self.app.data.get("commands", {})

        # Build label→text map
        lbl_map = {}
        for cat_cmds in cmds.values():
            for c in cat_cmds:
                lbl_map[c["label"]] = c["text"]

        # Drag handle
        drag = QLabel("⚡ QUICK")
        drag.setObjectName("DimLabel")
        drag.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        drag.setFixedWidth(60)
        self._lay.addWidget(drag)

        for label in ql:
            if label not in lbl_map:
                continue
            text = lbl_map[label]
            btn = QPushButton(label[:14] + ("…" if len(label) > 14 else ""))
            btn.setObjectName("CmdBtn")
            btn.setFixedHeight(28)
            btn.setToolTip(text[:100])
            btn.clicked.connect(lambda checked, l=label, t=text: self._copy(l, t))
            self._lay.addWidget(btn)

        # Close
        close = QPushButton("✕")
        close.setObjectName("GhostBtn")
        close.setFixedSize(24, 24)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self.adjustSize()

    def _copy(self, label: str, text: str):
        QApplication.clipboard().setText(text)
        self.app.toast.show_toast(f"Copied: {label}")
        from src import data as D
        D.record_copy(self.app.data, label, "Quick Launch")
        D.save(self.app.data)

    def _position(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - 600, screen.top() + 4)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
