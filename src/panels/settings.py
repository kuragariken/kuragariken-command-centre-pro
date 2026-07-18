"""
settings.py — Settings as a premium floating popout window.
Launched from the nav, slides in from the right edge of the main window.
"""
from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QSpinBox, QScrollArea,
    QFileDialog, QMessageBox, QLineEdit, QSizeGrip
)
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QPoint, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath
from src import data as D
from src import startup as Startup
from src.themes import THEMES
from src.widgets.accent_line import AccentLine

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"


class SettingsWindow(QWidget):
    """Floating settings window — slides in from the right of the main window."""
    theme_changed = pyqtSignal(str)
    data_changed  = pyqtSignal()

    def __init__(self, app_win):
        super().__init__(None)
        self._app = app_win
        self._dragging = False
        self._drag_pos = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        from src.widgets.app_icon import apply_window_icon
        apply_window_icon(self)
        self.setFixedWidth(380)
        self.setMinimumHeight(500)

        self._build_ui()
        self._apply_glass()

    def _apply_glass(self):
        self.setStyleSheet(
            "QWidget { background: rgba(6,10,18,0.97); color: #d4dfe9; "
            f"font-family: {FONT}; font-size: 12px; border: none; }}"
            "QScrollArea { background: transparent; border: none; }"
            "QScrollArea > QWidget { background: transparent; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            "QScrollBar::handle:vertical { background: #1a2840; border-radius: 2px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Shimmer line
        self._accent_line = AccentLine(self)
        root.addWidget(self._accent_line)

        # Title bar
        hdr = QWidget()
        hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            "background: rgba(8,13,22,0.98);"
            "border-bottom: 1px solid rgba(255,255,255,0.07);")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 12, 0)

        mark = QLabel()
        mark.setFixedSize(3, 22)
        self._mark = mark
        mark.setStyleSheet("background:#00e87a; border-radius:1px;")
        hl.addWidget(mark)
        hl.addSpacing(10)

        title = QLabel("SETTINGS")
        title.setStyleSheet(
            f"background:transparent; color:#00e87a; font-size:10px;"
            f"font-weight:800; letter-spacing:3px; border:none; font-family:{FONT};")
        hl.addWidget(title)
        hl.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#6b83a0;border:none;"
            "border-radius:8px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#f87171;color:#080b12;}")
        close_btn.clicked.connect(self.slide_out)
        hl.addWidget(close_btn)
        root.addWidget(hdr)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(content)
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(14)

        # ── APPEARANCE ────────────────────────────────────────
        lay.addWidget(self._section("APPEARANCE"))

        lay.addWidget(self._row_label("Theme"))
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES.keys()))
        self._theme_combo.setCurrentText(
            self._app.data["settings"].get("theme", "Default"))
        self._theme_combo.currentTextChanged.connect(self.theme_changed.emit)
        self._style_input(self._theme_combo)
        lay.addWidget(self._theme_combo)

        lay.addWidget(self._row_label("Button size"))
        self._btn_size = QComboBox()
        self._btn_size.addItems(["S — Small", "M — Medium", "L — Large"])
        cur = self._app.data["settings"].get("btn_size", "M")
        self._btn_size.setCurrentIndex({"S":0,"M":1,"L":2}.get(cur, 1))
        self._btn_size.currentIndexChanged.connect(self._save_btn_size)
        self._style_input(self._btn_size)
        lay.addWidget(self._btn_size)

        # ── SYSTEM ───────────────────────────────────────────
        lay.addWidget(self._section("SYSTEM"))

        self._startup_cb = QCheckBox("Start with Windows")
        self._startup_cb.setChecked(Startup.is_startup_enabled())
        self._startup_cb.toggled.connect(Startup.set_startup)
        self._style_check(self._startup_cb)
        lay.addWidget(self._startup_cb)

        self._aot_cb = QCheckBox("Always on top")
        self._aot_cb.setChecked(
            self._app.data["settings"].get("always_on_top", False))
        self._aot_cb.toggled.connect(self._save_aot)
        self._style_check(self._aot_cb)
        lay.addWidget(self._aot_cb)

        self._paste_cb = QCheckBox("Auto-paste after copy")
        self._paste_cb.setChecked(
            self._app.data["settings"].get("auto_paste", False))
        self._paste_cb.toggled.connect(self._save_paste)
        self._style_check(self._paste_cb)
        lay.addWidget(self._paste_cb)


        # ── POMODORO ─────────────────────────────────────────
        lay.addWidget(self._section("POMODORO"))

        prow = QHBoxLayout()
        prow.addWidget(self._row_label("Focus (min)"))
        self._pomo_focus = QSpinBox()
        self._pomo_focus.setRange(5, 120)
        self._pomo_focus.setValue(
            self._app.data["settings"].get("pomo_focus", 25))
        self._pomo_focus.valueChanged.connect(self._save_pomo)
        self._style_input(self._pomo_focus)
        prow.addWidget(self._pomo_focus)
        prow.addSpacing(16)
        prow.addWidget(self._row_label("Break (min)"))
        self._pomo_break = QSpinBox()
        self._pomo_break.setRange(1, 60)
        self._pomo_break.setValue(
            self._app.data["settings"].get("pomo_break", 5))
        self._pomo_break.valueChanged.connect(self._save_pomo)
        self._style_input(self._pomo_break)
        prow.addWidget(self._pomo_break)
        lay.addLayout(prow)

        # ── HOTSTRINGS ────────────────────────────────────────
        lay.addWidget(self._section("HOTSTRINGS"))

        hs_row = QHBoxLayout()
        self._hs_trigger = QLineEdit()
        self._hs_trigger.setPlaceholderText("Trigger  e.g. /gm")
        self._style_input(self._hs_trigger)
        hs_row.addWidget(self._hs_trigger, 1)
        self._hs_label = QLineEdit()
        self._hs_label.setPlaceholderText("Expands to…")
        self._style_input(self._hs_label)
        hs_row.addWidget(self._hs_label, 2)
        add_hs = QPushButton("Add")
        add_hs.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:8px;padding:5px 12px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        add_hs.clicked.connect(self._add_hotstring)
        hs_row.addWidget(add_hs)
        lay.addLayout(hs_row)

        self._hs_lay = QVBoxLayout()
        self._hs_lay.setSpacing(4)
        lay.addLayout(self._hs_lay)

        # ── DATA ─────────────────────────────────────────────
        lay.addWidget(self._section("DATA"))

        # Data folder location — always visible so user knows where data is
        from src.data import get_data_folder
        folder_path = get_data_folder()
        folder_card = QWidget()
        folder_card.setStyleSheet(
            "background:rgba(0,232,122,0.05);border:1px solid rgba(0,232,122,0.15);"
            "border-radius:8px;")
        fc_lay = QVBoxLayout(folder_card)
        fc_lay.setContentsMargins(12, 10, 12, 10)
        fc_lay.setSpacing(4)
        fl1 = QLabel("DATA FOLDER")
        fl1.setStyleSheet(
            f"background:transparent;color:#00e87a;font-size:9px;"
            f"font-weight:800;letter-spacing:2px;border:none;font-family:{FONT};")
        fc_lay.addWidget(fl1)
        fl2 = QLabel(folder_path)
        fl2.setWordWrap(True)
        fl2.setStyleSheet(
            f"background:transparent;color:#6b7f96;font-size:10px;"
            f"font-family:'JetBrains Mono','Consolas',monospace;border:none;")
        fc_lay.addWidget(fl2)
        open_btn = QPushButton("Open Folder")
        open_btn.setFixedHeight(26)
        open_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#00e87a;border:none;"
            f"font-size:10px;font-weight:600;font-family:{FONT};}}"
            "QPushButton:hover{text-decoration:underline;}")
        import subprocess as _sp, sys as _sys
        open_btn.clicked.connect(
            lambda: _sp.Popen(["explorer", folder_path]) if _sys.platform=="win32"
            else None)
        fc_lay.addWidget(open_btn)
        lay.addWidget(folder_card)

        # Import from old AHK GUI — prominent, at top of data section
        ahk_btn = QPushButton("⬆  Import from Old AHK GUI")
        ahk_btn.setFixedHeight(40)
        ahk_btn.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 rgba(0,232,122,0.15),stop:1 rgba(0,232,122,0.05));"
            f"color:#00e87a;border:1px solid rgba(0,232,122,0.3);"
            f"border-radius:8px;padding:0 16px;font-size:12px;font-weight:700;"
            f"font-family:{FONT};}}"
            f"QPushButton:hover{{background:rgba(0,232,122,0.22);"
            f"border-color:rgba(0,232,122,0.6);}}")
        ahk_btn.clicked.connect(self._import_ahk)
        lay.addWidget(ahk_btn)

        drow = QHBoxLayout(); drow.setSpacing(8)
        for label, slot in [
            ("Export JSON", self._export),
            ("Import JSON", self._import),
            ("Backup Now",  self._backup),
        ]:
            b = QPushButton(label)
            b.setStyleSheet(
                "QPushButton{background:rgba(15,25,40,0.8);color:#9ca3af;"
                "border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
                f"padding:6px 10px;font-size:11px;font-family:{FONT};}}"
                "QPushButton:hover{background:rgba(25,40,60,0.9);"
                "color:#e2e8f0;border-color:rgba(255,255,255,0.15);}")
            b.clicked.connect(slot)
            drow.addWidget(b)
        lay.addLayout(drow)

        rst = QPushButton("Reset Analytics")
        rst.setStyleSheet(
            "QPushButton{background:transparent;color:#f87171;"
            "border:1px solid rgba(248,113,113,0.3);border-radius:8px;"
            f"padding:6px 12px;font-size:11px;font-family:{FONT};}}"
            "QPushButton:hover{background:rgba(248,113,113,0.1);"
            "border-color:#f87171;}")
        rst.clicked.connect(self._reset_stats)
        lay.addWidget(rst)

        # ── UPDATES ───────────────────────────────────────────
        lay.addWidget(self._section("UPDATES"))
        from src.updater import APP_VERSION
        ver_lbl = QLabel(f"Current version:  v{APP_VERSION}")
        ver_lbl.setStyleSheet(
            "background:transparent;color:#6b83a0;font-size:11px;border:none;")
        lay.addWidget(ver_lbl)
        lay.addSpacing(6)

        upd_btn = QPushButton("⟳  Check for updates")
        upd_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        upd_btn.setStyleSheet(
            "QPushButton{background:rgba(0,232,122,0.12);color:#00e87a;"
            "border:1px solid rgba(0,232,122,0.35);border-radius:8px;"
            "padding:7px 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:rgba(0,232,122,0.2);}")
        upd_btn.clicked.connect(self._check_updates_clicked)
        lay.addWidget(upd_btn)

        # ── BACKUP & SYNC ─────────────────────────────────────
        lay.addWidget(self._section("BACKUP & SYNC"))

        bk_desc = QLabel(
            "Export all your commands, macros, reminders, tickets, notes and "
            "settings to a single file — then import it on another PC. Your "
            "vault comes along encrypted; you'll still need its password to "
            "unlock it there.")
        bk_desc.setWordWrap(True)
        bk_desc.setStyleSheet(
            "background:transparent;color:#6b83a0;font-size:11px;border:none;")
        lay.addWidget(bk_desc)
        lay.addSpacing(6)

        bk_row = QHBoxLayout(); bk_row.setSpacing(8)
        exp = QPushButton("⬆  Export data")
        exp.setCursor(Qt.CursorShape.PointingHandCursor)
        exp.setStyleSheet(
            "QPushButton{background:rgba(56,189,248,0.12);color:#38bdf8;"
            "border:1px solid rgba(56,189,248,0.35);border-radius:8px;"
            "padding:7px 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:rgba(56,189,248,0.2);}")
        exp.clicked.connect(self._export_data)
        bk_row.addWidget(exp)

        imp = QPushButton("⬇  Import data")
        imp.setCursor(Qt.CursorShape.PointingHandCursor)
        imp.setStyleSheet(
            "QPushButton{background:rgba(167,139,250,0.12);color:#a78bfa;"
            "border:1px solid rgba(167,139,250,0.35);border-radius:8px;"
            "padding:7px 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:rgba(167,139,250,0.2);}")
        imp.clicked.connect(self._import_data)
        bk_row.addWidget(imp)
        bk_row.addStretch()
        lay.addLayout(bk_row)

        lay.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # Resize grip
        gr = QHBoxLayout()
        gr.setContentsMargins(0, 0, 4, 4)
        gr.addStretch()
        grip = QSizeGrip(self)
        grip.setFixedSize(12, 12)
        gr.addWidget(grip)
        gw = QWidget(); gw.setFixedHeight(14); gw.setLayout(gr)
        gw.setStyleSheet("background:transparent;")
        root.addWidget(gw)

    # ── Helpers ───────────────────────────────────────────────
    def _section(self, text: str) -> QWidget:
        row = QWidget(); row.setStyleSheet("background:transparent;")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 6, 0, 2); rl.setSpacing(8)
        dot = QLabel("●"); dot.setFixedWidth(10)
        dot.setStyleSheet(
            "background:transparent;color:#00e87a;font-size:7px;border:none;")
        rl.addWidget(dot)
        lbl = QLabel(text)
        lbl.setStyleSheet(
            f"background:transparent;color:#6b83a0;font-size:9px;"
            f"font-weight:800;letter-spacing:3px;border:none;font-family:{FONT};")
        rl.addWidget(lbl)
        line = QFrame(); line.setFixedHeight(1)
        line.setStyleSheet("background:rgba(255,255,255,0.06);")
        rl.addWidget(line, 1)
        return row

    def _row_label(self, text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"background:transparent;color:#6b7f96;font-size:10px;"
            f"font-weight:600;letter-spacing:0.5px;border:none;font-family:{FONT};")
        return l

    def _style_input(self, w):
        w.setStyleSheet(
            "QComboBox,QLineEdit,QSpinBox{"
            "background:rgba(10,16,26,0.9);color:#d4dfe9;"
            "border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
            f"padding:7px 10px;font-size:12px;font-family:{FONT};}}"
            "QComboBox:focus,QLineEdit:focus,QSpinBox:focus{"
            "border-color:#00e87a;}"
            "QComboBox::drop-down{border:none;width:20px;}"
            "QComboBox QAbstractItemView{"
            "background:#0a101a;color:#d4dfe9;"
            "border:1px solid rgba(255,255,255,0.08);"
            "selection-background-color:#182030;}"
            "QSpinBox::up-button,QSpinBox::down-button{"
            "background:rgba(20,30,45,0.8);border:none;width:18px;}")

    def _style_check(self, cb: QCheckBox):
        cb.setStyleSheet(
            f"QCheckBox{{background:transparent;color:#9ca3af;font-size:12px;"
            f"font-family:{FONT};spacing:10px;}}"
            f"QCheckBox::indicator{{width:18px;height:18px;"
            f"border:1px solid rgba(255,255,255,0.12);border-radius:8px;"
            f"background:rgba(10,16,26,0.8);}}"
            f"QCheckBox::indicator:checked{{"
            f"background:#00e87a;border-color:#00e87a;}}"
            f"QCheckBox:hover{{color:#e2e8f0;}}")

    # ── Slide animation ───────────────────────────────────────
    def slide_in(self):
        if not self._app: return
        from PyQt6.QtWidgets import QApplication
        mw      = self._app
        screen  = QApplication.primaryScreen().availableGeometry()
        win_w   = self.width()
        win_h   = self.height()

        # Prefer right of main window, fall back to left if no room
        right_x = mw.x() + mw.width() + 8
        if right_x + win_w <= screen.right():
            target_x = right_x
            start_x  = target_x + 60
        else:
            target_x = max(screen.left(), mw.x() - win_w - 8)
            start_x  = target_x - 60

        ideal_y  = mw.y() + (mw.height() - win_h) // 2
        target_y = max(screen.top(), min(ideal_y, screen.bottom() - win_h))

        self.move(start_x, target_y)
        self.setWindowOpacity(0)
        self.show()
        self.raise_()

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(320)
        pos_anim.setStartValue(QPoint(start_x, target_y))
        pos_anim.setEndValue(QPoint(target_x, target_y))
        pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        op_anim = QPropertyAnimation(self, b"windowOpacity")
        op_anim.setDuration(280)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        pos_anim.start(); op_anim.start()
        self._slide_in_anim  = pos_anim
        self._slide_op_anim  = op_anim

        self.refresh()

    def slide_out(self):
        if not self._app: self.hide(); return
        mw   = self._app
        end_x = mw.x() + mw.width() + 60

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(220)
        pos_anim.setStartValue(self.pos())
        pos_anim.setEndValue(QPoint(end_x, self.y()))
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)
        pos_anim.finished.connect(self.hide)

        op_anim = QPropertyAnimation(self, b"windowOpacity")
        op_anim.setDuration(180)
        op_anim.setStartValue(self.windowOpacity())
        op_anim.setEndValue(0.0)
        pos_anim.start(); op_anim.start()
        self._slide_out_anim = pos_anim
        self._slide_out_op   = op_anim

    def refresh(self):
        self._refresh_hotstrings()

    def set_palette(self, p):
        accent = p.get("accent", "#00e87a")
        self._accent_line.set_accent(accent)
        self._mark.setStyleSheet(f"background:{accent}; border-radius:1px;")

    # ── Drag title bar ────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 48:
            self._dragging = True
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def closeEvent(self, e):
        e.ignore(); self.slide_out()

    # ── Save handlers ─────────────────────────────────────────
    def _save_btn_size(self, idx):
        self._app.data["settings"]["btn_size"] = ["S","M","L"][idx]
        D.save(self._app.data)
        self.data_changed.emit()

    def _save_aot(self, v):
        self._app.data["settings"]["always_on_top"] = v
        D.save(self._app.data)
        self.data_changed.emit()

    def _save_paste(self, v):
        self._app.data["settings"]["auto_paste"] = v
        D.save(self._app.data)

    def _save_pomo(self):
        self._app.data["settings"]["pomo_focus"] = self._pomo_focus.value()
        self._app.data["settings"]["pomo_break"] = self._pomo_break.value()
        D.save(self._app.data)

    def _refresh_hotstrings(self):
        while self._hs_lay.count():
            w = self._hs_lay.takeAt(0).widget()
            if w: w.deleteLater()
        for trigger, label in self._app.data.get("hotstrings", {}).items():
            row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
            rl = QHBoxLayout(row_w); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
            t = QLabel(trigger)
            t.setStyleSheet(
                f"background:rgba(0,232,122,0.08);color:#00e87a;"
                f"font-family:'JetBrains Mono','Consolas',monospace;"
                f"font-size:11px;border-radius:4px;padding:2px 8px;border:none;")
            rl.addWidget(t)
            arr = QLabel("→")
            arr.setStyleSheet("background:transparent;color:#6b83a0;border:none;")
            rl.addWidget(arr)
            lbl = QLabel(label)
            lbl.setStyleSheet("background:transparent;color:#9ca3af;font-size:11px;border:none;")
            rl.addWidget(lbl, 1)
            del_btn = QPushButton("✕")
            del_btn.setFixedSize(22, 22)
            del_btn.setStyleSheet(
                "QPushButton{background:transparent;color:#6b83a0;border:none;"
                "border-radius:4px;font-size:11px;font-weight:700;}"
                "QPushButton:hover{background:rgba(248,113,113,0.15);color:#f87171;}")
            del_btn.clicked.connect(lambda checked, t=trigger: self._del_hotstring(t))
            rl.addWidget(del_btn)
            self._hs_lay.addWidget(row_w)

    def _check_updates_clicked(self):
        app = getattr(self, "_app", None)
        if app and hasattr(app, "check_for_update_manual"):
            app.check_for_update_manual()

    def _export_data(self):
        """Write the entire CCP dataset to a single portable .json file."""
        import json, datetime
        default = f"CommandCentre_backup_{datetime.date.today().isoformat()}.json"
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Command Centre data", default, "CCP data (*.json)")
        if not path:
            return
        try:
            payload = {
                "_ccp_export": True,
                "_exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
                "data": self._app.data,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            QMessageBox.information(
                self, "Export complete",
                "Your Command Centre data has been exported.\n\n"
                "Copy this file to another PC and use Import there.")
        except Exception as e:
            QMessageBox.warning(self, "Export failed", f"Could not export:\n{e}")

    def _import_data(self):
        """Replace the current dataset with an exported file (with confirm)."""
        import json
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Command Centre data", "", "CCP data (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Import failed", f"Could not read file:\n{e}")
            return

        # Accept either a wrapped export or a raw CommandCentre.json
        incoming = payload.get("data") if isinstance(payload, dict) and \
            payload.get("_ccp_export") else payload
        if not isinstance(incoming, dict) or "commands" not in incoming:
            QMessageBox.warning(
                self, "Import failed",
                "That doesn't look like a Command Centre export file.")
            return

        # Count what's coming in so the user knows what they're replacing
        n_cmds = sum(len(v) for v in incoming.get("commands", {}).values()
                     if isinstance(v, dict))
        n_mac  = len(incoming.get("macros", []))
        n_rem  = len(incoming.get("reminders", []))
        confirm = QMessageBox.question(
            self, "Replace current data?",
            f"This will REPLACE your current Command Centre data with the "
            f"imported file:\n\n"
            f"• {n_cmds} commands\n• {n_mac} macros\n• {n_rem} reminders\n"
            f"• plus notes, tickets, vault and settings\n\n"
            f"Your current data will be overwritten. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            # Merge onto a fresh default so any missing keys are filled in.
            base = D._default_data()
            D._deep_merge(base, incoming)
            self._app.data = base
            D.save(self._app.data)
            self.data_changed.emit()
            QMessageBox.information(
                self, "Import complete",
                "Data imported successfully. Some changes may need a restart "
                "to show everywhere.")
        except Exception as e:
            QMessageBox.warning(self, "Import failed", f"Could not import:\n{e}")

    def _add_hotstring(self):
        trigger = self._hs_trigger.text().strip()
        label   = self._hs_label.text().strip()
        if trigger and label:
            self._app.data.setdefault("hotstrings", {})[trigger] = label
            D.save(self._app.data)
            self._hs_trigger.clear(); self._hs_label.clear()
            self._refresh_hotstrings()

    def _del_hotstring(self, trigger):
        self._app.data.get("hotstrings", {}).pop(trigger, None)
        D.save(self._app.data)
        self._refresh_hotstrings()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", "CommandCentre_export.json", "JSON (*.json)")
        if path:
            import json
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self._app.data, f, indent=2, ensure_ascii=False)
            self._app.toast.show_toast("Exported")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "Import", "", "JSON (*.json)")
        if path:
            reply = QMessageBox.question(self, "Import",
                "Replace all data with imported file?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                D.backup(self._app.data)
                import json
                with open(path, "r", encoding="utf-8") as f:
                    self._app.data = json.load(f)
                D.save(self._app.data)
                self.data_changed.emit()
                self._app.toast.show_toast("Imported")

    def _import_ahk(self):
        """Import categories and commands from old AHK v9 JSON export."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Import from Old AHK GUI", "",
            "JSON Export (*.json);;All Files (*)")
        if not path:
            return
        try:
            from src import data as D2
            cats, cmds, skipped = D2.import_from_ahk(self._app.data, path)
            self.data_changed.emit()
            QMessageBox.information(self, "Import Complete",
                f"Successfully imported from AHK GUI:\n\n"
                f"  ● {cats} new categories\n"
                f"  ● {cmds} commands imported\n"
                f"  ● {skipped} skipped (duplicates or empty)\n\n"
                f"Switch to Commands to see your imported data.")
        except Exception as e:
            QMessageBox.critical(self, "Import Failed",
                f"Could not import file:\n\n{e}")

    def _backup(self):
        D.backup(self._app.data)
        self._app.toast.show_toast("Backup created")

    def _reset_stats(self):
        reply = QMessageBox.question(self, "Reset", "Reset all analytics data?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from src.data import _default_data
            self._app.data["session_stats"] = _default_data()["session_stats"]
            self._app.data["copy_counts"]   = {}
            D.save(self._app.data)
            self._app.toast.show_toast("Analytics reset")


# ── Thin panel proxy — stays in the stack, opens the real window ──
class SettingsPanel(QWidget):
    theme_changed = pyqtSignal(str)
    data_changed  = pyqtSignal()

    def __init__(self, app):
        super().__init__()
        self.app  = app
        self._win = None
        # Invisible — settings nav item immediately opens the popout
        self.setStyleSheet("background:transparent;")

    def refresh(self):
        """Called by app._nav_to — open the settings window."""
        if not self._win:
            self._win = SettingsWindow(self.app)
            self._win.theme_changed.connect(self.theme_changed)
            self._win.data_changed.connect(self.data_changed)
        if not self._win.isVisible():
            self._win.resize(380, self.app.height())
            self._win.slide_in()
        # Immediately navigate back to commands so the main window looks right
        # Go back to commands without triggering panel transition
        QTimer.singleShot(50, lambda: self.app._stack.setCurrentIndex(
            list(self.app._panels.keys()).index('commands')
            if hasattr(self.app, '_panels') else 0))

    def set_palette(self, p):
        if self._win:
            self._win.set_palette(p)
