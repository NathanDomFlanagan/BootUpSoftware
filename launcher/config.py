import json
import shutil
import sys
from pathlib import Path

CONFIG_NAME = "config.json"


def _is_default_category(name: str) -> bool:
    return name.strip().lower() == "default"


def _resolve_config_path() -> Path:
    if getattr(sys, "frozen", False):
        external = Path(sys.executable).parent / CONFIG_NAME
        if not external.exists():
            bundled = Path(sys._MEIPASS) / CONFIG_NAME
            if bundled.exists():
                shutil.copy(bundled, external)
        return external
    return Path(__file__).with_name(CONFIG_NAME)


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

        with self.path.open("r", encoding="utf-8") as f:
            raw = json.load(f)

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
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

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

    # Category management

    def add_category(self, name: str):
        name = name.strip()
        if not name:
            return False
        if name in self.categories:
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
        if new in self.categories and new != old:
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
        self.save()
        return True

    def rename_profile(self, old: str, new: str):
        new = new.strip()
        if not new or old not in self.profiles:
            return False
        if new in self.profiles and new != old:
            return False
        self.profiles[new] = self.profiles.pop(old)
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