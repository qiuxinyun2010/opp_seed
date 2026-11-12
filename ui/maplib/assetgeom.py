# -*- coding: utf-8 -*-
"""assetgeom.py — 读 pak/OPP/Content 里 FModel 导出的资产，补回真实几何尺寸。

map3d.py 以前只能按网格名猜尺寸：关卡 JSON 里只有 `StaticMesh'xxx'` 引用，
资产本体（/Content/MapSet、/Content/LD、/Content/Props）不在导出里。
补上这些包之后，资产 JSON 里有两种可用信息：

  * BodySetup.AggGeom.ConvexElems[].VertexData / IndexData
        —— 真实简化碰撞凸包（8 顶点 / 12 三角面这种量级），可当低模形状画。
  * StaticMesh.ExtendedBounds / SkeletalMesh.ImportedBounds
        —— 实测包围盒（Origin + BoxExtent），单位 cm，直接就是道具尺寸。

渲染顶点（RenderData / LODModels）在导出里全是 null，所以本模块最多还原到
「凸包 + 实测包围盒」，没有箱盖开合、UV、贴图细节；装饰件是按包围盒比例
程序化补的（盖沿 / 标签 / 封条），只为在 3D 里一眼认出是档案箱。

用法：
    idx = AssetIndex(r'D:\\workspace\\outlast\\pak\\OPP\\Content')
    shape = resolve_shape('PrivateFilesBox-01_BP_C', idx, label='箱子', key='box')
    size = idx.mesh_size("StaticMesh'FileBox-01'")     # -> [27.6, 27.9, 24.4]
"""
from __future__ import print_function

import io
import json
import os
import re

from . import extract as mp

NUMERIC = re.compile(r'^\d+$')
BIG_JSON = 8 * 1024 * 1024

# 程序化装饰件配色：比场景里按经验值画的普通箱子更亮，便于一眼认出任务道具
C_BODY = '#96663a'
C_LID = '#d8ad6a'
C_LABEL = '#fff4d6'
C_TAPE = '#4a3520'
C_MARK = '#3b82f6'      # 点位底座框（与 2D 点位色系呼应）
C_GENERIC = '#9aa3af'


# ---------------------------------------------------------------------------
# 路径 / 名字
# ---------------------------------------------------------------------------
def _num(s):
    return bool(NUMERIC.match(str(s or '')))


def objpath_to_file(object_path, root):
    """`OPP/Content/MapSet/Mansion/Mesh/FileBox-01.2` -> <root>/.../FileBox-01.json"""
    if not object_path or not root:
        return None
    s = str(object_path).replace('\\', '/')
    base, _, tail = s.rpartition('.')
    if not _num(tail):
        base, tail = s, ''
    for prefix in ('OPP/Content/', '/Game/', 'Game/'):
        if base.startswith(prefix):
            rel = base[len(prefix):]
            break
    else:
        return None
    path = os.path.join(root, *rel.split('/')) + '.json'
    return path if os.path.isfile(path) else None


def _name_keys(name):
    """`StaticMesh'/Game/Props/SM_Box.SM_Box'` -> ['sm_box', ...] 候选小写名。"""
    s = str(name or '').strip()
    m = re.match(r"^[A-Za-z0-9_]+'(.*)'$", s)
    if m:
        s = m.group(1)
    s = s.replace('\\', '/').split('/')[-1]
    head, _, tail = s.rpartition('.')
    parts = [head, tail] if head and _num(tail) else [s]
    if s.endswith('.0') or ('.' in s and not _num(s.rsplit('.', 1)[1])):
        parts += [s.rsplit('.', 1)[0], s.rsplit('.', 1)[-1]]
    keys = []
    for p in parts + [s]:
        p = p.lower()
        if p and p not in keys:
            keys.append(p)
    for p in list(keys):
        if p.endswith('_sm') and p[:-3] not in keys:
            keys.append(p[:-3])
    return keys


def _blueprint_stem(type_name):
    """`PrivateFilesBox-01_BP_C` -> `PrivateFilesBox-01_BP`。"""
    return re.sub(r'_C$', '', str(type_name or '').strip())


def load_objects(path):
    """资产 JSON 是顶层数组；大的用 maplib 的流式解析。"""
    if not path or not os.path.isfile(path):
        return []
    try:
        if os.path.getsize(path) > BIG_JSON:
            return [o for _, o in mp.iter_objects(path)]
        with io.open(path, encoding='utf-8') as fp:
            data = json.load(fp)
        return data if isinstance(data, list) else [data]
    except (ValueError, IOError, OSError) as e:
        print('  ! 资产 JSON 解析失败 %s: %s' % (path, e))
        return []


# ---------------------------------------------------------------------------
# 索引
# ---------------------------------------------------------------------------
class AssetIndex(object):
    """按文件名索引 /Content 下的 json；只在真的要找资产时扫一次目录。"""

    def __init__(self, root):
        self.root = os.path.abspath(root) if root else None
        self._names = None
        self._geom = {}

    @property
    def ok(self):
        return bool(self.root and os.path.isdir(self.root))

    def _scan(self):
        self._names = {}
        if not self.ok:
            return
        for dirpath, _dirs, files in os.walk(self.root):
            for fn in files:
                if fn.endswith('.json'):
                    key = os.path.splitext(fn)[0].lower()
                    self._names.setdefault(key, []).append(os.path.join(dirpath, fn))

    def find(self, name, prefer=None):
        """按资产名找 json；prefer 是路径片段（如 '/Mesh/'），用于消歧。"""
        if self._names is None:
            self._scan()
        for key in _name_keys(name):
            hits = self._names.get(key) or []
            if not hits:
                continue
            if prefer:
                hits = sorted(hits, key=lambda p: 0 if prefer in p.replace('\\', '/') else 1)
            return hits[0]
        return None

    def geometry(self, path):
        if not path:
            return None
        if path not in self._geom:
            self._geom[path] = read_geometry(path)
        return self._geom[path]

    def mesh_size(self, name, prefer='/Mesh/'):
        """返回资产实测 [宽, 深, 高]（cm），找不到 / 不合理则 None。"""
        g = self.geometry(self.find(name, prefer))
        if not g or not g.get('size'):
            return None
        w, d, h = g['size']
        if min(w, d, h) < 1 or max(w, d, h) > 2000:
            return None
        return [round(v, 1) for v in (w, d, h)]


def _bbox(verts):
    mn = [min(v[i] for v in verts) for i in range(3)]
    mx = [max(v[i] for v in verts) for i in range(3)]
    return mn, mx


def box_part(bmin, bmax, color, name='part'):
    """轴对齐盒 -> 8 顶点 / 12 三角面。"""
    x0, y0, z0 = bmin
    x1, y1, z1 = bmax
    verts = [[x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
             [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]]
    tris = [[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7],
            [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
            [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]]
    return {'name': name, 'color': color, 'verts': verts, 'tris': tris}


def read_geometry(path):
    """读一个 StaticMesh / SkeletalMesh 资产的凸包与实测包围盒。"""
    out = {'path': path, 'verts': [], 'tris': [], 'min': None, 'max': None,
           'size': None, 'bounds': None, 'elem_box': None}
    best = None
    # 各导出器把 Bounds 放的位置不统一：StaticMesh 在 Properties 里，
    # SkeletalMesh 的 ImportedBounds 常在对象顶层，AggGeom 在 BodySetup 里。
    for obj in load_objects(path):
        for holder in (obj.get('Properties') or {}, obj):
            ag = holder.get('AggGeom') or {}
            for ce in ag.get('ConvexElems') or []:
                vs = [list(mp.vec(v)) for v in ce.get('VertexData') or []]
                if len(vs) < 4:
                    continue
                idx = ce.get('IndexData') or []
                tris = [[int(idx[i]), int(idx[i + 1]), int(idx[i + 2])]
                        for i in range(0, len(idx) - 2, 3)
                        if max(idx[i], idx[i + 1], idx[i + 2]) < len(vs)]
                if not tris:
                    continue
                if best is None or len(vs) > len(best['verts']):
                    best = {'verts': vs, 'tris': tris}
                    eb = ce.get('ElemBox') or {}
                    if eb.get('Min') and eb.get('Max'):
                        out['elem_box'] = [list(mp.vec(eb['Min'])),
                                           list(mp.vec(eb['Max']))]
            if out['bounds']:
                continue
            for key in ('ExtendedBounds', 'ImportedBounds', 'Bounds'):
                b = holder.get(key)
                if isinstance(b, dict) and b.get('BoxExtent'):
                    org, ext = mp.vec(b.get('Origin')), mp.vec(b.get('BoxExtent'))
                    out['bounds'] = {'origin': list(org), 'extent': list(ext),
                                     'from': key}
                    break
    if out['bounds']:
        o, e = out['bounds']['origin'], out['bounds']['extent']
        mn = [o[i] - e[i] for i in range(3)]
        mx = [o[i] + e[i] for i in range(3)]
    elif out['elem_box']:
        mn, mx = out['elem_box']
    elif best:
        mn, mx = _bbox(best['verts'])
    else:
        return out
    if best:
        # 凸包顶点线性映射到实测 AABB：形状来自碰撞凸包，尺寸以资产 Bounds 为准
        cmn, cmx = _bbox(best['verts'])
        vs = []
        for v in best['verts']:
            vs.append([
                round(mn[i] + (v[i] - cmn[i]) * (mx[i] - mn[i]) /
                      max(1e-6, cmx[i] - cmn[i]), 3)
                for i in range(3)])
        out['verts'], out['tris'] = vs, best['tris']
    else:
        out['verts'], out['tris'] = [], []
    out['min'], out['max'] = [round(v, 3) for v in mn], [round(v, 3) for v in mx]
    out['size'] = [round(mx[i] - mn[i], 2) for i in range(3)]
    return out


def _box_elem(ce):
    """UE BoxElem（Center + X/Y/Z 半尺寸）-> 8 顶点 / 12 三角面。"""
    c = mp.vec(ce.get('Center'))
    hx, hy, hz = (float(ce.get('X') or 0), float(ce.get('Y') or 0),
                  float(ce.get('Z') or 0))
    if min(hx, hy, hz) <= 0:
        return [], []
    verts = [[c[0] + sx * hx, c[1] + sy * hy, c[2] + sz * hz]
             for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    tris = [[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5],
            [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6],
            [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]]
    return verts, tris


def read_parts(path):
    """读资产的**全部**碰撞体，用于带门/窗洞的墙板。

    read_geometry() 只取最大的一个凸包（适合任务道具的整体外形）；而窗洞墙板
    是由上梁 / 下墙裙 / 左右立板等多个 ConvexElem 或 BoxElem 围出来的空白，
    必须全取才能看见洞。返回 {parts:[{verts,tris}], min, max, size}。
    """
    parts = []
    for obj in load_objects(path):
        for holder in (obj.get('Properties') or {}, obj):
            ag = holder.get('AggGeom') or {}
            for ce in ag.get('ConvexElems') or []:
                t = ce.get('Transform') or {}
                off = mp.vec(t.get('Translation'))
                sc = mp.vec(t.get('Scale3D'), 1.0)
                vs = [[v[0] * sc[0] + off[0], v[1] * sc[1] + off[1],
                       v[2] * sc[2] + off[2]]
                      for v in (list(mp.vec(v)) for v in ce.get('VertexData') or [])]
                idx = ce.get('IndexData') or []
                tris = [[int(idx[i]), int(idx[i + 1]), int(idx[i + 2])]
                        for i in range(0, len(idx) - 2, 3)
                        if max(idx[i], idx[i + 1], idx[i + 2]) < len(vs)]
                if len(vs) >= 4 and tris:
                    parts.append({'verts': vs, 'tris': tris})
            for be in ag.get('BoxElems') or []:
                vs, tris = _box_elem(be)
                if vs:
                    parts.append({'verts': vs, 'tris': tris})
    if not parts:
        return None
    mn, mx = _bbox([v for p in parts for v in p['verts']])
    return {'parts': parts, 'min': [round(v, 3) for v in mn],
            'max': [round(v, 3) for v in mx],
            'size': [round(mx[i] - mn[i], 2) for i in range(3)]}


# ---------------------------------------------------------------------------
# 蓝图继承链 → 网格资产
# ---------------------------------------------------------------------------
def blueprint_chain(type_name, idx):
    """`PrivateFilesBox-01_BP_C` -> [本蓝图, 父蓝图, 祖蓝图 ...]。"""
    start = idx.find(_blueprint_stem(type_name), '/Blueprints/')
    chain, seen, cur = [], set(), start
    while cur and len(chain) < 8 and cur not in seen:
        seen.add(cur)
        chain.append(cur)
        nxt = None
        for obj in load_objects(cur):
            if obj.get('Type') != 'BlueprintGeneratedClass':
                continue
            ref = obj.get('SuperStruct') or obj.get('Super') or {}
            p = obj.get('Properties') or {}
            if not ref:
                ref = p.get('SuperStruct') or p.get('Super') or {}
            op = ref.get('ObjectPath') if isinstance(ref, dict) else None
            if op:
                nxt = objpath_to_file(op, idx.root)
                if nxt:
                    break
        cur = nxt
    return chain


def _mesh_refs(bp_path):
    refs = []
    for obj in load_objects(bp_path):
        p = obj.get('Properties') or {}
        for key in ('SkeletalMesh', 'StaticMesh'):
            ref = p.get(key)
            if isinstance(ref, dict) and ref.get('ObjectPath'):
                refs.append((key, ref['ObjectPath']))
    return refs


def _is_box(kind_hint):
    return bool(re.search(r'box|crate|file|record|package|case|chest|trunk',
                          str(kind_hint or ''), re.I))


def _frame_parts(mn, mx, color):
    """贴着底面的一圈细框：整图俯视时也能把任务道具从场景杂物里标出来。"""
    w, d = mx[0] - mn[0], mx[1] - mn[1]
    t = max(1.2, min(w, d) * 0.075)
    pad = min(w, d) * 0.07
    x0, x1 = mn[0] - pad, mx[0] + pad
    y0, y1 = mn[1] - pad, mx[1] + pad
    z0, z1 = mn[2] - 1.2, mn[2] + 0.4
    return [
        box_part([x0, y0, z0], [x1, y0 + t, z1], color, 'mark'),
        box_part([x0, y1 - t, z0], [x1, y1, z1], color, 'mark'),
        box_part([x0, y0 + t, z0], [x0 + t, y1 - t, z1], color, 'mark'),
        box_part([x1 - t, y0 + t, z0], [x1, y1 - t, z1], color, 'mark'),
    ]


def _decorate(geom, is_box):
    """按实测包围盒补装饰件，让档案箱看起来像档案箱而非一个灰方块。"""
    mn, mx = geom['min'], geom['max']
    w, d, h = [mx[i] - mn[i] for i in range(3)]
    parts = []
    if geom['verts']:
        parts.append({'name': 'body', 'color': C_BODY if is_box else C_GENERIC,
                      'verts': geom['verts'], 'tris': geom['tris']})
    else:
        parts.append(box_part(mn, mx, C_BODY if is_box else C_GENERIC, 'body'))
    parts.extend(_frame_parts(mn, mx, C_MARK))
    if not is_box or min(w, d, h) < 2:
        return parts
    e = lambda a, b, t: a + (b - a) * t
    # 盖沿：略外扩的薄板，压在箱顶
    parts.append(box_part(
        [mn[0] - w * 0.035, mn[1] - d * 0.035, e(mn[2], mx[2], 0.87)],
        [mx[0] + w * 0.035, mx[1] + d * 0.035, mx[2] + h * 0.02], C_LID, 'lid'))
    # 标签：正面（-Y）贴一张浅色纸条
    parts.append(box_part(
        [e(mn[0], mx[0], 0.22), mn[1] - d * 0.012, e(mn[2], mx[2], 0.34)],
        [e(mn[0], mx[0], 0.78), mn[1] - d * 0.002, e(mn[2], mx[2], 0.68)],
        C_LABEL, 'label'))
    # 封条：顶面横跨的一条深色带
    parts.append(box_part(
        [e(mn[0], mx[0], 0.44), mn[1] + d * 0.02, mx[2] + h * 0.02],
        [e(mn[0], mx[0], 0.56), mx[1] - d * 0.02, mx[2] + h * 0.035],
        C_TAPE, 'tape'))
    return parts


def resolve_shape(type_name, idx, label='', key='', verbose=False):
    """解析一个任务道具蓝图的真实形状；失败返回 None（前端退回八面体标记）。"""
    if not idx or not idx.ok or not type_name:
        return None
    chain = blueprint_chain(type_name, idx)
    if not chain:
        if verbose:
            print('  - 形状：找不到 %s 的蓝图资产' % type_name)
        return None
    refs = []
    for bp in chain:
        for kind, op in _mesh_refs(bp):
            if (kind, op) not in refs:
                refs.append((kind, op))
    refs.sort(key=lambda r: 0 if r[0] == 'SkeletalMesh' else 1)
    is_box = _is_box(key or type_name)
    for kind, op in refs:
        path = objpath_to_file(op, idx.root)
        geom = idx.geometry(path)
        asset_name = os.path.basename(path)[:-5] if path else str(op)
        if not geom or not geom.get('size') or min(geom['size']) < 0.5:
            continue
        # SkeletalMesh 通常没有凸包，用同名的 StaticMesh 资产补形状
        if not geom['verts']:
            alt = idx.find(re.sub(r'_SM$', '', asset_name, flags=re.I), '/Mesh/')
            alt_geom = idx.geometry(alt) if alt and alt != path else None
            if alt_geom and alt_geom['verts']:
                geom = dict(geom)
                geom['verts'], geom['tris'] = alt_geom['verts'], alt_geom['tris']
                geom['shape_asset'] = os.path.basename(alt)
        shape = {
            'id': str(type_name),
            'name': label or _blueprint_stem(type_name),
            'kind': 'box' if is_box else 'generic',
            'mesh': asset_name,
            'asset': os.path.relpath(path, idx.root).replace('\\', '/') if path else '',
            'shape_asset': geom.get('shape_asset') or
                           (os.path.basename(path) if geom['verts'] else ''),
            'size': [round(v, 1) for v in geom['size']],
            'bmin': geom['min'], 'bmax': geom['max'],
            'chain': [os.path.basename(p) for p in chain],
            'parts': _decorate(geom, is_box),
            'note': '凸包/包围盒来自资产实测；盖沿/标签/封条/底座框按包围盒比例程序化生成',
        }
        if verbose:
            print('  - 形状 %s -> %s  实测 %s cm  链 %s' % (
                shape['name'], asset_name, shape['size'],
                ' > '.join(shape['chain'])))
        return shape
    if verbose:
        print('  - 形状：%s 的继承链里没有带几何的网格资产' % type_name)
    return None
