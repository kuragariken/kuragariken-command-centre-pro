"""panels/reminders.py — Epic full-screen alarm overlay with snooze."""
import sys
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit,
    QComboBox, QTimeEdit, QFrame, QApplication, QGraphicsOpacityEffect
)
from PyQt6.QtCore import (
    Qt, QTime, QTimer, pyqtSignal, QPropertyAnimation,
    QEasingCurve, QRect, QRectF, QPoint, QPointF
)
from PyQt6.QtGui import (QFont, QColor, QPainter, QPainterPath,
                          QLinearGradient, QRadialGradient, QBrush, QPen)

from src import data as D

SNOOZE_MINUTES = [5, 10, 15]


class AlarmOverlay(QWidget):
    """
    Full-screen premium alarm overlay.
    Animations:
      - Dark translucent backdrop with radial vignette
      - 5 expanding pulse rings from card centre
      - Aurora mist orbs drifting around the card
      - Floating particle sparks
      - Breathing card border glow
      - Card slides in from above with spring easing
    """
    snoozed   = pyqtSignal(int)
    dismissed = pyqtSignal()

    def __init__(self, label: str, accent: str = "#00e87a"):
        super().__init__(None)
        self._label   = label
        self._accent  = QColor(accent)
        self._accent_str = accent
        self._tick    = 0.0
        self._card_y  = -400   # slides in from above

        # Pulse rings — each has its own phase offset
        self._rings = [{"r": 0.0, "alpha": 0} for _ in range(7)]
        self._ring_phase = [i * 0.16 for i in range(7)]

        # Mist orbs
        import random, math
        self._orbs = [
            {
                "angle": random.uniform(0, math.tau),
                "speed": random.uniform(0.004, 0.016),
                "dist":  random.uniform(160, 420),
                "size":  random.uniform(100, 220),
                "alpha": random.uniform(22, 46),
            }
            for _ in range(10)
        ]

        # Spark particles
        self._sparks = [
            {
                "x":     random.uniform(-1, 1),
                "y":     random.uniform(-1, 1),
                "vx":    random.uniform(-0.0035, 0.0035),
                "vy":    random.uniform(-0.005, -0.0015),
                "life":  random.uniform(0, 1),
                "size":  random.uniform(1.5, 4.5),
                "alpha": random.uniform(110, 230),
            }
            for _ in range(60)
        ]

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self._sw = screen.width()
        self._sh = screen.height()

        self._cx = self._sw // 2
        self._cy = self._sh // 2

        self._build_card()
        self._play_sound()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(16)

        QTimer.singleShot(180000, self._dismiss)

    def _build_card(self):
        self._card = QWidget(self)
        self._card.setFixedSize(540, 360)
        self._card.move((self._sw - 540) // 2, -400)
        self._card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._card.setStyleSheet(
            "QWidget{"
            "background:rgba(8,13,22,0.96);"
            "border-radius:22px;"
            "}")

        root = QVBoxLayout(self._card)
        root.setContentsMargins(44, 32, 44, 32)
        root.setSpacing(0)

        top = QHBoxLayout()
        self._time_lbl = QLabel(datetime.now().strftime("%H:%M:%S"))
        self._time_lbl.setFont(QFont("JetBrains Mono", 11))
        self._time_lbl.setStyleSheet("background:transparent;color:#3a4e64;border:none;")
        top.addWidget(self._time_lbl)
        top.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(30, 30)
        x_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#3a4e64;border:none;"
            "border-radius:8px;font-size:14px;font-weight:700;}"
            "QPushButton:hover{background:rgba(248,113,113,0.15);color:#f87171;}")
        x_btn.clicked.connect(self._dismiss)
        top.addWidget(x_btn)
        root.addLayout(top)
        root.addSpacing(10)

        # Bell icon
        bell = QLabel("🔔")
        bell.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bell.setStyleSheet("background:transparent;border:none;font-size:32px;")
        root.addWidget(bell)
        root.addSpacing(8)

        # Label
        lbl = QLabel(self._label)
        lbl.setFont(QFont("Inter", 22, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setWordWrap(True)
        lbl.setStyleSheet("background:transparent;color:#e2e8f0;border:none;")
        root.addWidget(lbl)
        root.addSpacing(6)

        sub = QLabel("● REMINDER ALERT ●")
        sub.setFont(QFont("Inter", 9, QFont.Weight.Bold))
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(
            f"background:transparent;color:{self._accent_str};"
            f"letter-spacing:4px;border:none;")
        root.addWidget(sub)
        root.addSpacing(24)

        snooze_row = QHBoxLayout(); snooze_row.setSpacing(8)
        snooze_lbl = QLabel("SNOOZE:")
        snooze_lbl.setStyleSheet(
            "background:transparent;color:#3a4e64;font-size:10px;"
            "font-weight:700;letter-spacing:1px;border:none;")
        snooze_row.addWidget(snooze_lbl)
        for mins in SNOOZE_MINUTES:
            sb = QPushButton(f"{mins} min")
            sb.setFixedHeight(34)
            sb.setFont(QFont("Inter", 10, QFont.Weight.Bold))
            sb.setStyleSheet(
                f"QPushButton{{background:rgba(13,21,32,0.8);color:#cdd9e5;"
                f"border:1px solid rgba(255,255,255,0.08);"
                f"border-radius:10px;padding:0 16px;font-weight:600;}}"
                f"QPushButton:hover{{background:rgba(20,31,48,0.9);"
                f"border-color:{self._accent_str};color:{self._accent_str};}}")
            sb.clicked.connect(lambda checked, m=mins: self._snooze(m))
            snooze_row.addWidget(sb)
        snooze_row.addStretch()
        root.addLayout(snooze_row)
        root.addSpacing(14)

        dismiss = QPushButton("   Acknowledge   ")
        dismiss.setFixedHeight(50)
        dismiss.setFont(QFont("Inter", 13, QFont.Weight.Bold))
        acc2 = self._accent_str
        dismiss.setStyleSheet(
            f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {acc2},stop:1 {acc2}cc);"
            f"color:#060a10;border:none;border-radius:14px;font-weight:700;"
            f"letter-spacing:0.5px;}}"
            f"QPushButton:hover{{background:{acc2};}}"
            f"QPushButton:pressed{{background:{acc2}aa;}}")
        dismiss.clicked.connect(self._dismiss)
        root.addWidget(dismiss)

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(
            lambda: self._time_lbl.setText(datetime.now().strftime("%H:%M:%S")))
        self._clock_timer.start(1000)

    def _animate(self):
        import math
        self._tick += 0.012

        # Slide card in with spring easing
        target_y = (self._sh - 360) // 2
        cy = self._card.y()
        if cy < target_y:
            new_y = min(target_y, cy + max(1, (target_y - cy) // 6 + 4))
            self._card.move(self._card.x(), new_y)

        # Update 5 staggered pulse rings
        for i, ring in enumerate(self._rings):
            phase = self._tick + self._ring_phase[i]
            ring["r"]     = abs(math.sin(phase * 0.8)) * 200 + 60
            ring["alpha"] = max(0, int(80 * (1 - (ring["r"] - 60) / 200)))

        # Drift mist orbs
        for orb in self._orbs:
            orb["angle"] = (orb["angle"] + orb["speed"]) % (2 * math.pi)

        # Update sparks
        for sp in self._sparks:
            sp["x"]    += sp["vx"]
            sp["y"]    += sp["vy"]
            sp["life"] += 0.008
            if sp["life"] > 1.0:
                sp["x"]    = 0
                sp["y"]    = 0
                sp["vx"]   = __import__("random").uniform(-0.003, 0.003)
                sp["vy"]   = __import__("random").uniform(-0.005, -0.001)
                sp["life"] = 0
                sp["alpha"]= __import__("random").uniform(100, 200)

        self.update()

    def paintEvent(self, event):
        import math
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        cx, cy = self._cx, self._cy

        ac = self._accent

        # ── Dark vignette backdrop ─────────────────────────────
        p.fillRect(0, 0, w, h, QColor(0, 0, 0, 175))

        # ── Cinematic full-screen colour wash — pulses with theme ──
        wash_alpha = int(14 + 8 * math.sin(self._tick * 0.6))
        wash = QColor(ac); wash.setAlpha(max(0, wash_alpha))
        p.fillRect(0, 0, w, h, wash)

        # Radial vignette
        vg = QRadialGradient(QPointF(cx, cy), max(w, h) * 0.75)
        vg.setColorAt(0, QColor(0, 0, 0, 0))
        vg.setColorAt(1, QColor(0, 0, 0, 130))
        p.fillRect(0, 0, w, h, QBrush(vg))

        # ── Pulsing screen-edge frame — cinematic letterbox glow ──
        edge_alpha = int(35 + 25 * math.sin(self._tick * 0.9))
        edge_c = QColor(ac); edge_c.setAlpha(max(0, edge_alpha))
        for thickness in [2, 6, 14]:
            ec = QColor(edge_c); ec.setAlpha(max(0, edge_c.alpha() // (thickness//2 or 1)))
            p.setPen(QPen(ec, thickness))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(thickness/2, thickness/2,
                              w - thickness, h - thickness))

        # ── Aurora mist orbs ───────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        for orb in self._orbs:
            ox = cx + math.cos(orb["angle"]) * orb["dist"]
            oy = cy + math.sin(orb["angle"]) * orb["dist"] * 0.55
            r  = orb["size"]
            og = QRadialGradient(QPointF(ox, oy), r)
            c_in  = QColor(ac); c_in.setAlpha(int(orb["alpha"]))
            c_out = QColor(ac); c_out.setAlpha(0)
            og.setColorAt(0, c_in); og.setColorAt(1, c_out)
            p.setBrush(QBrush(og))
            p.drawEllipse(QRectF(ox-r, oy-r, r*2, r*2))

        # ── Pulse rings ────────────────────────────────────────
        for ring in self._rings:
            r  = ring["r"]
            al = ring["alpha"]
            if al <= 0: continue
            for thickness, alpha_mul in [(1.5, 1.0), (6, 0.3), (14, 0.08)]:
                rc = QColor(ac); rc.setAlpha(max(0, int(al * alpha_mul)))
                p.setPen(QPen(rc, thickness))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(QRectF(cx-r, cy-r, r*2, r*2))

        # ── Spark particles ────────────────────────────────────
        p.setPen(Qt.PenStyle.NoPen)
        for sp in self._sparks:
            life_alpha = max(0, int(sp["alpha"] * (1 - sp["life"])))
            if life_alpha < 5: continue
            sc = QColor(ac); sc.setAlpha(life_alpha)
            p.setBrush(QBrush(sc))
            sx = cx + sp["x"] * w * 0.4
            sy = cy + sp["y"] * h * 0.4
            r  = sp["size"] * (1 - sp["life"] * 0.5)
            p.drawEllipse(QRectF(sx-r, sy-r, r*2, r*2))

        # ── Card border breathing glow ─────────────────────────
        import math as _m
        glow_a = int(60 + 50 * _m.sin(self._tick * 2))
        card = self._card
        cx2  = card.x(); cy2 = card.y()
        cw   = card.width(); ch = card.height()
        for size, alpha_mul in [(2, 1.0), (8, 0.4), (18, 0.12), (32, 0.05)]:
            gc = QColor(ac); gc.setAlpha(max(0, int(glow_a * alpha_mul)))
            p.setPen(QPen(gc, size))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(
                QRectF(cx2 - size//2, cy2 - size//2,
                       cw + size, ch + size), 24, 24)

    def _play_sound(self):
        try:
            if sys.platform == "win32":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                QTimer.singleShot(600,  lambda: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION))
                QTimer.singleShot(1200, lambda: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION))
        except Exception:
            pass

    def _snooze(self, mins: int):
        self._timer.stop()
        self._clock_timer.stop()
        self.snoozed.emit(mins)
        self.close()

    def _dismiss(self):
        self._timer.stop()
        self._clock_timer.stop()
        self.dismissed.emit()
        self.close()


class RemindersPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._snooze_timers = {}   # label -> QTimer
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet("background:rgba(6,10,18,0.85); border-bottom:1px solid rgba(255,255,255,0.07);")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 12, 0)
        title = QLabel("REMINDERS")
        title.setStyleSheet(
            "background:transparent;color:#00e87a;font-size:11px;"
            "font-weight:700;letter-spacing:2px;border:none;")
        hl.addWidget(title)
        hl.addStretch()
        add_btn = QPushButton("+ Add Reminder")
        add_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;border-radius:6px;"
            "padding:5px 14px;font-size:11px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        add_btn.clicked.connect(self._add_reminder)
        hl.addWidget(add_btn)
        root.addWidget(hdr)

        self._list = QListWidget()
        self._list.setStyleSheet(
            "QListWidget{background:transparent;border:none;outline:none;}"
            "QListWidget::item{background:#111827;color:#cdd9e5;"
            "border:1px solid #1f2d3d;border-radius:7px;"
            "padding:9px 12px;margin:3px 8px;font-size:12px;}"
            "QListWidget::item:hover{background:#182030;border-color:#4a5568;}"
            "QListWidget::item:selected{background:#182030;border:1px solid #00e87a;}")
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context)
        root.addWidget(self._list, 1)

        footer = QWidget()
        footer.setFixedHeight(36)
        footer.setStyleSheet("background:rgba(5,8,16,0.85); border-top:1px solid rgba(255,255,255,0.06);")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(10, 4, 10, 4)
        test_btn = QPushButton("Test Alarm Now")
        test_btn.setStyleSheet(
            "QPushButton{background:transparent;color:#4a5568;border:1px solid #1f2d3d;"
            "border-radius:5px;padding:2px 10px;font-size:10px;font-weight:600;}"
            "QPushButton:hover{color:#cdd9e5;border-color:#4a5568;background:#182030;}")
        test_btn.clicked.connect(lambda: self._fire_alarm("Test — Alarm System Working!"))
        fl.addWidget(test_btn)
        fl.addStretch()
        root.addWidget(footer)

    def refresh(self):
        self._list.clear()
        for r in self.app.data.get("reminders", []):
            enabled = r.get("enabled", True)
            mode    = r.get("mode", "once")
            snoozed = r.get("snoozedUntil", "")
            snooze_txt = f"  [snoozed until {snoozed}]" if snoozed else ""
            status     = "ON" if enabled else "OFF"
            enabled_dot = "●" if enabled else "○"
            item = QListWidgetItem(
                f"  {enabled_dot}  {r['label']}  ·  {r['time']}  ·  {mode.upper()}{snooze_txt}")
            item.setData(Qt.ItemDataRole.UserRole, r)
            if not enabled:
                item.setForeground(QColor("#4a5568"))
            elif snoozed:
                item.setForeground(QColor("#fbbf24"))
            self._list.addItem(item)

    def _add_reminder(self):
        dlg = ReminderDialog(self)
        if dlg.exec():
            r   = dlg.get_reminder()
            lst = self.app.data.get("reminders", [])
            r["id"] = max((x.get("id", 0) for x in lst), default=0) + 1
            lst.append(r)
            self.app.data["reminders"] = lst
            D.save(self.app.data)
            self.refresh()

    def _context(self, pos):
        item = self._list.itemAt(pos)
        if not item: return
        r = item.data(Qt.ItemDataRole.UserRole)
        from PyQt6.QtWidgets import QMenu
        menu = QMenu(self)
        menu.addAction("Test Now",
            lambda: self._fire_alarm(r["label"]))
        menu.addAction("Disable" if r.get("enabled", True) else "Enable",
            lambda: self._toggle(r))
        menu.addAction("Clear Snooze",
            lambda: self._clear_snooze(r))
        menu.addAction("Delete",
            lambda: self._delete(r))
        menu.exec(self._list.mapToGlobal(pos))

    def _toggle(self, r):
        r["enabled"] = not r.get("enabled", True)
        D.save(self.app.data); self.refresh()

    def _clear_snooze(self, r):
        r.pop("snoozedUntil", None)
        D.save(self.app.data); self.refresh()

    def _delete(self, r):
        self.app.data["reminders"] = [
            x for x in self.app.data.get("reminders", [])
            if x.get("id") != r.get("id")]
        D.save(self.app.data); self.refresh()

    def _fire_alarm(self, label: str):
        accent  = self.app._palette.get("accent", "#00e87a")
        accent2 = self.app._palette.get("accent2", accent)
        overlay = AlarmOverlay(label, accent)
        overlay.snoozed.connect(lambda m, lbl=label: self._handle_snooze(lbl, m))
        overlay.dismissed.connect(lambda: self._on_dismissed(overlay))
        # Keep reference so Python doesn't garbage-collect the overlay
        if not hasattr(self, "_overlays"): self._overlays = []
        self._overlays.append(overlay)
        overlay.show()
        overlay.raise_()
        overlay.activateWindow()

    def _on_dismissed(self, overlay):
        if hasattr(self, "_overlays") and overlay in self._overlays:
            self._overlays.remove(overlay)

    def _handle_snooze(self, label: str, minutes: int):
        """Re-fire alarm after snooze minutes."""
        snooze_ms  = minutes * 60 * 1000
        until_time = datetime.now().strftime(f"%H:%M (+ {minutes}m)")
        # Mark snooze in data
        for r in self.app.data.get("reminders", []):
            if r.get("label") == label:
                r["snoozedUntil"] = until_time
        D.save(self.app.data)
        self.refresh()

        t = QTimer(self)
        t.setSingleShot(True)
        t.timeout.connect(lambda: self._fire_alarm(label))
        t.start(snooze_ms)
        self._snooze_timers[label] = t
        self.app.toast.show_toast(f"Snoozed {label} for {minutes} min")

    def set_palette(self, p):
        pass


class ReminderDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Add Reminder")
        self.setModal(True)
        self.resize(380, 230)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.setContentsMargins(18, 18, 18, 14)
        lay.addWidget(QLabel("Reminder label:"))
        self._label = QLineEdit()
        self._label.setPlaceholderText("e.g. Cash Up, Check CCTV…")
        lay.addWidget(self._label)
        row = QHBoxLayout()
        row.addWidget(QLabel("Time:"))
        self._time = QTimeEdit()
        self._time.setDisplayFormat("HH:mm")
        self._time.setTime(QTime.currentTime())
        row.addWidget(self._time)
        row.addSpacing(20)
        row.addWidget(QLabel("Repeat:"))
        self._mode = QComboBox()
        self._mode.addItems(["once", "daily", "weekdays", "weekly"])
        row.addWidget(self._mode)
        lay.addLayout(row)
        btns = QHBoxLayout(); btns.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btns.addWidget(cancel)
        ok = QPushButton("Save"); ok.setStyleSheet("QPushButton{background:#00e87a;color:#080b12;border:none;border-radius:6px;padding:5px 14px;font-weight:700;} QPushButton:hover{background:#00ff88;}")
        ok.clicked.connect(self._ok); btns.addWidget(ok)
        lay.addLayout(btns)
        self._label.setFocus()

    def _ok(self):
        if self._label.text().strip(): self.accept()

    def get_reminder(self) -> dict:
        return {
            "label":     self._label.text().strip(),
            "time":      self._time.time().toString("HH:mm"),
            "mode":      self._mode.currentText(),
            "enabled":   True,
            "date":      date.today().isoformat(),
            "lastFired": "",
        }


def check_and_fire(data: dict, app_win):
    now     = datetime.now()
    today   = now.strftime("%Y-%m-%d")
    now_hm  = now.strftime("%H:%M")
    weekday = now.strftime("%A")[:2].upper()

    for r in data.get("reminders", []):
        if not r.get("enabled", True): continue

        # Check snooze
        snoozed_until = r.get("snoozedUntil", "")
        if snoozed_until:
            continue   # Snooze timer handles re-fire

        if r.get("time", "") != now_hm: continue

        last = r.get("lastFired", "")
        mode = r.get("mode", "once")

        fire = False
        if   mode == "once"     and last != today:                                           fire = True
        elif mode == "daily"    and last != today:                                           fire = True
        elif mode == "weekdays" and weekday in ("MO","TU","WE","TH","FR") and last != today: fire = True
        elif mode == "weekly"   and last < today:                                            fire = True

        if fire:
            r["lastFired"] = today
            D.save(data)
            accent  = getattr(app_win, "_palette", {}).get("accent", "#00e87a")
            overlay = AlarmOverlay(r["label"], accent)
            panel = getattr(app_win, "_panels", {}).get("reminders")
            if panel and hasattr(panel, "_handle_snooze"):
                overlay.snoozed.connect(
                    lambda m, lbl=r["label"]: panel._handle_snooze(lbl, m))
                overlay.dismissed.connect(
                    lambda ov=overlay: panel._on_dismissed(ov)
                    if hasattr(panel, "_on_dismissed") else None)
            # Keep alive
            if not hasattr(app_win, "_alarm_overlays"): app_win._alarm_overlays = []
            app_win._alarm_overlays.append(overlay)
            overlay.show()
            overlay.raise_()
            overlay.activateWindow()
