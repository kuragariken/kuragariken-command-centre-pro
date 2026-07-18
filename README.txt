============================================================
  COMMAND CENTRE PRO v10
  Support Engineer Toolkit
============================================================

WHAT IS THIS?
-------------
Command Centre Pro is a compact desktop tool for support
engineers. It lets you copy pre-written commands to your
clipboard instantly, track tickets, log your shift, store
encrypted credentials in a vault, set reminders, and more.

Everything lives in one small window that stays out of
your way until you need it.


FIRST LAUNCH
------------
1. Double-click CommandCentrePro.exe to start.
2. The app will create its data folder automatically at:

     C:\Users\<YourName>\AppData\Roaming\Command Centre Pro\

   This folder holds your config and is NEVER deleted by
   updates. Your data is always safe here.

3. The app starts blank. Either:
   - Click + Category to create your first category, then
     + Add Command to add buttons, OR
   - Go to Settings → Import from Old AHK GUI to import
     your existing commands from a JSON export file.


HOW TO USE IT
-------------

BRING IT FORWARD
  Press Alt + C at any time — even if the app is minimised
  or hidden — to bring it instantly to the front.

COPY A COMMAND
  Click any button to copy it to your clipboard instantly.
  If auto-paste is on, it will also paste into whatever
  you had open.

CATEGORIES
  Use the pills at the top to switch between your command
  categories. Click + Category to add a new one.

SEARCH
  Type in the search bar to filter commands across all
  categories in real time.

NAV MENU (COMMANDS ▾)
  Click the COMMANDS button in the title bar to open the
  nav dropdown. From here you can reach:
    · Analytics    — see your copy stats and usage heatmap
    · Reminders    — set one-off or recurring reminders
    · Macros       — automate multi-step sequences
    · History      — recent clipboard entries
    · Notepad      — floating multi-tab notes window
    · Tickets      — quick ticket logger + shift timer
    · Vault        — encrypted credential storage
    · Settings     — themes, hotstrings, import/export
    · Quick Launch — floating always-on-top shortcut bar


VAULT
-----
The Vault is a pop-out window for storing passwords and
secrets. It is protected by a master password using
PBKDF2-SHA256 (390,000 iterations) + AES-128 encryption.

YOUR MASTER PASSWORD IS NEVER STORED. If you forget it,
your vault entries cannot be recovered. Write it down and
keep it somewhere safe.

The vault auto-locks after 5 minutes of inactivity.


SETTINGS
--------
Click COMMANDS ▾ → Settings to open the settings panel.
From there you can:
  · Change the colour theme (11 themes available)
  · Toggle start with Windows
  · Set Pomodoro timer durations
  · Add hotstrings (shortcuts that expand to full text)
  · Import / Export / Backup your data
  · Open your data folder directly


THEMES
------
11 built-in themes:
  Default · Cyberpunk · Neon · Stealth · Ocean · Ember
  Solarized · Matrix · Vapor · Blood Moon · Arctic


YOUR DATA
---------
All data is stored in:
  %APPDATA%\Command Centre Pro\CommandCentre.json

Backups are saved automatically in:
  %APPDATA%\Command Centre Pro\CommandCentre_Backups\

Up to 5 rolling backups are kept. You can also trigger a
manual backup from Settings → Backup Now.


KEYBOARD SHORTCUTS
------------------
  Alt + C          Bring app to front (works always)
  Alt + V          Toggle auto-paste on/off
  Alt + Q          Open / close Quick Launch bar
  Alt + T          Start / stop Pomodoro timer
  Enter (on field) Submit forms (password, search, etc.)


WINDOW CONTROLS
---------------
  Yellow dot  Toggle always-on-top
  Green dot   Minimise to taskbar
  Red dot     Hide to system tray

The app lives in your system tray when closed. Right-click
the tray icon to show, hide, or exit completely.


UPDATING
--------
See UPDATE.bat and ADMIN_UPDATE_GUIDE.txt for instructions.
Your data is NEVER affected by updates.


TROUBLESHOOTING
---------------
App won't start?
  → Check crash.log next to the exe for the error message.

Hotkey not working?
  → Another app may have claimed that key combination.
    The app will try fallback combos automatically.

Data seems wrong after update?
  → Restore a backup from Settings → your data folder.
    Backups are timestamped and listed automatically.

Vault says wrong password?
  → The master password is never stored. There is no reset.
    If forgotten, use Settings → Data → Reset to start over
    (this clears vault entries only, not your commands).

============================================================
  Built with PyQt6 · Python 3 · Encrypted with cryptography
  © Command Centre Pro v10
============================================================
