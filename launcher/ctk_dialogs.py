"""
CTk-styled replacements for tkinter's messagebox/simpledialog.

Those are plain OS-native dialogs that ignore CustomTkinter's appearance
mode entirely — popping up as a light, unstyled window in the middle of an
otherwise fully dark, teal-accented app was the most visually jarring
inconsistency left in the UI. These wrap the same call shape (pass a
parent + text, get a value back) so call sites are a near-drop-in swap:

    messagebox.showinfo("Info", "...")       -> dialogs.show_info(self, "Info", "...")
    messagebox.showerror("Error", "...")     -> dialogs.show_error(self, "Error", "...")
    messagebox.askyesno("Confirm", "...")    -> dialogs.ask_yes_no(self, "Confirm", "...")
    messagebox.askyesnocancel(...)           -> dialogs.ask_yes_no_cancel(self, ...)
    simpledialog.askstring("Title", "...")   -> dialogs.ask_string(self, "Title", "...")

`parent` may be None (e.g. launcher.py has no window reference) — tkinter
resolves that to the default root itself, the same fallback plain
messagebox calls without a `parent=` kwarg already relied on.

Deliberately doesn't use CustomTkinter's own CTkInputDialog for ask_string:
that class's constructor has no way to accept a parent at all (it never
forwards one to its own super().__init__()), so it always attaches to the
default root instead of whichever window actually opened it — the same
problem every dialog here is meant to avoid. _InputDialog below is a
from-scratch CTkToplevel, parented the same way _MessageDialog already is.
"""
import tkinter as tk

import customtkinter as ctk

import ctk_theme as theme
import ctk_widgets as widgets


class _ModalDialog(ctk.CTkToplevel):
    """Base for every custom dialog in this module — handles the modal
    plumbing (Escape/window-close both cancelling, centering on the parent,
    grabbing input focus) so each subclass only has to build its own
    content and call self._finish(value) when done."""

    def __init__(self, parent, title: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.result = None
        self.bind("<Escape>", lambda e: self._finish(None))
        self.protocol("WM_DELETE_WINDOW", lambda: self._finish(None))

    def _finish_setup(self):
        """Call once a subclass has finished building its content widgets:
        centers the dialog on its parent and grabs input focus."""
        self.update_idletasks()
        self._center_on_parent()
        self.grab_set()

    def _center_on_parent(self):
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        parent = self.master
        if parent is not None and parent.winfo_ismapped():
            x = parent.winfo_rootx() + max((parent.winfo_width() - w) // 2, 0)
            y = parent.winfo_rooty() + max((parent.winfo_height() - h) // 2, 0)
        else:
            x = (self.winfo_screenwidth() - w) // 2
            y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    def _finish(self, value):
        self.result = value
        self.grab_release()
        self.destroy()


class _MessageDialog(_ModalDialog):
    """Modal dialog with a message and 1-3 buttons. `buttons` is a list of
    (label, value, button_class) tuples — button_class is one of
    ctk_widgets' themed button classes (SuccessButton, SecondaryButton,
    etc.), reused here rather than re-specifying color/corner-radius kwargs
    by hand as this file used to."""

    def __init__(self, parent, title: str, message: str, buttons: list):
        super().__init__(parent, title)

        ctk.CTkLabel(
            self, text=message, wraplength=360, justify="left",
        ).pack(padx=theme.PAD_LOOSE, pady=(theme.PAD_LOOSE, theme.PAD_NORMAL))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=(0, theme.PAD_LOOSE))
        for i, (label, value, button_cls) in enumerate(buttons):
            button_cls(
                btn_frame, text=label, width=90,
                command=lambda v=value: self._finish(v),
            ).grid(row=0, column=i, padx=theme.PAD_TIGHT)

        # Enter activates the first (primary) button — same keyboard
        # convention as the native dialogs this replaces.
        self.bind("<Return>", lambda e: self._finish(buttons[0][1]))

        self._finish_setup()
        self.focus_set()


class _InputDialog(_ModalDialog):
    """Modal single-line text prompt — see the module docstring for why
    this exists instead of CustomTkinter's own CTkInputDialog."""

    def __init__(self, parent, title: str, prompt: str):
        super().__init__(parent, title)

        ctk.CTkLabel(
            self, text=prompt, wraplength=300, justify="left",
        ).pack(padx=theme.PAD_LOOSE, pady=(theme.PAD_LOOSE, theme.PAD_NORMAL))

        self._entry_var = tk.StringVar()
        entry = widgets.ThemedEntry(self, textvariable=self._entry_var, width=250)
        entry.pack(padx=theme.PAD_LOOSE)
        entry.bind("<Return>", lambda e: self._finish(self._entry_var.get()))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=theme.PAD_LOOSE)
        widgets.PrimaryButton(
            btn_frame, text="OK", width=90, command=lambda: self._finish(self._entry_var.get()),
        ).grid(row=0, column=0, padx=theme.PAD_TIGHT)
        widgets.SecondaryButton(
            btn_frame, text="Cancel", width=90, command=lambda: self._finish(None),
        ).grid(row=0, column=1, padx=theme.PAD_TIGHT)

        self._finish_setup()
        entry.focus_set()


def _run(parent, title, message, buttons):
    dialog = _MessageDialog(parent, title, message, buttons)
    dialog.master.wait_window(dialog)
    return dialog.result


def show_info(parent, title: str, message: str):
    _run(parent, title, message, [("OK", True, widgets.PrimaryButton)])


def show_error(parent, title: str, message: str):
    _run(parent, title, message, [("OK", True, widgets.DangerButton)])


def show_warning(parent, title: str, message: str):
    _run(parent, title, message, [("OK", True, widgets.WarningButton)])


def ask_yes_no(parent, title: str, message: str) -> bool:
    return bool(_run(parent, title, message, [
        ("Yes", True, widgets.SuccessButton),
        ("No", False, widgets.SecondaryButton),
    ]))


def ask_yes_no_cancel(parent, title: str, message: str):
    """Returns True for Yes, False for No, None for Cancel/closed — the same
    three-way contract as tkinter's messagebox.askyesnocancel."""
    return _run(parent, title, message, [
        ("Yes", True, widgets.SuccessButton),
        ("No", False, widgets.SecondaryButton),
        ("Cancel", None, widgets.SecondaryButton),
    ])


def ask_string(parent, title: str, prompt: str):
    """Returns None if cancelled/closed, or the entered text (possibly
    empty) on OK — the same contract as tkinter.simpledialog.askstring."""
    dialog = _InputDialog(parent, title, prompt)
    dialog.master.wait_window(dialog)
    return dialog.result
