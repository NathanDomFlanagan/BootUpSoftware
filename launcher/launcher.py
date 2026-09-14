"""
Launches configured apps.

Each app entry is a dict: {"path", "name", "args", "working_dir"}. `path` is
usually a normal filesystem path (.exe/.lnk), but may also be a
`shell:AppsFolder\\<AUMID>` pseudo-path identifying a UWP/Store app — that
form isn't a real filesystem path, so it skips the existence check and goes
straight through os.startfile(), which understands the shell namespace
natively (it's a thin wrapper over ShellExecute).

Plain os.startfile(path) — unchanged from before — is used whenever no
arguments/working directory are configured, so the common case behaves
exactly as it always has, including UAC elevation for exes that need it
(ShellExecute honors that; a plain subprocess.Popen would not). Only entries
that explicitly set args/working_dir go through subprocess.Popen instead,
since os.startfile doesn't support passing them on the Python versions this
app supports.
"""
import logging
import os
import shlex
import subprocess
from pathlib import Path
from tkinter import messagebox

log = logging.getLogger(__name__)


class AppLauncher:
    def launch_entry(self, entry: dict):
        path = entry.get("path", "")
        name = entry.get("name") or path
        args = entry.get("args") or ""
        working_dir = entry.get("working_dir") or None

        if path.lower().startswith("shell:"):
            # UWP/Store apps — not a real filesystem path, so there's
            # nothing to existence-check; ShellExecute resolves
            # shell:AppsFolder\<AUMID> natively.
            try:
                os.startfile(path)  # type: ignore[attr-defined]
                log.info("Launched (UWP): %s", name)
            except Exception as e:
                log.exception("Launch failed (UWP): %s", name)
                messagebox.showerror("Launch Error", f"Could not launch:\n{name}\n\n{e}")
            return

        p = Path(path)
        if not p.exists():
            log.warning("Launch failed — file not found: %s", path)
            messagebox.showerror("Launch Error", f"File not found:\n{path}")
            return

        try:
            if args or working_dir:
                subprocess.Popen([str(p), *shlex.split(args)], cwd=working_dir)
            else:
                os.startfile(str(p))  # type: ignore[attr-defined]
            log.info("Launched: %s", name)
        except AttributeError:
            # Fallback for non-Windows (if ever run elsewhere) — os.startfile
            # doesn't exist there at all.
            try:
                subprocess.Popen([str(p), *shlex.split(args)], cwd=working_dir)
                log.info("Launched via subprocess fallback: %s", name)
            except Exception as e:
                log.exception("Launch failed (subprocess fallback): %s", name)
                messagebox.showerror("Launch Error", f"Could not launch:\n{name}\n\n{e}")
        except Exception as e:
            log.exception("Launch failed: %s", name)
            messagebox.showerror("Launch Error", f"Could not launch:\n{name}\n\n{e}")

    def launch_list(self, entries):
        for entry in entries:
            self.launch_entry(entry)
