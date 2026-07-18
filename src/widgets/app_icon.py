"""
app_icon.py — one reliable source of the CCP window icon.

Why this exists: on Windows, calling app.setWindowIcon() alone does NOT
guarantee every top-level window shows the app's icon. Frameless / Tool /
native popout windows (Settings, Vault, Notepad, Teams) each need their own
setWindowIcon(), otherwise Windows shows the taskbar entry with whatever
ambient icon it can find — which is how CCP ended up wearing another app's
icon (e.g. Claude). Combined with a unique AppUserModelID set at startup,
setting this icon on every top-level window fixes the theft.

Usage:
    from src.widgets.app_icon import apply_window_icon
    apply_window_icon(self)   # in each top-level window's __init__
"""
import os
import sys

from PyQt6.QtGui import QIcon

_cached_icon = None


def _resource(rel: str) -> str:
    """Resolve a bundled resource path in both frozen (.exe) and dev modes."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        # src/widgets/app_icon.py → project root is two levels up
        base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, rel)


def get_app_icon() -> QIcon:
    """Return the cached CCP QIcon, loading it once. Empty QIcon if missing."""
    global _cached_icon
    if _cached_icon is not None:
        return _cached_icon
    for name in ("icon.ico", "icon.png", "assets/icon.ico"):
        path = _resource(name)
        if os.path.exists(path):
            _cached_icon = QIcon(path)
            return _cached_icon
    _cached_icon = QIcon()  # empty — no crash, just no icon
    return _cached_icon


def apply_window_icon(window) -> None:
    """Set the CCP icon on a top-level window (no-op if icon unavailable)."""
    try:
        icon = get_app_icon()
        if not icon.isNull():
            window.setWindowIcon(icon)
    except Exception:
        pass
