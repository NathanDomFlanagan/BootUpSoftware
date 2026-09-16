"""
Settings window — CustomTkinter pilot.

A proper panel for changing app-wide preferences (global shortcut, startup
behavior, backup/restore) instead of hunting through menu checkbuttons.
Takes the LauncherUI instance itself as `app`: it's the Tk parent, and its
config_manager/startup_manager/hotkey wiring/export-import methods are
reused directly rather than duplicated here.

Built with CustomTkinter — see ctk_theme.py for the shared color palette
and global appearance setup.
"""
import logging
import tkinter as tk

import customtkinter as ctk

import ctk_theme as theme
import ctk_dialogs as dialogs
import ctk_widgets as widgets

log = logging.getLogger(__name__)


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Settings")
        self.geometry("440x430")
        self.resizable(False, False)

        tabview = ctk.CTkTabview(
            self, corner_radius=theme.CORNER_RADIUS,
            segmented_button_selected_color=theme.PRIMARY,
            segmented_button_selected_hover_color=theme.PRIMARY_HOVER,
        )
        tabview.pack(fill="both", expand=True, padx=theme.PAD_NORMAL, pady=theme.PAD_NORMAL)
        tabview.add("General")
        tabview.add("Backup")
        self.general_frame = tabview.tab("General")
        self.backup_frame = tabview.tab("Backup")

        self._build_general_tab()
        self._build_backup_tab()

        widgets.SecondaryButton(self, text="Close", command=self.destroy).pack(pady=(0, theme.PAD_NORMAL))

    # -- General tab ----------------------------------------------------------

    def _build_general_tab(self):
        f = self.general_frame
        cfg = self.app.config_manager

        # Appearance comes first — it's not tied to startup_manager
        # availability like everything below, so it needs to render even on
        # the early-return path a few lines down.
        self.dark_mode_var = tk.BooleanVar(value=cfg.get_dark_mode())
        widgets.ThemedSwitch(
            f, text="Dark Mode", variable=self.dark_mode_var,
            command=self._toggle_dark_mode,
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 2))

        widgets.Divider(f).grid(row=1, column=0, columnspan=2, sticky="ew", padx=theme.PAD_NORMAL, pady=theme.PAD_LOOSE)

        widgets.FieldLabel(f, text="Global shortcut:").grid(row=2, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(0, 4))
        self.hotkey_var = tk.StringVar(value=cfg.get_hotkey())
        widgets.ThemedEntry(
            f, textvariable=self.hotkey_var, width=160,
        ).grid(row=3, column=0, sticky="w", padx=theme.PAD_NORMAL)
        widgets.PrimaryButton(
            f, text="✓ Apply", command=self._apply_hotkey, width=90,
        ).grid(row=3, column=1, padx=theme.PAD_TIGHT)

        widgets.Divider(f).grid(row=4, column=0, columnspan=2, sticky="ew", padx=theme.PAD_NORMAL, pady=theme.PAD_LOOSE)

        if not self.app.startup_manager.is_available():
            widgets.MutedLabel(
                f, text="Run at Startup is unavailable on this system."
            ).grid(row=5, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL)
            return

        self.login_var = tk.BooleanVar(value=self.app.startup_manager.is_enabled())
        widgets.ThemedSwitch(
            f, text="Run at Startup", variable=self.login_var,
            command=self._toggle_run_at_startup,
        ).grid(row=5, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL, pady=2)

        self.minimized_var = tk.BooleanVar(value=cfg.get_start_minimized())
        widgets.ThemedSwitch(
            f, text="Start Minimized", variable=self.minimized_var,
            command=self._toggle_start_minimized,
        ).grid(row=6, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL, pady=2)

        widgets.FieldLabel(f, text="Startup profile:").grid(row=7, column=0, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 4))

        profile_names = list(cfg.profiles.keys())
        self._autostart_none = "(None)"
        self.autostart_var = tk.StringVar(value=cfg.get_autostart_profile() or self._autostart_none)
        autostart_menu = widgets.PrimaryOptionMenu(
            f, variable=self.autostart_var,
            values=[self._autostart_none] + profile_names,
            command=self._on_autostart_profile_change,
            width=160,
            state="normal" if profile_names else "disabled",
        )
        autostart_menu.grid(row=8, column=0, sticky="w", padx=theme.PAD_NORMAL)
        if not profile_names:
            widgets.MutedLabel(f, text="Create a profile first.").grid(
                row=8, column=1, sticky="w", padx=theme.PAD_TIGHT
            )

        # Holds the repair button, rebuilt whenever startup state changes so
        # it only appears when there's actually something to repair.
        self.repair_frame = ctk.CTkFrame(f, fg_color="transparent")
        self.repair_frame.grid(row=9, column=0, columnspan=2, sticky="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, 0))
        self._refresh_repair_notice()

    def _toggle_dark_mode(self):
        is_dark = self.dark_mode_var.get()
        self.app.config_manager.set_dark_mode(is_dark)
        self.app.set_dark_mode(is_dark)
        self.app.set_status(f"Appearance: {'Dark' if is_dark else 'Light'} mode")

    def _refresh_repair_notice(self):
        for widget in self.repair_frame.winfo_children():
            widget.destroy()
        if self.login_var.get() and not self.app.startup_manager.is_up_to_date():
            widgets.WarningButton(
                self.repair_frame, text="⚠ Repair Startup Entry...", command=self._repair,
            ).pack()

    def _apply_hotkey(self):
        new_combo = self.hotkey_var.get().strip()
        if not new_combo:
            return
        current = self.app.config_manager.get_hotkey()
        if not self.app._register_hotkey(new_combo):
            dialogs.show_error(
                self, "Invalid Shortcut",
                f"Could not register '{new_combo}'. It may be invalid or already in use by another app.\n\n"
                f"The previous shortcut ('{current}') is still active.",
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
                dialogs.show_error(
                    self, "Startup Error",
                    "Could not create the startup entry. Check launcher.log for details.",
                )
                self.login_var.set(False)
                return
            self.app.set_status("Enabled: Run at Startup")
        else:
            if not self.app.startup_manager.disable():
                dialogs.show_error(
                    self, "Startup Error",
                    "Could not remove the startup entry. Check launcher.log for details.",
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

    def _on_autostart_profile_change(self, selected_value=None):
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
            dialogs.show_error(
                self, "Startup Error",
                "Could not repair the startup entry. Check launcher.log for details.",
            )
        self._refresh_repair_notice()

    # -- Backup tab -------------------------------------------------------------

    def _build_backup_tab(self):
        f = self.backup_frame
        ctk.CTkLabel(f, text="Export or import your categories and profiles.").pack(
            anchor="w", padx=theme.PAD_NORMAL, pady=(theme.PAD_LOOSE, theme.PAD_NORMAL)
        )
        widgets.SuccessButton(
            f, text="⬆ Export Config...", command=self.app.export_config,
        ).pack(anchor="w", padx=theme.PAD_NORMAL, pady=4)
        widgets.PrimaryButton(
            f, text="⬇ Import Config...", command=self.app.import_config,
        ).pack(anchor="w", padx=theme.PAD_NORMAL, pady=4)
