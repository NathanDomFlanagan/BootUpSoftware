"""
Edit Profile dialog — a scrollable checklist of categories to include in a
profile. CTkScrollableFrame handles the scrolling/mousewheel plumbing
internally, unlike plain ttk which has no scrollable-frame widget at all —
that used to require manually wiring a Canvas + Scrollbar + mousewheel
binding by hand (see the ttkbootstrap version of this file in git history).

CustomTkinter's CTkScrollableFrame registers a handful of application-wide
event bindings (mouse wheel, shift press/release) in its own __init__ and
never removes them in destroy() — a bug in the library itself, not
something fixable from here. Recreating this dialog (and therefore its
CTkScrollableFrame) from scratch on every "Edit Profile" click would leak
a few more stale bindings each time, for the life of the process. Instead,
this dialog is built once and reused: ui.py keeps a single instance alive
and calls show_profile() to repoint it at a different profile, and Save/
Cancel/closing the window all hide it (withdraw) rather than destroy it.
"""
import tkinter as tk

import customtkinter as ctk

import ctk_theme as theme
import ctk_widgets as widgets


class EditProfileDialog(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.name = None
        self.vars_by_cat = {}

        self.geometry("300x400")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        self.title_label = widgets.FieldLabel(self, text="")
        self.title_label.pack(pady=(theme.PAD_NORMAL, theme.PAD_TIGHT))

        self.check_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.check_frame.pack(fill="both", expand=True, padx=theme.PAD_NORMAL)

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=theme.PAD_NORMAL)
        widgets.SuccessButton(
            btn_frame, text="✓ Save", command=self._save,
        ).grid(row=0, column=0, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            btn_frame, text="Cancel", command=self.withdraw,
        ).grid(row=0, column=1, padx=theme.PAD_TIGHT)

    def show_profile(self, name: str):
        """(Re)populates the dialog for `name` instead of building a new
        window — see the module docstring for why. Re-reads the current
        category list fresh each time, since categories may have been
        added/removed since this dialog was last shown."""
        self.name = name
        self.title(f"Edit Profile: {name}")
        self.title_label.configure(text=f"Select categories for '{name}':")

        for widget in self.check_frame.winfo_children():
            widget.destroy()
        self.vars_by_cat = {}

        all_cats = list(self.app.config_manager.categories.keys())
        current = set(self.app.config_manager.profiles.get(name, []))
        for cat in all_cats:
            var = tk.BooleanVar(value=(cat in current))
            self.vars_by_cat[cat] = var
            widgets.PrimaryCheckBox(
                self.check_frame, text=cat, variable=var,
            ).pack(anchor="w", pady=2, padx=theme.PAD_TIGHT)

    def _save(self):
        selected = [c for c, v in self.vars_by_cat.items() if v.get()]
        self.app.config_manager.set_profile_categories(self.name, selected)
        self.app.set_status(
            f"Updated profile '{self.name}' ({len(selected)} categor{'y' if len(selected) == 1 else 'ies'})"
        )
        self.withdraw()
