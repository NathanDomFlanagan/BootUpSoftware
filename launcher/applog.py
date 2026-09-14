"""
Centralized logging setup.

pythonw.exe has no console, so any unhandled exception in the main thread,
a background thread (tray icon, hotkey listener), or a Tkinter callback would
normally vanish with no trace. This module routes all of those into a
rotating log file instead, so a silent crash leaves evidence behind.

Log location matches config.py's path resolution: next to the script when
running from source, next to the exe when frozen with PyInstaller.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from paths import app_dir

LOG_NAME = "launcher.log"


def _resolve_log_path() -> Path:
    return app_dir(__file__) / LOG_NAME


LOG_PATH = _resolve_log_path()

_configured = False


def setup_logging():
    """Call once, early in main(). Safe to call more than once (no-ops after the first)."""
    global _configured
    if _configured:
        return

    handler = RotatingFileHandler(
        LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(threadName)s: %(message)s"
    ))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Route uncaught exceptions on the main thread into the log.
    sys.excepthook = _log_main_thread_exception

    # Route uncaught exceptions on any other thread (tray icon, hotkey
    # listener) into the log. Requires Python 3.8+.
    import threading
    threading.excepthook = _log_background_thread_exception

    _configured = True


def _log_main_thread_exception(exc_type, exc_value, exc_tb):
    logging.getLogger().critical("Unhandled exception (main thread)", exc_info=(exc_type, exc_value, exc_tb))


def _log_background_thread_exception(args):
    thread_name = args.thread.name if args.thread else "unknown"
    logging.getLogger().critical(
        "Unhandled exception in background thread '%s'",
        thread_name,
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


def tk_callback_exception_handler(exc, val, tb):
    """Assign to a Tk instance as `app.report_callback_exception = tk_callback_exception_handler`.
    Catches exceptions raised inside widget callbacks (button clicks, etc.) that
    Tkinter would otherwise only print to stderr — invisible under pythonw."""
    logging.getLogger().error("Unhandled exception in a UI callback", exc_info=(exc, val, tb))