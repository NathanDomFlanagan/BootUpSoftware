"""
Tests for launcher.py — AppLauncher.launch_entry()'s three launch paths:
plain os.startfile (the common, unchanged case), subprocess.Popen (only when
args/working_dir are set), and the shell:AppsFolder pseudo-path used for
UWP/Store apps (skips the filesystem existence check entirely).

Run with: pytest tests/test_launcher.py
(or just: python -m pytest tests/)
"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from launcher import AppLauncher


class TestPlainLaunch:
    def test_launches_via_os_startfile_when_no_args_or_working_dir(self, tmp_path):
        exe = tmp_path / "app.exe"
        exe.write_text("fake")
        entry = {"path": str(exe), "name": "app.exe", "args": "", "working_dir": ""}

        with patch("launcher.os.startfile") as mock_startfile, \
             patch("launcher.subprocess.Popen") as mock_popen:
            AppLauncher().launch_entry(entry)

        mock_startfile.assert_called_once_with(str(exe))
        mock_popen.assert_not_called()

    def test_shows_error_and_does_not_launch_when_file_missing(self, tmp_path):
        entry = {"path": str(tmp_path / "gone.exe"), "name": "gone.exe", "args": "", "working_dir": ""}

        with patch("launcher.os.startfile") as mock_startfile, \
             patch("launcher.messagebox.showerror") as mock_error:
            AppLauncher().launch_entry(entry)

        mock_startfile.assert_not_called()
        mock_error.assert_called_once()


class TestArgsAndWorkingDir:
    def test_uses_subprocess_when_args_are_set(self, tmp_path):
        exe = tmp_path / "app.exe"
        exe.write_text("fake")
        entry = {"path": str(exe), "name": "app.exe", "args": "--flag value", "working_dir": ""}

        with patch("launcher.os.startfile") as mock_startfile, \
             patch("launcher.subprocess.Popen") as mock_popen:
            AppLauncher().launch_entry(entry)

        mock_startfile.assert_not_called()
        mock_popen.assert_called_once_with([str(exe), "--flag", "value"], cwd=None)

    def test_uses_subprocess_when_only_working_dir_is_set(self, tmp_path):
        exe = tmp_path / "app.exe"
        exe.write_text("fake")
        entry = {"path": str(exe), "name": "app.exe", "args": "", "working_dir": str(tmp_path)}

        with patch("launcher.os.startfile") as mock_startfile, \
             patch("launcher.subprocess.Popen") as mock_popen:
            AppLauncher().launch_entry(entry)

        mock_startfile.assert_not_called()
        mock_popen.assert_called_once_with([str(exe)], cwd=str(tmp_path))


class TestUwpLaunch:
    def test_shell_appsfolder_path_skips_existence_check(self):
        """A shell:AppsFolder\\<AUMID> target isn't a real filesystem path —
        it must go straight to os.startfile without ever being tested for
        existence (which would always fail and block every UWP launch)."""
        entry = {
            "path": "shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
            "name": "Calculator",
            "args": "",
            "working_dir": "",
        }

        with patch("launcher.os.startfile") as mock_startfile, \
             patch("launcher.messagebox.showerror") as mock_error:
            AppLauncher().launch_entry(entry)

        mock_startfile.assert_called_once_with(entry["path"])
        mock_error.assert_not_called()

    def test_shell_launch_failure_shows_error(self):
        entry = {"path": "shell:AppsFolder\\Broken!App", "name": "Broken App", "args": "", "working_dir": ""}

        with patch("launcher.os.startfile", side_effect=OSError("boom")), \
             patch("launcher.messagebox.showerror") as mock_error:
            AppLauncher().launch_entry(entry)

        mock_error.assert_called_once()


class TestLaunchList:
    def test_launches_every_entry(self, tmp_path):
        exe1 = tmp_path / "a.exe"
        exe2 = tmp_path / "b.exe"
        exe1.write_text("fake")
        exe2.write_text("fake")
        entries = [
            {"path": str(exe1), "name": "a.exe", "args": "", "working_dir": ""},
            {"path": str(exe2), "name": "b.exe", "args": "", "working_dir": ""},
        ]

        with patch("launcher.os.startfile") as mock_startfile:
            AppLauncher().launch_list(entries)

        assert mock_startfile.call_count == 2
