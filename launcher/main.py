import argparse
import logging
import os
import sys

from applog import setup_logging, tk_callback_exception_handler
from paths import is_frozen
from ui import LauncherUI

__version__ = "1.0.0"


def _stop_leaking_tcl_tk_paths_to_launched_apps():
    """PyInstaller's frozen bootloader sets TCL_LIBRARY/TK_LIBRARY so this
    process can find its own bundled Tcl/Tk — necessary for Tkinter to
    start up at all when frozen. But Windows processes inherit their
    parent's environment, so every app this launcher opens (and anything
    *that* app goes on to open — e.g. a terminal inside a code editor)
    would otherwise inherit those paths too. If any of them are themselves
    Tcl/Tk-based, they'd try to load a Tcl/Tk version meant only for this
    app's own bundle and fail with a version-conflict error.

    Tkinter only reads these variables once, at interpreter creation, so
    it's safe to remove them right after our own window exists — every
    subsequent os.startfile() call this app makes (Run All, Run Selected,
    Run Profile, the Startup Profile) then launches with a clean
    environment instead, with no change to how launching itself works."""
    if not is_frozen():
        return
    os.environ.pop("TCL_LIBRARY", None)
    os.environ.pop("TK_LIBRARY", None)


def main():
    setup_logging()
    log = logging.getLogger()
    log.info("=== App Launcher v%s starting (args: %s) ===", __version__, sys.argv[1:])

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--startup",
        action="store_true",
        help="Indicates this launch was triggered by the Windows Run at Startup entry "
             "(rather than a manual open) — controls whether Start Minimized and the "
             "Startup Profile apply, both read from config.json"
    )
    args = parser.parse_args()

    try:
        app = LauncherUI(launched_at_startup=args.startup)
        _stop_leaking_tcl_tk_paths_to_launched_apps()
        # Catches exceptions raised inside widget callbacks (button clicks,
        # dialogs, etc.) — Tkinter would otherwise only print these to
        # stderr, which pythonw has no console to show.
        app.report_callback_exception = tk_callback_exception_handler
        app.mainloop()
    except Exception:
        log.critical("Fatal error during startup or mainloop", exc_info=True)
        raise
    finally:
        log.info("=== App exiting ===")

if __name__ == "__main__":
    main()