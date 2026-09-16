# App Launcher

A lightweight Windows desktop app for launching groups of programs with a single click — built with Python and [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter).

Instead of manually opening five apps every time you sit down to game, code, or study, you organize them into **categories** (e.g. "Gaming", "Programming") and optionally combine categories into **profiles** (e.g. a "School" profile that launches your Programming *and* Default apps together).

## Download

Grab the latest pre-built Windows release from the [Releases page](https://github.com/NathanDomFlanagan/BootUpSoftware/releases) — download the `.zip`, extract it, and run `AppLauncher.exe` (keep it next to its `_internal/` folder). No Python installation required.

To run from source instead, see [Requirements](#requirements) and [Running it](#running-it) below.

## Features

- **Categories** — group apps/shortcuts under a named category, and launch all of them at once
- **Profiles** — combine multiple categories into a single one-click launch (e.g. "Gaming Session" = Gaming + Default), with duplicate apps automatically de-duplicated
- **Add apps from three sources** — a searchable, refreshable scan of Start Menu + Desktop shortcuts, installed UWP/Microsoft Store apps, or browse for any `.exe`/`.lnk` file manually
- **Edit App** — change an app's display name, launch arguments, and working directory after adding it (e.g. turning a browser shortcut into a specific web-app launch with `--app=...`)
- **Rename / delete categories and profiles**
- **Undo** — restore the last app you removed from a category
- **Trash view** — see everything you've removed this session and restore any of them
- **Hover tooltips** — hover over an app in the list to see its full file path
- **System tray** — closing the window minimizes to the tray instead of quitting; the tray icon adapts to your Windows light/dark taskbar theme
- **Global hotkey** — bring the window back from anywhere with a configurable shortcut (default `ctrl+alt+l`)
- **Settings window** — a tabbed panel (menu bar → **Settings...**) for the global shortcut, Run at Startup, Start Minimized, Startup Profile, and config export/import
- **Run at Startup** — launches automatically at login via a registry entry (`HKCU\...\CurrentVersion\Run`), with automatic detection and one-click repair if the entry goes stale (e.g. after moving the project folder)
- **Startup Profile** — automatically launch a chosen profile's apps when the app starts at login (not on a manual open), so your usual set of apps is running by the time you sit down
- **Export / Import config** — back up or share your categories and profiles as a standalone JSON file
- **View Log** — open the app's log file directly from the menu bar (**File → View Log...**) for diagnosing a silent failure, without needing to know the file exists or where it lives
- **Light / Dark mode** — toggle in **Settings...**, switches the whole app's appearance live with no restart needed, and is remembered across sessions

## Requirements

- Python 3.9+
- Windows (uses `os.startfile()` to launch `.exe`/`.lnk` files; falls back to `subprocess.Popen` on other platforms, though the tray icon, global hotkey, Start Menu/Desktop scan, and Run at Startup are Windows-only features)
- See [`requirements.txt`](requirements.txt):

```bash
pip install -r requirements.txt
```

`pywin32` is optional but recommended — without it, the app picker falls back to manual file browsing, and Run at Startup is unaffected (it only needs the standard-library `winreg` module).

## Running it

```bash
python main.py
```

Pass `--startup` to launch minimized straight to the tray (this is what the Run at Startup registry entry uses automatically — you shouldn't need to pass it by hand).

On first run, if no `config.json` exists next to the script, one is created automatically with a single empty `Default` category.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — parses `--startup`, sets up logging, creates the UI window and starts the Tkinter event loop |
| `ui.py` | Main window UI logic: category/profile selectors, the app list (Treeview), buttons, tray/hotkey lifecycle |
| `app_picker.py` | The "Add App" window — searchable list combining Start Menu/Desktop shortcuts and UWP/Store apps, scanned on a background thread |
| `edit_app_dialog.py` | The "Edit App" window — change an app's name, path, arguments, and working directory |
| `edit_profile_dialog.py` | The "Edit Profile" window — scrollable category checklist for a profile |
| `trash_window.py` | The Trash window — view and restore apps removed this session |
| `settings_window.py` | Tabbed Settings window — global shortcut, Run at Startup, Start Minimized, Startup Profile, config export/import |
| `config.py` | `Config` class — loads/saves `config.json`, and all category/profile CRUD operations |
| `launcher.py` | `AppLauncher` class — launches apps via `os.startfile()` (or `subprocess` when arguments/working directory are set), with error handling |
| `tray.py` | `TrayIcon` — system tray icon and menu (pystray), theme-adaptive |
| `hotkey.py` | `HotkeyManager` — registers the global show-window shortcut (`keyboard`) |
| `startup.py` | `StartupManager` — Run at Startup via the `HKCU\...\Run` registry key |
| `appscan.py` | Scans the Start Menu + Desktop for installed apps (requires `pywin32`) and UWP/Store apps (via PowerShell's `Get-StartApps`, no extra dependency) |
| `paths.py` | Shared helper for resolving paths whether running from source or frozen as a PyInstaller exe |
| `applog.py` | Centralized rotating-file logging setup, including uncaught-exception handlers |
| `tooltip.py` | Small reusable `ToolTip` widget used for showing full file paths on hover |
| `ctk_theme.py` | Shared CustomTkinter theming — colors, corner radius, spacing scale, fonts, and the light/dark mode machinery |
| `ctk_widgets.py` | Themed button/entry/label/etc. subclasses with the app's styling baked in, so it isn't repeated at every call site |
| `ctk_dialogs.py` | CTk-styled replacements for `tkinter.messagebox`/`simpledialog`, so confirmation/error/input popups match the rest of the app instead of looking like plain OS dialogs |
| `safe_call.py` | Small shared helper for safely running a background-thread callback without an unhandled exception silently killing that thread |
| `config.json` | Your saved categories, apps, and profiles — created automatically, safe to back up |
| `tests/` | Pytest suite covering `config.py`, `appscan.py`, `startup.py`, `launcher.py`, and the undo/trash/import fixes in `ui.py` |

## How the data is stored

`config.json` looks like this:

```json
{
    "schema_version": 2,
    "categories": {
        "Default": [
            {"path": "C:/path/to/discord.lnk", "name": "Discord", "args": "", "working_dir": "", "type": "path"},
            {"path": "C:/path/to/brave.exe", "name": "Brave", "args": "", "working_dir": "", "type": "path"}
        ],
        "Gaming": [
            {"path": "C:/path/to/steam.exe", "name": "Steam", "args": "", "working_dir": "", "type": "path"}
        ],
        "Programming": [
            {"path": "shell:AppsFolder\\Microsoft.VisualStudioCode_xxx!App", "name": "VS Code", "args": "", "working_dir": "", "type": "uwp"}
        ]
    },
    "profiles": {
        "School": ["Default", "Programming"],
        "Gaming Session": ["Gaming", "Default"]
    },
    "settings": {
        "hotkey": "ctrl+alt+l",
        "start_minimized": true,
        "autostart_profile": "",
        "dark_mode": true
    }
}
```

- **`schema_version`** — bumped whenever this on-disk shape changes, so an older file can be upgraded with a direct version check instead of guessing its age from what's present or absent. Missing entirely just means the file predates this field.
- **`categories`** — each key is a category name, each value is a list of app entries in that category. Each entry has a `path` (a normal file path for a `.exe`/`.lnk`, or a `shell:AppsFolder\...` pseudo-path identifying a UWP/Store app), a display `name`, a `type` (`"path"` or `"uwp"`, matching which kind of `path` it is), and optional `args`/`working_dir` (set via **Edit App**).
- **`profiles`** — each key is a profile name, each value is a list of *category names* to launch together. Running a profile flattens every app across those categories into one de-duplicated launch list.
- **`settings`** — machine-specific preferences: the global hotkey, whether startup launches go straight to the tray, which profile (if any) auto-launches at login, and whether the UI is in dark or light mode.

If you have an older `config.json` from a previous version (the original flat format with no `categories` wrapper, one where each app was a bare path string instead of the object shown above, or one predating the `type`/`schema_version` fields), it's automatically detected and migrated to the current format the first time you run the app — no manual conversion needed.

## Using categories and profiles

**Categories:**
1. Click **New** next to the Category dropdown, name it
2. Select it, click **Add App** — pick from the searchable list (Start Menu/Desktop shortcuts and installed UWP/Store apps) or use **Browse Manually...** for anything not listed
3. Click **Run All** to launch everything in that category, or select one app and click **Run Selected**
4. Select an app and click **Edit App** (or double-click it) to rename it, or set launch arguments/a working directory — useful for e.g. turning a browser shortcut into a specific web-app launch

**Profiles:**
1. Click **New** next to the Profile dropdown, name it — this opens the category picker automatically
2. Check the categories you want included, click **Save**
3. Select the profile and click **Run Profile** to launch every app across all its categories at once

Use **Edit** on an existing profile any time to change which categories it includes.

## Settings

Open **Settings...** from the menu bar for:

- **General tab** — toggle **Dark Mode** for the whole app's appearance (applies immediately, remembered next time you open it); change the global shortcut that brings the window back from the tray; toggle **Run at Startup** (adds/removes a `HKCU\...\CurrentVersion\Run` registry entry, no admin rights needed); toggle **Start Minimized** for whether startup launches should skip straight to the tray; pick a **Startup Profile** to auto-launch its apps when the app starts at login (not on a manual open). If the startup entry goes stale — e.g. you moved or re-cloned the project folder — a **Repair Startup Entry** button appears automatically.
- **Backup tab** — export your categories/profiles to a JSON file, or import one (with merge/replace/skip choices per category on conflict).

## Notes / known limitations

- The Trash/Undo history is **in-memory only** — it resets when you close the app. Removed apps are gone from `config.json` immediately (that part is permanent across restarts), but the *undo/trash UI* for viewing what was removed only lasts for the current session.
- Category names are **case-insensitive** for uniqueness — `"Gaming"` and `"gaming"` can't both exist as separate categories (the typed casing is preserved, just not duplicated).
- Only one level of undo is kept — removing a second app before undoing the first discards the ability to undo the first one.
