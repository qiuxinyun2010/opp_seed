# -*- coding: utf-8 -*-
"""bundle.py — 把 opp_seed 打包成「一个文件」，反向也能拆回多文件。

给 AI 一次性喂上下文用：`pack` 出一个纯文本包，粘/传过去即可；AI 改完回传后，
`unpack` 能把包还原成原来的目录结构（内容按字节还原，CRLF/BAT 换行不会被动过）。

用法
----
    python tools/bundle.py pack                          # -> ./opp_seed.bundle.txt
    python tools/bundle.py pack -o C:\\tmp\\ctx.txt
    python tools/bundle.py pack --exclude 'ui/data/maps/*' --exclude '*.svg'
    python tools/bundle.py pack --all                     # PNG 等二进制也收（base64）
    python tools/bundle.py pack --root ui -o ui.bundle.txt  # 只打包 ui/ 这一个子目录
    python tools/bundle.py list opp_seed.bundle.txt       # 只看清单，不写盘
    python tools/bundle.py unpack opp_seed.bundle.txt -o .\\restore
    python tools/bundle.py unpack opp_seed.bundle.txt -o .\\restore --dry-run
    python tools/bundle.py unpack opp_seed.bundle.txt -o .\\restore --force

包格式（纯文本，行尾统一 LF，每段用「路径 + 结束标记」配合，AI 改内容也不会错位）
----
    @@@OPPSEED-BUNDLE 1
    @@@ROOT opp_seed
    @@@GENERATED 2026-10-30T12:00:00
    @@@FILES 42
    @@@INCLUDE .gitignore 119                     <- 清单：包内每个文件 + 字节数
    @@@INCLUDE seed.py 56555
    @@@INCLUDE ui/启动地图工具.bat 1267
    @@@BEGIN
    @@@FILE seed.py
    <seed.py 的原始字节>
    @@@END seed.py
    @@@FILE ui/启动地图工具.bat
    <bat 原始字节>
    @@@END ui/启动地图工具.bat
    @@@FILE data/logo.png b64
    <base64 文本>
    @@@END data/logo.png b64
    @@@EOF

标记说明：
  * `b64`  内容体是 base64（二进制文件，仅 `--all` 时出现）
  * `nonl` 原文件末尾没有换行，包里补的那个 LF 在还原时去掉
  * `@@@END <与 @@@FILE 完全相同的参数>`，所以内容里出现 `@@@END` 也不会被误判
"""
from __future__ import annotations

import argparse
import base64
import datetime
import fnmatch
import hashlib
import os
import sys

MAGIC = '@@@OPPSEED-BUNDLE 1'
FLAGS = ('b64', 'nonl')
DEFAULT_EXCLUDES = (
    '.git', '.github', '__pycache__', '*.pyc', '*.pyo', '*.pyd',
    '*.log', '*.zip', '*.bundle.txt', '.DS_Store', 'Thumbs.db',
    'tools/BUNDLE_RULES.md',          # 规则文件单独发，不塞进包里
)
DEFAULT_OUT = 'opp_seed.bundle.txt'


# --------------------------------------------------------------------------- 工具

def _rel_posix(path, root):
    return os.path.relpath(path, root).replace(os.sep, '/')


def _match(rel, name, patterns):
    """rel 或 name 命中任一 glob 就算排除（glob 里带 / 时按整路径匹配）。"""
    for pat in patterns:
        pat = pat.replace('\\', '/').strip('/')
        if '/' in pat:
            if fnmatch.fnmatch(rel, pat) or rel.startswith(pat.rstrip('/') + '/'):
                return True
        elif fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def _looks_binary(raw):
    if b'\x00' in raw:
        return True
    try:
        raw.decode('utf-8')
    except UnicodeDecodeError:
        return True
    return False


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


# --------------------------------------------------------------------------- pack

def iter_files(root, excludes, out_path):
    for dirpath, dirnames, filenames in os.walk(root):
        keep = []
        for d in sorted(dirnames):
            rel = _rel_posix(os.path.join(dirpath, d), root)
            if not _match(rel, d, excludes):
                keep.append(d)
        dirnames[:] = keep

        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if out_path and os.path.abspath(full) == out_path:
                continue
            rel = _rel_posix(full, root)
            if _match(rel, name, excludes):
                continue
            yield rel, full


def cmd_pack(args):
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        raise SystemExit('不是目录：%s' % root)

    out = os.path.abspath(args.out) if args.out else os.path.join(os.getcwd(), DEFAULT_OUT)
    excludes = list(DEFAULT_EXCLUDES) + list(args.exclude or [])

    entries, skipped = [], []
    for rel, full in iter_files(root, excludes, out):
        with open(full, 'rb') as f:
            raw = f.read()
        if _looks_binary(raw):
            if not args.all:
                skipped.append(rel)
                continue
            entries.append((rel, raw, True))
        else:
            entries.append((rel, raw, False))

    if not entries:
        raise SystemExit('没找到可打包的文件（检查 --root / --exclude）')

    stamp = datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    chunks = [
        MAGIC,
        '@@@ROOT %s' % os.path.basename(root),
        '@@@GENERATED %s' % stamp,
        '@@@FILES %d' % len(entries),
    ]
    # 头部清单：包内有哪些文件、各自多少字节（跳过的二进制不写进头部）
    chunks.extend('@@@INCLUDE %s %d' % (rel, len(raw)) for rel, raw, _ in entries)
    chunks.append('@@@BEGIN')

    # 先落一个临时文件，全部成功后再改名，避免半截包
    tmp = out + '.tmp'
    with open(tmp, 'wb') as f:
        f.write(('\n'.join(chunks) + '\n').encode('utf-8'))
        for rel, raw, is_bin in entries:
            flags = []
            body = raw
            if is_bin:
                flags.append('b64')
                body = base64.b64encode(raw)
            if not is_bin and not raw.endswith((b'\n', b'\r')):
                flags.append('nonl')
                body = raw + b'\n'
            tag = ' '.join([rel] + flags)
            f.write(('@@@FILE %s\n' % tag).encode('utf-8'))
            f.write(body)
            if not body.endswith(b'\n'):
                f.write(b'\n')
            f.write(('@@@END %s\n' % tag).encode('utf-8'))
        f.write(b'@@@EOF\n')

    # 回读校验：文件清单与内容哈希必须与源目录一一对应
    with open(tmp, 'rb') as f:
        parsed = _parse(f.read())
    got = {p: (_sha(raw), is_bin) for p, raw, is_bin in parsed}
    bad = [rel for rel, raw, _ in entries if got.get(rel, ('', ''))[0] != _sha(raw)]
    if bad:
        os.remove(tmp)
        raise SystemExit('回读校验失败，已放弃写入：%s' % ', '.join(bad[:5]))

    os.replace(tmp, out)
    size = os.path.getsize(out)
    print('打包完成：%s' % out)
    print('  文件 %d 个，%.1f KB%s' % (
        len(entries), size / 1024.0,
        ('，跳过二进制 %d 个（--all 可收录）' % len(skipped)) if skipped else ''))
    if args.quiet:
        return
    for rel, raw, is_bin in entries:
        print('  %-52s %8d B%s' % (rel, len(raw), '  [b64]' if is_bin else ''))


# ------------------------------------------------------------------------- unpack

def _parse(data):
    """-> [(path, raw_bytes, is_b64)]，格式见模块 docstring。"""
    if data.startswith(b'\xef\xbb\xbf'):          # 被编辑器加过 BOM
        data = data[3:]
    lines = data.splitlines(keepends=True)
    out, i = [], 0
    while i < len(lines):
        stripped = lines[i].rstrip(b'\r\n')
        if stripped.startswith(b'```'):
            # 整包被 Markdown 代码块包着时，跳过 ``` 围栏（只在外层生效，段内内容不受影响）
            i += 1
            continue
        if stripped.startswith(b'@@@FILE '):
            tag = stripped[len(b'@@@FILE '):].decode('utf-8')
            tokens = tag.split(' ')
            flags = []
            while len(tokens) > 1 and tokens[-1] in FLAGS:
                flags.append(tokens.pop())
            path = ' '.join(tokens)
            endmark = '@@@END %s' % tag
            buf, j = [], i + 1
            while j < len(lines) and lines[j].rstrip(b'\r\n').decode('utf-8', 'replace') != endmark:
                buf.append(lines[j])
                j += 1
            if j >= len(lines):
                raise SystemExit('包被截断：%s 缺少 @@@END 行' % path)
            raw = b''.join(buf)
            if 'b64' in flags:
                raw = base64.b64decode(b''.join(raw.split()), validate=True)
            elif 'nonl' in flags:
                raw = raw[:-1] if raw.endswith(b'\n') else raw
            out.append((path, raw, 'b64' in flags))
            i = j + 1
            continue
        if stripped == b'@@@EOF':
            break
        i += 1
    return out


def _safe_join(base, rel):
    rel = rel.replace('\\', '/')
    if rel.startswith('/') or ':' in rel.split('/')[0]:
        raise SystemExit('非法路径（绝对路径）：%s' % rel)
    if any(part == '..' for part in rel.split('/')):
        raise SystemExit('非法路径（包含 ..）：%s' % rel)
    dst = os.path.abspath(os.path.join(base, rel))
    if os.path.commonpath([base, dst]) != base:
        raise SystemExit('非法路径（越出目标目录）：%s' % rel)
    return dst


def cmd_list(args):
    with open(args.bundle, 'rb') as f:
        entries = _parse(f.read())
    if not entries:
        raise SystemExit('包里没有 @@@FILE 段：%s' % args.bundle)
    total = 0
    for path, raw, is_bin in entries:
        total += len(raw)
        print('%-52s %9d B%s' % (path, len(raw), '  [b64]' if is_bin else ''))
    print('---- %d 个文件，%.1f KB' % (len(entries), total / 1024.0))


def cmd_unpack(args):
    with open(args.bundle, 'rb') as f:
        entries = _parse(f.read())
    if not entries:
        raise SystemExit('包里没有 @@@FILE 段：%s' % args.bundle)

    base = os.path.abspath(args.out or '.')
    plan = [(p, _safe_join(base, p), raw) for p, raw, _ in entries]

    clash = [dst for _, dst, _ in plan if os.path.exists(dst) and not args.force]
    if clash and not args.dry_run:
        print('目标文件已存在（共 %d 个，用 --force 覆盖）：' % len(clash))
        for dst in clash[:10]:
            print('  %s' % dst)
        if len(clash) > 10:
            print('  ...')
        raise SystemExit(1)

    same = 0
    for path, dst, raw in plan:
        old = None
        if os.path.exists(dst):
            with open(dst, 'rb') as f:
                old = f.read()
        if old == raw:
            same += 1
            mark = '='
        else:
            mark = '~' if old is not None else '+'
        print('%s %s' % (mark, path))
        if args.dry_run:
            continue
        os.makedirs(os.path.dirname(dst) or base, exist_ok=True)
        with open(dst, 'wb') as f:
            f.write(raw)

    verb = '将写入' if args.dry_run else '已写入'
    print('---- %s %d 个文件到 %s（其中 %d 个内容未变）' % (verb, len(plan), base, same))


# ---------------------------------------------------------------------------- CLI

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='bundle.py',
        description='把项目打包成单个文本文件（给 AI 当上下文），或把包拆回多文件。')
    sub = ap.add_subparsers(dest='cmd')

    p = sub.add_parser('pack', help='目录 -> 单个 .txt 包')
    p.add_argument('-o', '--out', help='输出文件（默认 ./%s）' % DEFAULT_OUT)
    p.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   help='要打包的目录（默认=本脚本所在仓库根）')
    p.add_argument('--exclude', action='append', metavar='GLOB',
                   help='额外排除，可多次给；带 / 按相对路径匹配，否则按文件名')
    p.add_argument('--all', action='store_true', help='二进制文件也收（base64）')
    p.add_argument('-q', '--quiet', action='store_true', help='只打印汇总')
    p.set_defaults(func=cmd_pack)

    p = sub.add_parser('unpack', help='.txt 包 -> 多个文件')
    p.add_argument('bundle')
    p.add_argument('-o', '--out', help='解到哪个目录（默认当前目录）')
    p.add_argument('--force', action='store_true', help='覆盖已存在的文件')
    p.add_argument('--dry-run', action='store_true', help='只看会写哪些文件')
    p.set_defaults(func=cmd_unpack)

    p = sub.add_parser('list', help='列出包里的文件清单')
    p.add_argument('bundle')
    p.set_defaults(func=cmd_list)

    args = ap.parse_args(argv)
    if not getattr(args, 'func', None):
        ap.print_help()
        return 2
    return args.func(args) or 0


if __name__ == '__main__':
    sys.exit(main())
