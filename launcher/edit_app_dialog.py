"""
Edit App dialog — change an app's display name, path, launch arguments, and
working directory. This is the only place in the UI that writes to
args/working_dir; nothing else in the app sets those fields.
"""
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog

import ctk_theme as theme
import ctk_dialogs as dialogs
import ctk_widgets as widgets
from launcher import EXECUTABLE_FILETYPES


class EditAppDialog(ctk.CTkToplevel):
    def __init__(self, app, category: str, index: int, entry: dict):
        super().__init__(app)
        self.app = app
        self.category = category
        self.index = index
        self.is_uwp = entry.get("type") == "uwp"

        self.title("Edit App")
        self.geometry("480x320")
        self.resizable(False, False)

        state = "disabled" if self.is_uwp else "normal"

        widgets.FieldLabel(self, text="Name:").grid(row=0, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 4))
        self.name_var = tk.StringVar(value=entry["name"])
        widgets.ThemedEntry(self, textvariable=self.name_var, width=380).grid(
            row=1, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL
        )

        widgets.FieldLabel(self, text="Path:").grid(row=2, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 4))
        self.path_var = tk.StringVar(value=entry["path"])
        widgets.ThemedEntry(
            self, textvariable=self.path_var, width=310, state=state,
        ).grid(row=3, column=0, sticky="w", padx=theme.PAD_NORMAL)
        widgets.SecondaryButton(
            self, text="📁 Browse...", command=self._browse_path, state=state, width=100,
        ).grid(row=3, column=1, padx=theme.PAD_TIGHT)

        widgets.FieldLabel(self, text="Arguments (optional):").grid(row=4, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 4))
        self.args_var = tk.StringVar(value=entry.get("args", ""))
        widgets.ThemedEntry(
            self, textvariable=self.args_var, width=380, state=state,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL)

        widgets.FieldLabel(self, text="Working directory (optional):").grid(row=6, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 4))
        self.working_dir_var = tk.StringVar(value=entry.get("working_dir", ""))
        widgets.ThemedEntry(
            self, textvariable=self.working_dir_var, width=310, state=state,
        ).grid(row=7, column=0, sticky="w", padx=theme.PAD_NORMAL)
        widgets.SecondaryButton(
            self, text="📁 Browse...", command=self._browse_working_dir, state=state, width=100,
        ).grid(row=7, column=1, padx=theme.PAD_TIGHT)

        if self.is_uwp:
            widgets.MutedLabel(
                self,
                text="UWP/Store apps don't support a custom path, arguments, or working directory.",
                wraplength=440, justify="left",
            ).grid(row=8, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_NORMAL, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=9, column=0, columnspan=2, pady=theme.PAD_LOOSE)
        widgets.SuccessButton(
            btn_frame, text="✓ Save", command=self._save_and_close,
        ).grid(row=0, column=0, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            btn_frame, text="Cancel", command=self.destroy,
        ).grid(row=0, column=1, padx=theme.PAD_TIGHT)

    def _browse_path(self):
        chosen = filedialog.askopenfilename(
            title="Select Application or Shortcut",
            filetypes=EXECUTABLE_FILETYPES
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
            dialogs.show_error(self, "Invalid", "Path cannot be empty.")
            return
        if not self.is_uwp and not Path(new_path).exists():
            if not dialogs.ask_yes_no(
                self, "Path not found",
                f"'{new_path}' doesn't exist right now. Save anyway?",
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
            dialogs.show_error(
                self, "Could not save",
                "Another app in this category already uses that path.",
            )
            return
        self.app.load_apps(self.category)
        self.app.set_status(f"Updated: {new_name or Path(new_path).name}")
        self.destroy()
