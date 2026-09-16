"""
Wraps a callback invoked from a background (non-Tkinter) thread so an
unhandled exception gets logged instead of silently killing that thread —
shared by every background listener/callback in this app (the global
hotkey's keyboard-library thread, the tray icon's pystray menu actions)
where a crashed thread would otherwise disable the feature with no visible
error and no way to tell why.
"""
import logging


def safe_call(log: logging.Logger, error_message: str, callback, *args):
    try:
        callback(*args)
    except Exception:
        log.exception(error_message)
