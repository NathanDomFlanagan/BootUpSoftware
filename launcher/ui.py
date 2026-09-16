import logging
import os
import tkinter as tk
import tkinter.ttk as ttk

import customtkinter as ctk
from tkinter import filedialog, Menu

from config import Config
from launcher import AppLauncher, EXECUTABLE_FILETYPES
from tooltip import ToolTip
from hotkey import HotkeyManager
from tray import TrayIcon
from startup import StartupManager
from settings_window import SettingsWindow
from trash_window import TrashWindow
from edit_profile_dialog import EditProfileDialog
from edit_app_dialog import EditAppDialog
from app_picker import AppPickerWindow
import ctk_theme as theme
import ctk_dialogs as dialogs
import ctk_widgets as widgets
import appscan

log = logging.getLogger(__name__)


class LauncherUI(ctk.CTk):
    def __init__(self, launched_at_startup: bool = False):
        super().__init__()
        self.title("App Launcher")

        self.config_manager = Config()
        self.launcher = AppLauncher()
        # An instance attribute rather than calling the ctk_dialogs module
        # directly — every action method below goes through self.dialogs,
        # so a test can substitute a fake dialogs object on one instance
        # (e.g. ui_instance.dialogs = MagicMock()) instead of needing to
        # know and patch this module's exact internal import alias, which
        # breaks every time the dialog implementation itself changes.
        self.dialogs = dialogs
        theme.set_mode("dark" if self.config_manager.get_dark_mode() else "light")

        self.current_category = None
        self.tooltip = None
        self._settings_window = None
        self._trash_window = None
        self._edit_profile_window = None

        self.create_widgets()
        self.populate_categories()
        self.populate_profiles()

        # The window's natural width depends on how wide its button rows end
        # up (which varies with font metrics/DPI), so size it from the
        # widgets' actual layout requirements rather than a fixed pixel
        # guess — a hardcoded "800x560" here previously fell behind as
        # buttons grew wider, clipping the profiles row at launch until the
        # window was resized by hand. minsize() also stops the reverse
        # problem: without a floor, dragging the window smaller than its
        # content clips the same way instead of refusing to shrink further.
        self.update_idletasks()
        min_width = self.winfo_reqwidth()
        min_height = self.winfo_reqheight()
        self.minsize(min_width, min_height)
        self.geometry(f"{min_width}x{max(min_height, 560)}")

        self.last_deleted = None  # (category, index, entry)
        self.trash = []  # list of (original_category, entry)
        self._refresh_undo_button()

        # Tray + global hotkey setup
        self.tray_icon = TrayIcon(
            app_name="App Launcher",
            on_show=self.restore_from_tray,
            on_exit=self.quit_app,
        )
        self.hotkey_manager = HotkeyManager()
        self._register_hotkey(self.config_manager.get_hotkey())
        self.startup_manager = StartupManager()

        # Closing the window (X button) minimizes to tray instead of quitting.
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

        if launched_at_startup:
            self._apply_startup_behavior()

    def _apply_startup_behavior(self):
        """Called once from __init__, only when launched_at_startup is True
        (i.e. this run was triggered by the Windows Run at Startup entry,
        not a manual open — otherwise reopening the window during the day
        would relaunch everything every time).

        Start Minimized is a separate, independently-read preference here
        rather than something baked into how the process was launched — a
        user can want the Startup Profile to run without also wanting the
        window minimized. (Regression: this used to be gated on the same
        flag as minimizing, so a user with Start Minimized off never got
        their Startup Profile launched at all.)"""
        if self.config_manager.get_start_minimized():
            # Let the window fully initialize first, then hide it straight
            # to the tray rather than briefly flashing on screen at login.
            self.after(10, self.minimize_to_tray)
        self.after(20, self._maybe_run_autostart_profile)

    def _style_menu(self, menu: Menu):
        """Native tk.Menu widgets have no CustomTkinter equivalent — there's
        no CTk menu bar widget at all — so this hand-applies a palette
        matching the rest of the CTk-themed window and the current
        light/dark mode. Note: on Windows the top-level menu *bar* strip is
        drawn by the OS and ignores these colors regardless; only the
        dropdown panels that open from it are actually themeable this way."""
        colors = theme.menu_colors()
        menu.configure(
            background=colors["bg"],
            foreground=colors["fg"],
            activebackground=theme.PRIMARY,
            activeforeground="white",
            disabledforeground=colors["disabled_fg"],
            selectcolor=theme.PRIMARY,
            relief="flat",
            borderwidth=0,
            activeborderwidth=0,
        )

    def create_widgets(self):
        # Native menu bar — houses config-level actions (export/import,
        # shortcut, startup behavior). This is where users expect to find
        # them in a desktop app, rather than a button floating mid-window.
        self.menu_bar = Menu(self)
        self._style_menu(self.menu_bar)
        self.config(menu=self.menu_bar)

        self.file_menu = Menu(self.menu_bar, tearoff=False)
        self._style_menu(self.file_menu)
        self.file_menu.add_command(label="Export Config...", command=self.export_config)
        self.file_menu.add_command(label="Import Config...", command=self.import_config)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.quit_app)
        self.menu_bar.add_cascade(label="File", menu=self.file_menu)

        self.menu_bar.add_command(label="Settings...", command=self.open_settings)

        # Top frame: category selector
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=theme.PAD_NORMAL, pady=theme.PAD_NORMAL)

        widgets.FieldLabel(top_frame, text="Category:").pack(side="left")
        self.category_var = tk.StringVar()
        self.category_combo = widgets.PrimaryOptionMenu(
            top_frame,
            variable=self.category_var,
            values=[],
            command=self.on_category_change,
            width=250,
        )
        self.category_combo.pack(side="left", fill="x", expand=True, padx=theme.PAD_NORMAL)

        # Buttons for category management
        widgets.SuccessButton(
            top_frame, text="＋ New", command=self.new_category, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.PrimaryButton(
            top_frame, text="✎ Rename", command=self.rename_category, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.DangerButton(
            top_frame, text="🗑 Delete", command=self.remove_category, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)

        # Treeview for apps — stays plain ttk (mode-styled via ctk_theme) since
        # CustomTkinter has no Treeview equivalent.
        theme.apply_treeview_style()

        mid_frame = ctk.CTkFrame(self, fg_color="transparent")
        mid_frame.pack(fill="both", expand=True, padx=theme.PAD_NORMAL, pady=(0, theme.PAD_NORMAL))

        columns = ("name", "path")
        self.tree = ttk.Treeview(mid_frame, columns=columns, show="headings")
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("path", width=500, anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")

        # Tooltip for full path
        self.tooltip = ToolTip(self.tree)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self.tooltip.hidetip())
        self.tree.bind("<Double-1>", lambda e: self.edit_app())

        # Scrollbar
        scrollbar = ctk.CTkScrollbar(mid_frame, orientation="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Bottom buttons (category-level app actions)
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(pady=(0, theme.PAD_NORMAL))

        widgets.SuccessButton(
            bottom_frame, text="▶ Run All", command=self.run_apps,
        ).grid(row=0, column=0, padx=theme.PAD_TIGHT)
        widgets.PrimaryButton(
            bottom_frame, text="▶ Run Selected", command=self.run_selected,
        ).grid(row=0, column=1, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            bottom_frame, text="＋ Add App", command=self.add_app,
        ).grid(row=0, column=2, padx=theme.PAD_TIGHT)
        widgets.PrimaryButton(
            bottom_frame, text="✎ Edit App", command=self.edit_app,
        ).grid(row=0, column=3, padx=theme.PAD_TIGHT)
        widgets.DangerButton(
            bottom_frame, text="🗑 Remove App", command=self.remove_app,
        ).grid(row=0, column=4, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            bottom_frame, text="🗂 Trash", command=self.view_trash,
        ).grid(row=0, column=5, padx=theme.PAD_TIGHT)

        # Divider between categories and profiles
        widgets.Divider(self).pack(fill="x", padx=theme.PAD_NORMAL, pady=(0, theme.PAD_NORMAL))

        # Profiles frame: a profile = a named group of categories, run together
        profile_frame = ctk.CTkFrame(self, fg_color="transparent")
        profile_frame.pack(fill="x", padx=theme.PAD_NORMAL, pady=(0, theme.PAD_NORMAL))

        widgets.FieldLabel(profile_frame, text="Profile:").pack(side="left")
        self.profile_var = tk.StringVar()
        self.profile_combo = widgets.PrimaryOptionMenu(
            profile_frame,
            variable=self.profile_var,
            values=[],
            width=250,
        )
        self.profile_combo.pack(side="left", fill="x", expand=True, padx=theme.PAD_NORMAL)

        widgets.PrimaryButton(
            profile_frame, text="▶ Run Profile", command=self.run_profile,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.SuccessButton(
            profile_frame, text="＋ New", command=self.new_profile, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.PrimaryButton(
            profile_frame, text="✎ Edit", command=self.edit_profile, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.PrimaryButton(
            profile_frame, text="✎ Rename", command=self.rename_profile, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)
        widgets.DangerButton(
            profile_frame, text="🗑 Delete", command=self.remove_profile, width=95,
        ).pack(side="left", padx=theme.PAD_TIGHT)

        # Status bar — also carries the current shortcut and the tray-close
        # hint, both low-priority info that doesn't need its own row.
        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill="x", side="bottom")

        self.status_var = tk.StringVar(value="Ready")
        status_label = widgets.MutedLabel(status_frame, textvariable=self.status_var, anchor="w")
        status_label.pack(side="left", fill="x", expand=True, padx=(theme.PAD_TIGHT, 0))

        # Created but not packed yet — it only takes up space in the status
        # bar while there's actually something to undo (see
        # _refresh_undo_button), instead of sitting there disabled at all
        # other times.
        self.undo_button = widgets.PrimaryButton(
            status_frame,
            text="↺ Undo",
            command=self.undo_delete,
            width=90,
        )

        self.hotkey_label_var = tk.StringVar(value=f"Shortcut: {self.config_manager.get_hotkey()}")
        self._hotkey_label = widgets.MutedLabel(status_frame, textvariable=self.hotkey_label_var)
        self._hotkey_label.pack(side="right", padx=theme.PAD_NORMAL)

        tray_note_text = "Closing this window minimizes to the tray — use File ▸ Exit or the tray menu to quit"
        note_label = widgets.MutedLabel(status_frame, text="ⓘ", cursor="question_arrow")
        note_label.pack(side="right", padx=(theme.PAD_NORMAL, 0))
        self._tray_note_tooltip = ToolTip(note_label)
        note_label.bind("<Enter>", lambda e: self._tray_note_tooltip.schedule(tray_note_text))
        note_label.bind("<Leave>", lambda e: self._tray_note_tooltip.hidetip())

    def set_status(self, text: str):
        self.status_var.set(text)

    def _refresh_undo_button(self):
        """Shows the Undo button only while there's actually something to
        undo, rather than leaving it disabled-but-visible in the status bar
        the rest of the time. `before=self._hotkey_label` keeps it pinned to
        the far right of the status bar regardless of when it's re-packed."""
        if self.last_deleted is not None:
            if not self.undo_button.winfo_ismapped():
                self.undo_button.pack(side="right", padx=theme.PAD_NORMAL, before=self._hotkey_label)
        else:
            self.undo_button.pack_forget()

    def _require_category(self) -> bool:
        """True if a category is selected; otherwise shows an info dialog
        and returns False. Used as an early-return guard by every
        category-scoped app action, so all of them give the same feedback
        when nothing's selected instead of some silently doing nothing."""
        if self.current_category:
            return True
        self.dialogs.show_info(self, "Info", "Please select a category first.")
        return False

    def _require_profile(self):
        """Returns the selected profile's name, or None (after showing an
        info dialog) if none is selected."""
        name = self.profile_var.get()
        if name:
            return name
        self.dialogs.show_info(self, "Info", "Please select a profile first.")
        return None

    def _selected_app(self, no_selection_message: str):
        """Returns (index, entry) for the currently selected row in the app
        tree, or None if nothing's selected (after showing an info dialog
        with `no_selection_message`) or the selection is stale."""
        sel = self.tree.selection()
        if not sel:
            self.dialogs.show_info(self, "Info", no_selection_message)
            return None
        index = self.tree.index(sel[0])
        apps = self.config_manager.categories.get(self.current_category, [])
        if index >= len(apps):
            return None
        return index, apps[index]

    def populate_categories(self):
        cats = list(self.config_manager.categories.keys())
        self.category_combo.configure(values=cats)
        if not cats:
            self.category_var.set("")
            self.current_category = None
            self.tree.delete(*self.tree.get_children())
            return

        # Preserve the current selection if it's still valid (e.g. after an
        # import that didn't touch it), same as populate_profiles() already
        # does — only fall back to the first category if it's gone.
        current = self.category_var.get()
        if current not in cats:
            current = cats[0]
            self.category_combo.set(current)
        self.load_apps(current)

    def load_apps(self, category: str):
        self.current_category = category
        self.tree.delete(*self.tree.get_children())
        apps = self.config_manager.categories.get(category, [])
        for entry in apps:
            self.tree.insert("", "end", values=(entry["name"], entry["path"]))
        self.set_status(f"Loaded {len(apps)} app(s) in '{category}'")

    def on_category_change(self, selected=None):
        cat = self.category_var.get()
        if cat:
            self.load_apps(cat)

    def on_tree_motion(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            self.tooltip.hidetip()
            return
        values = self.tree.item(row_id, "values")
        if not values:
            self.tooltip.hidetip()
            return
        full_path = values[1]
        self.tooltip.schedule(full_path)

    @staticmethod
    def _apps_contains_path(apps: list, path: str) -> bool:
        """True if `apps` already has an entry with this path — used by
        undo_delete() and restore_from_trash() to avoid creating a
        duplicate when the same trashed item could be restored from
        either place."""
        return any(e["path"] == path for e in apps)

    def _remove_from_trash(self, category: str, path: str):
        """Strips the matching entry out of self.trash — called after
        restoring it (via Undo or the Trash window) so it can't be
        restored from there a second time."""
        self.trash = [
            t for t in self.trash
            if not (t[0] == category and t[1]["path"] == path)
        ]

    def undo_delete(self):
        if not self.last_deleted:
            return

        category, index, entry = self.last_deleted
        path = entry["path"]

        # Insert back into the list at the original index — but skip if
        # it's already there (e.g. it was already restored via the Trash
        # window before Undo was clicked), otherwise this would duplicate it.
        apps = self.config_manager.categories.get(category, [])
        if not self._apps_contains_path(apps, path):
            apps.insert(index, entry)
            self.config_manager.save()

        self._remove_from_trash(category, path)

        self.load_apps(category)
        self.set_status(f"Restored: {entry['name']}")

        # Clear undo buffer
        self.last_deleted = None
        self._refresh_undo_button()

    def view_trash(self):
        if self._trash_window is not None and self._trash_window.winfo_exists():
            self._trash_window.lift()
            self._trash_window.focus_force()
            return
        self._trash_window = TrashWindow(self)

    # Category actions

    def _select_category(self, name: str):
        """Refreshes the category list and switches the UI to `name` —
        shared by new_category()/rename_category() since both need to show
        the result of their change immediately rather than leaving the
        previous category selected/displayed."""
        self.populate_categories()
        self.category_combo.set(name)
        self.load_apps(name)

    def new_category(self):
        name = self.dialogs.ask_string(self, "New Category", "Enter new category name:")
        if not name:
            return
        if not self.config_manager.add_category(name):
            self.dialogs.show_info(self, "Info", f"Category '{name}' already exists or is invalid.")
            return
        self._select_category(name)
        self.set_status(f"Created category '{name}'")

    def rename_category(self):
        old = self.category_var.get()
        if not old:
            return
        new = self.dialogs.ask_string(self, "Rename Category", f"Rename '{old}' to:")
        if not new:
            return
        if not self.config_manager.rename_category(old, new):
            self.dialogs.show_info(self, "Info", f"Could not rename '{old}' to '{new}'.")
            return
        self._select_category(new)
        self.populate_profiles()  # profile category references may have been renamed
        self.set_status(f"Renamed category '{old}' to '{new}'")

    def remove_category(self):
        cat = self.category_var.get()
        if not cat:
            return
        if cat.strip().lower() == "default":
            self.dialogs.show_warning(self, "Not allowed", "The default category cannot be removed.")
            return
        if not self.dialogs.ask_yes_no(self, "Confirm", f"Delete category '{cat}' and all its apps?"):
            return
        if not self.config_manager.remove_category(cat):
            self.dialogs.show_info(self, "Info", f"Could not remove category '{cat}'.")
            return
        self.populate_categories()
        self.populate_profiles()  # profile category references may have been removed
        self.set_status(f"Removed category '{cat}'")

    # App actions

    def add_app(self):
        """Entry point for adding an app. Opens the Start Menu picker as the
        primary path — a searchable, multi-select list of apps discovered on
        this PC — with manual file browsing available as a fallback for
        anything not listed there (portable exes, custom scripts, etc.)."""
        if not self._require_category():
            return

        if not appscan.WIN32_AVAILABLE:
            # No pywin32 — the picker would always be empty, so skip
            # straight to the manual browse flow instead of showing it.
            self.add_app_manual()
            return

        AppPickerWindow(self, self.current_category)

    def add_app_manual(self):
        """The original manual file-picker flow — used as a fallback when the
        app you want isn't listed in the Start Menu scan (portable exes,
        custom scripts, etc.), or automatically when pywin32 isn't installed."""
        if not self._require_category():
            return

        path = filedialog.askopenfilename(
            title="Select Application or Shortcut",
            filetypes=EXECUTABLE_FILETYPES
        )
        if not path:
            return

        if not os.path.exists(path):
            self.dialogs.show_error(self, "Error", f"File not found:\n{path}")
            return

        if not self.config_manager.add_app_to_category(self.current_category, path):
            self.dialogs.show_info(self, "Info", "This application is already in the list.")
            return

        self.load_apps(self.current_category)
        self.set_status(f"Added app to '{self.current_category}'")

    def remove_app(self):
        if not self._require_category():
            return
        selected = self._selected_app("Please select an app to remove.")
        if selected is None:
            return
        index, entry = selected

        confirm = self.dialogs.ask_yes_no(
            self, "Confirm Removal",
            f"Remove this application from '{self.current_category}'?\n\n"
            f"Name: {entry['name']}\n"
            f"Path: {entry['path']}"
        )
        if not confirm:
            return

        # store for undo
        self.last_deleted = (self.current_category, index, entry)
        self._refresh_undo_button()

        # add to trash
        self.trash.append((self.current_category, entry))

        removed = self.config_manager.remove_app_from_category(self.current_category, index)
        if removed is None:
            self.dialogs.show_info(self, "Info", "Could not remove selected app.")
            return

        self.load_apps(self.current_category)
        self.set_status(f"Removed: {removed['name']}")

    def edit_app(self):
        if not self._require_category():
            return
        selected = self._selected_app("Please select an app to edit.")
        if selected is None:
            return
        index, entry = selected

        EditAppDialog(self, self.current_category, index, entry)

    def run_apps(self):
        if not self._require_category():
            return
        apps = self.config_manager.categories.get(self.current_category, [])
        if not apps:
            self.dialogs.show_info(self, "Info", "No applications to run in this category.")
            return
        self.launcher.launch_list(apps)
        self.set_status(f"Launched {len(apps)} app(s) from '{self.current_category}'")

    def run_selected(self):
        if not self._require_category():
            return
        selected = self._selected_app("Please select an app to run.")
        if selected is None:
            return
        index, entry = selected
        self.launcher.launch_entry(entry)
        self.set_status(f"Launched: {entry['name']}")

    def restore_from_trash(self, tree):
        sel = tree.selection()
        if not sel:
            return

        row_id = sel[0]
        cat, name, path = tree.item(row_id, "values")

        confirm = self.dialogs.ask_yes_no(self,
            "Restore Application",
            f"Restore this application?\n\n"
            f"Name: {name}\n"
            f"Category: {cat}\n"
            f"Path: {path}"
        )
        if not confirm:
            return

        # Find the full entry (carries args/working_dir, not just the
        # name/path the Treeview happens to display) from trash.
        matching_entry = next(
            (e for c, e in self.trash if c == cat and e["path"] == path), None
        )
        if matching_entry is None:
            return  # shouldn't happen, but be defensive

        # Insert back into category (skip if it's already there, e.g. it was
        # already restored via Undo)
        apps = self.config_manager.categories.get(cat, [])
        if not self._apps_contains_path(apps, path):
            apps.append(matching_entry)
            self.config_manager.save()

        self._remove_from_trash(cat, path)

        # If this is the item Undo would restore, clear it — it's already
        # back, so leaving Undo showing would be stale/misleading (clicking
        # it wouldn't do anything now that the duplicate-guard is in place,
        # but it shouldn't still look actionable).
        if self.last_deleted is not None and self.last_deleted[0] == cat \
                and self.last_deleted[2]["path"] == path:
            self.last_deleted = None
            self._refresh_undo_button()

        # Update trash window
        tree.delete(row_id)

        # Refresh main UI if needed
        if self.current_category == cat:
            self.load_apps(cat)

        self.set_status(f"Restored: {name}")

    # Profile actions

    def populate_profiles(self):
        profs = list(self.config_manager.profiles.keys())
        self.profile_combo.configure(values=profs)
        if profs:
            if self.profile_var.get() not in profs:
                self.profile_combo.set(profs[0])
        else:
            self.profile_var.set("")

    def run_profile(self):
        name = self._require_profile()
        if name is None:
            return
        apps = self.config_manager.get_profile_apps(name)
        if not apps:
            self.dialogs.show_info(self, "Info", f"Profile '{name}' has no categories with apps assigned.")
            return
        self.launcher.launch_list(apps)
        self.set_status(f"Launched profile '{name}' ({len(apps)} app(s))")

    def _select_profile(self, name: str):
        """Refreshes the profile list and switches the combo to `name` —
        shared by new_profile()/rename_profile()."""
        self.populate_profiles()
        self.profile_combo.set(name)

    def new_profile(self):
        name = self.dialogs.ask_string(self, "New Profile", "Enter new profile name:")
        if not name:
            return
        if not self.config_manager.add_profile(name):
            self.dialogs.show_info(self, "Info", f"Profile '{name}' already exists or is invalid.")
            return
        self._select_profile(name)
        self.set_status(f"Created profile '{name}'")
        # Immediately let the user pick categories for it
        self.edit_profile()

    def rename_profile(self):
        old = self._require_profile()
        if old is None:
            return
        new = self.dialogs.ask_string(self, "Rename Profile", f"Rename '{old}' to:")
        if not new:
            return
        if not self.config_manager.rename_profile(old, new):
            self.dialogs.show_info(self, "Info", f"Could not rename '{old}' to '{new}'.")
            return
        self._select_profile(new)
        self.set_status(f"Renamed profile '{old}' to '{new}'")

    def remove_profile(self):
        name = self._require_profile()
        if name is None:
            return
        if not self.dialogs.ask_yes_no(self, "Confirm", f"Delete profile '{name}'? (Categories and apps are unaffected.)"):
            return
        if not self.config_manager.remove_profile(name):
            self.dialogs.show_info(self, "Info", f"Could not remove profile '{name}'.")
            return
        self.populate_profiles()
        self.set_status(f"Removed profile '{name}'")

    def edit_profile(self):
        name = self._require_profile()
        if name is None:
            return
        # Built once and reused (see edit_profile_dialog.py's module
        # docstring for why) rather than a fresh instance per click.
        if self._edit_profile_window is None or not self._edit_profile_window.winfo_exists():
            self._edit_profile_window = EditProfileDialog(self)
        self._edit_profile_window.show_profile(name)
        self._edit_profile_window.deiconify()
        self._edit_profile_window.lift()
        self._edit_profile_window.focus_force()

    # Tray / hotkey / window lifecycle

    def _register_hotkey(self, combo: str):
        """(Re)register the global show-window hotkey. The hotkey fires on a
        background thread, so it schedules the actual UI work via self.after(0, ...)
        rather than touching widgets directly."""
        ok = self.hotkey_manager.register(combo, lambda: self.after(0, self.restore_from_tray))
        return ok

    def open_settings(self):
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.lift()
            self._settings_window.focus_force()
            return
        self._settings_window = SettingsWindow(self)
        self._settings_window.grab_set()

    def set_dark_mode(self, is_dark: bool):
        """Switches the whole app's appearance live, no restart needed. CTk
        widgets (buttons, entries, etc.) follow theme.set_mode() on their
        own; the Treeview is covered by that call too (see
        apply_treeview_style), but the native menu bar needs its own
        colors re-applied directly since restyling it requires a reference
        to the actual Menu widgets, not just the global ttk style."""
        theme.set_mode("dark" if is_dark else "light")
        self._style_menu(self.menu_bar)
        self._style_menu(self.file_menu)

    def _maybe_run_autostart_profile(self):
        """Launches the configured Startup Profile's apps, if one is set.
        Only called from __init__ when start_minimized is True — i.e. only
        at actual Windows login, not on a manual open of the launcher."""
        name = self.config_manager.get_autostart_profile()
        if not name:
            return
        apps = self.config_manager.get_profile_apps(name)
        if not apps:
            log.info("Autostart profile '%s' has no apps to launch — skipping", name)
            return
        self.launcher.launch_list(apps)
        log.info("Autostart: launched %d app(s) from profile '%s'", len(apps), name)

    def minimize_to_tray(self):
        """Called when the window's X button is clicked. Hides the window and
        starts the tray icon (if not already running) instead of quitting."""
        self.withdraw()
        self.tray_icon.start()
        self.set_status("Minimized to tray")
        log.info("Window minimized to tray")

    def restore_from_tray(self):
        """Called from the tray menu ('Show') or the global hotkey. Safe to call
        even if the window is already visible."""
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))  # pop to front, then stop force-pinning
        self.focus_force()
        log.info("Window restored from tray")

    def quit_app(self):
        """Called from the tray menu ('Exit'). Cleanly tears down the hotkey
        listener and tray icon before actually closing the app."""
        log.info("Quit requested from tray menu")
        self.hotkey_manager.unregister()
        self.tray_icon.stop()
        self.after(0, self.destroy)

    # Export / import

    def export_config(self):
        path = filedialog.asksaveasfilename(
            title="Export Config",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            initialfile="launcher_config_export.json"
        )
        if not path:
            return
        if self.config_manager.export_to(path):
            self.set_status(f"Exported config to {path}")
        else:
            self.dialogs.show_error(self, "Export Failed", f"Could not write to:\n{path}")

    def import_config(self):
        path = filedialog.askopenfilename(
            title="Import Config",
            filetypes=[("JSON files", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return

        data = self.config_manager.read_import_file(path)
        if data is None:
            self.dialogs.show_error(self,
                "Import Failed",
                f"'{path}' doesn't look like a valid exported config file."
            )
            return

        incoming_categories = data.get("categories", {})
        incoming_profiles = data.get("profiles", {})

        imported = 0
        skipped = 0
        for name, apps in incoming_categories.items():
            if not isinstance(apps, list):
                continue

            # Match existing categories case-insensitively, same as
            # add_category/rename_category, so importing e.g. "Default"
            # doesn't create a second category alongside an existing
            # "default".
            existing_name = next(
                (c for c in self.config_manager.categories if c.lower() == name.lower()),
                None
            )

            if existing_name is not None:
                choice = self.dialogs.ask_yes_no_cancel(self,
                    "Category Already Exists",
                    f"Category '{existing_name}' already exists.\n\n"
                    f"Yes = merge app lists (no duplicates)\n"
                    f"No = replace your existing '{existing_name}' entirely with the imported one\n"
                    f"Cancel = skip this category, keep yours as-is"
                )
                if choice is None:
                    skipped += 1
                    continue
                mode = "combine" if choice else "replace"
                name = existing_name
            else:
                mode = "add"

            self.config_manager.import_category(name, apps, mode, save=False)
            imported += 1

        # One write for the whole import instead of one per category (plus
        # one more for profiles) — same end state, far less disk I/O.
        self.config_manager.import_profiles(incoming_profiles, save=False)
        self.config_manager.save()

        self.populate_categories()
        self.populate_profiles()

        summary = f"Imported {imported} categor{'y' if imported == 1 else 'ies'}"
        if skipped:
            summary += f", skipped {skipped}"
        self.set_status(summary)
        log.info("Import from %s: %d imported, %d skipped", path, imported, skipped)
