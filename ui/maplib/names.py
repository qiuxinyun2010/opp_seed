# -*- coding: utf-8 -*-
"""房间显示名与点位归属（原 `release/map2/zonemap.py` 的模型部分，已内联）。

- 房间显示名：`Names`，优先级 房间备注 > 全局 room_names.json > 机翻 > 英文原名
- 点位归属：`room_of_point` / `point_zone`
- 通配匹配：`room_match`（支持 * 与 ! 排除）
"""
from __future__ import annotations

import fnmatch
import io
import json
import os
import re

from . import extract as ext

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ROOM_NAMES_FILE = os.path.join(DATA_DIR, 'room_names.json')

ZONE_PALETTE = ['#7c3aed', '#b45309', '#1d4ed8', '#0f766e', '#be123c',
                '#4d7c0f', '#0891b2', '#a21caf']

def load_json(path, default=None):
    if not path or not os.path.exists(path):
        return default
    try:
        with io.open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except (ValueError, OSError) as e:
        sys.stderr.write('忽略损坏的 JSON %s: %s\n' % (os.path.basename(path), e))
        return default

_SHORT_GENERIC = {'BP', 'ObjCoord', 'Base', 'Button', 'Simple', 'Orp', 'Movable',
                  'Triggerable', 'PasscodeTriggerable', 'Coord', 'ProjectionSymbol',
                  'Goto', 'GoTo'}

def short_actor(name):
    """Code_DiaporamaProjector_BP_2 -> BP_2; MT01_ExitStage_ObjCoord_BP -> ExitStage。"""
    s = re.sub(r'^MT\d+_', '', name or '')
    if not s:
        return name or ''
    parts = [p for p in s.split('_') if p]
    if len(parts) >= 2 and parts[-1].isdigit():
        return '%s_%s' % (parts[-2], parts[-1])
    if 'Boatman' in parts:
        return 'Boatman'
    keep = [p for p in parts
            if p not in _SHORT_GENERIC and not re.fullmatch(r'BP\d*', p)]
    if keep:
        return keep[0]
    return parts[-1]

def fmt_z(lo, hi):
    return ('z %d ~ %d' % (lo, hi)) if abs(hi - lo) >= 1 else ('z %d' % lo)

def _is_cjk(s):
    return any('\u4e00' <= c <= '\u9fff' for c in s or '')


def _is_mixed(s):
    return _is_cjk(s) and any(c.isascii() and c.isalpha() for c in s or '')


def raw_display(room):
    """老缓存里数字房间名会变成「未命名房 15 9」, 这里按原始名还原成 Room 15-9。"""
    s = re.sub(r'^RBRoom_?', '', room.get('raw_name') or '')
    s = s.replace('_', ' ').strip()
    if re.fullmatch(r'[\d\s\-]+', s):
        s = 'Room ' + s.replace(' ', '-')
    return s or (room.get('name') or '')


class Names(object):
    """房间显示名: 配置 > 全局 room_names.json > i18n/原名。"""

    def __init__(self, cfg):
        self.alias = {}
        self.alias.update({k: v for k, v in (load_json(ROOM_NAMES_FILE, {}) or {}).items()
                           if not k.startswith('_')})
        self.alias.update({k: v for k, v in (cfg.get('room_names') or {}).items()
                           if not k.startswith('_')})

    def get(self, room, lang):
        for key in (room.get('raw_name'), room.get('name')):
            if key and key in self.alias:
                val = self.alias[key]
                if isinstance(val, dict):
                    got = val.get(lang) or val.get('en') or val.get('zh')
                    if got:
                        return got
                    continue
                if val:
                    return val
        base = room.get('name') or ''
        if not base or base.startswith('未命名'):
            base = raw_display(room)
        if lang == 'zh' and not re.fullmatch(r'(?i)room[\s\d\-]+', base):
            zh = ext.translate(base)
            # 机翻出来「中英混杂」或没译出中文时, 直接用英文原名, 比半截译文可读
            if (zh and zh != base and _is_cjk(zh) and not _is_mixed(zh)
                    and not zh.startswith('未命名')):
                return zh
        return base

    def tooltip(self, room, lang):
        shown = self.get(room, lang)
        parts = [shown]
        if shown != room['raw_name']:
            parts.append(room['raw_name'])
        parts.append('%.0f uu² (≈%.0f m²)' % (room['area'], room['area'] / 1e4))
        parts.append(fmt_z(room['zmin'], room['zmax']))
        return '\n'.join(parts)


def room_match(room, pat):
    raw, name = room['raw_name'], room['name']
    if any(ch in pat for ch in '*?['):
        return (fnmatch.fnmatchcase(raw, pat) or fnmatch.fnmatchcase(name, pat)
                or fnmatch.fnmatchcase(raw.lower(), pat.lower()))
    return raw.lower() == pat.lower() or name.lower() == pat.lower()


def room_of_point(rooms, x, y, z):
    """点位所在房间: 先要求 XY 落在房间多边形内且 z 在高度范围内, 再退回最近房间。"""
    best = None
    for r in rooms:
        if not any(ext.point_in_poly(x, y, h) for h in r['hulls']):
            continue
        if r['zmin'] - 5 <= z <= r['zmax'] + 5:
            dz = 0.0
        else:
            dz = min(abs(z - r['zmin']), abs(z - r['zmax']))
        key = (0 if dz == 0 else 1, dz, r['area'])
        if best is None or key < best[0]:
            best = (key, r)
    if best is not None:
        return best[1]['raw_name']
    cand = None
    for r in rooms:
        if z < r['zmin'] - 400 or z > r['zmax'] + 400:
            continue
        d = min(ext.hull_dist(x, y, h) for h in r['hulls'])
        if cand is None or d < cand[0]:
            cand = (d, r)
    if cand is not None and cand[0] <= 400:
        return cand[1]['raw_name']
    return None


def natural_key(s):
    """自然排序键: xxx_2 排在 xxx_10 前面。"""
    out = []
    for t in re.split(r'(\d+)', s or ''):
        out.append((0, int(t), '') if t.isdigit() else (1, 0, t.lower()))
    return out


def point_zone(point, specs):
    for spec in specs:
        for a in spec.get('actors') or []:
            if fnmatch.fnmatchcase(point['actor'].lower(), a.lower()):
                return spec['id']
    oi = point['props'].get('ObjectiveIndex')
    oi = 0 if oi is None else oi
    try:
        oi = int(oi)
    except (TypeError, ValueError):
        return None
    for spec in specs:
        if spec.get('objective_index') is None:
            continue
        try:
            if int(spec['objective_index']) == oi:
                return spec['id']
        except (TypeError, ValueError):
            continue
    return None
