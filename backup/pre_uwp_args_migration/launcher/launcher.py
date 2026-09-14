import logging
import os
import subprocess
from pathlib import Path
from tkinter import messagebox

log = logging.getLogger(__name__)


class AppLauncher:
    def launch_path(self, path: str):
        p = Path(path)
        if not p.exists():
            log.warning("Launch failed — file not found: %s", path)
            messagebox.showerror("Launch Error", f"File not found:\n{path}")
            return

        try:
            # os.startfile works well for .exe and .lnk on Windows
            os.startfile(str(p))  # type: ignore[attr-defined]
            log.info("Launched: %s", path)
        except AttributeError:
            # Fallback for non-Windows (if ever run elsewhere)
            try:
                subprocess.Popen([str(p)])
                log.info("Launched via subprocess fallback: %s", path)
            except Exception as e:
                log.exception("Launch failed (subprocess fallback): %s", path)
                messagebox.showerror("Launch Error", f"Could not launch:\n{path}\n\n{e}")
        except Exception as e:
            log.exception("Launch failed: %s", path)
            messagebox.showerror("Launch Error", f"Could not launch:\n{path}\n\n{e}")

    def launch_list(self, paths):
        for path in paths:
            self.launch_path(path)