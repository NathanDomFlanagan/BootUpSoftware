# Backlog

Code quality / refactoring items for `launcher/`, in priority order.

## Done

- [x] Fix undo/trash desync — deleting an app, undoing it, then restoring the
      same item from Trash could create a duplicate entry. (`ui.py`)
- [x] Fix trash-restore duplicate-path bug — restoring from Trash didn't
      check whether the path was already back in the category. (`ui.py`)
- [x] Fix case-insensitive category collision on import — importing a
      category like `"Default"` could create a second category alongside an
      existing `"default"` instead of merging into it. (`ui.py`)
- [x] Extract shared frozen/dev path-resolution logic (previously duplicated
      across `config.py`, `applog.py`, and `startup.py`) into `paths.py`.
- [x] Replace the Startup-folder `.lnk` shortcut with a registry Run-key
      entry (`startup.py`), dropping the `pywin32` dependency for this
      feature, and add a proper tabbed Settings window (`settings_window.py`)
      in place of the old menu checkbuttons.

## To do, priority order

1. **Add CI to run the test suite** — 45 tests exist (`launcher/tests/`) but
   nothing runs them automatically. Add a GitHub Actions workflow that runs
   `pytest` on push/PR so regressions get caught before merge.
2. **Pin dependency versions** (`requirements.txt`) — `ttkbootstrap`,
   `keyboard`, `pystray`, `pillow`, `pywin32` currently have no version
   bounds, risking a silent break from an upstream major bump.
3. **Split `ui.py`** — `LauncherUI` is a single ~870-line class handling
   widget construction, category CRUD, profile CRUD, trash/undo, and
   import/export/startup/tray/hotkey wiring. Split into focused modules
   (e.g. `ui/main_window.py`, `ui/categories.py`, `ui/profiles.py`,
   `ui/dialogs.py`) once it grows further or becomes hard to navigate.
4. **Turn `launcher/` into a proper installable package** — currently a flat
   script directory using bare imports (`from applog import ...`) and
   `sys.path.insert(0, ...)` hacks in tests. Add `pyproject.toml`,
   `launcher/__init__.py`, and switch to absolute imports
   (`from launcher.applog import ...`).
5. **Fill in type hints** — `config.py` has partial coverage; `ui.py` and
   `tray.py` have almost none. Would let a type checker catch bugs like the
   case-insensitivity issue above before they ship.
