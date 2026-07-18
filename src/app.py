"""app.py — Command Centre Pro v10. All issues fixed."""
import sys
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QLabel, QPushButton, QSystemTrayIcon, QMenu,
    QApplication, QFrame, QSlider, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QIcon, QFont, QPixmap, QPainter, QColor

from src import data as D
from src.widgets.keep_alive import KeepAlivePanel
from src.themes import get_stylesheet, get_palette
from src.panels.commands   import CommandsPanel
from src.panels.analytics  import AnalyticsPanel
from src.panels.team_analytics import TeamAnalyticsPanel
from src.panels.reminders  import RemindersPanel
from src.panels.macros     import MacrosPanel
from src.panels.settings   import SettingsPanel
from src.panels.vault      import VaultPanel
from src.panels.history    import HistoryPanel
from src.panels.notepad    import NotepadPanel
from src.panels.ticket_log import TicketLogPanel
from src.widgets.toast     import ToastManager
from src.widgets.pomodoro  import PomodoroWidget
from src.widgets.quick_launch import QuickLaunchBar
from src.widgets.copy_burst   import CopyBurst
from src.widgets.accent_line  import AccentLine
from src.widgets.particle_trail  import ParticleTrail
from src.widgets.status_bar_fx   import FlashLabel
from src.widgets.panel_transition  import PanelTransition, FadeOverlay
from src.widgets.gradient_title    import GradientTitle
from src.widgets.liquid_glass      import LiquidGlassBar
from src.widgets.kinetic_label    import KineticLabel
from src.hotkeys import HotkeyManager
from src.widgets.command_palette import CommandPalette

DEFAULT_W, DEFAULT_H = 900, 300

NAV_ITEMS = [
    ("Commands",   "commands"),
    ("Analytics",  "analytics"),
    ("Teams",      "teams"),
    ("Upgrades",   "upgrades"),
    ("Reminders",  "reminders"),
    ("Macros",     "macros"),
    ("History",    "history"),
    ("Notepad",    "notepad"),
    ("Tickets",    "tickets"),
    ("Vault",      "vault"),
    ("Settings",     "settings"),
    ("Quick Launch", "ql"),
]


class RoundedWindow(QWidget):
    """Outer wrapper with rounded corners and drop shadow."""
    def __init__(self):
        super().__init__()

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainterPath, QBrush, QLinearGradient, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, 10, 10)

        # Subtle top-lit vertical gradient — premium dark UIs are never a
        # single flat fill; they catch a little light up top and sink into
        # shadow at the bottom. The shift is tiny (a few RGB points) so it
        # reads as depth, not as a visible gradient band.
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor("#0c1019"))
        grad.setColorAt(0.5, QColor("#080b12"))
        grad.setColorAt(1.0, QColor("#05070d"))
        p.fillPath(path, QBrush(grad))

        # Hairline inner highlight on the top edge — light grazing the bevel.
        p.setClipPath(path)
        edge = QColor("#ffffff"); edge.setAlpha(14)
        p.setPen(QPen(edge, 1))
        p.drawLine(12, 1, w - 12, 1)


class CommandCentreApp(QMainWindow):
    copy_requested = pyqtSignal(str, str, str)

    def __init__(self):
        super().__init__()
        self._dragging      = False
        self._drag_pos      = QPoint()
        self._current_nav   = "commands"
        self._quitting      = False
        self._nav_open      = False
        self._palette       = {}
        self._last_copy_pos = None

        self.data  = D.load()
        self.toast = ToastManager(self)

        from src.widgets.app_icon import apply_window_icon
        apply_window_icon(self)

        self._init_window()
        self._build_ui()
        self._apply_theme()
        self._init_tray()
        self._init_timers()
        self._init_hotkeys()

        pos = self.data["settings"].get("window_pos")
        if pos:
            self.move(pos[0], pos[1])

        if self.data["settings"].get("keep_alive_enabled", False):
            self._start_keep_alive(show_toast=False)

        self._nav_to("commands")

    def _init_window(self):
        flags = Qt.WindowType.FramelessWindowHint
        if self.data["settings"].get("always_on_top", False):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setFixedSize(DEFAULT_W, DEFAULT_H)

    # ─────────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        central.setObjectName("CentralWidget")
        self.setCentralWidget(central)

        # ── Aurora background — sits behind all content, fills the window ──
        # Created first and lowered so the title bar, panels, and status bar
        # (all transparent-backed) render on top of the animated background.
        # An event filter keeps it exactly matched to the central widget's
        # size at all times — no reliance on resize/show timing.
        from src.widgets.aurora import AuroraBackground
        self._aurora = AuroraBackground(central)
        self._aurora.setGeometry(central.rect())
        self._aurora.lower()
        central.installEventFilter(self)
        self._aurora_host = central

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._make_title_bar())

        # Floating nav popup — created here but NOT added to any layout;
        # it's a standalone Popup window shown/positioned on demand.
        self._nav_dropdown = self._make_nav_dropdown()

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 rgba(31,45,61,0.0),"
            "stop:0.5 rgba(31,45,61,1.0),"
            "stop:1 rgba(31,45,61,0.0));")
        root.addWidget(sep)

        self._stack  = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._panels = {}
        self._build_panels()
        root.addWidget(self._stack, 1)

        # Panel transition overlay
        self._panel_trans = PanelTransition(self._stack, central)

        root.addWidget(self._make_status_bar())


        # CopyBurst overlay
        self._copy_burst = CopyBurst(self)

        # Particle trail — sparks on copy
        self._particles = ParticleTrail(self)

        # Keyboard shortcuts reference (? or F1) — discoverability
        from src.widgets.shortcuts_overlay import ShortcutsOverlay
        self._shortcuts_overlay = ShortcutsOverlay(self)

        # Self-updater: silent check on startup, animated prompt if newer
        from src.panels.update_dialog import UpdateDialog
        self._update_dialog = UpdateDialog(self, self._palette.get("accent", "#00e87a"))
        QTimer.singleShot(2500, lambda: self._check_for_update(manual=False))

    # ─────────────────────────────────────────────────────────────
    # TITLE BAR
    # ─────────────────────────────────────────────────────────────
    def _make_title_bar(self) -> QWidget:
        wrapper = QWidget()
        wrapper.setFixedHeight(58)
        wrapper.setStyleSheet("background:rgba(5,8,16,0.92);")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(0)

        self._accent_line = AccentLine(wrapper)
        wl.addWidget(self._accent_line)

        bar = QWidget()
        bar.setFixedHeight(56)
        bar.setStyleSheet("background:rgba(6,10,18,0.94);""border-bottom:1px solid rgba(255,255,255,0.07);")
        wl.addWidget(bar)

        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 0, 10, 0)
        lay.setSpacing(0)

        # Accent stripe — 4x26, with its own glow (matches the HTML's
        # box-shadow:0 0 14px rgba(0,232,122,0.7) on .accent-bar)
        self._accent_mark = QLabel()
        self._accent_mark.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._accent_mark.setFixedSize(4, 26)
        self._accent_mark.setObjectName("AccentMark")
        self._accent_mark.setStyleSheet("background:#00e87a; border-radius:2px;")
        _accent_glow = QGraphicsDropShadowEffect(self._accent_mark)
        _accent_glow.setColor(QColor("#00e87a"))
        _accent_glow.setBlurRadius(14)
        _accent_glow.setOffset(0, 0)
        self._accent_mark.setGraphicsEffect(_accent_glow)
        self._accent_mark_glow = _accent_glow
        lay.addWidget(self._accent_mark)
        lay.addSpacing(12)

        # Wordmark — "COMMAND CENTRE" static glow gradient, "PRO" keeps its
        # small animated sweep. Two techniques, one glowing-text family.
        from src.widgets.gradient_title import StaticGradientLabel
        self._wordmark = StaticGradientLabel("COMMAND CENTRE")
        self._wordmark.setObjectName("Wordmark")
        _wm_glow = QGraphicsDropShadowEffect(self._wordmark)
        _wm_glow.setColor(QColor("#00e87a"))
        _wm_glow.setBlurRadius(22)
        _wm_glow.setOffset(0, 0)
        self._wordmark.setGraphicsEffect(_wm_glow)
        self._wordmark_glow = _wm_glow
        lay.addWidget(self._wordmark)
        lay.addSpacing(7)

        title = GradientTitle("PRO")
        title.setObjectName("AppTitle")
        self._gradient_title = title
        lay.addWidget(title)
        lay.addStretch(1)   # left group takes its own space; nav sits centred

        # Nav trigger — the ONE dropdown pill, centred, with a glow anchor
        self._nav_btn = QPushButton("COMMANDS  ▾")
        self._nav_btn.setObjectName("NavBtn")
        self._nav_btn.setFixedHeight(32)
        self._nav_btn.setMinimumWidth(140)
        self._nav_btn.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        self._nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._nav_btn.clicked.connect(self._toggle_nav_dropdown)
        _nav_glow = QGraphicsDropShadowEffect(self._nav_btn)
        _nav_glow.setColor(QColor("#00e87a"))
        _nav_glow.setBlurRadius(45)
        _nav_glow.setOffset(0, 4)
        self._nav_btn.setGraphicsEffect(_nav_glow)
        lay.addWidget(self._nav_btn)
        lay.addStretch(1)   # right group takes equal space -> true centring

        # Pomodoro — feature stays reachable via the right-click menu and
        # its own toast; it no longer occupies header space.
        self._pomo_widget = PomodoroWidget(self)

        # ── Status chips: Keep-Alive + clock, ONE shared chip style ──
        # (see _style_status_chip — the single source of truth so a status
        # change can never again silently discard the chip look)
        self._ka_label = QLabel("KEEP-ALIVE")
        self._ka_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._ka_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._ka_label.mousePressEvent = lambda e: self._toggle_keep_alive()
        self._ka_worker = None
        lay.addWidget(self._ka_label)
        lay.addSpacing(10)
        self._style_status_chip(self._ka_label, "#00e87a")

        self._clock = QLabel("00:00:00")
        self._clock.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._clock.setObjectName("Clock")
        self._clock.setFixedWidth(84)
        self._clock.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clock.setFont(QFont("JetBrains Mono", 10))
        lay.addWidget(self._clock)
        self._style_status_chip(self._clock, "#8494a8", mono=True)

        # Kept alive (unused visually) so the theme-switch loop iterating
        # [self._s1, self._s2] doesn't break; no divider lines are shown —
        # the reference design has the chips sitting adjacent with just
        # spacing between them.
        self._s1 = QLabel(); self._s1.setFixedSize(1, 18)
        self._s2 = QLabel(); self._s2.setFixedSize(1, 18)

        lay.addSpacing(10)

        # Window control dots — coloured circles, no text symbols
        self._pin_btn = self._dot_btn("#fbbf24", "#f59e0b", "Always on top", self._toggle_pin)
        self._min_btn = self._dot_btn("#4ade80", "#22c55e", "Minimise",       self.showMinimized)
        self._cls_btn = self._dot_btn("#f87171", "#ef4444", "Close to tray",  self._hide_to_tray)
        for b in [self._pin_btn, self._min_btn, self._cls_btn]:
            lay.addWidget(b)
            lay.addSpacing(5)
        lay.addSpacing(2)

        return wrapper

    def _style_status_chip(self, label: QLabel, color: str, mono: bool = False):
        """
        The ONE place that styles a header status chip (Keep-Alive or the
        clock) — matches the HTML reference's single .status-chip class
        exactly: padding 7px 12px, border-radius 8px, font-size 10.5px,
        a tinted background at the given colour, and a matching border.
        Every status change (keep-alive start/stop/found/lost, theme
        switch) MUST call this rather than set its own stylesheet — that
        was exactly the bug that kept discarding the chip look before.
        """
        c = QColor(color)
        r, g, b = c.red(), c.green(), c.blue()
        font_css = ("font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace;"
                    if mono else "")
        label.setStyleSheet(
            f"QLabel{{background:rgba({r},{g},{b},18);color:{color};"
            f"{font_css}"
            f"font-size:10.5px;font-weight:700;letter-spacing:0.4px;"
            f"border:1px solid rgba({r},{g},{b},60);"
            f"border-radius:8px;padding:7px 12px;}}"
            f"QLabel:hover{{background:rgba({r},{g},{b},32);}}")

    def _toggle_keep_alive(self):
        if self._ka_worker is None:
            self._start_keep_alive(show_toast=True)
        else:
            self._stop_keep_alive(show_toast=True)

    def _start_keep_alive(self, show_toast: bool = False):
        """Start the keep-alive worker and persist the enabled state."""
        from src.widgets.keep_alive import KeepAliveWorker
        if self._ka_worker is not None:
            return
        accent  = self._palette.get('accent', '#00e87a')
        minutes = self.data["settings"].get("keep_alive_interval_min", 4)

        self._ka_worker = KeepAliveWorker()
        self._ka_found_state = None   # reset so first found/lost toasts
        self._ka_worker.set_interval(minutes * 60 * 1000)
        self._ka_worker.status_update.connect(self._on_ka_status)
        self._ka_worker.found_window.connect(self._on_ka_found)
        self._ka_worker.start()
        self._style_ka_chip(accent)
        self._ka_label.setToolTip("Keep-Alive: starting…")

        self.data["settings"]["keep_alive_enabled"] = True
        D.save(self.data)

        if show_toast:
            self.toast.show_toast('Keep-Alive ON')

    def _stop_keep_alive(self, show_toast: bool = False):
        """Stop the keep-alive worker and persist the disabled state."""
        if self._ka_worker is not None:
            self._ka_worker.stop()
            self._ka_worker.wait(2000)
            self._ka_worker = None
        self._ka_label.setText("KEEP-ALIVE")
        self._style_ka_chip("#6b83a0")
        self._ka_found_state = None
        D.save(self.data)

        if show_toast:
            self.toast.show_toast('Keep-Alive OFF')
        self._ka_label.setToolTip("Keep-Alive: off")

    def _style_ka_chip(self, color: str):
        """Thin compatibility wrapper — the real styling logic now lives in
        _style_status_chip, shared with the clock, so both can never drift
        apart again."""
        self._style_status_chip(self._ka_label, color)

    def _on_ka_status(self, msg: str):
        """Surface keep-alive activity — tooltip on the label shows last event."""
        self._ka_label.setToolTip(f"Keep-Alive · {msg}")

    def _on_ka_found(self, found: bool):
        """
        Make 'is the POS GUI actually found?' unmissable:
          • label text switches: 'KEEP-ALIVE ●' green = found & pinging,
            'KEEP-ALIVE ○' amber = running but GUI not found yet
          • a toast fires only on the transition (found↔lost), so you get an
            active heads-up the moment it locks on or loses the window
        """
        if self._ka_worker is None:
            return
        accent = self._palette.get('accent', '#00e87a')
        prev = getattr(self, "_ka_found_state", None)

        if found:
            self._ka_label.setText("KEEP-ALIVE ●")
            col = accent
            if prev is not True:
                self.toast.show_toast('✓ POS Support GUI found — keeping alive')
            self._ka_label.setToolTip("Keep-Alive · POS Support GUI found ✓")
        else:
            self._ka_label.setText("KEEP-ALIVE ○")
            col = '#fbbf24'
            if prev is True:
                self.toast.show_toast('⚠ POS Support GUI lost — searching…')
            self._ka_label.setToolTip("Keep-Alive · searching for POS Support GUI…")

        self._ka_found_state = found
        self._style_ka_chip(col)

    def _dot_btn(self, color: str, hover_color: str, tip: str, slot) -> QPushButton:
        """Coloured circle button — no symbol, pure macOS style."""
        b = QPushButton()
        b.setFixedSize(14, 14)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(
            f"QPushButton{{background:{color};border:none;border-radius:8px;}}"
            f"QPushButton:hover{{background:{hover_color};}}"
            f"QPushButton:pressed{{background:{hover_color}; opacity:0.7;}}")
        b.clicked.connect(slot)
        return b

    # ─────────────────────────────────────────────────────────────
    # NAV DROPDOWN
    # ─────────────────────────────────────────────────────────────
    _NAV_ICONS = {
        "commands": "❯", "analytics": "▤", "teams": "◈", "upgrades": "△",
        "reminders": "◔", "macros": "◆", "history": "↺", "notepad": "▭",
        "tickets": "▣", "vault": "▦", "settings": "◍", "ql": "»",
    }

    def _make_nav_dropdown(self) -> QWidget:
        """
        A real floating popup menu — Qt.WindowType.Popup auto-closes on any
        outside click, the same behaviour the approved design relies on.
        Previously this built a full-width inline row that pushed the whole
        window's content down when opened; now it's a compact vertical list
        that overlays on top, exactly like the reference mockup's dropdown.
        """
        w = QWidget(self, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        w.setObjectName("NavDropdown")
        # WA_StyledBackground is required for a plain QWidget to actually
        # paint its own QSS background/border — without it the panel stays
        # unpainted and whatever's behind it (search bar, pills) shows
        # through, which is exactly the garbled overlap bug in the screenshot.
        w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        w.setStyleSheet(
            "#NavDropdown{background:#0a0e16;"
            "border:1px solid rgba(255,255,255,0.1);border-radius:11px;}")

        outer = QVBoxLayout(w)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(2)

        self._nav_pill_btns = {}
        for label, key in NAV_ITEMS:
            btn = QPushButton(f"{self._NAV_ICONS.get(key,'•')}   {label}")
            btn.setFixedHeight(32)
            btn.setMinimumWidth(180)
            btn.setFont(QFont("Inter", 10, QFont.Weight.Medium))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton{background:transparent;color:#a7b6c8;"
                "border:none;border-radius:8px;padding:0 10px;"
                "text-align:left;font-size:11.5px;}"
                "QPushButton:hover{background:rgba(255,255,255,0.07);color:#eef3f7;}")
            if key == "ql":
                btn.clicked.connect(lambda: (self._toggle_quick_launch(), self._nav_dropdown.hide()))
            else:
                btn.clicked.connect(lambda checked, k=key: self._nav_select(k))
                self._nav_pill_btns[key] = btn
            outer.addWidget(btn)

        # Keep the trigger's arrow in sync even when Qt's own Popup behaviour
        # closes this (e.g. a click outside), not just our own toggle calls.
        _orig_hide_event = w.hideEvent
        def _on_hide(event):
            self._nav_open = False
            if hasattr(self, "_nav_btn"):
                cur_label = dict(NAV_ITEMS).get(self._current_nav, self._current_nav.title())
                self._nav_btn.setText(f"{cur_label.upper()}  ▾")
            _orig_hide_event(event)
        w.hideEvent = _on_hide

        return w

    # ─────────────────────────────────────────────────────────────
    def _build_panels(self):
        from src.panels.upgrade_tracker_panel import UpgradeTrackerPanel
        for key, cls in [
            ("commands",  CommandsPanel),
            ("analytics", AnalyticsPanel),
            ("teams",     TeamAnalyticsPanel),
            ("upgrades",  UpgradeTrackerPanel),
            ("reminders", RemindersPanel),
            ("macros",    MacrosPanel),
            ("history",   HistoryPanel),
            ("notepad",   NotepadPanel),
            ("tickets",   TicketLogPanel),
            ("vault",     VaultPanel),
            ("settings",  SettingsPanel),
        ]:
            p = cls(self)
            self._panels[key] = p
            self._stack.addWidget(p)

        self._panels["commands"].copy_requested.connect(self._on_copy)
        self._panels["settings"].theme_changed.connect(self._apply_theme)
        self._panels["settings"].data_changed.connect(self._on_settings_changed)

    def _make_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(26)
        bar.setStyleSheet("background:rgba(5,8,14,0.82);""border-top:1px solid rgba(255,255,255,0.06);")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(12, 0, 10, 0)
        lay.setSpacing(10)

        self._status_copies = QLabel("0 today  /  0 total")
        self._status_copies.setStyleSheet(
            "background:transparent;color:#68809c;font-size:11px;font-weight:500;border:none;font-family:'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif;")
        lay.addWidget(self._status_copies)

        self._shift_display = QLabel("")
        self._shift_display.setStyleSheet(
            "background:transparent;color:#6e7d90;font-size:10px;"
            "font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace;border:none;font-weight:600;")
        lay.addWidget(self._shift_display)

        lay.addStretch()

        # Discoverable shortcuts hint (research: shortcuts are useless if hidden)
        kb_hint = QLabel("⌨ ?")
        kb_hint.setCursor(Qt.CursorShape.PointingHandCursor)
        kb_hint.setToolTip("Keyboard shortcuts  (press ? or F1)")
        kb_hint.setStyleSheet(
            "QLabel{background:transparent;color:#6b83a0;font-size:11px;"
            "font-weight:700;border:none;padding:1px 6px;border-radius:4px;}"
            "QLabel:hover{background:rgba(255,255,255,0.06);color:#9fb0c4;}")
        kb_hint.mousePressEvent = lambda e: (
            self._shortcuts_overlay.show_overlay()
            if hasattr(self, '_shortcuts_overlay') else None)
        lay.addWidget(kb_hint)

        sep0 = QLabel()
        sep0.setFixedSize(1, 12)
        sep0.setStyleSheet("background:#1f2d3d;")
        lay.addWidget(sep0)

        self._status_theme = QLabel("DEFAULT")
        self._status_theme.setObjectName("StatusTheme")
        self._status_theme.setStyleSheet(
            "background:transparent;color:#6e7d90;font-size:10px;"
            "font-weight:700;letter-spacing:1px;border:none;")
        lay.addWidget(self._status_theme)


        sep = QLabel()
        sep.setFixedSize(1, 12)
        sep.setStyleSheet("background:#1f2d3d;")
        lay.addWidget(sep)

        opc = QLabel("OPACITY")
        opc.setStyleSheet(
            "background:transparent;color:#6e7d90;font-size:9px;"
            "font-weight:700;letter-spacing:1px;border:none;")
        lay.addWidget(opc)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setFixedWidth(60)
        self._opacity_slider.setRange(30, 100)
        self._opacity_slider.setValue(self.data["settings"].get("opacity", 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity)
        lay.addWidget(self._opacity_slider)

        return bar

    # ─────────────────────────────────────────────────────────────
    # NAVIGATION
    # ─────────────────────────────────────────────────────────────
    def _toggle_nav_dropdown(self):
        if self._nav_dropdown.isVisible():
            self._nav_dropdown.hide()
            return

        self._nav_open = True
        label = dict(NAV_ITEMS).get(self._current_nav, self._current_nav.title())
        self._nav_btn.setText(f"{label.upper()}  ▴")

        # Show first, THEN measure+reposition — a widget's size isn't
        # reliably realized before it's actually shown, which was causing
        # the popup to appear at the wrong spot / wrong size on first open.
        self._nav_dropdown.show()
        self._nav_dropdown.adjustSize()
        popup_w = self._nav_dropdown.width()
        btn_center_x = self._nav_btn.mapToGlobal(QPoint(self._nav_btn.width() // 2, 0)).x()
        btn_bottom_y = self._nav_btn.mapToGlobal(QPoint(0, self._nav_btn.height() + 6)).y()
        self._nav_dropdown.move(btn_center_x - popup_w // 2, btn_bottom_y)
        self._nav_dropdown.raise_()

    def _nav_select(self, key: str):
        if self._nav_open:
            self._toggle_nav_dropdown()
        self._nav_to(key)

    def _nav_to(self, key: str):
        # Popout panels (settings / vault / notepad) are shown in their own
        # floating windows, so their widget is reparented out of the stack.
        # Running a stack transition toward them fades the main content to an
        # empty page → blank screen. They also must NOT become _current_nav,
        # or a later theme re-apply (which calls _nav_to(_current_nav)) would
        # target the empty popout page and blank the main area.
        _popout_keys = {'settings', 'vault', 'notepad', 'pcms', 'teams', 'upgrades'}

        panel = self._panels.get(key)
        if key in _popout_keys:
            if panel:
                try:
                    panel.refresh()
                except Exception as e:
                    print(f"[CCP] refresh error ({key}): {e}")
            return

        self._current_nav = key
        if panel:
            idx = self._stack.indexOf(panel)
            if hasattr(self, '_panel_trans'):
                self._panel_trans.switch(idx)
            else:
                self._stack.setCurrentIndex(idx)
            try:
                panel.refresh()
            except Exception as e:
                print(f"[CCP] refresh error ({key}): {e}")

        p      = self._palette
        accent = p.get("accent", "#00e87a")
        dim    = p.get("dim",    "#6e7d90")
        hover  = p.get("hover",  "#182030")
        card   = p.get("card",   "#111827")
        border = p.get("border", "#1f2d3d")
        text   = p.get("text",   "#cdd9e5")
        bg     = p.get("bg",     "#080b12")

        for k, btn in self._nav_pill_btns.items():
            if k == key:
                btn.setStyleSheet(
                    f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    f"stop:0 {accent},stop:1 {p.get('accent2',p.get('blue',accent))});"
                    f"color:#060a10;border:none;"
                    f"border-radius:12px;padding:2px 4px;font-size:10px;"
                    f"font-weight:700;letter-spacing:0.2px;}}"
                    f"QPushButton:hover{{background:{accent};}}")
            else:
                btn.setStyleSheet(
                    f"QPushButton{{background:rgba(255,255,255,0.05);"
                    f"color:#6a869f;"
                    f"border:1px solid rgba(255,255,255,0.08);"
                    f"border-radius:12px;padding:2px 4px;"
                    f"font-size:10px;font-weight:500;letter-spacing:0.2px;}}"
                    f"QPushButton:hover{{background:rgba(255,255,255,0.10);"
                    f"color:{text};border-color:rgba(255,255,255,0.20);}}")

        label = dict(NAV_ITEMS).get(key, key.title())
        arrow = "▴" if self._nav_open else "▾"
        self._nav_btn.setText(f"{label.upper()}  {arrow}")

    # ─────────────────────────────────────────────────────────────
    # COPY
    # ─────────────────────────────────────────────────────────────
    def _on_copy(self, label: str, text: str, category: str):
        QApplication.clipboard().setText(text)

        if self.data["settings"].get("auto_paste"):
            QTimer.singleShot(200, self._do_paste)

        D.record_copy(self.data, label, category)

        h = self.data.setdefault("clip_history", [])
        h.insert(0, {"label": label, "text": text,
                     "time": datetime.now().isoformat()})
        self.data["clip_history"] = h[:20]

        if self.data["settings"].get("session_log"):
            D.log_copy(label, text)

        D.save(self.data)
        self._update_status()
        # Flash copy count
        if hasattr(self._status_copies, 'flash'):
            self._status_copies.flash(self._palette.get('accent','#00e87a'))
        self.toast.show_toast(f"Copied  {label}")

        # Particle burst on copy
        if self._last_copy_pos:
            from PyQt6.QtCore import QPointF
            local = self._particles.mapFromGlobal(self._last_copy_pos)
            accent = self._palette.get("accent", "#00e87a")
            self._particles.set_accent(accent)
            self._particles.resize(self.size())
            self._particles.burst(QPointF(local.x(), local.y()), count=16)

        # Copy burst ring animation
        if self._last_copy_pos:
            burst_pos = self._copy_burst.mapFromGlobal(self._last_copy_pos)
            accent    = self._palette.get("accent", "#00e87a")
            self._copy_burst.resize(self.size())
            self._copy_burst.fire(burst_pos, accent)
            self._last_copy_pos = None

        if self._current_nav == "history":
            self._panels["history"].refresh()

    def set_copy_pos(self, global_pos):
        self._last_copy_pos = global_pos

    def _do_paste(self):
        if sys.platform != "win32": return
        try:
            import ctypes
            u = ctypes.windll.user32
            u.keybd_event(0x11, 0, 0, 0)
            u.keybd_event(0x56, 0, 0, 0)
            u.keybd_event(0x56, 0, 2, 0)
            u.keybd_event(0x11, 0, 2, 0)
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # THEME
    # ─────────────────────────────────────────────────────────────
    def _apply_theme(self, theme_name: str = None):
        if theme_name is None:
            theme_name = self.data["settings"].get("theme", "Default")
        self.data["settings"]["theme"] = theme_name
        self.setStyleSheet(get_stylesheet(theme_name))
        self._palette = get_palette(theme_name)
        p = self._palette

        # Aurora background follows the theme
        if hasattr(self, '_aurora'):
            self._aurora.set_palette(p)
        if hasattr(self, '_shortcuts_overlay'):
            self._shortcuts_overlay.set_accent(p.get("accent", "#00e87a"))

        accent = p.get("accent", "#00e87a")
        dim    = p.get("dim",    "#6e7d90")
        panel  = p.get("panel",  "#0d1117")
        border = p.get("border", "#1f2d3d")
        card   = p.get("card",   "#111827")
        text   = p.get("text",   "#cdd9e5")
        hover  = p.get("hover",  "#182030")
        bg     = p.get("bg",     "#080b12")

        # Title bar
        self._accent_mark.setStyleSheet(
            f"background:{accent}; border-radius:2px;")
        if hasattr(self, '_accent_mark_glow'):
            self._accent_mark_glow.setColor(QColor(accent))
        _a2 = self._palette.get('accent2', accent)
        self._accent_line.set_accent(accent, _a2)
        # Gradient title — update every theme change
        if hasattr(self, '_gradient_title'):
            self._gradient_title.set_accent(accent, _a2)
            self._gradient_title.update()
        if hasattr(self, '_wordmark'):
            self._wordmark.set_accent(accent)
        if hasattr(self, '_wordmark_glow'):
            self._wordmark_glow.setColor(QColor(accent))
        if hasattr(self, '_wordmark'):
            self._wordmark.update()

        # Clock — same shared chip helper as Keep-Alive, recoloured per theme
        self._style_status_chip(self._clock, dim, mono=True)
        for s in [self._s1, self._s2]:
            s.setStyleSheet(f"background:{border};")

        # Nav btn
        self._nav_btn.setStyleSheet(
            f"QPushButton{{background:{card};color:{text};border:1px solid {border};"
            f"border-radius:8px;padding:0 10px;font-size:9px;font-weight:700;"
            f"letter-spacing:1px;}}"
            f"QPushButton:hover{{background:{hover};border-color:{dim};}}")

        # Nav dropdown background
        self._nav_dropdown.setStyleSheet(
            f"background:rgba(8,13,22,0.94); border-bottom:1px solid rgba(255,255,255,0.07);")

        # Status bar
        for w in [self._status_copies, self._status_theme, self._shift_display]:
            w.setStyleSheet(
                f"background:transparent;color:{dim};"
                f"font-size:10px;border:none;")

        self._status_theme.setText(theme_name.upper())
        self._status_theme.setStyleSheet(
            f"background:transparent;color:{dim};font-size:10px;"
            f"font-weight:700;letter-spacing:1px;border:none;")

        # Toast + pomodoro
        if hasattr(self, "toast"):
            self.toast.set_accent(accent)
        if hasattr(self, "_pomo_widget"):
            self._pomo_widget.update_accent(accent, dim)

        # Re-draw nav active state
        self._nav_to(self._current_nav)

        # Update panel transition bg
        if hasattr(self, '_panel_trans'):
            self._panel_trans.set_bg_color(bg)
            self._panel_trans.resize(self.size())

        # Update particles
        if hasattr(self, '_particles'):
            self._particles.set_accent(accent)

        # Propagate to panels
        for panel_w in self._panels.values():
            if hasattr(panel_w, "set_palette"):
                panel_w.set_palette(self._palette)

        D.save(self.data)

    # ─────────────────────────────────────────────────────────────
    # PIN / OPACITY
    # ─────────────────────────────────────────────────────────────
    def _toggle_pin(self):
        aot = not self.data["settings"].get("always_on_top", False)
        self.data["settings"]["always_on_top"] = aot
        self._quitting = True
        flags = Qt.WindowType.FramelessWindowHint
        if aot:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self._quitting = False
        self.show()
        accent = self._palette.get("accent", "#00e87a")
        # Pin button goes accent-coloured when active
        if aot:
            self._pin_btn.setStyleSheet(
                f"QPushButton{{background:{accent};border:none;border-radius:8px;}}"
                f"QPushButton:hover{{background:{accent};}}")
        else:
            self._pin_btn.setStyleSheet(
                "QPushButton{background:#fbbf24;border:none;border-radius:8px;}"
                "QPushButton:hover{background:#f59e0b;}")
        D.save(self.data)

    def _on_opacity(self, v: int):
        self.setWindowOpacity(v / 100.0)
        self.data["settings"]["opacity"] = v

    # ─────────────────────────────────────────────────────────────
    # TRAY
    # ─────────────────────────────────────────────────────────────
    def _init_tray(self):
        self._tray = QSystemTrayIcon(self)
        px = QPixmap(32, 32)
        px.fill(Qt.GlobalColor.transparent)
        p2 = QPainter(px)
        p2.setRenderHint(QPainter.RenderHint.Antialiasing)
        p2.setBrush(QColor("#00e87a"))
        p2.setPen(Qt.PenStyle.NoPen)
        p2.drawRoundedRect(2, 2, 28, 28, 6, 6)
        p2.setPen(QColor("#080b12"))
        p2.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        p2.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "CC")
        p2.end()
        self._tray.setIcon(QIcon(px))
        self._tray.setToolTip("Command Centre Pro")

        m = QMenu()
        m.addAction("Show / Hide",  self._toggle_visibility)
        m.addAction("Commands",     lambda: self._show_nav("commands"))
        m.addAction("Tickets",      lambda: self._show_nav("tickets"))
        m.addAction("Analytics",    lambda: self._show_nav("analytics"))
        m.addSeparator()
        m.addAction("Quick Launch", self._toggle_quick_launch)
        m.addAction("Pomodoro",     self._pomo_widget.toggle)
        m.addSeparator()
        m.addAction("Exit",         self._quit)
        self._tray.setContextMenu(m)
        self._tray.activated.connect(self._tray_activated)
        self._tray.show()

    def _show_nav(self, key):
        self.show(); self.raise_(); self.activateWindow()
        self._nav_to(key)

    def _hide_to_tray(self): self.hide()

    def _toggle_visibility(self):
        if self.isVisible() and self.isActiveWindow():
            self.hide()
        else:
            self.show(); self.raise_(); self.activateWindow()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_visibility()

    # ─────────────────────────────────────────────────────────────
    # QUICK LAUNCH
    # ─────────────────────────────────────────────────────────────
    def _toggle_quick_launch(self):
        if not hasattr(self, "_ql_bar"):
            self._ql_bar = QuickLaunchBar(self)
        if self._ql_bar.isVisible(): self._ql_bar.hide()
        else: self._ql_bar.refresh(); self._ql_bar.show()

    # ─────────────────────────────────────────────────────────────
    # HOTKEYS
    # ─────────────────────────────────────────────────────────────
    def _init_hotkeys(self):
        self._hotkey_mgr = HotkeyManager(self)
        self._command_palette = None

    def portal_in(self):
        """Portal zoom-in effect when window is brought forward via Alt+C."""
        if not hasattr(self, "_portal_anim_running"):
            self._portal_anim_running = False
        if self._portal_anim_running:
            return
        self._portal_anim_running = True

        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QRect

        screen_center = self.geometry().center()
        full_geo = self.geometry()

        # Start small and centred on the same point, scale up to full size
        shrink_w = int(full_geo.width()  * 0.85)
        shrink_h = int(full_geo.height() * 0.85)
        start_geo = QRect(
            screen_center.x() - shrink_w // 2,
            screen_center.y() - shrink_h // 2,
            shrink_w, shrink_h
        )

        self.setGeometry(start_geo)
        self.setWindowOpacity(0.0)

        geo_anim = QPropertyAnimation(self, b"geometry")
        geo_anim.setDuration(220)
        geo_anim.setStartValue(start_geo)
        geo_anim.setEndValue(full_geo)
        geo_anim.setEasingCurve(QEasingCurve.Type.OutBack)

        op_anim = QPropertyAnimation(self, b"windowOpacity")
        op_anim.setDuration(180)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        def _done():
            self._portal_anim_running = False

        geo_anim.finished.connect(_done)
        geo_anim.start()
        op_anim.start()
        self._portal_geo_anim = geo_anim
        self._portal_op_anim  = op_anim

    def show_command_palette(self):
        """Show the immersive full-screen command palette (Alt+Space)."""
        if self._command_palette is None:
            self._command_palette = CommandPalette(self)
            self._command_palette.copy_requested.connect(
                self._on_palette_copy)
        self._command_palette.load_commands(self.data.get("commands", {}))
        self._command_palette.show_palette()

    def _on_palette_copy(self, label: str, text: str):
        # Reuse the exact same logic as normal command copy
        # (handles clipboard, toast, stats, history, copy burst)
        self._on_copy(label, text, "")

    # ─────────────────────────────────────────────────────────────
    # TIMERS
    # ─────────────────────────────────────────────────────────────
    def _init_timers(self):
        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._update_clock)
        self._clock_timer.start(1000)
        self._update_clock()

        self._reminder_timer = QTimer(self)
        self._reminder_timer.timeout.connect(self._check_reminders)
        self._reminder_timer.start(10000)

        self._save_timer = QTimer(self)
        self._save_timer.timeout.connect(lambda: D.save(self.data))
        self._save_timer.start(60000)

        self._shift_display_timer = QTimer(self)
        self._shift_display_timer.timeout.connect(self._update_shift_display)
        self._shift_display_timer.start(1000)

        self._update_status()

    def _update_clock(self):
        self._clock.setText(datetime.now().strftime('%H:%M:%S'))

    def _update_status(self):
        today = datetime.now().strftime("%Y-%m-%d")
        stats = self.data.get("session_stats", {})
        count = stats.get("copies_today", 0) if stats.get("last_reset_date") == today else 0
        total = stats.get("copies_total", 0)
        self._status_copies.setText(f"{count} today  /  {total} total")

    def _update_shift_display(self):
        panel = self._panels.get("tickets")
        if panel and hasattr(panel, "shift_timer"):
            st = panel.shift_timer
            if st._running:
                self._shift_display.setText(f"  ·  {st._lbl.text()}")
            else:
                self._shift_display.setText("")

    def _check_reminders(self):
        try:
            from src.panels.reminders import check_and_fire
            check_and_fire(self.data, self)
        except Exception as e:
            print(f"[CCP] Reminder error: {e}")

    def _on_settings_changed(self):
        self._apply_theme(); self._update_status()

    # ─────────────────────────────────────────────────────────────
    # DRAG
    # ─────────────────────────────────────────────────────────────
    def eventFilter(self, obj, event):
        # Keep the aurora background exactly sized to the central widget,
        # no matter when/how the layout changes — fixes it being stuck small
        # in the corner. Also keep it behind all sibling content.
        if obj is getattr(self, '_aurora_host', None) and hasattr(self, '_aurora'):
            from PyQt6.QtCore import QEvent
            if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
                self._aurora.setGeometry(obj.rect())
                self._aurora.lower()
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_glass_bar'):
            # Keep content bar filling glass bar
            for child in self._glass_bar.children():
                if hasattr(child, 'resize') and hasattr(child, 'height'):
                    try: child.resize(self._glass_bar.width(), child.height())
                    except: pass
        cw = self.centralWidget()
        if hasattr(self, '_aurora') and cw:
            self._aurora.setGeometry(0, 0, cw.width(), cw.height())
            self._aurora.lower()
        if hasattr(self, '_panel_trans'):
            self._panel_trans.resize(cw.size() if cw else self.size())
        if hasattr(self, '_copy_burst'):
            self._copy_burst.resize(self.size())
        if hasattr(self, '_update_dialog') and self._update_dialog.isVisible():
            self._update_dialog.setGeometry(self.rect())

    def showEvent(self, event):
        super().showEvent(event)
        cw = self.centralWidget()
        if hasattr(self, '_aurora') and cw:
            self._aurora.setGeometry(0, 0, cw.width(), cw.height())
            self._aurora.lower()
    def keyPressEvent(self, event):
        # ? or F1 → show the keyboard shortcuts reference (discoverability)
        if event.key() in (Qt.Key.Key_Question, Qt.Key.Key_F1):
            if hasattr(self, '_shortcuts_overlay'):
                self._shortcuts_overlay.show_overlay()
                return
        super().keyPressEvent(event)

    def _check_for_update(self, manual=False):
        """
        Check GitHub for a newer build.
          • silent (startup): only speaks up if an update exists.
          • manual (button):  also reports 'up to date' / errors, and shows a
            'checking…' state so the user gets feedback either way.
        """
        try:
            from src.updater import UpdateChecker, is_frozen, APP_VERSION
            self._update_manual = manual

            if manual and not is_frozen():
                # Running from source — no exe to update. Be honest about it.
                self.toast.show_toast("Updates only work in the built app")
                return

            if manual:
                self.toast.show_toast("Checking for updates…")

            self._update_checker = UpdateChecker()
            self._update_checker.update_available.connect(self._on_update_available)
            if manual:
                self._update_checker.up_to_date.connect(self._on_up_to_date)
                self._update_checker.check_failed.connect(self._on_check_failed)
            self._update_checker.start()
        except Exception as e:
            if manual:
                self.toast.show_toast("Update check failed")

    def _on_update_available(self, url, when, size, digest):
        if hasattr(self, "_update_dialog"):
            self._update_dialog.set_accent(self._palette.get("accent", "#00e87a"))
            self._update_dialog.offer(url, when, size, digest)

    def _on_up_to_date(self):
        # Only fires for a manual check (startup check leaves this unconnected).
        from src.updater import APP_VERSION
        self.toast.show_toast(f"You're up to date  ·  v{APP_VERSION}")

    def check_for_update_manual(self):
        """Public entry point for the Settings 'Check for updates' button."""
        self._check_for_update(manual=True)

    def _on_check_failed(self, msg):
        # Only fires for a manual check.
        self.toast.show_toast("Couldn't reach GitHub to check")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and event.position().y() < 46:
            self._dragging = True
            self._drag_pos = (event.globalPosition().toPoint()
                              - self.frameGeometry().topLeft())

    def mouseMoveEvent(self, event):
        if self._dragging and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event):
        self._dragging = False

    # ─────────────────────────────────────────────────────────────
    # QUIT
    # ─────────────────────────────────────────────────────────────
    def _quit(self):
        self._quitting = True
        pos = self.pos()
        self.data["settings"]["window_pos"] = [pos.x(), pos.y()]
        D.save(self.data)
        if hasattr(self, "_hotkey_mgr"):
            self._hotkey_mgr.stop()
        QApplication.quit()

    def closeEvent(self, event):
        if self._quitting: event.accept()
        else: event.ignore(); self._hide_to_tray()
