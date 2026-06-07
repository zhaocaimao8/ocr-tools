---
name: ocr
description: "Use this skill when the user asks about what's on their screen, desktop, or window — such as '你看看我屏幕', '桌面有什么', '这个窗口的内容', '帮我看看', '我界面上有什么', '截屏', '截图', 'OCR', '识别'. This skill captures the active window, preprocesses the image (2x upscale, Otsu threshold, sharpen), and runs Umi-OCR to extract text."
---

# OCR 屏幕识别

截取窗口 → 预处理 → OCR 识别 → 可选颜色分析

## 快速开始

输入 `/ocr` 查看菜单，然后说编号或命令。

## 命令参考

| 命令 | 作用 |
|------|------|
| `/ocr` | 显示菜单 |
| `/ocr 当前` | 截当前活动窗口 |
| `/ocr 浏览器` | 截浏览器窗口 |
| `/ocr 桌面` | 截桌面（壁纸+图标） |
| `/ocr 框选` | 鼠标拖拽选区域 |
| `/ocr 浏览器框选` | 激活浏览器 + 拖拽框选 |
| `/ocr 浏览器 --color` | 截图 + OCR + 颜色分析 |
| `/ocr 浏览器框选 --color` | 框选 + OCR + 颜色分析 |
| `/ocr 浏览器 --region 10,10,400,300` | 窗口内坐标 |
| `/ocr 浏览器 --screen 316,170,540,300` | 屏幕绝对坐标 |

## 输出

截图自动保存到 `截图存档/`，颜色分析的直方图/调色板也存同目录。
