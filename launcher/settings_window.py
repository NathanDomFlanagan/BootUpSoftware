"""
Settings window.

A proper panel for changing app-wide preferences (global shortcut, startup
behavior, backup/restore) instead of hunting through menu checkbuttons.
Takes the LauncherUI instance itself as `app`: it's the Tk parent, and its
config_manager/startup_manager/hotkey wiring/export-import methods are
reused directly rather than duplicated here.
"""
import logging

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

log = logging.getLogger(__name__)


class SettingsWindow(tb.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("440x430")
        self.resizable(False, False)

        notebook = tb.Notebook(self)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.general_frame = tb.Frame(notebook)
        self.backup_frame = tb.Frame(notebook)
        notebook.add(self.general_frame, text="General")
        notebook.add(self.backup_frame, text="Backup")

        self._build_general_tab()
        self._build_backup_tab()

        tb.Button(self, text="Close", command=self.destroy, bootstyle=SECONDARY).pack(pady=(0, 10))

    # -- General tab ----------------------------------------------------------

    def _build_general_tab(self):
        f = self.general_frame
        cfg = self.app.config_manager

        tb.Label(f, text="Global shortcut:").grid(row=0, column=0, sticky=W, padx=10, pady=(15, 2))
        self.hotkey_var = tb.StringVar(value=cfg.get_hotkey())
        tb.Entry(f, textvariable=self.hotkey_var, width=22).grid(row=1, column=0, sticky=W, padx=10)
        tb.Button(f, text="Apply", command=self._apply_hotkey, bootstyle=INFO).grid(row=1, column=1, padx=6)

        tb.Separator(f, orient=HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=15)

        if not self.app.startup_manager.is_available():
            tb.Label(
                f, text="Run at Startup is unavailable on this system.", bootstyle=SECONDARY
            ).grid(row=3, column=0, columnspan=2, sticky=W, padx=10)
            return

        self.login_var = tb.BooleanVar(value=self.app.startup_manager.is_enabled())
        tb.Checkbutton(
            f, text="Run at Startup", variable=self.login_var,
            bootstyle="round-toggle", command=self._toggle_run_at_startup
        ).grid(row=3, column=0, columnspan=2, sticky=W, padx=10, pady=2)

        self.minimized_var = tb.BooleanVar(value=cfg.get_start_minimized())
        tb.Checkbutton(
            f, text="Start Minimized", variable=self.minimized_var,
            bootstyle="round-toggle", command=self._toggle_start_minimized
        ).grid(row=4, column=0, columnspan=2, sticky=W, padx=10, pady=2)

        tb.Label(f, text="Startup profile:").grid(row=5, column=0, sticky=W, padx=10, pady=(15, 2))

        profile_names = list(cfg.profiles.keys())
        self._autostart_none = "(None)"
        self.autostart_var = tb.StringVar(value=cfg.get_autostart_profile() or self._autostart_none)
        autostart_combo = tb.Combobox(
            f, textvariable=self.autostart_var,
            values=[self._autostart_none] + profile_names,
            state="readonly" if profile_names else "disabled",
            width=20,
        )
        autostart_combo.grid(row=6, column=0, sticky=W, padx=10)
        autostart_combo.bind("<<ComboboxSelected>>", self._on_autostart_profile_change)
        if not profile_names:
            tb.Label(f, text="Create a profile first.", bootstyle=SECONDARY).grid(
                row=6, column=1, sticky=W, padx=6
            )

        # Holds the repair button, rebuilt whenever startup state changes so
        # it only appears when there's actually something to repair.
        self.repair_frame = tb.Frame(f)
        self.repair_frame.grid(row=7, column=0, columnspan=2, sticky=W, padx=10, pady=(15, 0))
        self._refresh_repair_notice()

    def _refresh_repair_notice(self):
        for widget in self.repair_frame.winfo_children():
            widget.destroy()
        if self.login_var.get() and not self.app.startup_manager.is_up_to_date():
            tb.Button(
                self.repair_frame, text="⚠ Repair Startup Entry...",
                command=self._repair, bootstyle=WARNING
            ).pack()

    def _apply_hotkey(self):
        new_combo = self.hotkey_var.get().strip()
        if not new_combo:
            return
        current = self.app.config_manager.get_hotkey()
        if not self.app._register_hotkey(new_combo):
            messagebox.showerror(
                "Invalid Shortcut",
                f"Could not register '{new_combo}'. It may be invalid or already in use by another app.\n\n"
                f"The previous shortcut ('{current}') is still active.",
                parent=self,
            )
            self.app._register_hotkey(current)
            self.hotkey_var.set(current)
            return
        self.app.config_manager.set_hotkey(new_combo)
        self.app.hotkey_label_var.set(f"Shortcut: {new_combo}")
        self.app.set_status(f"Shortcut changed to '{new_combo}'")

    def _toggle_run_at_startup(self):
        want_enabled = self.login_var.get()
        if want_enabled:
            if not self.app.startup_manager.enable():
                messagebox.showerror(
                    "Startup Error",
                    "Could not create the startup entry. Check launcher.log for details.",
                    parent=self,
                )
                self.login_var.set(False)
                return
            self.app.set_status("Enabled: Run at Startup")
        else:
            if not self.app.startup_manager.disable():
                messagebox.showerror(
                    "Startup Error",
                    "Could not remove the startup entry. Check launcher.log for details.",
                    parent=self,
                )
                self.login_var.set(True)
                return
            self.app.set_status("Disabled: Run at Startup")
        self._refresh_repair_notice()

    def _toggle_start_minimized(self):
        value = self.minimized_var.get()
        self.app.config_manager.set_start_minimized(value)
        # No need to touch the registry entry — the command line it holds
        # doesn't encode this preference; the app reads it live from
        # config.json each time it actually launches at startup.
        self.app.set_status(f"Start minimized at startup: {'On' if value else 'Off'}")
        self._refresh_repair_notice()

    def _on_autostart_profile_change(self, event=None):
        selected = self.autostart_var.get()
        name = "" if selected == self._autostart_none else selected
        self.app.config_manager.set_autostart_profile(name)
        self.app.set_status(
            f"Startup profile set to '{name}'" if name else "Startup profile disabled"
        )

    def _repair(self):
        if self.app.startup_manager.enable():
            self.app.set_status("Startup entry repaired")
        else:
            messagebox.showerror(
                "Startup Error",
                "Could not repair the startup entry. Check launcher.log for details.",
                parent=self,
            )
        self._refresh_repair_notice()

    # -- Backup tab -------------------------------------------------------------

    def _build_backup_tab(self):
        f = self.backup_frame
        tb.Label(f, text="Export or import your categories and profiles.").pack(
            anchor=W, padx=10, pady=(15, 10)
        )
        tb.Button(f, text="Export Config...", command=self.app.export_config, bootstyle=SUCCESS).pack(
            anchor=W, padx=10, pady=4
        )
        tb.Button(f, text="Import Config...", command=self.app.import_config, bootstyle=INFO).pack(
            anchor=W, padx=10, pady=4
        )
