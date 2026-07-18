"""
panels/ticket_log.py — Quick Ticket Logger + Session Timer / Shift Tracker.
One panel, two modes. Logs tickets with timestamp, tracks shift duration,
generates handover report. Saves to JSON.
"""
import os
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTextEdit,
    QFrame, QComboBox, QApplication, QDialog, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from src import data as D
from src.widgets.empty_state import show_empty_state
from src.widgets.theming import themed, apply_theme


STATUS_COLORS = {
    "OPEN":       "#fbbf24",
    "IN PROGRESS":"38bdf8",
    "RESOLVED":   "#00e87a",
    "ESCALATED":  "#f87171",
    "PENDING":    "#a78bfa",
}


class ShiftTimer(QWidget):
    """Live shift clock — shows elapsed time since shift start."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._start     = None
        self._running   = False
        self.setStyleSheet("background:transparent;")

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self._lbl = QLabel("SHIFT  00:00:00")
        self._lbl.setStyleSheet(
            "background:transparent; color:#6e7d90; border:none;"
            "font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace; font-size:11px; font-weight:700;"
            "letter-spacing:1px;")
        lay.addWidget(self._lbl)

        self._start_btn = QPushButton("Start Shift")
        self._start_btn.setFixedHeight(22)
        self._start_btn.setStyleSheet(
            "QPushButton{background:#141d2b;color:#00e87a;border:1px solid #1f2d3d;"
            "border-radius:4px;padding:0 8px;font-size:10px;font-weight:700;}"
            "QPushButton:hover{background:#182030;border-color:#00e87a;}")
        self._start_btn.clicked.connect(self.toggle)
        lay.addWidget(self._start_btn)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)

    def toggle(self):
        if self._running:
            self._running = False
            self._timer.stop()
            self._start_btn.setText("Start Shift")
            self._start_btn.setStyleSheet(
                "QPushButton{background:#141d2b;color:#00e87a;border:1px solid #1f2d3d;"
                "border-radius:4px;padding:0 8px;font-size:10px;font-weight:700;}"
                "QPushButton:hover{background:#182030;border-color:#00e87a;}")
        else:
            self._start = self._start or datetime.now()
            self._running = True
            self._timer.start(1000)
            self._start_btn.setText("End Shift")
            self._start_btn.setStyleSheet(
                "QPushButton{background:#f87171;color:#080b12;border:none;"
                "border-radius:4px;padding:0 8px;font-size:10px;font-weight:700;}"
                "QPushButton:hover{background:#ef4444;}")

    def _tick(self):
        if self._start:
            elapsed = datetime.now() - self._start
            total   = int(elapsed.total_seconds())
            h, rem  = divmod(total, 3600)
            m, s    = divmod(rem, 60)
            self._lbl.setText(f"SHIFT  {h:02d}:{m:02d}:{s:02d}")

    def get_duration(self) -> str:
        if not self._start:
            return "Not started"
        elapsed = datetime.now() - self._start
        total   = int(elapsed.total_seconds())
        h, rem  = divmod(total, 3600)
        m, _    = divmod(rem, 60)
        return f"{h}h {m}m"

    def get_start_time(self) -> str:
        return self._start.strftime("%H:%M:%S") if self._start else "—"

    def update_style(self, accent: str, dim: str):
        self._lbl.setStyleSheet(
            f"background:transparent; color:{dim}; border:none;"
            f"font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace; font-size:11px; font-weight:700;"
            f"letter-spacing:1px;")


class TicketLogPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app          = app
        self.shift_timer  = ShiftTimer(self)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setFixedHeight(46)
        hdr.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(14,20,30,0.92),stop:1 rgba(6,10,18,0.85)); border-top:1px solid rgba(255,255,255,0.06); border-bottom:1px solid rgba(255,255,255,0.07);")
        hl  = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 12, 0)

        title = QLabel("TICKETS  &  SHIFT")
        themed(self, title,
               "background:transparent;color:{accent};font-size:11px;"
               "font-weight:700;letter-spacing:2px;border:none;")
        hl.addWidget(title)
        hl.addSpacing(16)
        hl.addWidget(self.shift_timer)
        hl.addStretch()

        report_btn = QPushButton("Handover Report")
        report_btn.setStyleSheet(
            "QPushButton{background:#141d2b;color:#9ca3af;border:1px solid #1f2d3d;"
            "border-radius:8px;padding:4px 12px;font-size:10px;font-weight:600;}"
            "QPushButton:hover{background:#182030;color:#e2e8f0;}")
        report_btn.clicked.connect(self._gen_report)
        hl.addWidget(report_btn)
        root.addWidget(hdr)

        # ── Quick entry row ───────────────────────────────────────
        entry = QWidget()
        entry.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(14,20,30,0.92),stop:1 rgba(6,10,18,0.85)); border-top:1px solid rgba(255,255,255,0.06); border-bottom:1px solid rgba(255,255,255,0.07);")
        el = QHBoxLayout(entry)
        el.setContentsMargins(10, 8, 10, 8)
        el.setSpacing(6)
        entry.setFixedHeight(52)

        self._ticket_num = QLineEdit()
        self._ticket_num.setPlaceholderText("Ticket #  e.g. INC0001234")
        self._ticket_num.setFixedWidth(160)
        themed(self, self._ticket_num,
            "QLineEdit{{background:{input};color:{text};border:1px solid {border};"
            "border-radius:8px;padding:5px 10px;font-size:11px;font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace;}}"
            "QLineEdit:focus{{border-color:{accent};}}")
        el.addWidget(self._ticket_num)

        self._ticket_desc = QLineEdit()
        self._ticket_desc.setPlaceholderText("Summary / description…")
        themed(self, self._ticket_desc,
            "QLineEdit{{background:{input};color:{text};border:1px solid {border};"
            "border-radius:8px;padding:5px 10px;font-size:11px;}}"
            "QLineEdit:focus{{border-color:{accent};}}")
        el.addWidget(self._ticket_desc, 1)

        self._ticket_status = QComboBox()
        self._ticket_status.addItems(list(STATUS_COLORS.keys()))
        self._ticket_status.setFixedWidth(120)
        themed(self, self._ticket_status,
            "QComboBox{{background:{input};color:{text};border:1px solid {border};"
            "border-radius:8px;padding:5px 8px;font-size:11px;}}"
            "QComboBox:focus{{border-color:{accent};}}"
            "QComboBox::drop-down{{border:none;width:20px;}}"
            "QComboBox QAbstractItemView{{background:{input};color:{text};"
            "border:1px solid {border};selection-background-color:{hover};}}")
        el.addWidget(self._ticket_status)

        log_btn = QPushButton("+ Log")
        log_btn.setFixedHeight(34)
        log_btn.setFixedWidth(60)
        log_btn.setFont(QFont("Inter", 10, QFont.Weight.Bold))
        themed(self, log_btn,
            "QPushButton{{background:{accent};color:{bg};border:none;"
            "border-radius:8px;font-weight:700;}}"
            "QPushButton:hover{{background:{accent2};}}"
            "QPushButton:pressed{{background:{accent};padding-top:1px;}}")
        log_btn.clicked.connect(self._log_ticket)
        el.addWidget(log_btn)
        self._ticket_num.returnPressed.connect(self._log_ticket)
        self._ticket_desc.returnPressed.connect(self._log_ticket)
        root.addWidget(entry)

        # ── Ticket list ───────────────────────────────────────────
        self._list = QListWidget()
        themed(self, self._list,
            "QListWidget{{background:transparent;border:none;outline:none;}}"
            "QListWidget::item{{background:{card};color:{text};"
            "border:1px solid {border};border-radius:8px;"
            "padding:8px 12px;margin:2px 8px;font-size:11px;"
            "font-family:'JetBrains Mono','Cascadia Code','Fira Code','Consolas',monospace;}}"
            "QListWidget::item:hover{{background:{hover};border-color:{dim};}}"
            "QListWidget::item:selected{{background:{hover};"
            "border:1px solid {accent};border-left:3px solid {accent};}}")
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._ctx)
        root.addWidget(self._list, 1)

        # ── Stats footer ──────────────────────────────────────────
        footer = QWidget()
        footer.setFixedHeight(26)
        footer.setStyleSheet("background:rgba(5,8,16,0.85); border-top:1px solid rgba(255,255,255,0.06);")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(12, 0, 12, 0)
        self._stats_lbl = QLabel("")
        self._stats_lbl.setStyleSheet(
            "background:transparent;color:#6e7d90;font-size:10px;border:none;")
        fl.addWidget(self._stats_lbl)
        fl.addStretch()
        clr = QPushButton("Clear Resolved")
        clr.setStyleSheet(
            "QPushButton{background:transparent;color:#6e7d90;border:1px solid #1f2d3d;"
            "border-radius:4px;padding:1px 8px;font-size:9px;}"
            "QPushButton:hover{color:#e2e8f0;border-color:#6e7d90;}")
        clr.clicked.connect(self._clear_resolved)
        fl.addWidget(clr)
        root.addWidget(footer)

    def refresh(self):
        self._rebuild_list()

    def _log_ticket(self):
        num  = self._ticket_num.text().strip()
        desc = self._ticket_desc.text().strip()
        if not num and not desc:
            return

        ticket = {
            "num":    num or "—",
            "desc":   desc or "No description",
            "status": self._ticket_status.currentText(),
            "time":   datetime.now().isoformat(),
            "notes":  "",
        }
        self.app.data.setdefault("tickets", []).insert(0, ticket)
        D.save(self.app.data)

        self._ticket_num.clear()
        self._ticket_desc.clear()
        self._ticket_num.setFocus()
        self._rebuild_list()
        self.app.toast.show_toast(f"Ticket logged: {ticket['num']}")

    def _rebuild_list(self):
        self._list.clear()
        tickets  = self.app.data.get("tickets", [])
        open_cnt = resolved_cnt = 0

        for t in tickets:
            status = t.get("status", "OPEN")
            ts     = t.get("time", "")[:16].replace("T", " ")
            color  = STATUS_COLORS.get(status, "#6e7d90")
            text   = f"[{status}]  {t['num']}  ·  {t['desc']}  ·  {ts}"

            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, t)
            item.setForeground(QColor(color))
            self._list.addItem(item)

            if status == "RESOLVED": resolved_cnt += 1
            else: open_cnt += 1

        show_empty_state(self._list,
            "No tickets logged yet — add one above to start tracking.")

        total = len(tickets)
        self._stats_lbl.setText(
            f"{total} tickets  ·  {open_cnt} open  ·  {resolved_cnt} resolved  today")

    def _ctx(self, pos):
        item = self._list.itemAt(pos)
        if not item: return
        t = item.data(Qt.ItemDataRole.UserRole)
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        for status in STATUS_COLORS:
            m.addAction(f"Set: {status}", lambda s=status: self._set_status(t, s))
        m.addSeparator()
        m.addAction("Copy ticket #", lambda: QApplication.clipboard().setText(t["num"]))
        m.addAction("Copy summary",  lambda: QApplication.clipboard().setText(
            f"{t['num']} — {t['desc']}"))
        m.addAction("Delete",        lambda: self._delete(t))
        m.exec(self._list.mapToGlobal(pos))

    def _set_status(self, t: dict, status: str):
        t["status"] = status
        D.save(self.app.data)
        self._rebuild_list()

    def _delete(self, t: dict):
        tickets = self.app.data.get("tickets", [])
        self.app.data["tickets"] = [
            x for x in tickets if x.get("time") != t.get("time")]
        D.save(self.app.data)
        self._rebuild_list()

    def _clear_resolved(self):
        tickets = self.app.data.get("tickets", [])
        self.app.data["tickets"] = [
            t for t in tickets if t.get("status") != "RESOLVED"]
        D.save(self.app.data)
        self._rebuild_list()

    def _gen_report(self):
        tickets = self.app.data.get("tickets", [])
        stats   = self.app.data.get("session_stats", {})
        notes   = self.app.data.get("notes", [])

        note_txt = ""
        if notes:
            note_txt = "\n\nSESSION NOTES:\n" + "\n---\n".join(
                f"[{n.get('title','')}]\n{n.get('content','')[:300]}"
                for n in notes if n.get("content","").strip()
            )

        lines = [
            "=" * 60,
            "  SHIFT HANDOVER REPORT",
            f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"  Shift start: {self.shift_timer.get_start_time()}",
            f"  Duration:    {self.shift_timer.get_duration()}",
            "=" * 60,
            "",
            f"COPIES MADE TODAY:  {stats.get('copies_today', 0)}",
            f"TOTAL TICKETS:      {len(tickets)}",
            "",
            "TICKET LOG:",
            "-" * 50,
        ]
        for t in tickets:
            ts  = t.get("time", "")[:16].replace("T", " ")
            lines.append(
                f"  [{t.get('status','?'):12}]  {t.get('num','—'):14}  "
                f"{ts}  —  {t.get('desc','')}")

        if note_txt:
            lines.append(note_txt)

        lines += ["", "=" * 60,
                  "  END OF REPORT — Hand over to incoming officer",
                  "=" * 60]

        report = "\n".join(lines)

        dlg = ReportDialog(report, self)
        dlg.exec()

    def set_palette(self, p):
        accent = p.get("accent", "#00e87a")
        dim    = p.get("dim",    "#6e7d90")
        self.shift_timer.update_style(accent, dim)
        # Re-colour every accent-aware widget registered via themed()
        apply_theme(self, p)


class ReportDialog(QDialog):
    def __init__(self, text: str, parent):
        super().__init__(parent)
        self.setWindowTitle("Handover Report")
        self.setModal(True)
        self.resize(620, 500)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 14)
        lay.setSpacing(8)

        editor = QTextEdit()
        editor.setPlainText(text)
        editor.setReadOnly(True)
        editor.setFont(QFont("JetBrains Mono", 10))
        editor.setStyleSheet(
            "QTextEdit{background:#080b12;color:#cdd9e5;border:1px solid #1f2d3d;"
            "border-radius:8px;padding:10px;}")
        lay.addWidget(editor, 1)

        row = QHBoxLayout()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setStyleSheet(
            "QPushButton{background:#00e87a;color:#080b12;border:none;"
            "border-radius:8px;padding:6px 16px;font-weight:700;}"
            "QPushButton:hover{background:#00ff88;}")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        row.addWidget(copy_btn)

        save_btn = QPushButton("Save as .txt")
        save_btn.setStyleSheet(
            "QPushButton{background:#141d2b;color:#9ca3af;border:1px solid #1f2d3d;"
            "border-radius:8px;padding:6px 16px;}"
            "QPushButton:hover{background:#182030;color:#e2e8f0;}")
        save_btn.clicked.connect(lambda: self._save(text))
        row.addWidget(save_btn)
        row.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        lay.addLayout(row)

    def _save(self, text: str):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Report",
            f"handover_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
            "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
