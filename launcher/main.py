import argparse
import logging
import sys

from applog import setup_logging, tk_callback_exception_handler
from ui import LauncherUI


def main():
    setup_logging()
    log = logging.getLogger()
    log.info("=== App starting (args: %s) ===", sys.argv[1:])

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--startup",
        action="store_true",
        help="Start minimized to the system tray instead of showing the window (used by the Windows startup shortcut)"
    )
    args = parser.parse_args()

    try:
        app = LauncherUI(start_minimized=args.startup)
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