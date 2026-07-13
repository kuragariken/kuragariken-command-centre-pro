"""Command Centre Pro — Support Engineer Toolkit v10"""
import sys
import os
import traceback

os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CommandCentrePro.v10")
    except Exception:
        pass


# Ensure the project root is on sys.path so `src` is importable
# This is needed in both frozen and dev modes
import sys as _sys, os as _os
_root = _os.path.dirname(_os.path.abspath(__file__)) if not getattr(_sys,"frozen",False) else _sys._MEIPASS  # type: ignore
if _root not in _sys.path:
    _sys.path.insert(0, _root)


def _resource(rel: str) -> str:
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS  # type: ignore
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, rel)


def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def main():
    try:
        from PyQt6.QtWidgets import QApplication, QStyleFactory
        from PyQt6.QtGui import QIcon, QFont, QFontDatabase
        from PyQt6.QtCore import Qt
        import os as _os

        # ── High DPI — must be set BEFORE QApplication ────────
        # Enables crisp rendering on 1080p, 1440p, 4K and HiDPI displays
        # ── High-DPI: research-backed approach for Qt6 on Windows ─────
        # Source: Qt official docs + Qt Forum QTBUG-143646
        # Qt6 is already Per-Monitor-V2 DPI aware by default.
        # QT_ENABLE_HIGHDPI_SCALING=1 tells QtGui to apply per-screen
        # scale factors derived from the OS logical DPI.
        # RoundPreferFloor avoids fractional scaling which causes
        # sub-pixel blurring (e.g. 125% → stays at 1.0x, not 1.25x).
        _os.environ['QT_ENABLE_HIGHDPI_SCALING']       = '1'
        _os.environ['QT_SCALE_FACTOR_ROUNDING_POLICY'] = 'RoundPreferFloor'
        # QT_AUTO_SCREEN_SCALE_FACTOR for compatibility with Qt5 era code
        _os.environ['QT_AUTO_SCREEN_SCALE_FACTOR']     = '1'

        # ── Auto-set DPI override in registry ───────────────────────────
        # Equivalent to: right-click exe → Compatibility → Override DPI → Application
        # This tells Windows to let Qt handle scaling instead of bitmap-stretching
        # the window — the single biggest fix for pixelation on 125%/150% displays.
        try:
            import winreg, sys as _sys
            exe_path = _os.path.abspath(
                _sys.executable if getattr(_sys, 'frozen', False)
                else __file__)
            # The registry value that controls the Compatibility tab DPI setting
            key_path = (
                r'Software\Microsoft\Windows NT\CurrentVersion'
                r'\AppCompatFlags\Layers')
            # '~ HIGHDPIAWARE' = 'Override DPI scaling → Application'
            dpi_flag = '~ HIGHDPIAWARE'
            with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, key_path,
                    0, winreg.KEY_SET_VALUE | winreg.KEY_READ) as k:
                try:
                    existing, _ = winreg.QueryValueEx(k, exe_path)
                    if dpi_flag not in existing:
                        winreg.SetValueEx(
                            k, exe_path, 0,
                            winreg.REG_SZ,
                            existing + ' ' + dpi_flag)
                except FileNotFoundError:
                    winreg.SetValueEx(
                        k, exe_path, 0, winreg.REG_SZ, dpi_flag)
        except Exception:
            pass  # Non-Windows or no registry access — silent fail

        app = QApplication(sys.argv)
        app.setStyle(QStyleFactory.create("Fusion"))
        app.setApplicationName("Command Centre Pro")
        app.setApplicationVersion("10.0")
        app.setQuitOnLastWindowClosed(False)

        icon_path = _resource("icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))

        # Premium font: Inter > Segoe UI Variable Text (Win11) > Segoe UI (Win10)
        # Research: Segoe UI Variable is Windows 11's native variable font.
        # It has built-in optical axis scaling — small text gets different outlines
        # than large text, optimised for Windows DirectWrite rendering.
        # Inter .otf lacks Windows TrueType hinting → renders soft/blurry.
        # Source: Microsoft Typography docs + FlatLaf/Inter issue #764
        available = QFontDatabase.families()
        if "Segoe UI Variable Text" in available:
            ui_font = "Segoe UI Variable Text"   # Win11 native — sharpest
        elif "Segoe UI Variable" in available:
            ui_font = "Segoe UI Variable"
        elif "Inter" in available:
            ui_font = "Inter"                    # Fallback if installed
        else:
            ui_font = "Segoe UI"                # Win10 fallback

        base_font = QFont(ui_font, 10)
        base_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        base_font.setStyleStrategy(
            QFont.StyleStrategy.PreferAntialias |
            QFont.StyleStrategy.PreferQuality)
        app.setFont(base_font)

        # Crisp subpixel rendering
        from PyQt6.QtGui import QPainter
        # Force high quality render hints globally

        from src.app import CommandCentreApp
        window = CommandCentreApp()
        window.show()
        sys.exit(app.exec())

    except Exception as e:
        log_path = os.path.join(_exe_dir(), "crash.log")
        try:
            with open(log_path, "w") as f:
                f.write(f"Command Centre Pro crashed\nPython: {sys.version}\n"
                        f"Frozen: {getattr(sys, 'frozen', False)}\n\n")
                f.write(traceback.format_exc())
        except Exception:
            pass
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            _app = QApplication.instance() or QApplication(sys.argv)
            msg = QMessageBox()
            msg.setWindowTitle("Command Centre Pro — Startup Error")
            msg.setText(f"Failed to start:\n\n{e}\n\nSee crash.log next to the exe.")
            msg.exec()
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
