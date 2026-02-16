import tkinter as tk
import tkinter.font as tkfont


class ToolTip:
    def __init__(self, widget, delay: int = 500):
        self.widget = widget
        self.delay = delay
        self.id = None
        self.tipwindow = None
        self.font = tkfont.Font(family="Tahoma", size=8)
        self.text = ""

    def schedule(self, text: str):
        self.unschedule()
        self.text = text
        self.id = self.widget.after(self.delay, self.show)  # type: ignore

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_pointerx() + 20
        y = self.widget.winfo_pointery() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=self.font
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        if tw:
            tw.destroy()
        self.tipwindow = None
