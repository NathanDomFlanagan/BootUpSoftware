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
import logging
import os
import re
from pathlib import Path

log = logging.getLogger(__name__)

try:
    import win32com.client
    WIN32_AVAILABLE = True
except ImportError:
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

_cache = None  # (entries, skipped_count) from the last scan, or None


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

    results.sort(key=lambda e: e.name.lower())
    log.info(
        "Start Menu/Desktop scan found %d candidate app(s), %d shortcut(s) unresolved",
        len(results), skipped
    )
    _cache = (results, skipped)
    return _cache