"""
Tests for the undo/trash/import bug fixes in ui.py.

LauncherUI is a tkinter.Window subclass, so tests build a bare instance via
__new__ (skipping __init__, which would create a real window, tray icon, and
global hotkey) and stub out just the attributes each method under test
touches. No real Tk widgets or display are required.

Run with: pytest tests/test_ui_logic.py
(or just: python -m pytest tests/)
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Config
from ui import LauncherUI


def _make_config(tmp_path):
    c = Config.__new__(Config)
    c.path = tmp_path / "config.json"
    c.data = {"categories": {}, "profiles": {}}
    c.load()
    return c


def _make_ui(config_manager):
    ui = LauncherUI.__new__(LauncherUI)
    ui.config_manager = config_manager
    ui.current_category = None
    ui.last_deleted = None
    ui.trash = []
    ui.undo_button = MagicMock()
    ui.load_apps = MagicMock()
    ui.set_status = MagicMock()
    ui.populate_categories = MagicMock()
    ui.populate_profiles = MagicMock()
    ui._settings_window = None
    ui._trash_window = None
    return ui


class FakeVar:
    """Minimal stand-in for a tkinter StringVar's get/set, without needing a
    real Tk root."""
    def __init__(self, value=""):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class FakeCombo(dict):
    """Minimal stand-in for a ttk Combobox: supports `combo["values"] = ...`
    and `.set(...)`, without needing a real Tk root."""
    def set(self, value):
        self.current_text = value


class TestUndoTrashSync:
    def test_undo_removes_matching_entry_from_trash(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.last_deleted = ("Gaming", 0, "game.exe", "C:/Games/game.exe")
        ui.trash = [("Gaming", "game.exe", "C:/Games/game.exe")]
        c.remove_app_from_category("Gaming", 0)

        ui.undo_delete()

        assert "C:/Games/game.exe" in c.categories["Gaming"]
        assert ui.trash == []
        assert ui.last_deleted is None

    def test_trash_restore_after_undo_does_not_duplicate(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.last_deleted = ("Gaming", 0, "game.exe", "C:/Games/game.exe")
        ui.trash = [("Gaming", "game.exe", "C:/Games/game.exe")]

        ui.undo_delete()
        assert ui.trash == []

        # Simulate what remove_app previously allowed: restoring the same
        # item again from a trash window that was left open before undo ran.
        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        with patch("ui.messagebox.askyesno", return_value=True):
            ui.restore_from_trash(tree)

        assert c.categories["Gaming"].count("C:/Games/game.exe") == 1

    def test_undo_after_trash_restore_does_not_duplicate(self, tmp_path):
        """The reverse ordering of the test above: restore via the Trash
        window first, then click Undo — undo_delete() must not blindly
        re-insert a path that's already back in the category."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.last_deleted = ("Gaming", 0, "game.exe", "C:/Games/game.exe")
        ui.trash = [("Gaming", "game.exe", "C:/Games/game.exe")]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        with patch("ui.messagebox.askyesno", return_value=True):
            ui.restore_from_trash(tree)
        assert c.categories["Gaming"].count("C:/Games/game.exe") == 1

        # Calling undo_delete() afterward (e.g. a stray click before the
        # button visually updates) must be a safe no-op, not a duplicate
        # insert — and last_deleted should already be cleared by the
        # restore itself (see TestUndoButtonClearedByTrashRestore below).
        ui.undo_delete()

        assert c.categories["Gaming"].count("C:/Games/game.exe") == 1
        assert ui.last_deleted is None


class TestUndoButtonClearedByTrashRestore:
    """Restoring an item from the Trash window used to leave the Undo
    button showing (last_deleted was never cleared), so it stayed visible
    and seemingly actionable until clicked, even though the item was
    already back. restore_from_trash() should clear the pending undo entry
    itself when it matches what was just restored."""

    def test_last_deleted_cleared_when_restored_item_matches(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.last_deleted = ("Gaming", 0, "game.exe", "C:/Games/game.exe")
        ui.trash = [("Gaming", "game.exe", "C:/Games/game.exe")]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        with patch("ui.messagebox.askyesno", return_value=True):
            ui.restore_from_trash(tree)

        assert ui.last_deleted is None
        ui.undo_button.pack_forget.assert_called_once()

    def test_last_deleted_untouched_when_restored_item_is_unrelated(self, tmp_path):
        """Restoring some other trashed item shouldn't clear a still-valid
        pending undo for a different app."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/other.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.last_deleted = ("Gaming", 0, "other.exe", "C:/Games/other.exe")
        ui.trash = [
            ("Gaming", "other.exe", "C:/Games/other.exe"),
            ("Gaming", "unrelated.exe", "C:/Games/unrelated.exe"),
        ]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "unrelated.exe", "C:/Games/unrelated.exe")

        with patch("ui.messagebox.askyesno", return_value=True):
            ui.restore_from_trash(tree)

        assert ui.last_deleted == ("Gaming", 0, "other.exe", "C:/Games/other.exe")
        ui.undo_button.pack_forget.assert_not_called()


class TestImportCaseInsensitiveMerge:
    def test_import_merges_into_existing_category_regardless_of_case(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")

        ui = _make_ui(c)

        import_path = tmp_path / "export.json"
        import_data = {"categories": {"gaming": ["C:/Games/b.exe"]}, "profiles": {}}
        c.data  # noop, just for readability
        import json
        import_path.write_text(json.dumps(import_data))

        with patch("ui.filedialog.askopenfilename", return_value=str(import_path)), \
             patch("ui.messagebox.askyesnocancel", return_value=True):  # "Yes" = merge
            ui.import_config()

        # Merged into the existing "Gaming" category, no separate "gaming" created.
        assert set(c.categories.keys()) == {"default", "Gaming"}
        assert "C:/Games/a.exe" in c.categories["Gaming"]
        assert "C:/Games/b.exe" in c.categories["Gaming"]


class TestPopulateCategoriesPreservesSelection:
    """populate_categories() used to always jump to the first category,
    unlike populate_profiles() which preserves the current selection if it's
    still valid. That meant e.g. importing a config while viewing "Gaming"
    would silently snap the view back to whatever category came first."""

    def _make_ui_with_widgets(self, config_manager, current_selection):
        ui = _make_ui(config_manager)
        ui.category_var = FakeVar(current_selection)
        ui.category_combo = FakeCombo()
        ui.tree = MagicMock()
        # _make_ui() stubs these out for tests that don't exercise them —
        # here we're testing populate_categories() itself, so restore the
        # real bound methods (including the load_apps() it calls into).
        ui.load_apps = LauncherUI.load_apps.__get__(ui)
        ui.populate_categories = LauncherUI.populate_categories.__get__(ui)
        ui.set_status = MagicMock()
        return ui

    def test_preserves_still_valid_selection(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_category("Programming")
        ui = self._make_ui_with_widgets(c, "Gaming")

        ui.populate_categories()

        assert ui.category_var.get() == "Gaming"
        assert ui.current_category == "Gaming"

    def test_falls_back_to_first_when_selection_removed(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        ui = self._make_ui_with_widgets(c, "Deleted Category")

        ui.populate_categories()

        # FakeCombo.set() doesn't mirror back to FakeVar the way a real
        # Tkinter textvariable binding would, so current_category (what the
        # rest of the app actually keys off) is the meaningful assertion here.
        assert ui.current_category in c.categories
        assert ui.category_combo.current_text in c.categories


class TestWindowDedup:
    """open_settings()/view_trash() used to spawn a new window every click,
    even with one already open. Both now check for an existing, still-alive
    window first and refocus it instead."""

    def test_open_settings_reuses_existing_window(self, tmp_path):
        c = _make_config(tmp_path)
        ui = _make_ui(c)
        fake_window = MagicMock()
        fake_window.winfo_exists.return_value = True
        ui._settings_window = fake_window

        # Would raise trying to build a real SettingsWindow on a fake `ui`
        # if the dedup guard didn't short-circuit first.
        ui.open_settings()

        fake_window.lift.assert_called_once()
        fake_window.focus_force.assert_called_once()

    def test_view_trash_reuses_existing_window(self, tmp_path):
        c = _make_config(tmp_path)
        ui = _make_ui(c)
        fake_window = MagicMock()
        fake_window.winfo_exists.return_value = True
        ui._trash_window = fake_window

        ui.view_trash()

        fake_window.lift.assert_called_once()
        fake_window.focus_force.assert_called_once()


class TestAutostartProfile:
    """_maybe_run_autostart_profile() is only ever called from __init__ when
    start_minimized is True (i.e. launched via --startup at Windows login),
    so it's tested directly here rather than by driving __init__ itself."""

    def test_does_nothing_when_no_profile_configured(self, tmp_path):
        c = _make_config(tmp_path)
        ui = _make_ui(c)
        ui.launcher = MagicMock()

        ui._maybe_run_autostart_profile()

        ui.launcher.launch_list.assert_not_called()

    def test_launches_the_configured_profiles_apps(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/steam.exe")
        c.add_profile("Evening", ["Gaming"])
        c.set_autostart_profile("Evening")

        ui = _make_ui(c)
        ui.launcher = MagicMock()

        ui._maybe_run_autostart_profile()

        ui.launcher.launch_list.assert_called_once_with(["C:/Games/steam.exe"])

    def test_does_nothing_when_configured_profile_has_no_apps(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Empty")
        c.set_autostart_profile("Empty")

        ui = _make_ui(c)
        ui.launcher = MagicMock()

        ui._maybe_run_autostart_profile()

        ui.launcher.launch_list.assert_not_called()
