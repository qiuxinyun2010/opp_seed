#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""map3d.py — 从 paks 原始关卡 JSON 提取「粗略 3D 几何」，供 Web 版 3D 模式使用。

与 mapdb.py 的关系
------------------
mapdb.py 把 UE 房间 Brush 的 3D 凸包投影成 2D 多边形（只留 zmin/zmax），
本脚本回到原始 paks，补回 3D 模式下需要的东西：

  * props[]      从 CHJ_LA_*.json 的 StaticMeshComponent 提取家具/道具实例，
                 按网格名推断类别与近似尺寸，输出占位盒（桌子、椅子、箱子、
                 柜子、柱子、放映机、电视……）。没有材质，只有大致形状。
  * structures[] 同一批实例里的墙体/窗墙等结构网格，单独一层，默认不显示。
  * solids[]     CHJ_LD_Rooms.json 里每个 RBRoom 的 ConvexElems 世界包围盒，
                 用来画半透明房间体块（比 2D hulls + z 更贴近真实层高）。

门 / 楼梯 / 点位 / 楼层不重复提取，直接复用 data/maps/<LEVEL>.json。

用法
----
    python map3d.py CHJ_MT02                     # 需要 paks/MAP/Maps 在同级仓库
    python map3d.py CHJ_MT02 --paks D:/.../paks/MAP/Maps
    python map3d.py CHJ_MT02 --check            # 自检已生成的 JSON
    python map3d.py --all                       # data/levels.json 里有 2D 数据的关卡

输出：data/3d/<LEVEL>.json（CHJ_MT02 约 0.4 MB，纯文本，可随 ui/ 一起交付）
"""
from __future__ import print_function

import argparse
import datetime
import glob
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import mapdb                                    # noqa: E402  配置 / 路径 / IO
from maplib import extract as mp               # noqa: E402  流式解析与坐标原语

SCHEMA = 1
OUT_DIR = os.path.join(HERE, 'data', '3d')

# 组件类型：只要有 RelativeLocation / AttachParent 就收，用于拼父链
COMP_TYPES = {
    'SceneComponent', 'StaticMeshComponent', 'SkeletalMeshComponent',
    'BoxComponent', 'CapsuleComponent', 'SphereComponent', 'ArrowComponent',
    'BrushComponent', 'ChildActorComponent', 'BillboardComponent',
    'PrefabComponent', 'DecalComponent', 'SplineMeshComponent',
}

# ---------------------------------------------------------------------------
# 网格名 → 类别 / 近似尺寸（UE 单位 cm；[X 宽, Y 深, Z 高]）
# 资产本体不在 paks 里（只有引用），所以尺寸只能按名字里的标称值 + 类别经验值估。
# ---------------------------------------------------------------------------
CAT_RULES = [
    # (类别, 正则, 默认尺寸)  —— 顺序即优先级
    ('column',   r'column|pillar|obelisk|marblecolumn|fakecolumn|flagpole', [70, 70, 130]),
    ('statue',   r'statue|sculpt|bust|themis|conqueror|mannequinbust', [90, 90, 240]),
    ('projector',r'projector|filmreel|cassette|diaporama', [80, 55, 90]),
    ('screen',   r'pull?downscreen|televisionscreen|television|monitor|^tv|screen|narrativescreen', [140, 25, 100]),
    ('desk',     r'desk|lectern|podium|worktable|drawingtable|engineertable|librarytable', [170, 80, 78]),
    ('table',    r'table|countertop|tabletop', [150, 80, 75]),
    ('bench',    r'bench|pew', [190, 50, 90]),
    ('chair',    r'chair|stool|seating', [52, 52, 92]),
    ('sofa',     r'sofa|couch|armchair', [200, 90, 85]),
    ('bed',      r'\bbed\b|mattress|casket|coffin|gurney', [200, 120, 60]),
    ('cabinet',  r'cabinet|cupboard|wardrobe|locker|dresser|closet|drawer|filingcabinet|filecabinet|shelf|shelves|bookcase', [95, 48, 185]),
    ('box',      r'box|crate|chest|case|trunk|casket|toybox|evidencebox|filmbox', [62, 62, 58]),
    ('books',    r'book|binder|deedbook|pharmabook|librarybooks|fileorganizer|mailingletters', [32, 24, 12]),
    ('barrel',   r'barrel|bucket|pot\b|plantnop|flowerbox|planter|trashcan|bin\b|dispenser', [48, 48, 62]),
    ('machine',  r'generator|machine|oscilloscope|typewriter|console|electricpanel|mainpanel|elevatorcage|phone|radio|microphone', [100, 65, 135]),
    ('cart',     r'cart|trolley|wheelbarrow|stroller', [95, 62, 100]),
    ('sink',     r'sink|counter|faucet|kitchen', [170, 70, 92]),
    ('safe',     r'\bsafe\b|vault|clock|piano|organ|altar|fountain', [110, 80, 140]),
    ('divider',  r'divider|partition|cage|barrier|fence|gate', [130, 18, 80]),
]

# 结构类（单独一层，默认关闭）：按名字里的数字推断长宽
STRUCT_RULES = re.compile(
    r'^(?:wallmiddle|fakewall|wall_|wallplank|walltop|wallasphalt|wallbrick|'
    r'murkoffwallpartition|windowswall|ch_windows|wallbox|ch_wall|'
    r'plywood_|columnwoodframe)', re.I)

# 明显是杂项 / 碰撞体 / 装饰碎片，即使命中上面规则也不要
SKIP_RULES = re.compile(
    r'collision|blocker|occluder|invisible|shadow|decal|gen_variable|'
    r'rubbish|newspaper|trashcan_rubbish|debris|stain|blood|graffiti|'
    r'spline|lod\d|lightmap|navmesh|previs|'
    r'wire|pipe|cable|conduit|molding|moulding|cornice|baseboard|'
    r'ceiling|roof|vent|duct|beam|scaffold|stair|step\b|railing|'
    r'curtain|poster|signage|splatter|particle|'
    r'plywoodbox|wallmiddlecorner|wallframe|wallbackcorner', re.I)

CAT_COLORS = {
    'desk': '#b98a55', 'table': '#c39a63', 'chair': '#8a8f98',
    'bench': '#a07a52', 'sofa': '#8f6f78', 'bed': '#a6a2b8',
    'cabinet': '#7d8b74', 'box': '#a9793f', 'books': '#7b93a8',
    'column': '#c9c4b4', 'statue': '#b0a89a', 'barrel': '#6f8d7a',
    'machine': '#6b8396', 'screen': '#4d6b86', 'projector': '#8d6a9c',
    'cart': '#8b8069', 'sink': '#9aa5a7', 'safe': '#716f80',
    'divider': '#8c8c8c', 'misc': '#8d8b84',
}

STRUCT_SKIP = re.compile(
    r'wall|floor|ceiling|molding|moulding|plywood|plank|beam|wire|pipe|vent|'
    r'railing|rubbish|trash|window|door|frame|trim|cornice|baseboard|'
    r'light|lamp|decal|sign|poster|paper|stain|blood|graffiti|curtain|'
    r'scaffold|brick|asphalt|concrete|roof|stair|step|collision|blocker|'
    r'occluder|volume|nav|fog|particle|gizmo|newspaper|leaf|debris|'
    r'spline|shadow|arches|arch-|plantnop|'
    r'chainlinkfence|chainfence|forgedfence|fenceside|flagpole|booth_column', re.I)


def classify(mesh):
    """返回 (类别, 尺寸)；不属于家具/道具则返回 None。"""
    low = mesh.lower()
    if STRUCT_SKIP.search(low):
        return None
    for cat, rx, size in CAT_RULES:
        if re.search(rx, low):
            w, d, h = size
            # 名字里带标称尺寸就覆盖宽度（_1m / 375cm / 150x130 / WallMiddle1000）
            m = re.search(r'(\d{2,4})\s*[xX]\s*(\d{2,4})', mesh)
            if m:
                w = float(m.group(1)); d = float(m.group(2))
            else:
                m = re.search(r'(\d{2,4})\s*cm\b', mesh, re.I)
                if m:
                    w = float(m.group(1))
                else:
                    m = re.search(r'(?:^|[_\-])(\d{1,2})m(?:[_\-]|\d|$)', mesh, re.I)
                    if m:
                        w = float(m.group(1)) * 100
            return cat, [clamp(w, 18, 600), clamp(d, 18, 600), clamp(h, 8, 500)]
    return None


# 各品类的绝对尺寸上限（cm）。静态网格缩放有时会到 5~10 倍，
# 不夹住的话柱子/栅栏会变成几层楼高的细刺，把整张图糊住。
SIZE_CAPS = {
    'column': (160, 160, 180), 'statue': (220, 220, 260),
    'divider': (420, 90, 100), 'cabinet': (420, 180, 280),
    'box': (400, 400, 220), 'barrel': (180, 180, 140),
    'desk': (500, 220, 140), 'table': (500, 220, 140),
    'bench': (400, 120, 140), 'machine': (260, 180, 220),
    'screen': (300, 80, 180), 'safe': (220, 160, 220),
    'cart': (200, 140, 150), 'sink': (450, 140, 140),
    'sofa': (350, 160, 140), 'bed': (350, 220, 120),
    'chair': (120, 120, 140), 'books': (80, 60, 40),
    'projector': (180, 140, 140),
}
GENERIC_CAP = (500, 500, 320)


def limit_size(cat, size):
    cap = SIZE_CAPS.get(cat, GENERIC_CAP)
    out = [min(size[i], cap[i]) for i in range(3)]
    if cat == 'column':                 # 柱子别细成一根针
        out[0] = max(out[0], 40.0)
        out[1] = max(out[1], 40.0)
    return out


def clamp(v, lo=0.35, hi=2.5):
    return max(lo, min(hi, v))


def struct_size(mesh, scale):
    """墙体类网格：按名字里的数字推出长度，高度固定一层楼，厚度 18cm。"""
    m = re.search(r'(\d{2,4})\s*[xX]\s*(\d{2,4})', mesh)
    if m:
        w, h = float(m.group(1)), float(m.group(2))
    else:
        m = re.search(r'(?:middle|plank|bottom|top|wall|floor)(\d{2,4})', mesh, re.I)
        w = float(m.group(1)) if m else 200.0
        h = 300.0
    return [clamp(w * abs(scale[0]), 20, 1200), 18.0,
            clamp(h * abs(scale[2]), 40, 420)]


def clean_mesh(ref):
    if not ref:
        return ''
    return re.sub(r"^StaticMesh'\s*|\s*'$", '', ref).strip()


# ---------------------------------------------------------------------------
# 静态网格实例
# ---------------------------------------------------------------------------
def scan_components(path, verbose=False):
    """流式读一个 LA_*.json，只保留「已放置实例」的组件及其变换。"""
    comps = {}
    for idx, obj in mp.iter_objects(path):
        if obj.get('Type') not in COMP_TYPES:
            continue
        outer = (obj.get('Outer') or {}).get('ObjectName') or ''
        # CDO / 蓝图模板变量（Default__*, *_GEN_VARIABLE）不是场景实例
        if ':PersistentLevel.' not in outer:
            continue
        p = obj.get('Properties') or {}
        comps[idx] = {
            'loc': p.get('RelativeLocation'),
            'rot': p.get('RelativeRotation'),
            'scale': p.get('RelativeScale3D'),
            'parent': mp.ref_index(p.get('AttachParent')),
            'mesh': clean_mesh((p.get('StaticMesh') or {}).get('ObjectName')),
        }
    if verbose:
        print('  %-46s components=%d' % (os.path.basename(path), len(comps)))
    return comps


def world_transform(comps, idx, depth=0):
    """沿 AttachParent 累加位置 / yaw / scale（比 maplib.comp_transform 多带 scale）。"""
    c = comps.get(idx)
    if not c or depth > 8:
        return (0.0, 0.0, 0.0), 0.0, (1.0, 1.0, 1.0)
    loc = mp.vec(c['loc'])
    yaw = (c['rot'] or {}).get('Yaw', 0.0) or 0.0
    s = mp.vec(c['scale'], 1.0)
    if c['parent'] is not None:
        ploc, pyaw, pscale = world_transform(comps, c['parent'], depth + 1)
        dx, dy = mp.yaw_rotate(loc[0], loc[1], pyaw)
        loc = (ploc[0] + dx, ploc[1] + dy, ploc[2] + loc[2])
        s = (s[0] * pscale[0], s[1] * pscale[1], s[2] * pscale[2])
        yaw += pyaw
    return loc, yaw, s


def extract_meshes(folder, db, with_structures=True, max_structures=5000, verbose=False):
    """返回 (props, structures, stats)。坐标是世界坐标 uu，未做镜像。"""
    bbox = db.get('bbox') or [-1e6, -1e6, 1e6, 1e6]
    zrange = db.get('zrange') or [-1e6, 1e6]
    x0, y0, x1, y1 = bbox
    z0, z1 = zrange
    margin = 600.0

    props, structs = [], []
    seen = set()
    stats = Counter()
    files = [f for f in sorted(os.listdir(folder))
             if f.endswith('.json') and 'BuiltData' not in f
             and 'VisibilityData' not in f and '_LA_' in f]
    for fn in files:
        comps = scan_components(os.path.join(folder, fn), verbose)
        stats['components'] += len(comps)
        for idx, c in comps.items():
            mesh = c['mesh']
            if not mesh:
                continue
            stats['meshes'] += 1
            is_struct = bool(STRUCT_RULES.search(mesh)) and not SKIP_RULES.search(mesh)
            cat_size = None if is_struct else classify(mesh)
            if not is_struct and not cat_size:
                continue
            if not with_structures and is_struct:
                continue
            if is_struct and len(structs) >= max_structures:
                continue
            loc, yaw, scale = world_transform(comps, idx)
            x, y, z = loc
            if abs(x) < 1 and abs(y) < 1 and abs(z) < 1:
                stats['zero'] += 1
                continue
            if not (x0 - margin <= x <= x1 + margin and
                    y0 - margin <= y <= y1 + margin and
                    z0 - 500 <= z <= z1 + 250):
                stats['outside'] += 1
                continue
            key = (mesh, round(x), round(y), round(z))
            if key in seen:
                stats['duplicate'] += 1
                continue
            seen.add(key)
            # 负缩放只是镜像，取绝对值；异常大的缩放会造出巨盒，夹到合理区间
            sx, sy, sz = (clamp(abs(v)) for v in scale)
            if is_struct:
                size = struct_size(mesh, (sx, sy, sz))
                cat = 'wall'
            else:
                cat, base = cat_size
                size = limit_size(cat, [base[0] * sx, base[1] * sy, base[2] * sz])
            row = {
                'p': [round(x, 1), round(y, 1), round(z, 1)],
                'yaw': round(yaw, 1),
                'size': [round(v, 1) for v in size],
                'cat': cat,
                'mesh': mesh,
                'file': fn,
            }
            (structs if is_struct else props).append(row)
            stats[('struct' if is_struct else 'prop') + ':' + cat] += 1
    return props, structs, stats


# ---------------------------------------------------------------------------
# 房间 3D 体块（RBRoom 的 ConvexElems 世界包围盒）
# ---------------------------------------------------------------------------
def extract_room_solids(folder):
    paths = sorted(glob.glob(os.path.join(folder, '*LD_Rooms.json')))
    out = []
    if not paths:
        return out
    for path in paths:
        rooms, comps, bodies = {}, {}, {}
        for idx, obj in mp.iter_objects(path):
            t = obj.get('Type')
            if t == 'RBRoom':
                rooms[obj.get('Name')] = obj
            elif t == 'BrushComponent':
                comps[idx] = obj
            elif t == 'BodySetup':
                bodies[idx] = obj
        for raw, actor in rooms.items():
            p = actor.get('Properties') or {}
            ci = mp.ref_index(p.get('BrushComponent'))
            comp = comps.get(ci)
            if not comp:
                continue
            cp = comp.get('Properties') or {}
            bi = mp.ref_index(cp.get('BrushBodySetup'))
            body = bodies.get(bi)
            if not body:
                continue
            loc = mp.vec(cp.get('RelativeLocation'))
            yaw = (cp.get('RelativeRotation') or {}).get('Yaw', 0.0) or 0.0
            elems = (((body.get('Properties') or {}).get('AggGeom') or {})
                     .get('ConvexElems') or [])
            boxes = []
            for ce in elems:
                pts = []
                for v in ce.get('VertexData') or []:
                    vx, vy, vz = mp.vec(v)
                    dx, dy = mp.yaw_rotate(vx, vy, yaw)
                    pts.append((loc[0] + dx, loc[1] + dy, loc[2] + vz))
                if len(pts) < 4:
                    continue
                boxes.append([
                    round(min(q[0] for q in pts), 1), round(min(q[1] for q in pts), 1),
                    round(min(q[2] for q in pts), 1), round(max(q[0] for q in pts), 1),
                    round(max(q[1] for q in pts), 1), round(max(q[2] for q in pts), 1),
                ])
            if boxes:
                out.append({'raw': raw, 'boxes': boxes})
    return out


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------
def build(level, map_override=None, paks=None, with_structures=True,
          max_structures=5000, verbose=True):
    lv = level.upper()
    db_path = os.path.join(mapdb.OUT_DIR, '%s.json' % lv)
    db = mapdb.load_json(db_path)
    if not db:
        raise SystemExit('找不到 2D 地图数据 %s，先跑 python mapdb.py %s' % (db_path, lv))
    map_name = map_override or db.get('map') or (mapdb.LEVELS.get(lv) or {}).get('map')
    if not map_name:
        raise SystemExit('data/levels.json 里没有 %s 的地图名，请用 --map 指定' % lv)
    root = paks or mapdb.MAPS_DIR
    folder = os.path.join(root, map_name)
    if not os.path.isdir(folder):
        raise SystemExit('找不到地图目录 %s（用 --paks 指定 paks/MAP/Maps）' % folder)

    def log(*a):
        if verbose:
            print(*a)

    log('扫描 %s ...' % folder)
    props, structs, stats = extract_meshes(
        folder, db, with_structures, max_structures, verbose)
    solids = extract_room_solids(folder)
    cats = Counter(p['cat'] for p in props)
    data = {
        'schema': SCHEMA,
        'level': lv,
        'map': map_name,
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': {'folder': folder, 'files': sorted(set(
            [p['file'] for p in props] + [s['file'] for s in structs]))},
        'bbox': db.get('bbox'),
        'zrange': db.get('zrange'),
        'props': props,
        'structures': structs,
        'solids': solids,
        'stats': {
            'props': len(props), 'structures': len(structs),
            'solids': sum(len(s['boxes']) for s in solids),
            'rooms_with_solids': len(solids),
            'by_cat': dict(cats.most_common()),
            'scan': {k: v for k, v in stats.items() if ':' not in k},
        },
    }
    return data


def check_file(level, out_dir=OUT_DIR, verbose=True):
    path = os.path.join(out_dir, '%s.json' % level.upper())
    data = mapdb.load_json(path)
    if not data:
        print('  ! 没有 %s（跑 python map3d.py %s 生成）' % (path, level.upper()))
        return 1
    s = data.get('stats') or {}
    print('%s  3D 数据自检  %s  (%.0f KB)' % (
        level.upper(), path, os.path.getsize(path) / 1024.0))
    print('  生成 %s   来源 %s' % (data.get('generated'), data.get('map')))
    print('  道具 %d   结构 %d   房间体块 %d / %d 房间' % (
        len(data.get('props') or []), len(data.get('structures') or []),
        s.get('solids', 0), s.get('rooms_with_solids', 0)))
    print('  类别 %s' % (s.get('by_cat') or {}))
    print('  扫描 %s' % (s.get('scan') or {}))
    problems = []
    if not data.get('props'):
        problems.append('没有任何道具（检查 paks 路径 / 类别规则）')
    if not data.get('solids'):
        problems.append('没有房间体块（检查 *LD_Rooms.json）')
    for p in (data.get('props') or [])[:1]:
        if not p.get('size') or min(p['size']) <= 0:
            problems.append('道具尺寸异常')
    print('  结论  %s' % (('; '.join(problems)) if problems else '通过'))
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='从 paks 提取 3D 地图几何')
    ap.add_argument('levels', nargs='*', help='关卡号，如 CHJ_MT02')
    ap.add_argument('--all', action='store_true', help='所有已有 2D 数据的关卡')
    ap.add_argument('--check', action='store_true', help='自检已生成的 3D 数据')
    ap.add_argument('--paks', help='paks/MAP/Maps 目录')
    ap.add_argument('--map', help='手动指定地图目录名')
    ap.add_argument('--out-dir', default=OUT_DIR, help='输出目录')
    ap.add_argument('--no-structures', action='store_true', help='不提取结构墙体')
    ap.add_argument('--max-structures', type=int, default=5000)
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    levels = [x.upper() for x in args.levels]
    if args.all or not levels:
        levels = sorted(os.path.splitext(f)[0].upper() for f in os.listdir(mapdb.OUT_DIR)
                        if f.endswith('.json'))
    if args.check:
        return sum(check_file(lv, args.out_dir) for lv in levels)

    rc = 0
    cache = {}          # 同一张地图只扫一次 paks，多个关卡共用同一份几何
    for lv in levels:
        try:
            db = mapdb.load_json(os.path.join(mapdb.OUT_DIR, '%s.json' % lv)) or {}
            key = (args.map or db.get('map') or
                   (mapdb.LEVELS.get(lv) or {}).get('map'),
                   not args.no_structures, args.max_structures)
            if key in cache:
                data = dict(cache[key])
                data['level'] = lv
            else:
                data = build(lv, args.map, args.paks, not args.no_structures,
                             args.max_structures, not args.quiet)
                cache[key] = data
            out = os.path.join(args.out_dir, '%s.json' % lv)
            mapdb.save_json(out, data)
            print('%s -> %s  props=%d structures=%d solids=%d' % (
                lv, out, len(data['props']), len(data['structures']),
                data['stats']['solids']))
        except SystemExit as e:
            print('%s  ! %s' % (lv, e))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
