# -*- coding: utf-8 -*-
"""markers.py — 从 seed.py 的推理结果里把「坐标」挖出来，变成地图上的标记点。

不写死每关的结构，按字段名递归找：

    {"...": ..., "coordinates": [x, y, z], "room": "RBRoom_X", "code": "854"}
    clue.crime_scene_coordinates = [x, y, z]
    connections[].letter_coordinates / number_coordinates

每条标记：

    {'p': [x, y, z], 'label': '854', 'room': 'RBRoom_...', 'section': 'patterns',
     'kind': 'goal'|'clue', 'exact': True/False,
     'path': 'patterns[0]', 'text': 'MHS_MT01 — 854 · RBRoom_...'}
"""
from __future__ import annotations

_LABEL_FIELDS = ('code', 'color_name', 'pattern_name', 'label', 'name',
                 'letter', 'number', 'bucket')


def _is_point(value):
    return (isinstance(value, (list, tuple)) and len(value) == 3
            and all(isinstance(v, (int, float)) for v in value))


def _room_of(node, key):
    """坐标字段旁边一般有 room 字段：letter_coordinates -> letter_room。"""
    if not isinstance(node, dict):
        return ''
    if node.get('room'):
        return str(node['room'])
    base = key[:-len('_coordinates')] if key.endswith('_coordinates') else ''
    for cand in (base + '_room', base.replace('_', '') + '_room'):
        if node.get(cand):
            return str(node[cand])
    for cand in ('crime_scene', 'letter_room', 'number_room'):
        if node.get(cand):
            return str(node[cand])
    return ''


def _label_of(node, key, section):
    if isinstance(node, dict):
        base = key[:-len('_coordinates')] if key.endswith('_coordinates') else ''
        if 'crime_scene' in key:
            return str(node.get('crime_scene_name') or 'Crime scene')
        if base and node.get(base) not in (None, ''):
            if base in ('letter', 'number'):
                return '%s %s' % (base.title(), node[base])   # Letter J / Number 21
            return str(node[base])
        for field in _LABEL_FIELDS:
            val = node.get(field)
            if val not in (None, ''):
                if field == 'code' and node.get('pattern_name'):
                    return '%s %s' % (node['pattern_name'], val)
                return str(val)
        if base:
            return base.replace('_', ' ').title()
        if 'crime_scene' in key:
            return 'Crime scene'
        room = _room_of(node, key)
        if room:
            return room.replace('RBRoom_', '').replace('_', ' ')
    return section or 'marker'


def collect(result):
    """result = seed.py predict() 的返回值（dict）。返回标记列表。"""
    out = []
    seen = set()

    def add(node, key, section, path):
        point = node.get(key)
        if not _is_point(point):
            return
        p = [round(float(v), 1) for v in point]
        sig = (tuple(p), section)
        if sig in seen:
            return
        seen.add(sig)
        room = _room_of(node, key)
        label = _label_of(node, key, section)
        ctype = str(node.get('coordinate_type') or
                    node.get(key[:-len('_coordinates')] + '_coordinate_type') or '')
        out.append({
            'p': p,
            'label': label,
            'room': room,
            'section': section or '',
            'kind': 'goal' if node.get('code') else 'clue',
            'exact': ctype != 'room_center',
            'path': path,
            'text': '%s · %s%s' % (section or '', label,
                                   (' · ' + room) if room else ''),
        })

    def walk(node, path, section):
        if isinstance(node, dict):
            for key, val in list(node.items()):
                if isinstance(val, str) and 'coordinat' in key:
                    continue
                if 'coordinat' in key and _is_point(val):
                    add(node, key, section, path)
                elif isinstance(val, (dict, list)):
                    walk(val, '%s.%s' % (path, key) if path else key,
                         section or key)
        elif isinstance(node, list):
            for i, val in enumerate(node):
                if isinstance(val, (dict, list)):
                    walk(val, '%s[%d]' % (path, i), section)

    if isinstance(result, dict):
        walk(result, '', '')
    return out


def summary(markers):
    if not markers:
        return '无坐标'
    counts = {}
    for m in markers:
        counts[m['section'] or '?'] = counts.get(m['section'] or '?', 0) + 1
    return ' '.join('%s=%d' % kv for kv in sorted(counts.items()))


def main(argv=None):
    """自检：算一局并把坐标打出来。"""
    import argparse
    import sys

    ap = argparse.ArgumentParser(description='从 seed 推理结果里提坐标')
    ap.add_argument('level')
    ap.add_argument('seed', type=int)
    ap.add_argument('--players', type=int, default=1)
    ap.add_argument('--difficulty', default='easy')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    import seedinfo
    ans = seedinfo.answer({'trial': args.level, 'seed': args.seed},
                          players=args.players, difficulty=args.difficulty)
    if not ans.get('ok'):
        print(ans['text'])
        return 1
    items = collect(ans.get('data'))
    print('%-8s %-12s %-38s %s' % ('label', 'section', 'room', 'p'))
    for m in items:
        print('%-8s %-12s %-38s (%.1f, %.1f, %.1f)%s'
              % (m['label'], m['section'], m['room'] or '-', m['p'][0], m['p'][1], m['p'][2],
                 '' if m['exact'] else '  ≈room center'))
    print('共 %d 个（%s）' % (len(items), summary(items)))
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
