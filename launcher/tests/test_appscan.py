"""
Tests for appscan.py — noise-keyword filtering and the full scan pipeline
(folder walking, shortcut resolution, dedup, existence checks).

win32com only exists on Windows, so these tests fake it out to run
anywhere — same approach used to verify this logic during development.

Run with: pytest tests/test_appscan.py
"""
import json
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import appscan


@pytest.fixture(autouse=True)
def reset_scan_cache():
    """scan_start_menu()/scan_uwp_apps() cache their results at module scope
    — reset both before and after every test so tests don't see each
    other's fake data."""
    appscan._cache = None
    appscan._uwp_cache = None
    yield
    appscan._cache = None
    appscan._uwp_cache = None


class TestNoiseFilter:
    @pytest.mark.parametrize("name,expected_noise", [
        ("Discord", False),
        ("Uninstall Discord", True),
        ("Visual Studio Code", False),
        ("VS Code — Release Notes", True),
        ("Steam", False),
        ("Steam — Bug Report", True),
        ("README", True),
        ("Company Website", True),
        ("Adobe Acrobat Reader DC", False),
        ("Getting Started with Office", True),
        ("Helpdesk Manager", False),  # whole-word match: "help" != "helpdesk"
        ("User Guide and Manual", True),  # "manual" as its own word is still noise
    ])
    def test_is_noise(self, name, expected_noise):
        assert appscan._is_noise(name) == expected_noise


@pytest.fixture
def fake_start_menu(tmp_path, monkeypatch):
    """Builds a fake Start Menu + Desktop on disk plus a fake win32com so
    scan_start_menu() can run end-to-end without a real Windows machine."""
    appdata = tmp_path / "appdata"
    programdata = tmp_path / "programdata"
    userprofile = tmp_path / "userprofile"
    public = tmp_path / "public"
    user_start_menu = appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    user_desktop = userprofile / "Desktop"
    user_start_menu.mkdir(parents=True)
    user_desktop.mkdir(parents=True)

    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("PROGRAMDATA", str(programdata))
    monkeypatch.setenv("USERPROFILE", str(userprofile))
    monkeypatch.setenv("PUBLIC", str(public))

    target_map = {}
    broken_shortcuts = set()

    class FakeShortcut:
        def __init__(self, target):
            self.TargetPath = target

    class FakeShell:
        def CreateShortCut(self, path):
            if path in broken_shortcuts:
                raise OSError("corrupt shortcut")
            return FakeShortcut(target_map.get(path, ""))

    class FakeClientModule:
        def Dispatch(self, name):
            return FakeShell()

    fake_win32com = types.ModuleType("win32com")
    fake_win32com.client = FakeClientModule()
    monkeypatch.setattr(appscan, "WIN32_AVAILABLE", True)
    monkeypatch.setattr(appscan, "win32com", fake_win32com)

    real_apps_dir = tmp_path / "installed_apps"
    real_apps_dir.mkdir()

    def make_shortcut(subfolder_name, shortcut_name, target_path, root=None, broken=False):
        base = root if root is not None else user_start_menu
        folder = base / subfolder_name if subfolder_name else base
        folder.mkdir(exist_ok=True, parents=True)
        lnk = folder / f"{shortcut_name}.lnk"
        lnk.touch()
        if broken:
            broken_shortcuts.add(str(lnk))
        else:
            target_map[str(lnk)] = target_path
        return lnk

    return real_apps_dir, make_shortcut, user_desktop


class TestScanStartMenu:
    def test_no_pywin32_returns_empty(self, monkeypatch):
        monkeypatch.setattr(appscan, "WIN32_AVAILABLE", False)
        assert appscan.scan_start_menu() == ([], 0)

    def test_finds_real_apps_and_filters_noise(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        (real_apps_dir / "steam.exe").write_text("fake")
        (real_apps_dir / "discord.exe").write_text("fake")

        make_shortcut("Valve", "Steam", str(real_apps_dir / "steam.exe"))
        make_shortcut(None, "Discord", str(real_apps_dir / "discord.exe"))
        make_shortcut("Valve", "Steam - Bug Report", str(real_apps_dir / "steam.exe"))
        make_shortcut(None, "Uninstall Discord", "C:/uninstaller.exe")

        results, skipped = appscan.scan_start_menu()
        names = {r.name for r in results}

        assert "Steam" in names
        assert "Discord" in names
        assert "Steam - Bug Report" not in names
        assert "Uninstall Discord" not in names
        assert skipped == 0

    def test_filters_broken_shortcuts(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        make_shortcut(None, "Old Deleted App", "C:/nonexistent/gone.exe")
        results, skipped = appscan.scan_start_menu()
        assert results == []
        assert skipped == 0  # resolved fine, just points nowhere real — not a resolution failure

    def test_filters_non_exe_targets(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        make_shortcut(None, "Company Homepage", "https://example.com")
        results, skipped = appscan.scan_start_menu()
        assert results == []

    def test_dedupes_shortcuts_pointing_at_same_target(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        (real_apps_dir / "steam.exe").write_text("fake")
        make_shortcut(None, "Steam", str(real_apps_dir / "steam.exe"))
        make_shortcut(None, "Steam (desktop copy)", str(real_apps_dir / "steam.exe"))

        results, skipped = appscan.scan_start_menu()
        matching = [r for r in results if r.target == str(real_apps_dir / "steam.exe")]
        assert len(matching) == 1

    def test_also_scans_the_desktop(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        (real_apps_dir / "portable_tool.exe").write_text("fake")
        make_shortcut(None, "Portable Tool", str(real_apps_dir / "portable_tool.exe"), root=user_desktop)

        results, skipped = appscan.scan_start_menu()
        assert "Portable Tool" in {r.name for r in results}

    def test_unresolvable_shortcut_is_counted_as_skipped(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        make_shortcut(None, "Corrupt Shortcut", target_path=None, broken=True)

        results, skipped = appscan.scan_start_menu()
        assert results == []
        assert skipped == 1

    def test_result_is_cached_until_refresh(self, fake_start_menu):
        real_apps_dir, make_shortcut, user_desktop = fake_start_menu
        (real_apps_dir / "steam.exe").write_text("fake")
        make_shortcut(None, "Steam", str(real_apps_dir / "steam.exe"))

        first, _ = appscan.scan_start_menu()
        assert len(first) == 1

        # Installing something new shouldn't show up without a refresh...
        (real_apps_dir / "epic.exe").write_text("fake")
        make_shortcut(None, "Epic Games", str(real_apps_dir / "epic.exe"))
        cached, _ = appscan.scan_start_menu()
        assert len(cached) == 1

        # ...but does once explicitly refreshed.
        refreshed, _ = appscan.scan_start_menu(refresh=True)
        assert len(refreshed) == 2


def _fake_completed_process(stdout="", returncode=0):
    return types.SimpleNamespace(stdout=stdout, returncode=returncode)


class TestScanUwpApps:
    def test_keeps_packaged_apps_and_excludes_classic_ones(self, monkeypatch):
        """Get-StartApps lists both UWP (AUMID contains '!') and classic
        Win32 apps (plain path) — only the packaged ones belong here, since
        classic apps are already covered by scan_start_menu()'s .lnk scan."""
        output = json.dumps([
            {"Name": "Calculator", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"},
            {"Name": "Notepad", "AppID": "C:/Windows/System32/notepad.exe"},
        ])
        monkeypatch.setattr(appscan.subprocess, "run", lambda *a, **k: _fake_completed_process(output))

        results = appscan.scan_uwp_apps()

        names = {r.name for r in results}
        assert "Calculator" in names
        assert "Notepad" not in names
        calc = next(r for r in results if r.name == "Calculator")
        assert calc.target == "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"

    def test_applies_noise_filtering(self, monkeypatch):
        output = json.dumps([
            {"Name": "Uninstall Calculator", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!Uninstall"},
        ])
        monkeypatch.setattr(appscan.subprocess, "run", lambda *a, **k: _fake_completed_process(output))

        results = appscan.scan_uwp_apps()
        assert results == []

    def test_handles_single_result_as_bare_object(self, monkeypatch):
        """ConvertTo-Json emits a bare object instead of a one-element array
        when PowerShell only has a single result."""
        output = json.dumps({"Name": "Calculator", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"})
        monkeypatch.setattr(appscan.subprocess, "run", lambda *a, **k: _fake_completed_process(output))

        results = appscan.scan_uwp_apps()
        assert len(results) == 1
        assert results[0].name == "Calculator"

    def test_returns_empty_on_nonzero_exit(self, monkeypatch):
        monkeypatch.setattr(appscan.subprocess, "run", lambda *a, **k: _fake_completed_process("", returncode=1))
        assert appscan.scan_uwp_apps() == []

    def test_returns_empty_on_invalid_json(self, monkeypatch):
        monkeypatch.setattr(appscan.subprocess, "run", lambda *a, **k: _fake_completed_process("not json"))
        assert appscan.scan_uwp_apps() == []

    def test_returns_empty_when_powershell_unavailable(self, monkeypatch):
        def raise_oserror(*a, **k):
            raise OSError("powershell not found")
        monkeypatch.setattr(appscan.subprocess, "run", raise_oserror)
        assert appscan.scan_uwp_apps() == []

    def test_result_is_cached_until_refresh(self, monkeypatch):
        call_count = {"n": 0}

        def fake_run(*a, **k):
            call_count["n"] += 1
            return _fake_completed_process(json.dumps(
                [{"Name": "Calculator", "AppID": "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"}]
            ))

        monkeypatch.setattr(appscan.subprocess, "run", fake_run)

        appscan.scan_uwp_apps()
        appscan.scan_uwp_apps()
        assert call_count["n"] == 1

        appscan.scan_uwp_apps(refresh=True)
        assert call_count["n"] == 2