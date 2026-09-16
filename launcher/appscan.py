"""
Start Menu + Desktop app discovery.

Scans the Start Menu Programs folders and Desktop folders (per-user and
all-users) for .lnk shortcuts, resolves each one's real target via pywin32's
WScript.Shell COM interface (the same one startup.py already uses), and
filters out obvious non-app noise — uninstallers, readmes, broken links,
non-executable targets — so the result is a reasonably clean pick-list
instead of a wall of clutter.

Gracefully degrades if pywin32 isn't installed: returns an empty list rather
than crashing, same pattern as startup.py.

Results are cached in-process after the first scan (see `scan_start_menu`'s
`refresh` argument) since walking every folder and resolving every shortcut
via COM is real work — repeating it on every "Add App" click is wasteful
when nothing's changed since the app started.
"""
import json
import logging
import os
import re
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import pythoncom
    import win32com.client
    WIN32_AVAILABLE = True
except ImportError:
    pythoncom = None
    win32com = None
    WIN32_AVAILABLE = False
    log.warning("pywin32 not installed — Start Menu app discovery is unavailable")

# Shortcut names containing any of these as a whole word (case-insensitive)
# are treated as noise rather than genuine applications and filtered out.
# Whole-word matching (rather than plain substring) avoids false positives
# like "Helpdesk Manager" being filtered for containing "help".
NOISE_KEYWORDS = [
    "uninstall", "read me", "readme", "help", "website", "documentation",
    "changelog", "license", "support", "manual", "release notes",
    "getting started", "report a problem", "bug report",
]
_NOISE_PATTERNS = [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in NOISE_KEYWORDS]

_cache = None  # (entries, skipped_count) from the last .lnk scan, or None
_uwp_cache = None  # list of AppEntry from the last UWP scan, or None


def _shortcut_scan_folders():
    """Every folder to search for .lnk shortcuts: the Start Menu Programs
    folders (per-user and all-users) plus the Desktop folders, so apps that
    only have a desktop icon aren't missed."""
    folders = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        folders.append(Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    programdata = os.environ.get("PROGRAMDATA")
    if programdata:
        folders.append(Path(programdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        folders.append(Path(userprofile) / "Desktop")
    public = os.environ.get("PUBLIC")
    if public:
        folders.append(Path(public) / "Desktop")
    return folders


def _is_noise(name: str) -> bool:
    lowered = name.lower()
    return any(p.search(lowered) for p in _NOISE_PATTERNS)


class AppEntry:
    def __init__(self, name: str, target: str, shortcut_path: str):
        self.name = name
        self.target = target
        self.shortcut_path = shortcut_path


def _sort_by_name(entries: list) -> list:
    """In-place, case-insensitive sort by display name — shared by both
    scan functions so results from either source (or a future one) list in
    the same order."""
    entries.sort(key=lambda e: e.name.lower())
    return entries


def scan_start_menu(refresh: bool = False):
    """Returns (entries, skipped_count):
      - entries: a sorted list of AppEntry for genuine, resolvable
        applications found in the Start Menu or Desktop, with obvious noise
        filtered out.
      - skipped_count: how many shortcuts were found but couldn't actually
        be resolved (e.g. a corrupt .lnk file) — surfaced so a caller can
        hint that some entries were silently dropped, rather than it just
        looking like fewer apps exist than really do.

    Returns ([], 0) if pywin32 is unavailable, or the WScript.Shell COM
    object itself couldn't be created — callers should check
    WIN32_AVAILABLE separately to distinguish "nothing found" from
    "can't scan at all".

    Cached after the first successful scan for the rest of the process —
    pass refresh=True to force a rescan (e.g. after installing something new)."""
    global _cache
    if not WIN32_AVAILABLE:
        return [], 0
    if _cache is not None and not refresh:
        return _cache

    # COM requires CoInitialize on whichever thread uses it. This is often
    # already satisfied implicitly for the main thread (Tkinter and other
    # libraries tend to initialize COM as a side effect), but this function
    # can also run on a plain background thread (see app_picker.py), which
    # starts with no COM apartment at all — Dispatch() then fails with
    # "CoInitialize has not been called." Safe to call even if this thread
    # already has COM initialized (it just increments a per-thread refcount
    # that CoUninitialize decrements, so it never steals another caller's
    # apartment).
    pythoncom.CoInitialize()
    try:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
        except Exception:
            log.exception("Failed to create WScript.Shell for Start Menu scan")
            return [], 0

        results = []
        seen_targets = set()
        skipped = 0

        for folder in _shortcut_scan_folders():
            if not folder.exists():
                continue
            for lnk_path in folder.rglob("*.lnk"):
                name = lnk_path.stem
                if _is_noise(name):
                    continue
                try:
                    shortcut = shell.CreateShortCut(str(lnk_path))
                    target = shortcut.TargetPath
                except Exception:
                    log.debug("Could not resolve shortcut: %s", lnk_path, exc_info=True)
                    skipped += 1
                    continue

                if not target or not target.lower().endswith(".exe"):
                    continue  # skip shortcuts to URLs, docs, installers left behind, etc.
                if not Path(target).exists():
                    continue  # broken/stale shortcut
                if target in seen_targets:
                    continue  # same program listed under more than one shortcut

                seen_targets.add(target)
                results.append(AppEntry(name=name, target=target, shortcut_path=str(lnk_path)))

        _sort_by_name(results)
        log.info(
            "Start Menu/Desktop scan found %d candidate app(s), %d shortcut(s) unresolved",
            len(results), skipped
        )
        _cache = (results, skipped)
        return _cache
    finally:
        pythoncom.CoUninitialize()


def _run_get_start_apps():
    """Runs the `Get-StartApps` PowerShell cmdlet and returns its output as
    a list of {"Name": ..., "AppID": ...} dicts — every Start Menu entry,
    both classic Win32 apps and UWP/Store apps. Needs no pywin32/WinRT
    dependency, just the PowerShell that ships with Windows.

    Returns [] on any failure (PowerShell missing, non-Windows, timeout, bad
    output) — this is a best-effort supplementary source, not a hard
    requirement like the .lnk scan."""
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command",
             "Get-StartApps | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
            # Without this, a GUI app (no console of its own) spawning a
            # console subprocess still gets a briefly-visible console
            # window flash on Windows. getattr() keeps this a no-op on
            # non-Windows, where the attribute doesn't exist.
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired):
        log.debug("Could not run Get-StartApps", exc_info=True)
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError:
        log.debug("Could not parse Get-StartApps output as JSON")
        return []
    if isinstance(data, dict):
        # PowerShell's ConvertTo-Json emits a bare object instead of a
        # single-element array when there's only one result.
        data = [data]
    return data


def scan_uwp_apps(refresh: bool = False):
    """Returns a sorted list of AppEntry for UWP/Store apps, found via the
    Get-StartApps cmdlet. Each entry's target is a
    "shell:AppsFolder\\<AUMID>" pseudo-path — not a real filesystem path,
    but one os.startfile()/ShellExecute understands natively, so no special
    launch mechanism is needed (see AppLauncher.launch_entry, which just
    skips the usual file-existence check for "shell:"-prefixed targets).

    Classic Win32 apps are deliberately excluded here even though
    Get-StartApps lists them too — those are already covered by
    scan_start_menu()'s .lnk scan, which gives a real resolved exe path
    instead of relying on Get-StartApps' inconsistent AppID format for
    non-packaged apps.

    Cached after the first scan for the rest of the process — pass
    refresh=True to force a re-scan."""
    global _uwp_cache
    if _uwp_cache is not None and not refresh:
        return _uwp_cache

    results = []
    for item in _run_get_start_apps():
        name = item.get("Name")
        app_id = item.get("AppID")
        if not name or not app_id:
            continue
        if "!" not in app_id:
            continue  # a classic app's AppID, not a packaged app's AUMID — see docstring
        if _is_noise(name):
            continue
        results.append(AppEntry(name=name, target=f"shell:AppsFolder\\{app_id}", shortcut_path=""))

    _sort_by_name(results)
    log.info("UWP scan found %d app(s)", len(results))
    _uwp_cache = results
    return _uwp_cache