# App Launcher

A lightweight Windows desktop app for launching groups of programs with a single click — built with Python and [ttkbootstrap](https://ttkbootstrap.readthedocs.io/).

Instead of manually opening five apps every time you sit down to game, code, or study, you organize them into **categories** (e.g. "Gaming", "Programming") and optionally combine categories into **profiles** (e.g. a "School" profile that launches your Programming *and* Default apps together).

## Features

- **Categories** — group apps/shortcuts under a named category, and launch all of them at once
- **Profiles** — combine multiple categories into a single one-click launch (e.g. "Gaming Session" = Gaming + Default), with duplicate apps automatically de-duplicated
- **Add/remove apps** — pick from a searchable, refreshable Start Menu + Desktop scan, or browse for any `.exe`/`.lnk` file manually
- **Rename / delete categories and profiles**
- **Undo** — restore the last app you removed from a category
- **Trash view** — see everything you've removed this session and restore any of them
- **Hover tooltips** — hover over an app in the list to see its full file path
- **System tray** — closing the window minimizes to the tray instead of quitting; the tray icon adapts to your Windows light/dark taskbar theme
- **Global hotkey** — bring the window back from anywhere with a configurable shortcut (default `ctrl+alt+l`)
- **Settings window** — a tabbed panel (menu bar → **Settings...**) for the global shortcut, Run at Startup, Start Minimized, and config export/import
- **Run at Startup** — launches automatically at login via a registry entry (`HKCU\...\CurrentVersion\Run`), with automatic detection and one-click repair if the entry goes stale (e.g. after moving the project folder)
- **Export / Import config** — back up or share your categories and profiles as a standalone JSON file
- **Dark theme UI** via ttkbootstrap

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
| `ui.py` | Main window UI logic: category/profile selectors, the app list (Treeview), buttons, dialogs, tray/hotkey lifecycle |
| `settings_window.py` | Tabbed Settings window — global shortcut, Run at Startup, Start Minimized, config export/import |
| `config.py` | `Config` class — loads/saves `config.json`, and all category/profile CRUD operations |
| `launcher.py` | `AppLauncher` class — actually launches apps via `os.startfile()`, with error handling |
| `tray.py` | `TrayIcon` — system tray icon and menu (pystray), theme-adaptive |
| `hotkey.py` | `HotkeyManager` — registers the global show-window shortcut (`keyboard`) |
| `startup.py` | `StartupManager` — Run at Startup via the `HKCU\...\Run` registry key |
| `appscan.py` | Scans the Start Menu + Desktop for installed apps to populate the Add App picker (requires `pywin32`) |
| `paths.py` | Shared helper for resolving paths whether running from source or frozen as a PyInstaller exe |
| `applog.py` | Centralized rotating-file logging setup, including uncaught-exception handlers |
| `tooltip.py` | Small reusable `ToolTip` widget used for showing full file paths on hover |
| `config.json` | Your saved categories, apps, and profiles — created automatically, safe to back up |
| `tests/` | Pytest suite covering `config.py`, `appscan.py`, `startup.py`, and the undo/trash/import fixes in `ui.py` |

## How the data is stored

`config.json` looks like this:

```json
{
    "categories": {
        "Default": ["C:/path/to/discord.lnk", "C:/path/to/brave.exe"],
        "Gaming": ["C:/path/to/steam.exe"],
        "Programming": ["C:/path/to/vscode.exe"]
    },
    "profiles": {
        "School": ["Default", "Programming"],
        "Gaming Session": ["Gaming", "Default"]
    }
}
```

- **`categories`** — each key is a category name, each value is a list of file paths (apps or shortcuts) in that category.
- **`profiles`** — each key is a profile name, each value is a list of *category names* to launch together. Running a profile flattens every app across those categories into one de-duplicated launch list.

If you have an older `config.json` from a previous version (a flat format without the `categories` wrapper), it's automatically detected and migrated to the current format the first time you run the app — no manual conversion needed.

## Using categories and profiles

**Categories:**
1. Click **New** next to the Category dropdown, name it
2. Select it, click **Add App**, pick an `.exe` or `.lnk`
3. Click **Run All** to launch everything in that category, or select one app and click **Run Selected**

**Profiles:**
1. Click **New** next to the Profile dropdown, name it — this opens the category picker automatically
2. Check the categories you want included, click **Save**
3. Select the profile and click **Run Profile** to launch every app across all its categories at once

Use **Edit** on an existing profile any time to change which categories it includes.

## Settings

Open **Settings...** from the menu bar for:

- **General tab** — change the global shortcut that brings the window back from the tray; toggle **Run at Startup** (adds/removes a `HKCU\...\CurrentVersion\Run` registry entry, no admin rights needed); toggle **Start Minimized** for whether startup launches should skip straight to the tray. If the startup entry goes stale — e.g. you moved or re-cloned the project folder — a **Repair Startup Entry** button appears automatically.
- **Backup tab** — export your categories/profiles to a JSON file, or import one (with merge/replace/skip choices per category on conflict).

## Notes / known limitations

- The Trash/Undo history is **in-memory only** — it resets when you close the app. Removed apps are gone from `config.json` immediately (that part is permanent across restarts), but the *undo/trash UI* for viewing what was removed only lasts for the current session.
- Category names are **case-insensitive** for uniqueness — `"Gaming"` and `"gaming"` can't both exist as separate categories (the typed casing is preserved, just not duplicated).
- Only one level of undo is kept — removing a second app before undoing the first discards the ability to undo the first one.
