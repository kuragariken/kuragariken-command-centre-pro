"""
notepad.py — Floating notepad window with throw-out / throw-back animations,
shimmer header, syntax highlighting, multi-tab, autosave, search/replace.
"""
import os
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QPlainTextEdit, QTabWidget, QLineEdit, QFrame,
    QDialog, QMessageBox, QFileDialog, QApplication, QSizeGrip
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint,
    QRect, QSize, pyqtSignal, QParallelAnimationGroup
)
from PyQt6.QtGui import (
    QFont, QColor, QSyntaxHighlighter, QTextCharFormat,
    QPainter, QPainterPath
)
from src import data as D
from src.widgets.accent_line import AccentLine
from src.widgets.glow_button import GlowButton

# Premium font constants — used throughout this module
FONT_BODY = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"
FONT_MONO = "'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace"


class NoteHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc)
        import re
        self._rules = [
            (re.compile(r'https?://\S+'),                          "#38bdf8"),
            (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), "#a78bfa"),
            (re.compile(r'\b(INC|TASK|CHG|PRB|REQ)-?\d{4,}\b', re.I), "#fbbf24"),
            (re.compile(r'\b\d{2}:\d{2}(:\d{2})?\b'),              "#00e87a"),
            (re.compile(r'\b[A-Z]{3,}\b'),                          "#f87171"),
        ]
    def highlightBlock(self, text):
        for pat, col in self._rules:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(col))
            for m in pat.finditer(text):
                self.setFormat(m.start(), m.end() - m.start(), fmt)


class NoteTab(QWidget):
    changed = pyqtSignal()
    def __init__(self, title="Note", content=""):
        super().__init__()
        self.title  = title
        self._saved = True
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Mini toolbar
        tb = QWidget()
        tb.setFixedHeight(32)
        tb.setStyleSheet("background:rgba(6,10,18,0.85); border-bottom:1px solid rgba(255,255,255,0.07);")
        tl = QHBoxLayout(tb)
        tl.setContentsMargins(8, 3, 8, 3)
        tl.setSpacing(5)

        for label, fn in [
            ("+ Timestamp", self._ts),
            ("Copy All", self._copy_all),
            ("Export", self._export),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setStyleSheet(
                "QPushButton{background:#0d1520;color:#4a5568;border:1px solid #1a2535;"
                "border-radius:5px;padding:0 10px;font-size:10px;font-weight:600;"
                "font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;}"
                "QPushButton:hover{background:#131e2e;color:#8899aa;border-color:#2d4060;}")
            b.clicked.connect(fn)
            tl.addWidget(b)
        tl.addStretch()

        self._wc = QLabel("0 words")
        self._wc.setStyleSheet("background:transparent;color:#2d4060;font-size:10px;font-weight:500;border:none;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;")
        tl.addWidget(self._wc)
        lay.addWidget(tb)

        self._ed = QPlainTextEdit(content)
        self._ed.setFont(QFont("JetBrains Mono", 11))
        self._ed.setStyleSheet(
            "QPlainTextEdit{background:#080b12;color:#c8d8e8;border:none;"
            "padding:16px 20px;"
            "font-family:'JetBrains Mono','Cascadia Code','Fira Code','JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace;"
            "font-size:12px;line-height:1.7;"
            "selection-background-color:#00e87a;selection-color:#080b12;}"
            "QScrollBar:vertical{background:#080b12;width:5px;margin:0;}"
            "QScrollBar::handle:vertical{background:#1a2535;border-radius:2px;min-height:30px;}"
            "QScrollBar::handle:vertical:hover{background:#2d4060;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self._ed.textChanged.connect(self._ch)
        NoteHighlighter(self._ed.document())
        lay.addWidget(self._ed, 1)

    def _ch(self):
        self._saved = False
        t = self._ed.toPlainText()
        w = len(t.split()) if t.strip() else 0
        self._wc.setText(f"{w} words  ·  {len(t)} chars")
        self.changed.emit()

    def _ts(self):
        self._ed.insertPlainText(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ")

    def _copy_all(self):
        QApplication.clipboard().setText(self._ed.toPlainText())

    def _export(self):
        p, _ = QFileDialog.getSaveFileName(None, "Export", f"{self.title}.txt", "Text (*.txt)")
        if p:
            open(p, "w", encoding="utf-8").write(self._ed.toPlainText())

    def content(self): return self._ed.toPlainText()
    def set_content(self, t): self._ed.setPlainText(t)


class NotepadWindow(QWidget):
    """
    Floating, resizable notepad window.
    Throws out from the main window and throws back on close.
    """
    def __init__(self, app_win, parent=None):
        super().__init__(None)   # top-level window
        self._app_win    = app_win
        self._dragging   = False
        self._drag_pos   = QPoint()
        self._palette    = {}
        self._search_vis = False

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(480, 380)
        self.resize(600, 480)

        self._build_ui()

        # Autosave
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._autosave)
        self._autosave_timer.start(30000)

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Shimmer accent line
        self._accent_line = AccentLine(self)
        root.addWidget(self._accent_line)

        # Title bar
        hdr = QWidget()
        hdr.setFixedHeight(42)
        hdr.setStyleSheet("background:rgba(6,10,18,0.85); border-bottom:1px solid rgba(255,255,255,0.07);")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(14, 0, 10, 0)
        hl.setSpacing(8)

        self._accent_mark = QLabel()
        self._accent_mark.setFixedSize(3, 20)
        self._accent_mark.setStyleSheet("background:#00e87a; border-radius:1px;")
        hl.addWidget(self._accent_mark)
        hl.addSpacing(8)

        title_lbl = QLabel("NOTEPAD")
        title_lbl.setStyleSheet(
            "background:transparent;color:#00e87a;font-size:10px;"
            "font-weight:800;letter-spacing:3px;border:none;"
            "font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;")
        hl.addWidget(title_lbl)
        hl.addStretch()

        # Search toggle
        search_btn = QPushButton("⌕")
        search_btn.setFixedSize(26, 26)
        search_btn.setToolTip("Search / Replace")
        search_btn.setStyleSheet(
            "QPushButton{background:#141d2b;color:#9ca3af;border:1px solid #1f2d3d;"
            "border-radius:5px;font-size:14px;}"
            "QPushButton:hover{background:#182030;color:#e2e8f0;}")
        search_btn.clicked.connect(self._toggle_search)
        hl.addWidget(search_btn)

        new_btn = QPushButton("+ Note")
        new_btn.setFixedHeight(26)
        new_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:5px;padding:0 10px;font-size:10px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        new_btn.clicked.connect(self._new_tab)
        hl.addWidget(new_btn)
        hl.addSpacing(8)

        # Window dots
        for col, hov, slot in [
            ("#4ade80","#22c55e", self.showMinimized),
            ("#f87171","#ef4444", self._throw_back),
        ]:
            b = QPushButton()
            b.setFixedSize(12, 12)
            b.setStyleSheet(
                f"QPushButton{{background:{col};border:none;border-radius:6px;}}"
                f"QPushButton:hover{{background:{hov};}}")
            b.clicked.connect(slot)
            hl.addWidget(b)
            hl.addSpacing(4)

        root.addWidget(hdr)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setTabsClosable(True)
        self._tabs.setMovable(True)
        self._tabs.setDocumentMode(True)
        self._tabs.tabCloseRequested.connect(self._close_tab)
        _ss = (
            "QTabWidget,QTabWidget::pane{background:#080b12;border:none;margin:0;padding:0;}"
            "QTabWidget::tab-bar{background:#080b12;}"
            "QTabWidget>QWidget{background:#080b12;}"
            "QTabBar{background:#080b12;border:none;border-bottom:1px solid #1a2535;}"
            "QTabBar::tab{background:#080b12;color:#3d4f61;border:none;border-right:1px solid #1a2535;padding:7px 18px;font-size:11px;font-weight:500;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;min-width:80px;}"
            "QTabBar::tab:selected{background:#080b12;color:#00e87a;border-bottom:2px solid #00e87a;font-weight:700;}"
            "QTabBar::tab:hover:!selected{background:#0a1020;color:#8899aa;}"
            "QTabBar QToolButton{background:#080b12;border:none;}"
            "QTabBar::close-button{subcontrol-position:right;width:14px;height:14px;}"
        )
        self._tabs.setStyleSheet(_ss)
        root.addWidget(self._tabs, 1)

        # Search bar
        self._search_bar = self._make_search_bar()
        self._search_bar.setVisible(False)
        root.addWidget(self._search_bar)

        # Status
        st = QWidget()
        st.setFixedHeight(24)
        st.setStyleSheet("background:rgba(5,8,16,0.85); border-top:1px solid rgba(255,255,255,0.06);")
        sl = QHBoxLayout(st)
        sl.setContentsMargins(10, 0, 10, 0)
        self._status = QLabel("Ready")
        self._status.setStyleSheet("background:transparent;color:#2d3f50;font-size:10px;font-weight:500;border:none;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;")
        sl.addWidget(self._status)
        sl.addStretch()
        self._auto_lbl = QLabel("")
        self._auto_lbl.setStyleSheet("background:transparent;color:#2d3f50;font-size:10px;border:none;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;")
        sl.addWidget(self._auto_lbl)

        # Resize grip
        grip = QSizeGrip(self)
        grip.setFixedSize(12, 12)
        sl.addWidget(grip)
        root.addWidget(st)

    def _make_search_bar(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(36)
        w.setStyleSheet("background:#111827; border-top:1px solid #1f2d3d;")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(5)
        sty = ("QLineEdit{background:#0a1020;color:#c8d8e8;border:1px solid #1a2535;"
               "border-radius:6px;padding:4px 10px;font-size:11px;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;}"
               "QLineEdit:focus{border-color:#00e87a;}")
        self._find_ed = QLineEdit(); self._find_ed.setPlaceholderText("Find…")
        self._find_ed.setStyleSheet(sty); lay.addWidget(self._find_ed)
        self._repl_ed = QLineEdit(); self._repl_ed.setPlaceholderText("Replace…")
        self._repl_ed.setStyleSheet(sty); lay.addWidget(self._repl_ed)
        for lbl, fn in [("Find", self._do_find), ("Replace", self._do_repl),
                        ("All",  self._do_repl_all)]:
            b = QPushButton(lbl); b.setFixedHeight(24)
            b.setStyleSheet(
                "QPushButton{background:#141d2b;color:#9ca3af;border:1px solid #1f2d3d;"
                "border-radius:4px;padding:0 8px;font-size:10px;}"
                "QPushButton:hover{background:#182030;color:#e2e8f0;}")
            b.clicked.connect(fn); lay.addWidget(b)
        cx = QPushButton("✕"); cx.setFixedSize(22, 24)
        cx.setStyleSheet("QPushButton{background:transparent;color:#4a5568;border:none;}"
                         "QPushButton:hover{color:#e2e8f0;}")
        cx.clicked.connect(lambda: self._search_bar.setVisible(False))
        lay.addWidget(cx)
        return w

    def _toggle_search(self):
        self._search_vis = not self._search_vis
        self._search_bar.setVisible(self._search_vis)
        if self._search_vis: self._find_ed.setFocus()

    def _current_ed(self):
        t = self._tabs.currentWidget()
        return t._ed if isinstance(t, NoteTab) else None

    def _do_find(self):
        ed = self._current_ed()
        if ed: ed.find(self._find_ed.text())

    def _do_repl(self):
        ed = self._current_ed()
        if not ed: return
        c = ed.textCursor()
        if c.hasSelection(): c.insertText(self._repl_ed.text())
        ed.find(self._find_ed.text())

    def _do_repl_all(self):
        ed = self._current_ed()
        if not ed: return
        t = ed.toPlainText().replace(self._find_ed.text(), self._repl_ed.text())
        ed.setPlainText(t)

    def load_notes(self, app):
        notes = app.data.get("notes", [])
        if not notes:
            self._add_tab("Note 1", "")
        else:
            for n in notes:
                self._add_tab(n.get("title","Note"), n.get("content",""))

    def _add_tab(self, title: str, content: str):
        tab = NoteTab(title, content)
        tab.changed.connect(lambda: self._on_changed(tab))
        self._tabs.addTab(tab, title)

    def _new_tab(self):
        n = self._tabs.count() + 1
        self._add_tab(f"Note {n}", "")
        self._tabs.setCurrentIndex(self._tabs.count() - 1)

    def _close_tab(self, idx):
        if self._tabs.count() == 1:
            t = self._tabs.widget(0)
            if isinstance(t, NoteTab): t.set_content("")
            return
        self._tabs.removeTab(idx)

    def _on_changed(self, tab):
        idx = self._tabs.indexOf(tab)
        if idx >= 0:
            self._tabs.setTabText(idx, f"● {tab.title}")

    def _autosave(self):
        self._save_notes()
        now = datetime.now().strftime("%H:%M:%S")
        self._auto_lbl.setText(f"Saved {now}")
        QTimer.singleShot(3000, lambda: self._auto_lbl.setText(""))

    def _save_notes(self):
        app = self._app_win
        notes = []
        for i in range(self._tabs.count()):
            t = self._tabs.widget(i)
            if isinstance(t, NoteTab):
                title = self._tabs.tabText(i).lstrip("● ")
                notes.append({"title": title, "content": t.content()})
        app.data["notes"] = notes
        D.save(app.data)

    def set_palette(self, p):
        self._palette = p
        accent = p.get("accent", "#00e87a")
        self._accent_line.set_accent(accent)
        self._accent_mark.setStyleSheet(f"background:{accent}; border-radius:1px;")

    # ── THROW ANIMATION ───────────────────────────────────────────
    def throw_out(self, origin: QPoint):
        """Animate flying out from the main window origin point."""
        screen  = QApplication.primaryScreen().availableGeometry()
        final_x = max(screen.left(), min(screen.center().x() - self.width()//2,
                      screen.right() - self.width()))
        final_y = max(screen.top(), min(screen.center().y() - self.height()//2,
                      screen.bottom() - self.height()))

        self.move(origin.x(), origin.y())
        self.setWindowOpacity(0)
        self.show()

        # Position animation — fly from origin to centre
        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(380)
        pos_anim.setStartValue(QPoint(origin.x(), origin.y()))
        pos_anim.setEndValue(QPoint(final_x, final_y))
        pos_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        # Opacity animation — fade in
        op_anim = QPropertyAnimation(self, b"windowOpacity")
        op_anim.setDuration(280)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._throw_group = QParallelAnimationGroup()
        self._throw_group.addAnimation(pos_anim)
        self._throw_group.addAnimation(op_anim)
        self._throw_group.start()

    def _throw_back(self):
        """Animate shrinking back toward the main window, then hide."""
        if not self._app_win:
            self.hide(); return

        self._save_notes()
        origin = self._app_win.geometry().center()

        pos_anim = QPropertyAnimation(self, b"pos")
        pos_anim.setDuration(300)
        pos_anim.setStartValue(self.pos())
        pos_anim.setEndValue(QPoint(origin.x() - 20, origin.y() - 20))
        pos_anim.setEasingCurve(QEasingCurve.Type.InBack)

        op_anim = QPropertyAnimation(self, b"windowOpacity")
        op_anim.setDuration(260)
        op_anim.setStartValue(self.windowOpacity())
        op_anim.setEndValue(0.0)
        op_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        self._close_group = QParallelAnimationGroup()
        self._close_group.addAnimation(pos_anim)
        self._close_group.addAnimation(op_anim)
        self._close_group.finished.connect(self.hide)
        self._close_group.start()

    # Drag title bar
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 44:
            self._dragging = True
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragging and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._dragging = False

    def closeEvent(self, e):
        e.ignore()
        self._throw_back()


class NotepadPanel(QWidget):
    """Thin panel that just opens/closes the floating NotepadWindow."""
    def __init__(self, app):
        super().__init__()
        self.app      = app
        self._win     = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setAlignment(Qt.AlignmentFlag.AlignCenter)

        inner = QWidget()
        inner.setStyleSheet("background:transparent;")
        il = QVBoxLayout(inner)
        il.setAlignment(Qt.AlignmentFlag.AlignCenter)
        il.setSpacing(16)

        icon = QLabel("📝")
        icon.setFont(QFont("Segoe UI Emoji", 36))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet("background:transparent;border:none;")
        il.addWidget(icon)

        lbl = QLabel("NOTEPAD")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            "background:transparent;color:#00e87a;font-size:13px;"
            "font-weight:700;letter-spacing:3px;border:none;")
        il.addWidget(lbl)

        sub = QLabel("A floating window with multi-tab notes,\nsyntax highlighting, and autosave.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("background:transparent;color:#4a5568;font-size:11px;border:none;")
        il.addWidget(sub)

        self._open_btn = GlowButton("Open Notepad  →", accent="#00e87a", bg="#111827")
        self._open_btn.setFixedHeight(42)
        self._open_btn.setFixedWidth(210)
        self._open_btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        self._open_btn.clicked.connect(self._toggle)
        il.addWidget(self._open_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        root.addWidget(inner)

    def refresh(self):
        pass

    def _toggle(self):
        if not self._win:
            self._win = NotepadWindow(self.app)
            self._win.load_notes(self.app)
            if hasattr(self.app, "_palette"):
                self._win.set_palette(self.app._palette)

        if self._win.isVisible():
            self._win._throw_back()
            self._open_btn.setText("Open Notepad  →")
        else:
            # Throw out from the Open button position
            btn_center = self._open_btn.mapToGlobal(
                QPoint(self._open_btn.width()  // 2,
                       self._open_btn.height() // 2))
            self._win.throw_out(btn_center)
            self._open_btn.setText("Close Notepad  ×")

    def set_palette(self, p):
        if self._win:
            self._win.set_palette(p)
