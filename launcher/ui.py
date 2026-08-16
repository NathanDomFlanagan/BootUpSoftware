import os
from pathlib import Path
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, simpledialog, messagebox

from config import Config
from launcher import AppLauncher
from tooltip import ToolTip
from hotkey import HotkeyManager
from tray import TrayIcon


class LauncherUI(tb.Window):
    def __init__(self):
        super().__init__(title="App Launcher", themename="darkly")
        self.geometry("800x560")

        self.config_manager = Config()
        self.launcher = AppLauncher()

        self.current_category = None
        self.tooltip = None

        self.create_widgets()
        self.populate_categories()
        self.populate_profiles()

        self.last_deleted = None  # (category, index, path)
        self.trash = []  # list of (original_category, name, path)

        # Tray + global hotkey setup
        self.tray_icon = TrayIcon(
            app_name="App Launcher",
            on_show=self.restore_from_tray,
            on_exit=self.quit_app,
        )
        self.hotkey_manager = HotkeyManager()
        self._register_hotkey(self.config_manager.get_hotkey())

        # Closing the window (X button) minimizes to tray instead of quitting.
        self.protocol("WM_DELETE_WINDOW", self.minimize_to_tray)

    def create_widgets(self):
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
        tb.Button(bottom_frame, text="Remove App", command=self.remove_app, bootstyle=DANGER).grid(row=0, column=3, padx=5)
        tb.Button(bottom_frame, text="Trash", command=self.view_trash, bootstyle=SECONDARY).grid(row=0, column=4, padx=5)

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

        tb.Button(profile_frame, text="Run Profile", command=self.run_profile, bootstyle=SUCCESS).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="New", command=self.new_profile, bootstyle=INFO).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Edit", command=self.edit_profile, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Rename", command=self.rename_profile, bootstyle=SECONDARY).pack(side=LEFT, padx=5)
        tb.Button(profile_frame, text="Delete", command=self.remove_profile, bootstyle=DANGER).pack(side=LEFT, padx=5)

        # Separator between profiles and settings
        tb.Separator(self, orient=HORIZONTAL).pack(fill=X, padx=10, pady=(0, 10))

        # Settings frame: global hotkey + tray behavior
        settings_frame = tb.Frame(self)
        settings_frame.pack(fill=X, padx=10, pady=(0, 10))

        self.hotkey_label_var = tb.StringVar(value=f"Show shortcut: {self.config_manager.get_hotkey()}")
        tb.Label(settings_frame, textvariable=self.hotkey_label_var).pack(side=LEFT)
        tb.Button(
            settings_frame, text="Change Shortcut", command=self.change_hotkey, bootstyle=SECONDARY
        ).pack(side=LEFT, padx=10)
        tb.Label(
            settings_frame, text="(Closing this window minimizes to the tray — use Exit in the tray menu to quit)",
            bootstyle=SECONDARY
        ).pack(side=LEFT, padx=10)

        # Status bar
        status_frame = tb.Frame(self)
        status_frame.pack(fill=X, side=BOTTOM)

        self.status_var = tb.StringVar(value="Ready")
        status_label = tb.Label(status_frame, textvariable=self.status_var, anchor=W, bootstyle=SECONDARY)
        status_label.pack(side=LEFT, fill=X, expand=True)

        self.undo_button = tb.Button(
            status_frame,
            text="Undo",
            bootstyle=INFO,
            command=self.undo_delete
        )
        self.undo_button.pack(side=RIGHT, padx=10)
        self.undo_button.configure(state="disabled")

    def set_status(self, text: str):
        self.status_var.set(text)

    def populate_categories(self):
        cats = list(self.config_manager.categories.keys())
        self.category_combo["values"] = cats
        if cats:
            self.category_combo.set(cats[0])
            self.load_apps(cats[0])

    def load_apps(self, category: str):
        self.current_category = category
        self.tree.delete(*self.tree.get_children())
        apps = self.config_manager.categories.get(category, [])
        for path in apps:
            name = Path(path).name
            self.tree.insert("", "end", values=(name, path))
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

        category, index, path = self.last_deleted

        # Insert back into the list at the original index
        apps = self.config_manager.categories.get(category, [])
        apps.insert(index, path)
        self.config_manager.save()

        self.load_apps(category)
        self.set_status(f"Restored: {path}")

        # Clear undo buffer
        self.last_deleted = None
        self.undo_button.configure(state="disabled")
    
    def view_trash(self):
        win = tb.Toplevel(self)
        win.title("Trash")
        win.geometry("600x300")

        tree = tb.Treeview(win, columns=("category", "name", "path"), show="headings")
        tree.bind("<Double-1>", lambda e: self.restore_from_trash(tree))
        tree.heading("category", text="Original Category")
        tree.heading("name", text="Name")
        tree.heading("path", text="Path")
        tree.column("category", width=150, anchor=W)
        tree.column("name", width=200, anchor=W)
        tree.column("path", width=400, anchor=W)
        tree.pack(fill=BOTH, expand=True, padx=10, pady=10)

        for cat, name, path in self.trash:
            tree.insert("", "end", values=(cat, name, path))

        tb.Button(win, text="Close", command=win.destroy, bootstyle=SECONDARY).pack(pady=10)

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
        values = self.tree.item(row_id, "values")
        if not values:
            return

        app_name, app_path = values

        confirm = messagebox.askyesno(
            "Confirm Removal",
            f"Remove this application from '{self.current_category}'?\n\n"
            f"Name: {app_name}\n"
            f"Path: {app_path}"
        )
        if not confirm:
            return

        # store for undo
        self.last_deleted = (self.current_category, index, app_path)
        self.undo_button.configure(state="normal")

        # add to trash
        self.trash.append((self.current_category, app_name, app_path))

        removed = self.config_manager.remove_app_from_category(self.current_category, index)
        if removed is None:
            messagebox.showinfo("Info", "Could not remove selected app.")
            return

        self.load_apps(self.current_category)
        self.set_status(f"Removed: {removed}")

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
        values = self.tree.item(sel[0], "values")
        if not values:
            return
        path = values[1]
        self.launcher.launch_path(path)
        self.set_status(f"Launched: {path}")

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

        # Insert back into category
        apps = self.config_manager.categories.get(cat, [])
        apps.append(path)
        self.config_manager.save()

        # Remove from trash
        self.trash = [
            t for t in self.trash
            if not (t[0] == cat and t[1] == name and t[2] == path)
        ]

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

        all_cats = list(self.config_manager.categories.keys())
        current = set(self.config_manager.profiles.get(name, []))

        win = tb.Toplevel(self)
        win.title(f"Edit Profile: {name}")
        win.geometry("300x400")

        tb.Label(win, text=f"Select categories for '{name}':").pack(pady=(10, 5))

        vars_by_cat = {}
        check_frame = tb.Frame(win)
        check_frame.pack(fill=BOTH, expand=True, padx=15)
        for cat in all_cats:
            var = tb.BooleanVar(value=(cat in current))
            vars_by_cat[cat] = var
            tb.Checkbutton(check_frame, text=cat, variable=var, bootstyle="round-toggle").pack(anchor=W, pady=2)

        def save_and_close():
            selected = [c for c, v in vars_by_cat.items() if v.get()]
            self.config_manager.set_profile_categories(name, selected)
            self.set_status(f"Updated profile '{name}' ({len(selected)} categor{'y' if len(selected) == 1 else 'ies'})")
            win.destroy()

        btn_frame = tb.Frame(win)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="Save", command=save_and_close, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(btn_frame, text="Cancel", command=win.destroy, bootstyle=SECONDARY).grid(row=0, column=1, padx=5)

    # Tray / hotkey / window lifecycle

    def _register_hotkey(self, combo: str):
        """(Re)register the global show-window hotkey. The hotkey fires on a
        background thread, so it schedules the actual UI work via self.after(0, ...)
        rather than touching widgets directly."""
        ok = self.hotkey_manager.register(combo, lambda: self.after(0, self.restore_from_tray))
        return ok

    def change_hotkey(self):
        current = self.config_manager.get_hotkey()
        new_combo = simpledialog.askstring(
            "Change Shortcut",
            "Enter a key combo (e.g. ctrl+alt+l):",
            initialvalue=current,
            parent=self
        )
        if not new_combo:
            return
        if not self._register_hotkey(new_combo):
            messagebox.showerror(
                "Invalid Shortcut",
                f"Could not register '{new_combo}'. It may be invalid or already in use by another app.\n\n"
                f"The previous shortcut ('{current}') is still active."
            )
            self._register_hotkey(current)  # restore the old one
            return
        self.config_manager.set_hotkey(new_combo)
        self.hotkey_label_var.set(f"Show shortcut: {new_combo}")
        self.set_status(f"Shortcut changed to '{new_combo}'")

    def minimize_to_tray(self):
        """Called when the window's X button is clicked. Hides the window and
        starts the tray icon (if not already running) instead of quitting."""
        self.withdraw()
        self.tray_icon.start()
        self.set_status("Minimized to tray")

    def restore_from_tray(self):
        """Called from the tray menu ('Show') or the global hotkey. Safe to call
        even if the window is already visible."""
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(100, lambda: self.attributes("-topmost", False))  # pop to front, then stop force-pinning
        self.focus_force()

    def quit_app(self):
        """Called from the tray menu ('Exit'). Cleanly tears down the hotkey
        listener and tray icon before actually closing the app."""
        self.hotkey_manager.unregister()
        self.tray_icon.stop()
        self.after(0, self.destroy)