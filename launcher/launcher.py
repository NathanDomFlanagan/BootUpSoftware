import os
import subprocess
from pathlib import Path
from tkinter import messagebox


class AppLauncher:
    def __init__(self):
        pass

    def launch_path(self, path: str):
        p = Path(path)
        if not p.exists():
            messagebox.showerror("Launch Error", f"File not found:\n{path}")
            return

        try:
            # os.startfile works well for .exe and .lnk on Windows
            os.startfile(str(p))  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback for non-Windows (if ever run elsewhere)
            try:
                subprocess.Popen([str(p)])
            except Exception as e:
                messagebox.showerror("Launch Error", f"Could not launch:\n{path}\n\n{e}")
        except Exception as e:
            messagebox.showerror("Launch Error", f"Could not launch:\n{path}\n\n{e}")

    def launch_list(self, paths):
        for path in paths:
            self.launch_path(path)