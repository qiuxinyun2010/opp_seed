#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""map3d.py — 从关卡 JSON + 资产包提取「粗略 3D 几何」，供 Web 版 3D 模式使用。

与 mapdb.py 的关系
------------------
mapdb.py 把 UE 房间 Brush 的 3D 凸包投影成 2D 多边形（只留 zmin/zmax），
本脚本回到原始数据，补回 3D 模式下需要的东西：

  * props[]      从 *_LA_*.json / *_ART*.json 的 StaticMeshComponent 提取家具/道具
                 实例。尺寸优先取资产包里的实测包围盒，取不到才按网格名猜。
  * structures[] 同一批实例里的墙体/窗墙等结构网格，单独一层，默认不显示。
  * solids[]     *LD_Rooms.json 里每个 RBRoom 的 ConvexElems 世界包围盒。
  * shapes[]     任务道具的真实形状：沿蓝图继承链找到 StaticMesh/SkeletalMesh
                 资产，读 AggGeom 凸包 + ExtendedBounds/ImportedBounds，按实测
                 比例补盖沿/标签/封条（PSB_MT03 的档案箱就是这么来的）。
  * point_instances[]  每个任务点位 → 形状 + 位置 + yaw，前端据此画实体。
  * openings[]     *_ART*.json 里带窗/门洞的 Modules 墙板实例，用资产的全部
                   碰撞凸包还原真实洞口（窗框、过梁、下墙裙之间的空白）。
  * open_shapes[] / open_instances[]  与任务道具同构的「一种形状 + 一堆实例」。
  * reachable[]   本关可达区域：读 <LEVEL>_B00.json 的 RBRoomGroup.Rooms[] 得到
                   房间白名单，据此过滤不可达的房间/门/楼梯/点位，并给 3D 项打
                   reach 标记。没有 RoomGroup 的关卡返回 enabled=False，前端不过滤。

门 / 楼梯 / 点位 / 楼层不重复提取，直接复用 data/maps/<LEVEL>.json。

数据目录
--------
    paks/MAP/Maps 或 pak/OPP/Content/Maps_json   --paks    关卡布局 JSON
    pak/OPP/Content（MapSet / LD / Props / Modules） --content 资产本体（可选）
                                                 也可用 OUTLAST_CONTENT_DIR

用法
----
    python map3d.py PSB_MT03 --paks ../../pak/OPP/Content/Maps_json
    python map3d.py CHJ_MT02 --check            # 自检已生成的 JSON
    python map3d.py --all                       # data/levels.json 里有 2D 数据的关卡

输出：data/3d/<LEVEL>.json（纯文本，可随 ui/ 一起交付）
"""
from __future__ import print_function

import argparse
import datetime
import glob
import math
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import mapdb                                    # noqa: E402  配置 / 路径 / IO
from maplib import extract as mp               # noqa: E402  流式解析与坐标原语
from maplib import assetgeom                   # noqa: E402  资产凸包 / 实测包围盒


def _find_content_dir():
    """资产包 pak/OPP/Content 的位置（环境变量 > 仓库根 > ui 内）。"""
    for cand in (os.environ.get('OUTLAST_CONTENT_DIR'),
                 os.path.join(mapdb.ROOT, 'pak', 'OPP', 'Content'),
                 os.path.join(HERE, 'pak', 'OPP', 'Content')):
        if cand and os.path.isdir(cand):
            return os.path.abspath(cand)
    return None


SCHEMA = 3          # 3 起带 open_shapes / open_instances / reachable
OUT_DIR = os.path.join(HERE, 'data', '3d')
CONTENT_DIR = _find_content_dir()

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

# 带门/窗洞的 Modules 墙板与框架：这些网格的碰撞体是「上梁 + 下墙裙 + 左右立板」
# 等多个体块，中间的空白就是洞。名字来自 *_ART*.json 里的 StaticMesh 引用。
OPENING_RULES = re.compile(
    r'wallframe|wallplank(?:2)?(?:door|windows)|wallplankwindows|'
    r'murkoffwallpartition(?:200)?_window|murkoffdoorframe|'
    r'wall.*windows|windows_|windowshowcase|windowsgrate|window_?\d|'
    r'doorframe|frame.*door|opening\d|ps_window|basementwindows|'
    r'fakebuildingwindow|fakewallbottomdoorframe|wallwindow', re.I)
# 只是门扇 / 家具门 / 栅栏门 / 碰撞体 / 纯玻璃，不是墙体开口
OPENING_SKIP = re.compile(
    r'collision|stud|blocking|fence|glass|locker|fridge|washingmachine|'
    r'carfront|counter|toilet|slidingdoor|trapdoor|commercial|kiosk|stall|'
    r'labfloor|\bsign\b|blueprint', re.I)


def opening_color(mesh):
    low = mesh.lower()
    if 'window' in low or 'grate' in low:
        return '#7fb2d9'
    if 'opening' in low or 'breach' in low:
        return '#cbd5e1'
    if 'door' in low or 'frame' in low:
        return '#c2aa86'
    return '#aab4bf'


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


def extract_meshes(folder, db, with_structures=True, max_structures=5000,
                   with_art=True, max_props=12000, asset_idx=None,
                   opening_out=None, verbose=False):
    """返回 (props, structures, stats)。坐标是世界坐标 uu，未做镜像。

    asset_idx 给定时，道具尺寸改用资产包里的实测包围盒（ExtendedBounds /
    ImportedBounds），而不是 classify() 的经验值；命中情况记在 size_src。
    """
    bbox = db.get('bbox') or [-1e6, -1e6, 1e6, 1e6]
    zrange = db.get('zrange') or [-1e6, 1e6]
    x0, y0, x1, y1 = bbox
    z0, z1 = zrange
    margin = 600.0

    props, structs = [], []
    seen = set()
    stats = Counter()
    tags = ('_LA_', '_ART') if with_art else ('_LA_',)
    files = [f for f in sorted(os.listdir(folder))
             if f.endswith('.json') and 'BuiltData' not in f
             and 'VisibilityData' not in f and any(t in f for t in tags)]
    for fn in files:
        comps = scan_components(os.path.join(folder, fn), verbose)
        stats['components'] += len(comps)
        for idx, c in comps.items():
            mesh = c['mesh']
            if not mesh:
                continue
            stats['meshes'] += 1
            # 带门窗洞的墙板被 STRUCT_SKIP 排除在家具之外，这里单独收集
            if (opening_out is not None and len(opening_out) < 2000 and
                    OPENING_RULES.search(mesh) and not OPENING_SKIP.search(mesh)):
                oloc, oyaw, oscale = world_transform(comps, idx)
                if (abs(oloc[0]) + abs(oloc[1]) + abs(oloc[2]) > 1 and
                        x0 - margin <= oloc[0] <= x1 + margin and
                        y0 - margin <= oloc[1] <= y1 + margin and
                        z0 - 500 <= oloc[2] <= z1 + 250):
                    opening_out.append({
                        'mesh': mesh, 'p': [round(v, 1) for v in oloc],
                        'yaw': round(oyaw, 1),
                        'scale': [round(clamp(abs(v), 0.1, 8), 3)
                                  for v in oscale],
                    })
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
            size_src = 'guess'
            if is_struct:
                size = struct_size(mesh, (sx, sy, sz))
                cat = 'wall'
            else:
                cat, base = cat_size
                measured = asset_idx.mesh_size(mesh) if asset_idx else None
                if measured:
                    size = [measured[0] * sx, measured[1] * sy, measured[2] * sz]
                    size_src = 'asset'
                    stats['measured'] += 1
                else:
                    size = limit_size(cat, [base[0] * sx, base[1] * sy, base[2] * sz])
            row = {
                'p': [round(x, 1), round(y, 1), round(z, 1)],
                'yaw': round(yaw, 1),
                'size': [round(v, 1) for v in size],
                'cat': cat,
                'mesh': mesh,
                'file': fn,
                'size_src': size_src,
            }
            (structs if is_struct else props).append(row)
            stats[('struct' if is_struct else 'prop') + ':' + cat] += 1
        if len(props) >= max_props:
            stats['capped'] += 1
            break
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
# 本关可达区域：<LEVEL>_B00.json 的 RBRoomGroup.Rooms[]
# ---------------------------------------------------------------------------
ROOM_GROUP_FILE = re.compile(r'_(?:MT\d{2}|T\d{2}_B\d{2})_B\d{2}\.json$', re.I)


def room_whitelist(folder, level):
    """RBRoomGroup 是引擎实际使用的区域单位，Rooms[] 就是本关的房间白名单。

    比 maplib.extract.room_trial_tags() 可靠：后者只是「文本里提到过」，
    三关共用的 37 间房全都会被算进每一关，无法区分本关开放/关闭。
    """
    m = re.search(r'(MT\d{2}|T\d{2}_B\d{2}|B\d{2})$', level.upper())
    tag = (m.group(1) if m else '').lower()
    names, srcs = set(), []
    for path in sorted(glob.glob(os.path.join(folder, '*.json'))):
        base = os.path.basename(path)
        if 'BuiltData' in base or not ROOM_GROUP_FILE.search(base):
            continue
        if tag and tag not in base.lower():
            continue
        data = mapdb.load_json(path) or []
        if not isinstance(data, list):
            continue
        groups = [o for o in data if o.get('Type') == 'RBRoomGroup']
        if not groups:
            continue
        srcs.append(base)
        for g in groups:
            for ref in (g.get('Properties') or {}).get('Rooms') or []:
                raw = (ref.get('SubPathString') or '').split('.')[-1]
                if raw.startswith('RBRoom'):
                    names.add(raw)
    return names, srcs


def build_areas(rooms):
    """房间 hull 展开成 (多边形, z0, z1, bbox...) 供快速点判定。"""
    areas = []
    for r in rooms:
        z = r.get('z') or [0, 400]
        for hull in r.get('hulls') or []:
            if len(hull) < 3:
                continue
            xs = [v[0] for v in hull]
            ys = [v[1] for v in hull]
            areas.append((hull, z[0], z[1], min(xs), min(ys), max(xs), max(ys)))
    return areas


def _point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i][0], poly[i][1]
        bx, by = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        if (ay > y) != (by > y) and x < ax + (y - ay) * (bx - ax) / (by - ay or 1e-9):
            inside = not inside
    return inside


def _dist_to_poly(x, y, poly):
    best = 1e18
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i][0], poly[i][1]
        bx, by = poly[(i + 1) % n][0], poly[(i + 1) % n][1]
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) /
                         max(1e-9, dx * dx + dy * dy)))
        best = min(best, math.hypot(x - ax - t * dx, y - ay - t * dy))
    return best


def in_kept_area(p, areas, tol=180.0):
    """点落在保留房间内（门/楼梯允许贴边 tol cm），并做 z 容差。"""
    if not p:
        return False
    x, y, z = p[0], p[1], p[2]
    for poly, z0, z1, ax0, ay0, ax1, ay1 in areas:
        if x < ax0 - tol or x > ax1 + tol or y < ay0 - tol or y > ay1 + tol:
            continue
        if not (z0 - 250 <= z <= z1 + 250):
            continue
        if _point_in_poly(x, y, poly) or _dist_to_poly(x, y, poly) <= tol:
            return True
    return False


def compute_reachable(folder, level, db):
    """返回 (reachable 描述, 保留区域)。找不到 RoomGroup 时 enabled=False。"""
    names, srcs = room_whitelist(folder, level)
    if not names:
        return {'enabled': False, 'source': None}, []
    rooms = db.get('rooms') or []
    points_all = db.get('points') or []
    # 任务点位永远保留；RoomGroup 白名单偶尔会漏掉入口/出口区（那里也有点位），
    # 把这些房间补回可达区，避免点位悬在没有地板的空白处。
    point_rooms = {p.get('room') for p in points_all
                   if p.get('room') is not None}
    keep = [r for r in rooms
            if r.get('raw') in names or r.get('id') in point_rooms]
    if not keep:
        return {'enabled': False, 'source': ', '.join(srcs)}, []
    keep_ids = set(r.get('id') for r in keep)
    areas = build_areas(keep)
    doors_all = db.get('doors') or []
    stairs_all = db.get('stairs') or []
    door_ids = [d['id'] for d in doors_all
                if in_kept_area(d.get('p'), areas)]
    stair_ids = []
    for s in stairs_all:
        a, b = s.get('a'), s.get('b')
        mid = ([(a[i] + b[i]) / 2.0 for i in range(3)] if a and b else a or b)
        if in_kept_area(mid, areas, 240.0):
            stair_ids.append(s['id'])
    point_ids = [p['id'] for p in points_all]   # 任务点位一个都不能少
    out = {
        'enabled': True,
        'source': ', '.join(srcs) + ' / RBRoomGroup.Rooms[]',
        'room_ids': sorted(keep_ids),
        'room_raws': sorted(names),
        'door_ids': door_ids,
        'stair_ids': stair_ids,
        'point_ids': point_ids,
        'excluded': {
            'rooms': len(rooms) - len(keep),
            'doors': len(doors_all) - len(door_ids),
            'stairs': len(stairs_all) - len(stair_ids),
            'points': len(points_all) - len(point_ids),
        },
    }
    return out, areas


def mark_reach(items, areas):
    """给 3D 项打 reach 标记：前端可按「仅可达区域」开关过滤。"""
    for it in items:
        it['reach'] = 1 if in_kept_area(it.get('p'), areas) else 0
    return sum(1 for it in items if not it['reach'])


def mark_reach_solids(solids, names):
    for s in solids:
        s['reach'] = 1 if s.get('raw') in names else 0


# ---------------------------------------------------------------------------
# 窗 / 门洞：Modules 墙板的全部碰撞体
# ---------------------------------------------------------------------------
def build_open_shapes(rows, idx, verbose=False):
    """按网格分组，把带洞墙板解析成 open_shapes / open_instances。"""
    by_mesh = {}
    for r in rows:
        by_mesh.setdefault(r['mesh'], []).append(r)
    shapes, insts, missing = [], [], 0
    for mesh in sorted(by_mesh):
        path = idx.find(mesh, '/Modules/') or idx.find(mesh, '/Props/')
        geom = assetgeom.read_parts(path) if path else None
        if not geom or not geom['parts']:
            missing += 1
            continue
        color = opening_color(mesh)
        shapes.append({
            'id': mesh, 'name': mesh, 'asset': mapdb.rel(path),
            'size': geom['size'],
            'parts': [{'name': 'wall%d' % i, 'color': color,
                       'verts': [[round(v, 2) for v in xyz]
                                 for xyz in p['verts']],
                       'tris': p['tris']}
                      for i, p in enumerate(geom['parts'])],
        })
        for r in by_mesh[mesh]:
            insts.append({'shape': mesh, 'p': r['p'],
                          'yaw': r['yaw'], 'scale': r['scale']})
    if verbose:
        print('  - 门窗洞 %d 种网格 / %d 个实例（%d 种无碰撞几何）' % (
            len(shapes), len(insts), missing))
    return shapes, insts, {'kinds': len(by_mesh), 'shapes': len(shapes),
                           'instances': len(insts), 'no_geom': missing}


# ---------------------------------------------------------------------------
# 任务点位 → 真实道具形状（资产包 /Content/MapSet 等）
# ---------------------------------------------------------------------------
def load_point_meta(map_name, level):
    """点位缓存里有 mapdb 没写进 maps/<LEVEL>.json 的 type / yaw。"""
    path = os.path.join(mapdb.CACHE_DIR, '%s.points.%s.json' % (map_name, level))
    data = mapdb.load_json(path) or {}
    return {p['actor']: p for p in (data.get('points') or []) if p.get('actor')}


def _point_type(p, meta):
    m = meta.get(p.get('actor')) or {}
    return m.get('type') or re.sub(r'_\d+$', '', p.get('actor') or '')


def build_point_shapes(db, meta, idx, verbose=False):
    """返回 (shapes, instances, stats)。找不到资产的关卡返回空，前端退回标记。"""
    types = {}
    for p in db.get('points') or []:
        t = _point_type(p, meta)
        types.setdefault(t, {
            'label': p.get('label_zh') or p.get('label') or t,
            'key': p.get('key') or '',
        })
    shapes, by_type = [], {}
    for t, info in sorted(types.items()):
        sh = assetgeom.resolve_shape(t, idx, label=info['label'],
                                     key=info['key'], verbose=verbose)
        if sh:
            shapes.append(sh)
            by_type[t] = sh['id']
    insts = []
    missing_yaw = 0
    for p in db.get('points') or []:
        sid = by_type.get(_point_type(p, meta))
        if not sid:
            continue
        m = meta.get(p.get('actor')) or {}
        yaw = m.get('yaw')
        if yaw is None:
            missing_yaw += 1
        insts.append({
            'id': p.get('id'), 'shape': sid, 'p': p.get('p'),
            'yaw': round(float(yaw or 0), 1),
            'color': p.get('color') or m.get('color') or '',
            'actor': p.get('actor'), 'key': p.get('key'),
        })
    return shapes, insts, {
        'types': len(types), 'shapes': len(shapes),
        'instances': len(insts), 'missing_yaw': missing_yaw,
    }


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------
def level_overlays(folder, lv, map_name, db, idx, no_shapes, no_reachable, verbose):
    """按关卡重算的叠加层：任务道具形状 + 本关可达区域（几何可跨关卡共用）。"""
    shapes, insts, shape_stats = [], [], {}
    if idx and not no_shapes:
        shapes, insts, shape_stats = build_point_shapes(
            db, load_point_meta(map_name, lv), idx, verbose)
    reach, areas = {'enabled': False, 'source': None}, []
    if not no_reachable:
        reach, areas = compute_reachable(folder, lv, db)
    return shapes, insts, shape_stats, reach, areas


def apply_reach(data, reach, areas):
    """给所有 3D 项打 reach 标记；没有 RoomGroup 的关卡一律标 1（不过滤）。"""
    groups = ('props', 'structures', 'open_instances', 'point_instances')
    if not reach.get('enabled'):
        for key in groups:
            for it in data.get(key) or []:
                it['reach'] = 1
        for s in data.get('solids') or []:
            s['reach'] = 1
        return {}
    out = {}
    for key in ('props', 'structures', 'open_instances'):
        out[key] = mark_reach(data.get(key) or [], areas)
    pids = set(reach.get('point_ids') or [])
    out['point_instances'] = 0
    for it in data.get('point_instances') or []:
        it['reach'] = 1 if it.get('id') in pids else 0
        out['point_instances'] += 1 - it['reach']
    mark_reach_solids(data.get('solids') or [], set(reach.get('room_raws') or []))
    out['solids'] = sum(1 for s in data.get('solids') or [] if not s['reach'])
    return out


def build(level, map_override=None, paks=None, content=None, with_structures=True,
          max_structures=5000, with_art=True, max_props=12000, asset_sizes=True,
          no_shapes=False, no_openings=False, max_openings=1200,
          no_reachable=False, asset_index=None, verbose=True):
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
    idx = asset_index
    if idx is None and (asset_sizes or not no_shapes):
        idx = assetgeom.AssetIndex(content or CONTENT_DIR)
    if idx is not None and not idx.ok:
        log('  ! 找不到资产包（--content / OUTLAST_CONTENT_DIR），'
            '道具尺寸用经验值、任务点位不生成形状')
        idx = None
    if idx is not None:
        log('资产包 %s' % idx.root)
    opening_rows = [] if (idx and not no_openings) else None
    props, structs, stats = extract_meshes(
        folder, db, with_structures, max_structures, with_art, max_props,
        idx if asset_sizes else None, opening_out=opening_rows, verbose=verbose)
    solids = extract_room_solids(folder)
    open_shapes, open_insts, open_stats = [], [], {}
    if opening_rows and idx:
        open_shapes, open_insts, open_stats = build_open_shapes(
            opening_rows, idx, verbose)
        if max_openings and len(open_insts) > max_openings:
            open_insts = open_insts[:max_openings]
    shapes, insts, shape_stats, reach, areas = level_overlays(
        folder, lv, map_name, db, idx, no_shapes, no_reachable, verbose)
    cats = Counter(p['cat'] for p in props)
    data = {
        'schema': SCHEMA,
        'level': lv,
        'map': map_name,
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'source': {'folder': folder, 'files': sorted(set(
            [p['file'] for p in props] + [s['file'] for s in structs])),
            'content': mapdb.rel(idx.root) if idx else None},
        'bbox': db.get('bbox'),
        'zrange': db.get('zrange'),
        'props': props,
        'structures': structs,
        'solids': solids,
        'open_shapes': open_shapes,
        'open_instances': open_insts,
        'shapes': shapes,
        'point_instances': insts,
        'reachable': reach,
        'stats': {
            'props': len(props), 'structures': len(structs),
            'solids': sum(len(s['boxes']) for s in solids),
            'rooms_with_solids': len(solids),
            'measured_props': stats.get('measured', 0),
            'shapes': len(shapes), 'point_instances': len(insts),
            'shape_scan': shape_stats,
            'open_shapes': len(open_shapes),
            'open_instances': len(open_insts),
            'opening_scan': open_stats,
            'reachable': reach.get('enabled', False),
            'by_cat': dict(cats.most_common()),
            'scan': {k: v for k, v in stats.items() if ':' not in k},
        },
    }
    data['stats']['outside_reachable'] = apply_reach(data, reach, areas)
    return data


def refresh_reachable(level, out_dir=OUT_DIR, paks=None, map_override=None):
    """只重算 reachable + reach 标记，不重扫几何（可批量刷新旧数据）。"""
    lv = level.upper()
    db = mapdb.load_json(os.path.join(mapdb.OUT_DIR, '%s.json' % lv)) or {}
    path = os.path.join(out_dir, '%s.json' % lv)
    data = mapdb.load_json(path)
    if not db or not data:
        raise SystemExit('缺少 2D 或 3D 数据：%s' % lv)
    map_name = map_override or data.get('map') or db.get('map')
    folder = os.path.join(paks or mapdb.MAPS_DIR, map_name)
    reach, areas = compute_reachable(folder, lv, db)
    data['reachable'] = reach
    data['schema'] = SCHEMA
    stats = data.setdefault('stats', {})
    stats['reachable'] = reach.get('enabled', False)
    stats['outside_reachable'] = apply_reach(data, reach, areas)
    mapdb.save_json(path, data)
    return reach


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
    shapes = data.get('shapes') or []
    print('  形状 %d 种   点位实例 %d   资产实测道具 %d' % (
        len(shapes), len(data.get('point_instances') or []),
        s.get('measured_props', 0)))
    for sh in shapes:
        print('    %s -> %s  实测 %s cm  资产 %s' % (
            sh.get('name'), sh.get('mesh'),
            'x'.join(str(v) for v in sh.get('size') or []), sh.get('asset')))
    print('  形状解析 %s' % (s.get('shape_scan') or {}))
    print('  门窗洞 %d 种 / %d 实例   %s' % (
        len(data.get('open_shapes') or []), len(data.get('open_instances') or []),
        s.get('opening_scan') or {}))
    reach = data.get('reachable') or {}
    if reach.get('enabled'):
        print('  可达区域  %s' % reach.get('source'))
        print('    保留 房间 %d / 门 %d / 楼梯 %d / 点位 %d   排除 %s' % (
            len(reach.get('room_ids') or []), len(reach.get('door_ids') or []),
            len(reach.get('stair_ids') or []), len(reach.get('point_ids') or []),
            reach.get('excluded') or {}))
    else:
        print('  可达区域  未启用（没有 RBRoomGroup，显示全图）')
    print('  不可达 3D 项 %s' % (s.get('outside_reachable') or {}))
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
    ap.add_argument('--paks', help='关卡 JSON 目录（paks/MAP/Maps 或 Maps_json）')
    ap.add_argument('--content', help='资产包目录（pak/OPP/Content）')
    ap.add_argument('--map', help='手动指定地图目录名')
    ap.add_argument('--out-dir', default=OUT_DIR, help='输出目录')
    ap.add_argument('--no-structures', action='store_true', help='不提取结构墙体')
    ap.add_argument('--max-structures', type=int, default=5000)
    ap.add_argument('--no-art', action='store_true', help='不扫 *_ART*.json 家具层')
    ap.add_argument('--max-props', type=int, default=12000, help='道具数量上限')
    ap.add_argument('--no-shapes', action='store_true', help='不解析任务点位形状')
    ap.add_argument('--no-openings', action='store_true',
                    help='不解析 Modules 墙板的门/窗洞')
    ap.add_argument('--max-openings', type=int, default=1200,
                    help='门窗洞实例数量上限')
    ap.add_argument('--no-reachable', action='store_true',
                    help='不按 RBRoomGroup 过滤不可达区域（显示全图）')
    ap.add_argument('--reachable-only', action='store_true',
                    help='只重算可达区域，不重扫几何（可配合 --all 批量刷新）')
    ap.add_argument('--no-asset-sizes', action='store_true',
                    help='道具尺寸不用资产实测值（退回按名字猜）')
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    levels = [x.upper() for x in args.levels]
    if args.all or not levels:
        levels = sorted(os.path.splitext(f)[0].upper() for f in os.listdir(mapdb.OUT_DIR)
                        if f.endswith('.json'))
    if args.check:
        return sum(check_file(lv, args.out_dir) for lv in levels)
    if args.reachable_only:
        rc = 0
        done = 0
        for lv in levels:
            # 没有 3D 数据的关卡不需要刷新（视图里本来就没有这些层）
            if not os.path.isfile(os.path.join(args.out_dir, '%s.json' % lv)):
                continue
            try:
                r = refresh_reachable(lv, args.out_dir, args.paks, args.map)
                done += 1
                print('%s  可达区域 %s' % (
                    lv, ('启用，排除 ' + str(r.get('excluded')))
                    if r.get('enabled') else '未找到 RBRoomGroup（显示全图）'))
            except SystemExit as e:
                print('%s  ! %s' % (lv, e))
                rc = 1
        print('已刷新 %d 个 3D 数据文件' % done)
        return rc

    idx = None
    if not args.no_asset_sizes or not args.no_shapes or not args.no_openings:
        idx = assetgeom.AssetIndex(args.content or CONTENT_DIR)
        if not idx.ok:
            if not args.quiet:
                print('! 找不到资产包（--content / OUTLAST_CONTENT_DIR）：%s'
                      % (args.content or CONTENT_DIR))
            idx = None

    rc = 0
    cache = {}          # 同一张地图只扫一次关卡 JSON，多个关卡共用同一份几何
    for lv in levels:
        try:
            db = mapdb.load_json(os.path.join(mapdb.OUT_DIR, '%s.json' % lv)) or {}
            map_name = (args.map or db.get('map') or
                        (mapdb.LEVELS.get(lv) or {}).get('map'))
            key = (map_name, args.paks, not args.no_structures,
                   args.max_structures, not args.no_art, args.max_props,
                   not args.no_asset_sizes, not args.no_openings,
                   args.max_openings)
            if key in cache:
                data = dict(cache[key])
                data['level'] = lv
                data['stats'] = dict(data['stats'])
                # 点位形状 / 可达区域都按关卡重算，静态几何只扫一次
                sh, ins, sst, reach, areas = level_overlays(
                    data['source']['folder'], lv, map_name, db, idx,
                    args.no_shapes, args.no_reachable, not args.quiet)
                data['shapes'] = sh
                data['point_instances'] = ins
                data['reachable'] = reach
                data['stats'].update({'shapes': len(sh),
                                      'point_instances': len(ins),
                                      'shape_scan': sst,
                                      'reachable': reach.get('enabled', False)})
                data['stats']['outside_reachable'] = apply_reach(data, reach, areas)
            else:
                data = build(
                    lv, map_override=args.map, paks=args.paks,
                    content=args.content,
                    with_structures=not args.no_structures,
                    max_structures=args.max_structures,
                    with_art=not args.no_art, max_props=args.max_props,
                    asset_sizes=not args.no_asset_sizes,
                    no_shapes=args.no_shapes,
                    no_openings=args.no_openings,
                    max_openings=args.max_openings,
                    no_reachable=args.no_reachable,
                    asset_index=idx, verbose=not args.quiet)
                cache[key] = data
            out = os.path.join(args.out_dir, '%s.json' % lv)
            mapdb.save_json(out, data)
            print('%s -> %s  props=%d openings=%d shapes=%d points=%d reachable=%s' % (
                lv, out, len(data['props']),
                len(data.get('open_instances') or []),
                len(data.get('shapes') or []),
                len(data.get('point_instances') or []),
                (data.get('reachable') or {}).get('enabled', False)))
        except SystemExit as e:
            print('%s  ! %s' % (lv, e))
            rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
