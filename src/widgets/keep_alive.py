"""
keep_alive.py — Background window keep-alive.

Targets "POS Support GUI" by window title.
Every 4 minutes sends a silent WM_KEYDOWN (VK_SHIFT) directly
to the window's message queue — no focus steal, no visible effect.
Falls back to a mouse wiggle over the window if direct message fails.

Runs in a QThread so it never blocks the UI.
"""
import sys
import time
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox

FONT = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"

# Target window — partial match so version number doesn't matter
TARGET_TITLE = "POS Support GUI"
INTERVAL_MS  = 4 * 60 * 1000   # 4 minutes


class KeepAliveWorker(QThread):
    status_update = pyqtSignal(str)   # status message → UI
    found_window  = pyqtSignal(bool)  # True if target found

    def __init__(self):
        super().__init__()
        self._running  = False
        self._interval = INTERVAL_MS

    def set_interval(self, ms: int):
        self._interval = ms

    def _get_idle_ms(self) -> int:
        """
        Milliseconds since last system-wide keyboard/mouse input.
        Uses the same GetLastInputInfo API Windows itself uses for
        idle/screensaver detection — the authoritative source.
        """
        try:
            import ctypes
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint),
                            ("dwTime", ctypes.c_uint)]
            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
            return millis
        except Exception:
            return 999999  # assume idle if API fails — safe default

    def run(self):
        if sys.platform != "win32":
            self.status_update.emit("Windows only — keep-alive not available.")
            return

        import ctypes
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32

        WM_KEYDOWN = 0x0100
        WM_KEYUP   = 0x0101
        VK_SHIFT   = 0x10    # Shift key — completely harmless

        def find_window():
            """Find the POS Support GUI window handle."""
            result = []

            def enum_callback(hwnd, _):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, length + 1)
                    title = buf.value
                    if TARGET_TITLE.lower() in title.lower():
                        result.append((hwnd, title))
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
            user32.EnumWindows(WNDENUMPROC(enum_callback), 0)
            return result

        def ping_input():
            """
            Inject a REAL but invisible input event via SendInput. Unlike
            PostMessageW (which posts to a window's queue and does NOT reset
            the system idle timer), SendInput generates a genuine input event
            that resets GetLastInputInfo — the same timer the POS GUI's idle
            logout watches. We nudge the mouse by 0 pixels: no visible cursor
            movement, but it counts as activity.
            """
            # MOUSEINPUT via SendInput
            PUL = ctypes.POINTER(ctypes.c_ulong)

            class MOUSEINPUT(ctypes.Structure):
                _fields_ = [("dx", ctypes.c_long),
                            ("dy", ctypes.c_long),
                            ("mouseData", ctypes.c_ulong),
                            ("dwFlags", ctypes.c_ulong),
                            ("time", ctypes.c_ulong),
                            ("dwExtraInfo", PUL)]

            class _INPUTunion(ctypes.Union):
                _fields_ = [("mi", MOUSEINPUT)]

            class INPUT(ctypes.Structure):
                _fields_ = [("type", ctypes.c_ulong),
                            ("u", _INPUTunion)]

            MOUSEEVENTF_MOVE = 0x0001
            extra = ctypes.c_ulong(0)
            mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_MOVE, 0, ctypes.cast(ctypes.byref(extra), PUL))
            inp = INPUT(0, _INPUTunion(mi=mi))
            user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))

        def ping_window(hwnd):
            """
            Keep the session alive. Primary: SendInput real-input nudge (the
            only thing that reliably resets the idle timer). Secondary: also
            post a harmless key to the target window in case the GUI additionally
            tracks per-window messages. If minimised, we do NOT restore — the
            SendInput nudge works regardless of window state.
            """
            # Real input event — resets the OS idle timer.
            ping_input()

            # Belt-and-braces: also poke the window's own queue (harmless).
            try:
                user32.PostMessageW(hwnd, WM_KEYDOWN, VK_SHIFT, 0)
                user32.PostMessageW(hwnd, WM_KEYUP,   VK_SHIFT, 0)
            except Exception:
                pass

        self._running = True
        self.status_update.emit("Keep-alive started. Watching for POS Support GUI…")

        consecutive_misses = 0
        last_user_input    = self._get_idle_ms()

        while self._running:
            windows = find_window()

            if windows:
                hwnd, title = windows[0]
                self.found_window.emit(True)
                consecutive_misses = 0

                # ── Smart logic: skip ping if user is ALREADY active ──
                # Research: most apps detect activity via system-wide
                # input events (GetLastInputInfo), not window-specific.
                # If the engineer has typed/clicked anywhere in the last
                # 60 seconds, the OS-level session is already alive —
                # no need to also ping. Saves CPU and avoids unnecessary
                # window restores.
                idle_ms = self._get_idle_ms()
                if idle_ms < 60000:
                    t = time.strftime("%H:%M:%S")
                    self.status_update.emit(
                        f"[{t}]  Skipped — user active ({idle_ms//1000}s ago)")
                else:
                    ping_window(hwnd)
                    t = time.strftime("%H:%M:%S")
                    self.status_update.emit(
                        f"[{t}]  Pinged — {title[:40]}")
            else:
                self.found_window.emit(False)
                consecutive_misses += 1
                # Back off if window hasn't appeared in a while —
                # reduces log spam when POS GUI is simply closed
                if consecutive_misses <= 3:
                    self.status_update.emit(
                        f"[{time.strftime('%H:%M:%S')}]  POS GUI not found — waiting…")

            # Sleep in 1-second chunks so stop() is responsive
            slept = 0
            while self._running and slept < self._interval:
                time.sleep(1)
                slept += 1000

    def stop(self):
        self._running = False
        self.quit()


# ── Keep-alive panel (embedded in CCP nav) ────────────────────────
class KeepAlivePanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app      = app
        self._worker  = None
        self._palette = {}
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet("background:transparent;")
        settings = getattr(self.app, "data", {}).get("settings", {}) if self.app else {}
        saved_interval = settings.get("keep_alive_interval_min", 4)
        saved_enabled  = settings.get("keep_alive_enabled", False)
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(12)

        # ── Header card ───────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 rgba(16,24,36,0.90),stop:1 rgba(10,16,26,0.80));"
            "border:1px solid rgba(255,255,255,0.08);"
            "border-top:1px solid rgba(255,255,255,0.12);"
            "border-radius:12px;")
        from src.widgets.hover_lift import add_hover_lift
        add_hover_lift(hdr, lift=2)
        hl = QVBoxLayout(hdr); hl.setContentsMargins(18,16,18,16); hl.setSpacing(8)

        title_row = QHBoxLayout()
        dot = QLabel("●"); dot.setFixedWidth(14)
        dot.setStyleSheet("background:transparent;color:#6b83a0;font-size:9px;border:none;")
        self._dot = dot
        title_row.addWidget(dot)
        t = QLabel("POS GUI KEEP-ALIVE")
        t.setStyleSheet(
            f"background:transparent;color:#d4dfe9;font-size:10px;"
            f"font-weight:700;letter-spacing:2px;border:none;font-family:{FONT};")
        title_row.addWidget(t); title_row.addStretch()

        self._status_pill = QLabel("INACTIVE")
        self._status_pill.setStyleSheet(
            "background:#1a0808;color:#f87171;font-size:9px;font-weight:700;"
            "letter-spacing:2px;border:1px solid #f87171;border-radius:12px;"
            "padding:2px 10px;")
        title_row.addWidget(self._status_pill)
        hl.addLayout(title_row)

        desc = QLabel(
            "Sends a silent Shift keypress to the POS Support GUI every\n"
            "4 minutes to prevent session timeout. Never steals focus.")
        desc.setStyleSheet(
            f"background:transparent;color:#6e7d90;font-size:10px;"
            f"border:none;font-family:{FONT};line-height:1.5;")
        hl.addWidget(desc)

        # Interval selector
        int_row = QHBoxLayout(); int_row.setSpacing(10)
        int_lbl = QLabel("Ping every:")
        int_lbl.setStyleSheet(
            f"background:transparent;color:#6b7f96;font-size:10px;border:none;font-family:{FONT};")
        int_row.addWidget(int_lbl)
        self._interval_combo = QComboBox()
        self._interval_combo.addItems(["2 minutes","3 minutes","4 minutes","5 minutes","10 minutes"])
        _minutes_opts = [2, 3, 4, 5, 10]
        _default_idx  = _minutes_opts.index(saved_interval) if saved_interval in _minutes_opts else 2
        self._interval_combo.setCurrentIndex(_default_idx)  # restored from saved settings
        self._interval_combo.setFixedHeight(28)
        self._interval_combo.setStyleSheet(
            f"QComboBox{{background:rgba(5,8,16,0.8);color:#d4dfe9;"
            f"border:1px solid rgba(255,255,255,0.08);border-radius:8px;"
            f"padding:4px 10px;font-size:11px;font-family:{FONT};}}"
            f"QComboBox QAbstractItemView{{background:#0a101a;color:#d4dfe9;"
            f"border:1px solid rgba(255,255,255,0.08);"
            f"selection-background-color:#182030;}}")
        self._interval_combo.currentIndexChanged.connect(self._update_interval)
        int_row.addWidget(self._interval_combo); int_row.addStretch()
        hl.addLayout(int_row)
        root.addWidget(hdr)

        # ── Toggle button ─────────────────────────────────────
        self._toggle_btn = QPushButton("▶   Start Keep-Alive")
        self._toggle_btn.setFixedHeight(44)
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #00e87a,stop:1 #38bdf8);"
            f"color:#060a10;border:none;border-radius:12px;"
            f"font-size:12px;font-weight:700;font-family:{FONT};}}"
            f"QPushButton:hover{{background:qlineargradient(x1:1,y1:0,x2:0,y2:1,"
            f"stop:0 #00e87a,stop:1 #38bdf8);}}"
            f"QPushButton:disabled{{background:#1a2840;color:#6b83a0;}}")
        self._toggle_btn.clicked.connect(self._toggle)
        root.addWidget(self._toggle_btn)

        # ── Log ───────────────────────────────────────────────
        log_lbl = QLabel("ACTIVITY LOG")
        log_lbl.setStyleSheet(
            f"background:transparent;color:#6b83a0;font-size:9px;"
            f"font-weight:700;letter-spacing:2px;border:none;font-family:{FONT};")
        root.addWidget(log_lbl)

        self._log = QLabel("No activity yet.")
        self._log.setWordWrap(True)
        self._log.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._log.setStyleSheet(
            f"background:rgba(5,8,16,0.6);color:#6e7d90;"
            f"border:1px solid rgba(255,255,255,0.06);border-radius:8px;"
            f"font-size:10px;padding:10px 12px;border:none;"
            f"font-family:'JetBrains Mono','Consolas',monospace;")
        root.addWidget(self._log)
        root.addStretch()

        self._log.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        if saved_enabled:
            self._start()

    def _update_interval(self, idx):
        minutes = [2, 3, 4, 5, 10][idx]
        if self._worker:
            self._worker.set_interval(minutes * 60 * 1000)
        self._persist(interval_min=minutes)

    def _toggle(self):
        if self._worker and self._worker.isRunning():
            self._stop()
        else:
            self._start()

    def _start(self):
        idx     = self._interval_combo.currentIndex()
        minutes = [2, 3, 4, 5, 10][idx]
        p       = self._palette
        accent  = p.get("accent", "#00e87a")
        accent2 = p.get("accent2", "#38bdf8")

        self._worker = KeepAliveWorker()
        self._worker.set_interval(minutes * 60 * 1000)
        self._worker.status_update.connect(self._on_status)
        self._worker.found_window.connect(self._on_found)
        self._worker.start()
        self._persist(enabled=True, interval_min=minutes)

        self._toggle_btn.setText("■   Stop Keep-Alive")
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #f87171,stop:1 #e6a817);"
            f"color:#060a10;border:none;border-radius:12px;"
            f"font-size:12px;font-weight:700;font-family:{FONT};}}"
            f"QPushButton:hover{{background:#f87171;}}")
        self._status_pill.setText("ACTIVE")
        self._status_pill.setStyleSheet(
            f"background:#0a1a0a;color:{accent};font-size:9px;font-weight:700;"
            f"letter-spacing:2px;border:1px solid {accent};border-radius:12px;padding:2px 10px;")
        self._dot.setStyleSheet(f"background:transparent;color:{accent};font-size:9px;border:none;")

    def _stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(3000)
            self._worker = None

        self._toggle_btn.setText("▶   Start Keep-Alive")
        self._toggle_btn.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 #00e87a,stop:1 #38bdf8);"
            f"color:#060a10;border:none;border-radius:12px;"
            f"font-size:12px;font-weight:700;font-family:{FONT};}}"
            f"QPushButton:hover{{background:qlineargradient(x1:1,y1:0,x2:0,y2:1,"
            f"stop:0 #00e87a,stop:1 #38bdf8);}}")
        self._status_pill.setText("INACTIVE")
        self._status_pill.setStyleSheet(
            "background:#1a0808;color:#f87171;font-size:9px;font-weight:700;"
            "letter-spacing:2px;border:1px solid #f87171;border-radius:12px;padding:2px 10px;")
        self._dot.setStyleSheet("background:transparent;color:#6b83a0;font-size:9px;border:none;")
        self._log_line("Keep-alive stopped.")
        self._persist(enabled=False)

    def _persist(self, enabled: bool = None, interval_min: int = None):
        """Save keep-alive enabled/interval state to CommandCentre.json."""
        if not self.app or not hasattr(self.app, "data"):
            return
        settings = self.app.data.setdefault("settings", {})
        if enabled is not None:
            settings["keep_alive_enabled"] = enabled
        if interval_min is not None:
            settings["keep_alive_interval_min"] = interval_min
        try:
            from src import data as D
            D.save(self.app.data)
        except Exception:
            pass

    def _on_status(self, msg: str):
        self._log_line(msg)

    def _on_found(self, found: bool):
        pass  # pill colour already handled by _start/_stop

    def _log_line(self, msg: str):
        current = self._log.text()
        lines   = [l for l in current.split("\n") if l.strip() and l != "No activity yet."]
        lines.append(msg)
        lines   = lines[-8:]   # keep last 8 lines
        self._log.setText("\n".join(lines))

    def refresh(self):
        pass

    def set_palette(self, p: dict):
        self._palette = p
        accent  = p.get("accent", "#00e87a")
        accent2 = p.get("accent2", "#38bdf8")
        if self._worker and self._worker.isRunning():
            self._status_pill.setStyleSheet(
                f"background:#0a1a0a;color:{accent};font-size:9px;font-weight:700;"
                f"letter-spacing:2px;border:1px solid {accent};border-radius:12px;padding:2px 10px;")
            self._dot.setStyleSheet(
                f"background:transparent;color:{accent};font-size:9px;border:none;")
