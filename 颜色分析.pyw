import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw
import collections
import colorsys
import math
import io

# ---------- 颜色分析函数 ----------

def analyze_colors(img_path):
    img = Image.open(img_path)
    w, h = img.size
    img_mode = img.mode
    img_small = img.resize((100, 60))
    pixels = list(img_small.getdata())
    total = len(pixels)

    # 1. 主色调 Top 10
    counter = collections.Counter(pixels)
    top_raw = counter.most_common(30)

    # 2. 平均色
    avg_r = sum(p[0] for p in pixels) // total
    avg_g = sum(p[1] for p in pixels) // total
    avg_b = sum(p[2] for p in pixels) // total

    # 3. 颜色分布
    white = sum(1 for p in pixels if p[0] > 200 and p[1] > 200 and p[2] > 200)
    dark = sum(1 for p in pixels if p[0] < 60 and p[1] < 60 and p[2] < 60)
    gray = sum(1 for p in pixels if abs(p[0]-p[1]) < 20 and abs(p[1]-p[2]) < 20 and not (p[0] > 200 or p[0] < 60))
    red_p = sum(1 for p in pixels if p[0] > 150 and p[1] < 120 and p[2] < 120)
    green_p = sum(1 for p in pixels if p[1] > 150 and p[0] < 120 and p[2] < 120)
    blue_p = sum(1 for p in pixels if p[2] > 150 and p[0] < 120 and p[1] < 120)
    yellow_p = sum(1 for p in pixels if p[0] > 180 and p[1] > 150 and p[2] < 100)
    warm = sum(1 for p in pixels if p[0] > p[2] and max(p)-min(p) > 30)
    cool = sum(1 for p in pixels if p[2] > p[0] and max(p)-min(p) > 30)

    # 4. 合并相似色
    def quantize(c, step=32):
        return (c[0]//step*step, c[1]//step*step, c[2]//step*step)

    merged = {}
    for p in pixels:
        q = quantize(p)
        merged[q] = merged.get(q, 0) + 1
    sorted_merged = sorted(merged.items(), key=lambda x: -x[1])

    # 5. 提取代表色（取合并后top 6）
    palette = []
    for color, count in sorted_merged[:6]:
        pct = count / total * 100
        palette.append((color, pct))

    # 6. 明暗分布
    bright = sum(1 for p in pixels if (p[0]+p[1]+p[2])//3 > 180)
    mid = sum(1 for p in pixels if 60 <= (p[0]+p[1]+p[2])//3 <= 180)
    shadow = sum(1 for p in pixels if (p[0]+p[1]+p[2])//3 < 60)

    # 7. 色温
    if warm > cool * 1.3:
        temp = "暖色调"
    elif cool > warm * 1.3:
        temp = "冷色调"
    else:
        temp = "中性色调"

    # 全色分析
    unique_colors = len(set(pixels))
    coverage_ratio = unique_colors / (256**3) * 100

    # 8. 饱和度分析
    high_sat = 0
    for p in pixels:
        r, g, b = [x/255 for x in p[:3]]
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx - mn > 0.3:
            high_sat += 1
    sat_level = "高饱和" if high_sat > total * 0.3 else ("中饱和" if high_sat > total * 0.1 else "低饱和")

    # 9. 亮度直方图（简化：分10段）
    hist = [0]*10
    for p in pixels:
        brightness = (p[0] + p[1] + p[2]) // 3
        idx = min(brightness // 26, 9)
        hist[idx] += 1
    hist_pct = [round(h/total*100, 1) for h in hist]

    # ---- 生成结果文本 ----
    lines = []
    lines.append(f"📷 图片尺寸: {w}x{h}")
    lines.append(f"📐 色彩模式: {img_mode}")
    lines.append("")

    lines.append("🎨 主色调 Top 10:")
    for color, count in top_raw[:10]:
        r, g, b = color[:3]
        pct = count / total * 100
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        lines.append(f"   RGB({r:3d},{g:3d},{b:3d}) {hex_color}  {pct:.1f}%")

    lines.append("")
    lines.append(f"🎯 平均色: RGB({avg_r},{avg_g},{avg_b}) #{avg_r:02x}{avg_g:02x}{avg_b:02x}")
    lines.append("")

    lines.append("📊 颜色分布:")
    lines.append(f"   ⬜ 白色/浅色: {white/total*100:.1f}%")
    lines.append(f"   ⬛ 深色(文字/线条): {dark/total*100:.1f}%")
    lines.append(f"   🔘 灰色: {gray/total*100:.1f}%")
    lines.append(f"   🔴 红色系: {red_p/total*100:.1f}%")
    lines.append(f"   🟢 绿色系: {green_p/total*100:.1f}%")
    lines.append(f"   🔵 蓝色系: {blue_p/total*100:.1f}%")
    lines.append(f"   🟡 黄色系: {yellow_p/total*100:.1f}%")
    lines.append("")

    lines.append("🎨 代表色（合并后）:")
    for color, pct in palette:
        r, g, b = color
        hex_c = f"#{r:02x}{g:02x}{b:02x}"
        lines.append(f"   RGB({r},{g},{b}) {hex_c}  {pct:.1f}%")

    lines.append("")
    lines.append("☀️ 明暗分布:")
    lines.append(f"   亮部: {bright/total*100:.1f}%")
    lines.append(f"   中间调: {mid/total*100:.1f}%")
    lines.append(f"   暗部: {shadow/total*100:.1f}%")

    lines.append("")
    lines.append(f"🌡️  色温: {temp}")
    lines.append(f"🎚️  饱和度: {sat_level}")
    lines.append("")
    lines.append(f"🌈 全色统计:")
    lines.append(f"   唯一颜色数: {unique_colors} 种")
    lines.append(f"   色彩覆盖率: {coverage_ratio:.4f}%（占RGB空间）")

    lines.append("")
    lines.append("📈 亮度直方图（0最暗→9最亮）:")
    bar_max = 20
    for i, pct in enumerate(hist_pct):
        bar = "█" * max(1, int(pct / 100 * bar_max * 2))
        lines.append(f"   {i}: {bar} {pct}%")

    # ---- RGB直方图分布曲线 ----
    img_full = img.convert('RGB')
    full_pixels = list(img_full.getdata())
    hist_r = [0]*256
    hist_g = [0]*256
    hist_b = [0]*256
    for p in full_pixels:
        hist_r[p[0]] += 1
        hist_g[p[1]] += 1
        hist_b[p[2]] += 1

    hr_max = max(max(hist_r), max(hist_g), max(hist_b))
    hist_w, hist_h = 600, 250
    hist_img = Image.new('RGB', (hist_w, hist_h), (30,30,30))
    hd = ImageDraw.Draw(hist_img)

    # 坐标轴
    hd.line([(40, hist_h-20), (hist_w-10, hist_h-20)], fill=(180,180,180))  # X轴
    hd.line([(40, 10), (40, hist_h-20)], fill=(180,180,180))  # Y轴

    # 刻度标签
    from PIL import ImageFont
    try:
        font = ImageFont.load_default()
    except:
        font = None

    for i in range(0, 256, 64):
        x = 40 + i * (hist_w-50) / 256
        hd.line([(x, hist_h-20), (x, hist_h-15)], fill=(180,180,180))
        if font: hd.text((x-5, hist_h-18), str(i), fill=(200,200,200), font=font)

    # 画三通道曲线
    colors = [(255,50,50), (50,200,50), (50,130,255)]  # R,G,B
    hist_data = [hist_r, hist_g, hist_b]
    hist_name = ['R', 'G', 'B']

    for ch_idx, h_data in enumerate(hist_data):
        points = []
        for i in range(256):
            x = 40 + i * (hist_w-50) / 256
            y = hist_h-20 - (h_data[i] / hr_max) * (hist_h-40)
            points.append((x, y))

        # 画线
        for i in range(len(points)-1):
            hd.line([points[i], points[i+1]], fill=colors[ch_idx], width=2)

        # 画填充（半透明效果用细垂直线模拟）
        for i in range(0, 256, 2):
            x = 40 + i * (hist_w-50) / 256
            y_top = hist_h-20 - (h_data[i] / hr_max) * (hist_h-40)
            fill_color = colors[ch_idx][0]//3+20, colors[ch_idx][1]//3+20, colors[ch_idx][2]//3+20
            for y_line in range(int(y_top), hist_h-20):
                hd.point((int(x), y_line), fill=fill_color)

    # 图例
    legend_y = 15
    for ch_idx, name in enumerate(hist_name):
        lx = 50 + ch_idx * 60
        hd.rectangle([(lx, legend_y), (lx+15, legend_y+10)], fill=colors[ch_idx])
        if font: hd.text((lx+18, legend_y-2), name, fill=colors[ch_idx], font=font)

    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join("D:/Umi-OCR", "截图存档")
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(img_path))[0]
    hist_path = os.path.join(out_dir, base + '_histogram.png')
    hist_img.save(hist_path)
    lines.append(f"   📈 直方图已保存")

    # ---- 生成调色板图片 ----
    palette_img = Image.new('RGB', (600, 120), (255,255,255))
    draw = ImageDraw.Draw(palette_img)
    block_w = 80
    for i, (color, pct) in enumerate(palette[:6]):
        x = i * (block_w + 10) + 10
        draw.rectangle([x, 10, x+block_w, 110], fill=color[:3])
        r, g, b = color[:3]
        draw.text((x+5, 115), f"#{r:02x}{g:02x}{b:02x}", fill=(0,0,0))

    palette_path = os.path.join(out_dir, base + '_palette.png')
    palette_img.save(palette_path)

    return '\n'.join(lines), palette_path


# ---------- GUI ----------

class App:
    def __init__(self, root):
        self.root = root
        root.title('颜色分析')
        root.geometry('600x500+500+300')

        self.btn = tk.Button(root, text='选择图片', font=('微软雅黑', 14), command=self.pick)
        self.btn.pack(pady=10)

        self.text = tk.Text(root, font=('Consolas', 10), wrap='word')
        self.text.pack(fill='both', expand=True, padx=10, pady=5)

        self.status = tk.Label(root, text='点击"选择图片"开始分析', font=('微软雅黑', 10))
        self.status.pack(pady=5)

    def pick(self):
        path = filedialog.askopenfilename(
            title='选择图片',
            filetypes=[('图片', '*.png *.jpg *.jpeg *.bmp *.gif'), ('所有文件', '*.*')]
        )
        if not path:
            return

        self.status.config(text='分析中...')
        self.root.update()

        try:
            result, palette_path = analyze_colors(path)
            self.text.delete(1.0, tk.END)
            self.text.insert(1.0, result)
            fname = path.split('/')[-1].split('\\')[-1]
            self.status.config(text=f'{fname}   |   结果: D:/Umi-OCR/截图存档/')
        except Exception as e:
            messagebox.showerror('错误', str(e))
            self.status.config(text='分析失败')


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()
