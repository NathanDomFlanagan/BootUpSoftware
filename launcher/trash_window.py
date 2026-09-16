"""
Trash window — shows apps removed this session and lets you restore them.
Takes the LauncherUI instance as `app` and reuses its trash list, config
manager, and restore logic directly rather than duplicating it here.

The list itself stays a plain ttk.Treeview (styled to match the current
light/dark mode via ctk_theme) since CustomTkinter has no equivalent widget;
everything else here is CustomTkinter.
"""
import tkinter.ttk as ttk

import customtkinter as ctk

import ctk_theme as theme
import ctk_widgets as widgets


class TrashWindow(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Trash")
        self.geometry("600x300")

        theme.apply_treeview_style()

        list_frame = ctk.CTkFrame(self, fg_color="transparent")
        list_frame.pack(fill="both", expand=True, padx=theme.PAD_NORMAL, pady=theme.PAD_NORMAL)

        self.tree = ttk.Treeview(list_frame, columns=("category", "name", "path"), show="headings")
        self.tree.bind("<Double-1>", lambda e: self.app.restore_from_trash(self.tree))
        self.tree.heading("category", text="Original Category")
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("category", width=150, anchor="w")
        self.tree.column("name", width=200, anchor="w")
        self.tree.column("path", width=400, anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")

        scrollbar = ctk.CTkScrollbar(list_frame, orientation="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        for cat, entry in self.app.trash:
            self.tree.insert("", "end", values=(cat, entry["name"], entry["path"]))

        widgets.SecondaryButton(self, text="Close", command=self.destroy).pack(pady=theme.PAD_NORMAL)
