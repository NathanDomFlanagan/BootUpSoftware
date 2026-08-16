# App Launcher

A lightweight Windows desktop app for launching groups of programs with a single click — built with Python and [ttkbootstrap](https://ttkbootstrap.readthedocs.io/).

Instead of manually opening five apps every time you sit down to game, code, or study, you organize them into **categories** (e.g. "Gaming", "Programming") and optionally combine categories into **profiles** (e.g. a "School" profile that launches your Programming *and* Default apps together).

## Features

- **Categories** — group apps/shortcuts under a named category, and launch all of them at once
- **Profiles** — combine multiple categories into a single one-click launch (e.g. "Gaming Session" = Gaming + Default), with duplicate apps automatically de-duplicated
- **Add/remove apps** — pick any `.exe` or `.lnk` file via a native file picker
- **Rename / delete categories and profiles**
- **Undo** — restore the last app you removed from a category
- **Trash view** — see everything you've removed this session and restore any of them
- **Hover tooltips** — hover over an app in the list to see its full file path
- **Dark theme UI** via ttkbootstrap

## Requirements

- Python 3.9+
- Windows (uses `os.startfile()` to launch `.exe`/`.lnk` files; falls back to `subprocess.Popen` on other platforms, though the file picker and shortcut handling are Windows-oriented)
- [`ttkbootstrap`](https://pypi.org/project/ttkbootstrap/)

```bash
pip install ttkbootstrap
```

## Running it

```bash
python main.py
```

On first run, if no `config.json` exists next to the script, one is created automatically with a single empty `Default` category.

## Project structure

| File | Purpose |
|---|---|
| `main.py` | Entry point — creates the UI window and starts the Tkinter event loop |
| `ui.py` | All UI logic: category/profile selectors, the app list (Treeview), buttons, dialogs |
| `config.py` | `Config` class — loads/saves `config.json`, and all category/profile CRUD operations |
| `launcher.py` | `AppLauncher` class — actually launches apps via `os.startfile()`, with error handling |
| `tooltip.py` | Small reusable `ToolTip` widget used for showing full file paths on hover |
| `config.json` | Your saved categories, apps, and profiles — created automatically, safe to back up |

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

## Notes / known limitations

- The Trash/Undo history is **in-memory only** — it resets when you close the app. Removed apps are gone from `config.json` immediately (that part is permanent across restarts), but the *undo/trash UI* for viewing what was removed only lasts for the current session.
- Category names are **case-sensitive** — `"Gaming"` and `"gaming"` can exist as two separate categories.
- Have to know the location of an application you **want** to add to a category.
