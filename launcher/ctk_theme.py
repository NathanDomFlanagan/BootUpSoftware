"""
Shared CustomTkinter theme setup.

Sets the global appearance mode/color theme once here (must happen before
any CTk widget is created — done at import time since every CTk-based
module imports this first), and provides the semantic button color palette
used across every window, plus helpers to dark/light-style plain
ttk.Treeview and tkinter.Menu widgets so they track the current mode too.

CustomTkinter has no Treeview or Menu equivalent, so every list view in this
app (the main app list, Add App picker, Trash window) stays a plain
tkinter.ttk.Treeview, and the app's menu bar stays a plain tkinter.Menu.
Both render via ttk styles / raw Tk options rather than CustomTkinter's own
canvas-drawing code, so switching CTk's appearance mode does nothing to them
on its own — apply_treeview_style()/menu_colors() below re-derive their
colors from the *current* mode (read via ctk.get_appearance_mode(), which
also resolves "System" to whatever the OS is actually using) so a call to
set_mode() keeps every widget in the window consistent, live, with no
restart needed.

On Windows, the default "vista" ttk theme ignores most color overrides for
Treeview (a long-standing ttk quirk), so apply_treeview_style() also
switches to the "clam" theme — a purely Tcl-drawn theme that actually
honors them.
"""
import tkinter.ttk as ttk

import customtkinter as ctk

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# Accent — teal/cyan instead of CTk's stock blue, used for every "primary"
# interactive element (buttons with no more specific semantic meaning,
# option menus, switches, checkboxes) so the accent is consistent and
# doesn't rely on the built-in theme's default for anything. Used as-is in
# both light and dark mode — it reads fine against either background.
PRIMARY = "#0891b2"
PRIMARY_HOVER = "#0e7490"

SUCCESS = "#2fa572"
SUCCESS_HOVER = "#268a5f"
DANGER = "#c0392b"
DANGER_HOVER = "#a5301f"
WARNING = "#e8a33d"
WARNING_HOVER = "#c98a2e"
SECONDARY = "#565b5e"
SECONDARY_HOVER = "#6c7075"
MUTED_TEXT = "gray60"
DIVIDER_COLOR = "gray30"

# Applied to every button/entry/frame that isn't deliberately square —
# raise for a softer/rounder look, lower for a sharper/flatter one.
CORNER_RADIUS = 10

# Spacing scale — every window previously picked its own padx/pady per
# widget (10 here, 15 there, 5 vs. 6 for button gaps), which reads as
# arbitrary once several windows are open side by side. These three sizes
# replace those ad hoc values everywhere so spacing feels deliberate:
# PAD_TIGHT between closely related controls in the same row (buttons next
# to each other, a field next to its Browse button), PAD_NORMAL for a
# window's outer margins, PAD_LOOSE between distinct sections (above a
# divider, around a field label).
PAD_TIGHT = 6
PAD_NORMAL = 12
PAD_LOOSE = 20

# Plain (family, size[, weight]) tuples rather than ctk.CTkFont instances —
# CTkFont needs a Tk root to already exist, but this module is imported (and
# these constants read) before any window is created; tuples work as a font
# spec everywhere a CTkFont would and carry no such ordering requirement.
FONT_FAMILY = "Segoe UI"
FONT_LABEL = (FONT_FAMILY, 13, "bold")

# Per-mode palettes for the plain-tkinter widgets (Treeview, Menu) that
# don't follow CTk's appearance mode automatically. Keyed by the lowercase
# string ctk.get_appearance_mode() resolves to.
_TREEVIEW_COLORS = {
    "dark": dict(bg="#2b2b2b", fg="white", heading_bg="#3a3a3a", heading_fg="white", heading_active="#454545"),
    "light": dict(bg="#ffffff", fg="black", heading_bg="#e5e5e5", heading_fg="black", heading_active="#d5d5d5"),
}
_MENU_COLORS = {
    "dark": dict(bg="#2b2b2b", fg="white", disabled_fg="gray50"),
    "light": dict(bg="#f5f5f5", fg="black", disabled_fg="gray60"),
}
_TOOLTIP_COLORS = {
    "dark": dict(bg="#3a3a3a", fg="white"),
    "light": dict(bg="#f5f5f5", fg="black"),
}


def get_mode() -> str:
    """Current appearance mode as "dark" or "light" — ctk.get_appearance_mode()
    already resolves "System" to whichever the OS is actually using, so
    callers never need to handle a third case."""
    return ctk.get_appearance_mode().lower()


def set_mode(mode: str):
    """Switches CustomTkinter's global appearance mode and re-styles the
    shared ttk Treeview style to match. CTk widgets update live on their
    own; Treeview needs the explicit nudge since it renders via ttk, not
    CTk's canvas drawing. Native tk.Menu widgets aren't covered here since
    restyling one requires a direct reference to it — callers with a Menu
    open should re-apply menu_colors() to it themselves after calling this."""
    ctk.set_appearance_mode(mode)
    apply_treeview_style()


def menu_colors() -> dict:
    """Color kwargs for tk.Menu.configure(), matching the current mode."""
    return _MENU_COLORS[get_mode()]


def tooltip_colors() -> dict:
    """Color kwargs for the plain tk.Label tooltip.py draws, matching the
    current mode — read fresh each time a tooltip is shown, so it follows
    a live mode switch without needing its own restyle call."""
    return _TOOLTIP_COLORS[get_mode()]


def apply_treeview_style():
    """(Re)configures the shared "Treeview" ttk style to match the current
    appearance mode. ttk styles are global, not per-widget, so one call
    re-colors every Treeview in every open window immediately — safe to
    call both when a window first creates its Treeview and again anytime
    the mode changes at runtime."""
    colors = _TREEVIEW_COLORS[get_mode()]
    style = ttk.Style()
    style.theme_use("clam")
    style.configure(
        "Treeview",
        background=colors["bg"],
        fieldbackground=colors["bg"],
        foreground=colors["fg"],
        borderwidth=0,
        rowheight=24,
    )
    style.map(
        "Treeview",
        background=[("selected", PRIMARY)],
        foreground=[("selected", "white")],
    )
    style.configure(
        "Treeview.Heading",
        background=colors["heading_bg"],
        foreground=colors["heading_fg"],
        borderwidth=0,
        relief="flat",
    )
    style.map("Treeview.Heading", background=[("active", colors["heading_active"])])
