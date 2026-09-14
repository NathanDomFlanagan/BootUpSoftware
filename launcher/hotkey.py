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
import logging
import keyboard

log = logging.getLogger(__name__)


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

        def _safe_callback():
            # The hotkey fires on keyboard's own listener thread. If `callback`
            # raises here, an unhandled exception could kill that thread —
            # silently disabling the hotkey with no visible error. Catch and
            # log instead so the listener keeps running.
            try:
                callback()
            except Exception:
                log.exception("Error handling hotkey '%s'", combo)

        try:
            keyboard.add_hotkey(combo, _safe_callback)
            self._current_combo = combo
            log.info("Registered hotkey '%s'", combo)
            return True
        except Exception:
            log.exception("Failed to register hotkey '%s'", combo)
            return False

    def unregister(self):
        if self._current_combo:
            try:
                keyboard.remove_hotkey(self._current_combo)
                log.info("Unregistered hotkey '%s'", self._current_combo)
            except Exception:
                log.exception("Failed to unregister hotkey '%s'", self._current_combo)
            self._current_combo = None

    @property
    def current_combo(self):
        return self._current_combo