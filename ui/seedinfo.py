# -*- coding: utf-8 -*-
"""seedinfo.py — 把「关卡 + 种子」交给 seed.py 推理，拿回可直接显示的文字。

seed.py 在同项目的上一级目录（release/seed/seed.py），按需加载、进程内调用
（import 约 20 ms，一次推理 <1 ms）；结果按 (关卡, 种子, 人数, 难度) 缓存。

    ans = answer(gamelog.latest())
    ans['text']   # 多行文字，直接塞进文本框
    ans['ok']     # False 时 text 里是错误原因

也支持独立调用：

    python seedinfo.py MHS_MT01 759759 [--players 1] [--difficulty easy]
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LIB = os.path.join(os.path.dirname(HERE), 'seed.py')     # release/seed/seed.py

_MODS = {}
_CACHE = {}


def resolve_lib(path=None):
    """按 显式参数 → 环境变量 → 默认位置 找 seed.py（显式给了就不回退）。"""
    if path:
        return os.path.abspath(path) if os.path.isfile(path) else None
    for cand in (os.environ.get('OPP_SEED_LIB'), DEFAULT_LIB):
        if cand and os.path.isfile(cand):
            return os.path.abspath(cand)
    return None


def load(path=None):
    """加载 seed.py（同一路径只加载一次）。返回 (module, error)。"""
    real = resolve_lib(path)
    if not real:
        if path:
            return None, '找不到 seed.py：%s（检查 --seed-lib / OPP_SEED_LIB）' % path
        return None, ('找不到 seed.py（默认应位于 %s）；'
                      '用 --seed-lib 或环境变量 OPP_SEED_LIB 指定' % DEFAULT_LIB)
    if real in _MODS:
        return _MODS[real], None
    try:
        spec = importlib.util.spec_from_file_location('_opp_seed_%d' % len(_MODS), real)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except Exception as exc:                       # noqa: BLE001 - 展示给用户
        return None, '加载 %s 失败：%s: %s' % (real, type(exc).__name__, exc)
    _MODS[real] = mod
    return mod, None


def supported_levels(path=None):
    mod, err = load(path)
    if not mod:
        return [], err
    return [k for k, v in mod.LEVELS.items()
            if any(v.get(k2) for k2 in ('sections', 'gameshow', 'cluegame', 'projection',
                                        'switchboard', 'projectors', 'firepump', 'mhs',
                                        'mannequin'))], None


def answer(info, lib_path=None, players=None, difficulty=None):
    """info 是 gamelog 的返回值；返回 {'ok', 'text', 'level', 'seed', ...}。"""
    if not info:
        return {'ok': False, 'text': '还没有读到本局信息（日志里没有 StageReady）。\n'
                                     '先开一局游戏，或点「刷新」。', 'level': None, 'seed': None}
    mod, err = load(lib_path)
    if not mod:
        return {'ok': False, 'text': err, 'level': info.get('trial'), 'seed': info.get('seed')}

    level = (info.get('trial') or '').upper()
    seed = int(info.get('seed') or 0)
    players = int(players or info.get('players') or 1)
    diff = str(difficulty or info.get('difficulty') or 'easy').strip().lower()
    if diff not in ('easy', 'normal', 'hard', 'insane'):
        diff = 'easy'

    key = (level, seed, players, diff)
    if key in _CACHE:
        return _CACHE[key]

    levels = mod.LEVELS
    if level not in levels:
        try:
            level = mod.resolve(level)
        except Exception:
            pass
    if level not in levels:
        ok_levels, _e = supported_levels(lib_path)
        result = {'ok': False, 'level': level, 'seed': seed,
                  'text': 'seed 推理暂不支持 %s。\n已接入：%s'
                          % (level or '(空)', '、'.join(ok_levels) or '(无)')}
        _CACHE[key] = result
        return result

    try:
        data = mod.predict(level, seed, players=players, difficulty=diff)
        text = mod.render(data)
    except Exception as exc:                        # noqa: BLE001
        result = {'ok': False, 'level': level, 'seed': seed,
                  'text': '推理失败（%s: %s）\n关卡 %s，seed %d，%dP，%s'
                          % (type(exc).__name__, exc, level, seed, players, diff)}
        _CACHE[key] = result
        return result

    result = {'ok': True, 'level': level, 'seed': seed, 'players': players,
              'difficulty': diff, 'text': text, 'data': data,
              'notes': data.get('notes') or []}
    _CACHE[key] = result
    return result


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description='按关卡 + 种子推理（调用 seed.py）')
    ap.add_argument('level', nargs='?', help='关卡编号，如 MHS_MT01')
    ap.add_argument('seed', nargs='?', type=int, help='关卡种子')
    ap.add_argument('--players', type=int, default=1)
    ap.add_argument('--difficulty', default='easy')
    ap.add_argument('--lib', default=None, help='seed.py 路径')
    ap.add_argument('--log', action='store_true', help='直接从游戏日志里取最新一局')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if args.log:
        import gamelog
        info = gamelog.latest()
        print(gamelog.summary(info))
        ans = answer(info, args.lib)
        print()
        print(ans['text'])
        return 0 if ans['ok'] else 1

    if not args.level or args.seed is None:
        ap.print_help()
        return 2
    ans = answer({'trial': args.level, 'seed': args.seed, 'players': args.players,
                  'difficulty': args.difficulty}, args.lib,
                 players=args.players, difficulty=args.difficulty)
    print(ans['text'])
    return 0 if ans['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
