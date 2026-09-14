"""
Edit Profile dialog — a scrollable checklist of categories to include in a
profile. Canvas + Scrollbar is the standard Tkinter pattern for a scrollable
region, since ttk has no native scrollable frame.
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *


class EditProfileDialog(tb.Toplevel):
    def __init__(self, app, name: str):
        super().__init__(app)
        self.app = app
        self.name = name

        all_cats = list(app.config_manager.categories.keys())
        current = set(app.config_manager.profiles.get(name, []))

        self.title(f"Edit Profile: {name}")
        self.geometry("300x400")

        tb.Label(self, text=f"Select categories for '{name}':").pack(pady=(10, 5))

        # Scrollable list of checkboxes — a plain Frame would just clip once
        # there are more categories than fit in the fixed window height,
        # with no way to reach the rest short of manually resizing the
        # window.
        list_container = tb.Frame(self)
        list_container.pack(fill=BOTH, expand=True, padx=15)

        canvas = tb.Canvas(list_container, highlightthickness=0)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self._canvas = canvas

        list_scrollbar = tb.Scrollbar(list_container, orient="vertical", command=canvas.yview)
        list_scrollbar.pack(side=RIGHT, fill=Y)
        canvas.configure(yscrollcommand=list_scrollbar.set)

        check_frame = tb.Frame(canvas)
        check_frame_window = canvas.create_window((0, 0), window=check_frame, anchor="nw")

        def on_check_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        check_frame.bind("<Configure>", on_check_frame_configure)

        def on_canvas_configure(event):
            # Keep the inner frame's width matched to the canvas so it
            # doesn't get stuck at a stale width if the window is resized.
            canvas.itemconfigure(check_frame_window, width=event.width)

        canvas.bind("<Configure>", on_canvas_configure)

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        # Scope the mousewheel binding to while the cursor is actually over
        # this canvas, rather than binding it globally for the window's
        # whole lifetime.
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        self.vars_by_cat = {}
        for cat in all_cats:
            var = tb.BooleanVar(value=(cat in current))
            self.vars_by_cat[cat] = var
            tb.Checkbutton(
                check_frame, text=cat, variable=var, bootstyle="round-toggle"
            ).pack(anchor=W, pady=2, padx=5)

        self.protocol("WM_DELETE_WINDOW", self._close)

        btn_frame = tb.Frame(self)
        btn_frame.pack(pady=10)
        tb.Button(btn_frame, text="Save", command=self._save_and_close, bootstyle=SUCCESS).grid(row=0, column=0, padx=5)
        tb.Button(btn_frame, text="Cancel", command=self._close, bootstyle=SECONDARY).grid(row=0, column=1, padx=5)

    def _close(self):
        # The mousewheel binding is global (bind_all) while the cursor is
        # over the canvas — make sure it can't outlive the window.
        self._canvas.unbind_all("<MouseWheel>")
        self.destroy()

    def _save_and_close(self):
        selected = [c for c, v in self.vars_by_cat.items() if v.get()]
        self.app.config_manager.set_profile_categories(self.name, selected)
        self.app.set_status(
            f"Updated profile '{self.name}' ({len(selected)} categor{'y' if len(selected) == 1 else 'ies'})"
        )
        self._close()
