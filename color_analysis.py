"""
颜色分析模块 — 分析图片的主色调、分布、色温等
也包含 OCR 图像预处理公共函数（Otsu 二值化等）
"""
import collections
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance


# ========== OCR 预处理公共函数 ==========

def otsu_threshold(img_gray):
    """Otsu 自适应二值化阈值"""
    hist = img_gray.histogram()
    total = sum(hist)
    if total == 0:
        return 128
    sum_total = sum(i * hist[i] for i in range(256))
    sum_bg, w_bg, max_var = 0, 0, 0
    best = 128
    for t in range(256):
        w_bg += hist[t]
        if w_bg == 0:
            continue
        w_fg = total - w_bg
        if w_fg == 0:
            break
        sum_bg += t * hist[t]
        mean_bg = sum_bg / w_bg
        mean_fg = (sum_total - sum_bg) / w_fg
        var = w_bg * w_fg * (mean_bg - mean_fg) ** 2
        if var > max_var:
            max_var = var
            best = t
    return best


def preprocess_ocr(img, save_debug=False):
    """OCR 预处理流水线：2x → 灰度 → 对比度 → 锐化 → Otsu"""
    w, h = img.size
    img = img.resize((w * 2, h * 2), Image.LANCZOS)
    img_gray = img.convert("L")
    img_gray = ImageEnhance.Contrast(img_gray).enhance(1.8)
    img_gray = img_gray.filter(ImageFilter.SHARPEN)
    img_gray = img_gray.filter(ImageFilter.SHARPEN)
    threshold = otsu_threshold(img_gray)
    img_bw = img_gray.point(lambda x: 0 if x < threshold else 255)
    if save_debug:
        import os
        debug_path = os.path.expanduser("~/Desktop/ocr_debug.png")
        img_bw.convert("RGB").save(debug_path)
        print(f"[调试] 预处理图已保存: {debug_path}")
    return img_bw.convert("RGB")


def preprocess_ocr_preview(img):
    """返回 (原图缩略图, 预处理后缩略图) 用于预览"""
    raw_thumb = img.copy()
    raw_thumb.thumbnail((400, 300), Image.LANCZOS)
    w, h = img.size
    img2x = img.resize((w * 2, h * 2), Image.LANCZOS)
    img_gray = img2x.convert("L")
    img_gray = ImageEnhance.Contrast(img_gray).enhance(1.8)
    img_gray = img_gray.filter(ImageFilter.SHARPEN)
    img_gray = img_gray.filter(ImageFilter.SHARPEN)
    th = otsu_threshold(img_gray)
    processed = img_gray.point(lambda x: 0 if x < th else 255).convert("RGB")
    processed.thumbnail((400, 300), Image.LANCZOS)
    return raw_thumb, processed


# ========== 颜色分析 ==========

def analyze_colors(img):
    """
    分析 PIL Image 的颜色属性
    返回 (文本结果, 直方图Image, 调色板Image)
    """
    w, h = img.size
    img_small = img.resize((100, 60))
    pixels = list(img_small.getdata())
    total = len(pixels)

    # 主色调 Top 10
    counter = collections.Counter(pixels)
    top_raw = counter.most_common(30)

    # 平均色
    avg_r = sum(p[0] for p in pixels) // total
    avg_g = sum(p[1] for p in pixels) // total
    avg_b = sum(p[2] for p in pixels) // total

    # 颜色分布
    white = sum(1 for p in pixels if p[0] > 200 and p[1] > 200 and p[2] > 200)
    dark = sum(1 for p in pixels if p[0] < 60 and p[1] < 60 and p[2] < 60)
    gray = sum(1 for p in pixels if abs(p[0]-p[1]) < 20 and abs(p[1]-p[2]) < 20 and not (p[0] > 200 or p[0] < 60))
    red_p = sum(1 for p in pixels if p[0] > 150 and p[1] < 120 and p[2] < 120)
    green_p = sum(1 for p in pixels if p[1] > 150 and p[0] < 120 and p[2] < 120)
    blue_p = sum(1 for p in pixels if p[2] > 150 and p[0] < 120 and p[1] < 120)
    yellow_p = sum(1 for p in pixels if p[0] > 180 and p[1] > 150 and p[2] < 100)
    warm = sum(1 for p in pixels if p[0] > p[2] and max(p)-min(p) > 30)
    cool = sum(1 for p in pixels if p[2] > p[0] and max(p)-min(p) > 30)

    # 合并相似色
    def quantize(c, step=32):
        return (c[0]//step*step, c[1]//step*step, c[2]//step*step)
    merged = {}
    for p in pixels:
        q = quantize(p)
        merged[q] = merged.get(q, 0) + 1
    sorted_merged = sorted(merged.items(), key=lambda x: -x[1])

    palette = []
    for color, count in sorted_merged[:6]:
        pct = count / total * 100
        palette.append((color, pct))

    # 明暗分布
    bright = sum(1 for p in pixels if (p[0]+p[1]+p[2])//3 > 180)
    mid = sum(1 for p in pixels if 60 <= (p[0]+p[1]+p[2])//3 <= 180)
    shadow = sum(1 for p in pixels if (p[0]+p[1]+p[2])//3 < 60)

    # 色温
    if warm > cool * 1.3:
        temp = "暖色调"
    elif cool > warm * 1.3:
        temp = "冷色调"
    else:
        temp = "中性色调"

    unique_colors = len(set(pixels))
    coverage_ratio = unique_colors / (256**3) * 100

    # 饱和度
    high_sat = 0
    for p in pixels:
        r, g, b = [x/255 for x in p[:3]]
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx - mn > 0.3:
            high_sat += 1
    sat_level = "高饱和" if high_sat > total * 0.3 else ("中饱和" if high_sat > total * 0.1 else "低饱和")

    # 亮度直方图
    hist = [0]*10
    for p in pixels:
        brightness = (p[0] + p[1] + p[2]) // 3
        idx = min(brightness // 26, 9)
        hist[idx] += 1
    hist_pct = [round(h/total*100, 1) for h in hist]

    # ---- 生成文本 ----
    lines = []
    lines.append(f"📷 {w}x{h}")
    lines.append("")
    lines.append("🎨 主色调 Top 10:")
    for color, count in top_raw[:10]:
        r, g, b = color[:3]
        pct = count / total * 100
        lines.append(f"   RGB({r:3d},{g:3d},{b:3d}) #{r:02x}{g:02x}{b:02x}  {pct:.1f}%")
    lines.append("")
    lines.append(f"🎯 平均色: RGB({avg_r},{avg_g},{avg_b}) #{avg_r:02x}{avg_g:02x}{avg_b:02x}")
    lines.append("")
    lines.append("📊 颜色分布:")
    for label, val in [("白色/浅色", white), ("深色", dark), ("灰色", gray),
                       ("红色系", red_p), ("绿色系", green_p), ("蓝色系", blue_p), ("黄色系", yellow_p)]:
        lines.append(f"   {label}: {val/total*100:.1f}%")
    lines.append("")
    lines.append("🎨 代表色:")
    for color, pct in palette:
        r, g, b = color
        lines.append(f"   RGB({r},{g},{b}) #{r:02x}{g:02x}{b:02x}  {pct:.1f}%")
    lines.append("")
    lines.append(f"☀️ 明暗: 亮{bright/total*100:.0f}% / 中{mid/total*100:.0f}% / 暗{shadow/total*100:.0f}%")
    lines.append(f"🌡️ {temp}  🎚️ {sat_level}")
    lines.append(f"🌈 颜色数: {unique_colors} 覆盖率: {coverage_ratio:.3f}%")
    lines.append("")
    lines.append("📈 亮度直方图(0暗→9亮):")
    for i, pct in enumerate(hist_pct):
        bar = "█" * max(1, int(pct / 100 * 40))
        lines.append(f"   {i}: {bar} {pct}%")

    # ---- RGB 直方图 ----
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
    hist_w, hist_h = 600, 200
    hist_img = Image.new('RGB', (hist_w, hist_h), (30, 30, 30))
    hd = ImageDraw.Draw(hist_img)
    hd.line([(40, hist_h-20), (hist_w-10, hist_h-20)], fill=(180, 180, 180))
    hd.line([(40, 10), (40, hist_h-20)], fill=(180, 180, 180))

    colors_rgb = [(255, 50, 50), (50, 200, 50), (50, 130, 255)]
    for h_data, col in zip([hist_r, hist_g, hist_b], colors_rgb):
        points = []
        for i in range(256):
            x = 40 + i * (hist_w - 50) / 256
            y = hist_h - 20 - (h_data[i] / hr_max) * (hist_h - 40)
            points.append((x, y))
        for i in range(len(points) - 1):
            hd.line([points[i], points[i+1]], fill=col, width=2)
        for i in range(0, 256, 2):
            x = 40 + i * (hist_w - 50) / 256
            y_top = hist_h - 20 - (h_data[i] / hr_max) * (hist_h - 40)
            fc = tuple(v // 3 + 20 for v in col)
            for y_line in range(int(y_top), hist_h - 20):
                hd.point((int(x), y_line), fill=fc)

    # ---- 调色板 ----
    pal_img = Image.new('RGB', (600, 120), (255, 255, 255))
    pd = ImageDraw.Draw(pal_img)
    bw = 80
    for i, (color, pct) in enumerate(palette[:6]):
        x = i * (bw + 10) + 10
        pd.rectangle([x, 10, x + bw, 110], fill=color[:3])
        r, g, b = color[:3]
        pd.text((x + 5, 115), f"#{r:02x}{g:02x}{b:02x}", fill=(0, 0, 0))

    return "\n".join(lines), hist_img, pal_img
