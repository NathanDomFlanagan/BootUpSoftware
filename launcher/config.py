import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name("config.json")

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

        # Backward compatibility: old format was { "default": [...], "gaming": [...] }
        if "categories" not in raw:
            self.data["categories"] = raw
            self.data["profiles"] = {}
            self.save()
        else:
            self.data = raw

    def save(self):
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

    @property
    def categories(self):
        return self.data.setdefault("categories", {})

    @property
    def profiles(self):
        return self.data.setdefault("profiles", {})

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
        if name == "default":
            return False
        if name not in self.categories:
            return False
        del self.categories[name]
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
