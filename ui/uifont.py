# -*- coding: utf-8 -*-
"""uifont.py — 统一界面字体。

两个和「字发虚」有关的点：

1. **像素字号**：Tk 传负数字号表示像素，正数表示 pt。pt 要乘 tk scaling（96dpi 下是
   1.3330053…），9pt 算出来是 11.997px，落在半像素上，GDI 就按灰色边缘去对齐，看起来
   发虚。这里一律换算成整数像素。
2. **font_scale**：觉得字小可以直接放大，不用改代码（config.json / --font-scale）。
"""
from __future__ import annotations

FAMILY = 'Microsoft YaHei UI'
FAMILY_MONO = 'Consolas'

SCALE = 1.0
PT_TO_PX = 1.34          # 96dpi 下 1pt ≈ 1.34px


def set_scale(value):
    global SCALE
    try:
        SCALE = max(0.7, min(2.5, float(value)))
    except (TypeError, ValueError):
        SCALE = 1.0
    return SCALE


def fnt(size, bold=False, mono=False):
    """size 沿用原来的「pt 语义」（10 ≈ 13px），但换算成整数像素再交给 Tk。"""
    px = max(9, int(round(float(size) * PT_TO_PX * SCALE)))
    return (FAMILY_MONO if mono else FAMILY, -px, 'bold' if bold else 'normal')
