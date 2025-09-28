import json
import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import simpledialog

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def load_config():
    if not os.path.exists(CONFIG_PATH):
        # Initialize with an empty default if file is missing
        return {"default": []}
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=4)

class ConfigManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("App Launcher Config Manager")
        self.geometry("580x390")
        self.cfg = load_config()
        self.create_widgets()
        self.refresh_categories()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def create_widgets(self):
        # Category label + dropdown
        tk.Label(self, text="Select Category:").pack(pady=(10, 0))
        self.cat_var = tk.StringVar(self)
        self.cat_menu = tk.OptionMenu(self, self.cat_var, ()) # type: ignore
        self.cat_menu.pack(fill="x", padx=20)

        # Apps listbox
        tk.Label(self, text="Applications in this Category:").pack(pady=(10, 0))
        self.listbox = tk.Listbox(self, height=8)
        self.listbox.pack(fill="both", expand=True, padx=20)

        # Button panel
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="Add App",       command=self.add_app).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="Remove App",    command=self.remove_selected).grid(row=0, column=1, padx=5)
        tk.Button(btn_frame, text="Run Apps",      command=self.run_apps).grid(row=0, column=2, padx=5)
        tk.Button(btn_frame, text="New Category", command=self.new_category).grid(row=0, column=3, padx=5)
        tk.Button(btn_frame, text="Remove Category", command=self.remove_category).grid(row=0, column=4, padx=5)
        tk.Button(btn_frame, text="Save & Exit",   command=self.on_close).grid(row=0, column=5, padx=5)

        # When the dropdown changes, refresh the listbox
        self.cat_var.trace_add("write", lambda *args: self.refresh_apps())

    def refresh_categories(self):
        menu = self.cat_menu["menu"]
        menu.delete(0, "end")
        for cat in self.cfg.keys():
            menu.add_command(label=cat, command=lambda c=cat: self.cat_var.set(c))
        # Select the first category by default
        if self.cfg:
            first = next(iter(self.cfg))
            self.cat_var.set(first)

    def refresh_apps(self):
        self.listbox.delete(0, tk.END)
        apps = self.cfg.get(self.cat_var.get(), [])
        for path in apps:
            self.listbox.insert(tk.END, path)
    
    def new_category(self):
        name = simpledialog.askstring("New Category", "Enter the new category name:")
        if not name:
            return
        name = name.strip().lower()
        if name in self.cfg:
            messagebox.showinfo("Info", f"Category '{name}' already exists.")
            return
        # Add new category
        self.cfg[name] = []
        save_config(self.cfg)
        self.refresh_categories()
        messagebox.showinfo("Success", f"Created new category: '{name}'")
    
    def remove_category(self):
        cat = self.cat_var.get()
        # Prevent nuking your default fallback
        if cat == "default":
            messagebox.showwarning(
                "Cannot Remove",
                "The 'default' category cannot be removed."
            )
            return

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Delete category '{cat}' and all its apps?"
        )
        if not confirm:
            return

        # Remove, persist, and refresh
        del self.cfg[cat]
        save_config(self.cfg)
        self.refresh_categories()
        messagebox.showinfo(
            "Removed",
            f"Category '{cat}' has been removed."
        )


    def add_app(self):
        path = filedialog.askopenfilename(
            title="Select Application or Shortcut",
            filetypes=[("Executables and Shortcuts", "*.exe;*.lnk"), ("All Files", "*.*")]
        )
        if not path:
            return

        cat = self.cat_var.get()
        if path in self.cfg[cat]:
            messagebox.showinfo("Info", "This application is already in the list.")
            return

        # Validate file existence
        if not os.path.exists(path):
            messagebox.showerror("Error", f"File not found:\n{path}")
            return

        self.cfg[cat].append(path)
        save_config(self.cfg)       # persist immediately
        self.refresh_apps()

    def remove_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo("Info", "Please select an app to remove.")
            return

        idx = sel[0]
        cat = self.cat_var.get()
        removed = self.cfg[cat].pop(idx)
        save_config(self.cfg)       # persist immediately
        messagebox.showinfo("Removed", f"Removed:\n{removed}")
        self.refresh_apps()

    def run_apps(self):
        apps = self.cfg.get(self.cat_var.get(), [])
        if not apps:
            messagebox.showinfo("Info", "No applications to run in this category.")
            return

        for path in apps:
            try:
                # Use os.startfile so .lnk and .exe both open correctly
                os.startfile(path)
            except Exception as e:
                messagebox.showerror("Launch Error", f"Could not launch:\n{path}\n\n{e}")

    def on_close(self):
        # Final save and exit
        save_config(self.cfg)
        self.destroy()

if __name__ == "__main__":
    ConfigManager().mainloop()
