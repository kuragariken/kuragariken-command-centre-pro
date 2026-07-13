"""
panels/vault.py — Vault as a premium floating pop-out window.
Slides in from the right of the main window, same pattern as Settings.
PBKDF2-SHA256 + Fernet AES encryption. Master password never stored.
Auto-lock after 5 minutes. Built-in password generator.
"""
import math, secrets, string
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit,
    QFrame, QComboBox, QMessageBox, QStackedWidget,
    QApplication, QProgressBar, QSizeGrip
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRectF, QPoint
from PyQt6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush, QPen

from src import data as D
from src.vault_crypto import (
    new_salt, encrypt, decrypt, verify_password,
    make_canary, password_strength, generate_password
)
from src.widgets.glow_button import GlowButton
from src.widgets.accent_line import AccentLine

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"
MONO = "'JetBrains Mono','Cascadia Code','Consolas',monospace"


# ── Animated lock icon ────────────────────────────────────────────
class LockIcon(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self._angle  = 0.0
        self._locked = True
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(16)

    def set_locked(self, v: bool):
        self._locked = v

    def _tick(self):
        self._angle = (self._angle + 0.8) % 360
        self.update()

    def paintEvent(self, event):
        p  = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        for i in range(8):
            a  = math.radians(self._angle + i * 45)
            rx = cx + 22 * math.cos(a)
            ry = cy + 22 * math.sin(a)
            al = max(0, min(255, int(60 + 80 * abs(math.sin(a)))))
            c  = QColor("#f87171" if self._locked else "#00e87a")
            c.setAlpha(al)
            p.setBrush(QBrush(c)); p.setPen(Qt.PenStyle.NoPen)
            r = 3 if i % 2 == 0 else 2
            p.drawEllipse(QRectF(rx-r, ry-r, r*2, r*2))
        body = QColor("#f87171" if self._locked else "#00e87a"); body.setAlpha(220)
        p.setBrush(QBrush(body)); p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(cx-12, cy-3, 24, 18), 4, 4)
        p.drawPath(path)
        pen = QPen(body, 2.5); pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        if self._locked:
            p.drawArc(QRectF(cx-8, cy-16, 16, 17), 0, 180*16)
        else:
            p.drawArc(QRectF(cx+2, cy-18, 16, 17), 0, 180*16)
        p.setBrush(QBrush(QColor("#080b12"))); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QRectF(cx-3, cy+3, 6, 6))


# ── Vault Window ──────────────────────────────────────────────────
class VaultWindow(QWidget):
    AUTO_LOCK_MS = 5 * 60 * 1000

    def __init__(self, app_win):
        super().__init__(None)
        self._app       = app_win
        self._unlocked  = False
        self._master_pw = ""
        self._dragging  = False
        self._drag_pos  = QPoint()

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setFixedWidth(400)
        self.setMinimumHeight(520)

        self._auto_lock = QTimer(self)
        self._auto_lock.setSingleShot(True)
        self._auto_lock.timeout.connect(self._auto_lock_vault)

        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(
            f"QWidget{{background:rgba(5,8,16,0.97);color:#d4dfe9;"
            f"font-family:{FONT};font-size:12px;border:none;}}"
            "QScrollBar:vertical{background:transparent;width:4px;}"
            "QScrollBar::handle:vertical{background:#1a2840;border-radius:2px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Shimmer accent line
        self._accent_line = AccentLine(self)
        root.addWidget(self._accent_line)

        # ── Header ────────────────────────────────────────────
        hdr = QWidget(); hdr.setFixedHeight(48)
        hdr.setStyleSheet(
            "background:rgba(8,13,22,0.98);"
            "border-bottom:1px solid rgba(255,255,255,0.07);")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 12, 0)

        self._mark = QLabel()
        self._mark.setFixedSize(3, 20)
        self._mark.setStyleSheet("background:#f87171;border-radius:1px;")
        hl.addWidget(self._mark); hl.addSpacing(10)

        self._title_lbl = QLabel("VAULT")
        self._title_lbl.setStyleSheet(
            f"background:transparent;color:#f87171;font-size:10px;"
            f"font-weight:800;letter-spacing:3px;border:none;font-family:{FONT};")
        hl.addWidget(self._title_lbl)
        hl.addSpacing(10)

        self._status_pill = QLabel("LOCKED")
        self._status_pill.setStyleSheet(
            "background:#1a0808;color:#f87171;font-size:9px;font-weight:700;"
            "letter-spacing:2px;border:1px solid #f87171;border-radius:10px;"
            "padding:2px 10px;")
        hl.addWidget(self._status_pill)

        self._auto_lock_lbl = QLabel("")
        self._auto_lock_lbl.setStyleSheet(
            "background:transparent;color:#3a4e64;font-size:9px;border:none;")
        hl.addWidget(self._auto_lock_lbl)
        hl.addStretch()

        self._lock_btn = QPushButton("Unlock")
        self._lock_btn.setFixedHeight(28)
        self._lock_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:6px;padding:0 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        self._lock_btn.clicked.connect(self._toggle_lock)
        hl.addWidget(self._lock_btn)
        hl.addSpacing(8)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#3a4e64;border:none;"
            "border-radius:6px;font-size:13px;font-weight:700;}"
            "QPushButton:hover{background:#f87171;color:#080b12;}")
        close_btn.clicked.connect(self.slide_out)
        hl.addWidget(close_btn)
        root.addWidget(hdr)

        # ── Stack ────────────────────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        root.addWidget(self._stack, 1)

        self._stack.addWidget(self._build_setup_page())    # 0
        self._stack.addWidget(self._build_lock_page())     # 1
        self._stack.addWidget(self._build_unlocked_page()) # 2

        # Resize grip
        gr = QHBoxLayout(); gr.setContentsMargins(0,0,4,4); gr.addStretch()
        grip = QSizeGrip(self); grip.setFixedSize(12,12); gr.addWidget(grip)
        gw = QWidget(); gw.setFixedHeight(14); gw.setStyleSheet("background:transparent;")
        gw.setLayout(gr); root.addWidget(gw)

    # ── Setup page ────────────────────────────────────────────
    def _build_setup_page(self) -> QWidget:
        pg = QWidget(); pg.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(pg); lay.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.setSpacing(0)

        card = QWidget(); card.setFixedWidth(340)
        card.setStyleSheet(
            "background:#0d1117;border:1px solid #1f2d3d;border-radius:14px;")
        cl = QVBoxLayout(card); cl.setContentsMargins(24,22,24,22); cl.setSpacing(12)

        icon = LockIcon()
        cl.addWidget(icon, alignment=Qt.AlignmentFlag.AlignCenter)

        title = QLabel("SET UP YOUR VAULT")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"background:transparent;color:#e2e8f0;font-size:13px;"
            f"font-weight:800;letter-spacing:2px;border:none;font-family:{FONT};")
        cl.addWidget(title)

        sub = QLabel("Choose a strong master password.\nYour secrets will be encrypted with\nPBKDF2 + AES-256.")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("background:transparent;color:#4a5568;font-size:10px;border:none;")
        cl.addWidget(sub)

        sty = (f"QLineEdit{{background:#080b12;color:#e2e8f0;border:1px solid #1f2d3d;"
               f"border-radius:8px;padding:6px 12px;font-size:12px;font-family:{MONO};}}"
               f"QLineEdit:focus{{border-color:#00e87a;}}")

        lbl1 = self._small_lbl("MASTER PASSWORD")
        cl.addWidget(lbl1)
        self._setup_pw1 = QLineEdit()
        self._setup_pw1.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_pw1.setFixedHeight(36); self._setup_pw1.setStyleSheet(sty)
        self._setup_pw1.textChanged.connect(self._update_strength)
        cl.addWidget(self._setup_pw1)

        self._strength_bar = QProgressBar()
        self._strength_bar.setFixedHeight(4); self._strength_bar.setRange(0,4)
        self._strength_bar.setValue(0); self._strength_bar.setTextVisible(False)
        self._strength_bar.setStyleSheet(
            "QProgressBar{background:#1f2d3d;border-radius:2px;}"
            "QProgressBar::chunk{background:#ef4444;border-radius:2px;}")
        cl.addWidget(self._strength_bar)

        self._strength_lbl = QLabel("")
        self._strength_lbl.setStyleSheet(
            "background:transparent;color:#4a5568;font-size:9px;font-weight:700;border:none;")
        cl.addWidget(self._strength_lbl)

        cl.addWidget(self._small_lbl("CONFIRM PASSWORD"))
        self._setup_pw2 = QLineEdit()
        self._setup_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self._setup_pw2.setFixedHeight(36); self._setup_pw2.setStyleSheet(sty)
        self._setup_pw2.returnPressed.connect(self._do_setup)
        cl.addWidget(self._setup_pw2)

        self._setup_err = QLabel("")
        self._setup_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._setup_err.setStyleSheet(
            "background:transparent;color:#f87171;font-size:10px;border:none;")
        cl.addWidget(self._setup_err)

        btn = GlowButton("Create Vault", accent="#00e87a", bg="#080b12")
        btn.setFixedHeight(38); btn.setFont(QFont("Inter", 11, QFont.Weight.Bold))
        btn.clicked.connect(self._do_setup)
        cl.addWidget(btn)

        lay.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        return pg

    # ── Lock page ─────────────────────────────────────────────
    def _build_lock_page(self) -> QWidget:
        pg = QWidget(); pg.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(pg); lay.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.setSpacing(0)

        card = QWidget(); card.setFixedWidth(320)
        card.setStyleSheet(
            "background:#0d1117;border:1px solid #1f2d3d;border-radius:14px;")
        cl = QVBoxLayout(card); cl.setContentsMargins(22,18,22,18); cl.setSpacing(8)

        self._lock_icon = LockIcon()
        cl.addWidget(self._lock_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        title2 = QLabel("SECURE VAULT")
        title2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title2.setStyleSheet(
            f"background:transparent;color:#e2e8f0;font-size:13px;"
            f"font-weight:800;letter-spacing:2px;border:none;font-family:{FONT};")
        cl.addWidget(title2)

        enc = QLabel("PBKDF2-SHA256  ·  AES-128  ·  390k iterations")
        enc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        enc.setStyleSheet(
            "background:transparent;color:#3a4e64;font-size:9px;"
            "font-weight:600;letter-spacing:1px;border:none;")
        cl.addWidget(enc)

        div = QFrame(); div.setFixedHeight(1)
        div.setStyleSheet("background:#1f2d3d;"); cl.addWidget(div)

        cl.addWidget(self._small_lbl("MASTER PASSWORD"))
        sty = (f"QLineEdit{{background:#080b12;color:#e2e8f0;border:1px solid #1f2d3d;"
               f"border-radius:8px;padding:6px 12px;font-size:12px;"
               f"letter-spacing:2px;font-family:{MONO};}}"
               f"QLineEdit:focus{{border-color:#00e87a;}}")
        self._pw_field = QLineEdit()
        self._pw_field.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_field.setPlaceholderText("Enter master password…")
        self._pw_field.setFixedHeight(34); self._pw_field.setStyleSheet(sty)
        self._pw_field.returnPressed.connect(self._do_unlock)
        cl.addWidget(self._pw_field)

        self._pw_err = QLabel("")
        self._pw_err.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pw_err.setFixedHeight(14)
        self._pw_err.setStyleSheet(
            "background:transparent;color:#f87171;font-size:10px;border:none;")
        cl.addWidget(self._pw_err)

        unlock_btn = GlowButton("Unlock Vault", accent="#00e87a", bg="#080b12")
        unlock_btn.setFixedHeight(36); unlock_btn.setFont(QFont("Inter",11,QFont.Weight.Bold))
        unlock_btn.clicked.connect(self._do_unlock)
        cl.addWidget(unlock_btn)

        chg = QPushButton("Forgot / Change Password")
        chg.setStyleSheet(
            "QPushButton{background:transparent;color:#3a4e64;border:none;font-size:10px;}"
            "QPushButton:hover{color:#9ca3af;text-decoration:underline;}")
        chg.clicked.connect(self._change_password_dialog)
        cl.addWidget(chg, alignment=Qt.AlignmentFlag.AlignCenter)

        lay.addWidget(card, alignment=Qt.AlignmentFlag.AlignCenter)
        return pg

    # ── Unlocked page ─────────────────────────────────────────
    def _build_unlocked_page(self) -> QWidget:
        pg = QWidget(); pg.setStyleSheet("background:transparent;")
        ul = QVBoxLayout(pg); ul.setContentsMargins(0,0,0,0); ul.setSpacing(0)

        # Add entry bar
        add_bar = QWidget(); add_bar.setFixedHeight(52)
        add_bar.setStyleSheet(
            "background:rgba(8,13,22,0.9);border-bottom:1px solid rgba(255,255,255,0.07);")
        ab = QHBoxLayout(add_bar); ab.setContentsMargins(12,8,12,8); ab.setSpacing(6)

        self._v_label = QLineEdit(); self._v_label.setPlaceholderText("Label…")
        self._v_label.setFixedHeight(32)
        self._v_label.setStyleSheet(
            f"QLineEdit{{background:rgba(5,8,16,0.9);color:#e2e8f0;"
            f"border:1px solid rgba(255,255,255,0.08);border-radius:7px;"
            f"padding:4px 10px;font-size:11px;font-family:{FONT};}}"
            f"QLineEdit:focus{{border-color:#00e87a;}}")
        ab.addWidget(self._v_label, 1)

        self._v_secret = QLineEdit(); self._v_secret.setPlaceholderText("Secret…")
        self._v_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._v_secret.setFixedHeight(32)
        self._v_secret.setFont(QFont("JetBrains Mono", 10))
        self._v_secret.setStyleSheet(self._v_label.styleSheet())
        ab.addWidget(self._v_secret, 2)

        gen_btn = QPushButton("⚙ Gen")
        gen_btn.setFixedHeight(32); gen_btn.setFixedWidth(56)
        gen_btn.setStyleSheet(
            "QPushButton{background:rgba(15,25,40,0.8);color:#9ca3af;"
            "border:1px solid rgba(255,255,255,0.08);border-radius:6px;font-size:10px;}"
            "QPushButton:hover{background:rgba(25,40,60,0.9);color:#e2e8f0;}")
        gen_btn.clicked.connect(self._generate)
        ab.addWidget(gen_btn)

        self._v_cat = QComboBox()
        self._v_cat.setFixedWidth(100); self._v_cat.setFixedHeight(32)
        self._v_cat.setStyleSheet(
            f"QComboBox{{background:rgba(5,8,16,0.9);color:#e2e8f0;"
            f"border:1px solid rgba(255,255,255,0.08);border-radius:7px;"
            f"padding:4px 8px;font-size:11px;font-family:{FONT};}}"
            f"QComboBox QAbstractItemView{{background:#0a101a;color:#e2e8f0;"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"selection-background-color:#182030;}}")
        ab.addWidget(self._v_cat)

        add_btn = QPushButton("+ Save")
        add_btn.setFixedHeight(32)
        add_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:7px;padding:0 12px;font-weight:700;font-size:11px;}"
            "QPushButton:hover{background:#00ff88;}")
        add_btn.clicked.connect(self._add_entry)
        ab.addWidget(add_btn)
        ul.addWidget(add_bar)

        self._entry_list = QListWidget()
        self._entry_list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{background:rgba(10,16,26,0.70);color:#cdd9e5;"
            "border:1px solid rgba(255,255,255,0.05);border-radius:8px;"
            "padding:9px 14px;margin:3px 10px;font-size:11px;}"
            "QListWidget::item:hover{background:rgba(18,28,44,0.88);"
            "border-color:rgba(255,255,255,0.11);}"
            "QListWidget::item:selected{background:rgba(18,28,44,0.88);"
            "border:1px solid #00e87a;}")
        self._entry_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._entry_list.customContextMenuRequested.connect(self._entry_ctx)
        self._entry_list.itemDoubleClicked.connect(self._reveal_entry)
        ul.addWidget(self._entry_list, 1)

        ft = QWidget(); ft.setFixedHeight(30)
        ft.setStyleSheet(
            "background:rgba(5,8,16,0.9);"
            "border-top:1px solid rgba(255,255,255,0.06);")
        fl = QHBoxLayout(ft); fl.setContentsMargins(12,0,12,0)
        self._entry_count = QLabel("")
        self._entry_count.setStyleSheet(
            "background:transparent;color:#3a4e64;font-size:10px;border:none;")
        fl.addWidget(self._entry_count); fl.addStretch()
        chg2 = QPushButton("Change Password")
        chg2.setStyleSheet(
            "QPushButton{background:transparent;color:#3a4e64;border:none;font-size:10px;}"
            "QPushButton:hover{color:#9ca3af;text-decoration:underline;}")
        chg2.clicked.connect(self._change_password_dialog)
        fl.addWidget(chg2)
        tip = QLabel("Double-click to reveal")
        tip.setStyleSheet("background:transparent;color:#3a4e64;font-size:9px;border:none;")
        fl.addWidget(tip)
        ul.addWidget(ft)
        return pg

    # ── Slide animation ───────────────────────────────────────
    def slide_in(self):
        from PyQt6.QtWidgets import QApplication
        mw = self._app

        # Get available screen geometry so we never go off-screen
        screen  = QApplication.primaryScreen().availableGeometry()
        win_w   = self.width()
        win_h   = self.height()

        # Try right of main window first
        right_x = mw.x() + mw.width() + 8
        if right_x + win_w <= screen.right():
            target_x = right_x
            start_x  = target_x + 60
        else:
            # Not enough room on right — go left of main window
            target_x = max(screen.left(), mw.x() - win_w - 8)
            start_x  = target_x - 60

        # Clamp Y so window never goes above/below screen
        ideal_y  = mw.y() + (mw.height() - win_h) // 2
        target_y = max(screen.top(), min(ideal_y, screen.bottom() - win_h))

        self.move(start_x, target_y)
        self.setWindowOpacity(0)
        self.show(); self.raise_()

        pa = QPropertyAnimation(self, b"pos")
        pa.setDuration(280); pa.setEasingCurve(QEasingCurve.Type.OutCubic)
        pa.setStartValue(QPoint(start_x, target_y))
        pa.setEndValue(QPoint(target_x, target_y))

        oa = QPropertyAnimation(self, b"windowOpacity")
        oa.setDuration(220); oa.setStartValue(0.0); oa.setEndValue(1.0)

        pa.start(); oa.start()
        self._si_pa = pa; self._si_oa = oa

        self.refresh()

    def slide_out(self):
        mw  = self._app
        end = QPoint(mw.x() + mw.width() + 60, self.y())

        pa = QPropertyAnimation(self, b"pos")
        pa.setDuration(220); pa.setEasingCurve(QEasingCurve.Type.InCubic)
        pa.setStartValue(self.pos()); pa.setEndValue(end)
        pa.finished.connect(self.hide)

        oa = QPropertyAnimation(self, b"windowOpacity")
        oa.setDuration(180); oa.setStartValue(self.windowOpacity()); oa.setEndValue(0.0)

        pa.start(); oa.start()
        self._so_pa = pa; self._so_oa = oa

    def refresh(self):
        salt_hex = self._app.data["settings"].get("vault_salt","")
        canary   = self._app.data["settings"].get("vault_canary","")

        if not salt_hex or not canary:
            self._stack.setCurrentIndex(0)
        elif self._unlocked:
            self._rebuild_entries()
            cats = self._app.data.get("categories",[])
            self._v_cat.clear(); self._v_cat.addItem("General")
            for c in cats: self._v_cat.addItem(c)
        else:
            self._stack.setCurrentIndex(1)
            self._pw_field.setFocus()

    def set_palette(self, p):
        accent = p.get("accent","#00e87a")
        self._accent_line.set_accent(accent)
        self._mark.setStyleSheet(
            f"background:{'#00e87a' if self._unlocked else '#f87171'};border-radius:1px;")

    # ── Drag ─────────────────────────────────────────────────
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

    # ── Setup ─────────────────────────────────────────────────
    def _update_strength(self, pw):
        score, label, color = password_strength(pw)
        self._strength_bar.setValue(score)
        self._strength_bar.setStyleSheet(
            f"QProgressBar{{background:#1f2d3d;border-radius:2px;}}"
            f"QProgressBar::chunk{{background:{color};border-radius:2px;}}")
        self._strength_lbl.setText(label)
        self._strength_lbl.setStyleSheet(
            f"background:transparent;color:{color};font-size:9px;font-weight:700;border:none;")

    def _do_setup(self):
        pw1 = self._setup_pw1.text()
        pw2 = self._setup_pw2.text()
        if not pw1:
            self._setup_err.setText("Please enter a master password."); return
        score, label, _ = password_strength(pw1)
        if score < 2:
            self._setup_err.setText(f"Too weak ({label}). Use 8+ chars with mixed case & numbers."); return
        if pw1 != pw2:
            self._setup_err.setText("Passwords do not match."); return
        salt   = new_salt()
        canary = make_canary(pw1, salt)
        self._app.data["settings"]["vault_salt"]   = salt.hex()
        self._app.data["settings"]["vault_canary"] = canary
        self._app.data["settings"].pop("vault_hash", None)
        D.save(self._app.data)
        self._setup_pw1.clear(); self._setup_pw2.clear(); self._setup_err.setText("")
        self._do_unlock_with(pw1)

    # ── Lock / Unlock ─────────────────────────────────────────
    def _toggle_lock(self):
        if self._unlocked: self._lock()
        else: self._do_unlock()

    def _do_unlock(self):
        pw       = self._pw_field.text()
        salt_hex = self._app.data["settings"].get("vault_salt","")
        canary   = self._app.data["settings"].get("vault_canary","")
        if not pw:
            self._pw_err.setText("Enter your master password."); return
        if not verify_password(pw, salt_hex, canary):
            self._pw_err.setText("Incorrect password.")
            self._pw_field.clear(); self._pw_field.setFocus()
            self._shake(self._pw_field); return
        self._pw_field.clear(); self._pw_err.setText("")
        self._do_unlock_with(pw)

    def _do_unlock_with(self, pw):
        self._master_pw = pw; self._unlocked = True
        self._lock_icon.set_locked(False)
        self._stack.setCurrentIndex(2)
        accent = "#00e87a"
        self._title_lbl.setStyleSheet(
            f"background:transparent;color:{accent};font-size:10px;"
            f"font-weight:800;letter-spacing:3px;border:none;font-family:{FONT};")
        self._mark.setStyleSheet(f"background:{accent};border-radius:1px;")
        self._status_pill.setText("UNLOCKED")
        self._status_pill.setStyleSheet(
            f"background:#0a1a0a;color:{accent};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;border:1px solid {accent};border-radius:10px;padding:2px 10px;")
        self._lock_btn.setText("Lock")
        self._lock_btn.setStyleSheet(
            "QPushButton{background:#f87171;color:#080b12;border:none;"
            "border-radius:6px;padding:0 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:#ef4444;}")
        self.refresh()
        self._auto_lock.start(self.AUTO_LOCK_MS)
        self._start_al_display()

    def _lock(self):
        self._unlocked = False; self._master_pw = ""
        self._auto_lock.stop(); self._auto_lock_lbl.setText("")
        self._lock_icon.set_locked(True)
        self._stack.setCurrentIndex(1)
        self._title_lbl.setStyleSheet(
            f"background:transparent;color:#f87171;font-size:10px;"
            f"font-weight:800;letter-spacing:3px;border:none;font-family:{FONT};")
        self._mark.setStyleSheet("background:#f87171;border-radius:1px;")
        self._status_pill.setText("LOCKED")
        self._status_pill.setStyleSheet(
            "background:#1a0808;color:#f87171;font-size:9px;font-weight:700;"
            "letter-spacing:2px;border:1px solid #f87171;border-radius:10px;padding:2px 10px;")
        self._lock_btn.setText("Unlock")
        self._lock_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:6px;padding:0 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")

    def _auto_lock_vault(self):
        if self._unlocked:
            self._lock()
            self._app.toast.show_toast("Vault auto-locked")

    def _start_al_display(self):
        if not hasattr(self, "_al_timer"):
            self._al_timer = QTimer(self)
            self._al_timer.timeout.connect(self._update_al)
        self._al_timer.start(1000)

    def _update_al(self):
        if not self._unlocked:
            self._al_timer.stop(); return
        rem = self._auto_lock.remainingTime() // 1000
        if rem < 0: return
        m, s = divmod(rem, 60)
        self._auto_lock_lbl.setText(f"  auto-lock {m}:{s:02d}")

    def _shake(self, w):
        ox, oy = w.pos().x(), w.pos().y()
        for dx, delay in [(8,0),(-8,60),(8,120),(-8,180),(0,240)]:
            QTimer.singleShot(delay, lambda x=ox+dx, y=oy: w.move(x,y))

    # ── Entries ───────────────────────────────────────────────
    def _rebuild_entries(self):
        self._entry_list.clear()
        entries = self._app.data.get("vault_entries",[])
        salt    = bytes.fromhex(self._app.data["settings"].get("vault_salt","00"))
        for e in entries:
            ok    = decrypt(e.get("token",""), self._master_pw, salt) is not None
            cat   = e.get("cat","General"); label = e.get("label","")
            added = e.get("added","")[:10]
            icon  = "✓" if ok else "✗"
            item  = QListWidgetItem(f"  {icon}  {label}    ·    ••••••••    ·    [{cat}]    ·    {added}")
            item.setData(Qt.ItemDataRole.UserRole, e)
            if not ok: item.setForeground(QColor("#f87171"))
            self._entry_list.addItem(item)
        n = len(entries)
        self._entry_count.setText(f"{n} secret{'s' if n!=1 else ''}  ·  AES encrypted")

    def _add_entry(self):
        label  = self._v_label.text().strip()
        secret = self._v_secret.text().strip()
        if not label or not secret: return
        salt  = bytes.fromhex(self._app.data["settings"].get("vault_salt",""))
        token = encrypt(secret, self._master_pw, salt)
        self._app.data.setdefault("vault_entries",[]).append({
            "label":label,"token":token,
            "cat":self._v_cat.currentText(),"added":datetime.now().isoformat()[:10]})
        D.save(self._app.data)
        self._v_label.clear(); self._v_secret.clear(); self._v_label.setFocus()
        self._rebuild_entries()
        self._app.toast.show_toast(f"Saved: {label}")
        self._auto_lock.start(self.AUTO_LOCK_MS)

    def _reveal_entry(self, item):
        e    = item.data(Qt.ItemDataRole.UserRole)
        salt = bytes.fromhex(self._app.data["settings"].get("vault_salt",""))
        plain = decrypt(e.get("token",""), self._master_pw, salt)
        if plain is None:
            self._app.toast.show_toast("Decryption failed"); return
        dlg = RevealDialog(e.get("label",""), plain, e.get("cat",""), e.get("added",""), self)
        dlg.exec()
        self._auto_lock.start(self.AUTO_LOCK_MS)

    def _generate(self):
        pw = generate_password(16)
        self._v_secret.setText(pw)
        self._v_secret.setEchoMode(QLineEdit.EchoMode.Normal)
        QTimer.singleShot(3000, lambda: self._v_secret.setEchoMode(QLineEdit.EchoMode.Password))
        self._app.toast.show_toast("Generated secure password (visible 3s)")

    def _entry_ctx(self, pos):
        item = self._entry_list.itemAt(pos)
        if not item: return
        e = item.data(Qt.ItemDataRole.UserRole)
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Reveal",            lambda: self._reveal_entry(item))
        m.addAction("Copy to Clipboard", lambda: self._copy_entry(e))
        m.addAction("Delete",            lambda: self._delete(e))
        m.exec(self._entry_list.mapToGlobal(pos))

    def _copy_entry(self, e):
        salt  = bytes.fromhex(self._app.data["settings"].get("vault_salt",""))
        plain = decrypt(e.get("token",""), self._master_pw, salt)
        if plain:
            QApplication.clipboard().setText(plain)
            self._app.toast.show_toast(f"Copied: {e.get('label','')}")
        self._auto_lock.start(self.AUTO_LOCK_MS)

    def _delete(self, e):
        if QMessageBox.question(self, "Delete", f"Delete '{e.get('label')}'?",
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            self._app.data["vault_entries"] = [
                x for x in self._app.data.get("vault_entries",[])
                if x.get("token") != e.get("token")]
            D.save(self._app.data); self._rebuild_entries()

    def _change_password_dialog(self):
        salt_hex = self._app.data["settings"].get("vault_salt","")
        canary   = self._app.data["settings"].get("vault_canary","")
        dlg = ChangePasswordDialog(salt_hex, canary, self._master_pw, self)
        if dlg.exec():
            new_pw     = dlg.new_password(); old_pw = dlg.old_password()
            old_salt   = bytes.fromhex(salt_hex); new_salt_b = new_salt()
            entries    = self._app.data.get("vault_entries",[])
            failed     = 0
            for e in entries:
                plain = decrypt(e.get("token",""), old_pw, old_salt)
                if plain is not None: e["token"] = encrypt(plain, new_pw, new_salt_b)
                else: failed += 1
            if failed:
                QMessageBox.warning(self,"Warning",f"{failed} entries could not be re-encrypted.")
            self._app.data["settings"]["vault_salt"]   = new_salt_b.hex()
            self._app.data["settings"]["vault_canary"] = make_canary(new_pw, new_salt_b)
            self._master_pw = new_pw; D.save(self._app.data)
            self._app.toast.show_toast("Password changed — all entries re-encrypted")

    def _small_lbl(self, text):
        l = QLabel(text)
        l.setStyleSheet(
            f"background:transparent;color:#4a5568;font-size:9px;"
            f"font-weight:700;letter-spacing:2px;border:none;font-family:{FONT};")
        return l


# ── Thin panel proxy — immediately opens the popout ───────────────
class VaultPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app  = app
        self._win = None
        self.setStyleSheet("background:transparent;")

    def refresh(self):
        if not self._win:
            self._win = VaultWindow(self.app)
        if not self._win.isVisible():
            self._win.resize(400, self.app.height() + 100)
            self._win.slide_in()
        # Go back to commands without triggering panel transition
        QTimer.singleShot(50, lambda: self.app._stack.setCurrentIndex(
            list(self.app._panels.keys()).index('commands')
            if hasattr(self.app, '_panels') else 0))

    def set_palette(self, p):
        if self._win:
            self._win.set_palette(p)


# ── Reveal dialog ─────────────────────────────────────────────────
class RevealDialog(QDialog):
    def __init__(self, label, plaintext, cat, added, parent):
        super().__init__(parent)
        self.setWindowTitle("Vault — Reveal Secret")
        self.setModal(True); self.resize(420, 200)
        lay = QVBoxLayout(self); lay.setContentsMargins(20,18,20,16); lay.setSpacing(10)
        lbl = QLabel(label); lbl.setFont(QFont("Inter",13,QFont.Weight.Bold))
        lbl.setStyleSheet("background:transparent;color:#e2e8f0;border:none;")
        lay.addWidget(lbl)
        meta = QLabel(f"Category: {cat}  ·  Added: {added}")
        meta.setStyleSheet("background:transparent;color:#4a5568;font-size:10px;border:none;")
        lay.addWidget(meta)
        sep = QFrame(); sep.setFixedHeight(1); sep.setStyleSheet("background:#1f2d3d;")
        lay.addWidget(sep)
        val = QLineEdit(plaintext); val.setReadOnly(True)
        val.setFont(QFont("JetBrains Mono",12)); val.setFixedHeight(40)
        val.setStyleSheet(
            "QLineEdit{background:#0d1117;color:#00e87a;border:1px solid #1f2d3d;"
            "border-radius:8px;padding:6px 14px;letter-spacing:2px;}")
        lay.addWidget(val)
        row = QHBoxLayout(); row.addStretch()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:6px;padding:6px 16px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(plaintext))
        row.addWidget(copy_btn)
        ok = QPushButton("Close"); ok.clicked.connect(self.accept)
        row.addWidget(ok); lay.addLayout(row)


# ── Change password dialog ────────────────────────────────────────
class ChangePasswordDialog(QDialog):
    def __init__(self, salt_hex, canary, current_pw, parent):
        super().__init__(parent)
        self._salt = salt_hex; self._canary = canary; self._cur = current_pw
        self.setWindowTitle("Change Vault Password"); self.setModal(True); self.resize(360,260)
        lay = QVBoxLayout(self); lay.setContentsMargins(20,18,20,16); lay.setSpacing(8)
        sty = ("QLineEdit{background:#0d1117;color:#e2e8f0;border:1px solid #1f2d3d;"
               "border-radius:7px;padding:6px 12px;font-size:12px;font-family:'Consolas';}"
               "QLineEdit:focus{border-color:#00e87a;}")
        lay.addWidget(self._lbl("CURRENT PASSWORD"))
        self._old = QLineEdit(); self._old.setEchoMode(QLineEdit.EchoMode.Password)
        self._old.setFixedHeight(34); self._old.setStyleSheet(sty); lay.addWidget(self._old)
        lay.addWidget(self._lbl("NEW PASSWORD"))
        self._new1 = QLineEdit(); self._new1.setEchoMode(QLineEdit.EchoMode.Password)
        self._new1.setFixedHeight(34); self._new1.setStyleSheet(sty)
        self._new1.textChanged.connect(self._chk); lay.addWidget(self._new1)
        self._sbar = QProgressBar(); self._sbar.setFixedHeight(4)
        self._sbar.setRange(0,4); self._sbar.setValue(0); self._sbar.setTextVisible(False)
        self._sbar.setStyleSheet("QProgressBar{background:#1f2d3d;border-radius:2px;}"
                                 "QProgressBar::chunk{background:#ef4444;border-radius:2px;}")
        lay.addWidget(self._sbar)
        lay.addWidget(self._lbl("CONFIRM NEW PASSWORD"))
        self._new2 = QLineEdit(); self._new2.setEchoMode(QLineEdit.EchoMode.Password)
        self._new2.setFixedHeight(34); self._new2.setStyleSheet(sty)
        self._new2.returnPressed.connect(self._check); lay.addWidget(self._new2)
        self._err = QLabel("")
        self._err.setStyleSheet("background:transparent;color:#f87171;font-size:10px;border:none;")
        lay.addWidget(self._err)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject); row.addWidget(cancel)
        ok = QPushButton("Change Password")
        ok.setStyleSheet("QPushButton{background:#00e87a;color:#080b12;border:none;"
                         "border-radius:6px;padding:6px 14px;font-weight:700;}"
                         "QPushButton:hover{background:#00ff88;}")
        ok.clicked.connect(self._check); row.addWidget(ok); lay.addLayout(row)

    def _lbl(self, t):
        l = QLabel(t)
        l.setStyleSheet("background:transparent;color:#4a5568;font-size:9px;"
                        "font-weight:700;letter-spacing:2px;border:none;")
        return l

    def _chk(self, pw):
        score,_,color = password_strength(pw)
        self._sbar.setValue(score)
        self._sbar.setStyleSheet(f"QProgressBar{{background:#1f2d3d;border-radius:2px;}}"
                                 f"QProgressBar::chunk{{background:{color};border-radius:2px;}}")

    def _check(self):
        if not verify_password(self._old.text(), self._salt, self._canary):
            self._err.setText("Current password is incorrect."); return
        if self._new1.text() != self._new2.text():
            self._err.setText("New passwords do not match."); return
        score,label,_ = password_strength(self._new1.text())
        if score < 2:
            self._err.setText(f"Password too weak ({label})."); return
        self.accept()

    def old_password(self): return self._old.text()
    def new_password(self): return self._new1.text()
