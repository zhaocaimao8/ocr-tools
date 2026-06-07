import tkinter as tk
import ctypes

mutex = ctypes.windll.kernel32.CreateMutexW(None, False, 'Local\\MouseCoordTool')
if ctypes.windll.kernel32.GetLastError() == 183:
    hwnd = ctypes.windll.user32.FindWindowW(None, '坐标')
    if hwnd: ctypes.windll.user32.SetForegroundWindow(hwnd)
    exit()

user32 = ctypes.windll.user32

class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
def get_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

root = tk.Tk()
root.title('坐标')
root.geometry('130x36+400+780')
root.overrideredirect(True)
root.attributes('-topmost', True)
root.attributes('-alpha', 0.85)
root.configure(bg='#111')

label = tk.Label(root, text='0,0', font=('Consolas', 18), fg='lime', bg='#111')
label.pack(fill='both', expand=True)

title_bar = tk.Frame(root, bg='#333', height=20)
tk.Label(title_bar, text='坐标', fg='#aaa', bg='#333', font=('微软雅黑', 9)).pack(side='left', padx=5)
close = tk.Label(title_bar, text='✕', fg='#aaa', bg='#333', font=('微软雅黑', 9))
close.pack(side='right', padx=5)
close.bind('<Button-1>', lambda e: root.destroy())

_mouse_in = False
_hide_timer = None

def check():
    global _mouse_in, _hide_timer
    mx, my = get_pos()
    x, y = root.winfo_x(), root.winfo_y()
    w, h = root.winfo_width(), root.winfo_height()
    inside = x <= mx <= x+w and y <= my <= y+h

    if inside and not _mouse_in:
        _mouse_in = True
        title_bar.pack(fill='x', before=label)
        root.geometry(f'130x56+{x}+{y-20}')
        if _hide_timer:
            root.after_cancel(_hide_timer)
            _hide_timer = None
    elif not inside and _mouse_in and not _hide_timer:
        def hide():
            global _mouse_in, _hide_timer
            _mouse_in = False
            _hide_timer = None
            x, y = root.winfo_x(), root.winfo_y()
            title_bar.pack_forget()
            root.geometry(f'130x36+{x}+{y+20}')
        _hide_timer = root.after(1000, hide)
    elif inside and _hide_timer:
        root.after_cancel(_hide_timer)
        _hide_timer = None

    if root.winfo_y() > 800:
        root.geometry(f'+{root.winfo_x()}+800')

    label.config(text=f'{mx},{my}')
    root.after(100, check)

def start(e):
    root._x, root._y = e.x_root, e.y_root
    root._gx, root._gy = root.winfo_x(), root.winfo_y()
def drag(e):
    root.geometry(f'+{root._gx+e.x_root-root._x}+{root._gy+e.y_root-root._y}')
def drop(e):
    if root.winfo_y() > 800:
        root.geometry(f'+{root.winfo_x()}+800')

root.bind('<Button-1>', start)
root.bind('<B1-Motion>', drag)
root.bind('<ButtonRelease-1>', drop)
root.bind('<Escape>', lambda e: root.destroy())

check()
root.mainloop()
