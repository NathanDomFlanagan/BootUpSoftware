"""
Tests for config.py — categories, profiles, corrupt-file recovery, and
export/import merge behavior.

Run with: pytest tests/test_config.py
(or just: python -m pytest tests/)
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config


def _make_config(tmp_path):
    c = Config.__new__(Config)
    c.path = tmp_path / "config.json"
    c.data = {"categories": {}, "profiles": {}}
    c.load()
    return c


def _paths(entries):
    """Extracts just the path strings from a list of app entry dicts, for
    assertions that only care about which apps are present, not the full
    entry shape."""
    return [e["path"] for e in entries]


class TestCategoryCasing:
    def test_add_duplicate_different_case_fails(self, tmp_path):
        c = _make_config(tmp_path)
        assert c.add_category("Gaming") is True
        assert c.add_category("gaming") is False
        assert c.add_category("GAMING") is False
        assert list(c.categories.keys()).count("Gaming") == 1

    def test_add_preserves_typed_casing(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        assert "Gaming" in c.categories
        assert "gaming" not in c.categories

    def test_rename_to_case_variant_of_self_succeeds(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        assert c.rename_category("Gaming", "GAMING") is True
        assert "GAMING" in c.categories
        assert "Gaming" not in c.categories

    def test_rename_to_case_duplicate_of_other_fails(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_category("Programming")
        assert c.rename_category("Programming", "gaming") is False
        assert "Programming" in c.categories


class TestCategoryCRUD:
    def test_add_app_and_remove(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        assert c.add_app_to_category("Gaming", "C:/steam.exe") is True
        assert c.add_app_to_category("Gaming", "C:/steam.exe") is False  # exact dup blocked
        assert _paths(c.categories["Gaming"]) == ["C:/steam.exe"]
        removed = c.remove_app_from_category("Gaming", 0)
        assert removed["path"] == "C:/steam.exe"
        assert c.categories["Gaming"] == []

    def test_add_app_derives_name_from_path_by_default(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/steam.exe")
        assert c.categories["Gaming"][0]["name"] == "steam.exe"

    def test_add_app_accepts_an_explicit_name_and_args(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category(
            "Gaming", "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
            name="Calculator"
        )
        entry = c.categories["Gaming"][0]
        assert entry["name"] == "Calculator"
        assert entry["args"] == ""
        assert entry["working_dir"] == ""

    def test_default_category_cannot_be_removed(self, tmp_path):
        c = _make_config(tmp_path)
        assert c.remove_category("default") is False

    def test_remove_category_scrubs_it_from_profiles(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_profile("Evening", ["Gaming", "default"])
        c.remove_category("Gaming")
        assert "Gaming" not in c.profiles["Evening"]
        assert "default" in c.profiles["Evening"]


class TestUpdateApp:
    def test_updates_name_args_and_working_dir(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/chrome.exe")

        assert c.update_app(
            "Gaming", 0, path="C:/chrome.exe", name="Gmail",
            args="--app=https://mail.google.com/mail/", working_dir="C:/"
        ) is True

        entry = c.categories["Gaming"][0]
        assert entry == {
            "path": "C:/chrome.exe", "name": "Gmail",
            "args": "--app=https://mail.google.com/mail/", "working_dir": "C:/",
            "type": "path",
        }

    def test_can_change_the_path_itself(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/old.exe")
        assert c.update_app("Gaming", 0, path="C:/new.exe") is True
        assert c.categories["Gaming"][0]["path"] == "C:/new.exe"

    def test_blocks_changing_path_to_collide_with_another_entry(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/a.exe")
        c.add_app_to_category("Gaming", "C:/b.exe")

        assert c.update_app("Gaming", 1, path="C:/a.exe") is False
        assert c.categories["Gaming"][1]["path"] == "C:/b.exe"  # unchanged

    def test_allows_saving_with_the_same_path_it_already_had(self, tmp_path):
        """Editing just the name/args of an entry, path unchanged, must not
        be treated as a self-collision."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/a.exe")
        assert c.update_app("Gaming", 0, path="C:/a.exe", name="Renamed") is True
        assert c.categories["Gaming"][0]["name"] == "Renamed"

    def test_out_of_range_index_fails(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        assert c.update_app("Gaming", 0, path="C:/a.exe") is False

    def test_unknown_category_fails(self, tmp_path):
        c = _make_config(tmp_path)
        assert c.update_app("Nonexistent", 0, path="C:/a.exe") is False


class TestProfiles:
    def test_get_profile_apps_dedupes_across_categories(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("A")
        c.add_category("B")
        c.add_app_to_category("A", "C:/shared.exe")
        c.add_app_to_category("A", "C:/only_a.exe")
        c.add_app_to_category("B", "C:/shared.exe")
        c.add_app_to_category("B", "C:/only_b.exe")
        c.add_profile("Combo", ["A", "B"])
        apps = _paths(c.get_profile_apps("Combo"))
        assert apps.count("C:/shared.exe") == 1
        assert "C:/only_a.exe" in apps
        assert "C:/only_b.exe" in apps


class TestAutostartProfile:
    def test_defaults_to_disabled(self, tmp_path):
        c = _make_config(tmp_path)
        assert c.get_autostart_profile() == ""

    def test_set_and_get_roundtrip(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Evening")
        c.set_autostart_profile("Evening")
        assert c.get_autostart_profile() == "Evening"

    def test_removing_the_autostart_profile_clears_the_setting(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Evening")
        c.set_autostart_profile("Evening")
        c.remove_profile("Evening")
        assert c.get_autostart_profile() == ""

    def test_removing_an_unrelated_profile_leaves_it_untouched(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Evening")
        c.add_profile("Morning")
        c.set_autostart_profile("Evening")
        c.remove_profile("Morning")
        assert c.get_autostart_profile() == "Evening"

    def test_renaming_the_autostart_profile_follows_the_rename(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Evening")
        c.set_autostart_profile("Evening")
        c.rename_profile("Evening", "Night")
        assert c.get_autostart_profile() == "Night"

    def test_renaming_an_unrelated_profile_leaves_it_untouched(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Evening")
        c.add_profile("Morning")
        c.set_autostart_profile("Evening")
        c.rename_profile("Morning", "Early Morning")
        assert c.get_autostart_profile() == "Evening"


class TestCorruptConfigRecovery:
    def test_corrupt_json_falls_back_to_defaults(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text("this is not valid json {{{")

        c = Config.__new__(Config)
        c.path = path
        c.data = {"categories": {}, "profiles": {}}
        c.load()  # should not raise

        assert "default" in c.categories
        backup = path.with_suffix(".json.bak")
        assert backup.exists()

    def test_valid_config_loads_normally(self, tmp_path):
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "categories": {"Gaming": ["C:/steam.exe"]},
            "profiles": {}
        }))
        c = Config.__new__(Config)
        c.path = path
        c.data = {"categories": {}, "profiles": {}}
        c.load()
        assert _paths(c.categories["Gaming"]) == ["C:/steam.exe"]

    def test_old_flat_string_app_entries_are_migrated_on_load(self, tmp_path):
        """Apps used to be stored as bare path strings before per-app
        name/args/working_dir was added — an existing config.json in that
        older shape must still load correctly and be upgraded in place."""
        path = tmp_path / "config.json"
        path.write_text(json.dumps({
            "categories": {"Gaming": ["C:/Games/steam.exe"]},
            "profiles": {}
        }))
        c = Config.__new__(Config)
        c.path = path
        c.data = {"categories": {}, "profiles": {}}
        c.load()

        entry = c.categories["Gaming"][0]
        assert entry == {
            "path": "C:/Games/steam.exe", "name": "steam.exe", "args": "", "working_dir": "",
            "type": "path",
        }

        # The migration should have been persisted, not just held in memory.
        on_disk = json.loads(path.read_text())
        assert on_disk["categories"]["Gaming"][0]["name"] == "steam.exe"


class TestExportImport:
    def test_export_then_reimport_as_add(self, tmp_path):
        c1 = _make_config(tmp_path / "a")
        c1.add_category("Gaming")
        c1.add_app_to_category("Gaming", "C:/steam.exe")
        export_path = tmp_path / "export.json"
        assert c1.export_to(export_path) is True

        c2 = _make_config(tmp_path / "b")
        data = c2.read_import_file(export_path)
        assert data is not None
        c2.import_category("Gaming", data["categories"]["Gaming"], "add")
        assert _paths(c2.categories["Gaming"]) == ["C:/steam.exe"]

    def test_combine_mode_merges_without_duplicates(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/steam.exe")
        c.import_category("Gaming", ["C:/steam.exe", "C:/epic.exe"], "combine")
        assert _paths(c.categories["Gaming"]).count("C:/steam.exe") == 1
        assert "C:/epic.exe" in _paths(c.categories["Gaming"])

    def test_replace_mode_overwrites(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/old.exe")
        c.import_category("Gaming", ["C:/new.exe"], "replace")
        assert _paths(c.categories["Gaming"]) == ["C:/new.exe"]

    def test_import_category_accepts_old_flat_string_export(self, tmp_path):
        """A pre-migration export file (plain path strings) should still
        import cleanly into the current dict-based shape."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.import_category("Gaming", ["C:/old_export_style.exe"], "add")
        entry = c.categories["Gaming"][0]
        assert entry["path"] == "C:/old_export_style.exe"
        assert entry["name"] == "old_export_style.exe"

    def test_read_import_file_rejects_invalid_structure(self, tmp_path):
        path = tmp_path / "bad_export.json"
        path.write_text(json.dumps({"not_categories": {}}))
        c = _make_config(tmp_path / "cfg")
        assert c.read_import_file(path) is None

    def test_import_profiles_skips_existing(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_profile("Evening", ["Gaming"])
        c.import_profiles({"Evening": ["default"], "Morning": ["default"]})
        # Evening already existed locally — should NOT be overwritten
        assert c.profiles["Evening"] == ["Gaming"]
        assert c.profiles["Morning"] == ["default"]