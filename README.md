# OCR 截图识别工具

Windows 桌面 OCR + 颜色分析 + 区域框选工具集。

## 工具列表

| 文件 | 功能 |
|------|------|
| [screen_ocr_v2.py](screen_ocr_v2.py) | OCR 主脚本 — 窗口截图 → Otsu预处理 → Umi-OCR 识别 |
| [区域选择.pyw](%E5%8C%BA%E5%9F%9F%E9%80%89%E6%8B%A9.pyw) | 鼠标拖拽框选工具，支持颜色分析 |
| [color_analysis.py](color_analysis.py) | 颜色分析模块（主色调、分布、色温、饱和度、RGB直方图） |
| [颜色分析.pyw](%E9%A2%9C%E8%89%B2%E5%88%86%E6%9E%90.pyw) | 独立颜色分析 GUI（选图片→分析） |
| [鼠标坐标.pyw](%E9%BC%A0%E6%A0%87%E5%9D%90%E6%A0%87.pyw) | 屏幕鼠标坐标浮动显示 |

## 依赖

- Python 3.8+
- `pip install pillow pywin32`
- **Umi-OCR**（离线识别引擎，需另外下载）

## Umi-OCR 下载

本仓库未包含 Umi-OCR 安装包（超出 GitHub 100MB 限制）。

前往官网下载：**[https://github.com/hiroi-sora/Umi-OCR/releases](https://github.com/hiroi-sora/Umi-OCR/releases)**

选 `Umi-OCR_Paddle_v2.1.5.zip` 版本，解压后保持后台运行即可。

## 快速使用

```bash
# 截当前窗口
python screen_ocr_v2.py

# 菜单编号
python screen_ocr_v2.py 1   # 当前窗口
python screen_ocr_v2.py 2   # 浏览器
python screen_ocr_v2.py 4   # 浏览器框选
python screen_ocr_v2.py 5   # 浏览器 + 颜色分析
python screen_ocr_v2.py 6   # 框选 + 颜色分析
```
