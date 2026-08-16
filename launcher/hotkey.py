"""
Global keyboard shortcut support.

Uses the `keyboard` library (pip install keyboard) which listens system-wide
on Windows, so the hotkey works even when the app is minimized to the tray
or another window has focus.

Important: the callback fires on a background thread owned by `keyboard`,
not the Tkinter main thread. Tkinter is not thread-safe, so callers must
marshal back onto the main thread themselves (e.g. via `root.after(0, ...)`)
rather than touching widgets directly inside the callback.
"""
import keyboard


class HotkeyManager:
    def __init__(self):
        self._current_combo = None

    def register(self, combo: str, callback) -> bool:
        """Register `combo` (e.g. 'ctrl+alt+l') to call `callback` when pressed.
        Replaces any previously registered hotkey. Returns False if the combo
        is invalid or could not be registered (e.g. reserved by the OS)."""
        self.unregister()
        combo = combo.strip().lower()
        if not combo:
            return False
        try:
            keyboard.add_hotkey(combo, callback)
            self._current_combo = combo
            return True
        except Exception:
            return False

    def unregister(self):
        if self._current_combo:
            try:
                keyboard.remove_hotkey(self._current_combo)
            except Exception:
                pass
            self._current_combo = None

    @property
    def current_combo(self):
        return self._current_combo