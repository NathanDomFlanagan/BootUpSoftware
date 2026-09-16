"""
Add App picker — a searchable, multi-select list of apps discovered on this
PC (Start Menu/Desktop shortcuts plus UWP/Store apps), with manual file
browsing available as a fallback for anything not listed (portable exes,
custom scripts, etc.).

Scanning (COM shortcut resolution, and spawning PowerShell for the UWP
list) runs on a background thread — it can take a noticeable moment on a
machine with a large Start Menu, and running it on the main thread would
freeze the whole window while it works. Results are marshalled back via
`self.after(0, ...)`, the same pattern already used for the tray icon and
global hotkey callbacks (see tray.py/hotkey.py).

The list itself stays a plain ttk.Treeview (styled to match the current
light/dark mode via ctk_theme) since CustomTkinter has no equivalent
widget; everything else here is CustomTkinter.
"""
import threading
import tkinter as tk
import tkinter.ttk as ttk

import customtkinter as ctk

from tooltip import ToolTip
import ctk_theme as theme
import ctk_dialogs as dialogs
import ctk_widgets as widgets
import appscan


class AppPickerWindow(ctk.CTkToplevel):
    def __init__(self, app, category: str):
        super().__init__(app)
        self.app = app
        self.category = category
        self.entries = []
        self.unresolved_count = 0
        self.entry_by_row = {}

        self.title("Add App")
        self.geometry("760x480")

        theme.apply_treeview_style()

        widgets.FieldLabel(
            self, text=f"Adding to: {category} — select one or more",
        ).pack(pady=(theme.PAD_NORMAL, 0))

        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=theme.PAD_NORMAL, pady=theme.PAD_NORMAL)

        self.search_var = tk.StringVar()
        search_entry = widgets.ThemedEntry(search_row, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True)
        search_entry.focus_set()
        self.search_var.trace_add("write", lambda *a: self._populate(self.search_var.get()))

        self.refresh_button = widgets.SecondaryButton(
            search_row, text="⟳ Refresh", command=lambda: self._start_scan(refresh=True), width=90,
        )
        self.refresh_button.pack(side="left", padx=(theme.PAD_TIGHT, 0))

        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=theme.PAD_NORMAL)

        # Shows both name and path — a name-only list can't distinguish two
        # shortcuts that share a display name but point at different exes
        # (e.g. two installed versions, or the same app in two Start Menu
        # folders), so there's no way to tell which one you're picking.
        self.tree = ttk.Treeview(
            list_frame, columns=("name", "path"), show="headings", selectmode="extended"
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("name", width=220, anchor="w")
        self.tree.column("path", width=460, anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ctk.CTkScrollbar(list_frame, orientation="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Tooltip for the full path, same pattern as the main app list.
        self._tooltip = ToolTip(self.tree)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self._tooltip.hidetip())

        self.status_var = tk.StringVar(value="Scanning for apps...")
        widgets.MutedLabel(self, textvariable=self.status_var).pack(pady=(theme.PAD_TIGHT, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=theme.PAD_NORMAL)
        widgets.SuccessButton(
            btn_frame, text="✓ Add Selected", command=self._add_selected,
        ).grid(row=0, column=0, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            btn_frame, text="📁 Browse Manually...", command=self._browse_manually,
        ).grid(row=0, column=1, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            btn_frame, text="Cancel", command=self.destroy,
        ).grid(row=0, column=2, padx=theme.PAD_TIGHT)

        self._start_scan(refresh=False)

    def _on_tree_motion(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            self._tooltip.hidetip()
            return
        values = self.tree.item(row_id, "values")
        if not values:
            self._tooltip.hidetip()
            return
        self._tooltip.schedule(values[1])

    def _populate(self, filter_text=""):
        self.tree.delete(*self.tree.get_children())
        self.entry_by_row.clear()
        filter_lower = filter_text.lower()
        for entry in self.entries:
            if filter_lower and filter_lower not in entry.name.lower():
                continue
            row_id = self.tree.insert("", "end", values=(entry.name, entry.target))
            self.entry_by_row[row_id] = entry

    def _status_text(self):
        msg = f"{len(self.entries)} app(s) found" if self.entries else "No apps found in Start Menu or Desktop"
        if self.unresolved_count:
            msg += f" — {self.unresolved_count} shortcut(s) couldn't be read"
        return msg

    def _start_scan(self, refresh: bool):
        self.refresh_button.configure(state="disabled")
        self.status_var.set("Refreshing..." if refresh else "Scanning for apps...")

        def worker():
            lnk_entries, unresolved = appscan.scan_start_menu(refresh=refresh)
            uwp_entries = appscan.scan_uwp_apps(refresh=refresh)
            combined = sorted(lnk_entries + uwp_entries, key=lambda e: e.name.lower())
            self.after(0, lambda: self._on_scan_done(combined, unresolved))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, entries, unresolved_count):
        if not self.winfo_exists():
            return  # window was closed while the scan was running
        self.entries = entries
        self.unresolved_count = unresolved_count
        self._populate(self.search_var.get())
        self.status_var.set(self._status_text())
        self.refresh_button.configure(state="normal")

    def _add_selected(self):
        sel = self.tree.selection()
        if not sel:
            dialogs.show_info(self, "Info", "Select at least one app to add.")
            return
        added = 0
        skipped = 0
        for row_id in sel:
            entry = self.entry_by_row.get(row_id)
            if not entry:
                continue
            if self.app.config_manager.add_app_to_category(self.category, entry.target, name=entry.name):
                added += 1
            else:
                skipped += 1
        self.app.load_apps(self.category)
        msg = f"Added {added} app(s) to '{self.category}'"
        if skipped:
            msg += f" ({skipped} already existed)"
        self.app.set_status(msg)
        self.destroy()

    def _browse_manually(self):
        self.destroy()
        self.app.add_app_manual()
