import logging
import os
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, simpledialog, messagebox, Menu

from config import Config
from launcher import AppLauncher
from tooltip import ToolTip
from hotkey import HotkeyManager
from tray import TrayIcon
from startup import StartupManager
from settings_window import SettingsWindow
from trash_window import TrashWindow
from edit_profile_dialog import EditProfileDialog
from edit_app_dialog import EditAppDialog
from app_picker import AppPickerWindow
import appscan

log = logging.getLogger(__name__)


class LauncherUI(tb.Window):
    def __init__(self, launched_at_startup: bool = False):
        super().__init__(title="App Launcher", themename="darkly")
        self.geometry("800x560")

        self.config_manager = Config()
        self.launcher = AppLauncher()

        self.current_category = None
        self.tooltip = None
        self._settings_window = None
        self._trash_window = None

        self.create_widgets()
        self.populate_categories()
        self.populate_profiles()

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
        """Native tk.Menu widgets aren't ttk, so they don't auto-follow the
        ttkbootstrap theme — apply the current theme's palette by hand.
        Note: on Windows the top-level menu *bar* strip is drawn by the OS
        and ignores these colors regardless; only the dropdown panels that
        open from it are actually themeable this way."""
        colors = self.style.colors
        menu.configure(
            background=colors.bg,
            foreground=colors.fg,
            activebackground=colors.selectbg,
            activeforeground=colors.selectfg,
            disabledforeground=colors.border,
            selectcolor=colors.primary,
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

        file_menu = Menu(self.menu_bar, tearoff=False)
        self._style_menu(file_menu)
        file_menu.add_command(label="Export Config...", command=self.export_config)
        file_menu.add_command(label="Import Config...", command=self.import_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.quit_app)
        self.menu_bar.add_cascade(label="File", menu=file_menu)

        self.menu_bar.add_command(label="Settings...", command=self.open_settings)

        # Top frame: category selector
        top_frame = tb.Frame(self)
        top_frame.pack(fill=X, padx=10, pady=10)

        tb.Label(top_frame, text="Category:").pack(side=LEFT)
        self.category_var = tb.StringVar()
        self.category_combo = tb.Combobox(
            top_frame,
            textvariable=self.category_var,
            state="readonly",
            width=30
        )
        self.category_combo.pack(side=LEFT, fill=X, expand=True, padx=10)
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_change)

        # Buttons for category management
        tb.Button(top_frame, text="New", command=self.new_category, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        tb.Button(top_frame, text="Rename", command=self.rename_category, bootstyle=INFO).pack(side=LEFT, padx=5)
        tb.Button(top_frame, text="Delete", command=self.remove_category, bootstyle=DANGER).pack(side=LEFT, padx=5)

        # Treeview for apps
        mid_frame = tb.Frame(self)
        mid_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("name", "path")
        self.tree = tb.Treeview(
            mid_frame,
            columns=columns,
            show="headings",
            bootstyle=INFO
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("path", width=500, anchor=W)
        self.tree.pack(fill=BOTH, expand=True, side=LEFT)

        # Tooltip for full path
        self.tooltip = ToolTip(self.tree)
        self.tree.bind("<Motion>", self.on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self.tooltip.hidetip())
        self.tree.bind("<Double-1>", lambda e: self.edit_app())

        # Scrollbar
        scrollbar = tb.Scrollbar(mid_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Bottom buttons (category-level app actions)
        bottom_frame = tb.Frame(self)
        bottom_frame.pack(pady=(0, 10))

        tb.Button(bottom_frame, text="Run All", command=self.run_apps, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(bottom_frame, text="Run Selected", command=self.run_selected, bootstyle=PRIMARY).grid(row=0, column=1, padx=5)
        tb.Button(bottom_frame, text="Add App", command=self.add_app, bootstyle=SECONDARY).grid(row=0, column=2, padx=5)
        tb.Button(bottom_frame, text="Edit App", command=self.edit_app, bootstyle=INFO).grid(row=0, column=3, padx=5)
        tb.Button(bottom_frame, text="Remove App", command=self.remove_app, bootstyle=DANGER).grid(row=0, column=4, padx=5)
        tb.Button(bottom_frame, text="Trash", command=self.view_trash, bootstyle=SECONDARY).grid(row=0, column=5, padx=5)

        # Separator between categories and profiles
        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=10, pady=(0, 10))

        # Profiles frame: a profile = a named group of categories, run together
        profile_frame = tb.Frame(self)
        profile_frame.pack(fill=X, padx=10, pady=(0, 10))

        tb.Label(profile_frame, text="Profile:").pack(side=LEFT)
        self.profile_var = tb.StringVar()
        self.profile_combo = tb.Combobox(
            profile_frame,
            textvariable=self.profile_var,
            state="readonly",
            width=30
        )
        self.profile_combo.pack(side=LEFT, fill=X, expand=True, padx=10)

        tb.Button(profile_frame, text="Run Profile", command=self.run_profile, bootstyle=PRIMARY).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="New", command=self.new_profile, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Edit", command=self.edit_profile, bootstyle=INFO).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Rename", command=self.rename_profile, bootstyle=INFO).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Delete", command=self.remove_profile, bootstyle=DANGER).pack(side=LEFT, padx=5)

        # Status bar — also carries the current shortcut and the tray-close
        # hint, both low-priority info that doesn't need its own row.
        status_frame = tb.Frame(self)
        status_frame.pack(fill=X, side=BOTTOM)

        self.status_var = tb.StringVar(value="Ready")
        status_label = tb.Label(status_frame, textvariable=self.status_var, anchor=W, bootstyle=SECONDARY)
        status_label.pack(side=LEFT, fill=X, expand=True)

        # Created but not packed yet — it only takes up space in the status
        # bar while there's actually something to undo (see
        # _refresh_undo_button), instead of sitting there disabled at all
        # other times.
        self.undo_button = tb.Button(
            status_frame,
            text="Undo",
            bootstyle=INFO,
            command=self.undo_delete
        )

        self.hotkey_label_var = tb.StringVar(value=f"Shortcut: {self.config_manager.get_hotkey()}")
        self._hotkey_label = tb.Label(status_frame, textvariable=self.hotkey_label_var, bootstyle=SECONDARY)
        self._hotkey_label.pack(side=RIGHT, padx=10)

        tray_note_text = "Closing this window minimizes to the tray — use File ▸ Exit or the tray menu to quit"
        note_label = tb.Label(status_frame, text="ⓘ", bootstyle=SECONDARY, cursor="question_arrow")
        note_label.pack(side=RIGHT, padx=(10, 0))
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
                self.undo_button.pack(side=RIGHT, padx=10, before=self._hotkey_label)
        else:
            self.undo_button.pack_forget()

    def populate_categories(self):
        cats = list(self.config_manager.categories.keys())
        self.category_combo["values"] = cats
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

    def on_category_change(self, event=None):
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
    
    def undo_delete(self):
        if not self.last_deleted:
            return

        category, index, entry = self.last_deleted
        path = entry["path"]

        # Insert back into the list at the original index — but skip if
        # it's already there (e.g. it was already restored via the Trash
        # window before Undo was clicked), otherwise this would duplicate it.
        apps = self.config_manager.categories.get(category, [])
        if not any(e["path"] == path for e in apps):
            apps.insert(index, entry)
            self.config_manager.save()

        # Remove the matching entry from trash so it can't also be restored
        # from there later, which would otherwise create a duplicate.
        self.trash = [
            t for t in self.trash
            if not (t[0] == category and t[1]["path"] == path)
        ]

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

    def new_category(self):
        name = simpledialog.askstring("New Category", "Enter new category name:", parent=self)
        if not name:
            return
        if not self.config_manager.add_category(name):
            messagebox.showinfo("Info", f"Category '{name}' already exists or is invalid.")
            return
        self.populate_categories()
        self.category_combo.set(name)
        self.load_apps(name)
        self.set_status(f"Created category '{name}'")

    def rename_category(self):
        old = self.category_var.get()
        if not old:
            return
        new = simpledialog.askstring("Rename Category", f"Rename '{old}' to:", parent=self)
        if not new:
            return
        if not self.config_manager.rename_category(old, new):
            messagebox.showinfo("Info", f"Could not rename '{old}' to '{new}'.")
            return
        self.populate_categories()
        self.category_combo.set(new)
        self.load_apps(new)
        self.populate_profiles()  # profile category references may have been renamed
        self.set_status(f"Renamed category '{old}' to '{new}'")

    def remove_category(self):
        cat = self.category_var.get()
        if not cat:
            return
        if cat.strip().lower() == "default":
            messagebox.showwarning("Not allowed", "The default category cannot be removed.")
            return
        if not messagebox.askyesno("Confirm", f"Delete category '{cat}' and all its apps?"):
            return
        if not self.config_manager.remove_category(cat):
            messagebox.showinfo("Info", f"Could not remove category '{cat}'.")
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
        if not self.current_category:
            messagebox.showinfo("Info", "Please select a category first.")
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
        if not self.current_category:
            messagebox.showinfo("Info", "Please select a category first.")
            return

        path = filedialog.askopenfilename(
            title="Select Application or Shortcut",
            filetypes=[("Executables and Shortcuts", "*.exe;*.lnk"), ("All Files", "*.*")]
        )
        if not path:
            return

        if not os.path.exists(path):
            messagebox.showerror("Error", f"File not found:\n{path}")
            return

        if not self.config_manager.add_app_to_category(self.current_category, path):
            messagebox.showinfo("Info", "This application is already in the list.")
            return

        self.load_apps(self.current_category)
        self.set_status(f"Added app to '{self.current_category}'")

    def remove_app(self):
        if not self.current_category:
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Please select an app to remove.")
            return

        row_id = sel[0]
        index = self.tree.index(row_id)
        apps = self.config_manager.categories.get(self.current_category, [])
        if index >= len(apps):
            return
        entry = apps[index]

        confirm = messagebox.askyesno(
            "Confirm Removal",
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
            messagebox.showinfo("Info", "Could not remove selected app.")
            return

        self.load_apps(self.current_category)
        self.set_status(f"Removed: {removed['name']}")

    def edit_app(self):
        if not self.current_category:
            return

        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Please select an app to edit.")
            return

        index = self.tree.index(sel[0])
        apps = self.config_manager.categories.get(self.current_category, [])
        if index >= len(apps):
            return

        EditAppDialog(self, self.current_category, index, apps[index])

    def run_apps(self):
        if not self.current_category:
            return
        apps = self.config_manager.categories.get(self.current_category, [])
        if not apps:
            messagebox.showinfo("Info", "No applications to run in this category.")
            return
        self.launcher.launch_list(apps)
        self.set_status(f"Launched {len(apps)} app(s) from '{self.current_category}'")

    def run_selected(self):
        if not self.current_category:
            return
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Info", "Please select an app to run.")
            return
        index = self.tree.index(sel[0])
        apps = self.config_manager.categories.get(self.current_category, [])
        if index >= len(apps):
            return
        entry = apps[index]
        self.launcher.launch_entry(entry)
        self.set_status(f"Launched: {entry['name']}")

    def restore_from_trash(self, tree):
        sel = tree.selection()
        if not sel:
            return

        row_id = sel[0]
        cat, name, path = tree.item(row_id, "values")

        confirm = messagebox.askyesno(
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
        if not any(e["path"] == path for e in apps):
            apps.append(matching_entry)
            self.config_manager.save()

        # Remove from trash
        self.trash = [
            t for t in self.trash
            if not (t[0] == cat and t[1]["path"] == path)
        ]

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
        self.profile_combo["values"] = profs
        if profs:
            if self.profile_var.get() not in profs:
                self.profile_combo.set(profs[0])
        else:
            self.profile_var.set("")

    def run_profile(self):
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("Info", "Please select a profile first.")
            return
        apps = self.config_manager.get_profile_apps(name)
        if not apps:
            messagebox.showinfo("Info", f"Profile '{name}' has no categories with apps assigned.")
            return
        self.launcher.launch_list(apps)
        self.set_status(f"Launched profile '{name}' ({len(apps)} app(s))")

    def new_profile(self):
        name = simpledialog.askstring("New Profile", "Enter new profile name:", parent=self)
        if not name:
            return
        if not self.config_manager.add_profile(name):
            messagebox.showinfo("Info", f"Profile '{name}' already exists or is invalid.")
            return
        self.populate_profiles()
        self.profile_combo.set(name)
        self.set_status(f"Created profile '{name}'")
        # Immediately let the user pick categories for it
        self.edit_profile()

    def rename_profile(self):
        old = self.profile_var.get()
        if not old:
            messagebox.showinfo("Info", "Please select a profile first.")
            return
        new = simpledialog.askstring("Rename Profile", f"Rename '{old}' to:", parent=self)
        if not new:
            return
        if not self.config_manager.rename_profile(old, new):
            messagebox.showinfo("Info", f"Could not rename '{old}' to '{new}'.")
            return
        self.populate_profiles()
        self.profile_combo.set(new)
        self.set_status(f"Renamed profile '{old}' to '{new}'")

    def remove_profile(self):
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("Info", "Please select a profile first.")
            return
        if not messagebox.askyesno("Confirm", f"Delete profile '{name}'? (Categories and apps are unaffected.)"):
            return
        if not self.config_manager.remove_profile(name):
            messagebox.showinfo("Info", f"Could not remove profile '{name}'.")
            return
        self.populate_profiles()
        self.set_status(f"Removed profile '{name}'")

    def edit_profile(self):
        name = self.profile_var.get()
        if not name:
            messagebox.showinfo("Info", "Please select a profile first.")
            return
        EditProfileDialog(self, name)

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
            messagebox.showerror("Export Failed", f"Could not write to:\n{path}")

    def import_config(self):
        path = filedialog.askopenfilename(
            title="Import Config",
            filetypes=[("JSON files", "*.json"), ("All Files", "*.*")]
        )
        if not path:
            return

        data = self.config_manager.read_import_file(path)
        if data is None:
            messagebox.showerror(
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
                choice = messagebox.askyesnocancel(
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

            self.config_manager.import_category(name, apps, mode)
            imported += 1

        self.config_manager.import_profiles(incoming_profiles)

        self.populate_categories()
        self.populate_profiles()

        summary = f"Imported {imported} categor{'y' if imported == 1 else 'ies'}"
        if skipped:
            summary += f", skipped {skipped}"
        self.set_status(summary)
        log.info("Import from %s: %d imported, %d skipped", path, imported, skipped)

