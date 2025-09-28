# tooltip.py
import tkinter as tk
import tkinter.font as tkfont

class ToolTip:
    def __init__(self, widget, delay: int = 500):
        self.widget = widget
        self.delay = delay
        self.id = None
        self.tipwindow = None
        self.font = tkfont.Font(family="Tahoma", size=8)

    def schedule(self, text: str):
        self.unschedule()
        self.text = text
        self.id = self.widget.after(self.delay, self.show) # type: ignore

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def showtip(self, text):
        if self.tipwindow or not text:
            return
        x, y, _, _ = self.widget.bbox("active")  # coords of the hovered item
        x += self.widget.winfo_rootx() + 20
        y += self.widget.winfo_rooty() + 10
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=text,
            justify="left",
            background="#ffffe0",
            relief="solid",
            borderwidth=1,
            font=self.font
        )
        label.pack(ipadx=1)
        # ---- FONT INSPECTION ----
        # font_descr = label.cget("font")
        # f = tkfont.Font(font=font_descr)
        # info = (f"Font family: {f.actual('family')}\n"
        #         f"Font size:   {f.actual('size')}\n"
        #         f"Font weight: {f.actual('weight')}")
        # print(info)   # logs to console
        # text_with_font = f"{text}\n\n[{f.actual('family')}, size={f.actual('size')}, weight={f.actual('weight')}]"
        # label.config(text=text_with_font)
        # Or display in GUI:
        # messagebox.showinfo("Tooltip Font Details", info)

    def hidetip(self):
        tw = self.tipwindow
        if tw:
            tw.destroy()
        self.tipwindow = None
