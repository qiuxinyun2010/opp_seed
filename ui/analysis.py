# -*- coding: utf-8 -*-
"""analysis.py — 把 seed.py 的推理结果整理成「分析点位」，供前端按关卡渲染。

和 markers.py 的区别：
  markers.py  只按字段名瞎挖坐标，谁有 `*coordinates` 就画谁（通用、无关卡语义）。
  analysis.py 按关卡写适配器，决定「标哪些点、什么颜色、圆点里写什么字」，
              并可让前端在有分析点位时默认隐藏普通任务点位。

每条点位：

    {'p': [x, y, z],          世界坐标
     'room': 'RBRoom_X',      房间原始名（前端用来高亮房间、做 label 去重）
     'label': '密码',          圆点旁的文字（可为空）
     'badge': '0947',         圆点里的字（可为空）
     'color': '#f59e0b',      该点主色
     'kind': 'code',          语义：code/gem/section/pattern/panel/target/generic
     'size': 1.7,             圆点倍率（密码这种要多字就放大）
     'section': '',           原 section，前端 inspector 显示
     'exact': True}           是否 actor 级精确坐标（False = 房间中心）

build() 返回：

    {'level': 'CHJ_MT01', 'points': [...], 'legend': [{'label','color'}],
     'hide_points': True, 'note': ''}
"""

from __future__ import annotations

import markers as _markers

# 宝石颜色（RES_MT02）
GEM_STYLE = {
    'Ruby':     ('红', '#e11d48'),
    'Sapphire': ('蓝', '#3b82f6'),
    'Emerald':  ('绿', '#10b981'),
    'Topaz':    ('黄', '#eab308'),
    'Amethyst': ('紫', '#a855f7'),
}
GEM_DEFAULT = ('宝', '#a855f7')

# CHJ_MT01 三个密码房配色（顺序固定，和游戏里 1/2/3 号对应）
CODE_COLORS = ['#f59e0b', '#8b5cf6', '#0ea5e9']

# PSA_MT01 图案配色（按出现顺序循环）
PATTERN_COLORS = ['#0ea5e9', '#f59e0b', '#10b981', '#e11d48',
                  '#a855f7', '#14b8a6', '#ef4444', '#64748b']

PANEL_COLOR = '#14b8a6'
TARGET_COLOR = '#f43f5e'

# TFS_MT03：阀门按 A / B 两大区着色（和地图分区颜色一致）
TFS_AREA_COLORS = {'A': '#1d4ed8', 'B': '#b45309'}
TFS_AREA_NAMES = {'A': 'A 区（A1/A2/A3）', 'B': 'B 区（B1/B2/B3）'}

# CHJ_MT02：五种投影图案各自配色
PROJECTION_STYLE = {
    'Skull':          ('骷髅', '#e11d48'),
    'Spiral':         ('螺旋', '#8b5cf6'),
    'Pentagram':      ('五角星', '#f59e0b'),
    'Sun':            ('太阳', '#eab308'),
    'TriangleCircle': ('三角', '#14b8a6'),
}
PROJECTION_DEFAULT = ('图案', '#64748b')
TUTORIAL_COLOR = '#94a3b8'

# SRR_MT01：5 栋富豪宅各自配色
SRR_HOUSE_COLORS = {
    'H1': '#f59e0b', 'H2': '#8b5cf6', 'H3': '#0ea5e9',
    'H4': '#10b981', 'H5': '#e11d48',
}
SRR_HOUSE_DEFAULT = '#64748b'

# SMC_MT02 人偶下半身配色（按游戏里人偶颜色）
MANNEQUIN_STYLE = {
    'Red':      ('红', '#e11d48'),
    'Green':    ('绿', '#10b981'),
    'Blue':     ('蓝', '#3b82f6'),
    'Tutorial': ('教学', '#94a3b8'),
}
MANNEQUIN_DEFAULT = ('人偶', '#a855f7')
MANNEQUIN_ORDER = ['红', '绿', '蓝', '教学']


def _pt(p, room='', label='', badge='', color='#14b8a6', kind='generic',
        size=1.0, section='', exact=True):
    return {
        'p': [round(float(v), 1) for v in p],
        'room': room or '',
        'label': label or '',
        'badge': str(badge) if badge not in (None, '') else '',
        'color': color,
        'kind': kind,
        'size': size,
        'section': section or '',
        'exact': exact,
    }


def _legend(pairs):
    seen = []
    for label, color in pairs:
        if label and all(label != s[0] for s in seen):
            seen.append((label, color))
    return [{'label': l, 'color': c} for l, c in seen]


def _coords(item):
    p = item.get('coordinates')
    if isinstance(p, (list, tuple)) and len(p) == 3:
        return p
    return None


def _exact(item):
    return (item.get('coordinate_type') or '') != 'room_center'


# --------------------------------------------------------------------------
# 各关卡适配器
# --------------------------------------------------------------------------

def _chj_mt01(data):
    """3 个密码房：房间中心 + 4 位密码。"""
    points, legend = [], []
    for room in data.get('rooms') or []:
        p = _coords(room)
        if not p:
            continue
        idx = int(room.get('index') or (len(points) + 1))
        color = CODE_COLORS[(idx - 1) % len(CODE_COLORS)]
        code = str(room.get('code') or '')
        points.append(_pt(p, room.get('room'), '%d 号密码房' % idx, code,
                          color, 'code', 1.9, exact=_exact(room)))
        legend.append(('%d 号密码房' % idx, color))
    return points, _legend(legend)


def _chj_mt02(data):
    """4 个真投影机位 + 1 个教学机位：颜色=图案，圆点里写编号。"""
    points, legend = [], []
    order = ['Skull', 'Spiral', 'Pentagram', 'Sun', 'TriangleCircle']
    for proj in data.get('projections') or []:
        p = _coords(proj)
        if not p:
            continue
        symbol = str(proj.get('symbol') or '')
        name, color = PROJECTION_STYLE.get(symbol, PROJECTION_DEFAULT)
        name = proj.get('symbol_name') or name
        tutorial = bool(proj.get('tutorial'))
        if tutorial:
            color = TUTORIAL_COLOR
        points.append(_pt(p, proj.get('room'), name, proj.get('code'), color,
                          'symbol', 1.7, section=symbol, exact=_exact(proj)))
        legend.append(('教学 · %s' % name if tutorial else name, color))

    def _rank(m):
        index = order.index(m['section']) if m['section'] in order else 99
        return index
    points.sort(key=_rank)
    return points, _legend(legend)


def _res_mt02(data):
    """26 颗宝石：颜色即宝石颜色，圆点里写 红/蓝/绿。"""
    points, legend = [], []
    for gem in data.get('jewels') or []:
        p = _coords(gem)
        if not p:
            continue
        ch, color = GEM_STYLE.get(gem.get('gem'), GEM_DEFAULT)
        points.append(_pt(p, gem.get('room'), '', ch, color, 'gem', 1.15,
                          section=gem.get('gem_cn') or gem.get('gem') or ''))
        legend.append((gem.get('gem_cn') or gem.get('gem') or ch, color))
    return points, _legend(legend)


def _tfs_mt03(data):
    """6 个阀门：按 A / B 两大区着色，圆点里写小节号 A1/A2/B3…"""
    points = []
    for valve in data.get('valves') or []:
        p = _coords(valve)
        if not p:
            continue
        section = str(valve.get('section') or '')
        area = section[:1].upper()
        color = TFS_AREA_COLORS.get(area, '#64748b')
        points.append(_pt(p, valve.get('room'), '%s 区阀门' % area, section, color,
                          'valve', 1.5, section=section, exact=_exact(valve)))
    points.sort(key=lambda m: (m['badge'][:1], m['badge'][1:]))
    return points, _legend([(TFS_AREA_NAMES[a], TFS_AREA_COLORS[a]) for a in ('A', 'B')])


def _psa_mt01(data):
    """图案钥匙：每个点位标注对应图案。"""
    points, legend = [], []
    palette = {}
    for step in data.get('path') or []:
        p = _coords(step)
        if not p:
            continue
        symbol = str(step.get('symbol') or step.get('symbol_name_zh') or '')
        if symbol not in palette:
            palette[symbol] = PATTERN_COLORS[len(palette) % len(PATTERN_COLORS)]
        color = palette[symbol]
        name = step.get('symbol_name_zh') or symbol
        points.append(_pt(p, step.get('room'), name, '', color, 'pattern', 1.15,
                          section='key' if step.get('kind') == 'key' else 'reel',
                          exact=_exact(step)))
        legend.append((name, color))
    return points, _legend(legend)


def _dts_mt01(data):
    """调频器位置 + 目标人偶。"""
    points, legend = [], []
    for panel in data.get('frequency_panels') or []:
        p = _coords(panel)
        if not p:
            continue
        points.append(_pt(p, panel.get('room'), '调频器', '', PANEL_COLOR,
                          'panel', 1.0, section='panel', exact=_exact(panel)))
        legend.append(('调频器', PANEL_COLOR))
    target = data.get('target_model') or {}
    p = _coords(target)
    if p:
        points.append(_pt(p, target.get('room'), '目标人偶', '', TARGET_COLOR,
                          'target', 1.35, section='target', exact=_exact(target)))
        legend.append(('目标人偶', TARGET_COLOR))
    return points, _legend(legend)


def _smc_mt02(data):
    """4 个人偶下半身：按人偶颜色着色，圆点里写 红/绿/蓝/教学。"""
    points, legend = [], []
    for man in data.get('mannequins') or []:
        p = _coords(man)
        if not p:
            continue
        ch, color = MANNEQUIN_STYLE.get(man.get('color'), MANNEQUIN_DEFAULT)
        points.append(_pt(p, man.get('room'), '', man.get('color_name') or ch,
                          color, 'mannequin', 1.25, man.get('section'),
                          _exact(man)))
        legend.append(('%s人偶' % (man.get('color_name') or ch), color))
    def _rank(m):
        return MANNEQUIN_ORDER.index(m['badge']) if m['badge'] in MANNEQUIN_ORDER else 99
    points.sort(key=_rank)
    return points, _legend(legend)


def _srr_mt01(data):
    """密码盘点位：只画「哪个房间的密码盘」，圆点里写 4 位密码（不画贴花位）。

    本局激活的 3 栋按宅子着色；另外 2 栋画灰色备用点，判错时也能试。
    """
    points, legend = [], []
    houses = data.get('houses') or []
    order = ([h for h in houses if h.get('selected')]
             + [h for h in houses if not h.get('selected')])
    for house in order:
        tag = house.get('tag') or ''
        p = _coords(house)
        if not p:
            continue
        if house.get('selected'):
            color = SRR_HOUSE_COLORS.get(tag, SRR_HOUSE_DEFAULT)
            points.append(_pt(p, house.get('pad_room'), '%s 密码盘' % tag,
                              house.get('code'), color, 'code', 1.9,
                              section=tag, exact=_exact(house)))
            legend.append(('%s 密码房' % tag, color))
        else:
            points.append(_pt(p, house.get('pad_room'),
                              '%s 备用密码盘' % tag, house.get('code'),
                              SRR_HOUSE_DEFAULT, 'spare', 1.35,
                              section='备用', exact=_exact(house)))
            legend.append(('备用密码盘', SRR_HOUSE_DEFAULT))
    return points, _legend(legend)


def _generic(data):
    """未单独适配的关卡：沿用 markers.py 的通用挖坐标。"""
    points = []
    for m in _markers.collect(data):
        color = '#f43f5e' if m.get('kind') == 'goal' else '#14b8a6'
        points.append(_pt(m['p'], m.get('room'), m.get('label'), '', color,
                          'generic', 1.0, m.get('section'),
                          m.get('exact', True)))
    return points, []


ADAPTERS = {
    'CHJ_MT01': _chj_mt01,
    'CHJ_MT02': _chj_mt02,
    'RES_MT02': _res_mt02,
    'TFS_MT03': _tfs_mt03,
    'PSA_MT01': _psa_mt01,
    'DTS_MT01': _dts_mt01,
    'SMC_MT02': _smc_mt02,
    'SRR_MT01': _srr_mt01,
}


def build(result):
    """result = seed.py predict() 的返回值。返回前端要的分析点位包。"""
    level = str((result or {}).get('level') or '').upper()
    adapter = ADAPTERS.get(level)
    try:
        points, legend = adapter(result) if adapter else _generic(result)
    except Exception as exc:                     # 单关适配器出错不能拖垮整页
        return {'level': level, 'points': [], 'legend': [], 'hide_points': False,
                'note': '分析点位生成失败: %s' % exc}
    return {
        'level': level,
        'points': points,
        'legend': legend,
        'hide_points': bool(points),
        'note': '',
    }
