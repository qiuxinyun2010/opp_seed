# -*- coding: utf-8 -*-
"""mapview.py — 基于 mapdb.py 产物的实时渲染 demo（Tkinter）

读 data/maps/<关卡>.json 直接画，名称默认英文（有备注则显示备注）：
  - 叠加模式：所有楼层一起画（不关心垂直高度）
  - 分层模式：只看某一层，其它层留淡轮廓做参照
  - 默认只标「有任务点位的房间」和「有备注的房间」，不再满图房间名
  - 左键点房间/点位 → 显示信息并自动复制名字（按住拖动 = 平移地图）
  - 左上角图例默认不显示，工具栏 legend / H 切换；单击分区切显示，双击改分区名
  - 双击房间/点位 → 加备注，直接写回这份 JSON；N 键编辑当前选中项的备注
  - 滚轮缩放、左键/中键/右键拖动平移、F 适应窗口、1/2/3 切层、O 叠加、Esc 取消选中
  - 自动跟随游戏日志：日志里出现 Trial ID + Seed 就刷新答案（**不等 StageReady**）
  - 全局快捷键 Ctrl+A（config.json 可改）：显示/收起窗口；点 X 只收起，Quit 才退出
  - 房间里点击/复制的一律是**原始名**（`RBRoom_...`），中文/备注只做显示

用法：
    python mapview.py                     # 什么都不用给：等日志，读到关卡就加载地图
    python mapview.py PSA_MT01            # 锁定这一关（不跟日志自动切换）
    python mapview.py --png a.png         # 无窗口导出（不带关卡时用日志里那一关）
    python mapview.py PSA_MT01 --png a.png --mode floor --floor 1
    python mapview.py --list              # 有哪些关卡数据
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import tkinter as tk

try:
    import ctypes
    import ctypes.wintypes as wt
except Exception:                       # pragma: no cover - 非 Windows
    ctypes = None
    wt = None

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, 'data', 'maps')
CONFIG_PATH = os.path.join(HERE, 'config.json')

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gamelog                        # noqa: E402  日志 → 本局关卡/种子
import markers                        # noqa: E402  答案里的坐标 → 地图标记
import seedpanel                      # noqa: E402  右侧「本局答案」面板
from uifont import fnt, set_scale     # noqa: E402  统一字体（整数像素）
try:
    import hotkey                     # noqa: E402  全局快捷键（仅 Windows）
except Exception:                     # pragma: no cover
    hotkey = None

DEFAULT_CONFIG = {
    '_说明': 'log_path 留空=自动找 %LOCALAPPDATA%/OPP/Saved/Logs/OPP.log；'
             'hotkey 写 ctrl+a / M / F1~F12，写 none 关闭；seed_lib 留空=上级目录的 seed.py；'
             'font_scale 调字号（1.0 默认，嫌小就 1.15）；show_legend 图例默认关；'
             'flip 镜像方式（none/x/y/xy，空=按 data/orientation.json，缺省 x）；'
             'close_action=hide 时点窗口 X 只是收起（Ctrl+A 再叫出来），quit 才退出进程',
    'log_path': None,
    'hotkey': 'ctrl+a',
    'seed_lib': None,
    'panel_width': 440,
    'window': '1440x960',
    'activate_on_hotkey': True,
    'always_topmost': True,
    'follow_game': True,
    'poll_log': True,
    'poll_interval_ms': 900,
    'font_scale': 1.0,
    'show_legend': False,        # 左上角图例默认不显示（工具栏 legend / H 切换）
    'flip': None,                # 镜像：None=按 data/orientation.json（缺省左右镜像 x）
    'close_action': 'hide',      # 点窗口 X：hide=只收起（Ctrl+A 叫回来）/ quit=退出进程
}

BG = '#f6f8fb'
INK = '#1f2c38'
MUTED = '#7d8b99'
SELECT = '#f59e0b'
POINT_CLUE = '#ffffff'
POINT_GOAL = '#e11d48'
NOTE_COLOR = '#0f766e'
SEED_CLUE = '#0f766e'

FONT_PATHS = ['C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simhei.ttf']


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding='utf-8') as fp:
                cfg.update({k: v for k, v in json.load(fp).items() if not k.startswith('_')})
        except Exception:
            pass
    else:
        write_config({k: v for k, v in DEFAULT_CONFIG.items() if not k.startswith('_')})
    return cfg


def write_config(values):
    """只改传入的键，其余保持 config.json 原样。

    这样 --hotkey none / --log 这类「这一次的命令行参数」不会在关窗口时被写进配置。
    """
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding='utf-8') as fp:
                data = {k: v for k, v in json.load(fp).items() if not k.startswith('_')}
        except Exception:
            data = {}
    data.update(values or {})
    out = {'_说明': DEFAULT_CONFIG['_说明']}
    out.update(data)
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as fp:
            json.dump(out, fp, ensure_ascii=False, indent=1)
    except Exception:
        pass


VERSION = '2026-10-29.6'     # 显示在标题栏，方便确认跑的是不是最新的这一版

ORIENTATION_PATH = os.path.join(HERE, 'data', 'orientation.json')
DEFAULT_FLIP = 'x'          # 交付版地图是左右镜像的，见 data/orientation.json 的说明


def load_orientation():
    """地图名 / 关卡 → 'none' | 'x' | 'y' | 'xy'（镜像方式）。"""
    try:
        with open(ORIENTATION_PATH, encoding='utf-8') as fp:
            return {k: v for k, v in json.load(fp).items() if not k.startswith('_')}
    except Exception:
        return {}


def flip_of(value):
    """'x' → (True, False)；'xy' → (True, True)；'none' → (False, False)。"""
    s = str(value or '').strip().lower()
    return ('x' in s, 'y' in s)


def resolve_flip(db, cfg=None, table=None):
    """优先级：命令行/config 里的 flip → data/orientation.json → 交付版默认（左右镜像）。"""
    forced = (cfg or {}).get('flip')
    if forced:
        return flip_of(forced)
    table = load_orientation() if table is None else table
    db = db or {}
    for key in (db.get('map'), db.get('level')):
        if key and key in table:
            return flip_of(table[key])
    return flip_of(DEFAULT_FLIP)


def enable_dpi_awareness():
    """告诉 Windows「我自己处理缩放」。

    不声明 DPI 感知时，系统会把整个窗口当位图放大（125%/150% 缩放下字就发虚），
    声明之后 Tk 按物理像素绘制，字形和线条才是清晰的。
    """
    if os.name != 'nt' or ctypes is None:
        return False
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)      # SYSTEM_DPI_AWARE
        return True
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
        return True
    except Exception:
        return False


# 门类型：key -> (英文名, 颜色, 线宽, 虚线)
DOOR_KINDS = {
    'spawn':    ('Spawn door (monster closet)', '#dc2626', 3.0, (4, 2)),
    'normal':   ('Normal door', '#8b5cf6', 2.0, None),
    'rolling':  ('Rolling / shutter', '#2563eb', 2.0, None),
    'sliding':  ('Sliding door', '#0891b2', 2.0, None),
    'access':   ('Access door (SAS / employee)', '#b45309', 2.0, None),
    'backdrop': ('Backdrop door', '#94a3b8', 1.4, (2, 2)),
    'other':    ('Other door', '#6b7280', 2.0, None),
}
DOOR_KIND_ORDER = ['spawn', 'normal', 'rolling', 'sliding', 'access', 'backdrop', 'other']
TRIAL_ONLY_STYLE = ('Trial-only door', '#111827', 3.0, (5, 3))


def door_style(door):
    """本关专属门优先于普通类型；刷怪门再优先。"""
    kind = door.get('kind') or 'other'
    if kind == 'spawn':
        _n, color, width, dash = DOOR_KINDS['spawn']
    elif door.get('trial_only'):
        _n, color, width, dash = TRIAL_ONLY_STYLE
    else:
        _n, color, width, dash = DOOR_KINDS.get(kind, DOOR_KINDS['other'])
    if door.get('trial_only') and kind == 'spawn':
        width += 0.6
    return color, width, dash


def door_kind_label(door):
    kind = door.get('kind') or 'other'
    label = DOOR_KINDS.get(kind, DOOR_KINDS['other'])[0]
    if door.get('trial_only'):
        label += '  (trial-only)'
    return label


# ---------------------------------------------------------------------------
# 视图变换（世界坐标 → 屏幕像素）
# ---------------------------------------------------------------------------
class View(object):
    """世界坐标 → 屏幕像素。顺序：镜像 → 缩放平移 → 旋转（只能是 90° 的整数倍）。

    旋转在**屏幕空间**绕视图中心做，所以文字位置跟着转、字形本身不受影响
    （Tk 的文字永远是水平的）。
    """

    def __init__(self, db=None, flipx=False, flipy=False):
        x0, y0, x1, y1 = (db or {}).get('bbox') or (0.0, 0.0, 1.0, 1.0)
        self.box = (x0, y0, x1, y1)
        self.scale = 1.0
        self.ox = 0.0
        self.oy = 0.0
        self.w, self.h = 800, 600
        self.flipx = bool(flipx)
        self.flipy = bool(flipy)
        self.turns = 0                       # 0..3，每次 +1 = 顺时针 90°

    # -- 镜像 / 旋转
    def _flip(self, x, y):
        return (-x if self.flipx else x, -y if self.flipy else y)

    def display_box(self):
        """镜像之后的取景框（fit / 居中都用它）。"""
        x0, y0, x1, y1 = self.box
        if self.flipx:
            x0, x1 = -x1, -x0
        if self.flipy:
            y0, y1 = -y1, -y0
        return x0, y0, x1, y1

    def quarter_turned(self):
        return self.turns % 4 in (1, 3)

    def _rot(self, sx, sy):
        t = self.turns % 4
        if not t:
            return sx, sy
        ax, ay = self.w / 2.0, self.h / 2.0
        dx, dy = sx - ax, sy - ay
        if t == 1:
            return ax - dy, ay + dx
        if t == 2:
            return ax - dx, ay - dy
        return ax + dy, ay - dx

    def _unrot(self, sx, sy):
        t = self.turns % 4
        if not t:
            return sx, sy
        ax, ay = self.w / 2.0, self.h / 2.0
        dx, dy = sx - ax, sy - ay
        if t == 1:
            return ax + dy, ay - dx
        if t == 2:
            return ax - dx, ay - dy
        return ax - dy, ay + dx

    def fit(self, w, h, pad=46):
        x0, y0, x1, y1 = self.box
        self.w, self.h = max(1, w), max(1, h)
        bw = max(1.0, x1 - x0)
        bh = max(1.0, y1 - y0)
        if self.quarter_turned():            # 转 90° 后屏幕上的宽高互换
            bw, bh = bh, bw
        self.scale = min((w - 2 * pad) / bw, (h - 2 * pad) / bh)
        # 居中要用「镜像之后」的中心，否则镜像时整张图会偏到一边
        cx, cy = self._flip((x0 + x1) / 2.0, (y0 + y1) / 2.0)
        self.ox = w / 2.0 - cx * self.scale
        self.oy = h / 2.0 + cy * self.scale

    def clamp(self, margin=60):
        """别让地图被拖/缩到完全看不见（至少留 margin 像素在窗口里）。

        以前没有这个限制：拖远了再滚轮放大，图会整块飞出视野，看起来就是「跳到别处」。
        """
        x0, y0, x1, y1 = self.box
        pts = [self.pt(x0, y0), self.pt(x1, y0), self.pt(x0, y1), self.pt(x1, y1)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        dx = dy = 0.0
        if max(xs) < margin:
            dx = margin - max(xs)
        elif min(xs) > self.w - margin:
            dx = (self.w - margin) - min(xs)
        if max(ys) < margin:
            dy = margin - max(ys)
        elif min(ys) > self.h - margin:
            dy = (self.h - margin) - min(ys)
        if dx or dy:
            self.pan_by(dx, dy)
            return True
        return False

    def pan_by(self, dx, dy):
        """按屏幕像素平移视图。

        屏幕位移要先「反旋转」再折到 ox/oy 上：旋转 90°/270° 时，屏幕上的 (dx, dy)
        对应的是 ox/oy 的 (dy, -dx)。以前直接把 (dx, dy) 加到 ox/oy，拖动过程用
        canvas.move 看着是对的，但下一次重绘（比如点房间）位置就会跳到别处。
        """
        t = self.turns % 4
        if not t:
            ux, uy = dx, dy
        elif t == 1:
            ux, uy = dy, -dx
        elif t == 2:
            ux, uy = -dx, -dy
        else:
            ux, uy = -dy, dx
        self.ox += ux
        self.oy += uy

    def pt(self, x, y):
        x, y = self._flip(x, y)
        return self._rot(self.ox + x * self.scale, self.oy - y * self.scale)

    def inv(self, sx, sy):
        px, py = self._unrot(sx, sy)
        return self._flip((px - self.ox) / self.scale, (self.oy - py) / self.scale)

    def zoom_at(self, sx, sy, factor):
        """以光标处的点为锚缩放（先去掉旋转，改完 scale 再让同一点回到原位）。"""
        px, py = self._unrot(sx, sy)
        fx = (px - self.ox) / self.scale
        fy = (self.oy - py) / self.scale
        self.scale = max(0.005, min(3.0, self.scale * factor))
        self.ox = px - fx * self.scale
        self.oy = py + fy * self.scale


# ---------------------------------------------------------------------------
# 命名与备注
# ---------------------------------------------------------------------------
def notes_of(db, kind):
    return (db.get('notes') or {}).get(kind) or {}


def note_of(db, kind, key):
    return notes_of(db, kind).get(key) or ''


def room_label(db, room):
    return note_of(db, 'rooms', room['raw']) or room.get('name') or room['raw']


def zone_label(db, zone):
    return note_of(db, 'zones', zone['id']) or zone.get('name') or zone['id']


def tint(hexcolor, amount=0.82):
    c = (hexcolor or '#94a3b8').lstrip('#')
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    return '#%02x%02x%02x' % (int(r + (255 - r) * amount),
                              int(g + (255 - g) * amount),
                              int(b + (255 - b) * amount))


def zone_color(db, zid):
    for z in db['zones']:
        if z['id'] == zid:
            return z['color']
    return '#7f93a8'          # 未分区（该关卡还没有 zones 配置）


def floor_name(db, idx):
    for f in db['floors']:
        if f['index'] == idx:
            return f['label']
    return None


class State(object):
    def __init__(self):
        self.mode = 'overlay'          # overlay | floor
        self.floor = 0
        self.show_doors = True
        self.show_points = True
        self.show_items = False
        self.show_all_names = False
        self.show_seed = True          # 本局答案里的坐标标记
        self.show_legend = False       # 左上角图例：默认不显示，免得挡地图
        self.seed_markers = []
        self.hidden_zones = set()      # 图例里点掉的分区
        self.sel = None                # ('room'|'point'|'door'|'item'|'seed', id)


# ---------------------------------------------------------------------------
# 场景：db + 视图状态 → 绘图指令（与具体后端无关）
# ---------------------------------------------------------------------------
def build_ops(db, state, view):
    ops = []
    sel = state.sel
    hidden = state.hidden_zones
    rooms = db['rooms']
    points = db.get('points') or []
    items = db.get('items') or []

    def zone_hidden(zid):
        return zid in hidden

    # ---- 房间 ----
    # 叠加模式：按楼层排序，高层压在上面，越高的层填色越饱和
    # 分层模式：先画其它层的轮廓（背景色填充，因此仍可点选），再画本层
    if state.mode == 'floor':
        context = [r for r in rooms
                   if r['floors'] and state.floor not in r['floors'] and not zone_hidden(r['zone'])]
        visible = [r for r in rooms
                   if not (r['floors'] and state.floor not in r['floors'])
                   and not zone_hidden(r['zone'])]
    else:
        context = []
        visible = sorted((r for r in rooms if not zone_hidden(r['zone'])),
                         key=lambda r: max(r['floors'] or [0]))

    for r in context:
        for h in r['hulls']:
            ops.append(('poly', [view.pt(x, y) for x, y in h],
                        BG, '#dbe3ec', 1.0, ('room', r['id']), (2, 3)))

    for r in visible:
        color = zone_color(db, r['zone'])
        top = max(r['floors'] or [0])
        amount = max(0.55, 0.86 - 0.16 * top) if state.mode == 'overlay' else 0.86
        if r['kind'] == 'corridor':
            fill, stroke = tint(color, min(0.95, amount + 0.10)), tint(color, 0.55)
        else:
            fill, stroke = tint(color, amount), color
        if not r['zone']:
            # 没有分区配置的关卡：用中性色，避免整张图糊成一片白
            fill, stroke = ('#eef2f7' if r['kind'] == 'corridor' else '#e3eaf2'), '#a9bacb'
        hot = bool(sel and sel[0] == 'room' and sel[1] == r['id'])
        if not hot and sel and sel[0] == 'seed' and state.seed_markers:
            mk = state.seed_markers[sel[1]] if sel[1] < len(state.seed_markers) else None
            hot = bool(mk and mk.get('room') == r['raw'])
        if hot:
            fill, stroke = '#fef3c7', SELECT
        width = 3.0 if hot else 1.6
        for h in r['hulls']:
            ops.append(('poly', [view.pt(x, y) for x, y in h],
                        fill, stroke, width, ('room', r['id']), None))

    # ---- 门（按类型上色：刷怪门/本关专属门最显眼）----
    if state.show_doors and db.get('doors'):
        for d in db['doors']:
            if state.mode == 'floor' and d.get('floor') is not None and d['floor'] != state.floor:
                continue
            x, y, _z = d['p']
            half = max(160.0, d.get('w') or 230) / 2.0
            dx, dy = _dir((d.get('yaw') or 0.0) + 90.0)
            color, width, dash = door_style(d)
            ops.append(('line', [view.pt(x - dx * half, y - dy * half),
                                 view.pt(x + dx * half, y + dy * half)],
                        color, width, dash, ('door', d['id'])))

    # ---- 交互物品（默认不提取，配置里打开才有）----
    if state.show_items and items:
        for it in items:
            if state.mode == 'floor' and it.get('floor') is not None and it['floor'] != state.floor:
                continue
            ops.append(('circle', view.pt(it['p'][0], it['p'][1]), 2.5, '#94a3b8', None, 0.0,
                        ('item', it['id'])))

    # ---- 房间名 ----
    # 默认只标：有任务点位的房间 + 有备注的房间（备注优先显示）
    # 勾选 “All names” 后标全部房间（点位不准时用）
    point_rooms = {p['room'] for p in points if p.get('room') is not None}
    placed = []
    if state.show_all_names:
        cand = list(visible)
    else:
        cand = [r for r in visible
                if r['id'] in point_rooms or note_of(db, 'rooms', r['raw'])]
    cand.sort(key=lambda r: -r['area'])
    for r in cand:
        x0, y0, x1, y1 = _scr_bbox(view, r)
        w, h = x1 - x0, y1 - y0
        if w < 26 or h < 12:
            continue
        has_note = bool(note_of(db, 'rooms', r['raw']))
        size = 11
        # 房间太窄时允许标签溢出到房间外（重叠由 placed 检测兜住）
        text = _fit_text(room_label(db, r), size, max(w - 8, 92))
        if not text:
            continue
        sx, sy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        tw = _text_w(text, size)
        box = (sx - tw / 2 - 3, sy - size * 0.7, sx + tw / 2 + 3, sy + size * 0.7)
        if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3])
               for b in placed):
            continue
        placed.append(box)
        # 标签不参与命中：下面还有房间多边形/门/点位，别让文字抢点击
        ops.append(('text', (sx, sy), text, size,
                    NOTE_COLOR if has_note else '#334155', 'mm', has_note, None))

    # ---- 任务点位（画在房间名之上）----
    if state.show_points:
        vis = [p for p in points
               if not (state.mode == 'floor' and p.get('floor') is not None
                       and p['floor'] != state.floor)
               and not zone_hidden(p.get('zone'))]
        # 点位太多时只标编号，短名放到信息栏（避免满屏文字）
        with_name = len(vis) <= 12
        for p in vis:
            sx, sy = view.pt(p['p'][0], p['p'][1])
            goal = (p.get('style') or '') != 'clue'
            color = zone_color(db, p.get('zone'))
            r = 12.0 if sel == ('point', p['id']) else 9.0
            ops.append(('circle', (sx, sy), r + 2.5,
                        POINT_GOAL if goal else '#ffffff', color, 2.0, ('point', p['id'])))
            ops.append(('circle', (sx, sy), r - 1.0,
                        POINT_GOAL if goal else POINT_CLUE, color, 1.6, ('point', p['id'])))
            ops.append(('text', (sx, sy), str(p.get('num') or ''), 10,
                        '#ffffff' if goal else INK, 'mm', True, ('point', p['id'])))
            if with_name or sel == ('point', p['id']):
                ops.append(('text', (sx + r + 6, sy - r - 4), p.get('short') or '',
                            10, INK, 'lm', False, ('point', p['id'])))

    # ---- 本局答案里的坐标标记（画在最上层）----
    if state.show_seed and state.seed_markers:
        band = None
        if state.mode == 'floor':
            band = next((f.get('band') for f in db['floors'] if f['index'] == state.floor), None)
        for i, m in enumerate(state.seed_markers):
            if band and len(m['p']) > 2:
                lo, hi = band[0], band[1]
                z = m['p'][2]
                if ((lo is not None and z < lo - 200) or (hi is not None and z > hi + 200)):
                    continue                      # 不在当前楼层
            sx, sy = view.pt(m['p'][0], m['p'][1])
            if not (0 <= sx <= view.w and 0 <= sy <= view.h):
                continue
            picked = sel == ('seed', i)
            goal = m.get('kind') == 'goal'
            color = '#dc2626' if goal else SEED_CLUE
            r = 12.0 if picked else 9.0
            # 钉头：实心圆 + 白色描边；只有房间中心坐标（≈）用虚线空心
            if m.get('exact', True):
                ops.append(('circle', (sx, sy), r + 2.5, color, '#ffffff', 2.0, ('seed', i)))
                ops.append(('circle', (sx, sy), r - 2.0, '#ffffff', color, 1.6, ('seed', i)))
            else:
                ops.append(('circle', (sx, sy), r + 2.5, '#ffffff', color, 2.0, ('seed', i)))
                ops.append(('circle', (sx, sy), r - 2.0, None, color, 1.4, ('seed', i)))
            ops.append(('text', (sx, sy), str(i + 1), 10,
                        color if m.get('exact', True) else '#ffffff', 'mm', True, ('seed', i)))
            ops.append(('text', (sx + r + 6, sy - r - 4), m.get('label') or '',
                        10, color, 'lm', True, ('seed', i)))

    # ---- 图例 / 分区交互 ----
    ops.extend(_legend_ops(db, state))

    # ---- 右下角模式 ----
    if state.mode == 'overlay':
        mode_txt = 'Overlay · all floors (%d)' % len(db['floors'])
    else:
        mode_txt = 'Floor · %s' % (floor_name(db, state.floor) or '?')
    turns = getattr(view, 'turns', 0) % 4
    if turns:
        mode_txt += ' · rot %d°' % (turns * 90)
    if getattr(view, 'flipx', False):
        mode_txt += ' · mirror X'
    if getattr(view, 'flipy', False):
        mode_txt += ' · mirror Y'
    ops.append(('text', (view.w - 14, view.h - 14), mode_txt, 11, MUTED, 'rm', False, None))
    return ops


def _dir(deg):
    import math
    r = math.radians(deg)
    return math.cos(r), math.sin(r)


def _scr_bbox(view, room):
    xs, ys = [], []
    for hull in room['hulls']:
        for x, y in hull:
            px, py = view.pt(x, y)
            xs.append(px)
            ys.append(py)
    if not xs:
        return (0, 0, 0, 0)
    return (min(xs), min(ys), max(xs), max(ys))


def _text_w(text, size):
    w = 0.0
    for ch in text or '':
        w += size * (1.0 if ord(ch) > 0x2e80 else 0.56)
    return w


def _fit_text(text, size, max_w):
    if not text or _text_w(text, size) <= max_w:
        return text
    out = ''
    for ch in text:
        if _text_w(out + ch + '…', size) > max_w:
            break
        out += ch
    return (out + '…') if out else ''


def _legend_ops(db, state):
    """左上角图例（默认关闭）：工具栏 legend / H 切换；单击分区切换显示，双击改分区名。"""
    if not getattr(state, 'show_legend', False):
        return []
    ops = []
    zones = db['zones']
    x, y = 14, 14
    row = 22
    lines = len(zones) + 1
    height = 46 + row * lines
    ops.append(('rect', (x, y, 250, height), '#ffffff', '#dbe3ec', 1.0, None))
    ops.append(('text', (x + 12, y + 16), '%s  ·  %s' % (db['level'], db['map']),
                12, INK, 'lm', True, None))
    for i, z in enumerate(zones):
        yy = y + 44 + row * i
        hidden = z['id'] in state.hidden_zones
        key = ('zone', z['id'])
        if hidden:
            ops.append(('rect', (x + 12, yy - 7, 14, 14), '#ffffff', '#cbd5e1', 1.5, key))
            ops.append(('text', (x + 34, yy), '%s  %s' % (z['id'], zone_label(db, z)),
                        10, '#cbd5e1', 'lm', False, key))
        else:
            ops.append(('rect', (x + 12, yy - 7, 14, 14), z['color'], z['color'], 1.0, key))
            ops.append(('text', (x + 34, yy), '%s  %s' % (z['id'], zone_label(db, z)),
                        10, '#334155', 'lm', bool(note_of(db, 'zones', z['id'])), key))
    yy = y + 44 + row * len(zones)
    if zones:
        ops.append(('text', (x + 12, yy), 'All zones  (click a row to toggle)', 9,
                    '#64748b', 'lm', False, ('zoneall', 0)))
    else:
        ops.append(('text', (x + 12, yy), 'no zone config for this level', 9,
                    '#94a3b8', 'lm', False, None))

    # ---- 门类型图例（只列本关出现的类型）----
    doors = db.get('doors') or []
    if doors and state.show_doors:
        shown = [k for k in DOOR_KIND_ORDER if any((d.get('kind') or 'other') == k for d in doors)]
        trial_only = any(d.get('trial_only') for d in doors)
        rows = [DOOR_KINDS[k] for k in shown]
        if trial_only:
            rows.append(TRIAL_ONLY_STYLE)
        dy = y + height + 8
        dheight = 30 + 18 * len(rows)
        ops.append(('rect', (x, dy, 250, dheight), '#ffffff', '#dbe3ec', 1.0, None))
        ops.append(('text', (x + 12, dy + 15), 'Doors', 11, INK, 'lm', True, None))
        for i, (label, color, width, dash) in enumerate(rows):
            yy2 = dy + 32 + 18 * i
            ops.append(('line', [(x + 12, yy2), (x + 30, yy2)], color, width, dash, None))
            ops.append(('text', (x + 36, yy2), label, 9, '#334155', 'lm', False, None))
    return ops


# ---------------------------------------------------------------------------
# 后端：Tk Canvas
# ---------------------------------------------------------------------------
class TkBackend(object):
    def __init__(self, canvas):
        self.c = canvas
        self.hit = {}

    def clear(self):
        self.c.delete('all')
        self.hit = {}

    def draw(self, ops):
        c = self.c
        self.clear()
        for op in ops:
            kind = op[0]
            if kind == 'poly':
                _, pts, fill, stroke, width, key, dash = op
                if len(pts) < 3:
                    continue
                item = c.create_polygon(*_flat(pts), fill=fill or '',
                                        outline=stroke or '', width=width,
                                        dash=list(dash) if dash else ())
            elif kind == 'line':
                _, pts, color, width, _dash, key = op
                item = c.create_line(*_flat(pts), fill=color, width=width)
            elif kind == 'circle':
                _, (cx, cy), r, fill, stroke, width, key = op
                item = c.create_oval(cx - r, cy - r, cx + r, cy + r,
                                     fill=fill or '', outline=stroke or '', width=width)
            elif kind == 'rect':
                _, (x, y, w, h), fill, stroke, width, key = op
                item = c.create_rectangle(x, y, x + w, y + h,
                                          fill=fill or '', outline=stroke or '', width=width)
            elif kind == 'text':
                _, (x, y), s, size, color, anchor, bold, key = op
                tk_anchor = {'mm': 'center', 'lm': 'w', 'rm': 'e', 'la': 'nw'}.get(anchor, 'center')
                item = c.create_text(x, y, text=s, fill=color, anchor=tk_anchor,
                                     font=fnt(size, bold))
            else:
                continue
            if key:
                self.hit[item] = key

    def pick(self, x, y):
        for item in reversed(self.c.find_overlapping(x - 1, y - 1, x + 1, y + 1)):
            key = self.hit.get(item)
            if key:
                return key
        return None


def _flat(pts):
    out = []
    for p in pts:
        out.extend(p)
    return out


# ---------------------------------------------------------------------------
# 后端：PIL（静态预览 / 自检）
# ---------------------------------------------------------------------------
class PilBackend(object):
    def __init__(self, size=(2200, 1500), ss=1):
        from PIL import Image, ImageDraw, ImageFont
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.ss = ss
        self.img = Image.new('RGB', (size[0] * ss, size[1] * ss), BG)
        self.d = ImageDraw.Draw(self.img, 'RGBA')
        self._fonts = {}
        self.size = size
        # 导出的图通常比窗口大，按比例放大字号，否则预览里名字看不清
        self.fs = max(1.0, size[0] / 1400.0)

    def _font(self, size, bold=False):
        key = (size, bold)
        if key not in self._fonts:
            path = FONT_PATHS[1] if bold else FONT_PATHS[0]
            if not os.path.exists(path):
                path = FONT_PATHS[0]
            self._fonts[key] = self.ImageFont.truetype(path, max(9, int(size * self.ss)))
        return self._fonts[key]

    def draw(self, ops):
        s = self.ss
        for op in ops:
            kind = op[0]
            if kind == 'poly':
                _, pts, fill, stroke, width, _key, dash = op
                if len(pts) < 3:
                    continue
                self.d.polygon([(x * s, y * s) for x, y in pts], fill=fill or None)
                if stroke:
                    self.d.line([(x * s, y * s) for x, y in pts] + [(pts[0][0] * s, pts[0][1] * s)],
                                fill=stroke, width=max(1, int(width * s)))
            elif kind == 'line':
                _, pts, color, width, _dash, _key = op
                self.d.line([(x * s, y * s) for x, y in pts], fill=color, width=max(1, int(width * s)))
            elif kind == 'circle':
                _, (cx, cy), r, fill, stroke, width, _key = op
                box = [(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s]
                self.d.ellipse(box, fill=fill or None, outline=stroke or None,
                               width=max(1, int(width * s)))
            elif kind == 'rect':
                _, (x, y, w, h), fill, stroke, width, _key = op
                self.d.rectangle([x * s, y * s, (x + w) * s, (y + h) * s],
                                 fill=fill or None, outline=stroke or None,
                                 width=max(1, int(width * s)))
            elif kind == 'text':
                _, (x, y), text, size, color, anchor, bold, _key = op
                anc = {'mm': 'mm', 'lm': 'lm', 'rm': 'rm', 'la': 'la'}.get(anchor, 'mm')
                self.d.text((x * s, y * s), text, font=self._font(size * self.fs, bold),
                            fill=color, anchor=anc)

    def save(self, path):
        self.img.resize(self.size, self.Image.LANCZOS).save(path)


# ---------------------------------------------------------------------------
# 窗口
# ---------------------------------------------------------------------------
class _NullPanel(object):
    """--no-seed 时占位，接口与 SeedPanel 一致。"""

    def pack(self, *_a, **_k):
        pass

    def refresh(self, info=None):
        return False


class App(object):
    def __init__(self, db=None, path=None, cfg=None, pinned=False):
        self.db = db
        self.path = path
        self.cfg = cfg or load_config()
        self.pinned = bool(pinned and db)
        self.follow = bool(self.cfg.get('follow_game', True)) and not self.pinned
        self.state = State()
        self.state.show_legend = bool(self.cfg.get('show_legend', False))
        self._flip_manual = bool(self.cfg.get('flip'))
        fx, fy = resolve_flip(db, self.cfg)
        self.view = View(db, flipx=fx, flipy=fy)

        self.last_info = None
        self.pending = None            # (关卡, seed)：日志里有、但还没有地图数据
        self._log_sig = None
        self._last_key = object()      # 哨兵：保证首次一定刷新
        self._press = None
        self._moved = False
        self._last_xy = None
        self._press_hit = None
        self._pan = None
        self._fitted = False
        self._hotkey = None
        self._hotkey_q = queue.Queue()

        self.root = tk.Tk()
        self.root.title(self._title())
        self.root.geometry(self._initial_geometry())
        self.root.configure(bg=BG)
        self.root.minsize(720, 480)

        bar = tk.Frame(self.root, bg=BG)
        bar.pack(side='top', fill='x', padx=8, pady=(8, 2))
        self._toolbar(bar)

        info = tk.Frame(self.root, bg='#ffffff', height=84)
        info.pack(side='bottom', fill='x', padx=8, pady=6)
        info.pack_propagate(False)
        self.lbl_main = tk.Label(info, text='Click a room or point — 名称会自动复制',
                                 bg='#ffffff', fg=INK, anchor='w', font=fnt(11, True))
        self.lbl_main.pack(fill='x', padx=10, pady=(8, 0))
        self.lbl_sub = tk.Label(info, text='', bg='#ffffff', fg='#475569', anchor='w',
                                justify='left', font=fnt(9, mono=True))
        self.lbl_sub.pack(fill='x', padx=10)
        self.lbl_copy = tk.Label(info, text='', bg='#ffffff', fg='#0f766e', anchor='w',
                                 font=fnt(9))
        self.lbl_copy.pack(fill='x', padx=10)

        # 右侧：本局种子与答案
        if self.cfg.get('seed_panel', True):
            self.panel = seedpanel.SeedPanel(
                self.root,
                log_path=self.cfg.get('log_path'),
                seed_lib=self.cfg.get('seed_lib'),
                width=int(self.cfg.get('panel_width') or 440))
            self.panel.pack(side='right', fill='y', padx=(0, 8), pady=2)
        else:
            self.panel = _NullPanel()

        self.canvas = tk.Canvas(self.root, bg=BG, highlightthickness=0)
        self.canvas.pack(side='left', fill='both', expand=True, padx=8, pady=2)
        self.back = TkBackend(self.canvas)

        self.canvas.bind('<Configure>', self._on_resize)
        self.canvas.bind('<ButtonPress-1>', self._on_press)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._on_release)
        self.canvas.bind('<Double-Button-1>', self._on_double)
        self.canvas.bind('<MouseWheel>', self._on_wheel)
        # 中键 / 右键直接平移，不用先点空白
        for num in ('2', '3'):
            self.canvas.bind('<ButtonPress-%s>' % num, self._on_pan_press)
            self.canvas.bind('<B%s-Motion>' % num, self._on_pan_move)
            self.canvas.bind('<ButtonRelease-%s>' % num, self._on_pan_release)
        self.root.bind('<Key>', self._on_key)
        self.root.bind('<Escape>', lambda e: self._clear())
        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

        self._start_hotkey()
        self.root.after(80, self._first_load)

    # -- 启动
    def _title(self):
        if self.db:
            base = '%s · %s' % (self.db['level'], self.db.get('map') or '')
        else:
            base = 'OPP map — 等待游戏日志'
        return '%s   [%s]' % (base, VERSION)

    def _initial_geometry(self):
        geo = str(self.cfg.get('window') or '1440x960').lower()
        try:
            w, h = [int(v) for v in geo.split('x')]
        except Exception:
            w, h = 1440, 960
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        w = max(900, min(w, sw - 60))
        h = max(560, min(h, sh - 90))
        return '%dx%d' % (w, h)

    def _first_load(self):
        try:
            self.refresh_seed(force=True)
        finally:
            self._schedule_poll()

    def _schedule_poll(self):
        interval = int(self.cfg.get('poll_interval_ms') or 900)
        try:
            self.root.after(max(300, interval), self._poll_log)
        except tk.TclError:                  # 窗口已经销毁，别再续定时器
            pass

    def _poll_log(self):
        """轻量轮询：只 stat 一次日志，文件变了才解析（这就是「种子一出来就刷新」）。"""
        try:
            if not self.root.winfo_exists():
                return
            if self.cfg.get('poll_log', True):
                sig = gamelog.signature(self.cfg.get('log_path'))
                if sig and sig != self._log_sig:
                    self._log_sig = sig
                    self.refresh_seed(gamelog.latest(self.cfg.get('log_path')))
        except tk.TclError:
            return
        except Exception as exc:                    # noqa: BLE001 - 显示给用户
            self.lbl_copy.config(text='读日志失败：%s' % exc)
        self._schedule_poll()

    # -- 本局答案
    def refresh_seed(self, info=None, force=False):
        """刷新右侧答案 + 坐标标记；跟随模式下顺便切到本局关卡的地图。"""
        if info is None:
            info = gamelog.latest(self.cfg.get('log_path'))

        key = None if not info else (info.get('trial'), info.get('seed'), info.get('players'),
                                     info.get('difficulty'), info.get('status'))
        if not force and key == self._last_key:
            return bool(getattr(self.panel, 'answer', None)
                        and self.panel.answer.get('ok'))
        self._last_key = key
        self.last_info = info

        ok = self.panel.refresh(info)
        self._sync_map(info)

        if not ok:
            self.set_seed_markers([])
            if not info and not self.pending:
                self.lbl_copy.config(text='还没读到本局信息：进一次试炼关卡，或检查 log_path')
            return False

        data = (getattr(self.panel, 'answer', None) or {}).get('data')
        same_level = bool(self.db) and (info.get('trial') or '').upper() == \
            (self.db.get('level') or '').upper()
        found = markers.collect(data) if (data and same_level) else []
        self.set_seed_markers(found)
        if found:
            self.lbl_copy.config(text='本局坐标标记 %d 个（%s），按 S 可隐藏'
                                      % (len(found), markers.summary(found)))
        return True

    def set_seed_markers(self, found):
        self.state.seed_markers = list(found or [])
        if getattr(self, 'chk_seed', None) is not None:
            self.chk_seed.config(text='seed (%d)' % len(self.state.seed_markers),
                                 state=('normal' if self.state.seed_markers else 'disabled'))
        self._redraw()

    def _sync_map(self, info):
        """日志里的关卡和当前地图不一致时切过去（跟随模式）。"""
        if not info:
            return False
        level = (info.get('trial') or '').upper()
        if not level:
            return False
        if self.db and level == (self.db.get('level') or '').upper():
            self.pending = None
            return False
        if self.pinned or not self.follow:
            if self.db:
                self.lbl_copy.config(text='本局是 %s（seed %s），地图锁定在 %s；按 L 跟随本局'
                                          % (level, info.get('seed') or 0, self.db['level']))
                return False
        return self._load_level(level, info)

    def _load_level(self, level, info=None):
        target = os.path.join(DATA_DIR, '%s.json' % level)
        if not os.path.exists(target):
            self.pending = (level, (info or {}).get('seed'))
            self.lbl_copy.config(text='本局 %s 还没有地图数据（先跑 python mapdb.py %s）'
                                      % (level, level))
            if self.db is None:
                self._redraw()
            return False
        if not self.switch_level(level):
            return False
        self.pending = None
        self.lbl_copy.config(text='已切到本局关卡 %s 的地图' % level)
        return True

    def switch_level(self, level):
        """换一张关卡地图（保留图层开关、图例位置）。"""
        try:
            db, path = load_db(level)
        except SystemExit:
            return False
        keep = (self.state.show_doors, self.state.show_points, self.state.show_items,
                self.state.show_all_names, self.state.mode, self.state.hidden_zones,
                self.state.show_seed, self.state.show_legend, self.state.floor)
        keep_view = (getattr(self.view, 'turns', 0), self.view.flipx, self.view.flipy)
        self.db, self.path = db, path
        self.state = State()
        (self.state.show_doors, self.state.show_points, self.state.show_items,
         self.state.show_all_names, self.state.mode, self.state.hidden_zones,
         self.state.show_seed, self.state.show_legend, self.state.floor) = keep
        if self.state.floor >= len(db['floors']):
            self.state.floor = 0
        if self._flip_manual:
            fx, fy = keep_view[1], keep_view[2]
        else:
            fx, fy = resolve_flip(db, self.cfg)
        self.view = View(db, flipx=fx, flipy=fy)
        self.view.turns = keep_view[0]
        self.root.title(self._title())
        self._build_floors()
        self.root.update_idletasks()
        self.view.fit(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._fitted = True
        self._redraw()
        return True

    # -- 全局快捷键
    def _start_hotkey(self):
        key = (self.cfg.get('hotkey') or 'none').strip()
        if not hotkey or key.lower() in ('none', 'off', ''):
            return
        self._hotkey = hotkey.Listener(key, self._hotkey_q)
        self._hotkey.start()
        try:                                   # 记到 mapview_out.log，方便确认生效的是哪个键
            print('全局快捷键：%s' % (self._hotkey.label or key), flush=True)
        except Exception:
            pass
        self.root.after(150, self._poll_hotkey)

    def _poll_hotkey(self):
        while True:
            try:
                kind, payload = self._hotkey_q.get_nowait()
            except queue.Empty:
                break
            if kind == 'hotkey':
                self.toggle_window()
            elif kind == 'ready':
                extra = '' if hotkey.is_admin() else '（普通权限；游戏若是管理员，本工具也要管理员）'
                self.lbl_copy.config(text='全局快捷键 %s 已就绪%s' % (payload, extra))
            elif kind == 'error':
                self.lbl_copy.config(text='快捷键不可用：%s（改 config.json 的 hotkey）' % payload)
        self.root.after(150, self._poll_hotkey)

    def is_hidden(self):
        """窗口现在是不是收着（收起 / 最小化）。"""
        try:
            return self.root.state() in ('withdrawn', 'iconic')
        except tk.TclError:
            return True

    def show_window(self):
        """弹到最前 + 抢焦点 + 刷新答案（游戏全屏时也能压在上面）。"""
        try:
            self.root.deiconify()
            self.root.attributes('-topmost', bool(self.cfg.get('always_topmost', True)))
            self.root.lift()
        except tk.TclError:
            return
        if self.cfg.get('activate_on_hotkey', True):
            self._force_focus()
        self.refresh_seed(force=True)

    def _force_focus(self):
        """真的把窗口切到前台，并且把鼠标「还」给桌面。

        游戏全屏时单纯 SetForegroundWindow 会被 Windows 的前台锁拒绝（点了也没用），
        必须 AttachThreadInput 到当前前台线程才允许抢；另外游戏常把鼠标锁在屏幕中间
        （ClipCursor），不解除的话鼠标根本移不到工具栏上，动一下就变成转视角。
        """
        try:
            self.root.focus_force()
            self.canvas.focus_set()
        except tk.TclError:
            pass
        if ctypes is None or os.name != 'nt' or wt is None:
            return
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
            hwnd = int(self.root.wm_frame(), 16)
            user32.ShowWindow(hwnd, 9)                 # SW_RESTORE
            user32.ClipCursor(None)                    # 解除游戏的鼠标裁剪
            fg = user32.GetForegroundWindow()
            if fg == hwnd:
                user32.SetFocus(hwnd)
            else:
                tid_cur = kernel32.GetCurrentThreadId()
                tid_fg = user32.GetWindowThreadProcessId(fg, None)
                attached = False
                if tid_fg and tid_fg != tid_cur:
                    attached = bool(user32.AttachThreadInput(tid_fg, tid_cur, True))
                try:
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.SetFocus(hwnd)
                finally:
                    if attached:
                        user32.AttachThreadInput(tid_fg, tid_cur, False)
            # 鼠标还在窗口外（多半被游戏锁在中间）就挪到窗口中心，省得找不到指针
            pt = wt.POINT()
            if user32.GetCursorPos(ctypes.byref(pt)):
                x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
                w, h = self.root.winfo_width(), self.root.winfo_height()
                if not (x <= pt.x <= x + w and y <= pt.y <= y + h):
                    user32.SetCursorPos(x + w // 2, y + h // 2)
        except Exception:
            pass

    def toggle_window(self, *_args):
        """快捷键：收着（或最小化）就弹出来，已经显示着就收回。

        不用「窗口是不是前台」来判断——游戏全屏时前台永远是游戏，
        那样再按一次也只会再弹一次，看起来就是「关不掉」。
        """
        if self.is_hidden():
            self.show_window()
        else:
            self.root.withdraw()

    def _on_close(self):
        """点窗口 X：默认只收起（进程留着，Ctrl+M 再叫出来）；close_action=quit 才退出。"""
        self._save_layout()
        if str(self.cfg.get('close_action') or 'hide').lower() == 'quit':
            self._quit()
            return
        self.root.withdraw()
        try:
            self.lbl_copy.config(text='窗口已收起：Ctrl+M 再弹出；要真正退出点 Quit')
        except tk.TclError:
            pass

    def _save_layout(self):
        try:
            write_config({'window': '%dx%d' % (self.root.winfo_width(),
                                               self.root.winfo_height()),
                          'show_legend': bool(self.state.show_legend),
                          'follow_game': bool(self.cfg.get('follow_game', True))})
        except Exception:
            pass

    def _quit(self):
        self._save_layout()
        try:
            if self._hotkey:
                self._hotkey.stop()
        finally:
            self.root.destroy()

    # -- 工具栏
    def _toolbar(self, bar):
        self.var_mode = tk.StringVar(value='overlay')
        for text, val in (('Overlay', 'overlay'), ('Floor', 'floor')):
            tk.Radiobutton(bar, text=text, indicatoron=False, value=val, variable=self.var_mode,
                           command=lambda v=val: self._set_mode(v), bg='#e2e8f0',
                           selectcolor='#93c5fd', activebackground='#cbd5e1', bd=0,
                           padx=10, pady=3, font=fnt(9)).pack(side='left', padx=2)

        tk.Label(bar, text='floors:', bg=BG, font=fnt(9)).pack(side='left', padx=(8, 0))
        self.floor_bar = tk.Frame(bar, bg=BG)
        self.floor_bar.pack(side='left')
        self._build_floors()

        self.var_doors = tk.BooleanVar(value=True)
        self.var_points = tk.BooleanVar(value=True)
        self.var_items = tk.BooleanVar(value=False)
        self.var_allnames = tk.BooleanVar(value=False)
        self.var_seed = tk.BooleanVar(value=True)
        self.var_follow = tk.BooleanVar(value=bool(self.follow))
        toggles = [('doors', self.var_doors), ('points', self.var_points),
                   ('all names', self.var_allnames)]
        if self.db and self.db.get('items'):
            toggles.append(('items', self.var_items))
        for text, var in toggles:
            tk.Checkbutton(bar, text=text, variable=var, command=self._redraw, bg='#e2e8f0',
                           selectcolor='#93c5fd', bd=0, padx=8,
                           font=fnt(9)).pack(side='left', padx=2)
        # 本局坐标标记（数量在读到答案后更新）
        self.chk_seed = tk.Checkbutton(
            bar, text='seed (0)', variable=self.var_seed, command=self._redraw,
            bg='#e2e8f0', selectcolor='#93c5fd', bd=0, padx=8, state='disabled',
            font=fnt(9))
        self.chk_seed.pack(side='left', padx=2)
        tk.Checkbutton(bar, text='follow log', variable=self.var_follow,
                       command=self._on_follow, bg='#e2e8f0', selectcolor='#93c5fd',
                       bd=0, padx=8, font=fnt(9)).pack(side='left', padx=2)
        self.var_legend = tk.BooleanVar(value=bool(self.state.show_legend))
        tk.Checkbutton(bar, text='legend (H)', variable=self.var_legend,
                       command=self._on_legend, bg='#e2e8f0', selectcolor='#93c5fd',
                       bd=0, padx=8, font=fnt(9)).pack(side='left', padx=2)

        tk.Button(bar, text='Fit (F)', command=self._fit, bd=0, padx=10, pady=3,
                  bg='#dbeafe', font=fnt(9)).pack(side='right')
        tk.Button(bar, text='Rotate (T)', command=self._rotate, bd=0, padx=10, pady=3,
                  bg='#dbeafe', font=fnt(9)).pack(side='right', padx=6)
        tk.Button(bar, text='Mirror X (X)', command=self._toggle_mirror, bd=0, padx=10,
                  pady=3, bg='#dbeafe', font=fnt(9)).pack(side='right')
        tk.Button(bar, text='Note (N)', command=self._edit_selected_note, bd=0, padx=10,
                  pady=3, bg='#dbeafe', font=fnt(9)).pack(side='right', padx=6)
        tk.Button(bar, text='Copy raw', command=self._copy_raw, bd=0, padx=10, pady=3,
                  bg='#dbeafe', font=fnt(9)).pack(side='right')
        tk.Button(bar, text='All zones', command=self._show_all_zones, bd=0, padx=10,
                  pady=3, bg='#dbeafe', font=fnt(9)).pack(side='right', padx=6)
        tk.Button(bar, text='Quit', command=self._quit, bd=0, padx=10, pady=3,
                  bg='#fee2e2', font=fnt(9)).pack(side='right', padx=6)

    def _build_floors(self):
        for w in self.floor_bar.winfo_children():
            w.destroy()
        self.var_floor = tk.IntVar(value=int(self.state.floor or 0))
        if not self.db:
            return
        for f in self.db['floors']:
            tk.Radiobutton(self.floor_bar, text=f['label'], indicatoron=False, value=f['index'],
                           variable=self.var_floor, command=self._on_floor, bg='#e2e8f0',
                           selectcolor='#93c5fd', bd=0, padx=8, pady=3,
                           font=fnt(9)).pack(side='left', padx=1)

    # -- 交互
    def _set_mode(self, mode):
        self.state.mode = mode
        self._redraw()

    def _on_floor(self):
        self.state.floor = self.var_floor.get()
        self.state.mode = 'floor'
        self.var_mode.set('floor')
        self._redraw()

    def _on_follow(self):
        self.follow = bool(self.var_follow.get())
        self.cfg['follow_game'] = self.follow
        if self.follow:
            self.pinned = False
            self.refresh_seed(force=True)
        else:
            self.lbl_copy.config(text='已停止跟随日志，地图固定在 %s'
                                      % (self.db['level'] if self.db else '-'))

    def _on_legend(self):
        self.state.show_legend = bool(self.var_legend.get())
        self._redraw()
        self.lbl_copy.config(text='图例：%s（H 或工具栏 legend 切换）'
                                  % ('显示' if self.state.show_legend else '隐藏'))

    def _show_all_zones(self):
        self.state.hidden_zones.clear()
        self._redraw()

    def _on_resize(self, event):
        self.view.w, self.view.h = event.width, event.height
        if not self._fitted and self.db:
            self.view.fit(event.width, event.height)
            self._fitted = True
        self._redraw()

    def _on_press(self, event):
        self._press = (event.x, event.y)
        self._last_xy = (event.x, event.y)
        self._moved = False
        self._press_hit = self.back.pick(event.x, event.y)

    def _on_drag(self, event):
        """按住左键拖：超过阈值就算平移（不再当成点选）。"""
        if not self._press:
            return
        if not self._moved:
            if abs(event.x - self._press[0]) + abs(event.y - self._press[1]) < 5:
                return
            self._moved = True
        dx, dy = event.x - self._last_xy[0], event.y - self._last_xy[1]
        self._last_xy = (event.x, event.y)
        self.view.pan_by(dx, dy)
        self.canvas.move('all', dx, dy)

    def _on_release(self, event):
        press, moved, hit = self._press, self._moved, self._press_hit
        self._press = None
        if moved:
            # 拖动结束：按视图状态重整一次画布（canvas.move 只是拖动中的快速反馈），
            # 这样画布内容和 view 一定一致，后面点击、滚轮都不会再「跳」。
            self.view.clamp()
            self._redraw()
            return
        if not press:
            return
        if hit and hit[0] == 'zone':
            self._toggle_zone(hit[1])
        elif hit and hit[0] == 'zoneall':
            self._show_all_zones()
        elif hit:
            self._select(hit)

    def _on_pan_press(self, event):
        self._pan = (event.x, event.y)

    def _on_pan_move(self, event):
        if not self._pan:
            return
        dx, dy = event.x - self._pan[0], event.y - self._pan[1]
        self._pan = (event.x, event.y)
        self.view.pan_by(dx, dy)
        self.canvas.move('all', dx, dy)

    def _on_pan_release(self, _event):
        if self._pan:
            self._pan = None
            self.view.clamp()
            self._redraw()

    def _on_double(self, event):
        hit = self.back.pick(event.x, event.y)
        if not hit:
            return
        if hit[0] == 'zone':
            self._edit_zone_note(hit[1])
        elif hit[0] in ('room', 'point'):
            self._select(hit, copy=False)
            self._edit_selected_note()

    def _toggle_zone(self, zid):
        if zid in self.state.hidden_zones:
            self.state.hidden_zones.discard(zid)
        else:
            self.state.hidden_zones.add(zid)
        self._redraw()

    def _on_wheel(self, event):
        if not self.db:
            return
        self.view.zoom_at(event.x, event.y, 1.12 if event.delta > 0 else 1 / 1.12)
        self.view.clamp()                      # 别让一次放大把图甩出视野
        self._redraw()
        return 'break'                          # 别让 Canvas 的默认滚轮绑定再滚视口

    def _on_key(self, event):
        try:
            if isinstance(self.root.focus_get(), (tk.Text, tk.Entry)):
                return                             # 焦点在文本框里就别抢键
        except Exception:
            pass
        k = (event.keysym or '').lower()
        if k == 'f':
            self._fit()
        elif k == 'o':
            self.var_mode.set('overlay')
            self._set_mode('overlay')
        elif k == 'n':
            self._edit_selected_note()
        elif k == 'r':
            if not self.refresh_seed(force=True):
                self.lbl_copy.config(text='刷新了，但没读到有效对局')
        elif k == 't':
            self._rotate()
        elif k == 'x':
            self._toggle_mirror()
        elif k == 'l':
            self.var_follow.set(True)
            self._on_follow()
        elif k == 'h':
            self.var_legend.set(not self.var_legend.get())
            self._on_legend()
        elif k == 's':
            self.var_seed.set(not self.var_seed.get())
            self._redraw()
            self.lbl_copy.config(text='种子标记：%s' % ('显示' if self.var_seed.get() else '隐藏'))
        elif k == 'escape':
            self._clear()
        elif self.db and k in [str(f['index'] + 1) for f in self.db['floors']]:
            self.var_floor.set(int(k) - 1)
            self._on_floor()

    def _fit(self):
        if not self.db:
            return
        self.view.fit(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._redraw()

    def _rotate(self):
        """每次点击顺时针转 90°，转完重新适应窗口（文字不跟着转）。"""
        if not self.db:
            return
        self.view.turns = (getattr(self.view, 'turns', 0) + 1) % 4
        self.view.fit(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._fitted = True
        self._redraw()
        self.lbl_copy.config(text='地图旋转 %d°（文字保持水平；T 继续转，F 适应窗口）'
                                  % (self.view.turns * 90))

    def _toggle_mirror(self):
        """左右镜像（对应世界坐标的 X 轴翻转）。"""
        if not self.db:
            return
        self.view.flipx = not self.view.flipx
        self._flip_manual = True
        self.view.fit(self.canvas.winfo_width(), self.canvas.winfo_height())
        self._fitted = True
        self._redraw()
        self.lbl_copy.config(text='左右镜像：%s（X 每次点都切换）'
                                  % ('开' if self.view.flipx else '关'))

    def _clear(self):
        self.state.sel = None
        self.lbl_main.config(text='Click a room or point — 名称会自动复制')
        self.lbl_sub.config(text='')
        self._redraw()

    def _redraw(self):
        if self.db is None:
            self._draw_placeholder()
            return
        self.state.show_doors = self.var_doors.get()
        self.state.show_points = self.var_points.get()
        self.state.show_items = self.var_items.get()
        self.state.show_all_names = self.var_allnames.get()
        self.state.show_seed = self.var_seed.get()
        self.state.show_legend = self.var_legend.get()
        self.back.draw(build_ops(self.db, self.state, self.view))

    def _draw_placeholder(self):
        """还没有地图（没读到日志 / 这关没数据）时的空窗口提示。"""
        c = self.canvas
        self.back.clear()
        w = c.winfo_width() or 900
        h = c.winfo_height() or 600
        if self.pending:
            level, seed = self.pending
            title = '本局 %s（seed %s）还没有地图数据' % (level, seed)
            sub = '生成：python mapdb.py %s      → data/maps/%s.json' % (level, level)
        else:
            title = '等待游戏日志…'
            sub = '进入试炼关卡（日志出现 Trial ID + Seed）后地图会自动加载'
        c.create_text(w / 2.0, h / 2.0 - 16, text=title, fill=INK, font=fnt(15, True))
        c.create_text(w / 2.0, h / 2.0 + 16, text=sub, fill=MUTED, font=fnt(10))

    # -- 选中 / 复制
    def _select(self, key, copy=True):
        if not self.db:
            return
        kind, oid = key
        self.state.sel = key
        self._redraw()
        obj, title, copy_text, sub = self._describe(kind, oid)
        if not obj:
            return
        self.lbl_main.config(text=title)
        self.lbl_sub.config(text=sub)
        if copy and copy_text:
            self._copy(copy_text)

    def _describe(self, kind, oid):
        db = self.db
        if not db:
            return None, '', '', ''
        if kind == 'room':
            r = db['rooms'][oid]
            zname = next((zone_label(db, z) for z in db['zones'] if z['id'] == r['zone']), '-')
            floors = '/'.join(floor_name(db, i) or '?' for i in (r['floors'] or [])) or '-'
            note = note_of(db, 'rooms', r['raw'])
            title = '%s   [%s]' % (room_label(db, r), r['kind'])
            sub = ('raw  : %s\n'
                   'zone : %s %s     floors : %s     z : %.0f ~ %.0f     area : %.0f uu²%s'
                   % (r['raw'], r['zone'] or '-', zname, floors,
                      r['z'][0], r['z'][1], r['area'],
                      '' if note else '\n(no note — double click / N to add)'))
            return r, title, r['raw'], sub        # 自动复制原始名（RBRoom_...），显示才用备注
        if kind == 'point':
            p = db['points'][oid]
            room = db['rooms'][p['room']] if p.get('room') is not None else None
            zname = next((zone_label(db, z) for z in db['zones'] if z['id'] == p['zone']), '-')
            note = note_of(db, 'points', p['actor'])
            title = '%s #%d   %s' % (p.get('label') or p['key'], p.get('num') or 0, p['actor'])
            sub = ('zone : %s %s     %s     p : (%.0f, %.0f, %.0f)\nroom : %s%s'
                   % (p['zone'] or '-', zname, floor_name(db, p.get('floor')) or '-',
                      p['p'][0], p['p'][1], p['p'][2],
                      room['raw'] if room else '-',
                      ('\nnote : ' + note) if note else ''))
            return p, title, p['actor'], sub
        if kind == 'door':
            d = db['doors'][oid]
            rooms = ', '.join(db['rooms'][i]['raw'] for i in d['rooms']) or '-'
            title = 'Door  %s   —   %s' % (d['name'], door_kind_label(d))
            sub = ('type : %s   width : %.0f   p : (%.0f, %.0f, %.0f)\nrooms : %s'
                   % (d.get('type') or d['cat'], d['w'],
                      d['p'][0], d['p'][1], d['p'][2], rooms))
            return d, title, d['name'], sub
        if kind == 'item':
            it = db['items'][oid]
            title = 'Item  %s' % it['name']
            sub = 'cat : %s     p : (%.0f, %.0f, %.0f)' % (it['label'], it['p'][0], it['p'][1], it['p'][2])
            return it, title, it['name'], sub
        if kind == 'seed':
            m = self.state.seed_markers[oid]
            room = next((r for r in db['rooms'] if r['raw'] == m.get('room')), None)
            title = 'SEED #%d  %s%s' % (oid + 1, m.get('label') or '',
                                        '' if m.get('exact', True) else '   (≈ 房间中心)')
            sub = ('section : %s\nroom : %s%s\np : (%.1f, %.1f, %.1f)'
                   % (m.get('section') or '-', m.get('room') or '-',
                      ('   [' + room['name'] + ']') if room else '',
                      m['p'][0], m['p'][1], m['p'][2]))
            return m, title, '%.1f, %.1f, %.1f' % tuple(m['p']), sub
        return None, '', '', ''

    def _copy(self, text):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.root.update()
            self.lbl_copy.config(text='copied: %s' % text)
        except tk.TclError:
            self.lbl_copy.config(text='copy failed: %s' % text)

    def _copy_raw(self):
        if not self.state.sel or not self.db:
            return
        kind, oid = self.state.sel
        db = self.db
        if kind == 'room':
            self._copy(db['rooms'][oid]['raw'])
        elif kind == 'point':
            self._copy(db['points'][oid]['actor'])

    # -- 备注编辑（写回同一份 JSON）
    def _edit_zone_note(self, zid):
        zone = next((z for z in self.db['zones'] if z['id'] == zid), None)
        if not zone:
            return
        text = self._ask_note('Zone %s note — %s' % (zid, zone.get('name') or ''),
                              note_of(self.db, 'zones', zid))
        if text is None:
            return
        self._set_note('zones', zid, text)

    def _edit_selected_note(self):
        if not self.state.sel or not self.db:
            self.lbl_copy.config(text='select a room / point first')
            return
        kind, oid = self.state.sel
        db = self.db
        if kind == 'room':
            r = db['rooms'][oid]
            text = self._ask_note('Room note — %s' % r['name'], note_of(db, 'rooms', r['raw']))
            if text is not None:
                self._set_note('rooms', r['raw'], text)
        elif kind == 'point':
            p = db['points'][oid]
            text = self._ask_note('Point note — %s' % p['actor'], note_of(db, 'points', p['actor']))
            if text is not None:
                self._set_note('points', p['actor'], text)
        elif kind == 'door':
            self.lbl_copy.config(text='doors have no notes (pick a room or point)')

    def _ask_note(self, title, current):
        top = tk.Toplevel(self.root)
        top.title(title)
        top.transient(self.root)
        top.grab_set()
        tk.Label(top, text=title, font=fnt(10)).pack(anchor='w', padx=14, pady=(14, 4))
        tk.Label(top, text='空着保存 = 删除备注；备注会写回关卡 JSON 并优先作为显示名',
                 font=fnt(8), fg='#64748b').pack(anchor='w', padx=14)
        ent = tk.Entry(top, width=56, font=fnt(10))
        ent.insert(0, current or '')
        ent.pack(padx=14, pady=8)
        ent.focus_set()
        ent.select_range(0, 'end')
        result = {'v': None}

        def ok(_event=None):
            result['v'] = ent.get().strip()
            top.destroy()

        def cancel(_event=None):
            top.destroy()

        bar = tk.Frame(top)
        bar.pack(pady=(0, 12))
        tk.Button(bar, text='Save', width=8, command=ok).pack(side='left', padx=4)
        tk.Button(bar, text='Cancel', width=8, command=cancel).pack(side='left', padx=4)
        top.bind('<Return>', ok)
        top.bind('<Escape>', cancel)
        self.root.wait_window(top)
        return result['v']

    def _set_note(self, kind, key, text):
        notes = self.db.setdefault('notes', {})
        bucket = notes.setdefault(kind, {})
        if text:
            bucket[key] = text
        else:
            bucket.pop(key, None)
        self._save_db()
        self._redraw()
        if self.state.sel:
            _o, title, _c, sub = self._describe(*self.state.sel)
            self.lbl_main.config(text=title)
            self.lbl_sub.config(text=sub)
        self.lbl_copy.config(text='note saved → %s (%s %s)' % (os.path.basename(self.path), kind, key))

    def _save_db(self):
        with open(self.path, 'w', encoding='utf-8') as fp:
            json.dump(self.db, fp, ensure_ascii=False, separators=(',', ':'))

    def run(self):
        self.root.after(60, self._fit)
        self.root.mainloop()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------
_INSTANCE = {}


def lock_instance(name='Local\\OPP_mapview'):
    """只允许一个实例在跑。

    两个实例会各装一份键盘钩子：旧的那份还在按旧快捷键响应（比如配置已经改成
    Ctrl+A 了，按 M 仍然会弹出，其实是老进程）。返回 (ok, 原因)。
    """
    if os.name != 'nt' or ctypes is None:
        return True, ''
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            return True, ''
        if kernel32.GetLastError() == 183:            # ERROR_ALREADY_EXISTS
            return False, '已经有一个地图工具在运行了'
        _INSTANCE['handle'] = handle
        return True, ''
    except Exception:
        return True, ''


def load_db(target):
    path = target if os.path.exists(target) else os.path.join(DATA_DIR, '%s.json' % target.upper())
    if not os.path.exists(path):
        raise SystemExit('找不到关卡数据：%s（先跑 mapdb.py %s）' % (path, target))
    with open(path, encoding='utf-8') as fp:
        db = json.load(fp)
    notes = db.setdefault('notes', {})
    for key in ('rooms', 'zones', 'points'):
        notes.setdefault(key, {})
    db.setdefault('points', [])
    return db, path


def main(argv=None):
    ap = argparse.ArgumentParser(description='地图实时渲染（默认跟随游戏日志）')
    ap.add_argument('target', nargs='?', help='关卡编号（如 PSA_MT01）或 JSON 路径；省略=跟随日志')
    ap.add_argument('--png', metavar='FILE', help='无窗口导出静态图')
    ap.add_argument('--mode', default='overlay', choices=('overlay', 'floor'))
    ap.add_argument('--floor', type=int, default=0, help='分层模式看第几层（0 起）')
    ap.add_argument('--size', default='2200x1500', help='--png 的输出尺寸')
    ap.add_argument('--all-names', action='store_true', help='--png 时标注所有房间名')
    ap.add_argument('--list', action='store_true', help='列出已生成的关卡数据')
    ap.add_argument('--log', metavar='FILE', help='OPP.log 路径（默认自动找）')
    ap.add_argument('--seed-lib', metavar='FILE', help='seed.py 路径（默认上级目录）')
    ap.add_argument('--hotkey', metavar='KEY', help='全局快捷键，如 ctrl+m / F8 / none')
    ap.add_argument('--no-hotkey', action='store_true', help='不注册全局快捷键')
    ap.add_argument('--no-seed', action='store_true', help='不显示右侧答案面板')
    ap.add_argument('--seed-marks', action='store_true',
                    help='--png 时把本局答案里的坐标也画上去')
    ap.add_argument('--follow', action='store_true', help='指定了关卡也仍跟随日志自动切图')
    ap.add_argument('--font-scale', type=float, default=None, help='字号缩放（默认 1.0）')
    ap.add_argument('--flip', choices=('none', 'x', 'y', 'xy'), default=None,
                    help='镜像方式：none=原样 / x=左右镜像（交付版默认）/ y=上下 / xy=180°')
    ap.add_argument('--rot', type=int, default=0, choices=(0, 90, 180, 270),
                    help='--png 时顺便旋转（顺时针度数）')
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    enable_dpi_awareness()

    cfg = load_config()
    set_scale(args.font_scale or cfg.get('font_scale') or 1.0)
    if args.log:
        cfg['log_path'] = args.log
    if args.seed_lib:
        cfg['seed_lib'] = args.seed_lib
    if args.hotkey:
        cfg['hotkey'] = args.hotkey
    if args.no_hotkey:
        cfg['hotkey'] = 'none'
    if args.no_seed:
        cfg['seed_panel'] = False
    if args.flip:
        cfg['flip'] = args.flip

    if args.list:
        for f in sorted(f for f in os.listdir(DATA_DIR) if f.endswith('.json')):
            size = os.path.getsize(os.path.join(DATA_DIR, f)) / 1024.0
            print('%-16s %6.0f KB' % (f[:-5], size))
        return 0

    if args.png:
        level = args.target
        if not level:
            info = gamelog.latest(cfg.get('log_path'))
            if not info:
                print('日志里还没有关卡信息；用法：python mapview.py <LEVEL> --png a.png')
                return 2
            level = info['trial']
        db, path = load_db(level)
        w, h = [int(v) for v in args.size.lower().split('x')]
        view = View(db, *resolve_flip(db, cfg))
        view.turns = (int(args.rot) // 90) % 4
        view.fit(w, h)
        state = State()
        state.mode = args.mode
        state.floor = args.floor
        state.show_all_names = args.all_names
        if args.seed_marks:
            try:
                import seedinfo
                info = gamelog.latest(cfg.get('log_path'))
                ans = seedinfo.answer(info, cfg.get('seed_lib'))
                if ans.get('ok') and (info.get('trial') or '').upper() == db['level'].upper():
                    state.seed_markers = markers.collect(ans.get('data'))
            except Exception:
                state.seed_markers = []
        back = PilBackend((w, h))
        back.draw(build_ops(db, state, view))
        back.save(args.png)
        print('%s → %s（%s%s）'
              % (os.path.basename(path), args.png, args.mode,
                 '' if args.mode == 'overlay' else ' %s' % (floor_name(db, args.floor) or '')))
        return 0

    ok, why = lock_instance()
    if not ok:
        msg = ('%s。\n\n如果那个窗口的快捷键还是旧的（比如按 M 也弹），先在任务管理器里'
               '结束 pythonw.exe / python.exe，再重新启动本工具。' % why)
        print(msg)
        if ctypes is not None and os.name == 'nt':
            try:
                ctypes.windll.user32.MessageBoxW(None, msg, 'OPP map', 0x40)
            except Exception:
                pass
        return 1

    try:
        print('mapview %s' % VERSION, flush=True)
    except Exception:
        pass

    if args.target:
        db, path = load_db(args.target)
        pinned = not args.follow
    else:
        db, path, pinned = None, None, False
        cfg['follow_game'] = True          # 不给关卡 = 跟着日志走

    App(db, path, cfg, pinned=pinned).run()
    return 0


if __name__ == '__main__':
    sys.exit(main())
