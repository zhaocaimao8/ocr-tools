# -*- coding: utf-8 -*-
"""
增强版截图OCR v2 — 截活动窗口 → 放大2x → 锐化 → 二值化 → OCR
用法:
  python screen_ocr_v2.py                → 截当前活动窗口
  python screen_ocr_v2.py 关键词         → 切换到目标窗口后截图
  python screen_ocr_v2.py 关键词 --save-debug  → 额外保存预处理图用于调试
输出: OCR识别的文字（按阅读顺序排序）
"""
import sys, io, os, base64, json, urllib.request, time, argparse, subprocess, ctypes
import win32gui, win32con, win32com.client, win32api
from PIL import Image, ImageGrab
from color_analysis import otsu_threshold, preprocess_ocr

# ----- 工具函数 -----

def list_visible_windows():
    """返回所有可见窗口标题列表"""
    result = []
    def cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            t = win32gui.GetWindowText(hwnd)
            if t:
                result.append(t)
    win32gui.EnumWindows(cb, None)
    return result


# ----- 窗口截图 -----

def capture_active_window(keyword=None):
    """截图整个窗口（含标题栏），返回 PIL Image"""
    current = win32gui.GetForegroundWindow()
    cur_placement = win32gui.GetWindowPlacement(current)

    target = current
    if keyword:
        kw = keyword.strip()

        # 特殊：截桌面（最小化所有窗口 → 全屏截图）
        if kw in ("桌面", "desktop"):
            shell = win32com.client.Dispatch("Shell.Application")
            shell.MinimizeAll()
            time.sleep(0.5)
            img = ImageGrab.grab()
            time.sleep(0.2)
            shell.UndoMinimizeAll()
            return img, None

        # 特殊：截当前活动窗口（等同于无关键词）
        elif kw in ("当前", "当前窗口", "active", ""):
            target = current  # 保留活动窗口

        else:
            # 中文关键词 → 可能的窗口标题别名
            ALIASES = {
                "浏览器": ["edge", "chrome", "firefox", "browser", "iexplore", "ie", "搜狗", "360"],
                "编辑器": ["code", "vim", "notepad", "sublime", "text"],
                "终端": ["cmd", "powershell", "terminal", "console", "bash", "windows terminal"],
                "文件": ["explorer", "文件夹", "directory", "此电脑", "我的电脑", "computer"],
            }
            candidates = [kw]
            for cn, en_list in ALIASES.items():
                if cn in kw:
                    candidates.extend(en_list)

            def find_hwnd(kw):
                result = []
                def cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd):
                        if kw.lower() in win32gui.GetWindowText(hwnd).lower():
                            result.append(hwnd)
                win32gui.EnumWindows(cb, None)
                return result[0] if result else None

            target = None
            for candidate in candidates:
                target = find_hwnd(candidate)
                if target:
                    break
            if target:
                try:
                    win32gui.ShowWindow(target, win32con.SW_MAXIMIZE)
                    win32gui.SetForegroundWindow(target)
                except Exception:
                    pass
                time.sleep(1.5)

    if not target:
        return None, None

    # 获取整个窗口坐标（含标题栏）
    try:
        wx1, wy1, wx2, wy2 = win32gui.GetWindowRect(target)
    except Exception:
        wx1 = wy1 = wx2 = wy2 = None

    img = ImageGrab.grab()
    # 保存窗口原始虚拟屏幕坐标（用于 --screen 换算）
    window_rect = (wx1, wy1, wx2, wy2) if all(v is not None for v in (wx1, wy1, wx2, wy2)) else None
    if all(v is not None for v in (wx1, wy1, wx2, wy2)):
        sw, sh = img.size
        # 修正副屏坐标：虚拟屏幕原点可能为负
        vx = win32api.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        vy = win32api.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
        cx1 = wx1 - vx
        cy1 = wy1 - vy
        cx2 = wx2 - vx
        cy2 = wy2 - vy
        # 裁剪到图片边界内
        cx1 = max(cx1, 0)
        cy1 = max(cy1, 0)
        cx2 = min(cx2, sw)
        cy2 = min(cy2, sh)
        if cx2 > cx1 and cy2 > cy1:
            img = img.crop((cx1, cy1, cx2, cy2))

    if keyword and current:
        try:
            win32gui.SetWindowPlacement(current, cur_placement)
            win32gui.SetForegroundWindow(current)
        except Exception:
            pass

    return img, window_rect


# ----- 图像预处理 -----

def preprocess(img, save_debug=False):
    """OCR 预处理（委托 color_analysis）"""
    return preprocess_ocr(img, save_debug)


# ----- OCR调用 -----

def ocr(img, retries=2, decode_qr=False):
    """Umi-OCR API 识别，带重试"""
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    payload = {"base64": b64}
    if decode_qr:
        # 启用二维码/条形码识别
        payload["options"] = {"decode_bar": True, "decode_qrcode": True}
    data = json.dumps(payload).encode()

    last_err = None
    for attempt in range(1 + retries):
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:1224/api/ocr", data=data,
                headers={"Content-Type": "application/json"}
            )
            res = json.loads(urllib.request.urlopen(req, timeout=30).read())
            break
        except urllib.error.URLError as e:
            last_err = f"无法连接 Umi-OCR (127.0.0.1:1224) — 请确认服务已启动"
            if attempt < retries:
                time.sleep(1)
            continue
        except json.JSONDecodeError as e:
            last_err = f"OCR 返回数据解析失败: {e}"
            break
        except Exception as e:
            last_err = f"OCR 请求异常: {e}"
            break
    else:
        raise RuntimeError(last_err)

    items = res.get("data", [])
    if not isinstance(items, list):
        return []
    # 按位置排序：先按行(top相近为一组)，再按列从左到右
    # Umi-OCR 返回格式中每个 item 可能有 box 坐标
    def sort_key(item):
        box = item.get("box", None) or item.get("position", None)
        if box:
            # box: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            top = min(p[1] for p in box)
            left = min(p[0] for p in box)
        else:
            top = left = 0
        # 行高容差 20px 内视为同行
        return (top // 20, left)

    items.sort(key=sort_key)

    texts = []
    for item in items:
        t = item.get("text", "").strip()
        if t:
            texts.append(t)
    return texts


# ----- 入口 -----

if __name__ == "__main__":
    # 强制UTF-8输出
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    parser = argparse.ArgumentParser(description="截图OCR识别")
    parser.add_argument("keyword", nargs="?", default=None, help="窗口标题关键词")
    parser.add_argument("--region", type=str, default=None,
                        help="截图区域 x1,y1,x2,y2（相对于窗口左上角，像素）")
    parser.add_argument("--screen", type=str, default=None,
                        help="屏幕绝对坐标 x1,y1,x2,y2（自动换算为窗口内坐标）")
    parser.add_argument("--color", action="store_true", help="同时分析颜色（主色调/分布/色温等）")
    parser.add_argument("--qr", action="store_true", help="同时识别二维码/条形码")
    parser.add_argument("--save-debug", action="store_true", help="保存预处理图到桌面")
    args = parser.parse_args()

    # 无参数时打印菜单到聊天
    if not args.keyword and not args.region and not args.screen and not args.save_debug:
        print("🖥️ OCR 截图识别")
        print("─" * 30)
        print("说编号或命令开始：")
        print()
        print("  1  当前窗口")
        print("  2  浏览器")
        print("  3  桌面")
        print("  4  浏览器框选")
        print("  5  浏览器 + 颜色")
        print("  6  框选 + 颜色")
        sys.exit(0)

    # 菜单编号 → 命令（支持"4呢""4。"等模糊）
    MENU_MAP = {"1": "", "2": "浏览器", "3": "桌面", "4": "浏览器框选", "5": "浏览器", "6": "浏览器框选"}
    kw = args.keyword.strip() if args.keyword else ""
    menu_num = kw
    import re as _re
    if kw and kw[0].isdigit():
        m = _re.match(r"\d+", kw)
        if m:
            menu_num = m.group()
    if menu_num in MENU_MAP:
        mapped = MENU_MAP[menu_num]
        if mapped:
            args.keyword = mapped
            kw = mapped
        if menu_num in ("5", "6"):
            args.color = True

    # 特殊：框选模式 → 启动区域选择工具（阻塞，选完才回）
    kw = args.keyword.strip() if args.keyword else ""
    if kw == "框选" or kw == "select" or kw == "区域" or (kw.endswith("框选") and len(kw) > 2):
        sel_tool = os.path.join(os.path.dirname(os.path.abspath(__file__)), "区域选择.pyw")
        if not os.path.exists(sel_tool):
            print("未找到区域选择工具")
            sys.exit(1)

        # 组合关键词：仅激活目标窗口到前台，不动大小
        if kw.endswith("框选") and len(kw) > 2:
            base = kw[:-2]
            def find_hwnd(kw):
                result = []
                def cb(hwnd, _):
                    if win32gui.IsWindowVisible(hwnd) and kw.lower() in win32gui.GetWindowText(hwnd).lower():
                        result.append(hwnd)
                win32gui.EnumWindows(cb, None)
                return result[0] if result else None
            ALIASES = {
                "浏览器": ["edge", "chrome", "firefox", "browser", "iexplore"],
                "编辑器": ["code", "vim", "notepad", "sublime"],
                "终端": ["cmd", "powershell", "terminal", "console", "bash", "windows terminal"],
                "文件": ["explorer", "文件夹", "此电脑", "computer"],
            }
            candidates = [base]
            for cn, en_list in ALIASES.items():
                if cn in base:
                    candidates.extend(en_list)
            for c in candidates:
                h = find_hwnd(c)
                if h:
                    try:
                        # 用 SwitchToThisWindow 替代 SetForegroundWindow（不改窗口状态）
                        ctypes.windll.user32.SwitchToThisWindow(h, True)
                    except Exception:
                        pass
                    time.sleep(0.3)
                    break

        # 先清掉旧结果，避免读到上次的
        result_file = os.path.join("D:/Umi-OCR", "截图存档", "_框选结果.txt")
        try:
            os.remove(result_file)
        except:
            pass

        # 阻塞等待，选完点→OCR 才返回
        sel_args = [sys.executable, sel_tool, "--output-file", result_file]
        if args.color:
            sel_args.append("--color")
        if args.qr:
            sel_args.append("--qr")
        subprocess.run(sel_args, timeout=600)

        # 切回聊天（AttachThreadInput 绕过前台锁）
        try:
            def find_chat(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and "visual studio code" in win32gui.GetWindowText(hwnd).lower():
                    try:
                        cur_tid = ctypes.windll.user32.GetWindowThreadProcessId(
                            ctypes.windll.user32.GetForegroundWindow(), None)
                        tgt_tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
                        ctypes.windll.user32.AttachThreadInput(cur_tid, tgt_tid, True)
                        win32gui.SetForegroundWindow(hwnd)
                        win32gui.BringWindowToTop(hwnd)
                        ctypes.windll.user32.AttachThreadInput(cur_tid, tgt_tid, False)
                    except:
                        pass
            win32gui.EnumWindows(find_chat, None)
        except:
            pass
        time.sleep(0.3)

        # 读取结果
        if os.path.exists(result_file):
            with open(result_file, "r", encoding="utf-8") as f:
                content = f.read().strip()
            try:
                os.remove(result_file)
            except Exception:
                pass
            if content:
                print(content)
            else:
                print("（未识别到文字）")
        else:
            print("（未选择区域）")
        sys.exit(0)

    try:
        img, window_rect = capture_active_window(args.keyword)
    except Exception as e:
        print(f"截图失败: {e}")
        sys.exit(1)

    if not img:
        print("未找到匹配的窗口")
        # 列出可用窗口帮助用户
        all_wins = list_visible_windows()
        if all_wins:
            print("\n当前可见窗口列表：")
            for w in all_wins:
                print(f"  - {w}")
        sys.exit(1)

    # --screen 屏幕绝对坐标 → 窗口内坐标
    if args.screen:
        try:
            scr_str = args.screen.replace("，", ",").replace(" ", ",").replace("；", ",")
            parts = [int(x.strip()) for x in scr_str.split(",") if x.strip()]
            if len(parts) != 4:
                raise ValueError("需要 4 个值")
            sx1, sy1, sx2, sy2 = parts
            if window_rect:
                # 屏幕绝对坐标 → 窗口内坐标（减窗口左上角虚拟屏位置）
                wx, wy, _, _ = window_rect
                sx1 -= wx
                sy1 -= wy
                sx2 -= wx
                sy2 -= wy
            w, h = img.size
            if any(v < 0 for v in (sx1, sy1, sx2, sy2)):
                raise ValueError("坐标超出窗口范围（负数）")
            if sx2 <= sx1 or sy2 <= sy1:
                raise ValueError("x2>x1, y2>y1")
            if sx2 > w or sy2 > h:
                raise ValueError(f"坐标超出窗口范围 ({w}x{h})")
            img = img.crop((sx1, sy1, sx2, sy2))
        except ValueError as e:
            print(f"--screen 参数错误: {e}，正确格式: --screen x1,y1,x2,y2（屏幕绝对坐标）")
            sys.exit(1)

    # --region 裁剪（相对于窗口左上角）
    if args.region:
        try:
            # 兼容中文逗号
            region_str = args.region.replace("，", ",").replace(" ", ",").replace("；", ",")
            parts = [int(x.strip()) for x in region_str.split(",") if x.strip()]
            if len(parts) != 4:
                raise ValueError("需要 4 个值")
            rx1, ry1, rx2, ry2 = parts
            w, h = img.size
            if any(v < 0 for v in (rx1, ry1, rx2, ry2)):
                raise ValueError("坐标不能为负")
            if rx2 <= rx1 or ry2 <= ry1:
                raise ValueError("x2>x1, y2>y1")
            if rx2 > w or ry2 > h:
                raise ValueError(f"超出图片范围 ({w}x{h})")
            img = img.crop((rx1, ry1, rx2, ry2))
        except ValueError as e:
            print(f"--region 参数错误: {e}，正确格式: --region x1,y1,x2,y2（相对于窗口左上角）")
            sys.exit(1)

    # 自动保存截图原图
    save_dir = os.path.join("D:/Umi-OCR", "截图存档")
    os.makedirs(save_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(save_dir, f"截图_{timestamp}.png")
    img.save(save_path)
    print(f"[截图已保存] {save_path}")

    # 预处理
    try:
        processed = preprocess(img, save_debug=args.save_debug)
    except Exception as e:
        print(f"图像预处理失败: {e}")
        sys.exit(1)

    # OCR
    try:
        texts = ocr(processed, decode_qr=args.qr)
    except RuntimeError as e:
        print(e)
        sys.exit(1)
    except Exception as e:
        print(f"OCR 识别异常: {e}")
        sys.exit(1)

    # --qr 额外用 pyzbar 本地解码（不依赖 Umi-OCR 的二维码功能）
    qr_results = []
    if args.qr:
        try:
            from pyzbar.pyzbar import decode as qr_decode, ZBarSymbol
            seen = set()
            # 原图 + 缩小 0.7x 分别扫一次，提高小二维码检出率
            for scale in [1.0, 0.7]:
                if scale != 1.0:
                    w, h = img.size
                    scaled = img.resize((int(w*scale), int(h*scale)))
                else:
                    scaled = img
                qr_codes = qr_decode(scaled, symbols=[ZBarSymbol.QRCODE])
                for qr in qr_codes:
                    data = qr.data.decode('utf-8', errors='replace')
                    key = data[:50]
                    if key not in seen:
                        seen.add(key)
                        qr_results.append(f"[{qr.type}] {data}")
        except ImportError:
            pass

    # 输出结果
    if not texts:
        print("（未识别到文字）")
    else:
        for t in texts:
            print(t)

    # 输出二维码/条形码结果
    if qr_results:
        print()
        print("📱 识别到二维码/条码:")
        for q in qr_results:
            print(f"  {q}")

    # --color 颜色分析
    if args.color:
        try:
            from color_analysis import analyze_colors
            color_text, hist_img, pal_img = analyze_colors(img)
            print("\n" + "=" * 40)
            print("🎨 颜色分析")
            print("=" * 40)
            print(color_text)
            # 保存分析图
            hist_path = os.path.join(save_dir, f"分析_直方图_{timestamp}.png")
            pal_path = os.path.join(save_dir, f"分析_调色板_{timestamp}.png")
            hist_img.save(hist_path)
            pal_img.save(pal_path)
            print(f"[直方图] {hist_path}")
            print(f"[调色板] {pal_path}")
        except Exception as e:
            print(f"[颜色分析失败] {e}")


    # 截图完成后切回聊天窗口
    try:
        def _focus(hwnd, _):
            t = win32gui.GetWindowText(hwnd).lower()
            if win32gui.IsWindowVisible(hwnd) and 'visual studio code' in t:
                try:
                    ct = ctypes.windll.user32.GetWindowThreadProcessId(
                        ctypes.windll.user32.GetForegroundWindow(), None)
                    tt = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
                    ctypes.windll.user32.AttachThreadInput(ct, tt, True)
                    win32gui.SetForegroundWindow(hwnd)
                    win32gui.BringWindowToTop(hwnd)
                    ctypes.windll.user32.AttachThreadInput(ct, tt, False)
                except:
                    pass
        win32gui.EnumWindows(_focus, None)
    except:
        pass