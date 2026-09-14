"""
Trash window — shows apps removed this session and lets you restore them.
Takes the LauncherUI instance as `app` and reuses its trash list, config
manager, and restore logic directly rather than duplicating it here.
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *


class TrashWindow(tb.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Trash")
        self.geometry("600x300")

        list_frame = tb.Frame(self)
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.tree = tb.Treeview(list_frame, columns=("category", "name", "path"), show="headings")
        self.tree.bind("<Double-1>", lambda e: self.app.restore_from_trash(self.tree))
        self.tree.heading("category", text="Original Category")
        self.tree.heading("name", text="Name")
        self.tree.heading("path", text="Path")
        self.tree.column("category", width=150, anchor=W)
        self.tree.column("name", width=200, anchor=W)
        self.tree.column("path", width=400, anchor=W)
        self.tree.pack(fill=BOTH, expand=True, side=LEFT)

        scrollbar = tb.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        for cat, entry in self.app.trash:
            self.tree.insert("", "end", values=(cat, entry["name"], entry["path"]))

        tb.Button(self, text="Close", command=self.destroy, bootstyle=SECONDARY).pack(pady=10)
