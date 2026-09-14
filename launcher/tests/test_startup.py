"""
Tests for startup.py — Run-at-login via the HKCU Run registry key, and the
is_up_to_date() repair detection logic. This specifically guards against the
bug we found in the old shortcut-based implementation where comparing
"expected" against a stale value could trivially match even after the
project folder moved — is_up_to_date() must check real file existence, not
just string equality.

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
        assert startup.StartupManager().enable(True) is False

    def test_is_enabled_false(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().is_enabled() is False

    def test_is_up_to_date_defaults_true_to_avoid_false_repair_prompt(self, monkeypatch):
        monkeypatch.setattr(startup, "WINREG_AVAILABLE", False)
        assert startup.StartupManager().is_up_to_date(True) is True


class TestEnableDisable:
    def test_enable_writes_registry_value(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.enable(start_minimized=True) is True
        assert mgr.is_enabled() is True

    def test_disable_removes_registry_value(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        mgr.enable(True)
        assert mgr.disable() is True
        assert mgr.is_enabled() is False

    def test_disable_when_nothing_registered_is_a_noop_success(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.disable() is True


class TestUpToDateDetection:
    def test_freshly_enabled_is_up_to_date(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        mgr.enable(True)
        assert mgr.is_up_to_date(True) is True

    def test_nothing_registered_counts_as_up_to_date(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        assert mgr.is_up_to_date(True) is True

    def test_moved_project_folder_is_detected_as_stale(self, fake_registry, fake_project, monkeypatch):
        """The core regression test: renaming the project folder after the
        registry entry was created must be detected, even though the
        running process's own __file__ is equally stale and would otherwise
        match the (also stale) stored command trivially."""
        mgr = startup.StartupManager()
        mgr.enable(True)
        assert mgr.is_up_to_date(True) is True  # sanity check before the move

        moved_dir = fake_project.parent / "launcher_MOVED"
        fake_project.rename(moved_dir)

        assert mgr.is_up_to_date(True) is False

    def test_repair_after_move_restores_up_to_date(self, fake_registry, fake_project, monkeypatch):
        mgr = startup.StartupManager()
        mgr.enable(True)

        moved_dir = fake_project.parent / "launcher_MOVED"
        fake_project.rename(moved_dir)
        assert mgr.is_up_to_date(True) is False

        # Simulate restarting the app from the new location
        monkeypatch.setattr(startup, "__file__", str(moved_dir / "startup.py"))
        mgr.enable(True)
        assert mgr.is_up_to_date(True) is True

    def test_toggling_start_minimized_is_detected_as_stale(self, fake_registry, fake_project):
        mgr = startup.StartupManager()
        mgr.enable(start_minimized=True)
        assert mgr.is_up_to_date(start_minimized=False) is False
