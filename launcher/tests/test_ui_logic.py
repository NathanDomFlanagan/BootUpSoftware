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
from ui import LauncherUI, CONFIRM_LAUNCH_THRESHOLD


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
    ui.undo_stack = []
    ui.trash = []
    ui.undo_button = MagicMock()
    ui.load_apps = MagicMock()
    ui.set_status = MagicMock()
    ui.populate_categories = MagicMock()
    ui.populate_profiles = MagicMock()
    ui._settings_window = None
    ui._trash_window = None
    # A fake dialogs object per instance, same as the real self.dialogs =
    # dialogs assignment in __init__ — tests configure return values
    # directly on it (e.g. ui.dialogs.ask_yes_no.return_value = True)
    # instead of patching ctk_dialogs by name.
    ui.dialogs = MagicMock()
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


class FakeCombo:
    """Minimal stand-in for a CTkOptionMenu: supports `.configure(values=...)`
    and `.set(...)`, without needing a real Tk root."""
    def __init__(self):
        self.values = []
        self.current_text = None

    def configure(self, values=None, **kwargs):
        if values is not None:
            self.values = values

    def set(self, value):
        self.current_text = value


def _entry(path, name=None):
    """Builds an app entry dict matching config.py's normalize_app_entry
    shape, for tests that need to construct one directly."""
    return {
        "path": path, "name": name or Path(path).name, "args": "", "working_dir": "",
        "type": "uwp" if path.lower().startswith("shell:") else "path",
    }


class TestUndoTrashSync:
    def test_undo_removes_matching_entry_from_trash(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        entry = _entry("C:/Games/game.exe")
        ui.undo_stack = [("Gaming", 0, entry)]
        ui.trash = [("Gaming", entry)]
        c.remove_app_from_category("Gaming", 0)

        ui.undo_delete()

        assert any(e["path"] == "C:/Games/game.exe" for e in c.categories["Gaming"])
        assert ui.trash == []
        assert ui.undo_stack == []

    def test_trash_restore_after_undo_does_not_duplicate(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        entry = _entry("C:/Games/game.exe")
        ui.undo_stack = [("Gaming", 0, entry)]
        ui.trash = [("Gaming", entry)]

        ui.undo_delete()
        assert ui.trash == []

        # Simulate what remove_app previously allowed: restoring the same
        # item again from a trash window that was left open before undo ran.
        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        ui.dialogs.ask_yes_no.return_value = True
        ui.restore_from_trash(tree)

        matching = [e for e in c.categories["Gaming"] if e["path"] == "C:/Games/game.exe"]
        assert len(matching) == 1

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
        entry = _entry("C:/Games/game.exe")
        ui.undo_stack = [("Gaming", 0, entry)]
        ui.trash = [("Gaming", entry)]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        ui.dialogs.ask_yes_no.return_value = True
        ui.restore_from_trash(tree)
        matching = [e for e in c.categories["Gaming"] if e["path"] == "C:/Games/game.exe"]
        assert len(matching) == 1

        # Calling undo_delete() afterward (e.g. a stray click before the
        # button visually updates) must be a safe no-op, not a duplicate
        # insert — and the undo stack should already be cleared of this
        # item by the restore itself (see TestUndoButtonClearedByTrashRestore
        # below).
        ui.undo_delete()

        matching = [e for e in c.categories["Gaming"] if e["path"] == "C:/Games/game.exe"]
        assert len(matching) == 1
        assert ui.undo_stack == []


class TestUndoButtonClearedByTrashRestore:
    """Restoring an item from the Trash window used to leave the Undo
    button showing (the pending undo entry was never cleared), so it stayed
    visible and seemingly actionable until clicked, even though the item
    was already back. restore_from_trash() should drop the matching entry
    from the undo stack when it matches what was just restored."""

    def test_last_deleted_cleared_when_restored_item_matches(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/game.exe")
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        entry = _entry("C:/Games/game.exe")
        ui.undo_stack = [("Gaming", 0, entry)]
        ui.trash = [("Gaming", entry)]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "game.exe", "C:/Games/game.exe")

        ui.dialogs.ask_yes_no.return_value = True
        ui.restore_from_trash(tree)

        assert ui.undo_stack == []
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
        other_entry = _entry("C:/Games/other.exe")
        ui.undo_stack = [("Gaming", 0, other_entry)]
        ui.trash = [
            ("Gaming", other_entry),
            ("Gaming", _entry("C:/Games/unrelated.exe")),
        ]

        tree = MagicMock()
        row_id = "row1"
        tree.selection.return_value = [row_id]
        tree.item.return_value = ("Gaming", "unrelated.exe", "C:/Games/unrelated.exe")

        ui.dialogs.ask_yes_no.return_value = True
        ui.restore_from_trash(tree)

        assert ui.undo_stack == [("Gaming", 0, other_entry)]
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

        ui.dialogs.ask_yes_no_cancel.return_value = True  # "Yes" = merge
        with patch("ui.filedialog.askopenfilename", return_value=str(import_path)):
            ui.import_config()

        # Merged into the existing "Gaming" category, no separate "gaming" created.
        assert set(c.categories.keys()) == {"default", "Gaming"}
        paths = [e["path"] for e in c.categories["Gaming"]]
        assert "C:/Games/a.exe" in paths
        assert "C:/Games/b.exe" in paths


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


class TestApplyStartupBehavior:
    """_apply_startup_behavior() is called from __init__ only when launched
    via --startup (i.e. at actual Windows login). Regression coverage for
    the bug where it used to only run _maybe_run_autostart_profile when
    Start Minimized was also on — a user with that preference off never
    got their Startup Profile launched at all, since --startup itself was
    only added to the registry command when start_minimized was true."""

    def test_runs_autostart_profile_even_when_not_starting_minimized(self, tmp_path):
        c = _make_config(tmp_path)
        c.set_start_minimized(False)
        ui = _make_ui(c)
        ui.after = MagicMock()

        ui._apply_startup_behavior()

        # minimize_to_tray must NOT be scheduled...
        scheduled_callbacks = [call.args[1] for call in ui.after.call_args_list]
        assert ui.minimize_to_tray not in scheduled_callbacks
        # ...but the autostart profile check must still be scheduled regardless.
        assert ui._maybe_run_autostart_profile in scheduled_callbacks

    def test_schedules_minimize_when_start_minimized_is_on(self, tmp_path):
        c = _make_config(tmp_path)
        c.set_start_minimized(True)
        ui = _make_ui(c)
        ui.after = MagicMock()

        ui._apply_startup_behavior()

        scheduled_callbacks = [call.args[1] for call in ui.after.call_args_list]
        assert ui.minimize_to_tray in scheduled_callbacks
        assert ui._maybe_run_autostart_profile in scheduled_callbacks


class TestAutostartProfile:
    """_maybe_run_autostart_profile() is called from _apply_startup_behavior()
    (see TestApplyStartupBehavior above), so it's tested directly here
    rather than by driving __init__ itself."""

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

        ui.launcher.launch_list.assert_called_once_with([_entry("C:/Games/steam.exe")])

    def test_does_nothing_when_configured_profile_has_no_apps(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_profile("Empty")
        c.set_autostart_profile("Empty")

        ui = _make_ui(c)
        ui.launcher = MagicMock()

        ui._maybe_run_autostart_profile()

        ui.launcher.launch_list.assert_not_called()


class TestRunSelected:
    """run_selected() used to only launch the first selected row even though
    the app tree's default ttk selectmode ("extended") allows multi-select
    via Ctrl/Shift-click — clicking three rows and hitting Run Selected
    silently launched just one. It now reads tree.selection() directly
    (rather than going through _selected_app(), which is deliberately
    single-row for remove_app()/edit_app()) and launches all of them via
    AppLauncher.launch_list(), in top-to-bottom tree order regardless of the
    order the rows were clicked in."""

    def _make_tree(self, index_by_row):
        tree = MagicMock()
        tree.index.side_effect = lambda row_id: index_by_row[row_id]
        return tree

    def test_multiple_selected_launch_in_tree_order(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")
        c.add_app_to_category("Gaming", "C:/Games/b.exe")
        c.add_app_to_category("Gaming", "C:/Games/c.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.tree = self._make_tree({"row0": 0, "row1": 1, "row2": 2})
        # Selection order deliberately reversed from tree order — launch
        # order must still be top-to-bottom.
        ui.tree.selection.return_value = ("row2", "row0")

        ui.run_selected()

        apps = c.categories["Gaming"]
        ui.launcher.launch_list.assert_called_once_with([apps[0], apps[2]])
        ui.set_status.assert_called_once_with("Launched 2 app(s) from 'Gaming'")

    def test_single_selected_keeps_original_status_message(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.tree = self._make_tree({"row0": 0})
        ui.tree.selection.return_value = ("row0",)

        ui.run_selected()

        apps = c.categories["Gaming"]
        ui.launcher.launch_list.assert_called_once_with([apps[0]])
        ui.set_status.assert_called_once_with("Launched: a.exe")

    def test_no_selection_shows_info_and_launches_nothing(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.tree = MagicMock()
        ui.tree.selection.return_value = ()

        ui.run_selected()

        ui.dialogs.show_info.assert_called_once_with(ui, "Info", "Please select an app to run.")
        ui.launcher.launch_list.assert_not_called()
        ui.launcher.launch_entry.assert_not_called()
        ui.set_status.assert_not_called()

    def test_stale_row_filtered_out_without_error(self, tmp_path):
        """A selected row whose tree index no longer maps to a real app is
        skipped rather than raising an IndexError — matching
        _selected_app()'s existing `index >= len(apps)` guard."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.tree = self._make_tree({"row0": 0, "stale": 5})
        ui.tree.selection.return_value = ("stale", "row0")

        ui.run_selected()

        apps = c.categories["Gaming"]
        ui.launcher.launch_list.assert_called_once_with([apps[0]])
        ui.set_status.assert_called_once_with("Launched: a.exe")


class TestMultiLevelUndo:
    """undo_stack replaced a single last_deleted slot, which discarded the
    ability to undo an earlier removal as soon as a second one happened.
    These cover what's actually new: repeated undo walking back through
    several removals in order, the button's depth label, and that
    restoring one still-pending item via Trash only drops that one entry
    from the stack."""

    def test_undo_delete_restores_multiple_removals_in_reverse_order(self, tmp_path):
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/Games/a.exe")
        c.add_app_to_category("Gaming", "C:/Games/b.exe")
        c.add_app_to_category("Gaming", "C:/Games/c.exe")

        ui = _make_ui(c)
        ui.current_category = "Gaming"

        entry_a = _entry("C:/Games/a.exe")
        entry_b = _entry("C:/Games/b.exe")
        entry_c = _entry("C:/Games/c.exe")

        # Mirrors what three consecutive remove_app() clicks would do:
        # remove b (index 1) -> [a, c]; remove what's now index 1, c -> [a];
        # remove index 0, a -> []. Each index is recorded at the moment of
        # that specific removal, same as remove_app() does.
        c.remove_app_from_category("Gaming", 1)
        ui.undo_stack.append(("Gaming", 1, entry_b))
        c.remove_app_from_category("Gaming", 1)
        ui.undo_stack.append(("Gaming", 1, entry_c))
        c.remove_app_from_category("Gaming", 0)
        ui.undo_stack.append(("Gaming", 0, entry_a))

        assert len(ui.undo_stack) == 3

        ui.undo_delete()  # restores a (the most recent removal)
        assert [e["path"] for e in c.categories["Gaming"]] == ["C:/Games/a.exe"]

        ui.undo_delete()  # restores c
        assert [e["path"] for e in c.categories["Gaming"]] == ["C:/Games/a.exe", "C:/Games/c.exe"]

        ui.undo_delete()  # restores b — fully back to the original order
        assert [e["path"] for e in c.categories["Gaming"]] == [
            "C:/Games/a.exe", "C:/Games/b.exe", "C:/Games/c.exe",
        ]
        assert ui.undo_stack == []

    def test_undo_button_label_shows_stack_depth(self, tmp_path):
        c = _make_config(tmp_path)
        ui = _make_ui(c)

        ui.undo_stack.append(("Gaming", 0, _entry("C:/a.exe")))
        ui._refresh_undo_button()
        ui.undo_button.configure.assert_called_with(text="↺ Undo")

        ui.undo_stack.append(("Gaming", 0, _entry("C:/b.exe")))
        ui._refresh_undo_button()
        ui.undo_button.configure.assert_called_with(text="↺ Undo (2)")

        ui.undo_stack.pop()
        ui._refresh_undo_button()
        ui.undo_button.configure.assert_called_with(text="↺ Undo")

    def test_restore_from_trash_removes_only_matching_entry_from_stack(self, tmp_path):
        """Two removals are both still pending in the undo stack; restoring
        one of them via the Trash window must only drop that one entry,
        leaving the other one's Undo still intact — a scenario that
        couldn't exist under the old single-slot design."""
        c = _make_config(tmp_path)
        c.add_category("Gaming")
        c.add_app_to_category("Gaming", "C:/a.exe")
        c.add_app_to_category("Gaming", "C:/b.exe")
        c.remove_app_from_category("Gaming", 1)
        c.remove_app_from_category("Gaming", 0)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        entry_a = _entry("C:/a.exe")
        entry_b = _entry("C:/b.exe")
        ui.undo_stack = [("Gaming", 1, entry_b), ("Gaming", 0, entry_a)]
        ui.trash = [("Gaming", entry_b), ("Gaming", entry_a)]

        tree = MagicMock()
        tree.selection.return_value = ["row_b"]
        tree.item.return_value = ("Gaming", "b.exe", "C:/b.exe")
        ui.dialogs.ask_yes_no.return_value = True

        ui.restore_from_trash(tree)

        assert ui.undo_stack == [("Gaming", 0, entry_a)]


class TestConfirmBeforeBulkLaunch:
    """run_apps()/run_profile() previously launched immediately regardless
    of size — one mis-click could silently open a dozen windows. Above
    CONFIRM_LAUNCH_THRESHOLD apps, both now confirm first via
    dialogs.ask_yes_no(); below it, they stay one-click as before."""

    def _fill_category(self, c, count):
        c.add_category("Gaming")
        for i in range(count):
            c.add_app_to_category("Gaming", f"C:/Games/app{i}.exe")
        return c.categories["Gaming"]

    # -- run_apps() --

    def test_run_apps_below_threshold_launches_without_confirming(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD - 1)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()

        ui.run_apps()

        ui.dialogs.ask_yes_no.assert_not_called()
        ui.launcher.launch_list.assert_called_once_with(apps)
        ui.set_status.assert_called_once_with(f"Launched {len(apps)} app(s) from 'Gaming'")

    def test_run_apps_at_threshold_confirmed_launches(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.dialogs.ask_yes_no.return_value = True

        ui.run_apps()

        ui.dialogs.ask_yes_no.assert_called_once_with(
            ui, "Confirm Launch", f"Launch {len(apps)} apps in 'Gaming'?"
        )
        ui.launcher.launch_list.assert_called_once_with(apps)
        ui.set_status.assert_called_once_with(f"Launched {len(apps)} app(s) from 'Gaming'")

    def test_run_apps_at_threshold_declined_does_not_launch(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD)

        ui = _make_ui(c)
        ui.current_category = "Gaming"
        ui.launcher = MagicMock()
        ui.dialogs.ask_yes_no.return_value = False

        ui.run_apps()

        ui.dialogs.ask_yes_no.assert_called_once_with(
            ui, "Confirm Launch", f"Launch {len(apps)} apps in 'Gaming'?"
        )
        ui.launcher.launch_list.assert_not_called()
        ui.set_status.assert_not_called()

    # -- run_profile() --

    def test_run_profile_below_threshold_launches_without_confirming(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD - 1)
        c.add_profile("Evening", ["Gaming"])

        ui = _make_ui(c)
        ui.profile_var = FakeVar("Evening")
        ui.launcher = MagicMock()

        ui.run_profile()

        ui.dialogs.ask_yes_no.assert_not_called()
        ui.launcher.launch_list.assert_called_once_with(apps)
        ui.set_status.assert_called_once_with(f"Launched profile 'Evening' ({len(apps)} app(s))")

    def test_run_profile_at_threshold_confirmed_launches(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD)
        c.add_profile("Evening", ["Gaming"])

        ui = _make_ui(c)
        ui.profile_var = FakeVar("Evening")
        ui.launcher = MagicMock()
        ui.dialogs.ask_yes_no.return_value = True

        ui.run_profile()

        ui.dialogs.ask_yes_no.assert_called_once_with(
            ui, "Confirm Launch", f"Launch {len(apps)} apps in profile 'Evening'?"
        )
        ui.launcher.launch_list.assert_called_once_with(apps)
        ui.set_status.assert_called_once_with(f"Launched profile 'Evening' ({len(apps)} app(s))")

    def test_run_profile_at_threshold_declined_does_not_launch(self, tmp_path):
        c = _make_config(tmp_path)
        apps = self._fill_category(c, CONFIRM_LAUNCH_THRESHOLD)
        c.add_profile("Evening", ["Gaming"])

        ui = _make_ui(c)
        ui.profile_var = FakeVar("Evening")
        ui.launcher = MagicMock()
        ui.dialogs.ask_yes_no.return_value = False

        ui.run_profile()

        ui.dialogs.ask_yes_no.assert_called_once_with(
            ui, "Confirm Launch", f"Launch {len(apps)} apps in profile 'Evening'?"
        )
        ui.launcher.launch_list.assert_not_called()
        ui.set_status.assert_not_called()
