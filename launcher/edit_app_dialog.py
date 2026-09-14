"""
Edit App dialog — change an app's display name, path, launch arguments, and
working directory. This is the only place in the UI that writes to
args/working_dir; nothing else in the app sets those fields.
"""
from pathlib import Path

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox


class EditAppDialog(tb.Toplevel):
    def __init__(self, app, category: str, index: int, entry: dict):
        super().__init__(app)
        self.app = app
        self.category = category
        self.index = index
        self.is_uwp = entry["path"].lower().startswith("shell:")

        self.title("Edit App")
        self.geometry("480x300")
        self.resizable(False, False)

        state = "disabled" if self.is_uwp else "normal"

        tb.Label(self, text="Name:").grid(row=0, column=0, sticky=W, padx=10, pady=(15, 2))
        self.name_var = tb.StringVar(value=entry["name"])
        tb.Entry(self, textvariable=self.name_var, width=45).grid(row=1, column=0, columnspan=2, sticky=W, padx=10)

        tb.Label(self, text="Path:").grid(row=2, column=0, sticky=W, padx=10, pady=(12, 2))
        self.path_var = tb.StringVar(value=entry["path"])
        tb.Entry(self, textvariable=self.path_var, width=45, state=state).grid(row=3, column=0, sticky=W, padx=10)
        tb.Button(
            self, text="Browse...", command=self._browse_path, bootstyle=SECONDARY, state=state
        ).grid(row=3, column=1, padx=6)

        tb.Label(self, text="Arguments (optional):").grid(row=4, column=0, sticky=W, padx=10, pady=(12, 2))
        self.args_var = tb.StringVar(value=entry.get("args", ""))
        tb.Entry(self, textvariable=self.args_var, width=45, state=state).grid(row=5, column=0, columnspan=2, sticky=W, padx=10)

        tb.Label(self, text="Working directory (optional):").grid(row=6, column=0, sticky=W, padx=10, pady=(12, 2))
        self.working_dir_var = tb.StringVar(value=entry.get("working_dir", ""))
        tb.Entry(self, textvariable=self.working_dir_var, width=45, state=state).grid(row=7, column=0, sticky=W, padx=10)
        tb.Button(
            self, text="Browse...", command=self._browse_working_dir, bootstyle=SECONDARY, state=state
        ).grid(row=7, column=1, padx=6)

        if self.is_uwp:
            tb.Label(
                self,
                text="UWP/Store apps don't support a custom path, arguments, or working directory.",
                bootstyle=SECONDARY, wraplength=440
            ).grid(row=8, column=0, columnspan=2, sticky=W, padx=10, pady=(10, 0))

        btn_frame = tb.Frame(self)
        btn_frame.grid(row=9, column=0, columnspan=2, pady=15)
        tb.Button(btn_frame, text="Save", command=self._save_and_close, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle=SECONDARY).grid(row=0, column=1, padx=5)

    def _browse_path(self):
        chosen = filedialog.askopenfilename(
            title="Select Application or Shortcut",
            filetypes=[("Executables and Shortcuts", "*.exe;*.lnk"), ("All Files", "*.*")]
        )
        if chosen:
            self.path_var.set(chosen)

    def _browse_working_dir(self):
        chosen = filedialog.askdirectory(title="Select Working Directory")
        if chosen:
            self.working_dir_var.set(chosen)

    def _save_and_close(self):
        new_path = self.path_var.get().strip()
        new_name = self.name_var.get().strip()
        if not new_path:
            messagebox.showerror("Invalid", "Path cannot be empty.", parent=self)
            return
        if not self.is_uwp and not Path(new_path).exists():
            if not messagebox.askyesno(
                "Path not found",
                f"'{new_path}' doesn't exist right now. Save anyway?",
                parent=self
            ):
                return
        ok = self.app.config_manager.update_app(
            self.category, self.index,
            path=new_path,
            name=new_name or None,
            args=self.args_var.get().strip(),
            working_dir=self.working_dir_var.get().strip(),
        )
        if not ok:
            messagebox.showerror(
                "Could not save",
                "Another app in this category already uses that path.",
                parent=self
            )
            return
        self.app.load_apps(self.category)
        self.app.set_status(f"Updated: {new_name or Path(new_path).name}")
        self.destroy()
