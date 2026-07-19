"""
update_dialog.py — the animated 'update available' popup + progress UI.

States:
  available   → shows "New version available" with an animated download glyph
                and Update / Later buttons.
  downloading → animated progress bar (with a shimmer sweep) + live % and MB.
  ready       → brief "Restarting…" state, then triggers the helper + quit.
  failed      → error line with a Retry / Close.

Styling follows CCP's aurora/glass language and the theme accent.
"""
import math

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QRectF
)
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QBrush, QPen, QPainterPath

MONO = "'JetBrains Mono','Cascadia Code','Consolas',monospace"


class AnimatedProgressBar(QWidget):
    """A rounded progress bar with a gradient fill and a moving shimmer sweep."""
    def __init__(self, accent="#00e87a", parent=None):
        super().__init__(parent)
        self.setFixedHeight(10)
        self._accent = accent
        self._frac = 0.0
        self._target = 0.0
        self._shimmer = 0.0
        self._indeterminate = False
        self._t = QTimer(self)
        self._t.setInterval(16)   # ~60fps
        self._t.timeout.connect(self._tick)
        self._t.start()

    def set_accent(self, a):
        self._accent = a
        self.update()

    def set_fraction(self, f):
        self._indeterminate = False
        self._target = max(0.0, min(1.0, f))

    def set_indeterminate(self, on=True):
        self._indeterminate = on

    def _tick(self):
        # ease current fraction toward target for smooth motion
        self._frac += (self._target - self._frac) * 0.18
        self._shimmer = (self._shimmer + 0.018) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        # track
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 20))
        p.drawRoundedRect(QRectF(0, 0, w, h), r, r)

        accent = QColor(self._accent)
        if self._indeterminate:
            # a gliding pill sweeping left→right
            seg = w * 0.3
            x = (self._shimmer * (w + seg)) - seg
            grad = QLinearGradient(x, 0, x + seg, 0)
            c0 = QColor(accent); c0.setAlpha(0)
            grad.setColorAt(0, c0)
            grad.setColorAt(0.5, accent)
            grad.setColorAt(1, c0)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(max(0, x), 0, min(seg, w), h), r, r)
            return

        fw = w * self._frac
        if fw > 1:
            grad = QLinearGradient(0, 0, fw, 0)
            c2 = QColor(accent); c2.setAlpha(200)
            grad.setColorAt(0, c2)
            grad.setColorAt(1, accent)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(0, 0, fw, h), r, r)

            # shimmer sweep over the filled portion
            sx = self._shimmer * fw
            seg = max(20, fw * 0.25)
            sg = QLinearGradient(sx - seg, 0, sx + seg, 0)
            cc = QColor(255, 255, 255, 90)
            c0 = QColor(255, 255, 255, 0)
            sg.setColorAt(0, c0); sg.setColorAt(0.5, cc); sg.setColorAt(1, c0)
            path = QPainterPath()
            path.addRoundedRect(QRectF(0, 0, fw, h), r, r)
            p.setClipPath(path)
            p.setBrush(QBrush(sg))
            p.drawRect(QRectF(sx - seg, 0, seg * 2, h))


class _PulseGlyph(QWidget):
    """A download arrow that gently pulses / bobs while idle."""
    def __init__(self, accent="#00e87a", parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 46)
        self._accent = accent
        self._t = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_accent(self, a):
        self._accent = a; self.update()

    def _tick(self):
        self._t += 0.05
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        accent = QColor(self._accent)

        # pulsing halo
        pulse = (math.sin(self._t) + 1) / 2   # 0..1
        halo = QColor(accent); halo.setAlpha(int(30 + 40 * pulse))
        rad = 16 + 5 * pulse
        p.setPen(Qt.PenStyle.NoPen); p.setBrush(halo)
        p.drawEllipse(QRectF(cx - rad, cy - rad, rad * 2, rad * 2))

        # arrow bobs down slightly
        bob = math.sin(self._t * 1.2) * 1.5
        p.setPen(QPen(accent, 2.4, cap=Qt.PenCapStyle.RoundCap,
                      join=Qt.PenJoinStyle.RoundJoin))
        p.drawLine(int(cx), int(cy - 8 + bob), int(cx), int(cy + 6 + bob))
        p.drawLine(int(cx - 6), int(cy + bob), int(cx), int(cy + 6 + bob))
        p.drawLine(int(cx + 6), int(cy + bob), int(cx), int(cy + 6 + bob))
        # base line
        p.drawLine(int(cx - 7), int(cy + 11 + bob), int(cx + 7), int(cy + 11 + bob))


class UpdateDialog(QWidget):
    def __init__(self, main_window, accent="#00e87a"):
        super().__init__(main_window)
        self._mw = main_window
        self._accent = accent
        self._url = ""
        self._size = 0
        self._when = ""
        self._digest = ""
        self._downloader = None
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.hide()
        self._build()

    def set_accent(self, a):
        self._accent = a
        for wdg in (getattr(self, "_glyph", None), getattr(self, "_bar", None)):
            if wdg: wdg.set_accent(a)

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch()
        row = QHBoxLayout(); row.addStretch()

        self._card = QWidget()
        self._card.setObjectName("UpdateCard")
        self._card.setFixedWidth(400)
        self._card.setStyleSheet(
            "#UpdateCard{background:#0d1520;border:1px solid #24374f;"
            "border-top:1px solid rgba(255,255,255,0.12);border-radius:16px;}")
        sh = QGraphicsDropShadowEffect(self)
        sh.setBlurRadius(40); sh.setColor(QColor(0, 0, 0, 180)); sh.setOffset(0, 12)
        self._card.setGraphicsEffect(sh)

        cl = QVBoxLayout(self._card)
        cl.setContentsMargins(26, 22, 26, 22)
        cl.setSpacing(12)

        top = QHBoxLayout(); top.setSpacing(14)
        self._glyph = _PulseGlyph(self._accent)
        top.addWidget(self._glyph)
        tcol = QVBoxLayout(); tcol.setSpacing(2)
        self._title = QLabel("Update available")
        self._title.setStyleSheet(
            "background:transparent;color:#e8eef5;font-size:15px;"
            "font-weight:800;border:none;")
        tcol.addWidget(self._title)
        self._sub = QLabel("A newer build of Command Centre Pro is ready.")
        self._sub.setWordWrap(True)
        self._sub.setStyleSheet(
            "background:transparent;color:#9fb0c4;font-size:11px;border:none;")
        tcol.addWidget(self._sub)
        top.addLayout(tcol, 1)
        cl.addLayout(top)

        # progress area (hidden until downloading)
        self._bar = AnimatedProgressBar(self._accent)
        self._bar.hide()
        cl.addWidget(self._bar)
        self._pct = QLabel("")
        self._pct.setStyleSheet(
            f"background:transparent;color:#6b83a0;font-size:10px;"
            f"border:none;font-family:{MONO};")
        self._pct.hide()
        cl.addWidget(self._pct)

        # buttons
        btns = QHBoxLayout(); btns.setSpacing(8)
        btns.addStretch()
        self._later = QPushButton("Later")
        self._later.setCursor(Qt.CursorShape.PointingHandCursor)
        self._later.setFixedHeight(32)
        self._later.setStyleSheet(
            "QPushButton{background:transparent;color:#9fb0c4;border:1px solid #24374f;"
            "border-radius:8px;padding:0 16px;font-size:12px;font-weight:600;}"
            "QPushButton:hover{background:rgba(255,255,255,0.05);color:#d4dfe9;}")
        self._later.clicked.connect(self.hide_dialog)
        btns.addWidget(self._later)

        self._update = QPushButton("Update now")
        self._update.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update.setFixedHeight = self._update.setFixedHeight  # noop guard
        self._update.setFixedHeight(32)
        self._update.setStyleSheet(
            f"QPushButton{{background:{self._accent};color:#060a10;border:none;"
            f"border-radius:8px;padding:0 18px;font-size:12px;font-weight:800;}}"
            f"QPushButton:hover{{background:{self._accent};}}")
        self._update.clicked.connect(self._start_download)
        btns.addWidget(self._update)
        self._btns = btns
        cl.addLayout(btns)

        row.addWidget(self._card)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(3, 6, 12, 170))

    # ── public API ──
    def offer(self, url, tag, size, digest=""):
        self._url, self._when, self._size, self._digest = url, tag, size, digest
        mb = size / (1024 * 1024) if size else 0
        ver = tag.lstrip("vV") if tag else ""
        self._title.setText(f"Update available" + (f"  ·  v{ver}" if ver else ""))
        self._sub.setText(
            f"A newer build is ready ({mb:.1f} MB). Update now and Command "
            f"Centre Pro will restart itself.")
        self._bar.hide(); self._pct.hide()
        self._update.setEnabled(True)
        self._later.show(); self._update.show()
        self._show()

    def _show(self):
        if self._mw:
            self.setGeometry(self._mw.rect())
        self.show(); self.raise_()
        self.setWindowOpacity(0.0)
        self._a = QPropertyAnimation(self, b"windowOpacity", self)
        self._a.setDuration(180); self._a.setStartValue(0.0); self._a.setEndValue(1.0)
        self._a.setEasingCurve(QEasingCurve.Type.OutCubic); self._a.start()
        # card slide-up
        self._card.move(self._card.x(), self._card.y() + 20)
        self._sa = QPropertyAnimation(self._card, b"pos", self)
        self._sa.setDuration(240)
        self._sa.setStartValue(QPoint(self._card.x(), self._card.y()))
        self._sa.setEndValue(QPoint(self._card.x(), self._card.y() - 20))
        self._sa.setEasingCurve(QEasingCurve.Type.OutBack); self._sa.start()

    def hide_dialog(self):
        self._a = QPropertyAnimation(self, b"windowOpacity", self)
        self._a.setDuration(140); self._a.setStartValue(self.windowOpacity())
        self._a.setEndValue(0.0); self._a.finished.connect(self.hide); self._a.start()

    def _start_download(self):
        from src.updater import UpdateDownloader
        self._title.setText("Downloading update…")
        self._sub.setText("Fetching the latest build. This won't touch your data.")
        self._later.hide(); self._update.hide()
        self._bar.show(); self._pct.show()
        self._bar.set_indeterminate(True)
        self._pct.setText("starting…")

        self._downloader = UpdateDownloader(self._url, self._size, self._when, self._digest)
        self._downloader.progress.connect(self._on_progress)
        self._downloader.finished_ok.connect(self._on_done)
        self._downloader.failed.connect(self._on_failed)
        self._downloader.start()

    def _on_progress(self, done, total):
        if total > 0:
            self._bar.set_fraction(done / total)
            mb_d = done / (1024 * 1024); mb_t = total / (1024 * 1024)
            self._pct.setText(f"{int(100*done/total)}%   ·   {mb_d:.1f} / {mb_t:.1f} MB")
        else:
            self._bar.set_indeterminate(True)
            self._pct.setText(f"{done/(1024*1024):.1f} MB")

    def _on_done(self, temp_path):
        from src.updater import apply_update_and_relaunch
        self._bar.set_fraction(1.0)
        self._title.setText("Restarting…")
        self._sub.setText("Update downloaded. Command Centre Pro will now restart.")
        self._pct.setText("100%   ·   applying")
        # brief beat so the 100% + message registers, then swap + quit
        QTimer.singleShot(900, lambda: self._finalize(temp_path))

    def _finalize(self, temp_path):
        from src.updater import apply_update_and_relaunch
        ok = apply_update_and_relaunch(temp_path)
        if ok:
            from PyQt6.QtWidgets import QApplication
            QApplication.quit()
        else:
            self._on_failed("Could not launch the update helper.")

    def _on_failed(self, msg):
        self._bar.hide(); self._pct.hide()
        self._title.setText("Update failed")
        self._sub.setText(f"{msg}\nYour current version is unchanged.")
        self._later.setText("Close"); self._later.show()
        self._update.setText("Retry"); self._update.show()
        self._update.setEnabled(True)
