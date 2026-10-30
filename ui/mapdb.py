# -*- coding: utf-8 -*-
"""mapdb.py — 地图元数据提取：paks/MAP/Maps/<Map> → data/maps/<关卡>.json

只做「提取 + 固化」，不做任何绘制。产物是交互式地图（mapview.py）的唯一数据源：
房间多边形 / 门 / 任务点位 / 楼层 / 分区，全部烘进一份 JSON。
名称一律英文为主（name），中文放 name_zh 备查；备注（notes）与游戏备注由 UI 写入同一份 JSON，
重新提取时会原样保留。

提取哪些内容由 data/extract.json 控制（默认只提门 + 任务点位，不提藏身点/血包等物品）。

解析内核在本项目内（maplib/），不依赖 release/map、release/map2；
只有游戏数据 paks/MAP/Maps 需要外部提供（--paks 或 OUTLAST_MAPS_DIR）。

用法：
    python mapdb.py SMC_MT02                # 生成 data/maps/SMC_MT02.json
    python mapdb.py --all                   # data/levels.json 里的所有关卡
    python mapdb.py SMC_MT02 --paks D:/.../paks/MAP/Maps   # 指定游戏数据目录
    python mapdb.py SMC_MT02 --refresh      # 强制重扫 paks 几何
    python mapdb.py SMC_MT02 --with-items   # 额外提取交互物品（临时覆盖配置）
    python mapdb.py SMC_MT02 --check        # 自检（点位归属 / 分区覆盖 / 坐标）
    python mapdb.py --sync-levels           # 从 release/seed/seed.py 同步关卡表

新关卡怎么提点位：**自己去读原始关卡 JSON**（paks/MAP/Maps/<Map>/<LEVEL>_B00.json 等），
确认要提的蓝图类名和实例名，然后手写 data/points/<关卡>.json 的 point_types，再跑本脚本。
具体做法见 README.md §2。

层级：
    data/extract.json                   提取配置（要哪些图层、物品白名单、楼层聚类参数）
    data/zones/<关卡>.json              分区/点位默认配置（历史配置，可被 data/points 覆盖）
    data/points/<关卡>.json             本关点位规则（手写）
    data/levels.json                    关卡 → 地图名
    data/cache/<Map>.geom.json          整张地图的几何缓存（扫一次 ~20s，之后秒开）
    data/cache/<Map>.points.<关卡>.json  任务点位缓存（按 sources 文件时间戳失效）
    data/maps/<关卡>.json               交付给渲染器的关卡数据（每个关卡一份，含备注）
"""
from __future__ import annotations

import argparse
import datetime
import glob
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SEED_DIR = os.path.dirname(HERE)                  # 仓库根（含 seed.py）
ROOT = os.path.dirname(SEED_DIR)                  # 仓库的上级目录（paks 通常在这里）


def _find_maps_dir():
    """paks/MAP/Maps 的位置：环境变量 > 仓库内 > 仓库上级 > ui 内，取第一个存在的。"""
    for cand in (os.environ.get('OUTLAST_MAPS_DIR'),
                 os.path.join(SEED_DIR, 'paks', 'MAP', 'Maps'),
                 os.path.join(ROOT, 'paks', 'MAP', 'Maps'),
                 os.path.join(HERE, 'paks', 'MAP', 'Maps')):
        if cand and os.path.isdir(cand):
            return cand
    return os.path.join(ROOT, 'paks', 'MAP', 'Maps')   # 都没有：报错信息里给出这个路径


MAPS_DIR = _find_maps_dir()

DATA_DIR = os.path.join(HERE, 'data')
CACHE_DIR = os.path.join(DATA_DIR, 'cache')
OUT_DIR = os.path.join(DATA_DIR, 'maps')
POINT_DIR = os.path.join(DATA_DIR, 'points')
ZONE_DIR = os.path.join(DATA_DIR, 'zones')        # 本工具自带的分区/点位配置
EXTRACT_CFG = os.path.join(DATA_DIR, 'extract.json')
LEVELS_JSON = os.path.join(DATA_DIR, 'levels.json')

DEFAULT_EXTRACT = {
    '_说明': '提取哪些图层。doors=各种门，points=任务点位，items=藏身点/血包等交互物品；'
             'item_cats 为空表示不限制类别（仅在 items=true 时生效）。floors 是楼层聚类参数。',
    'layers': {'doors': True, 'points': True, 'items': False},
    'item_cats': [],
    'floors': {'min_sep': 250.0, 'min_rooms': 3, 'span': 400.0},
}

# 解析内核在本项目内（maplib/），不再依赖 release/map 系列
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from maplib import extract as mp        # noqa: E402  解析 / 翻译 / 几何原语
from maplib import names as zm         # noqa: E402  房间命名 / 点位归属 / 分区匹配

# 关卡 → 地图名：只读本项目 data/levels.json（用 --sync-levels 从 seed.py 同步）
# key 统一按大写索引：大关编号形如 PoliceStation_T02，命令行/文件名都按大写归一
LEVELS = {}
if os.path.exists(LEVELS_JSON):
    with io.open(LEVELS_JSON, encoding='utf-8') as _fp:
        LEVELS = {k.upper(): v for k, v in json.load(_fp).items()}

SCHEMA = 1


# ---------------------------------------------------------------------------
# 基础 IO
# ---------------------------------------------------------------------------
def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with io.open(path, encoding='utf-8') as fp:
        return json.load(fp)


def save_json(path, data, compact=True):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(path, 'w', encoding='utf-8') as fp:
        if compact:
            json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))
        else:
            json.dump(data, fp, ensure_ascii=False, indent=1)


def rel(path):
    return os.path.relpath(path, ROOT).replace('\\', '/')


def _r1(v):
    return round(float(v), 1)


def pretty_en(text):
    """DepartmentStore_Central -> Department Store Central（只用于显示，raw_name 不动）。"""
    s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', text or '')
    s = re.sub(r'(?<=[A-Z])(?=[A-Z][a-z])', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def sync_levels():
    """从 release/seed/seed.py 同步「关卡 → 地图名」到 data/levels.json。

    只在仓库里需要（新增关卡时跑一次）；交付出去的 ui/ 用现成的 levels.json 即可。
    """
    path = os.path.join(SEED_DIR, 'seed.py')
    if not os.path.exists(path):
        print('找不到 %s；独立交付时不需要同步关卡表' % path)
        return 1
    import importlib.util
    spec = importlib.util.spec_from_file_location('_seed_levels', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    levels = {k: {'map': v.get('map'), 'name': v.get('name')}
              for k, v in mod.LEVELS.items() if v.get('map')}
    save_json(LEVELS_JSON, levels, compact=False)
    print('已同步 %d 个关卡 → %s' % (len(levels), rel(LEVELS_JSON)))
    return 0


def load_extract_cfg():
    """data/extract.json：要提哪些图层。缺失时写一份默认值，方便手工改。"""
    cfg = load_json(EXTRACT_CFG, None)
    if cfg is None:
        save_json(EXTRACT_CFG, DEFAULT_EXTRACT, compact=False)
        cfg = dict(DEFAULT_EXTRACT)
    merged = dict(DEFAULT_EXTRACT)
    merged.update({k: v for k, v in cfg.items() if not k.startswith('_')})
    layers = dict(DEFAULT_EXTRACT['layers'])
    layers.update(cfg.get('layers') or {})
    merged['layers'] = layers
    floors = dict(DEFAULT_EXTRACT['floors'])
    floors.update(cfg.get('floors') or {})
    merged['floors'] = floors
    return merged


# ---------------------------------------------------------------------------
# 关卡 → 地图 / 分区配置
# ---------------------------------------------------------------------------
def zone_cfg_path(level):
    return os.path.join(ZONE_DIR, '%s.json' % level.upper())


def load_zone_cfg(level):
    """旧的分区配置当注释层读入（不改写）；没有就当空配置。"""
    cfg = load_json(zone_cfg_path(level), None)
    return cfg or {}


def split_level(level):
    """TSR_MT02 -> ('TSR', 'MT02')；认不出就返回 (前缀, None)。"""
    m = re.match(r'^([A-Z0-9]+)_(MT\d{2}|T\d{2})$', (level or '').upper())
    if m:
        return m.group(1), m.group(2)
    return (level or '').split('_')[0].upper(), None


def resolve_map(level, override=None):
    if override:
        return override
    cfg = LEVELS.get(level) or {}
    if cfg.get('map'):
        return cfg['map']
    zc = load_zone_cfg(level)
    if zc.get('map'):
        return zc['map']
    # seed.py 里没有的关卡（如 TSR_MT02）：按「<前缀>_LD_<MTxx>_B00.json」在 paks 里反查
    prefix, trial = split_level(level)
    if trial and os.path.isdir(MAPS_DIR):
        pats = ['%s_LD_%s_B00.json' % (prefix, trial), '%s_%s_B00.json' % (prefix, trial),
                '*_%s_B00.json' % trial]
        for pat in pats:
            for folder in sorted(os.listdir(MAPS_DIR)):
                full = os.path.join(MAPS_DIR, folder)
                if os.path.isdir(full) and glob.glob(os.path.join(full, pat)):
                    return folder
    raise SystemExit('关卡 %s 找不到对应地图（用 --map 指定 paks/MAP/Maps 下的目录名；'
                     '数据目录默认 %s，可用 --paks 改）' % (level, MAPS_DIR))


def load_point_cfg(level):
    """点位规则 = 旧分区配置（只读）+ data/points/<关卡>.json（自己的，优先级更高）。

    自己的文件里给了 point_types / sources 就整体覆盖旧的，没给的字段沿用旧的。
    """
    base = dict(load_zone_cfg(level))
    own = load_json(point_cfg_path(level), None)
    if own:
        for key, val in own.items():
            if key.startswith('_'):
                continue
            if key in ('point_types', 'sources') or val:
                base[key] = val
        base['_own'] = True
    return base


def point_cfg_path(level):
    return os.path.join(POINT_DIR, '%s.json' % level.upper())


# ---------------------------------------------------------------------------
# 几何：整张地图扫一次，缓存起来
# ---------------------------------------------------------------------------
def folder_stamp(folder):
    stamp = []
    for fn in sorted(os.listdir(folder)):
        if not fn.endswith('.json') or 'BuiltData' in fn or 'VisibilityData' in fn:
            continue
        st = os.stat(os.path.join(folder, fn))
        stamp.append([fn, st.st_size, int(st.st_mtime)])
    return stamp


def load_geometry(map_name, refresh=False, verbose=True):
    folder = os.path.join(MAPS_DIR, map_name)
    if not os.path.isdir(folder):
        raise SystemExit(
            '找不到地图数据目录: %s\n'
            '  用 --paks <.../paks/MAP/Maps> 指定游戏数据目录，或设环境变量 OUTLAST_MAPS_DIR'
            % folder)
    cache_path = os.path.join(CACHE_DIR, '%s.geom.json' % map_name)
    stamp = folder_stamp(folder)

    if not refresh:
        old = load_json(cache_path, None)
        if old and old.get('stamp') == stamp:
            if verbose:
                print('几何缓存 %-28s rooms=%d doors=%d items=%d'
                      % (map_name, len(old['rooms']), len(old['doors']), len(old['items'])))
            return old

    if verbose:
        print('扫描 %s（%d 个 json）…' % (map_name, len(stamp)))
    ex = mp.MapExtractor(folder)
    ex.scan()
    rooms = ex.extract_rooms()
    doors = ex.extract_doors()
    items = ex.extract_items()
    spawns = ex.extract_spawns()

    # 房间被哪些关卡变体引用（B00 文件里的 RBRoom 引用）；点位/门看所在文件名
    rtags = mp.room_trial_tags(folder, [r['raw_name'] for r in rooms])
    for r in rooms:
        r['trials'] = rtags.get(r['raw_name']) or []
    for d in doors:
        d['trials'] = mp.trial_of_file(d['file'])
    for it in items:
        it['trials'] = mp.trial_of_file(it['file'])

    data = {'map': map_name, 'folder': rel(folder), 'stamp': stamp,
            'rooms': rooms, 'doors': doors, 'items': items, 'spawns': spawns}
    save_json(cache_path, data)
    if verbose:
        print('  → %s  rooms=%d doors=%d items=%d spawns=%d'
              % (rel(cache_path), len(rooms), len(doors), len(items), len(spawns)))
    return data


# ---------------------------------------------------------------------------
# 任务点位：按分区配置里的 point_types 正则扫原始关卡 JSON
# ---------------------------------------------------------------------------
def resolve_sources(map_name, cfg, level=None):
    folder = os.path.join(MAPS_DIR, map_name)
    pats = cfg.get('sources') or []
    if not pats:
        prefix, trial = split_level(level) if level else (None, None)
        cands = []
        if trial:
            cands += ['%s_LD_%s_B00.json' % (prefix, trial), '*_%s_B00.json' % trial]
        cands += ['%s_B00.json' % map_name, '*.json']
        for cand in cands:
            if glob.glob(os.path.join(folder, cand)):
                pats = [cand]
                break
        pats = pats or ['*.json']
    files = []
    for pat in pats:
        for hit in sorted(glob.glob(os.path.join(folder, pat))):
            base = os.path.basename(hit)
            if 'BuiltData' in base or 'VisibilityData' in base:
                continue
            if hit not in files:
                files.append(hit)
    return folder, files


def _comp_world(comps, ref, depth=0):
    idx = mp.ref_index(ref)
    if idx is None or idx not in comps:
        return (0.0, 0.0, 0.0), 0.0
    p = comps[idx]
    loc = mp.vec(p.get('RelativeLocation'))
    yaw = (p.get('RelativeRotation') or {}).get('Yaw', 0.0) or 0.0
    parent = p.get('AttachParent')
    if parent and depth < 6:
        ploc, pyaw = _comp_world(comps, parent, depth + 1)
        dx, dy = mp.yaw_rotate(loc[0], loc[1], pyaw)
        loc = (ploc[0] + dx, ploc[1] + dy, ploc[2] + loc[2])
        yaw += pyaw
    return loc, yaw


def scan_points(map_name, level, cfg, refresh=False, verbose=True):
    ptypes = cfg.get('point_types') or []
    if not ptypes:
        return []
    folder, files = resolve_sources(map_name, cfg, level)
    cache_path = os.path.join(CACHE_DIR, '%s.points.%s.json' % (map_name, level))

    stamp = []
    for path in files:
        st = os.stat(path)
        stamp.append([os.path.basename(path), st.st_size, int(st.st_mtime)])
    meta = [[t.get('pattern'), t.get('match') or 'name', t.get('label'), t.get('style'),
             t.get('merge_room', True), t.get('props') or [], t.get('short') or '']
            for t in ptypes]

    old = load_json(cache_path, None)
    if not refresh and old and old.get('stamp') == stamp and old.get('meta') == meta:
        if verbose:
            print('点位缓存 %-28s %d 个' % (level, len(old['points'])))
        return old['points']

    # match=type: 按蓝图类名匹配（推荐写法）
    # match=name: 按实例名匹配（旧的 zones/*.json 规则）
    pats = [(t['key'], re.compile(t['pattern']), t.get('label') or '',
             t.get('style') or '', t.get('merge_room', True), t.get('match') or 'name',
             t.get('short') or '')
            for t in ptypes]
    prop_keys = sorted({k for t in ptypes for k in (t.get('props') or [])})

    points = []
    for path in files:
        comps, actors = {}, []
        for idx, obj in mp.iter_objects(path):
            t = obj.get('Type') or ''
            if t in mp.KEEP_COMPONENT_TYPES:
                p = obj.get('Properties') or {}
                comps[idx] = {k: p[k] for k in mp.COMP_TRIM_KEYS if k in p}
                continue
            name = obj.get('Name') or ''
            if not name or not t.endswith('_C'):
                continue
            for key, rx, lab, sty, mrg, mmode, shrt in pats:
                hay = t if mmode == 'type' else name
                if rx.search(hay):
                    props = obj.get('Properties') or {}
                    actors.append({'actor': name, 'type': t, 'key': key, 'label': lab,
                                   'style': sty, 'merge_room': mrg, 'short': shrt,
                                   'root': props.get('RootComponent'),
                                   'props': {k: props[k] for k in prop_keys if k in props}})
                    break
        for a in actors:
            loc, yaw = _comp_world(comps, a['root'])
            points.append({'actor': a['actor'], 'type': a['type'], 'key': a['key'],
                           'label': a['label'], 'style': a['style'],
                           'merge_room': a['merge_room'], 'short': a['short'],
                           'file': os.path.basename(path),
                           'x': _r1(loc[0]), 'y': _r1(loc[1]), 'z': _r1(loc[2]),
                           'yaw': round(yaw, 2), 'props': a['props']})
        if verbose:
            print('  点位 %-42s → %d' % (os.path.basename(path), len(actors)))

    save_json(cache_path, {'stamp': stamp, 'meta': meta, 'points': points})
    return points


# 文件名里的试炼标记：PSB_MT03_B00.json → MT03；没有就属于通用文件
TRIAL_FILE_RE = re.compile(r'_(MT\d{2}|T\d{2}_B\d{2}|B\d{2})_', re.I)

# 刷怪门：怪物从这种门/柜里出来（MonsterClosetDoor-01_BP 等）
SPAWN_DOOR_RE = re.compile(r'MonsterCloset|MonsterDoor|ClosetDoor|SpawnDoor|BursterDoor', re.I)


def door_class_maps():
    """{地图名: {门类名…}}，从各图的几何缓存里汇总（有缓存，秒开）。"""
    cache_path = os.path.join(CACHE_DIR, 'door_classes.json')
    paths = sorted(glob.glob(os.path.join(CACHE_DIR, '*.geom.json')))
    stamp = [[os.path.basename(p), int(os.path.getmtime(p))] for p in paths]
    old = load_json(cache_path, None)
    if old and old.get('stamp') == stamp:
        return old['maps']
    index = {}
    for path in paths:
        geo = load_json(path, None) or {}
        name = os.path.basename(path)[:-len('.geom.json')]
        index[name] = sorted({d.get('type') for d in geo.get('doors') or [] if d.get('type')})
    save_json(cache_path, {'stamp': stamp, 'maps': index})
    return index


# ---------------------------------------------------------------------------
# 归属：点位→房间→分区，房间→分区，以及楼层
# ---------------------------------------------------------------------------
def assign_zones(rooms, points, specs):
    """点位所在房间优先，其次按 zones[].rooms 通配（支持 ! 排除）。"""
    owner = {}
    for p in points:
        # merge_room=False 的点位只给自己上色，不把所在房间划进自己的分区
        if p.get('room') and p.get('zone') and p.get('merge_room', True):
            owner[p['room']] = p['zone']
    for spec in specs:
        raw = list(spec.get('rooms') or [])
        pats = [x for x in raw if not x.startswith('!')]
        skip = [x[1:] for x in raw if x.startswith('!')]
        pats += [p['room'] for p in points
                 if p['zone'] == spec['id'] and p.get('room') and p.get('merge_room', True)]
        for pat in pats:
            for r in rooms:
                if not zm.room_match(r, pat):
                    continue
                if any(zm.room_match(r, s) for s in skip):
                    continue
                owner.setdefault(r['raw_name'], spec['id'])
    return owner


def cluster_floors(rooms, min_sep=250.0, min_rooms=3, span=400.0):
    """按房间地面高度 z 聚层。

    不用「相邻值链式聚合」（一路链下去会把整张图合成一层），而是
    「以簇内第一个值为锚点，超过 min_sep 就开新簇」；簇内房间数不足的
    并入最近的真实楼层。
    高跨度房间（楼梯井/中庭）不参与采样，跨越楼层分界 >= span 时同时归属两层。
    """
    clusters = []
    for z in sorted(r['zmin'] for r in rooms):
        if clusters and z - clusters[-1][0] <= min_sep:
            clusters[-1][1].append(z)
        else:
            clusters.append([z, [z]])
    # 只有 1~2 个房间的碎簇通常是夹层/平台，并到最近的真实楼层
    keep = [c for c in clusters if len(c[1]) >= min_rooms] or clusters
    levels = sorted(sum(c[1]) / len(c[1]) for c in keep)

    def nearest(z):
        return min(range(len(levels)), key=lambda i: (abs(levels[i] - z), i)) if levels else 0

    def band(i):
        lo = -1e9 if i == 0 else (levels[i] + levels[i - 1]) / 2.0
        hi = 1e9 if i == len(levels) - 1 else (levels[i] + levels[i + 1]) / 2.0
        return lo, hi

    room_floors = {}
    for r in rooms:
        primary = nearest(r['zmin'])
        room_floors[r['raw_name']] = [primary]
        for i in range(len(levels)):
            if i == primary:
                continue
            lo, hi = band(i)
            if min(r['zmax'], hi) - max(r['zmin'], lo) >= span:
                room_floors[r['raw_name']].append(i)
        room_floors[r['raw_name']].sort()

    # 标签：最低层在地面以下（< -150）时叫 B1，其余从 1F 开始编号
    labels = []
    has_basement = bool(levels) and levels[0] < -150
    for i in range(len(levels)):
        if i == 0 and has_basement:
            labels.append('B1')
        else:
            labels.append('%dF' % (i + 1 - (1 if has_basement else 0)))

    out = [{'index': i, 'level': round(lv, 1), 'label': labels[i],
            'band': [None if band(i)[0] < -1e8 else round(band(i)[0], 1),
                     None if band(i)[1] > 1e8 else round(band(i)[1], 1)]}
           for i, lv in enumerate(levels)]
    return out, room_floors, nearest


def build_floors(rooms, doors, items, points, opts=None):
    opts = opts or {}
    out, room_floors, nearest = cluster_floors(
        rooms, opts.get('min_sep', 250.0), opts.get('min_rooms', 3), opts.get('span', 400.0))
    door_floor = {id(d): nearest(d['z']) for d in doors}
    item_floor = {}
    for it in items:
        near = None
        for r in rooms:
            if any(mp.point_in_poly(it['x'], it['y'], h) for h in r['hulls']) \
                    and r['zmin'] - 5 <= it['z'] <= r['zmax'] + 5:
                near = r
                break
        cand = room_floors.get(near['raw_name']) if near else None
        item_floor[id(it)] = cand[0] if cand else nearest(it['z'])
    for p in points:
        p['floor'] = nearest(p['z'])
    return out, room_floors, door_floor, item_floor, nearest


# ---------------------------------------------------------------------------
# 组装关卡 JSON
# ---------------------------------------------------------------------------
def build_level(level, map_override=None, refresh=False, verbose=True, opts=None):
    level = level.upper()
    map_name = resolve_map(level, map_override)
    cfg = load_point_cfg(level)
    opts = opts or {}
    ecfg = opts.get('extract') or load_extract_cfg()
    layers = ecfg.get('layers') or {}
    item_cats = set(ecfg.get('item_cats') or [])

    geo = load_geometry(map_name, refresh=refresh, verbose=verbose)
    rooms, doors, items, spawns = geo['rooms'], geo['doors'], geo['items'], geo['spawns']

    points = (scan_points(map_name, level, cfg, refresh=refresh, verbose=verbose)
              if layers.get('points', True) else [])

    # 点位 → 房间 → 分区
    for p in points:
        p['room'] = zm.room_of_point(rooms, p['x'], p['y'], p['z'])
        p['zone'] = zm.point_zone(p, cfg.get('zones') or [])
        p['short'] = p.get('short') or zm.short_actor(p['actor'])
        if len(p['short']) <= 3 or p['short'].upper().startswith('BP'):
            p['short'] = p.get('label') or p['short']

    specs = cfg.get('zones') or []
    for i, spec in enumerate(specs):
        spec.setdefault('color', zm.ZONE_PALETTE[i % len(zm.ZONE_PALETTE)])
    owner = assign_zones(rooms, points, specs)

    # 分区只按 rooms 划分时，点位跟着所在房间继承分区（否则隐藏分区时点位还留在图上）
    for p in points:
        if not p.get('zone') and p.get('room'):
            p['zone'] = owner.get(p['room'])

    floor_meta, room_floors, door_floor, item_floor, nearest = build_floors(
        rooms, doors, items, points, ecfg.get('floors'))

    names = zm.Names(cfg)
    raw2id = {r['raw_name']: i for i, r in enumerate(rooms)}

    # 门分类：刷怪门（怪物柜门）+ 本关专属门（只在本次试炼的文件里出现）
    door_files = {}
    for d in doors:
        door_files.setdefault(d['type'], set()).add(d['file'])
    generic_files = {s[0] for s in geo['stamp'] if not TRIAL_FILE_RE.search(s[0])}
    other_maps = set()
    for name, types in door_class_maps().items():
        if name != map_name:
            other_maps.update(types)

    def door_kind(dtype):
        if SPAWN_DOOR_RE.search(dtype or ''):
            return 'spawn'
        return mp.door_cat(dtype)

    def door_trial_only(dtype):
        """本关专属门：本图没有通用文件放它，而且别的图里也没有同类。"""
        if door_files.get(dtype, set()) & generic_files:
            return False
        return dtype not in other_maps

    out_rooms = []
    for i, r in enumerate(rooms):
        en_name = pretty_en(names.get(r, 'en')) or ''
        if not en_name.isascii():                 # 别名表里只有中文名时，回落到原始名的英文
            en_name = pretty_en(zm.raw_display(r))
        out_rooms.append({
            'id': i,
            'raw': r['raw_name'],
            'name': en_name or r['raw_name'],
            'name_zh': names.get(r, 'zh'),
            'hulls': [[[_r1(x), _r1(y)] for x, y in h] for h in r['hulls']],
            'z': [_r1(r['zmin']), _r1(r['zmax'])],
            'c': [_r1(r['cx']), _r1(r['cy'])],
            'area': r['area'],
            'size': (r.get('room_size') or '').replace('ERoomSize::', ''),
            'kind': ('corridor' if mp.is_corridor(r['name'])
                     else 'connector' if mp.is_connector(r['name']) else 'room'),
            'floors': room_floors.get(r['raw_name']) or [],
            'zone': owner.get(r['raw_name']),
        })

    out_doors = []
    if layers.get('doors', True):
        for i, d in enumerate(doors):
            if (d.get('name') or '').startswith('Default__'):
                continue                       # 关卡蓝图 CDO，不是摆在场景里的门
            cat = mp.door_cat(d['type'])
            kind = door_kind(d['type'])
            base_cat = cat if cat in mp.DOOR_CATS else 'other'
            trial_only = door_trial_only(d['type'])
            out_doors.append({
                'id': i, 'name': d['name'], 'type': d['type'], 'cat': cat, 'kind': kind,
                'trial_only': bool(trial_only),
                'w': mp.door_width(d['type'], mp.DOOR_CATS[base_cat][3]),
                'p': [_r1(d['x']), _r1(d['y']), _r1(d['z'])],
                'yaw': round(d['yaw'] or 0.0, 1),
                'rooms': [raw2id[n] for n in (d.get('_rooms') or []) if n in raw2id],
                'floor': door_floor.get(id(d)),
            })

    out_items = []
    if layers.get('items', False):
        for i, it in enumerate(items):
            if item_cats and it['cat'] not in item_cats:
                continue
            out_items.append({
                'id': i, 'name': it['name'], 'cat': it['cat'],
                'label': pretty_en((it['cat'] or '').replace('_', ' ')).title(),
                'label_zh': it['cat_label'],
                'p': [_r1(it['x']), _r1(it['y']), _r1(it['z'])],
                'room': raw2id.get(zm.room_of_point(rooms, it['x'], it['y'], it['z'])),
                'floor': item_floor.get(id(it)),
            })

    # 点位编号：区内按 actor 自然序（与关卡内编号一致）
    points.sort(key=lambda p: (p.get('zone') or '~', zm.natural_key(p['actor'])))
    # 同一分区里短名重复（如都是 Code）就没意义，统一退化为类型名
    dup = {}
    for p in points:
        k = (p.get('zone'), p['short'])
        dup[k] = dup.get(k, 0) + 1
    counter = {}
    out_points = []
    for i, p in enumerate(points):
        zid = p.get('zone') or '~'
        counter[zid] = counter.get(zid, 0) + 1
        label_en = pretty_en(p['key'].replace('_', ' ')).title()
        short = p['short']
        if (len(short) <= 3 or short.upper().startswith('BP') or not short.isascii()
                or dup.get((p.get('zone'), p['short']), 0) > 1):
            short = label_en
        out_points.append({
            'id': i, 'actor': p['actor'], 'key': p['key'],
            'label': label_en, 'label_zh': p['label'],
            'style': p['style'], 'short': short, 'num': counter[zid],
            'p': [p['x'], p['y'], p['z']],
            'room': raw2id.get(p.get('room')),
            'zone': p.get('zone'), 'floor': p.get('floor'),
        })

    xs = [v[0] for r in out_rooms for h in r['hulls'] for v in h]
    ys = [v[1] for r in out_rooms for h in r['hulls'] for v in h]
    bbox = [min(xs), min(ys), max(xs), max(ys)] if xs else [0, 0, 1, 1]

    db = {
        'schema': SCHEMA,
        'level': level,
        'map': map_name,
        'title': cfg.get('title') or level,
        'subtitle': cfg.get('subtitle') or '',
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': {'folder': geo['folder'],
                   'files': len(geo['stamp']),
                   'zone_cfg': rel(zone_cfg_path(level)) if os.path.exists(zone_cfg_path(level)) else None,
                   'point_cfg': rel(point_cfg_path(level)) if os.path.exists(point_cfg_path(level)) else None},
        'bbox': [_r1(v) for v in bbox],
        'zrange': [min((r['z'][0] for r in out_rooms), default=0),
                   max((r['z'][1] for r in out_rooms), default=0)],
        'floors': floor_meta,
        'zones': [{'id': s['id'],
                   'name': (s.get('name_en') or s.get('name')
                            or s['id']) if (s.get('name_en') or (s.get('name') or '').isascii())
                           else 'Zone %s' % s['id'],
                   'name_zh': s.get('name') or '',
                   'color': s['color'],
                   'note_zh': s.get('note') or ''} for s in specs],
        'rooms': out_rooms,
        'doors': out_doors,
        'points': out_points,
        'items': out_items,
        'notes': {'rooms': {}, 'zones': {}, 'points': {}},
    }
    return db


def merge_notes(db, path):
    """保留上一版 JSON 里的备注（UI 里加的备注不能被重新提取冲掉）。"""
    old = load_json(path, None)
    if not old:
        return db
    notes = old.get('notes') or {}
    for key in ('rooms', 'zones', 'points'):
        db['notes'][key] = dict(notes.get(key) or {})
    kept = sum(len(v) for v in db['notes'].values())
    if kept:
        print('  保留备注 %d 条（rooms=%d zones=%d points=%d）'
              % (kept, len(db['notes']['rooms']), len(db['notes']['zones']),
                 len(db['notes']['points'])))
    return db


def write_level(level, db, out_dir=None):
    path = os.path.join(out_dir or OUT_DIR, '%s.json' % level.upper())
    merge_notes(db, path)
    save_json(path, db)
    print('%s → %s  (%.0f KB)' % (level, rel(path), os.path.getsize(path) / 1024.0))
    return path


def check_level(level, out_dir=None):
    """数据自检：点位数、归属、坐标、分区覆盖。返回问题条数（0=通过）。"""
    path = os.path.join(out_dir or OUT_DIR, '%s.json' % level.upper())
    db = load_json(path, None)
    if not db:
        print('找不到 %s（先跑 python mapdb.py %s）' % (rel(path), level))
        return 1
    rooms = db['rooms']
    doors = db.get('doors') or []
    points = db.get('points') or []
    zones = db.get('zones') or []
    print('%s  数据自检  %s  (%.0f KB)' % (level, rel(path), os.path.getsize(path) / 1024.0))
    print('  生成 %s   来源 %s' % (db.get('generated'), (db.get('source') or {}).get('folder')))
    print('  房间 %d   门 %d   点位 %d   物品 %d   楼层 %d   分区 %d'
          % (len(rooms), len(doors), len(points), len(db.get('items') or []),
             len(db.get('floors') or []), len(zones)))
    if doors:
        kinds = {}
        for d in doors:
            kinds[d.get('kind') or 'other'] = kinds.get(d.get('kind') or 'other', 0) + 1
        print('  门类型  %s   trial_only=%d'
              % (' '.join('%s=%d' % kv for kv in sorted(kinds.items())),
                 sum(1 for d in doors if d.get('trial_only'))))
    if points:
        keys = {}
        for p in points:
            keys[p['key']] = keys.get(p['key'], 0) + 1
        print('  点位类型  %s' % ' '.join('%s=%d' % kv for kv in sorted(keys.items())))

    issues = []
    if not zones:
        issues.append('该关卡没有分区（zones 为空）：图例无法按区筛选，房间用中性色')
    else:
        unzoned = [r for r in rooms if not r.get('zone')]
        if unzoned:
            issues.append('%d 个房间没有分区归属：%s'
                          % (len(unzoned), ', '.join(r['raw'] for r in unzoned[:4])))
        empty = [z['id'] for z in zones
                 if not any(r.get('zone') == z['id'] for r in rooms)]
        if empty:
            issues.append('分区 %s 没有任何房间（rooms 通配可能写错）' % ','.join(empty))
    no_room = [p for p in points if p.get('room') is None]
    if no_room:
        issues.append('%d 个点位没匹配到房间：%s'
                      % (len(no_room), ', '.join(p['actor'] for p in no_room[:4])))
    zero = [p for p in points if p['p'][:3] == [0, 0, 0]]
    if zero:
        issues.append('%d 个点位坐标是 (0,0,0)（可能是占位或读取失败）：%s'
                      % (len(zero), ', '.join(p['actor'] for p in zero[:3])))
    if zones:
        no_zone = [p for p in points if not p.get('zone')]
        if no_zone:
            issues.append('%d 个点位没有分区：%s'
                          % (len(no_zone), ', '.join(p['actor'] for p in no_zone[:4])))
        dup = {}
        for p in points:
            if (p.get('short') or '') == (p.get('label') or ''):
                continue          # 短名就是类型名时，同类型重复是正常的
            k = (p.get('zone'), p.get('short'))
            dup[k] = dup.get(k, 0) + 1
        same = [k for k, v in dup.items() if v > 1 and k[1]]
        if same:
            issues.append('%d 组同区同短名（图上会重名）：%s'
                          % (len(same), ', '.join(str(k[1]) for k in same[:3])))
    if not db.get('floors'):
        issues.append('没有楼层信息（z 聚类失败），分层模式不可用')

    for text in issues:
        print('  ! ' + text)
    print('  结论  %s' % ('通过' if not issues else '%d 条提示' % len(issues)))
    return len(issues)


def main(argv=None):
    ap = argparse.ArgumentParser(description='从 paks 地图 JSON 提取关卡元数据')
    ap.add_argument('level', nargs='?', help='关卡编号，如 SMC_MT02')
    ap.add_argument('--all', action='store_true', help='生成 seed.py 里所有能定位到地图的关卡')
    ap.add_argument('--map', default=None, help='手动指定 paks/MAP/Maps 下的目录名')
    ap.add_argument('--out-dir', default=None, help='输出目录（默认 data/maps）')
    ap.add_argument('--refresh', action='store_true', help='强制重扫几何与点位')
    ap.add_argument('--with-items', action='store_true', help='额外提取交互物品（藏身点/血包等）')
    ap.add_argument('--item-cats', default=None, help='物品类别白名单，如 hide,health')
    ap.add_argument('--no-doors', action='store_true', help='不提取门')
    ap.add_argument('--no-points', action='store_true', help='不提取任务点位')
    ap.add_argument('--check', action='store_true', help='自检已生成的 JSON（点位数/归属/分区覆盖）')
    ap.add_argument('--sync-levels', action='store_true',
                    help='从 release/seed/seed.py 同步「关卡 → 地图名」到 data/levels.json')
    ap.add_argument('--paks', default=None, metavar='DIR',
                    help='paks/MAP/Maps 目录（独立交付时用；也可设环境变量 OUTLAST_MAPS_DIR）')
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    global MAPS_DIR
    if args.paks:
        MAPS_DIR = os.path.abspath(args.paks)
    if args.sync_levels:
        return sync_levels()

    verbose = not args.quiet
    if args.all:
        levels = [k for k, v in LEVELS.items() if v.get('map')]
    elif args.level:
        levels = [args.level.upper()]
    else:
        ap.print_help()
        return 2

    ecfg = load_extract_cfg()
    if args.with_items:
        ecfg['layers']['items'] = True
    if args.item_cats:
        ecfg['item_cats'] = [c.strip() for c in args.item_cats.split(',') if c.strip()]
    if args.no_doors:
        ecfg['layers']['doors'] = False
    if args.no_points:
        ecfg['layers']['points'] = False
    if verbose:
        print('提取配置：doors=%s points=%s items=%s%s'
              % (ecfg['layers']['doors'], ecfg['layers']['points'], ecfg['layers']['items'],
                 (' cats=' + ','.join(ecfg['item_cats'])) if ecfg['item_cats'] else ''))
    opts = {'extract': ecfg}

    # --check：自检已生成的 JSON
    if args.check:
        issues = 0
        for level in levels:
            issues += check_level(level, args.out_dir)
        return 0 if issues == 0 else 1

    for level in levels:
        try:
            db = build_level(level, args.map, args.refresh, verbose, opts)
        except SystemExit as exc:
            print('跳过 %s：%s' % (level, exc))
            continue
        except Exception as exc:                       # 单个关卡失败不影响其它关卡
            print('失败 %s：%s: %s' % (level, type(exc).__name__, exc))
            continue
        write_level(level, db, args.out_dir)
        if verbose:
            print('   rooms=%d doors=%d points=%d items=%d floors=%d zones=%d'
                  % (len(db['rooms']), len(db['doors']), len(db['points']),
                     len(db['items']), len(db['floors']), len(db['zones'])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
