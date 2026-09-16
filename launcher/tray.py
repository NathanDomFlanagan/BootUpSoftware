"""
System tray icon support.

Uses pystray (pip install pystray) + Pillow (pip install pillow) to draw a
small icon and run a "Show" / "Exit" menu. pystray's `.run()` call blocks,
so it's started on its own daemon thread; its menu callbacks also fire on
that thread, so anything that touches Tkinter widgets must be marshalled
back onto the main thread by the caller.

The icon's colors adapt to the Windows taskbar theme (read from the
registry) so it stays visible against either a light or dark taskbar,
rather than being a fixed color that can wash out against one of them.
"""
import logging
import threading
from PIL import Image, ImageDraw
import pystray

from safe_call import safe_call

log = logging.getLogger(__name__)

try:
    import winreg
    WINREG_AVAILABLE = True
except ImportError:
    winreg = None
    WINREG_AVAILABLE = False


def _is_light_taskbar() -> bool:
    """Reads the Windows registry to determine whether the taskbar is
    currently in light mode. Defaults to False (assume dark taskbar — the
    more common default) if the key is missing or unreadable, e.g. on a
    non-Windows system or an older Windows version without this setting."""
    if not WINREG_AVAILABLE:
        return False
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        )
        value, _ = winreg.QueryValueEx(key, "SystemUsesLightTheme")
        winreg.CloseKey(key)
        return bool(value)
    except Exception:
        log.debug("Could not read taskbar theme from registry — defaulting to dark", exc_info=True)
        return False


class TrayIcon:
    def __init__(self, app_name: str, on_show, on_exit):
        self._is_light = _is_light_taskbar()
        self._icon = pystray.Icon(
            app_name,
            self._build_image(is_light=self._is_light),
            app_name,
            menu=pystray.Menu(
                pystray.MenuItem(
                    "Show",
                    lambda icon, item: safe_call(log, "Error handling tray menu action 'Show'", on_show),
                    default=True,
                ),
                pystray.MenuItem(
                    "Exit",
                    lambda icon, item: safe_call(log, "Error handling tray menu action 'Exit'", on_exit),
                ),
            ),
        )
        self._thread = None
        self._theme_thread = None
        self._stop_event = threading.Event()

    @staticmethod
    def _build_image(size: int = 64, is_light: bool = False) -> Image.Image:
        # Option A: load a real icon file (place icon.png next to this script,
        # or next to the exe if frozen with PyInstaller — see note in README).
        # return Image.open(Path(__file__).with_name("icon.png"))

        # Option B (current default): generated "app-drawer grid" icon —
        # a 3x3 grid of dots on a rounded square, colored to contrast with
        # the current Windows taskbar theme (light taskbar -> dark icon,
        # dark taskbar -> light icon) so it never washes out.
        if is_light:
            bg_color = (0, 0, 0, 255)          # black background
            dot_color = (255, 255, 255, 255)    # white dots
        else:
            bg_color = (255, 255, 255, 255)     # white background
            dot_color = (0, 0, 0, 255)          # black dots

        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=size * 0.2, fill=bg_color)

        # 3x3 grid of small squares, scaled proportionally to `size`.
        cell = size * 0.12
        gap = size * 0.10
        grid_span = cell * 3 + gap * 2
        start = (size - grid_span) / 2
        radius = cell * 0.25

        for row in range(3):
            for col in range(3):
                x0 = start + col * (cell + gap)
                y0 = start + row * (cell + gap)
                draw.rounded_rectangle([x0, y0, x0 + cell, y0 + cell], radius=radius, fill=dot_color)

        return image

    def _monitor_theme(self):
        """Polls the Windows taskbar theme every 5 seconds and swaps the tray
        icon's image live if it's changed, so toggling dark/light mode in
        Windows Settings is picked up without needing to restart the app."""
        while not self._stop_event.is_set():
            if self._stop_event.wait(5):
                break  # stop() was called during the wait
            try:
                current_is_light = _is_light_taskbar()
                if current_is_light != self._is_light:
                    self._is_light = current_is_light
                    self._icon.icon = self._build_image(is_light=current_is_light)
                    log.info("Taskbar theme changed — tray icon redrawn (light=%s)", current_is_light)
            except Exception:
                log.exception("Error while polling taskbar theme")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_icon, daemon=True, name="TrayIconThread")
        self._thread.start()
        self._theme_thread = threading.Thread(target=self._monitor_theme, daemon=True, name="TrayThemeMonitorThread")
        self._theme_thread.start()
        log.info("Tray icon started")

    def _run_icon(self):
        try:
            self._icon.run()
        except Exception:
            log.exception("Tray icon thread crashed")

    def stop(self):
        self._stop_event.set()
        try:
            self._icon.stop()
            log.info("Tray icon stopped")
        except Exception:
            log.exception("Error stopping tray icon")