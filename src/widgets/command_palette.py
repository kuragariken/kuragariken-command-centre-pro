"""
command_palette.py — Immersive full-screen command palette.

Triggered by Alt+Space. Darkens the entire screen, shows a floating
glass search panel centred on screen — Spotlight / Raycast style.
Type to filter across ALL commands regardless of category.
Enter copies the top result. Escape dismisses.
"""
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
    QScrollArea, QPushButton, QApplication, QFrame
)
from PyQt6.QtCore import (Qt, QTimer, QPropertyAnimation, QEasingCurve,
                           pyqtSignal, QRectF, QPointF, pyqtProperty)
from PyQt6.QtGui import (QPainter, QColor, QFont, QLinearGradient,
                          QRadialGradient, QBrush, QPen, QPainterPath,
                          QKeyEvent)

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"
MONO = "'JetBrains Mono','Cascadia Code','Consolas',monospace"


class CommandPalette(QWidget):
    """
    Full-screen immersive overlay. Darkens everything, floats a glass
    search card centre-screen with live-filtered results.
    """
    copy_requested = pyqtSignal(str, str)   # label, text

    def __init__(self, app_win):
        super().__init__(None)
        self._app   = app_win
        self._all_commands = []   # flat list of (label, text, category)
        self._results       = []
        self._selected_idx  = 0
        self._tick_t        = 0.0

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self._sw, self._sh = screen.width(), screen.height()

        self._card_target_y = (self._sh - 420) // 2
        self._card_y = self._card_target_y - 40   # slides up into place

        self._build_ui()

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)
        self._anim_timer.start(16)

    # ── UI ────────────────────────────────────────────────────
    def _build_ui(self):
        accent = self._app._palette.get("accent", "#00e87a")
        accent2 = self._app._palette.get("accent2", "#38bdf8")
        self._accent  = accent
        self._accent2 = accent2

        self._card = QWidget(self)
        self._card.setFixedSize(640, 420)
        self._card.move((self._sw - 640) // 2, self._card_y)
        self._card.setStyleSheet(
            "background: rgba(8,13,22,0.97);"
            "border-radius: 20px;")

        root = QVBoxLayout(self._card)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Search input row
        search_row = QWidget()
        search_row.setFixedHeight(64)
        search_row.setStyleSheet("background: transparent;")
        sl = QHBoxLayout(search_row)
        sl.setContentsMargins(24, 0, 24, 0)
        sl.setSpacing(12)

        icon = QLabel("⌕")
        icon.setStyleSheet(
            f"background:transparent;color:{accent};font-size:22px;border:none;")
        sl.addWidget(icon)

        self._input = QLineEdit()
        self._input.setPlaceholderText("Search all commands…")
        self._input.setStyleSheet(
            f"QLineEdit{{background:transparent;color:#f0f4f8;"
            f"border:none;font-size:20px;font-family:{FONT};"
            f"font-weight:500;}}")
        self._input.textChanged.connect(self._on_search)
        self._input.installEventFilter(self)
        sl.addWidget(self._input, 1)

        hint = QLabel("ESC")
        hint.setStyleSheet(
            "background:rgba(255,255,255,0.08);color:#6b7f96;"
            "font-size:10px;font-weight:700;border-radius:8px;"
            "padding:4px 8px;border:none;")
        sl.addWidget(hint)

        root.addWidget(search_row)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: rgba(255,255,255,0.07);")
        root.addWidget(sep)

        # Results list
        self._results_scroll = QScrollArea()
        self._results_scroll.setWidgetResizable(True)
        self._results_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._results_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._results_scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:4px;background:transparent;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,0.12);"
            "border-radius:2px;}")

        self._results_w = QWidget()
        self._results_w.setStyleSheet("background:transparent;")
        self._results_lay = QVBoxLayout(self._results_w)
        self._results_lay.setContentsMargins(12, 12, 12, 12)
        self._results_lay.setSpacing(4)
        self._results_lay.addStretch()

        self._results_scroll.setWidget(self._results_w)
        root.addWidget(self._results_scroll, 1)

        # Footer hint bar
        footer = QWidget()
        footer.setFixedHeight(36)
        footer.setStyleSheet(
            "background: rgba(0,0,0,0.2); border-radius: 0 0 20px 20px;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(20, 0, 20, 0)
        fhint = QLabel("↑↓ Navigate    ⏎ Copy    ESC Close")
        fhint.setStyleSheet(
            "background:transparent;color:#6b83a0;font-size:10px;"
            "font-weight:500;border:none;")
        fl.addWidget(fhint)
        fl.addStretch()
        root.addWidget(footer)

        from src.widgets.elevation import elevate
        elevate(self._card, level=3)

    # ── Data ──────────────────────────────────────────────────
    def load_commands(self, commands_dict: dict):
        """Flatten all commands across categories for global search."""
        self._all_commands = []
        for cat, cmds in commands_dict.items():
            for cmd in cmds:
                self._all_commands.append(
                    (cmd.get("label", ""), cmd.get("text", ""), cat))

    def _on_search(self, text: str):
        text = text.strip().lower()
        if not text:
            self._results = self._all_commands[:8]
        else:
            self._results = [
                c for c in self._all_commands
                if text in c[0].lower() or text in c[1].lower()
            ][:8]
        self._selected_idx = 0
        self._render_results()

    def _render_results(self):
        # Clear
        while self._results_lay.count() > 1:
            item = self._results_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._results:
            empty = QLabel("No commands match your search")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(
                "background:transparent;color:#6b83a0;font-size:13px;"
                "border:none;padding:40px;")
            self._results_lay.insertWidget(0, empty)
            return

        for i, (label, text, cat) in enumerate(self._results):
            row = self._make_result_row(label, text, cat, i == self._selected_idx)
            self._results_lay.insertWidget(i, row)

    def _make_result_row(self, label, text, cat, selected):
        row = QPushButton()
        row.setFixedHeight(52)
        row.setCursor(Qt.CursorShape.PointingHandCursor)

        accent = self._accent
        if selected:
            row.setStyleSheet(
                f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                f"stop:0 rgba(255,255,255,0.10),stop:1 rgba(255,255,255,0.04));"
                f"border:1px solid {accent};border-radius:12px;text-align:left;"
                f"padding:0 16px;}}")
        else:
            row.setStyleSheet(
                "QPushButton{background:transparent;border:1px solid transparent;"
                "border-radius:12px;text-align:left;padding:0 16px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.05);}")

        lay = QHBoxLayout(row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"background:transparent;color:#f0f4f8;font-size:14px;"
            f"font-weight:600;border:none;font-family:{FONT};")
        lay.addWidget(lbl)

        preview = QLabel(text[:50] + ("…" if len(text) > 50 else ""))
        preview.setStyleSheet(
            "background:transparent;color:#6e7d90;font-size:11px;"
            "border:none;")
        lay.addWidget(preview, 1)

        cat_pill = QLabel(cat)
        cat_pill.setStyleSheet(
            f"background:rgba(255,255,255,0.06);color:{accent};"
            f"font-size:9px;font-weight:700;border-radius:8px;"
            f"padding:3px 10px;border:none;")
        lay.addWidget(cat_pill)

        row.clicked.connect(lambda: self._copy_result(label, text))
        return row

    def _copy_result(self, label, text):
        self.copy_requested.emit(label, text)
        self._dismiss()

    # ── Keyboard navigation ───────────────────────────────────
    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key == Qt.Key.Key_Escape:
                self._dismiss()
                return True
            elif key == Qt.Key.Key_Down:
                self._selected_idx = min(
                    len(self._results)-1, self._selected_idx+1)
                self._render_results()
                return True
            elif key == Qt.Key.Key_Up:
                self._selected_idx = max(0, self._selected_idx-1)
                self._render_results()
                return True
            elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if self._results:
                    label, text, _ = self._results[self._selected_idx]
                    self._copy_result(label, text)
                return True
        return False

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() == Qt.Key.Key_Escape:
            self._dismiss()

    # ── Show / dismiss ────────────────────────────────────────
    def show_palette(self):
        self.setGeometry(QApplication.primaryScreen().geometry())
        self._card_y = self._card_target_y - 40
        self._card.move((self._sw - 640)//2, self._card_y)
        self._input.clear()
        self._on_search("")
        self.setWindowOpacity(0.0)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(160)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()

    def _dismiss(self):
        self._fade_out = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out.setDuration(140)
        self._fade_out.setStartValue(self.windowOpacity())
        self._fade_out.setEndValue(0.0)
        self._fade_out.finished.connect(self.hide)
        self._fade_out.start()

    def _animate(self):
        # Slide card up into place on open
        if self._card_y < self._card_target_y:
            self._card_y = min(self._card_target_y,
                                self._card_y + max(1, (self._card_target_y-self._card_y)//4+2))
            self._card.move(self._card.x(), self._card_y)

        self._tick_t += 0.01
        self.update()

    # ── Background paint ──────────────────────────────────────
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Dark vignette backdrop
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 180))

        vg = QRadialGradient(QPointF(w/2, h/2), max(w,h)*0.7)
        vg.setColorAt(0, QColor(0,0,0,0))
        vg.setColorAt(1, QColor(0,0,0,90))
        p.fillRect(0, 0, w, h, QBrush(vg))

        # Ambient accent glow behind card
        ac = QColor(self._accent)
        cx = self._card.x() + self._card.width()/2
        cy = self._card.y() + self._card.height()/2
        glow = QRadialGradient(QPointF(cx, cy), 420)
        gc = QColor(ac); gc.setAlpha(int(20 + 8*math.sin(self._tick_t)))
        glow.setColorAt(0, gc)
        glow.setColorAt(1, QColor(0,0,0,0))
        p.fillRect(0, 0, w, h, QBrush(glow))

        # Card border glow
        cx0, cy0 = self._card.x(), self._card.y()
        cw, ch = self._card.width(), self._card.height()
        for size, alpha in [(1, 60), (6, 18), (16, 6)]:
            bc = QColor(ac); bc.setAlpha(alpha)
            p.setPen(QPen(bc, size))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(QRectF(cx0-size//2, cy0-size//2,
                                     cw+size, ch+size), 22, 22)

    def mousePressEvent(self, e):
        # Click outside card dismisses
        if not self._card.geometry().contains(e.pos()):
            self._dismiss()
