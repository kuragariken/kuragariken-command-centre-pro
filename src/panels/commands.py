"""panels/commands.py — Grid layout with working category pills."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QScrollArea, QFrame, QMenu, QDialog, QTextEdit,
    QComboBox, QMessageBox, QGridLayout, QSizePolicy, QInputDialog
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui  import QFont, QColor, QCursor
from src import data as D
from src.widgets.hover_card import HoverCard
from src.widgets.auto_scroll import AutoHideScrollBar

def _tint(hex_color: str, amount: int) -> str:
    """Lighten a hex colour by amount (0-255)."""
    try:
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        r = min(255, r + amount)
        g = min(255, g + amount)
        b = min(255, b + amount)
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


PRIORITY_COLORS = {
    "URGENT": "#f87171",
    "INFO":   "#38bdf8",
    "DONE":   "#00e87a",
    "NORMAL": "",
}
FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"


class CommandsPanel(QWidget):
    copy_requested = pyqtSignal(str, str, str)

    def __init__(self, app):
        super().__init__()
        self.app          = app
        self._current_cat = None
        self._search_text = ""
        self._palette     = {}
        self._build_ui()

    # ──────────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet("background:transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Search ──────────────────────────────────────────
        sw = QWidget(); sw.setFixedHeight(44)
        sw.setStyleSheet("background:transparent;")
        sl = QHBoxLayout(sw); sl.setContentsMargins(10,6,10,6); sl.setSpacing(6)
        icon = QLabel("⌕"); icon.setFixedWidth(18)
        icon.setStyleSheet("background:transparent;color:#6e7d90;font-size:15px;border:none;")
        sl.addWidget(icon)
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Search commands, #tags…")
        self._search_bar.textChanged.connect(self._on_search)
        sl.addWidget(self._search_bar, 1)
        add_btn = QPushButton("+ Add"); add_btn.setFixedSize(64, 30)
        add_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:8px;font-weight:700;font-size:11px;}"
            "QPushButton:hover{background:#00ff88;}")
        add_btn.clicked.connect(self._add_command)
        sl.addWidget(add_btn)
        root.addWidget(sw)

        # ── Category pills — plain QHBoxLayout, NO scroll area ──
        self._cat_row = QWidget(); self._cat_row.setFixedHeight(38)
        self._cat_row.setStyleSheet("background:transparent;")
        self._cat_lay = QHBoxLayout(self._cat_row)
        self._cat_lay.setContentsMargins(10, 5, 10, 5)
        self._cat_lay.setSpacing(6)
        self._cat_lay.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(self._cat_row)

        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet("background:rgba(255,255,255,0.07);")
        root.addWidget(sep)

        # ── Grid ────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:transparent;width:0px;border:none;}"
            "QScrollBar::handle:vertical{background:transparent;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")

        self._grid_w = QWidget(); self._grid_w.setStyleSheet("background:transparent;")
        self._grid   = QGridLayout(self._grid_w)
        self._grid.setContentsMargins(8,8,8,8); self._grid.setSpacing(6)
        for _c in range(6):
            self._grid.setColumnStretch(_c, 1)
        self._scroll.setWidget(self._grid_w)
        root.addWidget(self._scroll, 1)
        # Auto-hide scrollbar overlay
        self._autoscroll = AutoHideScrollBar(self._scroll)

        # ── Footer ──────────────────────────────────────────
        ft = QWidget(); ft.setFixedHeight(30)
        ft.setStyleSheet("background:rgba(5,8,16,0.85);border-top:1px solid rgba(255,255,255,0.05);")
        fl = QHBoxLayout(ft); fl.setContentsMargins(10,4,10,4)
        add_c = QPushButton("+ Add Command")
        add_c.setStyleSheet(
            f"QPushButton{{background:transparent;color:#6b83a0;border:none;"
            f"font-size:10px;font-family:{FONT};}}"
            f"QPushButton:hover{{color:#9ca3af;}}")
        add_c.clicked.connect(self._add_command)
        fl.addWidget(add_c); fl.addStretch()
        root.addWidget(ft)

    # ── Refresh ──────────────────────────────────────────────
    def refresh(self):
        self._rebuild_cat_pills()
        if not self._current_cat:
            cats = self.app.data.get("categories", [])
            self._current_cat = cats[0] if cats else None
        self._rebuild_grid()

    def _on_search(self, text):
        self._search_text = text; self._rebuild_grid()

    def _select_cat(self, cat):
        self._current_cat = cat
        self._rebuild_cat_pills()
        self._rebuild_grid()

    # ── Category pills ───────────────────────────────────────
    def _rebuild_cat_pills(self):
        # Remove all widgets from layout
        while self._cat_lay.count():
            item = self._cat_lay.takeAt(0)
            w = item.widget()
            if w: w.deleteLater()

        p      = self._palette
        accent = p.get("accent", "#00e87a")
        text_c = p.get("text",   "#d4dfe9")

        for cat in self.app.data.get("categories", []):
            count  = len(self.app.data.get("commands",{}).get(cat,[]))
            label  = f"{cat}  {count}" if count else cat
            active = (cat == self._current_cat)
            btn    = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setFont(QFont("Inter", 10))
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            if active:
                accent2 = p.get("accent2", p.get("blue", accent))
                btn.setStyleSheet(
                    f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    f"stop:0 {accent},stop:1 {accent2});"
                    f"color:#060a10;border:none;"
                    f"border-radius:12px;padding:2px 14px;font-size:10px;font-weight:700;}}"
                    f"QPushButton:hover{{background:qlineargradient(x1:1,y1:0,x2:0,y2:1,"
                    f"stop:0 {accent},stop:1 {accent2});}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:rgba(255,255,255,0.07);color:{text_c};"
                    f"border:1px solid rgba(255,255,255,0.13);"
                    f"border-radius:12px;padding:2px 12px;font-size:10px;font-weight:500;}}"
                    f"QPushButton:hover{{color:{accent};border-color:{accent};"
                    f"background:rgba(255,255,255,0.12);}}")
            btn.clicked.connect(lambda checked, c=cat, b=btn: (
                self._bounce(b), self._select_cat(c)))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, c=cat: self._cat_ctx(c))
            self._cat_lay.addWidget(btn)

        # + Category button
        add_c = QPushButton("+ Category")
        add_c.setFixedHeight(26)
        add_c.setFont(QFont("Inter", 10))
        add_c.setStyleSheet(
            f"QPushButton{{background:transparent;color:#6b83a0;"
            f"border:1px solid rgba(255,255,255,0.10);border-radius:12px;"
            f"padding:2px 10px;font-size:10px;}}"
            f"QPushButton:hover{{color:{text_c};border-color:rgba(255,255,255,0.25);}}")
        add_c.clicked.connect(self._add_category)
        self._cat_lay.addWidget(add_c)
        self._cat_lay.addStretch()

    # ── Grid ─────────────────────────────────────────────────
    def _bounce(self, btn):
        """Micro-bounce: scale 95%→100% via geometry shrink/expand."""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QRect
            orig = btn.geometry()
            dx = orig.width() * 0.025
            dy = orig.height() * 0.025
            small = QRect(int(orig.x()+dx), int(orig.y()+dy),
                          int(orig.width()-dx*2), int(orig.height()-dy*2))
            a = QPropertyAnimation(btn, b"geometry")
            a.setDuration(120)
            a.setKeyValueAt(0.0, orig)
            a.setKeyValueAt(0.4, small)
            a.setKeyValueAt(1.0, orig)
            a.setEasingCurve(QEasingCurve.Type.OutBack)
            a.start()
            btn._bounce_anim = a
        except Exception:
            pass

    def _rebuild_grid(self):
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()

        cmds = self._get_commands()
        p      = self._palette
        accent = p.get("accent", "#00e87a")
        card   = p.get("card",   "#0d1520")
        border = p.get("border", "#172338")
        text_c = p.get("text",   "#d4dfe9")

        if not cmds:
            lbl = QLabel("No commands yet.\nClick + Add Command to create one.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"background:transparent;color:#6b83a0;font-size:12px;"
                f"border:none;font-family:{FONT};")
            self._grid.addWidget(lbl, 0, 0, 1, 6)
            self._grid_w.setFixedHeight(80)
            return

        COLS   = 6
        BTN_H  = 40
        FONT_SZ = 9
        FONT_W  = 500
        for i, cmd in enumerate(cmds):
            label  = cmd.get("label","")
            txt    = cmd.get("text","")
            pcolor = PRIORITY_COLORS.get(cmd.get("priority","NORMAL"),"")
            accent2 = p.get("accent2", p.get("blue", accent))
            # Subtle row tint — even rows slightly lighter for grid separation
            row_idx = i // COLS
            row_bg  = card if row_idx % 2 == 0 else _tint(card, 8)
            btn = HoverCard(label, accent=accent, bg=row_bg,
                            border=border, priority_color=pcolor,
                            accent2=accent2)
            btn.setFixedHeight(BTN_H)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFont(QFont("Segoe UI Variable Text", FONT_SZ, FONT_W))
            btn.setWindowOpacity(0.0)
            btn.clicked.connect(lambda checked, l=label, t=txt: self._copy(l, t))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, c=cmd: self._cmd_ctx(c))
            self._grid.addWidget(btn, i // COLS, i % COLS)
            # Staggered fade-in entrance
            QTimer.singleShot(i * 18, lambda b=btn: self._fade_in_btn(b))

        rows = (len(cmds) + COLS - 1) // COLS
        self._grid_w.setFixedHeight(rows * BTN_H + rows * 8 + 16)

    def _get_commands(self):
        s = self._search_text.strip().lower()
        if s:
            out = []
            for cmds in self.app.data.get("commands",{}).values():
                for c in cmds:
                    if (s in c.get("label","").lower() or
                        s in c.get("text","").lower() or
                        s in c.get("tags","").lower()):
                        out.append(c)
            return out
        if self._current_cat:
            return self.app.data.get("commands",{}).get(self._current_cat,[])
        return []

    def _fade_in_btn(self, btn):
        """Fade a button in from 0 to 1 opacity."""
        try:
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            a = QPropertyAnimation(btn, b"windowOpacity")
            a.setDuration(180)
            a.setStartValue(0.0)
            a.setEndValue(1.0)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            a.start()
            btn._fade_anim = a  # keep reference
        except Exception:
            pass

    def _copy(self, label, text):
        if hasattr(self.app,"set_copy_pos"):
            self.app.set_copy_pos(QCursor.pos())
        self.copy_requested.emit(label, text, self._current_cat or "")

    # ── Context menus ────────────────────────────────────────
    def _cat_ctx(self, cat):
        m = QMenu(self)
        m.addAction("Rename", lambda: self._rename_cat(cat))
        m.addAction("Delete", lambda: self._delete_cat(cat))
        m.exec(QCursor.pos())

    def _cmd_ctx(self, cmd):
        m = QMenu(self)
        label = cmd.get("label", "")

        # Quick launch pin/unpin
        ql = self.app.data.get("quick_launch", [])
        if label in ql:
            m.addAction("⚡  Remove from Quick Launch",
                        lambda: self._ql_remove(label))
        else:
            m.addAction("⚡  Pin to Quick Launch",
                        lambda: self._ql_add(label))

        m.addSeparator()
        m.addAction("Edit",   lambda: self._edit_cmd(cmd))
        m.addAction("Delete", lambda: self._delete_cmd(cmd))
        m.exec(QCursor.pos())

    def _ql_add(self, label: str):
        ql = self.app.data.setdefault("quick_launch", [])
        if label not in ql:
            ql.append(label)
            D.save(self.app.data)
            # Refresh quick launch bar if open
            if hasattr(self.app, "_ql_bar") and self.app._ql_bar:
                self.app._ql_bar.refresh()
            self.app.toast.show_toast(f"Pinned: {label}")

    def _ql_remove(self, label: str):
        ql = self.app.data.get("quick_launch", [])
        if label in ql:
            ql.remove(label)
            D.save(self.app.data)
            if hasattr(self.app, "_ql_bar") and self.app._ql_bar:
                self.app._ql_bar.refresh()
            self.app.toast.show_toast(f"Unpinned: {label}")

    # ── CRUD ─────────────────────────────────────────────────
    def _add_category(self):
        name, ok = QInputDialog.getText(self, "New Category", "Category name:")
        if ok and name.strip():
            n = name.strip()
            cats = self.app.data.setdefault("categories", [])
            if n not in cats:
                cats.append(n)
                self.app.data.setdefault("commands", {})[n] = []
                D.save(self.app.data)
                self._current_cat = n
                self.refresh()

    def _rename_cat(self, old):
        new, ok = QInputDialog.getText(self, "Rename", "New name:", text=old)
        if ok and new.strip() and new != old:
            cats = self.app.data.get("categories", [])
            cmds = self.app.data.get("commands", {})
            if old in cats: cats[cats.index(old)] = new
            if old in cmds: cmds[new] = cmds.pop(old)
            if self._current_cat == old: self._current_cat = new
            D.save(self.app.data); self.refresh()

    def _delete_cat(self, cat):
        r = QMessageBox.question(self, "Delete", f"Delete '{cat}' and all commands?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            cats = self.app.data.get("categories", [])
            if cat in cats: cats.remove(cat)
            self.app.data.get("commands", {}).pop(cat, None)
            if self._current_cat == cat:
                self._current_cat = cats[0] if cats else None
            D.save(self.app.data); self.refresh()

    def _add_command(self):
        dlg = CommandDialog(self, None, self.app.data.get("categories",[]),
                            self._current_cat or "")
        if dlg.exec():
            cmd = dlg.get_command(); cat = dlg.get_category()
            self.app.data.setdefault("commands",{}).setdefault(cat,[]).append(cmd)
            if cat not in self.app.data.setdefault("categories",[]): 
                self.app.data["categories"].append(cat)
            D.save(self.app.data); self._current_cat = cat; self.refresh()

    def _edit_cmd(self, cmd):
        dlg = CommandDialog(self, cmd, self.app.data.get("categories",[]),
                            self._current_cat or "")
        if dlg.exec():
            updated = dlg.get_command(); cat = dlg.get_category()
            for cc in self.app.data.get("commands",{}).values():
                if cmd in cc: cc.remove(cmd); break
            self.app.data.setdefault("commands",{}).setdefault(cat,[]).append(updated)
            D.save(self.app.data); self.refresh()

    def _delete_cmd(self, cmd):
        for cc in self.app.data.get("commands",{}).values():
            if cmd in cc: cc.remove(cmd); break
        D.save(self.app.data); self.refresh()

    def set_palette(self, p):
        self._palette = p
        accent  = p.get('accent', '#00e87a')
        accent2 = p.get('accent2', accent)
        bg      = p.get('card',   '#0d1520')
        border  = p.get('border', '#172338')
        text    = p.get('text',   '#d4dfe9')
        # Update scrollbar accent immediately
        if hasattr(self, '_autoscroll'):
            self._autoscroll._accent  = accent
            self._autoscroll._accent2 = accent2
            self._autoscroll.update()
        # Update HoverCard colours on existing grid buttons
        for i in range(self._grid.count()):
            item = self._grid.itemAt(i)
            if item and item.widget() and hasattr(item.widget(), 'set_colours'):
                item.widget().set_colours(accent, bg, border, text)
        self.refresh()


# ── CommandDialog ────────────────────────────────────────────────
class CommandDialog(QDialog):
    def __init__(self, parent, cmd, categories, current_cat=""):
        super().__init__(parent)
        self._cmd  = cmd or {}; self._cats = categories; self._cur = current_cat
        self.setWindowTitle("Add Command" if not cmd else "Edit Command")
        self.setModal(True); self.resize(500, 340)
        lay = QVBoxLayout(self); lay.setContentsMargins(18,18,18,14); lay.setSpacing(10)
        sty = (f"QLineEdit,QTextEdit{{background:#0a101a;color:#d4dfe9;"
               f"border:1px solid #1a2840;border-radius:8px;"
               f"padding:6px 10px;font-size:12px;font-family:{FONT};}}"
               f"QLineEdit:focus,QTextEdit:focus{{border-color:#00e87a;}}")
        lay.addWidget(self._lbl("LABEL"))
        self._label = QLineEdit(self._cmd.get("label",""))
        self._label.setFixedHeight(36); self._label.setStyleSheet(sty); lay.addWidget(self._label)
        lay.addWidget(self._lbl("COMMAND TEXT"))
        self._text = QTextEdit(self._cmd.get("text",""))
        self._text.setFixedHeight(100); self._text.setStyleSheet(sty); lay.addWidget(self._text)
        row = QHBoxLayout(); row.setSpacing(10)
        cc = QVBoxLayout(); cc.addWidget(self._lbl("CATEGORY"))
        self._cat = QComboBox()
        for c in self._cats: self._cat.addItem(c)
        if self._cur in self._cats: self._cat.setCurrentText(self._cur)
        self._cat.setStyleSheet(
            f"QComboBox{{background:#0a101a;color:#d4dfe9;border:1px solid #1a2840;"
            f"border-radius:8px;padding:5px 10px;font-size:12px;font-family:{FONT};}}"
            f"QComboBox QAbstractItemView{{background:#0a101a;color:#d4dfe9;"
            f"border:1px solid #1a2840;selection-background-color:#182030;}}")
        cc.addWidget(self._cat); row.addLayout(cc,1)
        pc = QVBoxLayout(); pc.addWidget(self._lbl("PRIORITY"))
        self._pri = QComboBox(); self._pri.addItems(["NORMAL","URGENT","INFO","DONE"])
        self._pri.setCurrentText(self._cmd.get("priority","NORMAL"))
        self._pri.setStyleSheet(self._cat.styleSheet()); pc.addWidget(self._pri); row.addLayout(pc,1)
        lay.addLayout(row)
        nc = QVBoxLayout(); nc.addWidget(self._lbl("NOTES (optional)"))
        self._notes = QLineEdit(self._cmd.get("notes",""))
        self._notes.setFixedHeight(34); self._notes.setStyleSheet(sty); nc.addWidget(self._notes)
        lay.addLayout(nc)
        br = QHBoxLayout(); br.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject); br.addWidget(cancel)
        ok = QPushButton("Save")
        ok.setStyleSheet("QPushButton{background:#00e87a;color:#080b12;border:none;"
                         "border-radius:8px;padding:6px 18px;font-weight:700;}"
                         "QPushButton:hover{background:#00ff88;}")
        ok.clicked.connect(self.accept); br.addWidget(ok); lay.addLayout(br)

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet(
            f"background:transparent;color:#6b83a0;font-size:9px;"
            f"font-weight:700;letter-spacing:2px;border:none;font-family:{FONT};")
        return l

    def get_command(self):
        return {"label": self._label.text().strip(), "text": self._text.toPlainText().strip(),
                "notes": self._notes.text().strip(), "tags": self._cmd.get("tags",""),
                "priority": self._pri.currentText()}

    def get_category(self): return self._cat.currentText()
