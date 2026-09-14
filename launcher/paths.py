"""
Shared path resolution for running from source vs. frozen as a PyInstaller exe.

When frozen, "the app" lives next to the exe (sys.executable); when running
from source, it's this package's own directory. Every module that needs to
find a file alongside the app (config.json, launcher.log, main.py) resolves
it through here, so there's one place that knows how PyInstaller changes
these paths instead of several separate copies of the same branch.
"""
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_dir(reference_file: str = __file__) -> Path:
    """Directory containing the running app: next to the exe when frozen
    with PyInstaller, otherwise the directory of `reference_file` — pass the
    caller's own `__file__` (they all live alongside each other, so any of
    them works, but passing your own keeps `__file__`-patching tests correct)."""
    if is_frozen():
        return Path(sys.executable).parent
    return Path(reference_file).parent


def bundled_dir() -> Path:
    """PyInstaller's temporary extraction directory (onefile builds only).
    Only meaningful when is_frozen() is True."""
    return Path(getattr(sys, "_MEIPASS", app_dir()))
