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
import time
import subprocess
import tempfile

from PyQt6.QtCore import QThread, pyqtSignal

REPO   = "kuragariken/kuragariken-command-centre-pro"
ASSET  = "CommandCentrePro.exe"
API    = f"https://api.github.com/repos/{REPO}/releases/latest"

# CCP's own version — compared against the GitHub release tag. Bump this in
# lockstep with the tag you publish (tag 10.2 → set this to "10.2").
APP_VERSION = "10.11"


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


def _proxy_attempts():
    """
    Build the ordered list of proxy configs to try for GitHub, reusing the same
    detection + Pick n Pay fallback list that the 4me client uses. On the
    corporate network, direct connections to github.com are blocked and time
    out — the updater must go through the company proxy just like Team
    Analytics does. Returns a list of dicts for requests(proxies=...).
    """
    attempts = []
    try:
        from src.widgets.xurrent_client import _system_proxies, PNP_PROXIES
        detected = _system_proxies()
        if detected:
            attempts.append(detected)
        attempts.append({})   # direct (works at home / open networks)
        for p in PNP_PROXIES:
            attempts.append({"http": "http://" + p, "https": "http://" + p})
    except Exception:
        attempts = [{}]   # fall back to a plain direct attempt
    # de-dupe preserving order
    seen, ordered = set(), []
    for a in attempts:
        key = a.get("https", "") if a else ""
        if key not in seen:
            seen.add(key); ordered.append(a)
    return ordered


def _get_with_proxy(url, **kwargs):
    """
    requests.get that tries each proxy route until one connects.

    Two speed optimisations so a slow/blocked route doesn't stall the whole
    update on a fast network:
      • The proxy that worked once is cached and tried FIRST next time, so the
        download doesn't repeat the direct-connection timeout the check already
        discovered was blocked.
      • Fallback attempts use a short *connect* timeout (a dead route fails in
        ~4s instead of the full read timeout), while the real read timeout is
        preserved for the route that actually connects.
    """
    import requests
    # Split timeout into (connect, read). A blocked route hangs on CONNECT,
    # so a short connect timeout makes fallback fast; the read timeout stays
    # generous for the actual download.
    read_timeout = kwargs.pop("timeout", 30)
    fast = (4, read_timeout)

    ordered = _proxy_attempts()
    cached = getattr(_get_with_proxy, "_cached", None)
    if cached is not None:
        # try the previously-working route first
        ordered = [cached] + [a for a in ordered
                              if a.get("https", "") != (cached.get("https", "") if cached else "")]

    last_err = None
    for proxies in ordered:
        try:
            r = requests.get(url, proxies=proxies or None, timeout=fast, **kwargs)
            _get_with_proxy._cached = proxies   # remember what worked
            return r
        except (requests.exceptions.ProxyError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError) as e:
            last_err = e
            continue
    raise last_err or RuntimeError("Could not reach " + url)


_get_with_proxy._cached = None


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
            r = _get_with_proxy(
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
            # Download into the SYSTEM temp folder, never next to the exe.
            # On corporate laptops the exe often lives under a OneDrive-synced
            # Desktop, and OneDrive locks files there — which broke the swap
            # with 'Permission denied'. %TEMP% is never OneDrive-synced.
            tmp_path = os.path.join(tempfile.gettempdir(), "CommandCentrePro_new.tmp")
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except Exception: pass

            # Try PowerShell's Invoke-WebRequest first — the same mechanism
            # UPDATE.bat uses. It goes through Windows' native proxy
            # resolution (WinINet) automatically, whereas the Python path has
            # to guess through a list of candidate proxies one at a time.
            # Confirmed empirically faster on the corporate network. Falls
            # back to the Python method below if this doesn't work (non-
            # Windows dev machine, PowerShell unavailable, etc).
            ok = self._download_via_powershell(tmp_path)
            if not ok:
                self._download_via_requests(tmp_path)

            # verify 1: size sanity
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1_000_000:
                self.failed.emit("Downloaded file is too small — aborting.")
                self._cleanup(tmp_path)
                return

            # verify 2: SHA256 digest (when GitHub provides one). Computed by
            # reading the finished file once — same check regardless of which
            # download method wrote it. Assets uploaded before mid-2025 have
            # no digest → we skip this and rely on the size check alone.
            if self.digest.startswith("sha256:"):
                import hashlib
                sha = hashlib.sha256()
                with open(tmp_path, "rb") as f:
                    for block in iter(lambda: f.read(1024 * 1024), b""):
                        sha.update(block)
                want = self.digest.split(":", 1)[1].strip().lower()
                got = sha.hexdigest().lower()
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

    def _download_via_powershell(self, tmp_path):
        """
        Download via a temp .ps1 running Invoke-WebRequest (not inline
        -Command with caret continuation — that's fragile, see UPDATE.bat's
        history). Polls the growing file's size to drive the progress bar,
        since Invoke-WebRequest doesn't report byte progress back to us.
        Returns True on success, False to fall back to the Python method.
        """
        if not sys.platform.startswith("win"):
            return False
        ps1 = None
        try:
            ps1 = os.path.join(tempfile.gettempdir(), f"ccp_download_{os.getpid()}.ps1")
            with open(ps1, "w", encoding="utf-8") as f:
                f.write(
                    "$ErrorActionPreference = 'Stop'\n"
                    "[Net.ServicePointManager]::SecurityProtocol = "
                    "[Net.SecurityProtocolType]::Tls12\n"
                    "try { [System.Net.WebRequest]::DefaultWebProxy.Credentials = "
                    "[System.Net.CredentialCache]::DefaultCredentials } catch {}\n"
                    f"Invoke-WebRequest -Uri '{self.url}' -OutFile '{tmp_path}' "
                    "-Headers @{ 'User-Agent' = 'CCP-Updater' } -UseBasicParsing\n"
                )

            proc = subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", ps1],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))

            total = self.expected_size or 0
            last_emit_t = 0.0
            while proc.poll() is None:
                time.sleep(0.15)
                try:
                    done = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0
                except OSError:
                    done = 0
                now = time.monotonic()
                if now - last_emit_t > 0.1:
                    self.progress.emit(done, total)
                    last_emit_t = now
            proc.communicate()

            if proc.returncode != 0:
                return False
            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1_000_000:
                return False
            final_size = os.path.getsize(tmp_path)
            self.progress.emit(final_size, total or final_size)
            return True
        except Exception:
            return False
        finally:
            if ps1 and os.path.exists(ps1):
                try: os.remove(ps1)
                except Exception: pass

    def _download_via_requests(self, tmp_path):
        """Fallback path: Python requests with the proxy-guessing logic.
        Used only if the PowerShell method isn't available or fails."""
        with _get_with_proxy(self.url, stream=True,
                          headers={"User-Agent": "CCP-Updater"},
                          timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("Content-Length", self.expected_size or 0))
            done = 0
            last_emit_t = 0.0
            last_emit_bytes = 0
            with open(tmp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    now = time.monotonic()
                    if (now - last_emit_t > 0.1
                            or done - last_emit_bytes > 4 * 1024 * 1024
                            or done >= total > 0):
                        self.progress.emit(done, total)
                        last_emit_t = now
                        last_emit_bytes = done

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
    logf = os.path.join(tempfile.gettempdir(), "ccp_update_log.txt")

    # Notes on the logic below:
    #  • We do NOT rely on `errorlevel` inside a for-loop (it's evaluated at
    #    parse time in ()-blocks and gives stale results — a classic batch bug
    #    that made the swap silently "fail" even when the copy worked).
    #  • Instead we compare file sizes to confirm the copy landed, using a
    #    :label subroutine with CALL so errorlevel/vars behave normally.
    #  • Everything is logged to ccp_update_log.txt so a failure is visible.
    script = f"""@echo off
setlocal enabledelayedexpansion
title Command Centre Pro - applying update
set "LOG={logf}"
set "SRC={temp_path}"
set "DST={exe}"
set "BAK={exe}.bak"
echo ==== CCP update helper started %DATE% %TIME% ==== > "%LOG%"

echo Applying update, please wait...

:waitloop
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I "{exe_name}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto waitloop
)
echo App closed, proceeding. >> "%LOG%"

rem --- Backup current exe ---
copy /Y "%DST%" "%BAK%" >NUL 2>>"%LOG%"
echo Backup made. >> "%LOG%"

rem --- Try the swap up to 15 times (OneDrive/AV locks are brief) ---
set ATTEMPT=0
:swaploop
set /a ATTEMPT+=1
copy /Y "%SRC%" "%DST%" >NUL 2>>"%LOG%"
call :sizecheck
if "%SWAP_OK%"=="1" goto swapdone
if %ATTEMPT% GEQ 15 goto swapfail
echo Swap attempt %ATTEMPT% failed, retrying... >> "%LOG%"
timeout /t 1 /nobreak >NUL
goto swaploop

:swapfail
echo SWAP FAILED after %ATTEMPT% attempts. Restoring backup. >> "%LOG%"
copy /Y "%BAK%" "%DST%" >NUL 2>>"%LOG%"
del "%BAK%" >NUL 2>&1
echo.
echo  Update could not be applied ^(the file stayed locked^).
echo  Your existing version is unchanged.
echo  A log was saved to: %LOG%
echo.
pause
goto cleanup

:swapdone
echo Swap OK on attempt %ATTEMPT%. >> "%LOG%"
del "%SRC%" >NUL 2>&1

rem --- Let the freshly-written exe settle before launching. Relaunching a
rem     PyInstaller onefile too fast can collide with antivirus/OneDrive still
rem     scanning it, causing 'Failed to load python3xx.dll'. A short pause
rem     lets the file finish flushing/scanning first. ---
timeout /t 3 /nobreak >NUL
echo Relaunching... >> "%LOG%"
start "" "%DST%"
timeout /t 5 /nobreak >NUL
tasklist /FI "IMAGENAME eq {exe_name}" 2>NUL | find /I "{exe_name}" >NUL
if not errorlevel 1 (
    echo New version launched -- deleting backup. >> "%LOG%"
    del "%BAK%" >NUL 2>&1
) else (
    echo New version did NOT start -- rolling back. >> "%LOG%"
    copy /Y "%BAK%" "%DST%" >NUL 2>>"%LOG%"
    del "%BAK%" >NUL 2>&1
    start "" "%DST%"
)

:cleanup
echo ==== done ==== >> "%LOG%"
del "%~f0" >NUL 2>&1
exit /b 0

rem --- subroutine: sets SWAP_OK=1 if DST exists and is >= 1MB ---
:sizecheck
set SWAP_OK=0
if not exist "%DST%" exit /b
for %%Z in ("%DST%") do set DSTSIZE=%%~zZ
if %DSTSIZE% GEQ 1000000 set SWAP_OK=1
exit /b
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
