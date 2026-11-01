# -*- coding: utf-8 -*-
"""gamelog.py — 从游戏日志（OPP.log）里读出「本局用的是哪个关卡、什么种子、几个人、什么难度」。

**不用等 StageReady**：日志里先出现的是 GameStageInfo，这一行就带齐了关卡 + 种子 + 难度 +
人数，可以立刻算答案：

    [..]RB:  GameStageInfo changed. Program ID: programCoreMH, Trial ID: MHS_MT01,
             Program difficulty: Easy, Stage: MobsterHideoutSyndicate, Mission: MHS_MT01,
             Seed: 707707, EffectiveNumberOfPlayers: 1

StageReady 通常要几十秒后才来（

    [..]RB:  StageReady. Trial ID: MHS_MT01, Stage: MobsterHideoutSyndicate,
             Mission: MHS_MT01, Seed: 707707, ENbPlayer: 1

），只用来把状态推进到「准备中/进行中」。

「最后一局」的判定：StageReady 和 GameStageInfo 一起按行号排序，取最后一条。所以新一局刚
开始（只有 GameStageInfo）时也能立刻读到 seed；打完一局回大厅时日志里也不会再冒出旧局。

返回（找不到就 None）：

    {'trial': 'MHS_MT01', 'mission': 'MHS_MT01', 'stage': 'MobsterHideoutSyndicate',
     'seed': 707707, 'players': 1, 'difficulty': 'Easy',
     'ts': '2026.10.29-19.47.40:659', 'time': '19:47:40',
     'status': 'loading' / 'ready' / 'started' / 'ended',
     'stage_ready': False,             # 这一局是否已经出过 StageReady
     'event': 'stageinfo' / 'ready',   # 这条信息来自哪种行
     'age_min': 12.4,                  # 这局距离现在多少分钟
     'line': '原始行', 'source': 日志路径}

读文件不做常驻轮询；`signature()` 给人做「文件变了没」的廉价判断（stat 一次）。
"""
from __future__ import annotations

import datetime
import glob
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LOCAL_OPP_LOG = os.path.join(HERE, 'OPP.log')       # 调试用的副本

RE_TS = re.compile(r'^\[(\d{4}\.\d{2}\.\d{2}-\d{2}\.\d{2}\.\d{2}:\d{3})\]')
RE_STAGE_READY = re.compile(
    r'StageReady\.\s*Trial ID:\s*(?P<trial>[^,]+),\s*Stage:\s*(?P<stage>[^,]+),'
    r'\s*Mission:\s*(?P<mission>[^,]*),\s*Seed:\s*(?P<seed>\d+),'
    r'\s*ENbPlayer:\s*(?P<players>\d+)')
RE_GAME_STAGE = re.compile(
    r'GameStageInfo changed\.\s*Program ID:\s*(?P<program>[^,]+),'
    r'\s*Trial ID:\s*(?P<trial>[^,]+),\s*Program difficulty:\s*(?P<difficulty>[^,]+),'
    r'\s*Stage:\s*(?P<stage>[^,]+),\s*Mission:\s*(?P<mission>[^,]*),'
    r'\s*Seed:\s*(?P<seed>\d+),\s*EffectiveNumberOfPlayers:\s*(?P<players>\d+)')
RE_PHASE = re.compile(r'GamePhase changed to (?P<phase>\w+)')

PHASE_STATUS = {
    'StageReady': 'ready',
    'StageStarted': 'started',
    'StageEnding': 'ended',
    'StageSuccess': 'ended',
    'ReturnToLobby': 'ended',
}

STATUS_NAME = {'loading': '加载中', 'ready': '准备中', 'started': '进行中', 'ended': '已结束'}

FULL_READ_LIMIT = 16 * 1024 * 1024      # 16MB 以内整份读，够覆盖很多局
TAIL_BYTES = 8 * 1024 * 1024           # 超大日志只读末尾这么多


# ---------------------------------------------------------------------------
# 找日志 / 读文件
# ---------------------------------------------------------------------------
def default_paths():
    """按可能性排序的日志候选路径。"""
    out = []
    env = os.environ.get('OPP_LOG')
    if env:
        out.append(env)
    local = os.environ.get('LOCALAPPDATA')
    if local:
        out.append(os.path.join(local, 'OPP', 'Saved', 'Logs', 'OPP.log'))
        out.extend(sorted(glob.glob(os.path.join(local, '*', 'Saved', 'Logs', 'OPP.log'))))
    out.append(LOCAL_OPP_LOG)
    return out


def find_path(explicit=None):
    """返回第一个存在的日志路径；都没有就 None。

    显式给了路径就以它为准（不存在直接返回 None，不偷偷回退到默认位置）。
    """
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    for path in default_paths():
        if path and os.path.isfile(path):
            return path
    return None


def signature(path=None):
    """(路径, 大小, mtime) —— 变了就说明日志有更新，可以直接比对，不做解析。"""
    real = find_path(path)
    if not real:
        return None
    try:
        st = os.stat(real)
    except OSError:
        return None
    return (real, st.st_size, st.st_mtime_ns)


def read_text(path):
    """整份读日志（UTF-8，坏字节替换）；特别大时只读末尾一段。

    注意：不能只读固定 512KB —— 一局打完日志可能已经涨到几 MB，StageReady 早就被挤出
    末尾窗口了，那才会出现「明明开了一局却没有 seed」。
    """
    size = os.path.getsize(path)
    with io.open(path, 'rb') as fp:
        if size > FULL_READ_LIMIT:
            fp.seek(size - TAIL_BYTES)
        data = fp.read()
    text = data.decode('utf-8', 'replace')
    if size > FULL_READ_LIMIT:
        cut = text.find('\n')
        if cut >= 0:
            text = text[cut + 1:]
    return text


def _ts(text):
    m = RE_TS.match(text or '')
    return m.group(1) if m else ''


def _parse_ts(ts):
    """2026.10.29-19.47.40:659 -> datetime"""
    try:
        date, rest = ts.split('-', 1)
        clock, _ms = rest.split(':', 1)
        return datetime.datetime.strptime('%s %s' % (date, clock), '%Y.%m.%d %H.%M.%S')
    except Exception:
        return None


def _age_min(info):
    dt = _parse_ts((info or {}).get('ts'))
    if not dt:
        return None
    return round((datetime.datetime.now() - dt).total_seconds() / 60.0, 1)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def _valid(match):
    try:
        return bool(match.group('trial').strip()) and int(match.group('seed')) > 0
    except Exception:
        return False


def events(text):
    """所有「关卡 + 种子」事件，按行号升序：[(行号, 'ready'|'stageinfo', match)]"""
    out = []
    for i, line in enumerate(text.splitlines()):
        m = RE_STAGE_READY.search(line)
        if m:
            if _valid(m):
                out.append((i, 'ready', m))
            continue
        m = RE_GAME_STAGE.search(line)
        if m and _valid(m):
            out.append((i, 'stageinfo', m))
    return out


def parse_text(text, source=None):
    """从日志文本里取最后一局（StageReady 和 GameStageInfo 一起排序取最后一条）。"""
    lines = text.splitlines()
    evs = events(text)
    if not evs:
        return None
    idx, kind, m = evs[-1]
    seed = int(m.group('seed'))

    info = {
        'trial': m.group('trial').strip(),
        'stage': m.group('stage').strip(),
        'mission': (m.group('mission') or '').strip(),
        'seed': seed,
        'players': int(m.group('players')),
        'difficulty': m.group('difficulty').strip() if kind == 'stageinfo' else '',
        'ts': _ts(lines[idx]),
        'status': 'loading',
        'event': kind,
        'line': lines[idx].strip(),
        'source': source,
    }

    # 难度：StageReady 里没有，往前找同一 seed 的 GameStageInfo（越过上一局就不找）
    if not info['difficulty']:
        for j, k2, m2 in reversed([e for e in evs if e[0] < idx]):
            if k2 == 'stageinfo' and int(m2.group('seed')) == seed:
                info['difficulty'] = m2.group('difficulty').strip()
                break
            if k2 == 'ready':
                break

    # 状态：这一局之后出现的阶段变化（StageReady / StageStarted / StageEnding ...）
    info['status'] = 'loading'
    seen_phase = False
    for line in lines[idx + 1:]:
        m2 = RE_PHASE.search(line)
        if m2 and m2.group('phase') in PHASE_STATUS:
            info['status'] = PHASE_STATUS[m2.group('phase')]
            seen_phase = True
    if not seen_phase:
        info['status'] = 'ready' if kind == 'ready' else 'loading'
    info['stage_ready'] = kind == 'ready' or info['status'] != 'loading'

    dt = _parse_ts(info['ts'])
    info['time'] = dt.strftime('%H:%M:%S') if dt else info['ts']
    info['age_min'] = _age_min(info)
    info['players'] = max(1, min(3, info['players']))    # seed.py 只支持 1~3 人
    info['difficulty'] = info['difficulty'] or 'Easy'
    return info


_CACHE = {}          # 路径 -> (signature, info)


def latest(path=None):
    """读日志，返回最新一局的信息（没有就 None）。文件没变就直接用缓存。"""
    sig = signature(path)
    if not sig:
        return None
    real = sig[0]
    hit = _CACHE.get(real)
    if hit and hit[0] == sig:
        info = hit[1]
    else:
        try:
            text = read_text(real)
        except OSError:
            return hit[1] if hit else None
        info = parse_text(text, source=real)
        _CACHE[real] = (sig, info)
    if info:
        info['age_min'] = _age_min(info)      # 缓存里的 age 会过期，每次重算
    return info


def seed_line(info):
    """拼成日志里 GameStageInfo 那一行的格式，方便直接贴给别人。

    Trial ID: PSO_MT01, Program difficulty: Easy, Stage: PoliceStationOffices,
    Mission: PSO_MT01, Seed: 329329, EffectiveNumberOfPlayers: 1
    """
    if not info:
        return ''
    return ('Trial ID: %s, Program difficulty: %s, Stage: %s, Mission: %s, '
            'Seed: %s, EffectiveNumberOfPlayers: %s' % (
                info.get('trial') or '',
                info.get('difficulty') or 'Easy',
                info.get('stage') or '',
                info.get('mission') or info.get('trial') or '',
                info.get('seed') if info.get('seed') is not None else '',
                info.get('players') or 1))


def summary(info):
    """一行摘要，给界面/命令行用。"""
    if not info:
        return '未在日志里找到 Trial ID / Seed（先开一局游戏，或检查日志路径）'
    status = STATUS_NAME.get(info.get('status'), '?')
    extra = '   %.0f 分钟前' % info['age_min'] if info.get('age_min') is not None else ''
    return '%s · seed %d · %dP · %s · %s（%s）%s' % (
        info['trial'], info['seed'], info['players'], info['difficulty'],
        status, info['time'], extra)


# ---------------------------------------------------------------------------
# CLI 自检
# ---------------------------------------------------------------------------
def main(argv=None):
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(description='读游戏日志里的本局关卡与种子')
    ap.add_argument('--log', default=None, help='日志路径（默认自动找）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--all', action='store_true', help='列出日志里所有对局（含 GameStageInfo）')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    path = find_path(args.log)
    if not path:
        print('找不到 OPP.log，试过：')
        for p in default_paths():
            print('  ' + p)
        return 2

    if args.all:
        lines = read_text(path).splitlines()
        for idx, kind, m in events('\n'.join(lines)):
            print('%s  %-6s %-10s seed=%-7s %sP  %s' % (
                _ts(lines[idx]), kind, m.group('trial').strip(), m.group('seed'),
                m.group('players'), m.group('stage').strip()))
        return 0

    info = latest(args.log)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2, default=str))
    else:
        print('日志：%s' % path)
        print(summary(info))
        if info:
            print('原始行：%s' % info['line'])
    return 0 if info else 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
