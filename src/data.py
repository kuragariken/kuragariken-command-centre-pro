"""
data.py — All persistence for Command Centre Pro v10.
Data lives in %APPDATA%/Command Centre Pro/ — never next to the exe.
"""
import json
import os
import sys
import copy
import hashlib
from datetime import datetime

APP_NAME   = "CommandCentrePro"
APP_FOLDER = "Command Centre Pro"

MAX_BACKUPS = 5

# Bundled default loaded after _exe_dir is defined (see below)


# ── Paths ─────────────────────────────────────────────────────────

def _data_dir() -> str:
    """
    Dedicated data folder — never floats next to the exe.
    Windows: %APPDATA%/Command Centre Pro/
    Other:   ~/.CommandCentrePro/
    Created automatically on first run.
    """
    appdata = os.environ.get("APPDATA", "")
    if appdata and sys.platform == "win32":
        folder = os.path.join(appdata, APP_FOLDER)
    else:
        folder = os.path.join(os.path.expanduser("~"), f".{APP_NAME}")
    os.makedirs(folder, exist_ok=True)
    return folder


def _exe_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def _paths() -> dict:
    d = _data_dir()
    return {
        "data":   os.path.join(d, "CommandCentre.json"),
        "backup": os.path.join(d, "CommandCentre_Backups"),
        "log":    os.path.join(d, "CommandCentre_session.log"),
        "ini":    os.path.join(_exe_dir(), "CommandCentre.ini"),  # old location
        "folder": d,
    }


def _load_default_commands() -> dict:
    """Load the bundled default config, trying exe dir then script dir."""
    candidates = [
        os.path.join(_exe_dir(), "CommandCentre_default.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     "..", "CommandCentre_default.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}

_BUNDLED_DEFAULT = _load_default_commands()


def get_data_folder() -> str:
    """Return the data folder path — shown in Settings."""
    return _data_dir()


# ── Default data ──────────────────────────────────────────────────

def _default_data() -> dict:
    return {
        "settings": {
            "theme":         "Default",
            "display_mode":  "grid",
            "layout_mode":   "flow",   # flow or bento
            "btn_size":      "M",
            "opacity":       100,
            "auto_paste":    False,
            "session_log":   False,
            "pomo_focus":    25,
            "pomo_break":    5,
            "vault_salt":    "",
            "vault_canary":  "",
            "always_on_top": False,
            "window_pos":    None,
            "keep_alive_enabled":      False,
            "keep_alive_interval_min": 4,
        },
        "categories":    _BUNDLED_DEFAULT.get("categories",
                              list(_BUNDLED_DEFAULT.get("commands", {}).keys())),
        "commands":      copy.deepcopy(
                              _BUNDLED_DEFAULT.get("commands", {})),
        "copy_counts":   {},
        "favourites":    [],
        "clip_history":  [],
        "quick_launch":  [],
        "hotstrings":    {},
        "reminders":     [],
        "macros":        [],
        "vault_entries": [],
        "notes":         [],
        "tickets":       [],
        "session_stats": {
            "copies_today":    0,
            "copies_total":    0,
            "pomo_sessions":   0,
            "last_reset_date": "",
            "daily_history":   {},
            "hourly_today":    {},
            "top_commands":    {},
            "category_counts": {},
        },
    }


# ── Load / Save ───────────────────────────────────────────────────

def _deep_merge(base: dict, overlay: dict):
    for k, v in overlay.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


def load() -> dict:
    paths = _paths()
    # Load from JSON
    if os.path.exists(paths["data"]):
        try:
            with open(paths["data"], "r", encoding="utf-8") as f:
                loaded = json.load(f)
            base = _default_data()
            _deep_merge(base, loaded)
            return base
        except Exception as e:
            print(f"[CCP] Load error: {e}")

    # Try INI migration from old location
    if os.path.exists(paths["ini"]):
        data = _migrate_ini(paths["ini"])
        save(data)
        return data

    return _default_data()


def save(data: dict):
    paths = _paths()
    try:
        tmp = paths["data"] + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, paths["data"])   # atomic — no data loss on crash
    except Exception as e:
        print(f"[CCP] Save error: {e}")


# ── Backup ────────────────────────────────────────────────────────

def backup(data: dict):
    paths = _paths()
    bd    = paths["backup"]
    os.makedirs(bd, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest  = os.path.join(bd, f"backup_{stamp}.json")
    try:
        with open(dest, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    _rotate_backups(bd)


def _rotate_backups(bd: str):
    try:
        files = sorted(f for f in os.listdir(bd) if f.startswith("backup_"))
        while len(files) > MAX_BACKUPS:
            os.remove(os.path.join(bd, files.pop(0)))
    except Exception:
        pass


def list_backups() -> list:
    paths = _paths()
    try:
        files = sorted(
            (f for f in os.listdir(paths["backup"]) if f.startswith("backup_")),
            reverse=True
        )
        return [os.path.join(paths["backup"], f) for f in files]
    except Exception:
        return []


def restore_backup(path: str, current_data: dict) -> dict:
    backup(current_data)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ── Vault helpers ────────────────────────────────────────────────

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode("utf-8")).hexdigest()


def check_password(pw: str, stored_hash: str) -> bool:
    return hash_password(pw) == stored_hash


# ── Analytics ─────────────────────────────────────────────────────

def record_copy(data: dict, label: str, category: str):
    today = datetime.now().strftime("%Y-%m-%d")
    hour  = datetime.now().strftime("%H")
    stats = data.setdefault("session_stats", {})

    if stats.get("last_reset_date") != today:
        stats["copies_today"]    = 0
        stats["hourly_today"]    = {}
        stats["last_reset_date"] = today

    stats["copies_today"] = stats.get("copies_today", 0) + 1
    stats["copies_total"] = stats.get("copies_total", 0) + 1

    stats.setdefault("daily_history", {})[today] = \
        stats["daily_history"].get(today, 0) + 1
    stats.setdefault("hourly_today", {})[hour] = \
        stats["hourly_today"].get(hour, 0) + 1
    stats.setdefault("top_commands", {})[label] = \
        stats["top_commands"].get(label, 0) + 1
    stats.setdefault("category_counts", {})[category] = \
        stats["category_counts"].get(category, 0) + 1
    data.setdefault("copy_counts", {})[label] = \
        data["copy_counts"].get(label, 0) + 1


# ── Session log ───────────────────────────────────────────────────

def log_copy(label: str, text: str):
    paths = _paths()
    try:
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(paths["log"], "a", encoding="utf-8") as f:
            f.write(f"[{stamp}]  COPY  [{label}]  {text[:80]}\n")
    except Exception:
        pass


# ── INI migration ─────────────────────────────────────────────────

def _read_ini_section(path: str, section: str) -> dict:
    result = {}; in_sec = False
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("["):
                    in_sec = (line[1:].split("]")[0].strip() == section)
                elif in_sec and "=" in line:
                    k, _, v = line.partition("=")
                    result[k.strip().lower()] = v.strip()
    except Exception:
        pass
    return result


def _migrate_ini(ini_path: str) -> dict:
    data = _default_data()
    s    = _read_ini_section(ini_path, "Settings")
    data["settings"]["theme"]        = s.get("theme", "Default")
    data["settings"]["always_on_top"]= s.get("alwaysontop","0") == "1"
    try: data["settings"]["opacity"] = max(30, min(100, int(s.get("opacity","255"))*100//255))
    except Exception: pass
    try: data["settings"]["pomo_focus"] = int(s.get("pomofocus","25"))
    except Exception: pass
    try: data["settings"]["pomo_break"] = int(s.get("pomobreak","5"))
    except Exception: pass

    cats_sec = _read_ini_section(ini_path, "Categories")
    try:    total_cats = int(cats_sec.get("total","0"))
    except: total_cats = 0
    if total_cats > 0:
        data["categories"] = []; data["commands"] = {}
        for ci in range(1, total_cats+1):
            cat = cats_sec.get(f"cat{ci}","")
            if not cat: continue
            data["categories"].append(cat)
            cat_sec = _read_ini_section(ini_path, f"Cat_{ci}")
            try:    n = int(cat_sec.get("total","0"))
            except: n = 0
            cmds = []
            for di in range(1, n+1):
                lbl = cat_sec.get(f"label{di}","")
                txt = cat_sec.get(f"text{di}","")
                if lbl:
                    cmds.append({"label":lbl,"text":txt,"notes":"","tags":"","priority":"NORMAL"})
            data["commands"][cat] = cmds
    return data


# ── AHK JSON import ───────────────────────────────────────────────

def import_from_ahk(app_data: dict, file_path: str) -> tuple:
    """
    Import from old AHK v9 JSON export.
    Returns (new_cats, new_cmds, skipped).
    """
    import re

    raw = open(file_path, encoding="utf-8").read()

    def fix_escapes(s):
        result = []; i = 0
        while i < len(s):
            if s[i] == "\\" and i+1 < len(s):
                if s[i+1] in ('"','\\','/','b','f','n','r','t','u'):
                    result.append(s[i]); result.append(s[i+1]); i += 2
                else:
                    result.append('\\\\'); i += 1
            else:
                result.append(s[i]); i += 1
        return ''.join(result)

    ahk_data = json.loads(fix_escapes(raw))
    ahk_cats = ahk_data.get("categories", {})

    new_cats = 0; new_cmds = 0; skipped = 0
    existing_cats = app_data.setdefault("categories", [])
    existing_cmds = app_data.setdefault("commands",   {})

    for cat_name, cmds in ahk_cats.items():
        if cat_name not in existing_cats:
            existing_cats.append(cat_name)
            existing_cmds[cat_name] = []
            new_cats += 1
        elif cat_name not in existing_cmds:
            existing_cmds[cat_name] = []

        existing_labels = {c.get("label","").strip().lower()
                           for c in existing_cmds[cat_name]}
        for cmd in cmds:
            label = cmd.get("label","").strip()
            text  = cmd.get("text", "").strip()
            if not label or not text:
                skipped += 1; continue
            if label.lower() in existing_labels:
                skipped += 1; continue
            pmap = {"URGENT":"URGENT","INFO":"INFO","DONE":"DONE","NORMAL":"NORMAL"}
            existing_cmds[cat_name].append({
                "label":    label,
                "text":     text,
                "notes":    cmd.get("note",""),
                "tags":     cmd.get("tags",""),
                "priority": pmap.get(cmd.get("prio","NORMAL"),"NORMAL"),
            })
            existing_labels.add(label.lower())
            new_cmds += 1
            if cmd.get("fav"):
                favs = app_data.setdefault("favourites",[])
                if label not in favs: favs.append(label)

    save(app_data)
    return new_cats, new_cmds, skipped
