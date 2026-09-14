import json
import logging
import shutil
from pathlib import Path

from paths import app_dir, bundled_dir, is_frozen

log = logging.getLogger(__name__)

CONFIG_NAME = "config.json"


def _is_default_category(name: str) -> bool:
    return name.strip().lower() == "default"


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
            self.save()
        else:
            self.data = raw
            self.data.setdefault("profiles", {})

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

    def get_autostart_profile(self) -> str:
        """Name of the profile to launch automatically when the app starts
        via --startup (i.e. at Windows login) — empty string means none."""
        return self.settings.get("autostart_profile", "")

    def set_autostart_profile(self, name: str):
        self.settings["autostart_profile"] = name.strip() if name else ""
        self.save()

    # Category management

    def add_category(self, name: str):
        name = name.strip()
        if not name:
            return False
        # Case-insensitive duplicate check — "Gaming" and "gaming" shouldn't
        # be able to coexist as separate categories — while still storing
        # the name with whatever casing the user actually typed, since a
        # nicely capitalized display name is nicer than forcing lowercase.
        if name.lower() in {c.lower() for c in self.categories}:
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
        # Same case-insensitive duplicate check as add_category — but allow
        # renaming a category to a different casing of its own current name
        # (e.g. "gaming" -> "Gaming"), which is a legitimate rename, not a
        # collision with itself.
        clashes = new.lower() in {c.lower() for c in self.categories if c != old}
        if clashes:
            return False
        self.categories[new] = self.categories.pop(old)
        # Update profiles that reference this category
        for prof, cats in self.profiles.items():
            self.profiles[prof] = [new if c == old else c for c in cats]
        self.save()
        return True

    def add_app_to_category(self, category: str, path: str):
        if category not in self.categories:
            return False
        if path in self.categories[category]:
            return False
        self.categories[category].append(path)
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
        """Flattened, de-duplicated list of app paths across all categories in a profile."""
        cats = self.profiles.get(name, [])
        seen = set()
        apps = []
        for c in cats:
            for path in self.categories.get(c, []):
                if path not in seen:
                    seen.add(path)
                    apps.append(path)
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

    def import_category(self, name: str, apps: list, mode: str):
        """mode: 'add' (name doesn't exist locally yet), 'replace' (overwrite
        the existing category's app list), or 'combine' (merge app lists,
        skipping duplicate paths)."""
        if mode in ("add", "replace"):
            self.categories[name] = list(apps)
        elif mode == "combine":
            existing = self.categories.setdefault(name, [])
            for path in apps:
                if path not in existing:
                    existing.append(path)
        self.save()

    def import_profiles(self, profiles: dict):
        """Adds profiles from an import file that don't already exist locally.
        Existing profiles with the same name are left untouched."""
        for name, cats in profiles.items():
            if name in self.profiles or not isinstance(cats, list):
                continue
            valid = [c for c in cats if c in self.categories]
            self.profiles[name] = valid
        self.save()