<<<<<<< HEAD
# Upgrade Command Centre

A new Command Centre Pro module that replaces the manual `UPGRADES_REPORT` Excel
workbook with a single live, shareable dataset.

## What it does

- **Dashboard** — total tills, upgraded/failed/pending counts, overall % complete,
  a status-breakdown donut, a pre/post-cutover failure breakdown, and a
  worst-first ranked progress bar per store (the stores that need attention
  float to the top automatically).
- **Stores** — searchable/filterable list of every store with a progress bar
  and status pills. Click into a store to see every till, and change its
  status (Pending / Upgraded / Failed + Pre/Post-cutover) with a couple of
  clicks — saved instantly.
- **Import** — paste a raw SSH cache-health CSV dump (same format you're
  already pulling per store) and it adds new tills as Pending and refreshes
  existing ones in place, without duplicating anything. There's also a
  one-off "Import legacy Excel workbook" button for pulling in an old-style
  `UPGRADES_REPORT` file if one shows up again later.
- **Share** — one click to copy a clean plain-text progress report to the
  clipboard (ready for Teams/Slack/email), one click to save the dashboard as
  a PNG, and one click to re-export everything back into the original
  SUMMARY + per-store Excel layout if the team still wants a workbook.

## Your existing data

Your uploaded workbook (`UPGRADES_REPORT_COMMAND_CENTER`) and the new-stores
text file have already been migrated into `seed_data.json`, sitting next to
`upgrade_tracker.py`. **24 stores, 468 tills** — the 19 stores that already had
tracked upgrade sheets, plus the 5 new stores from the text file
(GC48, GF54, GH01, KC09, NC30) seeded as Pending.

The first time you run the app on a machine with no `UpgradeTracker.json` yet,
it'll ask if you want to import that seed data. Say yes once and you're set —
after that it's just your live dataset.

One data-quality note from the migration: the `EC12` sheet in your old
workbook had its status column headed `UPGRADED STATUS` instead of
`UPGRADE STATUS` (rest of the sheets are consistent) — the importer handles
both, but worth knowing if you ever hand-edit that sheet again.

## Data storage

`%APPDATA%\Command Centre Pro\UpgradeTracker.json` on Windows (falls back to
`~/.command_centre_pro/UpgradeTracker.json` elsewhere) — same folder
convention as CCP's own `CommandCentre.json`.

## Wiring it into Command Centre Pro

```python
from upgrade_tracker import UpgradeTrackerWindow

class CommandCentrePro(QMainWindow):
    def _open_upgrade_tracker(self):
        if not hasattr(self, "_upgrade_win") or self._upgrade_win is None:
            self._upgrade_win = UpgradeTrackerWindow()
        self._upgrade_win.show_fullscreen()
```

Wire `_open_upgrade_tracker` to a new HoverCard button the same way
Vault/Notepad/Settings are launched today. The window is fully self-contained
(own data file, own aurora/glass styling matching CCP) — it doesn't need
anything else from the host app. Requires `openpyxl` (already a CCP
dependency) for the Excel import/export features.

## Standalone

```
python upgrade_tracker.py
```

Opens maximized. Esc un-maximizes; the ✕ in the custom title bar closes it.
=======
# kuragariken-command-centre-pro
>>>>>>> a90484f3dc4306323cd6a47d2765d354bee5b3fd
