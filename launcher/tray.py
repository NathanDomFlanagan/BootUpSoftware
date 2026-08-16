"""
System tray icon support.

Uses pystray (pip install pystray) + Pillow (pip install pillow) to draw a
small icon and run a "Show" / "Exit" menu. pystray's `.run()` call blocks,
so it's started on its own daemon thread; its menu callbacks also fire on
that thread, so — same rule as hotkey.py — anything that touches Tkinter
widgets must be marshalled back onto the main thread by the caller.
"""
import threading
from PIL import Image, ImageDraw
import pystray


class TrayIcon:
    def __init__(self, app_name: str, on_show, on_exit):
        self._icon = pystray.Icon(
            app_name,
            self._build_image(),
            app_name,
            menu=pystray.Menu(
                pystray.MenuItem("Show", lambda icon, item: on_show(), default=True),
                pystray.MenuItem("Exit", lambda icon, item: on_exit()),
            ),
        )
        self._thread = None

    @staticmethod
    def _build_image(size: int = 64) -> Image.Image:
        # Simple generated icon so there's no external asset file to ship/lose.
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle([4, 4, size - 4, size - 4], radius=14, fill=(45, 125, 220, 255))
        draw.text((size / 2 - 10, size / 2 - 10), "AL", fill="white")
        return image

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self):
        self._icon.stop()