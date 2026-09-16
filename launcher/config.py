import json
import logging
import shutil
from pathlib import Path

from paths import app_dir, bundled_dir, is_frozen

log = logging.getLogger(__name__)

CONFIG_NAME = "config.json"

# Bumped whenever the on-disk shape changes. A file with no "schema_version"
# key at all predates this field existing (version 1, implicitly) — every
# real config.json this app has ever written falls in that bucket today.
# Going forward, load() upgrades step by step (`if version < N`) rather than
# guessing a file's age from what's structurally present or absent, which is
# how the two migrations below this constant still have to work, since they
# predate there being a version number to check at all.
CURRENT_SCHEMA_VERSION = 2


def _is_default_category(name: str) -> bool:
    return name.strip().lower() == "default"


def _entry_type(path: str) -> str:
    """"uwp" for a shell:AppsFolder\\<AUMID> pseudo-path (identifies a
    UWP/Store app), "path" for a normal filesystem path/shortcut. Computed
    once here and stored on the entry as "type", rather than every caller
    that cares (launcher.py, edit_app_dialog.py) independently re-deriving
    it from the path string — one place decides, everywhere else reads."""
    return "uwp" if path.lower().startswith("shell:") else "path"


def _build_entry(path: str, name: str = None, args: str = "", working_dir: str = "") -> dict:
    """Builds the current {"path", "name", "args", "working_dir", "type"}
    app-entry shape — the one place this shape is assembled, shared by
    every mutator that creates or overwrites an entry from explicit field
    values."""
    return {
        "path": path,
        "name": name or Path(path).name,
        "args": args,
        "working_dir": working_dir,
        "type": _entry_type(path),
    }


def normalize_app_entry(entry) -> dict:
    """Coerces an app entry into the current {"path", "name", "args",
    "working_dir", "type"} shape. Accepts either that dict shape (from a
    current config or export) or a bare path string (from an older
    config/export, predating per-app names/arguments) — the plain-string
    case derives its display name from the path's filename, same as the
    old behavior. "type" is always (re)computed from "path" rather than
    trusted from the input, since it's cheap and always correct — a
    shell:AppsFolder path is never anything but a UWP app."""
    if isinstance(entry, str):
        return _build_entry(entry)
    return _build_entry(
        entry.get("path", ""),
        entry.get("name"),
        entry.get("args", ""),
        entry.get("working_dir", ""),
    )


def _resolve_config_path() -> Path:
    if is_frozen():
        external = app_dir(__file__) / CONFIG_NAME
        if not external.exists():
            bundled = bundled_dir() / CONFIG_NAME
            if bundled.exists():
                shutil.copy(bundled, external)
        return external
    return app_dir(__file__) / CONFIG_NAME


CONFIG_PATH = _resolve_config_path()

DEFAULT_HOTKEY = "ctrl+alt+l"


class Config:
    def __init__(self):
        self.path = CONFIG_PATH
        self.data = {
            "categories": {},
            "profiles": {}
        }
        self.load()

    def load(self):
        if not self.path.exists():
            # Initialize with a default category
            self.data = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "categories": {"default": []},
                "profiles": {}
            }
            self.save()
            return

        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            # Corrupt or unreadable config.json would otherwise crash the app
            # on every startup with no way to recover without manual file
            # surgery. Back up the bad file and fall back to defaults instead
            # — a background app should degrade gracefully, not refuse to start.
            log.exception("Failed to read %s — falling back to a fresh default config", self.path)
            try:
                backup_path = self.path.with_suffix(".json.bak")
                shutil.copy(self.path, backup_path)
                log.info("Backed up unreadable config to %s", backup_path)
            except OSError:
                log.exception("Could not back up unreadable config file")
            self.data = {
                "schema_version": CURRENT_SCHEMA_VERSION,
                "categories": {"default": []},
                "profiles": {}
            }
            self.save()
            return

        # Backward compatibility: old format was { "default": [...], "gaming": [...], "profiles": {...} }
        if "categories" not in raw:
            profiles = raw.get("profiles") if isinstance(raw.get("profiles"), dict) else {}
            self.data["categories"] = {
                k: v for k, v in raw.items()
                if k != "profiles" and isinstance(v, list)
            }
            self.data["profiles"] = profiles
            needs_save = True
        else:
            self.data = raw
            self.data.setdefault("profiles", {})
            needs_save = False

        # Backward compatibility: app entries used to be plain path strings
        # rather than {"path", "name", "args", "working_dir"} dicts (added
        # to support UWP/Store apps and per-app launch arguments). Normalize
        # in place so the rest of the app never has to handle both shapes.
        for cat, apps in self.categories.items():
            if any(isinstance(e, str) for e in apps):
                self.categories[cat] = [normalize_app_entry(e) for e in apps]
                needs_save = True

        # From here on, format changes are tracked by an explicit version
        # number instead of guessing a file's age from its shape (the two
        # migrations above predate this field existing, so they're the last
        # ones that have to guess). Each `if version < N` step only needs to
        # know its own upgrade, never re-examine the whole file.
        version = self.data.get("schema_version", 1)
        if version < 2:
            # Version 2 added an explicit "type" ("path" or "uwp") to every
            # app entry — see _entry_type()'s docstring for why. Entries
            # normalized above already have it; this backfills entries that
            # were already in the current dict shape and so skipped that step.
            for apps in self.categories.values():
                for entry in apps:
                    entry.setdefault("type", _entry_type(entry.get("path", "")))
            version = 2
            needs_save = True
        self.data["schema_version"] = version

        if needs_save:
            self.save()

    def save(self):
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
        except OSError:
            # Disk full, permissions issue, file locked by another process, etc.
            # Log it rather than crash — the in-memory state is still valid
            # for the rest of this session even if it couldn't be persisted.
            log.exception("Failed to save %s", self.path)

    @property
    def categories(self):
        return self.data.setdefault("categories", {})

    @property
    def profiles(self):
        return self.data.setdefault("profiles", {})

    @property
    def settings(self):
        return self.data.setdefault("settings", {})

    def get_hotkey(self) -> str:
        return self.settings.get("hotkey", DEFAULT_HOTKEY)

    def set_hotkey(self, combo: str) -> bool:
        combo = combo.strip().lower()
        if not combo:
            return False
        self.settings["hotkey"] = combo
        self.save()
        return True

    def get_start_minimized(self) -> bool:
        return self.settings.get("start_minimized", True)

    def set_start_minimized(self, value: bool):
        self.settings["start_minimized"] = bool(value)
        self.save()

    def get_dark_mode(self) -> bool:
        return self.settings.get("dark_mode", True)

    def set_dark_mode(self, value: bool):
        self.settings["dark_mode"] = bool(value)
        self.save()

    def get_autostart_profile(self) -> str:
        """Name of the profile to launch automatically when the app starts
        via --startup (i.e. at Windows login) — empty string means none."""
        return self.settings.get("autostart_profile", "")

    def set_autostart_profile(self, name: str):
        self.settings["autostart_profile"] = name.strip() if name else ""
        self.save()

    # Category management

    def _category_name_taken(self, name: str, exclude: str = None) -> bool:
        """Case-insensitive collision check — "Gaming" and "gaming" shouldn't
        be able to coexist as separate categories. `exclude` lets
        rename_category ignore a category's own current name, since
        renaming "gaming" -> "Gaming" is a legitimate case change, not a
        collision with itself."""
        lower = name.lower()
        return any(c.lower() == lower for c in self.categories if c != exclude)

    def add_category(self, name: str):
        name = name.strip()
        if not name:
            return False
        # Stores the name with whatever casing the user actually typed,
        # since a nicely capitalized display name is nicer than forcing
        # lowercase — only the collision check itself is case-insensitive.
        if self._category_name_taken(name):
            return False
        self.categories[name] = []
        self.save()
        return True

    def remove_category(self, name: str):
        if _is_default_category(name):
            return False
        if name not in self.categories:
            return False
        del self.categories[name]
        # Keep profiles consistent: drop the removed category from any profile
        for prof, cats in self.profiles.items():
            self.profiles[prof] = [c for c in cats if c != name]
        self.save()
        return True

    def rename_category(self, old: str, new: str):
        new = new.strip()
        if not new or old not in self.categories:
            return False
        if self._category_name_taken(new, exclude=old):
            return False
        self.categories[new] = self.categories.pop(old)
        # Update profiles that reference this category
        for prof, cats in self.profiles.items():
            self.profiles[prof] = [new if c == old else c for c in cats]
        self.save()
        return True

    @staticmethod
    def _path_taken(apps: list, path: str, exclude_index: int = None) -> bool:
        """True if any entry in `apps` already uses `path`. `exclude_index`
        lets update_app ignore the entry being edited, since overwriting it
        with the same path it already had isn't a collision."""
        return any(i != exclude_index and e["path"] == path for i, e in enumerate(apps))

    def add_app_to_category(self, category: str, path: str, name: str = None,
                             args: str = "", working_dir: str = ""):
        if category not in self.categories:
            return False
        if self._path_taken(self.categories[category], path):
            return False
        self.categories[category].append(_build_entry(path, name, args, working_dir))
        self.save()
        return True

    def remove_app_from_category(self, category: str, index: int):
        if category not in self.categories:
            return None
        try:
            removed = self.categories[category].pop(index)
        except IndexError:
            return None
        self.save()
        return removed

    def update_app(self, category: str, index: int, path: str, name: str = None,
                    args: str = "", working_dir: str = ""):
        """Overwrites the app entry at `index` with new field values — used
        by the Edit App dialog to change name/path/arguments/working
        directory for an existing entry. Returns False if the index is out
        of range, or another entry in the category already uses that path."""
        if category not in self.categories:
            return False
        apps = self.categories[category]
        if index < 0 or index >= len(apps):
            return False
        if self._path_taken(apps, path, exclude_index=index):
            return False
        apps[index] = _build_entry(path, name, args, working_dir)
        self.save()
        return True

    # Profile management

    def add_profile(self, name: str, categories=None):
        name = name.strip()
        if not name:
            return False
        if name in self.profiles:
            return False
        valid = [c for c in (categories or []) if c in self.categories]
        self.profiles[name] = valid
        self.save()
        return True

    def remove_profile(self, name: str):
        if name not in self.profiles:
            return False
        del self.profiles[name]
        # Don't leave the autostart setting pointing at a profile that no
        # longer exists.
        if self.get_autostart_profile() == name:
            self.settings["autostart_profile"] = ""
        self.save()
        return True

    def rename_profile(self, old: str, new: str):
        new = new.strip()
        if not new or old not in self.profiles:
            return False
        if new in self.profiles and new != old:
            return False
        self.profiles[new] = self.profiles.pop(old)
        # Keep the autostart setting following the profile it refers to.
        if self.get_autostart_profile() == old:
            self.settings["autostart_profile"] = new
        self.save()
        return True

    def set_profile_categories(self, name: str, categories):
        if name not in self.profiles:
            return False
        valid = [c for c in categories if c in self.categories]
        self.profiles[name] = valid
        self.save()
        return True

    def get_profile_apps(self, name: str):
        """Flattened, de-duplicated (by path) list of app entries across all
        categories in a profile."""
        cats = self.profiles.get(name, [])
        seen = set()
        apps = []
        for c in cats:
            for entry in self.categories.get(c, []):
                if entry["path"] not in seen:
                    seen.add(entry["path"])
                    apps.append(entry)
        return apps

    # Export / import

    def export_to(self, path) -> bool:
        """Writes categories + profiles (not settings — those are machine-specific,
        like the hotkey) to a standalone JSON file for backup or sharing."""
        payload = {"categories": self.categories, "profiles": self.profiles}
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=4)
            log.info("Exported config to %s", path)
            return True
        except OSError:
            log.exception("Failed to export config to %s", path)
            return False

    def read_import_file(self, path):
        """Reads and validates an export file without applying it yet.
        Returns the parsed dict, or None if the file is missing, corrupt,
        or doesn't look like a valid export."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except (OSError, json.JSONDecodeError):
            log.exception("Failed to read import file %s", path)
            return None
        if not isinstance(raw.get("categories"), dict):
            log.warning("Import file %s missing a valid 'categories' key", path)
            return None
        return raw

    def import_category(self, name: str, apps: list, mode: str, save: bool = True):
        """mode: 'add' (name doesn't exist locally yet), 'replace' (overwrite
        the existing category's app list), or 'combine' (merge app lists,
        skipping duplicate paths). `apps` entries may be plain path strings
        (an older export) or the current dict shape — normalized either way.
        `save=False` lets a caller importing multiple categories in a loop
        (see ui.py's import_config) batch them into one disk write at the
        end instead of one per category."""
        normalized = [normalize_app_entry(e) for e in apps]
        if mode in ("add", "replace"):
            self.categories[name] = normalized
        elif mode == "combine":
            existing = self.categories.setdefault(name, [])
            existing_paths = {e["path"] for e in existing}
            for entry in normalized:
                if entry["path"] not in existing_paths:
                    existing.append(entry)
                    existing_paths.add(entry["path"])
        if save:
            self.save()

    def import_profiles(self, profiles: dict, save: bool = True):
        """Adds profiles from an import file that don't already exist locally.
        Existing profiles with the same name are left untouched."""
        for name, cats in profiles.items():
            if name in self.profiles or not isinstance(cats, list):
                continue
            valid = [c for c in cats if c in self.categories]
            self.profiles[name] = valid
        if save:
            self.save()