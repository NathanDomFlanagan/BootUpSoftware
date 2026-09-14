# Backup: before UWP + per-app arguments migration

Snapshot of the launcher files as they were **before** the migration that
changes each category's app list from a flat list of path strings to a list
of `{"path", "name", "args", "working_dir"}` objects (needed to support both
UWP/Store apps and launching with command-line arguments).

## Files backed up

- `launcher/config.py`
- `launcher/ui.py`
- `launcher/launcher.py`
- `launcher/appscan.py`
- `launcher/tests/test_config.py`
- `launcher/tests/test_ui_logic.py`
- `launcher/tests/test_appscan.py`

## How to revert

If you decide you don't want the migration, copy each file here back over
its counterpart in `launcher/`, e.g. from the repo root:

```
cp backup/pre_uwp_args_migration/launcher/config.py launcher/config.py
cp backup/pre_uwp_args_migration/launcher/ui.py launcher/ui.py
cp backup/pre_uwp_args_migration/launcher/launcher.py launcher/launcher.py
cp backup/pre_uwp_args_migration/launcher/appscan.py launcher/appscan.py
cp backup/pre_uwp_args_migration/launcher/tests/test_config.py launcher/tests/test_config.py
cp backup/pre_uwp_args_migration/launcher/tests/test_ui_logic.py launcher/tests/test_ui_logic.py
cp backup/pre_uwp_args_migration/launcher/tests/test_appscan.py launcher/tests/test_appscan.py
```

Note: your actual `launcher/config.json` (your real categories/profiles/apps)
is **not** touched by this backup — the migration includes a one-time,
backward-compatible format upgrade that runs automatically the first time
the app loads an old-format config, so nothing you'd need to manually
restore there. If something goes wrong with that upgrade specifically, your
original `config.json` content is still recoverable from git history
(`git diff`/`git log -- launcher/config.json`).
