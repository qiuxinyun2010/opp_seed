# -*- coding: utf-8 -*-
"""variatorpoints.py — 提取「关卡变量」相关的静态点位：火桶候选点 + 全部隐藏点。

背景：
  - 日志只打印 `RB:  Variator Active: <ID>`，不含坐标。
  - 火桶 (BurningBarrelSecondaryObjective) 是运行时动态生成的：
    BurningBarrel_Secondary_ObjCoordBP 的 ReplaceRequiredTags 为
    RoomForBarrel / RoomForBarrelInteraction，地图里带这两个 Tag 的静态 actor
    就是火桶落点的候选池（NumberToSpawn=8，1P 时 FixedMaxCount=2，按 seed 抽取）。
    所以这里导出的是「全部候选落点」，不是本局实际刷出的那几个。
  - 隐藏点 (NoPlaceToHide / NoPlaceToHide2) 封闭的是 Hidespot_* / Locker 类 actor，
    这些在关卡 JSON 里有静态坐标，可以全部导出。

用法：
  python variatorpoints.py --import-names <TotHUD.ps1>   # 生成/更新 ID→中文名表
  python variatorpoints.py PSB_MT01                       # 提取这一关的点位
  python variatorpoints.py PSB_MT01 --paks D:/.../Maps_json
  python variatorpoints.py PSB_MT01 --map PoliceStationBasement --out xxx.json

输出：data/variator_points/<LEVEL>.json（/api/map 会自动把它合并进地图数据）。
"""
from __future__ import annotations

import argparse
import collections
import datetime
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from maplib.extract import MapExtractor, KEEP_COMPONENT_TYPES, iter_objects

DATA_DIR = os.path.join(HERE, 'data')
OUT_DIR = os.path.join(DATA_DIR, 'variator_points')
NAMES_FILE = os.path.join(DATA_DIR, 'variators.json')

# 火桶协调器 CDO 的 ReplaceRequiredTags（精确匹配，不含 Front/Back 等空间标记）
BARREL_TAGS = ('RoomForBarrel', 'RoomForBarrelInteraction')
# 火桶协调器 CDO 的 ReplaceActorClasses（含其地图里的子类/实例类名）
REPLACE_TYPE = re.compile(
    r'Base_PropagandaPoster|PropagandaFlyer|RBInvestigationPoint|'
    r'Placeable_PsychosisMine|VariatorGameplayIngredient_Placement|'
    r'DeadBody_Container', re.I)
# 与 maplib/extract.py 的 ITEM_RULES.hide 同口径；Locker 要按词首匹配，
# 否则 DoubleDoorsBlocker_BP_C 这类名字里的 "...blocker" 会被误当成隐藏点。
HIDE_TYPE = re.compile(r'^(?:Hidespot|PhoneBooth)|(?:^|_)Locker', re.I)

# 官方 HUD 译名与本工具用语略有差别，显示时统一成地图工具里的叫法
DISPLAY_OVERRIDES = {
    'NoPlaceToHide2': '有限隐藏点2',
    'BurningBarrelSecondaryObjective': '扑灭火桶',
    'BurningBarrelSecondaryObjective_Ext': '扑灭火桶',
}


def import_names(src):
    """从 TotHUD.ps1 的 $VarNames 哈希表生成 ID→中文名映射。"""
    text = io.open(src, encoding='utf-8-sig').read()
    start = text.find('$VarNames')
    end = text.find('$VarOrder', start)
    if start < 0 or end < 0:
        raise SystemExit('找不到 $VarNames / $VarOrder，无法导入变数名')
    pairs = re.findall(r'"([A-Za-z0-9_]+)"\s*=\s*"([^"]+)"', text[start:end])
    names = {}
    for key, val in pairs:
        names.setdefault(key, DISPLAY_OVERRIDES.get(key, val))
    data = {
        '_说明': ('关卡变量(Variator) ID -> 中文名。日志只给出 ID，中文名在这里查；'
                 'layers 指明该变数会启用哪个点位图层。可用 '
                 'python variatorpoints.py --import-names <TotHUD.ps1> 重新生成。'),
        'names': names,
        'layers': {
            'BurningBarrelSecondaryObjective': 'barrels',
            'BurningBarrelSecondaryObjective_Ext': 'barrels',
            'NoPlaceToHide': 'hidespots',
            'NoPlaceToHide2': 'hidespots',
        },
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with io.open(NAMES_FILE, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, indent=2)
        fp.write('\n')
    print('写出 %s（%d 条）' % (NAMES_FILE, len(names)))
    return 0


def map_name_of(level):
    """关卡 → 地图目录名：优先用已生成的 data/maps/<LEVEL>.json，其次 levels.json。"""
    path = os.path.join(DATA_DIR, 'maps', '%s.json' % level.upper())
    if os.path.isfile(path):
        with io.open(path, encoding='utf-8') as fp:
            name = (json.load(fp).get('map') or '').strip()
        if name:
            return name
    lv = os.path.join(DATA_DIR, 'levels.json')
    if os.path.isfile(lv):
        with io.open(lv, encoding='utf-8') as fp:
            entry = json.load(fp).get(level.upper()) or {}
        if isinstance(entry, dict) and entry.get('map'):
            return entry['map']
        if isinstance(entry, str):
            return entry
    return ''


def resolve_folder(map_name, paks):
    """找到关卡 JSON 所在目录。paks 可以是 Maps_json 根目录，也可以直接是地图目录。"""
    roots = []
    if paks:
        roots.append(paks)
    env = os.environ.get('OUTLAST_MAPS_DIR')
    if env:
        roots.append(env)
    roots.append(os.path.abspath(os.path.join(
        HERE, '..', '..', 'pak', 'OPP', 'Content', 'Maps_json')))
    roots.append(os.path.abspath(os.path.join(HERE, '..', '..', 'paks', 'MAP', 'Maps')))
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        # 先按地图名进子目录；Maps_json 根目录里偶尔也有零星 .json，
        # 不能因为看到 .json 就把根目录当成关卡目录。
        if map_name:
            cand = os.path.join(root, map_name)
            if os.path.isdir(cand):
                return cand
        if any(fn.endswith('.json') for fn in os.listdir(root)):
            return root                       # 直接就是地图目录
    raise SystemExit('找不到关卡 JSON 目录（用 --paks 指定 Maps_json 或地图目录）')


def extract(folder):
    """一遍扫描：建组件索引 + 收集目标 actor，然后用 MapExtractor 算世界坐标。"""
    ex = MapExtractor(folder)
    barrels, hidespots = [], []
    files = sorted(fn for fn in os.listdir(folder)
                   if fn.endswith('.json')
                   and 'BuiltData' not in fn and 'VisibilityData' not in fn)
    for fn in files:
        comps, hits = {}, []
        for idx, obj in iter_objects(os.path.join(folder, fn)):
            typ = obj.get('Type') or ''
            if typ in KEEP_COMPONENT_TYPES:
                comps[idx] = obj
            props = obj.get('Properties') or {}
            root = props.get('RootComponent')
            if not root:
                continue
            raw_tags = props.get('Tags')
            tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else []
            if any(t in BARREL_TAGS for t in tags):
                hits.append(('barrels', obj, tags))
            if HIDE_TYPE.search(typ):
                hits.append(('hidespots', obj, tags))
        ex.per_file[fn] = comps
        for kind, obj, tags in hits:
            props = obj.get('Properties') or {}
            loc, yaw = ex.comp_transform(fn, props.get('RootComponent'))
            x, y, z = (round(float(v), 1) for v in loc)
            if x == 0 and y == 0 and z == 0:
                continue                      # 读不到变换的占位对象
            rec = {
                'name': obj.get('Name') or '',
                'type': obj.get('Type') or '',
                'p': [x, y, z],
                'yaw': round(float(yaw), 1),
                'file': fn,
            }
            if kind == 'barrels':
                rec['tags'] = tags
                rec['interaction'] = 'RoomForBarrelInteraction' in tags
                rec['replaceable'] = bool(REPLACE_TYPE.search(rec['type']))
            (barrels if kind == 'barrels' else hidespots).append(rec)
    for arr in (barrels, hidespots):
        for i, rec in enumerate(arr):
            rec['id'] = i
    return barrels, hidespots, files


def dump_counter(rows):
    return collections.Counter(r['type'] for r in rows).most_common(8)


def main(argv=None):
    ap = argparse.ArgumentParser(description='提取变数相关点位（火桶候选 / 隐藏点）')
    ap.add_argument('level', nargs='?', help='关卡 ID，如 PSB_MT01')
    ap.add_argument('--paks', default=None, help='关卡 JSON 根目录或地图目录')
    ap.add_argument('--map', default=None, help='手动指定地图目录名')
    ap.add_argument('--out', default=None, help='输出文件')
    ap.add_argument('--import-names', default=None, metavar='TOTHUD_PS1',
                    help='从 TotHUD.ps1 导入变数中文名，生成 data/variators.json')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if args.import_names:
        return import_names(args.import_names)
    if not args.level:
        ap.error('需要关卡 ID（如 PSB_MT01），或用 --import-names 生成变数名表')

    level = args.level.upper()
    map_name = args.map or map_name_of(level)
    folder = resolve_folder(map_name, args.paks)
    print('扫描 %s' % folder)
    barrels, hidespots, files = extract(folder)

    data = {
        'level': level,
        'map': map_name,
        'source': folder.replace('\\', '/'),
        'files': len(files),
        'generated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '_说明': ('barrels = 火桶变数的全部静态候选落点（带 RoomForBarrel / '
                 'RoomForBarrelInteraction 标签的 actor）；本局实际刷出哪些由 seed 决定。'
                 'hidespots = 地图上全部隐藏点，有限隐藏点变数会封闭其中一部分。'),
        'barrels': barrels,
        'hidespots': hidespots,
    }
    out = args.out or os.path.join(OUT_DIR, '%s.json' % level)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with io.open(out, 'w', encoding='utf-8') as fp:
        json.dump(data, fp, ensure_ascii=False, separators=(',', ':'))
        fp.write('\n')
    print('写出 %s' % out)
    print('  火桶候选 %d 个（可交互 %d / 可替换类 %d）' % (
        len(barrels), sum(1 for r in barrels if r['interaction']),
        sum(1 for r in barrels if r['replaceable'])))
    print('  类型 %s' % dump_counter(barrels))
    print('  隐藏点 %d 个' % len(hidespots))
    print('  类型 %s' % dump_counter(hidespots))
    return 0


if __name__ == '__main__':
    sys.exit(main())
