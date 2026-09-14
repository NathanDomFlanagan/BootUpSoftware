"""
Tests for startup.py — Run-at-login via the HKCU Run registry key, and the
is_up_to_date() repair detection logic. This specifically guards against two
bugs we found:

1. In the old shortcut-based implementation, comparing "expected" against a
   stale value could trivially match even after the project folder moved —
   is_up_to_date() must check real file existence, not just string equality.
2. The registry command used to conditionally include --startup only when
   the "Start Minimized" preference was on, so a user with that preference
   off never actually got flagged as "launched at startup" at all — silently
   breaking the Startup Profile feature for them. --startup must always be
   present in the registry command; Start Minimized is read live from
   config.json instead of being baked into the command line.

Run with: pytest tests/test_startup.py
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import startup


@pytest.fixture
def fake_registry(monkeypatch):
    """Fakes out winreg with an in-memory dict standing in for the HKCU Run
    key, so registry behavior can be tested without touching the real
    Windows registry."""
    store = {}

    def OpenKey(hive, subkey, *args, **kwargs):
        return object()

    def CloseKey(key):
        pass

    def QueryValueEx(key, name):
        if name not in store:
            raise FileNotFoundError(name)
        return store[name], 1  # 1 = REG_SZ

    def SetValueEx(key, name, reserved, type_, value):
        store[name] = value

    def DeleteValue(key, name):
        if name not in store:
            raise FileNotFoundError(name)
        del store[name]

    fake_winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        KEY_SET_VALUE=1,
        REG_SZ=1,
        OpenKey=OpenKey,
        CloseKey=CloseKey,
        QueryValueEx=QueryValueEx,
        SetValueEx=SetValueEx,
        DeleteValue=DeleteValue,
    )
    monkeypatch.setattr(startup, "WINREG_AVAILABLE", True)
    monkeypatch.setattr(startup, "winreg", fake_winreg)
    return store


@pytest.fixture
def fake_project(tmp_path, monkeypatch):
    """Sets up a fake project folder + fake pythonw.exe, and points
    startup.py's internals at them, standing in for a real install."""
    project_dir = tmp_path / "launcher"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("# entry point")

    python_dir = tmp_path / "python_install"
    python_dir.mkdir()
    (python_dir / "pythonw.exe").write_text("fake interpreter")

    monkeypatch.setattr(startup.sys, "executable", str(python_dir / "python.exe"))
    monkeypatch.setattr(startup, "__file__", str(project_dir / "startup.py"))

    return project_dir


class TestNoWinreg:
    def test_is_available_false(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().is_available() is False

    def test_enable_fails_gracefully(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().enable() is False

    def test_is_enabled_false(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().is_enabled() is False

    def test_is_up_to_date_defaults_true_to_avoid_false_repair_prompt(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().is_up_to_date() is True


class TestEnableDisable:
    def test_enable_writes_registry_value(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.enable() is True
        assert mgr.is_enabled() is True

    def test_enable_always_includes_the_startup_flag(self, fake_registry, fake_project):
        """Regression test: the registry command must always signal
        --startup regardless of the Start Minimized preference — that
        preference is read live from config.json at launch instead, not
        baked into the command line."""
        mgr = startup.StartupManager()
        mgr.enable()
        assert "--startup" in fake_registry[startup.REGISTRY_VALUE_NAME]

    def test_disable_removes_registry_value(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        mgr.enable()
        assert mgr.disable() is True
        assert mgr.is_enabled() is False

    def test_disable_when_nothing_registered_is_a_noop_success(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.disable() is True


class TestUpToDateDetection:
    def test_freshly_enabled_is_up_to_date(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        mgr.enable()
        assert mgr.is_up_to_date() is True

    def test_nothing_registered_counts_as_up_to_date(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.is_up_to_date() is True

    def test_moved_project_folder_is_detected_as_stale(self, fake_registry, fake_project, monkeypatch):
        """The core regression test: renaming the project folder after the
        registry entry was created must be detected, even though the
        running process's own __file__ is equally stale and would otherwise
        match the (also stale) stored command trivially."""
        mgr = startup.StartupManager()
        mgr.enable()
        assert mgr.is_up_to_date() is True  # sanity check before the move

        moved_dir = fake_project.parent / "launcher_MOVED"
        fake_project.rename(moved_dir)

        assert mgr.is_up_to_date() is False

    def test_repair_after_move_restores_up_to_date(self, fake_registry, fake_project, monkeypatch):
        mgr = startup.StartupManager()
        mgr.enable()

        moved_dir = fake_project.parent / "launcher_MOVED"
        fake_project.rename(moved_dir)
        assert mgr.is_up_to_date() is False

        # Simulate restarting the app from the new location
        monkeypatch.setattr(startup, "__file__", str(moved_dir / "startup.py"))
        mgr.enable()
        assert mgr.is_up_to_date() is True
