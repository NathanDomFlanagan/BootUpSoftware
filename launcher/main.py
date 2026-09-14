import argparse
import logging
import sys

from applog import setup_logging, tk_callback_exception_handler
from ui import LauncherUI

__version__ = "1.0.0"


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