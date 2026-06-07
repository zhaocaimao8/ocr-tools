"""
鼠标框选+OCR预览工具 — 拖拽选择 → 预处理预览 → 一键 OCR
用法: 区域选择.pyw [--output-file 路径]
  --output-file  → OCR 结果写入该文件后退出（供 Claude 读取）
"""
import sys, os, io, time, base64, json, urllib.request, tkinter as tk, ctypes
from tkinter import ttk
from PIL import Image, ImageGrab, ImageTk
from color_analysis import preprocess_ocr, preprocess_ocr_preview, analyze_colors

# ---- 命令行参数 ----
OUTPUT_FILE = None
if "--output-file" in sys.argv:
    idx = sys.argv.index("--output-file")
    if idx + 1 < len(sys.argv):
        OUTPUT_FILE = sys.argv[idx + 1]
        try:
            os.remove(OUTPUT_FILE)
        except:
            pass

COLOR_FLAG = "--color" in sys.argv

# ---- DPI 感知（确保坐标和截图一致）----
ctypes.windll.user32.SetProcessDPIAware()

# ---- 底层鼠标坐标（和你的 鼠标坐标.pyw 一致）----
class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]

def get_cursor_pos():
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

OCR_SCRIPT = os.path.join(os.path.dirname(__file__), "screen_ocr_v2.py")

# ---- 全局 ----
start_x = start_y = 0
end_x = end_y = 0
rect_id = None
canvas = None
root = None

# ---- 图像预处理（复用 color_analysis）----

# ---- 抓取区域 -----

def capture_region(x1, y1, x2, y2):
    """从屏幕截取指定区域（遮罩需外部管理）"""
    img = ImageGrab.grab()
    sw, sh = img.size
    user32 = ctypes.windll.user32
    vx = user32.GetSystemMetrics(76)
    vy = user32.GetSystemMetrics(77)
    px1 = max(x1 - vx, 0)
    py1 = max(y1 - vy, 0)
    px2 = min(x2 - vx, sw)
    py2 = min(y2 - vy, sh)
    if px2 > px1 and py2 > py1:
        img = img.crop((px1, py1, px2, py2))
    return img

# ---- OCR 调用 ----

def run_ocr_from_image(pil_img):
    """直接对 PIL Image 做 OCR，返回文字列表"""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    data = json.dumps({"base64": b64}).encode()
    req = urllib.request.Request(
        "http://127.0.0.1:1224/api/ocr", data=data,
        headers={"Content-Type": "application/json"}
    )
    res = json.loads(urllib.request.urlopen(req, timeout=30).read())
    texts = []
    for item in res.get("data", []):
        t = item.get("text", "").strip()
        if t:
            texts.append(t)
    return texts

# ---- 选择逻辑 ----

def on_press(event):
    global start_x, start_y, end_x, end_y
    start_x, start_y = get_cursor_pos()
    end_x, end_y = start_x, start_y
    canvas.delete("sel_rect")
    canvas.create_rectangle(
        0, 0, 0, 0,
        outline="#00ff44", width=3, tags="sel_rect"
    )
    for tag in ("sel_tl", "sel_br"):
        canvas.create_oval(0, 0, 0, 0, fill="#00ff44", outline="",
                           tags=(tag, "sel_rect"))

def on_drag(event):
    global end_x, end_y
    end_x, end_y = get_cursor_pos()
    x1, y1 = min(start_x, end_x), min(start_y, end_y)
    x2, y2 = max(start_x, end_x), max(start_y, end_y)
    canvas.coords("sel_rect", x1, y1, x2, y2)
    if x2 - x1 > 10 and y2 - y1 > 10:
        canvas.coords("sel_tl", x1-5, y1-5, x1+5, y1+5)
        canvas.coords("sel_br", x2-5, y2-5, x2+5, y2+5)
    coord_label.config(text=f"({x1},{y1}) → ({x2},{y2})  [{x2-x1}×{y2-y1}]")

def on_release(event):
    global end_x, end_y
    end_x, end_y = get_cursor_pos()
    x1, y1 = min(start_x, end_x), min(start_y, end_y)
    x2, y2 = max(start_x, end_x), max(start_y, end_y)

    coord_text = f"{x1},{y1},{x2},{y2}"
    root.clipboard_clear()
    root.clipboard_append(coord_text)

    # 抓取并预处理
    root.attributes("-alpha", 0.01)  # 几乎透明但保留窗口存在
    root.update()
    time.sleep(0.15)
    raw_img = capture_region(x1, y1, x2, y2)
    raw_thumb, processed_thumb = preprocess_ocr_preview(raw_img)

    # 生成原图和预处理图的 ImageTk
    raw_tk = ImageTk.PhotoImage(raw_thumb)
    proc_tk = ImageTk.PhotoImage(processed_thumb)

    # 显示预览窗口
    preview_win = tk.Toplevel(root)
    preview_win.title("区域预览")
    preview_win.attributes("-topmost", True)
    preview_win.configure(bg="#222")
    preview_win.geometry("+300+200")

    # 标题
    tk.Label(preview_win, text="已选区域", fg="#0f0", bg="#222",
             font=("微软雅黑", 12, "bold")).pack(pady=(10, 2))
    tk.Label(preview_win, text=coord_text, fg="#fff", bg="#222",
             font=("Consolas", 13)).pack()
    tk.Label(preview_win, text=f"{x2-x1}×{y2-y1} px · 已复制到剪贴板",
             fg="#aaa", bg="#222", font=("微软雅黑", 9)).pack()

    # 预览图左右并排
    img_frame = tk.Frame(preview_win, bg="#222")
    img_frame.pack(pady=8)

    left_frame = tk.Frame(img_frame, bg="#222")
    left_frame.pack(side="left", padx=8)
    tk.Label(left_frame, text="原图", fg="#888", bg="#222",
             font=("微软雅黑", 9)).pack()
    raw_label = tk.Label(left_frame, image=raw_tk, bg="#111", bd=1, relief="solid")
    raw_label.pack()
    raw_label.image = raw_tk  # 防止 GC

    right_frame = tk.Frame(img_frame, bg="#222")
    right_frame.pack(side="left", padx=8)
    tk.Label(right_frame, text="预处理后（Otsu 二值化）", fg="#888", bg="#222",
             font=("微软雅黑", 9)).pack()
    proc_label = tk.Label(right_frame, image=proc_tk, bg="#111", bd=1, relief="solid")
    proc_label.pack()
    proc_label.image = proc_tk

    # 按钮
    btn_frame = tk.Frame(preview_win, bg="#222")
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="重新选择",
              command=lambda: [preview_win.destroy(), root.attributes("-alpha", 0.3)],
              bg="#444", fg="#fff", font=("微软雅黑", 10), width=10
              ).pack(side="left", padx=5)

    tk.Button(btn_frame, text="→ OCR",
              command=lambda: [preview_win.destroy(), do_ocr_local(raw_img)],
              bg="#0a0", fg="#fff", font=("微软雅黑", 10, "bold"), width=10
              ).pack(side="left", padx=5)

    tk.Button(btn_frame, text="关闭",
              command=sys.exit,
              bg="#a00", fg="#fff", font=("微软雅黑", 10), width=10
              ).pack(side="left", padx=5)


def do_ocr_local(raw_img):
    """预处理 → OCR → 可选颜色分析 → 保存/显示"""
    try:
        processed = preprocess_ocr(raw_img)
        texts = run_ocr_from_image(processed)
        lines = texts if texts else ["（未识别到文字）"]

        # --color 颜色分析
        if COLOR_FLAG:
            save_dir = os.path.join(os.path.dirname(__file__), "截图存档")
            os.makedirs(save_dir, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            try:
                color_text, hist_img, pal_img = analyze_colors(raw_img)
                lines.append("")
                lines.append("=" * 40)
                lines.append("🎨 颜色分析")
                lines.append("=" * 40)
                lines.append(color_text)
                hist_img.save(os.path.join(save_dir, f"分析_直方图_{ts}.png"))
                pal_img.save(os.path.join(save_dir, f"分析_调色板_{ts}.png"))
            except Exception as e:
                lines.append(f"[颜色分析失败] {e}")

        # --output-file 模式：写入文件
        if OUTPUT_FILE:
            try:
                os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            except Exception as e:
                print(f"保存结果失败: {e}")
            sys.exit(0)

        show_ocr_result(lines)
    except Exception as e:
        lines = [f"OCR 失败: {e}"]
        if OUTPUT_FILE:
            try:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines))
            except Exception:
                pass
            sys.exit(0)
        show_ocr_result(lines)


def show_ocr_result(lines):
    rw = tk.Toplevel(root)
    rw.title("OCR 结果")
    rw.geometry("+400+200")
    rw.attributes("-topmost", True)
    rw.configure(bg="#222")

    tk.Label(rw, text="OCR 识别结果", fg="#0f0", bg="#222",
             font=("微软雅黑", 12, "bold")).pack(pady=(10, 5))

    text_frame = tk.Frame(rw, bg="#111")
    text_frame.pack(padx=15, pady=5, fill="both", expand=True)

    text_widget = tk.Text(text_frame, bg="#111", fg="#fff",
                          font=("微软雅黑", 11), wrap="word",
                          height=10, width=50, bd=0, padx=8, pady=8)
    text_widget.pack(fill="both", expand=True)
    text_widget.insert("1.0", "\n".join(lines))
    text_widget.config(state="disabled")

    def copy_and_close():
        rw.clipboard_clear()
        rw.clipboard_append("\n".join(lines))
        sys.exit(0)

    btn_frame = tk.Frame(rw, bg="#222")
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="重新选择",
              command=lambda: [rw.destroy(), root.attributes("-alpha", 0.3)],
              bg="#444", fg="#fff", font=("微软雅黑", 10), width=10
              ).pack(side="left", padx=5)

    tk.Button(btn_frame, text="复制并关闭",
              command=copy_and_close,
              bg="#0a0", fg="#fff", font=("微软雅黑", 10, "bold"), width=10
              ).pack(side="left", padx=5)

    tk.Button(btn_frame, text="关闭",
              command=sys.exit,
              bg="#a00", fg="#fff", font=("微软雅黑", 10), width=10
              ).pack(side="left", padx=5)


def cancel(event):
    sys.exit(0)


# ---- 主窗口 ----
root = tk.Tk()
root.title("区域选择")
root.attributes("-topmost", True)
root.overrideredirect(True)
root.attributes("-alpha", 0.3)
root.configure(bg="#000")
root.config(cursor="crosshair")
# 覆盖整个虚拟屏幕，不用 -fullscreen（避免影响其他窗口）
sw = ctypes.windll.user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
sh = ctypes.windll.user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
vx = ctypes.windll.user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
vy = ctypes.windll.user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
root.geometry(f"{sw}x{sh}+{vx}+{vy}")

canvas = tk.Canvas(root, highlightthickness=0, bg="#000")
canvas.pack(fill="both", expand=True)

tip = tk.Label(root, text="拖拽选择区域 · Esc 退出",
               fg="#888", bg="#000", font=("微软雅黑", 11))
tip.place(relx=0.5, rely=0.95, anchor="center")

coord_label = tk.Label(root, text="", fg="#0f0", bg="#000",
                        font=("Consolas", 12))
coord_label.place(relx=0.5, rely=0.02, anchor="n")

canvas.bind("<ButtonPress-1>", on_press)
canvas.bind("<B1-Motion>", on_drag)
canvas.bind("<ButtonRelease-1>", on_release)
root.bind("<Escape>", cancel)

root.mainloop()
