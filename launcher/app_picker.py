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
"""
import threading

import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from tooltip import ToolTip
import appscan


class AppPickerWindow(tb.Toplevel):
    def __init__(self, app, category: str):
        super().__init__(app)
        self.app = app
        self.category = category
        self.entries = []
        self.unresolved_count = 0
        self.entry_by_row = {}

        self.title("Add App")
        self.geometry("760x480")

        tb.Label(self, text=f"Adding to: {category} — select one or more").pack(pady=(10, 0))

        search_row = tb.Frame(self)
        search_row.pack(fill=X, padx=15, pady=10)

        self.search_var = tb.StringVar()
        search_entry = tb.Entry(search_row, textvariable=self.search_var)
        search_entry.pack(side=LEFT, fill=X, expand=True)
        search_entry.focus_set()
        self.search_var.trace_add("write", lambda *a: self._populate(self.search_var.get()))

        self.refresh_button = tb.Button(
            search_row, text="⟳ Refresh", command=lambda: self._start_scan(refresh=True), bootstyle=SECONDARY
        )
        self.refresh_button.pack(side=LEFT, padx=(8, 0))

        list_frame = tb.Frame(self)
        list_frame.pack(fill=BOTH, expand=True, padx=15)

        # Shows both name and path — a name-only list can't distinguish two
        # shortcuts that share a display name but point at different exes
        # (e.g. two installed versions, or the same app in two Start Menu
        # folders), so there's no way to tell which one you're picking.
        self.tree = tb.Treeview(
            list_frame, columns=("name", "path"), show="headings",
            selectmode="extended", bootstyle=INFO
        )
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("name", width=220, anchor=W)
        self.tree.column("path", width=460, anchor=W)
        self.tree.pack(fill=BOTH, expand=True, side=LEFT)

        scrollbar = tb.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Tooltip for the full path, same pattern as the main app list.
        self._tooltip = ToolTip(self.tree)
        self.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.bind("<Leave>", lambda e: self._tooltip.hidetip())

        self.status_var = tb.StringVar(value="Scanning for apps...")
        tb.Label(self, textvariable=self.status_var, bootstyle=SECONDARY).pack(pady=(5, 0))

        btn_frame = tb.Frame(self)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="Add Selected", command=self._add_selected, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(btn_frame, text="Browse Manually...", command=self._browse_manually, bootstyle=SECONDARY).grid(row=0, column=1, padx=5)
        tb.Button(btn_frame, text="Cancel", command=self.destroy, bootstyle=SECONDARY).grid(row=0, column=2, padx=5)

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
            messagebox.showinfo("Info", "Select at least one app to add.")
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
