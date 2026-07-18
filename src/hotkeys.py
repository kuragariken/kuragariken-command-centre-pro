"""hotkeys.py — Global hotkeys via Windows RegisterHotKey.
Alt+C always works. Other hotkeys try preferred combo then fall back gracefully.
"""
import sys
import time
from PyQt6.QtCore import QObject, QThread, pyqtSignal

MOD_ALT  = 0x0001
MOD_CTRL = 0x0002
MOD_WIN  = 0x0008
MOD_NONE = 0x0000


class HotkeyThread(QThread):
    triggered = pyqtSignal(str)

    # Each entry: name -> list of (modifier, vk) to try in order
    # First one that registers successfully wins.
    HOTKEYS = {
        "show_hide":    [(MOD_ALT,  ord('C'))],               # Alt+C  (primary)
        "auto_paste":   [(MOD_WIN,  ord('V')),                # Win+V
                         (MOD_ALT,  ord('V')),                # Alt+V
                         (MOD_CTRL|MOD_ALT, ord('V'))],       # Ctrl+Alt+V
        "quick_launch": [(MOD_WIN,  ord('Q')),                # Win+Q
                         (MOD_ALT,  ord('Q')),                # Alt+Q
                         (MOD_CTRL|MOD_ALT, ord('Q'))],       # Ctrl+Alt+Q
        "pomodoro":     [(MOD_WIN,  ord('T')),                # Win+T
                         (MOD_ALT,  ord('T')),                # Alt+T
                         (MOD_CTRL|MOD_ALT, ord('T'))],       # Ctrl+Alt+T
        "command_palette": [(MOD_ALT, 0x20),                  # Alt+Space (VK_SPACE)
                         (MOD_CTRL|MOD_ALT, 0x20)],            # Ctrl+Alt+Space
    }

    def __init__(self):
        super().__init__()
        self._running = True
        self.registered = {}   # name -> (mod, vk) actually registered

    def run(self):
        if sys.platform != "win32":
            return
        try:
            import ctypes
            import ctypes.wintypes as wt
            user32 = ctypes.windll.user32

            ids = {}
            hotkey_id = 1
            for name, candidates in self.HOTKEYS.items():
                for (mod, vk) in candidates:
                    if user32.RegisterHotKey(None, hotkey_id, mod, vk):
                        ids[hotkey_id] = name
                        self.registered[name] = (mod, vk)
                        hotkey_id += 1
                        break
                else:
                    print(f"[Hotkey] Could not register {name} — all combos taken")

            msg = wt.MSG()
            while self._running:
                if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                    if msg.message == 0x0312:  # WM_HOTKEY
                        name = ids.get(msg.wParam)
                        if name:
                            self.triggered.emit(name)
                else:
                    time.sleep(0.01)

            for i in ids:
                user32.UnregisterHotKey(None, i)

        except Exception as e:
            print(f"[Hotkey] Error: {e}")

    def stop(self):
        self._running = False
        self.quit()


class HotkeyManager(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self._thread = HotkeyThread()
        self._thread.triggered.connect(self._on_hotkey)
        self._thread.start()

    def _on_hotkey(self, name: str):
        try:
            if name == "show_hide":
                self._bring_forward()
            elif name == "auto_paste":
                ap = not self.app.data["settings"].get("auto_paste", False)
                self.app.data["settings"]["auto_paste"] = ap
                from src import data as D
                D.save(self.app.data)
                self.app.toast.show_toast(f"Auto-paste {'ON' if ap else 'OFF'}")
            elif name == "quick_launch":
                self.app._toggle_quick_launch()
            elif name == "pomodoro":
                self.app._pomo_widget.toggle()
            elif name == "command_palette":
                self.app.show_command_palette()
        except Exception as e:
            print(f"[Hotkey] Handler error: {e}")

    def _bring_forward(self):
        win = self.app
        was_hidden = win.isMinimized() or not win.isVisible()
        if win.isMinimized():
            win.showNormal()
        elif not win.isVisible():
            win.show()
        win.raise_()
        win.activateWindow()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.SetForegroundWindow(int(win.winId()))
            except Exception:
                pass
        # Portal zoom-in effect when bringing window from hidden/minimised
        if was_hidden and hasattr(win, 'portal_in'):
            win.portal_in()

    def stop(self):
        self._thread.stop()
        self._thread.wait(2000)
