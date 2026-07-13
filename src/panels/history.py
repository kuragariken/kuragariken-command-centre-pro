"""panels/history.py — Clipboard history + favourites"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFrame, QTabWidget, QMenu, QApplication
)
from PyQt6.QtCore import Qt
from src import data as D


class HistoryPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(44); hdr.setStyleSheet("background:rgba(6,10,18,0.85); border-bottom:1px solid rgba(255,255,255,0.07);")
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 12, 0)
        hdr_lay.addWidget(self._lbl("HISTORY"))
        hdr_lay.addStretch()
        clear = QPushButton("Clear"); clear.setStyleSheet("QPushButton{background:transparent;color:#4a5568;border:none;border-radius:5px;padding:4px 8px;} QPushButton:hover{color:#cdd9e5;background:#111827;}")
        clear.clicked.connect(self._clear_history)
        hdr_lay.addWidget(clear)
        root.addWidget(hdr)

        sep = QFrame(); sep.setStyleSheet("background:#1f2d3d; max-height:1px; min-height:1px;"); root.addWidget(sep)

        tabs = QTabWidget()
        tabs.setDocumentMode(True)
        tabs.setStyleSheet(
            'QTabWidget,QTabWidget::pane{background:transparent;border:none;}'
            'QTabBar{background:transparent;border-bottom:1px solid rgba(255,255,255,0.06);}'
            'QTabBar::tab{background:transparent;color:#3a4e64;border:none;'
            'padding:7px 20px;font-size:11px;font-weight:600;letter-spacing:0.3px;}'
            'QTabBar::tab:selected{color:#00e87a;border-bottom:2px solid #00e87a;}'
            'QTabBar::tab:hover:!selected{color:#9ca3af;}')

        # Clipboard history tab
        self._hist_list = QListWidget()
        self._hist_list.itemActivated.connect(self._recopy)
        self._hist_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._hist_list.customContextMenuRequested.connect(self._hist_context)
        tabs.addTab(self._hist_list, "Clipboard")

        # Favourites tab
        self._fav_list = QListWidget()
        self._fav_list.itemActivated.connect(self._copy_fav)
        self._fav_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._fav_list.customContextMenuRequested.connect(self._fav_context)
        tabs.addTab(self._fav_list, "Favourites")

        root.addWidget(tabs, 1)

    def refresh(self):
        self._hist_list.clear()
        for entry in self.app.data.get("clip_history", []):
            label = entry.get("label", "?")
            text  = entry.get("text", "")[:60]
            t     = entry.get("time", "")[:16].replace("T", " ")
            item  = QListWidgetItem(f"{t}  ·  {label}  —  {text}")
            item.setData(Qt.ItemDataRole.UserRole, entry)
            self._hist_list.addItem(item)

        self._fav_list.clear()
        favs = self.app.data.get("favourites", [])
        cmds = self.app.data.get("commands", {})
        for label in favs:
            text = ""
            for cat_cmds in cmds.values():
                for c in cat_cmds:
                    if c.get("label") == label:
                        text = c.get("text", "")[:60]
                        break
            item = QListWidgetItem(f"★  {label}  —  {text}")
            item.setData(Qt.ItemDataRole.UserRole, {"label": label, "text": text})
            self._fav_list.addItem(item)

    def _recopy(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole)
        QApplication.clipboard().setText(entry.get("text", ""))
        self.app.toast.show_toast(f"Re-copied: {entry.get('label','')}")

    def _copy_fav(self, item: QListWidgetItem):
        entry = item.data(Qt.ItemDataRole.UserRole)
        # Find full text
        label = entry.get("label", "")
        for cat_cmds in self.app.data.get("commands", {}).values():
            for c in cat_cmds:
                if c.get("label") == label:
                    QApplication.clipboard().setText(c.get("text", ""))
                    self.app.toast.show_toast(f"Copied: {label}")
                    return

    def _hist_context(self, pos):
        item = self._hist_list.itemAt(pos)
        if not item: return
        entry = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Copy", lambda: self._recopy(item))
        menu.addAction("🗑 Remove", lambda: self._remove_hist(entry))
        menu.exec(self._hist_list.mapToGlobal(pos))

    def _fav_context(self, pos):
        item = self._fav_list.itemAt(pos)
        if not item: return
        entry = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("Copy",         lambda: self._copy_fav(item))
        menu.addAction("Remove from Favourites",
            lambda: self._remove_fav(entry.get("label","")))
        menu.exec(self._fav_list.mapToGlobal(pos))

    def _remove_hist(self, entry: dict):
        self.app.data["clip_history"] = [
            e for e in self.app.data.get("clip_history", [])
            if e.get("text") != entry.get("text") or e.get("time") != entry.get("time")
        ]
        D.save(self.app.data)
        self.refresh()

    def _remove_fav(self, label: str):
        favs = self.app.data.get("favourites", [])
        if label in favs:
            favs.remove(label)
        D.save(self.app.data)
        self.refresh()

    def _clear_history(self):
        self.app.data["clip_history"] = []
        D.save(self.app.data)
        self.refresh()

    def _lbl(self, text):
        l = QLabel(text); l.setStyleSheet("background:transparent; color:#00e87a; font-size:11px; font-weight:700; letter-spacing:2px; border:none;"); return l

    def set_palette(self, p): pass
