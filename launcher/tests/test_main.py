"""
Tests for main.py's _stop_leaking_tcl_tk_paths_to_launched_apps() — see its
docstring. PyInstaller's frozen bootloader sets TCL_LIBRARY/TK_LIBRARY to
find its own bundled Tcl/Tk, and since Windows processes inherit their
parent's environment, anything this app then launches (and anything
launched apps launch in turn) would otherwise inherit paths meant only for
this app's own bundle, breaking any Tcl/Tk-based tool several process
generations downstream — this is exactly what happened when the built app
launched a code editor, which was then used to run this project's own
Tkinter code, and it failed with a Tcl version-conflict error.

Run with: pytest tests/test_main.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import main


class TestStopLeakingTclTkPaths:
    def test_removes_both_variables_when_frozen(self, monkeypatch):
        monkeypatch.setattr(main, "is_frozen", lambda: True)
        monkeypatch.setenv("TCL_LIBRARY", r"C:\some\frozen\_tcl_data")
        monkeypatch.setenv("TK_LIBRARY", r"C:\some\frozen\_tk_data")

        main._stop_leaking_tcl_tk_paths_to_launched_apps()

        assert "TCL_LIBRARY" not in os.environ
        assert "TK_LIBRARY" not in os.environ

    def test_leaves_variables_alone_when_not_frozen(self, monkeypatch):
        """Running from source never has this problem — PyInstaller's
        bootloader is what sets these, so there's nothing to clean up, and
        a developer's own real Tcl/Tk env vars (if any) shouldn't be
        touched."""
        monkeypatch.setattr(main, "is_frozen", lambda: False)
        monkeypatch.setenv("TCL_LIBRARY", r"C:\real\tcl")

        main._stop_leaking_tcl_tk_paths_to_launched_apps()

        assert os.environ["TCL_LIBRARY"] == r"C:\real\tcl"

    def test_does_not_raise_when_variables_are_absent(self, monkeypatch):
        monkeypatch.setattr(main, "is_frozen", lambda: True)
        monkeypatch.delenv("TCL_LIBRARY", raising=False)
        monkeypatch.delenv("TK_LIBRARY", raising=False)

        main._stop_leaking_tcl_tk_paths_to_launched_apps()  # should not raise
