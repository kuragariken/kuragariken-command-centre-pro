"""panels/commands.py — Grid layout with working category pills."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QLineEdit, QScrollArea, QFrame, QMenu, QDialog, QTextEdit,
    QComboBox, QMessageBox, QGridLayout, QSizePolicy, QInputDialog,
    QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui  import QFont, QColor, QCursor
from src import data as D
from src.widgets.hover_card import HoverCard
from src.widgets.command_tag import CommandTag
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


def _row_widget(row_layout) -> QWidget:
    """Wrap an HBoxLayout in a plain widget so a row of flowing tags can be
    added to the outer QVBoxLayout with addWidget (matching the approved
    design's per-row structure)."""
    w = QWidget()
    w.setStyleSheet("background:transparent;")
    w.setLayout(row_layout)
    return w


def _clear_layout(layout):
    """Recursively delete every widget inside a layout (and any nested
    row layouts within it) — needed now that the grid is a stack of row
    widgets rather than a flat QGridLayout of direct widget cells."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


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
        # A real framed input instead of an icon+field floating on nothing —
        # this is the app's primary entry point, so it earns a proper look:
        # soft inset field, hover lift, and an accent glow when focused.
        sw = QWidget(); sw.setFixedHeight(52)
        sw.setStyleSheet("background:transparent;")
        outer_sl = QHBoxLayout(sw)
        outer_sl.setContentsMargins(10, 8, 10, 8); outer_sl.setSpacing(8)

        self._search_field = QWidget()
        self._search_field.setObjectName("SearchField")
        self._search_field.setStyleSheet(
            "#SearchField{background:rgba(255,255,255,0.04);"
            "border:1px solid rgba(255,255,255,0.09);border-radius:12px;}"
            "#SearchField:hover{border-color:rgba(255,255,255,0.16);}")
        sl = QHBoxLayout(self._search_field)
        sl.setContentsMargins(12, 0, 8, 0); sl.setSpacing(8)
        icon = QLabel("⌕"); icon.setFixedWidth(18)
        icon.setStyleSheet("background:transparent;color:#5a6b80;font-size:16px;border:none;")
        sl.addWidget(icon)
        self._search_bar = QLineEdit()
        self._search_bar.setPlaceholderText("Search commands, #tags…")
        self._search_bar.setStyleSheet(
            "QLineEdit{background:transparent;border:none;color:#d4dfe9;"
            "font-size:13px;selection-background-color:rgba(0,232,122,0.3);}")
        self._search_bar.textChanged.connect(self._on_search)
        self._search_bar.focusInEvent = self._wrap_search_focus(
            self._search_bar.focusInEvent, True)
        self._search_bar.focusOutEvent = self._wrap_search_focus(
            self._search_bar.focusOutEvent, False)
        sl.addWidget(self._search_bar, 1)

        add_btn = QPushButton("+ Add"); add_btn.setFixedSize(70, 34)
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_btn.setStyleSheet(
            "QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #00e87a,stop:1 #00c96b);color:#062015;border:none;"
            "border-radius:9px;font-weight:700;font-size:11px;}"
            "QPushButton:hover{background:qlineargradient(x1:1,y1:1,x2:0,y2:0,"
            "stop:0 #00e87a,stop:1 #00c96b);}"
            "QPushButton:pressed{background:#00cc6a;}")
        _add_glow = QGraphicsDropShadowEffect(add_btn)
        _add_glow.setColor(QColor(0, 232, 122, 90))
        _add_glow.setBlurRadius(14)
        _add_glow.setOffset(0, 4)
        add_btn.setGraphicsEffect(_add_glow)
        add_btn.clicked.connect(self._add_command)
        # Add button sits INSIDE the same bordered glass box as the search
        # input (matching the approved design's single-container structure),
        # not as a separate element floating outside it.
        sl.addWidget(add_btn)

        outer_sl.addWidget(self._search_field, 1)
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

        self._grid_w = QWidget()
        self._grid_w.setObjectName("CommandGridPanel")
        self._grid_w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._grid_w.setStyleSheet(
            "#CommandGridPanel{background:rgba(255,255,255,0.018);"
            "border:1px solid rgba(255,255,255,0.06);border-radius:13px;}")
        # A vertical stack of flowing HBoxLayout rows, NOT a rigid QGridLayout
        # with stretched-equal columns. Each command tag now sizes to its own
        # text (see CommandTag.sizeHint) so short labels stay compact and
        # long ones don't force everything else in the row to match their
        # width — matching the approved design's natural "tag cloud" flow.
        self._grid = QVBoxLayout(self._grid_w)
        self._grid.setContentsMargins(12, 12, 12, 12); self._grid.setSpacing(8)
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
            f"QPushButton{{background:transparent;color:#3a4e64;border:none;"
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

    def _wrap_search_focus(self, original_handler, focused):
        """Wrap the search field's focus events to glow its border while
        the cursor is active in it, and settle back to a quiet frame on blur."""
        def handler(event):
            if focused:
                self._search_field.setStyleSheet(
                    "#SearchField{background:rgba(255,255,255,0.05);"
                    "border:1px solid rgba(0,232,122,0.5);border-radius:12px;}")
            else:
                self._search_field.setStyleSheet(
                    "#SearchField{background:rgba(255,255,255,0.04);"
                    "border:1px solid rgba(255,255,255,0.09);border-radius:12px;}"
                    "#SearchField:hover{border-color:rgba(255,255,255,0.16);}")
            return original_handler(event)
        return handler

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

        p       = self._palette
        accent  = p.get("accent", "#00e87a")
        accent2 = p.get("accent2", p.get("blue", accent))
        text_c  = p.get("text",   "#d4dfe9")

        for cat in self.app.data.get("categories", []):
            count  = len(self.app.data.get("commands",{}).get(cat,[]))
            active = (cat == self._current_cat)

            box = QWidget()
            box.setFixedHeight(30)
            box.setCursor(Qt.CursorShape.PointingHandCursor)
            box.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            box.setObjectName("CatPill")
            if active:
                # One shared brand gradient for every active pill — not a
                # different hue per category — but a REAL two-tone gradient
                # fill, not just a subtle border change, so the selected
                # category clearly pops against the neutral inactive ones.
                box.setStyleSheet(
                    "#CatPill{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    f"stop:0 rgba({QColor(accent).red()},{QColor(accent).green()},{QColor(accent).blue()},40),"
                    f"stop:1 rgba({QColor(accent2).red()},{QColor(accent2).green()},{QColor(accent2).blue()},25));"
                    f"border:1px solid {accent}77;border-radius:10px;}}")
            else:
                box.setStyleSheet(
                    "#CatPill{background:rgba(255,255,255,0.035);"
                    "border:1px solid rgba(255,255,255,0.09);border-radius:10px;}"
                    "#CatPill:hover{background:rgba(255,255,255,0.06);"
                    "border-color:rgba(255,255,255,0.18);}")

            bl = QHBoxLayout(box)
            bl.setContentsMargins(6, 4, 13, 4)
            bl.setSpacing(8)

            badge = QLabel(str(count))
            badge.setFixedSize(22, 22)
            badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            badge.setStyleSheet(
                f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                f"stop:0 {accent},stop:1 {accent2});"
                f"color:#062015;border-radius:7px;font-size:10px;"
                f"font-weight:800;border:none;")
            bl.addWidget(badge)

            lbl = QLabel(cat)
            lbl.setStyleSheet(
                f"background:transparent;color:{'#eef3f7' if active else '#9aa9bb'};"
                f"font-size:11px;font-weight:700;border:none;")
            bl.addWidget(lbl)

            def _pill_click(e, c=cat, b=box):
                if e.button() == Qt.MouseButton.LeftButton:
                    self._bounce(b)
                    self._select_cat(c)
            box.mousePressEvent = _pill_click
            box.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            box.customContextMenuRequested.connect(lambda pos, c=cat: self._cat_ctx(c))
            self._cat_lay.addWidget(box)

        # + Category button
        add_c = QPushButton("+ Category")
        add_c.setFixedHeight(26)
        add_c.setFont(QFont("Inter", 10))
        add_c.setStyleSheet(
            f"QPushButton{{background:transparent;color:#3a4e64;"
            f"border:1px solid rgba(255,255,255,0.10);border-radius:13px;"
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
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _clear_layout(item.layout())

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
                f"background:transparent;color:#3a4e64;font-size:12px;"
                f"border:none;font-family:{FONT};")
            self._grid.addWidget(lbl)
            self._grid_w.setMinimumHeight(80)
            return

        BTN_H  = 40
        FONT_SZ = 9
        FONT_W  = 500
        # How many tags fit per row is based on the panel's own width, not a
        # fixed column count — a flowing wrap, not a rigid grid.
        avail_w = max(self._scroll.viewport().width() - 24, 300)
        # Rotating palette for the cap colour — the approved design used
        # varied colours per command tile for visual rhythm (distinct from
        # the category-pill "don't colour-code" decision, which was about a
        # different element). Falls back to the single accent if a theme is
        # missing some of these keys.
        _tag_palette = [c for c in [
            p.get("green", accent), p.get("blue", accent),
            p.get("purple", accent), p.get("amber", accent),
            p.get("red", accent),
        ] if c]
        if not _tag_palette:
            _tag_palette = [accent]

        row = None
        row_w = 0
        row_count = 0
        for i, cmd in enumerate(cmds):
            label  = cmd.get("label","")
            txt    = cmd.get("text","")
            pcolor = PRIORITY_COLORS.get(cmd.get("priority","NORMAL"),"")
            accent2 = p.get("accent2", p.get("blue", accent))
            cap_accent = _tag_palette[i % len(_tag_palette)]
            row_bg  = card if row_count % 2 == 0 else _tint(card, 8)
            btn = CommandTag(label, accent=cap_accent, bg=row_bg,
                            border=border, priority_color=pcolor,
                            accent2=accent2)
            btn.setFixedHeight(BTN_H)
            _tag_font = QFont()
            _tag_font.setFamilies(["Manrope", "Segoe UI Semibold", "Segoe UI Variable Text", "Segoe UI"])
            _tag_font.setPointSize(FONT_SZ)
            _tag_font.setWeight(QFont.Weight(FONT_W))
            btn.setFont(_tag_font)
            btn.setWindowOpacity(0.0)
            try:
                from src.widgets.hover_lift import add_hover_lift
                add_hover_lift(btn, lift=2, shadow_color=cap_accent)
            except Exception:
                pass
            btn.clicked.connect(lambda checked, l=label, t=txt: self._copy(l, t))
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(
                lambda pos, c=cmd: self._cmd_ctx(c))

            tag_w = btn.sizeHint().width()
            if row is None or row_w + tag_w + 8 > avail_w:
                row = QHBoxLayout(); row.setSpacing(8)
                self._grid.addWidget(_row_widget(row))
                row_w = 0
                row_count += 1
            row.addWidget(btn)
            row_w += tag_w + 8

            # Staggered fade-in entrance
            QTimer.singleShot(i * 18, lambda b=btn: self._fade_in_btn(b))

        if row is not None:
            row.addStretch()
        # No manual height calculation here — rows wrap dynamically based on
        # the ACTUAL runtime width, so any pre-computed row-count formula can
        # drift out of sync with what really gets rendered (that drift is
        # exactly what caused rows to overlap the footer below the panel).
        # Letting the QVBoxLayout size itself from its real child rows, with
        # the surrounding QScrollArea (setWidgetResizable=True) handling any
        # overflow via scrolling, is the robust fix.
        self._grid_w.updateGeometry()

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
        # Update command-tag colours on existing grid buttons — now that the
        # grid is a stack of flowing ROW widgets (not a flat grid of direct
        # button cells), recurse one level into each row to find them.
        for i in range(self._grid.count()):
            row_item = self._grid.itemAt(i)
            row_w = row_item.widget() if row_item else None
            row_layout = row_w.layout() if row_w else None
            if not row_layout:
                continue
            for j in range(row_layout.count()):
                cell = row_layout.itemAt(j)
                if cell and cell.widget() and hasattr(cell.widget(), 'set_colours'):
                    cell.widget().set_colours(accent, bg, border, text)
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
                         "border-radius:7px;padding:6px 18px;font-weight:700;}"
                         "QPushButton:hover{background:#00ff88;}")
        ok.clicked.connect(self.accept); br.addWidget(ok); lay.addLayout(br)

    def _lbl(self, t):
        l = QLabel(t); l.setStyleSheet(
            f"background:transparent;color:#3a4e64;font-size:9px;"
            f"font-weight:700;letter-spacing:2px;border:none;font-family:{FONT};")
        return l

    def get_command(self):
        return {"label": self._label.text().strip(), "text": self._text.toPlainText().strip(),
                "notes": self._notes.text().strip(), "tags": self._cmd.get("tags",""),
                "priority": self._pri.currentText()}

    def get_category(self): return self._cat.currentText()
