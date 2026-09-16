"""
Thin CustomTkinter subclasses that bake in this app's default styling.

Every dialog file was hand-repeating the same kwarg combinations on nearly
every widget constructor call — `corner_radius=theme.CORNER_RADIUS,
fg_color=theme.PRIMARY, hover_color=theme.PRIMARY_HOVER` and its
SUCCESS/DANGER/SECONDARY/WARNING variants, over and over, across every
window file. These subclasses set those as defaults via
kwargs.setdefault(), so a call site just says
`SuccessButton(parent, text="Save", command=...)` — and can still override
any default (a different color, corner_radius, etc.) by passing it
explicitly, since setdefault() only fills in what wasn't already given.
"""
import customtkinter as ctk

import ctk_theme as theme


def _colored_button(fg_color, hover_color):
    """Returns a CTkButton subclass pre-colored with the given fg/hover
    pair and the shared corner radius."""
    class _Button(ctk.CTkButton):
        def __init__(self, master, **kwargs):
            kwargs.setdefault("corner_radius", theme.CORNER_RADIUS)
            kwargs.setdefault("fg_color", fg_color)
            kwargs.setdefault("hover_color", hover_color)
            super().__init__(master, **kwargs)
    return _Button


PrimaryButton = _colored_button(theme.PRIMARY, theme.PRIMARY_HOVER)
SuccessButton = _colored_button(theme.SUCCESS, theme.SUCCESS_HOVER)
DangerButton = _colored_button(theme.DANGER, theme.DANGER_HOVER)
SecondaryButton = _colored_button(theme.SECONDARY, theme.SECONDARY_HOVER)
WarningButton = _colored_button(theme.WARNING, theme.WARNING_HOVER)


class ThemedEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", theme.CORNER_RADIUS)
        super().__init__(master, **kwargs)


class PrimaryOptionMenu(ctk.CTkOptionMenu):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", theme.CORNER_RADIUS)
        kwargs.setdefault("fg_color", theme.PRIMARY)
        kwargs.setdefault("button_color", theme.PRIMARY)
        kwargs.setdefault("button_hover_color", theme.PRIMARY_HOVER)
        super().__init__(master, **kwargs)


class ThemedSwitch(ctk.CTkSwitch):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", theme.CORNER_RADIUS)
        kwargs.setdefault("progress_color", theme.PRIMARY)
        super().__init__(master, **kwargs)


class PrimaryCheckBox(ctk.CTkCheckBox):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("corner_radius", theme.CORNER_RADIUS)
        kwargs.setdefault("fg_color", theme.PRIMARY)
        kwargs.setdefault("hover_color", theme.PRIMARY_HOVER)
        super().__init__(master, **kwargs)


class FieldLabel(ctk.CTkLabel):
    """A bold section/field label, e.g. "Category:", "Name:"."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("font", theme.FONT_LABEL)
        super().__init__(master, **kwargs)


class MutedLabel(ctk.CTkLabel):
    """Low-emphasis secondary text, e.g. status lines and hints."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("text_color", theme.MUTED_TEXT)
        super().__init__(master, **kwargs)


class Divider(ctk.CTkFrame):
    """A thin horizontal rule separating sections within a window."""
    def __init__(self, master, **kwargs):
        kwargs.setdefault("height", 2)
        kwargs.setdefault("fg_color", theme.DIVIDER_COLOR)
        kwargs.setdefault("corner_radius", 0)
        super().__init__(master, **kwargs)
