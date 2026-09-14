"""
Windows "launch at login" support via the registry Run key.

Adds/removes a value under HKCU\\...\\CurrentVersion\\Run pointing at this
app, which Windows launches automatically at login — the standard mechanism
for a per-user background app. Unlike a Startup-folder shortcut, this needs
only the standard-library `winreg` module, not pywin32.

Gracefully degrades if winreg isn't available (e.g. running on a
non-Windows OS): the feature just reports itself unavailable instead of
crashing the whole app.
"""
import logging
import sys
from pathlib import Path

from paths import app_dir, is_frozen

log = logging.getLogger(__name__)

REGISTRY_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REGISTRY_VALUE_NAME = "App Launcher"

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    winreg = None
    WINREG_AVAILABLE = False
    log.warning("winreg not available — Run at Startup feature is unavailable")


def _expected_command() -> str:
    """The command line the registry value SHOULD hold right now — differs
    depending on whether running from source (via pythonw.exe) or frozen as
    a standalone exe (PyInstaller). Always passes --startup, which signals
    "Windows launched this at login" — that's a fact about how the process
    started, not a preference, so it doesn't vary. Whether to actually
    minimize to tray or auto-launch a profile are separate preferences the
    app reads live from config.json once it's running (see ui.py), rather
    than being baked into the registry command itself."""
    if is_frozen():
        return f'"{sys.executable}" --startup'

    python_dir = Path(sys.executable).parent
    pythonw = python_dir / "pythonw.exe"
    if not pythonw.exists():
        pythonw = Path(sys.executable)  # fall back to python.exe if pythonw.exe is missing
    main_py = app_dir(__file__) / "main.py"
    return f'"{pythonw}" "{main_py}" --startup'


def _files_exist() -> bool:
    """Do the files the current command line would point at actually exist
    on disk right now? This is the check that catches a moved/renamed
    project folder or a reinstalled Python — comparing a stored command
    against a freshly computed one isn't enough on its own, since a stale
    __file__ and a stale stored command would trivially match each other
    while both point nowhere real."""
    if is_frozen():
        return Path(sys.executable).exists()

    python_dir = Path(sys.executable).parent
    pythonw_exists = (python_dir / "pythonw.exe").exists() or Path(sys.executable).exists()
    main_py_exists = (app_dir(__file__) / "main.py").exists()
    return pythonw_exists and main_py_exists


class StartupManager:
    def is_available(self) -> bool:
        return WINREG_AVAILABLE

    def is_enabled(self) -> bool:
        """Source of truth is the registry — always reflects reality, never
        a cached/stale value."""
        if not WINREG_AVAILABLE:
            return False
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_RUN_KEY)
            winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
            winreg.CloseKey(key)
            return True
        except OSError:
            return False

    def is_up_to_date(self) -> bool:
        """True if no entry is registered (nothing to repair), or the
        registered command both (a) points at files that actually exist on
        disk right now, and (b) matches what we'd currently create. False
        means a stale entry — e.g. the project folder was moved, or Python
        was reinstalled to a new location."""
        if not WINREG_AVAILABLE:
            return True
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REGISTRY_RUN_KEY)
            value, _ = winreg.QueryValueEx(key, REGISTRY_VALUE_NAME)
            winreg.CloseKey(key)
        except OSError:
            return True  # nothing registered — nothing to repair

        if not _files_exist():
            return False

        return value == _expected_command()

    def enable(self) -> bool:
        """Writes the registry value, overwriting it if one already exists
        (used both for first-time enable and for repairing/updating)."""
        if not WINREG_AVAILABLE:
            log.warning("Cannot enable Run at Startup — winreg is not available")
            return False
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_RUN_KEY, 0, winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(
                key, REGISTRY_VALUE_NAME, 0, winreg.REG_SZ, _expected_command()
            )
            winreg.CloseKey(key)
            log.info("Startup registry entry created/updated")
            return True
        except OSError:
            log.exception("Failed to create startup registry entry")
            return False

    def disable(self) -> bool:
        if not WINREG_AVAILABLE:
            return True
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, REGISTRY_RUN_KEY, 0, winreg.KEY_SET_VALUE
            )
            try:
                winreg.DeleteValue(key, REGISTRY_VALUE_NAME)
            except FileNotFoundError:
                pass
            winreg.CloseKey(key)
            log.info("Startup registry entry removed")
            return True
        except OSError:
            log.exception("Failed to remove startup registry entry")
            return False
