"""panels/macros.py — Macros (Command Chains) panel"""
import time
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QLineEdit, QComboBox,
    QSpinBox, QScrollArea, QFrame, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from src import data as D
from src.widgets.empty_state import show_empty_state
from src.widgets.theming import themed, apply_theme


STEP_TYPES = ["copy","run","activate","close","winwait","sendkeys","mouseclick","sleep","ifwin","repeat"]


class MacroRunner(QThread):
    status = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, macro: dict, cmd_data: dict):
        super().__init__()
        self._macro    = macro
        self._cmd_data = cmd_data
        self._running  = True

    def run(self):
        steps = self._macro.get("steps", [])
        i = 0
        repeat_stack = []

        while i < len(steps) and self._running:
            step = steps[i]
            t    = step.get("type", "")
            delay = int(step.get("delay", 0))

            try:
                if t == "copy":
                    lbl = step.get("label", "")
                    txt = self._find_text(lbl)
                    if txt:
                        from PyQt6.QtWidgets import QApplication
                        QApplication.clipboard().setText(txt)
                        self.status.emit(f"Copied: {lbl}")

                elif t == "run":
                    import subprocess
                    subprocess.Popen(step.get("target", ""), shell=True)

                elif t == "activate":
                    self._activate_win(step.get("winTitle", ""))

                elif t == "close":
                    self._close_win(step.get("winTitle", ""))

                elif t == "winwait":
                    title   = step.get("winTitle", "")
                    timeout = int(step.get("timeout", 5000))
                    self._wait_win(title, timeout)

                elif t == "sendkeys":
                    try:
                        self._send_keys(step.get("keys", ""))
                    except Exception as e:
                        self.status.emit(f"sendkeys error: {e}")

                elif t == "mouseclick":
                    try:
                        import pyautogui
                        pyautogui.click(int(step.get("x", 0)), int(step.get("y", 0)))
                    except ImportError:
                        self.status.emit("mouseclick: pyautogui not available")

                elif t == "sleep":
                    dur = int(step.get("duration", 500))
                    time.sleep(dur / 1000)

                elif t == "ifwin":
                    title = step.get("winTitle", "")
                    if not self._win_exists(title):
                        skip = int(step.get("skipCount", 1))
                        i += skip

                elif t == "repeat":
                    count     = int(step.get("count", 1))
                    step_cnt  = int(step.get("stepCount", 1))
                    repeat_stack.append({"count": count, "remaining": count - 1,
                                         "start": i + 1, "span": step_cnt})

            except Exception as e:
                self.status.emit(f"Step error: {e}")

            if delay > 0:
                time.sleep(delay / 1000)

            # Handle repeat
            if repeat_stack:
                entry = repeat_stack[-1]
                if i >= entry["start"] + entry["span"] - 1:
                    if entry["remaining"] > 0:
                        entry["remaining"] -= 1
                        i = entry["start"]
                        continue
                    else:
                        repeat_stack.pop()

            i += 1

        self.finished.emit()

    def stop(self):
        self._running = False

    def _find_text(self, label: str) -> str:
        for cmds in self._cmd_data.values():
            for c in cmds:
                if c.get("label") == label:
                    return c.get("text", "")
        return ""

    def _activate_win(self, title: str):
        try:
            import ctypes
            import ctypes.wintypes as wt
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.SetForegroundWindow(hwnd)
        except: pass

    def _close_win(self, title: str):
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwnd = user32.FindWindowW(None, title)
            if hwnd:
                user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        except: pass

    def _wait_win(self, title: str, timeout_ms: int):
        import ctypes
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            hwnd = ctypes.windll.user32.FindWindowW(None, title)
            if hwnd: return
            time.sleep(0.2)

    def _send_keys(self, keys: str):
        try:
            import pyautogui
            # Convert basic AHK-style keys
            keys = keys.replace("^v", "ctrl+v").replace("^c", "ctrl+c")
            keys = keys.replace("{Enter}", "enter").replace("{Tab}", "tab")
            pyautogui.hotkey(*keys.split("+")) if "+" in keys else pyautogui.press(keys)
        except: pass

    def _win_exists(self, title: str) -> bool:
        try:
            import ctypes
            return bool(ctypes.windll.user32.FindWindowW(None, title))
        except:
            return False


class MacrosPanel(QWidget):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._runner = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hdr = QWidget(); hdr.setStyleSheet("background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(14,20,30,0.92),stop:1 rgba(6,10,18,0.85)); border-top:1px solid rgba(255,255,255,0.06); border-bottom:1px solid rgba(255,255,255,0.07);"); hdr.setFixedHeight(44)
        hdr_lay = QHBoxLayout(hdr)
        hdr_lay.setContentsMargins(16, 0, 12, 0)
        hdr_lay.addWidget(self._lbl("MACROS"))
        hdr_lay.addStretch()
        add = QPushButton("＋ Macro")
        themed(self, add,
               "QPushButton{{background:{accent};color:{bg};border:none;"
               "border-radius:8px;padding:5px 14px;font-weight:700;}}"
               "QPushButton:hover{{background:{accent2};}}"
               "QPushButton:pressed{{background:{accent};padding-top:6px;}}")
        add.clicked.connect(self._add)
        hdr_lay.addWidget(add)
        root.addWidget(hdr)

        sep = QFrame(); sep.setStyleSheet("background:#1f2d3d; max-height:1px; min-height:1px;"); root.addWidget(sep)

        self._list = QListWidget()
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.customContextMenuRequested.connect(self._context)
        self._list.itemDoubleClicked.connect(lambda item: self._run(item.data(Qt.ItemDataRole.UserRole)))
        root.addWidget(self._list, 1)

        self._status = QLabel("")
        self._status.setStyleSheet("background:transparent; color:#6e7d90; font-size:11px; border:none;")
        self._status.setContentsMargins(12, 4, 12, 4)
        root.addWidget(self._status)

    def refresh(self):
        self._list.clear()
        for m in self.app.data.get("macros", []):
            steps = len(m.get("steps", []))
            item = QListWidgetItem(f"⚡  {m['name']}  ({steps} steps)")
            item.setData(Qt.ItemDataRole.UserRole, m)
            self._list.addItem(item)
        show_empty_state(self._list,
            "No macros yet — chain commands together with ＋ Macro.", icon="⚡")

    def _add(self):
        dlg = MacroDialog(self, None, self.app.data.get("commands", {}))
        if dlg.exec():
            macro = dlg.get_macro()
            self.app.data.setdefault("macros", []).append(macro)
            D.save(self.app.data)
            self.refresh()

    def _context(self, pos):
        item = self._list.itemAt(pos)
        if not item: return
        m = item.data(Qt.ItemDataRole.UserRole)
        menu = QMenu(self)
        menu.addAction("▶ Run",    lambda: self._run(m))
        menu.addAction("■ Stop",   self._stop)
        menu.addAction("Edit",   lambda: self._edit(m))
        menu.addAction("Delete", lambda: self._delete(m))
        menu.exec(self._list.mapToGlobal(pos))

    def _run(self, macro: dict):
        if self._runner and self._runner.isRunning():
            self._runner.stop()
        self._runner = MacroRunner(macro, self.app.data.get("commands", {}))
        self._runner.status.connect(lambda s: self._status.setText(s))
        self._runner.finished.connect(lambda: self._status.setText("Macro complete"))
        self._runner.start()
        self._status.setText(f"Running: {macro['name']}…")

    def _stop(self):
        if self._runner:
            self._runner.stop()
            self._status.setText("Stopped")

    def _edit(self, macro: dict):
        dlg = MacroDialog(self, macro, self.app.data.get("commands", {}))
        if dlg.exec():
            updated = dlg.get_macro()
            macros = self.app.data.get("macros", [])
            for i, m in enumerate(macros):
                if m.get("name") == macro.get("name"):
                    macros[i] = updated
                    break
            D.save(self.app.data)
            self.refresh()

    def _delete(self, macro: dict):
        self.app.data["macros"] = [m for m in self.app.data.get("macros", [])
                                    if m.get("name") != macro.get("name")]
        D.save(self.app.data)
        self.refresh()

    def _lbl(self, text):
        l = QLabel(text)
        themed(self, l,
               "background:transparent; color:{accent}; font-size:11px; "
               "font-weight:700; letter-spacing:2px; border:none;")
        return l

    def set_palette(self, p):
        apply_theme(self, p)


class MacroDialog(QDialog):
    def __init__(self, parent, macro, cmd_data):
        super().__init__(parent)
        self._macro    = macro or {"name": "", "steps": []}
        self._cmd_data = cmd_data
        self._steps    = list(self._macro.get("steps", []))
        self.setWindowTitle("Edit Macro" if macro else "New Macro")
        self.setModal(True); self.resize(520, 480)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self); lay.setSpacing(8); lay.setContentsMargins(14,14,14,14)

        row = QHBoxLayout()
        row.addWidget(QLabel("Name:"))
        self._name = QLineEdit(self._macro.get("name", ""))
        row.addWidget(self._name, 1)
        lay.addLayout(row)

        lay.addWidget(QLabel("Steps:"))
        self._step_list = QListWidget()
        self._step_list.setFixedHeight(200)
        lay.addWidget(self._step_list)
        self._refresh_steps()

        # Add step row
        add_row = QHBoxLayout()
        self._step_type = QComboBox()
        self._step_type.addItems(STEP_TYPES)
        add_row.addWidget(self._step_type)
        add_btn = QPushButton("＋ Add Step")
        add_btn.clicked.connect(self._add_step)
        add_row.addWidget(add_btn)
        del_btn = QPushButton("🗑 Remove")
        del_btn.clicked.connect(self._del_step)
        add_row.addWidget(del_btn)
        lay.addLayout(add_row)

        btn_row = QHBoxLayout(); btn_row.addStretch()
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        btn_row.addWidget(cancel)
        ok = QPushButton("Save"); ok.setStyleSheet("QPushButton{background:#00e87a;color:#080b12;border:none;border-radius:8px;padding:5px 14px;font-weight:700;} QPushButton:hover{background:#00ff88;}"); ok.clicked.connect(self._save)
        btn_row.addWidget(ok)
        lay.addLayout(btn_row)

    def _refresh_steps(self):
        self._step_list.clear()
        for i, s in enumerate(self._steps):
            t = s.get("type","")
            detail = s.get("label") or s.get("target") or s.get("winTitle") or s.get("keys") or s.get("duration","")
            self._step_list.addItem(f"{i+1}. {t}  {detail or ''}")

    def _add_step(self):
        t = self._step_type.currentText()
        self._steps.append({"type": t, "delay": 200})
        self._refresh_steps()

    def _del_step(self):
        row = self._step_list.currentRow()
        if 0 <= row < len(self._steps):
            self._steps.pop(row)
            self._refresh_steps()

    def _save(self):
        if self._name.text().strip(): self.accept()

    def get_macro(self) -> dict:
        return {"name": self._name.text().strip(), "steps": self._steps}
