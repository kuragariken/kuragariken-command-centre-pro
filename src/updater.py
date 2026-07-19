"""
updater.py — self-updater for Command Centre Pro.

Design:
  • Detection: compares APP_VERSION (baked into this build) against the latest
    GitHub release tag_name. A higher tag → an update is available. Tags are
    parsed numerically ("10.10" > "10.9"), tolerating a leading 'v'.
  • Check: silent, on startup, in a background thread. Only speaks up if an
    update is actually available.
  • Apply: download+verify to a temp file (size + SHA256 against GitHub's
    asset digest), write a helper .bat, quit CCP, let the helper swap the exe
    and relaunch. The running exe is never touched by CCP itself. One backup
    is kept during the swap and auto-deleted once the new build launches.
  • Dev mode: everything no-ops when not frozen (no exe to swap).

Remember to bump APP_VERSION to match each release tag you publish.
"""
import os
import sys
import json
import subprocess
import tempfile

from PyQt6.QtCore import QThread, pyqtSignal

REPO   = "kuragariken/kuragariken-command-centre-pro"
ASSET  = "CommandCentrePro.exe"
API    = f"https://api.github.com/repos/{REPO}/releases/latest"

# CCP's own version — compared against the GitHub release tag. Bump this in
# lockstep with the tag you publish (tag 10.2 → set this to "10.2").
APP_VERSION = "10.1"


def _parse_version(v: str):
    """
    Turn a version string into a comparable tuple of ints.
    Handles a leading 'v' and any non-numeric noise: 'v10.1' -> (10, 1),
    '10.10' -> (10, 10). Missing/garbage parts count as 0 so a malformed
    tag never falsely reads as newer.
    """
    v = (v or "").strip().lstrip("vV")
    parts = []
    for chunk in v.split("."):
        num = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts) if parts else (0,)

# Where we remember which asset build we're on (its updated_at timestamp).
def _state_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = os.path.join(base, "Command Centre Pro")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "update_state.json")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _load_state() -> dict:
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: dict):
    try:
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


class UpdateChecker(QThread):
    """
    Silently asks GitHub for the latest asset's updated_at + download URL.
    Emits update_available(url, when, size) only if it's newer than the
    baseline we recorded. Emits nothing user-facing on error / up-to-date.
    """
    update_available = pyqtSignal(str, str, int, str)   # url, tag, size, digest
    up_to_date       = pyqtSignal()
    check_failed     = pyqtSignal(str)

    def run(self):
        if not is_frozen():
            self.up_to_date.emit()     # nothing to update in dev mode
            return
        try:
            import requests
            r = requests.get(
                API, headers={"User-Agent": "CCP-Updater",
                              "Accept": "application/vnd.github+json"},
                timeout=15)
            r.raise_for_status()
            data = r.json()

            tag = data.get("tag_name", "")
            asset = next((a for a in data.get("assets", [])
                          if a.get("name") == ASSET), None)
            if not asset:
                self.check_failed.emit("No matching release asset found.")
                return

            url    = asset.get("browser_download_url", "")
            size   = int(asset.get("size", 0))
            digest = asset.get("digest") or ""

            # Compare the release tag against our own version. Newer tag → offer.
            if _parse_version(tag) > _parse_version(APP_VERSION):
                self.update_available.emit(url, tag, size, digest)
            else:
                self.up_to_date.emit()
        except Exception as e:
            self.check_failed.emit(str(e))


class UpdateDownloader(QThread):
    """
    Downloads the new exe to a temp file, streaming progress. Verifies size,
    then emits finished(temp_path). On any failure emits failed(msg) and the
    running exe is left untouched.
    """
    progress = pyqtSignal(int, int)    # bytes_done, bytes_total
    finished_ok = pyqtSignal(str)      # temp_path
    failed = pyqtSignal(str)

    def __init__(self, url: str, expected_size: int, tag: str, digest: str = ""):
        super().__init__()
        self.url = url
        self.expected_size = expected_size
        self.tag = tag
        self.digest = digest          # "sha256:<hex>" or "" if unavailable

    def run(self):
        try:
            import requests, hashlib
            tmp_dir = os.path.dirname(sys.executable)
            tmp_path = os.path.join(tmp_dir, "CommandCentrePro_new.tmp")
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass

            sha = hashlib.sha256()
            with requests.get(self.url, stream=True,
                              headers={"User-Agent": "CCP-Updater"},
                              timeout=30) as r:
                r.raise_for_status()
                total = int(r.headers.get("Content-Length",
                                          self.expected_size or 0))
                done = 0
                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)
                        sha.update(chunk)
                        done += len(chunk)
                        self.progress.emit(done, total)

            # verify 1: size sanity
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1_000_000:
                self.failed.emit("Downloaded file is too small — aborting.")
                self._cleanup(tmp_path)
                return

            # verify 2: SHA256 digest (when GitHub provides one). This catches
            # corrupt / partial / tampered downloads that still pass the size
            # check. Assets uploaded before mid-2025 have no digest → we skip
            # this step and rely on the size check alone.
            if self.digest.startswith("sha256:"):
                want = self.digest.split(":", 1)[1].strip().lower()
                got  = sha.hexdigest().lower()
                if want != got:
                    self.failed.emit(
                        "Integrity check failed — the download's checksum "
                        "doesn't match GitHub's. Update aborted; your version "
                        "is unchanged.")
                    self._cleanup(tmp_path)
                    return

            # Tag-based detection compares against APP_VERSION (baked into the
            # build), so there's no per-machine state to write here.
            self.finished_ok.emit(tmp_path)
        except Exception as e:
            self.failed.emit(str(e))

    def _cleanup(self, path):
        try: os.remove(path)
        except Exception: pass


def apply_update_and_relaunch(temp_path: str):
    """
    Write a helper .bat that waits for CCP to exit, swaps the temp exe over the
    running exe, relaunches it, and deletes itself. Then quit CCP. The running
    exe is only touched by the helper, after we've exited — no file lock.
    """
    if not is_frozen():
        return False
    exe = sys.executable
    exe_name = os.path.basename(exe)
    helper = os.path.join(tempfile.gettempdir(), "ccp_update_helper.bat")

    script = f"""@echo off
title Command Centre Pro - applying update
cd /d "{os.path.dirname(exe)}"
echo Applying update, please wait...
:waitloop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I "{exe_name}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto waitloop
)

rem --- One safety backup of the current exe before we overwrite it ---
copy /Y "{exe}" "{exe}.bak" >NUL

rem --- Swap in the new build ---
move /Y "{temp_path}" "{exe}" >NUL
if errorlevel 1 (
    echo Update failed to apply. Restoring previous version...
    copy /Y "{exe}.bak" "{exe}" >NUL
    del "{exe}.bak" >NUL 2>&1
    echo Your app is unchanged.
    pause
    exit /b 1
)

rem --- Relaunch; only clear the backup once the new build actually starts ---
start "" "{exe}"
timeout /t 3 /nobreak >NUL
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I "{exe_name}" >NUL
if not errorlevel 1 (
    rem New version launched successfully -> backup no longer needed
    del "{exe}.bak" >NUL 2>&1
) else (
    rem New build didn't start -> roll back to the backup
    copy /Y "{exe}.bak" "{exe}" >NUL
    del "{exe}.bak" >NUL 2>&1
    start "" "{exe}"
)
del "%~f0"
"""
    try:
        with open(helper, "w", encoding="utf-8") as f:
            f.write(script)
        # Launch detached so it survives CCP exiting.
        subprocess.Popen(
            ["cmd", "/c", helper],
            creationflags=(subprocess.CREATE_NO_WINDOW
                           if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
            close_fds=True)
        return True
    except Exception:
        return False
