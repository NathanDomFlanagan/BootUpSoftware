import os
from pathlib import Path
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, simpledialog, messagebox

from config import Config
from launcher import AppLauncher
from tooltip import ToolTip


class LauncherUI(tb.Window):
    def __init__(self):
        super().__init__(title="App Launcher", themename="darkly")
        self.geometry("800x500")

        self.config_manager = Config()
        self.launcher = AppLauncher()

        self.current_category = None
        self.tooltip = None

        self.create_widgets()
        self.populate_categories()

        self.last_deleted = None  # (category, index, path)S
        self.trash = []  # list of (original_category, path)

    def create_widgets(self):
        # menubar = tb.Menu(self)
        # self.config(menu=menubar)

        # tools_menu = tb.Menu(menubar, tearoff=0)
        # tools_menu.add_command(label="View Trash", command=self.view_trash)

        # menubar.add_cascade(label="Tools", menu=tools_menu)
        

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

        # Bottom buttons
        bottom_frame = tb.Frame(self)
        bottom_frame.pack(pady=10)

        tb.Button(bottom_frame, text="Run All", command=self.run_apps, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(bottom_frame, text="Run Selected", command=self.run_selected, bootstyle=PRIMARY).grid(row=0, column=1, padx=5)
        tb.Button(bottom_frame, text="Add App", command=self.add_app, bootstyle=SECONDARY).grid(row=0, column=2, padx=5)
        tb.Button(bottom_frame, text="Remove App", command=self.remove_app, bootstyle=DANGER).grid(row=0, column=3, padx=5)
        tb.Button(bottom_frame, text="Trash",command=self.view_trash, bootstyle=SECONDARY).grid(row=0, column=4, padx=5)
        tb.Button(bottom_frame,text="Trash", command=self.view_trash, bootstyle=SECONDARY).grid(row=0, column=4, padx=5)



        # Status bar
        self.status_var = tb.StringVar(value="Ready")
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
        self.set_status(f"Renamed category '{old}' to '{new}'")

    def remove_category(self):
        cat = self.category_var.get()
        if not cat:
            return
        if cat == "default":
            messagebox.showwarning("Not allowed", "The 'default' category cannot be removed.")
            return
        if not messagebox.askyesno("Confirm", f"Delete category '{cat}' and all its apps?"):
            return
        if not self.config_manager.remove_category(cat):
            messagebox.showinfo("Info", f"Could not remove category '{cat}'.")
            return
        self.populate_categories()
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
