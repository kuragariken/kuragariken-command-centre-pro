"""
panels/analytics.py — Raycast-Wrapped inspired analytics dashboard.
Bento grid of stat cards: large numbers, subtle sparklines,
gradient backgrounds, animated counters. Dark premium aesthetic.
"""
import math
from datetime import datetime, date, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore  import Qt, QTimer, QRectF, QPointF, pyqtProperty, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui   import (QPainter, QColor, QLinearGradient, QRadialGradient,
                            QBrush, QPen, QPainterPath, QFont, QFontMetrics)
from src import data as D
from src.widgets.command_dna import CommandDNA

FONT      = "'Segoe UI Variable Text','Segoe UI Variable','Inter','Segoe UI',sans-serif"
MONO      = "'JetBrains Mono','Cascadia Code','Consolas',monospace"


# ── Animated counter label ────────────────────────────────────────
class CountLabel(QLabel):
    def __init__(self, target: int = 0, color: str = "#ffffff", size: int = 32, parent=None):
        super().__init__("0", parent)
        self._target  = target
        self._current = 0.0
        self._color   = color
        f = QFont("Inter", size, QFont.Weight.ExtraBold)
        self.setFont(f)
        self.setStyleSheet(f"background:transparent;color:{color};border:none;")
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

    def animate_to(self, target: int):
        self._target  = target
        self._current = 0.0
        t = QTimer(self)
        t.timeout.connect(self._tick)
        t.start(16)
        self._timer = t

    def _tick(self):
        diff = self._target - self._current
        if abs(diff) < 0.5:
            self._current = self._target
            self.setText(str(int(self._target)))
            self._timer.stop()
            return
        self._current += diff * 0.12
        self.setText(str(int(self._current)))


# ── Sparkline widget ──────────────────────────────────────────────
class Sparkline(QWidget):
    def __init__(self, values: list, color: str = "#00e87a", parent=None):
        super().__init__(parent)
        self._values = values or [0]
        self._color  = color
        self.setFixedHeight(40)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setStyleSheet("background:transparent;")

    def set_values(self, values: list, color: str = ""):
        self._values = values or [0]
        if color: self._color = color
        self.update()

    def paintEvent(self, event):
        if not self._values: return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        mn, mx = min(self._values), max(self._values)
        rng = mx - mn or 1
        n   = len(self._values)
        pts = []
        for i, v in enumerate(self._values):
            x = i / (n-1) * w if n > 1 else w/2
            y = h - (v - mn) / rng * (h - 6) - 3
            pts.append(QPointF(x, y))

        # Gradient fill under line
        path = QPainterPath()
        path.moveTo(pts[0].x(), h)
        for pt in pts: path.lineTo(pt)
        path.lineTo(pts[-1].x(), h)
        path.closeSubpath()
        grad = QLinearGradient(0, 0, 0, h)
        c1 = QColor(self._color); c1.setAlpha(60)
        c2 = QColor(self._color); c2.setAlpha(0)
        grad.setColorAt(0, c1); grad.setColorAt(1, c2)
        p.fillPath(path, QBrush(grad))

        # Line
        lp = QPainterPath()
        lp.moveTo(pts[0])
        for pt in pts[1:]: lp.lineTo(pt)
        lc = QColor(self._color); lc.setAlpha(200)
        p.setPen(QPen(lc, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(lp)

        # End dot
        if pts:
            dc = QColor(self._color)
            p.setBrush(QBrush(dc)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QRectF(pts[-1].x()-3, pts[-1].y()-3, 6, 6))


# ── Stat card ─────────────────────────────────────────────────────
class StatCard(QWidget):
    def __init__(self, title: str, value: int, subtitle: str = "",
                 accent: str = "#00e87a", bg: str = "#0d1520",
                 sparkline_data: list = None, wide: bool = False,
                 parent=None):
        super().__init__(parent)
        self._accent = accent
        self._bg     = bg
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(100)
        if wide:
            self.setMinimumWidth(200)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 12)
        lay.setSpacing(2)

        # Title
        t = QLabel(title)
        t.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);"
            f"font-size:10px;font-weight:600;letter-spacing:0.5px;border:none;"
            f"font-family:{FONT};")
        lay.addWidget(t)

        # Big number
        self._count = CountLabel(value, "#ffffff", 28)
        lay.addWidget(self._count)

        # Subtitle
        if subtitle:
            s = QLabel(subtitle)
            s.setStyleSheet(
                f"background:transparent;color:rgba(255,255,255,0.35);"
                f"font-size:9px;font-weight:500;border:none;font-family:{FONT};")
            lay.addWidget(s)

        lay.addStretch()

        # Sparkline
        if sparkline_data:
            self._spark = Sparkline(sparkline_data, accent)
            lay.addWidget(self._spark)
        else:
            self._spark = None

        # Schedule count-up
        QTimer.singleShot(200, lambda: self._count.animate_to(value))

    def update_accent(self, accent: str):
        self._accent = accent
        if self._spark:
            self._spark.set_values(self._spark._values, accent)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, w, h), 14, 14)

        # Dark glass bg
        grad = QLinearGradient(0, 0, w, h)
        c1 = QColor(self._bg)
        c2 = QColor(self._bg)
        c2.setRed(min(255, c2.red()+6))
        c2.setBlue(min(255, c2.blue()+10))
        grad.setColorAt(0, c1); grad.setColorAt(1, c2)
        p.fillPath(path, QBrush(grad))

        # Accent top border
        ac = QColor(self._accent); ac.setAlpha(180)
        p.setPen(QPen(ac, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        top = QPainterPath()
        top.moveTo(14, 0); top.lineTo(w-14, 0)
        p.drawPath(top)

        # Subtle inner highlight top
        hi = QColor(255, 255, 255, 12)
        p.setPen(QPen(hi, 1))
        inner = QPainterPath()
        inner.addRoundedRect(QRectF(0.5, 0.5, w-1, h-1), 14, 14)
        p.drawPath(inner)

        # Accent corner glow
        rg = QRadialGradient(QPointF(0, 0), w * 0.7)
        cg = QColor(self._accent); cg.setAlpha(18)
        rg.setColorAt(0, cg); rg.setColorAt(1, QColor(0,0,0,0))
        p.fillPath(path, QBrush(rg))


# ── Main panel ────────────────────────────────────────────────────
class AnalyticsPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app      = app
        self._palette = {}
        self._cards   = []
        self.setStyleSheet("background:transparent;")

    def refresh(self):
        # Clear
        for c in self._cards:
            c.setParent(None)
        self._cards.clear()

        old_lay = self.layout()
        if old_lay:
            QWidget().setLayout(old_lay)

        stats  = self.app.data.get("session_stats", {})
        cmds   = self.app.data.get("commands", {})
        p      = self._palette
        accent = p.get("accent", "#00e87a")
        blue   = p.get("blue",   "#38bdf8")
        amber  = p.get("amber",  "#fbbf24")
        red    = p.get("red",    "#f87171")
        purple = p.get("purple", "#a78bfa")
        green  = p.get("green",  "#00e87a")
        bg     = p.get("card",   "#0d1520")

        copies_today = stats.get("copies_today",  0)
        copies_total = stats.get("copies_total",  0)
        pomo_done    = stats.get("pomo_sessions", 0)
        total_cats   = len(self.app.data.get("categories", []))
        total_cmds   = sum(len(v) for v in cmds.values())

        # Daily history sparkline (last 7 days)
        today    = date.today()
        history  = stats.get("daily_history", {})
        daily_7  = [history.get((today - timedelta(days=6-i)).strftime("%Y-%m-%d"), 0) for i in range(7)]

        # Hourly heatmap (today)
        hourly   = stats.get("hourly_today", {})
        hourly_24 = [hourly.get(f"{h:02d}", 0) for h in range(24)]

        # Top commands
        top_cmds = sorted(stats.get("top_commands", {}).items(), key=lambda x: -x[1])[:3]
        top_cat  = sorted(stats.get("category_counts", {}).items(), key=lambda x: -x[1])

        # ── Build bento grid ──────────────────────────────────────
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{width:3px;background:transparent;}"
            "QScrollBar::handle:vertical{background:#1a2840;border-radius:2px;}")

        container = QWidget(); container.setStyleSheet("background:transparent;")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)

        def card(title, value, subtitle="", color=accent, sparks=None, wide=False):
            c = StatCard(title, value, subtitle, color, bg, sparks, wide)
            self._cards.append(c)
            return c

        # Row 0 — headline stats
        grid.addWidget(card("Copies Today",   copies_today, "commands copied", accent, daily_7), 0, 0)
        grid.addWidget(card("Total Copies",   copies_total, "all time",        blue), 0, 1)
        grid.addWidget(card("Pomodoro Sessions", pomo_done, "focus sessions",  amber), 0, 2)
        grid.addWidget(card("Categories",     total_cats,   "active",          purple), 0, 3)

        # Row 1 — commands + activity
        grid.addWidget(card("Commands",       total_cmds,   "in library",      green, hourly_24), 1, 0)

        # Most active hour
        peak_h   = max(hourly.items(), key=lambda x: x[1], default=("--", 0))
        peak_val = int(peak_h[0]) if peak_h[0] != "--" else 0
        peak_label = f"{peak_val:02d}:00" if peak_h[0] != "--" else "--:--"
        peak_card = QWidget(); peak_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        peak_card.setMinimumHeight(100)
        pl = QVBoxLayout(peak_card); pl.setContentsMargins(16,14,16,12); pl.setSpacing(2)
        lbl = QLabel("Most Active Hour"); lbl.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);font-size:10px;"
            f"font-weight:600;letter-spacing:0.5px;border:none;font-family:{FONT};")
        pl.addWidget(lbl)
        big = QLabel(peak_label); big.setStyleSheet(
            f"background:transparent;color:#ffffff;font-size:28px;"
            f"font-weight:800;border:none;font-family:{MONO};")
        pl.addWidget(big)
        pl.addWidget(Sparkline(hourly_24, accent))
        grid.addWidget(peak_card, 1, 1)

        # Top commands card
        top_card = QWidget(); top_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        top_card.setMinimumHeight(100)
        tl = QVBoxLayout(top_card); tl.setContentsMargins(16,14,16,12); tl.setSpacing(6)
        lbl2 = QLabel("Top Commands"); lbl2.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);font-size:10px;"
            f"font-weight:600;letter-spacing:0.5px;border:none;font-family:{FONT};")
        tl.addWidget(lbl2)
        if top_cmds:
            for cmd_label, cnt in top_cmds:
                row_w = QWidget(); row_w.setStyleSheet("background:transparent;")
                rl = QHBoxLayout(row_w); rl.setContentsMargins(0,0,0,0); rl.setSpacing(8)
                nl = QLabel(cmd_label[:22]); nl.setStyleSheet(
                    f"background:transparent;color:#e2e8f0;font-size:10px;border:none;font-family:{FONT};")
                rl.addWidget(nl, 1)
                cl = QLabel(str(cnt)); cl.setStyleSheet(
                    f"background:rgba(255,255,255,0.08);color:{accent};"
                    f"font-size:9px;font-weight:700;border-radius:8px;"
                    f"padding:1px 7px;border:none;font-family:{MONO};")
                cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                rl.addWidget(cl)
                tl.addWidget(row_w)
        else:
            tl.addWidget(QLabel("No copies yet"))
        tl.addStretch()
        grid.addWidget(top_card, 1, 2, 1, 2)

        # Row 2 — category breakdown
        if top_cat:
            cat_card = QWidget(); cat_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            cat_card.setMinimumHeight(90)
            cl2 = QVBoxLayout(cat_card); cl2.setContentsMargins(16,14,16,12); cl2.setSpacing(6)
            lbl3 = QLabel("By Category"); lbl3.setStyleSheet(
                f"background:transparent;color:rgba(255,255,255,0.45);font-size:10px;"
                f"font-weight:600;letter-spacing:0.5px;border:none;font-family:{FONT};")
            cl2.addWidget(lbl3)
            colors = [accent, blue, amber, purple, red]
            for i, (cat, cnt) in enumerate(top_cat[:4]):
                rw = QWidget(); rw.setStyleSheet("background:transparent;")
                rl3 = QHBoxLayout(rw); rl3.setContentsMargins(0,0,0,0); rl3.setSpacing(8)
                dot = QLabel("●"); c = colors[i % len(colors)]
                dot.setStyleSheet(f"background:transparent;color:{c};font-size:8px;border:none;")
                rl3.addWidget(dot)
                nl2 = QLabel(cat[:20]); nl2.setStyleSheet(
                    f"background:transparent;color:#e2e8f0;font-size:10px;border:none;font-family:{FONT};")
                rl3.addWidget(nl2, 1)
                cl3 = QLabel(str(cnt)); cl3.setStyleSheet(
                    f"background:transparent;color:rgba(255,255,255,0.45);"
                    f"font-size:9px;font-weight:700;border:none;font-family:{MONO};")
                rl3.addWidget(cl3)
                cl2.addWidget(rw)
            cl2.addStretch()
            grid.addWidget(cat_card, 2, 0, 1, 2)

        # Today's date card
        date_card = QWidget(); date_card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        date_card.setMinimumHeight(90)
        dl = QVBoxLayout(date_card); dl.setContentsMargins(16,14,16,12); dl.setSpacing(2)
        QLabel("Today").setParent(None)
        lbl4 = QLabel("Today"); lbl4.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);font-size:10px;"
            f"font-weight:600;letter-spacing:0.5px;border:none;font-family:{FONT};")
        dl.addWidget(lbl4)
        day_lbl = QLabel(datetime.now().strftime("%A")); day_lbl.setStyleSheet(
            f"background:transparent;color:#ffffff;font-size:20px;"
            f"font-weight:800;border:none;font-family:{FONT};")
        dl.addWidget(day_lbl)
        date_lbl = QLabel(datetime.now().strftime("%d %B %Y")); date_lbl.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);font-size:10px;"
            f"border:none;font-family:{FONT};")
        dl.addWidget(date_lbl)
        dl.addStretch()
        grid.addWidget(date_card, 2, 2, 1, 2)

        # Apply paint to all WA_StyledBackground cards
        for c in [peak_card, top_card, cat_card if top_cat else QWidget(), date_card]:
            try:
                c.setStyleSheet(
                    f"QWidget{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
                    f"stop:0 {bg},stop:1 rgba(8,14,22,0.9));"
                    f"border:1px solid rgba(255,255,255,0.07);"
                    f"border-top:2px solid {accent};"
                    f"border-radius:14px;}}")
            except Exception:
                pass

        # ── Command DNA tree — full-width organic visualisation ──
        dna_card = QWidget()
        dna_card.setMinimumHeight(260)
        dna_lay = QVBoxLayout(dna_card)
        dna_lay.setContentsMargins(16, 12, 16, 12)
        dna_lay.setSpacing(6)

        dna_title = QLabel("COMMAND DNA")
        dna_title.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.45);"
            f"font-size:10px;font-weight:600;letter-spacing:1.5px;"
            f"border:none;font-family:{FONT};")
        dna_lay.addWidget(dna_title)

        dna_sub = QLabel("Your command usage as a living organism")
        dna_sub.setStyleSheet(
            f"background:transparent;color:rgba(255,255,255,0.3);"
            f"font-size:9px;border:none;font-family:{FONT};")
        dna_lay.addWidget(dna_sub)

        self._dna_tree = CommandDNA()
        dna_lay.addWidget(self._dna_tree, 1)

        dna_card.setStyleSheet(
            f"QWidget{{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {bg},stop:1 rgba(8,14,22,0.9));"
            f"border:1px solid rgba(255,255,255,0.07);"
            f"border-top:2px solid {accent};"
            f"border-radius:14px;}}")

        grid.addWidget(dna_card, 3, 0, 1, 4)

        # Feed real usage data to the DNA tree
        dna_data = {}
        for cat in self.app.data.get("categories", []):
            cmd_counts = []
            for cmd in self.app.data.get("commands", {}).get(cat, []):
                lbl = cmd.get("label", "")
                cnt = stats.get("top_commands", {}).get(lbl, 0)
                if cnt > 0:
                    cmd_counts.append((lbl, cnt))
            if cmd_counts:
                cmd_counts.sort(key=lambda x: -x[1])
                dna_data[cat] = cmd_counts
        accent2 = p.get("accent2", blue)
        self._dna_tree.set_data(dna_data, accent, accent2)

        scroll.setWidget(container)
        root.addWidget(scroll, 1)

    def set_palette(self, p: dict):
        self._palette = p
        accent = p.get("accent","#00e87a")
        for c in self._cards:
            c.update_accent(accent)
        self.refresh()
