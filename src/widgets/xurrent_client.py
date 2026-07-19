"""
xurrent_client.py — 4me / Xurrent GraphQL client for CCP team analytics.

Ported from the standalone 4me_pro app, trimmed to exactly what the CCP
Team Analytics panel needs: the credential store, the GraphQL POST helper,
the completed-ticket analytics query (paginated), and a QThread worker.

Only two teams are tracked here — POS Support and POS EFT — since the CCP
panel is a focused head-to-head between them (BCX dropped).

Credential storage: a base64-obfuscated file in the user's home dir, the
same file the standalone 4me_pro uses, so credentials are shared between
the two apps and load silently (no master-password prompt) — which is what
lets the panel auto-refresh in the background. NOTE: base64 is obfuscation,
not encryption; anyone with the file can decode the token.
"""
import os
import json
import base64
from collections import defaultdict
from datetime import date, timedelta

import requests
from PyQt6.QtCore import QThread, pyqtSignal


GRAPHQL_URL = "https://graphql.4me.com/"
VAULT_FILE  = os.path.join(os.path.expanduser("~"), ".4me_pro_creds.json")

# Only the two teams this panel compares. Node IDs carried over from 4me_pro.
TEAM_IDS = {
    "POS Support": "NG1lLmNvbS9UZWFtLzE1ODQw",
    "POS EFT":     "NG1lLmNvbS9UZWFtLzE1ODM4",
}


# ── date helpers ──────────────────────────────────────────────────────────────
def today_str():  return date.today().isoformat()
def week_start(): return (date.today() - timedelta(days=date.today().weekday())).isoformat()
def month_start(): return date.today().replace(day=1).isoformat()


# ── credential vault (shared with standalone 4me_pro) ─────────────────────────
def vault_save(token, account):
    with open(VAULT_FILE, "w") as f:
        json.dump({"v": base64.b64encode(
            json.dumps({"t": token, "a": account}).encode()).decode()}, f)


def vault_load():
    try:
        with open(VAULT_FILE) as f:
            d = json.loads(base64.b64decode(json.load(f)["v"]).decode())
            return d.get("t", ""), d.get("a", "")
    except Exception:
        return "", ""


def vault_clear():
    try:
        os.remove(VAULT_FILE)
    except Exception:
        pass


# ── metric helpers ────────────────────────────────────────────────────────────
def _hours_between(created_iso: str, updated_iso: str):
    """Hours between createdAt and updatedAt. None if either is missing/bad."""
    from datetime import datetime
    if not created_iso or not updated_iso:
        return None
    try:
        c = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
        u = datetime.fromisoformat(updated_iso.replace("Z", "+00:00"))
        return (u - c).total_seconds() / 3600.0
    except Exception:
        return None


def _median(vals):
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _steadiness(daily_counts):
    """
    0–100 steadiness score from daily close counts. Uses the coefficient of
    variation (std/mean): steady output → low CV → high score. A team that
    closes ~the same number every day scores near 100; one that spikes and
    goes quiet scores low.
    """
    if not daily_counts or len(daily_counts) < 2:
        return None
    mean = sum(daily_counts) / len(daily_counts)
    if mean == 0:
        return None
    var = sum((x - mean) ** 2 for x in daily_counts) / len(daily_counts)
    std = var ** 0.5
    cv = std / mean
    # map CV (0 = perfect) to 0–100; CV of 1.0+ → ~0, CV of 0 → 100
    return max(0.0, min(100.0, (1.0 - cv) * 100.0))


def _balance(agent_counts):
    """
    0–100 balance score for how evenly work is spread across a team's agents,
    using (1 - Gini) * 100. 100 = everyone did an equal share; low = one or
    two people carried the whole team. Single-agent teams return None (no
    spread to measure).
    """
    vals = [v for v in agent_counts if v > 0]
    n = len(vals)
    if n < 2:
        return None
    vals.sort()
    total = sum(vals)
    if total == 0:
        return None
    # Gini coefficient
    cum = 0
    for i, v in enumerate(vals, 1):
        cum += i * v
    gini = (2 * cum) / (n * total) - (n + 1) / n
    return max(0.0, min(100.0, (1.0 - gini) * 100.0))


# ── GraphQL ───────────────────────────────────────────────────────────────────
def _winhttp_proxy_for(url):
    """
    Ask Windows what proxy the *browser* would use for this URL, including
    resolving any PAC / auto-config script. This is the WinHTTP auto-proxy
    API (WinHttpGetProxyForUrl) — the same machinery IE/Edge/Chrome use.

    This is the key fix for corporate networks that hand out proxy settings
    via a PAC file: the registry ProxyServer value is empty in that case, so
    the older lookup found nothing and CCP fell back to a direct (blocked)
    connection. This resolves the actual proxy the browser is using.

    Returns "host:port" or None.
    """
    try:
        import ctypes
        from ctypes import wintypes

        winhttp = ctypes.WinDLL("winhttp", use_last_error=True)

        # WINHTTP_AUTOPROXY_OPTIONS
        WINHTTP_AUTOPROXY_AUTO_DETECT      = 0x00000001
        WINHTTP_AUTOPROXY_CONFIG_URL       = 0x00000002
        WINHTTP_AUTO_DETECT_TYPE_DHCP      = 0x00000001
        WINHTTP_AUTO_DETECT_TYPE_DNS_A     = 0x00000002
        WINHTTP_ACCESS_TYPE_NO_PROXY       = 1

        class WINHTTP_AUTOPROXY_OPTIONS(ctypes.Structure):
            _fields_ = [
                ("dwFlags", wintypes.DWORD),
                ("dwAutoDetectFlags", wintypes.DWORD),
                ("lpszAutoConfigUrl", wintypes.LPCWSTR),
                ("lpvReserved", ctypes.c_void_p),
                ("dwReserved", wintypes.DWORD),
                ("fAutoLogonIfChallenged", wintypes.BOOL),
            ]

        class WINHTTP_CURRENT_USER_IE_PROXY_CONFIG(ctypes.Structure):
            _fields_ = [
                ("fAutoDetect", wintypes.BOOL),
                ("lpszAutoConfigUrl", wintypes.LPWSTR),
                ("lpszProxy", wintypes.LPWSTR),
                ("lpszProxyBypass", wintypes.LPWSTR),
            ]

        class WINHTTP_PROXY_INFO(ctypes.Structure):
            _fields_ = [
                ("dwAccessType", wintypes.DWORD),
                ("lpszProxy", wintypes.LPWSTR),
                ("lpszProxyBypass", wintypes.LPWSTR),
            ]

        hSession = winhttp.WinHttpOpen(
            ctypes.c_wchar_p("CCP-Updater"),
            WINHTTP_ACCESS_TYPE_NO_PROXY, None, None, 0)
        if not hSession:
            return None

        try:
            # Read the user's IE/Edge proxy config (auto-detect + PAC URL)
            ie = WINHTTP_CURRENT_USER_IE_PROXY_CONFIG()
            winhttp.WinHttpGetIEProxyConfigForCurrentUser(ctypes.byref(ie))

            # If a static proxy is set here, use it directly.
            if ie.lpszProxy:
                return _first_proxy(ie.lpszProxy)

            # Otherwise resolve via auto-detect / PAC.
            opts = WINHTTP_AUTOPROXY_OPTIONS()
            if ie.fAutoDetect:
                opts.dwFlags |= WINHTTP_AUTOPROXY_AUTO_DETECT
                opts.dwAutoDetectFlags = (WINHTTP_AUTO_DETECT_TYPE_DHCP |
                                          WINHTTP_AUTO_DETECT_TYPE_DNS_A)
            if ie.lpszAutoConfigUrl:
                opts.dwFlags |= WINHTTP_AUTOPROXY_CONFIG_URL
                opts.lpszAutoConfigUrl = ie.lpszAutoConfigUrl
            opts.fAutoLogonIfChallenged = True

            if opts.dwFlags == 0:
                return None

            info = WINHTTP_PROXY_INFO()
            ok = winhttp.WinHttpGetProxyForUrl(
                hSession, ctypes.c_wchar_p(url),
                ctypes.byref(opts), ctypes.byref(info))
            if ok and info.lpszProxy:
                return _first_proxy(info.lpszProxy)
        finally:
            winhttp.WinHttpCloseHandle(hSession)
    except Exception:
        pass
    return None


def _first_proxy(proxy_str):
    """WinHTTP may return 'host:port' or a list 'h1:p1;h2:p2' — take the first."""
    if not proxy_str:
        return None
    first = proxy_str.replace(" ", ";").split(";")[0].strip()
    return first or None


def _system_proxies():
    """
    Discover the proxy CCP should use for outbound HTTPS, in order:
      1. HTTPS_PROXY / HTTP_PROXY environment variables (manual override)
      2. WinHTTP auto-proxy — resolves PAC / auto-config scripts, the same as
         the browser (handles corporate networks that use a .pac file)
      3. the static Windows registry proxy (simple host:port setups)
    Returns a dict for requests(proxies=...), or {} for a direct connection.
    """
    # 1. explicit env vars win
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val:
            return {"http": val, "https": val}

    # 2. WinHTTP auto-proxy (PAC-aware — the real fix for corporate networks)
    try:
        p = _winhttp_proxy_for("https://graphql.4me.com/")
        if p:
            if not p.startswith("http"):
                p = "http://" + p
            return {"http": p, "https": p}
    except Exception:
        pass

    # 3. static registry proxy (simple host:port)
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Internet Settings")
        enabled, _ = winreg.QueryValueEx(key, "ProxyEnable")
        if enabled:
            server, _ = winreg.QueryValueEx(key, "ProxyServer")
            winreg.CloseKey(key)
            if server:
                if "=" in server:
                    parts = dict(
                        p.split("=", 1) for p in server.split(";") if "=" in p)
                    https = parts.get("https") or parts.get("http")
                else:
                    https = server
                if https:
                    if not https.startswith("http"):
                        https = "http://" + https
                    return {"http": https, "https": https}
        else:
            winreg.CloseKey(key)
    except Exception:
        pass
    return {}


# Known Pick n Pay proxies, taken from the corporate PAC file
# (proxyconfig.pnpgroup.co.za/proxy.pac). Which one applies depends on the
# office/IP, but these are ALL the proxies the network uses. CCP tries them
# in order (default first) and uses whichever actually connects — so it works
# from any PnP location without needing to know which office you're in.
PNP_PROXIES = [
    "isproxy01.pnpgroup.co.za:3128",   # default / VPN / most locations
    "wcproxy01.pnpgroup.co.za:3128",   # Western Cape / PNPStudio
    "gpproxy01.pnpgroup.co.za:3128",   # Gauteng
    "breeproxy01.pnpgroup.co.za:3128", # KZN (Bree)
    "proxy01.pnpgroup.co.za:3128",     # WC (10.1.12.x)
]


def _gql(token, account, query):
    h = {
        "Authorization":    f"Bearer {token}",
        "X-Xurrent-Account": account,
        "Content-Type":     "application/json",
    }

    # Build the list of connection attempts to try, in priority order:
    #   1. whatever _system_proxies found (env var / WinHTTP / registry)
    #   2. a direct connection (works at home / open networks)
    #   3. each known Pick n Pay proxy in turn (corporate network)
    # We use the first one that actually connects. A cached working proxy is
    # tried first on subsequent calls so we don't re-scan every time.
    attempts = []

    if getattr(_gql, "_cached_proxy", None) is not None:
        attempts.append(_gql._cached_proxy)   # last thing that worked

    detected = _system_proxies()
    if detected:
        attempts.append(detected)
    attempts.append({})   # direct
    for p in PNP_PROXIES:
        attempts.append({"http": "http://" + p, "https": "http://" + p})

    # de-dupe while preserving order
    seen = set(); ordered = []
    for a in attempts:
        key = a.get("https", "") if a else ""
        if key not in seen:
            seen.add(key); ordered.append(a)

    last_err = None
    for proxies in ordered:
        try:
            r = requests.post(GRAPHQL_URL, json={"query": query}, headers=h,
                              timeout=12, proxies=proxies or None)
            r.raise_for_status()
            d = r.json()
            if "errors" in d:
                # A GraphQL error means we DID reach 4me — connection is fine,
                # so stop trying proxies and surface the real error.
                _gql._cached_proxy = proxies
                raise RuntimeError(d["errors"][0]["message"])
            _gql._cached_proxy = proxies   # remember what worked
            return d.get("data", {})
        except (requests.exceptions.ProxyError,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError) as e:
            last_err = e
            continue   # this route failed — try the next one
        except requests.exceptions.RequestException as e:
            last_err = e
            continue

    # Nothing connected.
    raise RuntimeError(
        "Couldn't reach graphql.4me.com through any known route "
        "(direct or the Pick n Pay proxies).\n"
        "If your browser CAN open 4me, run this in PowerShell to find your "
        "exact proxy and set it as HTTPS_PROXY:\n"
        '  [System.Net.WebRequest]::GetSystemWebProxy().GetProxy'
        '("https://graphql.4me.com")\n'
        f"Last error: {last_err}")


_gql._cached_proxy = None


def build_analytics_query(start_date: str, cursors: dict = None, done: set = None):
    """
    Completed tickets since start_date for each tracked team, paginated.
    Teams already fully paged (in `done`) are skipped so they don't get
    silently re-fetched from page 1 while others are still paging.
    Returns None when every team is done.
    """
    done  = done or set()
    parts = []
    for i, (name, tid) in enumerate(TEAM_IDS.items()):
        alias = f"a{i}"
        if alias in done:
            continue
        cursor = cursors.get(alias, "") if cursors else ""
        after  = f', after: "{cursor}"' if cursor else ""
        flt    = (f'updatedAt: {{ greaterThanOrEqualTo: "{start_date}T00:00:00Z" }}, '
                  f'status: {{ values: [completed] }}')
        parts.append(f"""
  {alias}: requests(first:100{after}, filter: {{ team: {{ values: ["{tid}"] }}, {flt} }},
    order: {{ field: updatedAt, direction: desc }}) {{
    nodes {{
      requestId subject status createdAt updatedAt completedAt
      resolutionDuration assignmentCount reopenCount
      member {{ name }}
      team {{ name }}
    }}
    pageInfo {{ hasNextPage endCursor }}
  }}""")
    if not parts:
        return None
    return "query Analytics {" + "".join(parts) + "\n}"


def build_reassignment_query(start_date: str, cursors: dict = None, done: set = None):
    """
    Pull completed requests per team since start_date WITH their audit trail,
    so we can count team→team reassignments. This is a heavier query (nested
    auditEntries), kept separate from the main analytics fetch.

    NOTE: the exact audit field path is not 100% verifiable without hitting
    the live schema. If the API rejects `auditEntries`/`changes`, the worker
    reports it as unavailable rather than faking numbers.
    """
    done  = done or set()
    parts = []
    for i, (name, tid) in enumerate(TEAM_IDS.items()):
        alias = f"r{i}"
        if alias in done:
            continue
        cursor = cursors.get(alias, "") if cursors else ""
        after  = f', after: "{cursor}"' if cursor else ""
        flt    = (f'updatedAt: {{ greaterThanOrEqualTo: "{start_date}T00:00:00Z" }}, '
                  f'status: {{ values: [completed] }}')
        parts.append(f"""
  {alias}: requests(first:50{after}, filter: {{ team: {{ values: ["{tid}"] }}, {flt} }},
    order: {{ field: updatedAt, direction: desc }}) {{
    nodes {{
      requestId
      team {{ name }}
      auditEntries(first: 25) {{
        nodes {{ createdAt changes }}
      }}
    }}
    pageInfo {{ hasNextPage endCursor }}
  }}""")
    if not parts:
        return None
    return "query Reassign {" + "".join(parts) + "\n}"


class ReassignmentWorker(QThread):
    """
    Counts team→team reassignments from request audit trails. Emits a matrix:
      { "POS Support": {"POS EFT": n}, "POS EFT": {"POS Support": m} }
    where n = tickets Support handed to EFT (Team changed FROM Support TO EFT).

    If the audit field path isn't supported by the instance, emits
    unavailable=True so the UI can say so honestly instead of showing zeros.
    """
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, token, account, start_date):
        super().__init__()
        self.token = token
        self.account = account
        self.start_date = start_date

    def run(self):
        try:
            query = build_reassignment_query(self.start_date)
            if query is None:
                self.done.emit({"unavailable": True,
                                "reason": "No teams configured.", "matrix": {}})
                return
            try:
                d = _gql(self.token, self.account, query)
            except Exception as e:
                # Surface EVERY failure with its real message so we can see
                # exactly why (bad scope, wrong field path, cost limit, etc.)
                # instead of a blank "unavailable".
                self.done.emit({"unavailable": True, "reason": str(e), "matrix": {}})
                return

            team_names = list(TEAM_IDS.keys())
            matrix = {a: {b: 0 for b in team_names if b != a} for a in team_names}
            audit_seen = False

            for i in range(len(TEAM_IDS)):
                bucket = d.get(f"r{i}", {})
                for node in bucket.get("nodes", []):
                    ae_nodes = (node.get("auditEntries") or {}).get("nodes", [])
                    if ae_nodes:
                        audit_seen = True
                    for ae in ae_nodes:
                        frm, to = _parse_team_change(ae.get("changes"))
                        if frm and to and frm in matrix and to in matrix.get(frm, {}):
                            matrix[frm][to] += 1

            # The query succeeded but returned no audit entries at all — likely
            # the field exists but is empty, OR the changes payload shape isn't
            # what we parse. Report it so we know to inspect a sample.
            self.done.emit({
                "unavailable": False,
                "matrix": matrix,
                "audit_seen": audit_seen,
                "debug_sample": _first_audit_sample(d),
            })
        except Exception as e:
            self.error.emit(str(e))


def _first_audit_sample(d):
    """Return the first raw audit entry found, so we can inspect the actual
    `changes` shape 4me returns for this instance."""
    try:
        for i in range(len(TEAM_IDS)):
            for node in d.get(f"r{i}", {}).get("nodes", []):
                aes = (node.get("auditEntries") or {}).get("nodes", [])
                if aes:
                    return aes[0]
    except Exception:
        pass
    return None


def _parse_team_change(changes):
    """
    Extract (from_team, to_team) from an audit entry's `changes` payload if it
    records a Team field change. The `changes` shape varies by instance/version
    (dict or JSON string); handle the common forms defensively. Returns
    (None, None) if this entry isn't a team change.
    """
    if not changes:
        return None, None
    data = changes
    if isinstance(changes, str):
        try:
            import json
            data = json.loads(changes)
        except Exception:
            # crude text fallback: "team changed from X to Y"
            low = changes.lower()
            if "team" in low and "from" in low and " to " in low:
                try:
                    seg = changes.split("from", 1)[1]
                    frm, to = seg.split(" to ", 1)
                    return frm.strip().strip('"').strip(), to.strip().strip('"').strip().rstrip(".")
                except Exception:
                    return None, None
            return None, None
    # dict form: look for a 'team' key with old/new
    try:
        for key in ("team", "Team", "team_id", "teamId"):
            if key in data:
                entry = data[key]
                if isinstance(entry, (list, tuple)) and len(entry) == 2:
                    return str(entry[0]), str(entry[1])
                if isinstance(entry, dict):
                    return (str(entry.get("old") or entry.get("from") or ""),
                            str(entry.get("new") or entry.get("to") or ""))
    except Exception:
        pass
    return None, None


class AnalyticsWorker(QThread):
    """
    Fetches all completed tickets since start_date across both teams,
    following pagination, then aggregates by team, agent, day, and
    per-team-per-agent. Emits a dict; never raises into the UI thread.
    """
    done  = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, token, account, start_date):
        super().__init__()
        self.token = token
        self.account = account
        self.start_date = start_date

    def run(self):
        try:
            all_nodes = []
            cursors   = {}
            done      = set()
            keys      = [f"a{i}" for i in range(len(TEAM_IDS))]

            while True:
                query = build_analytics_query(self.start_date, cursors, done)
                if query is None:
                    break
                d = _gql(self.token, self.account, query)
                for key in keys:
                    if key in done:
                        continue
                    bucket = d.get(key, {})
                    all_nodes.extend(bucket.get("nodes", []))
                    pi = bucket.get("pageInfo", {})
                    if pi.get("hasNextPage"):
                        cursors[key] = pi["endCursor"]
                    else:
                        cursors.pop(key, None)
                        done.add(key)
                if len(done) == len(keys):
                    break

            by_agent = defaultdict(int)
            by_team  = defaultdict(int)
            by_day   = defaultdict(int)
            team_agent = defaultdict(lambda: defaultdict(int))
            team_durations = defaultdict(list)
            team_day = defaultdict(lambda: defaultdict(int))
            # reassignment signal: tickets that bounced teams before landing
            team_reassigned = defaultdict(int)   # tickets w/ assignmentCount > 1
            team_reassign_total = defaultdict(int)  # sum of extra assignments
            team_reopened = defaultdict(int)

            for t in all_nodes:
                agent = (t.get("member") or {}).get("name", "Unassigned")
                team  = (t.get("team")   or {}).get("name", "Unknown")
                upd   = t.get("updatedAt") or ""
                crt   = t.get("createdAt") or ""
                day   = upd[:10]
                by_agent[agent] += 1
                by_team[team]   += 1
                team_agent[team][agent] += 1
                if day:
                    by_day[day] += 1
                    team_day[team][day] += 1

                # Speed: prefer 4me's own resolutionDuration (minutes) — it's
                # the real work-time metric. Fall back to created→updated only
                # if the field is missing.
                rd = t.get("resolutionDuration")
                if isinstance(rd, (int, float)) and rd >= 0:
                    team_durations[team].append(rd / 60.0)   # minutes → hours
                else:
                    dur = _hours_between(crt, upd)
                    if dur is not None and dur >= 0:
                        team_durations[team].append(dur)

                # Reassignments: assignmentCount = times the Team field was set.
                # >1 means the ticket was moved between teams before finishing
                # here — i.e. this team absorbed a reassigned ticket.
                ac = t.get("assignmentCount")
                if isinstance(ac, int) and ac > 1:
                    team_reassigned[team] += 1
                    team_reassign_total[team] += (ac - 1)

                rc = t.get("reopenCount")
                if isinstance(rc, int) and rc > 0:
                    team_reopened[team] += 1

            # ── derived team metrics ────────────────────────────────
            metrics = {}
            for team in TEAM_IDS:
                total   = by_team.get(team, 0)
                agents  = team_agent.get(team, {})
                active  = len([a for a, c in agents.items() if c > 0])
                durs    = team_durations.get(team, [])
                days    = team_day.get(team, {})

                med_hours = _median(durs) if durs else None
                avg_hours = (sum(durs) / len(durs)) if durs else None
                per_agent = (total / active) if active else 0.0
                steadiness = _steadiness(list(days.values()))
                balance = _balance(list(agents.values()))

                metrics[team] = {
                    "total":         total,
                    "active":        active,
                    "med_hours":     med_hours,
                    "avg_hours":     avg_hours,
                    "per_agent":     per_agent,
                    "steadiness":    steadiness,
                    "balance":       balance,
                    "resolved_ct":   len(durs),
                    "reassigned_in": team_reassigned.get(team, 0),
                    "reassign_moves": team_reassign_total.get(team, 0),
                    "reopened":      team_reopened.get(team, 0),
                }

            self.done.emit({
                "total":      len(all_nodes),
                "by_agent":   dict(by_agent),
                "by_team":    dict(by_team),
                "by_day":     dict(by_day),
                "team_agent": {k: dict(v) for k, v in team_agent.items()},
                "metrics":    metrics,
                "raw":        all_nodes,
            })
        except Exception as e:
            self.error.emit(str(e))
