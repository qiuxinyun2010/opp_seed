# -*- coding: utf-8 -*-
"""mapweb.py — Web 版实时交互地图与本局种子答案工具（支持游戏内全局快捷键呼出）。

用法：
    python mapweb.py                      # 启动并跟随游戏日志
    python mapweb.py PSA_MT01             # 指定初始关卡
    python mapweb.py --browser            # 用普通浏览器标签页打开
    python mapweb.py --port 18765         # 固定本地端口
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import mimetypes
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, 'web')
DATA_DIR = os.path.join(HERE, 'data', 'maps')

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gamelog       # noqa: E402
import hotkey        # noqa: E402
import markers       # noqa: E402
import mapview       # noqa: E402
import seedinfo      # noqa: E402

VERSION = '2026-10-30.web1'

SW_HIDE = 0
SW_SHOW = 5
SW_RESTORE = 9
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_SHOWWINDOW = 0x0040


class Win32WindowController(object):
    """管理 Web 窗口的 Win32 句柄：支持游戏内一键置顶弹出、解锁鼠标、隐藏后归还焦点给游戏。"""

    def __init__(self, title_marker='OPP Map Tool', topmost=True, activate=True):
        self.title_marker = title_marker
        self.topmost = bool(topmost)
        self.activate = bool(activate)
        self.hwnd = None
        self.prev_fg_hwnd = None
        self.visible = True

    def available(self):
        return os.name == 'nt' and ctypes is not None and wt is not None

    def find_hwnd(self):
        if not self.available():
            return None
        user32 = ctypes.windll.user32
        if self.hwnd and user32.IsWindow(self.hwnd):
            return self.hwnd

        found = []
        WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

        def _cb(hwnd, _lparam):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if self.title_marker in (buf.value or ''):
                    found.append(hwnd)
                    return False
            return True

        proc = WNDENUMPROC(_cb)
        user32.EnumWindows(proc, 0)
        if found:
            self.hwnd = found[0]
        return self.hwnd

    def is_hidden(self):
        hwnd = self.find_hwnd()
        if not hwnd:
            return not self.visible
        user32 = ctypes.windll.user32
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        return not self.visible

    def show_and_focus(self):
        hwnd = self.find_hwnd()
        if not hwnd:
            return False
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        try:
            fg = user32.GetForegroundWindow()
            if fg and fg != hwnd:
                self.prev_fg_hwnd = fg

            user32.ClipCursor(None)

            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            else:
                user32.ShowWindow(hwnd, SW_SHOW)

            z_order = HWND_TOPMOST if self.topmost else HWND_NOTOPMOST
            user32.SetWindowPos(
                hwnd, wt.HWND(z_order), 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW
            )

            if self.activate:
                tid_cur = kernel32.GetCurrentThreadId()
                tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
                tid_target = user32.GetWindowThreadProcessId(hwnd, None)
                attached_fg = False
                attached_target = False
                try:
                    if tid_fg and tid_fg != tid_cur:
                        attached_fg = bool(user32.AttachThreadInput(tid_fg, tid_cur, True))
                    if tid_target and tid_target != tid_cur:
                        attached_target = bool(user32.AttachThreadInput(tid_target, tid_cur, True))
                    user32.BringWindowToTop(hwnd)
                    user32.SetForegroundWindow(hwnd)
                    user32.SetActiveWindow(hwnd)
                    user32.SetFocus(hwnd)
                finally:
                    if attached_target:
                        user32.AttachThreadInput(tid_target, tid_cur, False)
                    if attached_fg:
                        user32.AttachThreadInput(tid_fg, tid_cur, False)

                rect = wt.RECT()
                pt = wt.POINT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)) and user32.GetCursorPos(ctypes.byref(pt)):
                    if not (rect.left <= pt.x <= rect.right and rect.top <= pt.y <= rect.bottom):
                        cx = (rect.left + rect.right) // 2
                        cy = (rect.top + rect.bottom) // 2
                        user32.SetCursorPos(cx, cy)

            self.visible = True
            return True
        except Exception:
            return False

    def hide_and_restore_game(self):
        hwnd = self.find_hwnd()
        if not hwnd:
            return False
        user32 = ctypes.windll.user32
        try:
            user32.ShowWindow(hwnd, SW_HIDE)
            self.visible = False
            if self.prev_fg_hwnd and user32.IsWindow(self.prev_fg_hwnd):
                user32.SetForegroundWindow(self.prev_fg_hwnd)
            return True
        except Exception:
            return False

    def toggle(self):
        if self.is_hidden():
            return self.show_and_focus()
        return self.hide_and_restore_game()


class AppState(object):
    def __init__(self, cfg, initial_level=None, pinned=False):
        self.cfg = cfg
        self.pinned = bool(pinned and initial_level)
        self.follow_game = bool(cfg.get('follow_game', True)) and not self.pinned
        self.current_level = (initial_level or '').upper() or None
        self.orientation = mapview.load_orientation()
        self.lock = threading.Lock()
        self.win_ctrl = None
        self.hotkey_label = hotkey.parse(cfg.get('hotkey') or 'ctrl+a')[2]
        self.is_admin = hotkey.is_admin() if hotkey else False
        self.shutdown_event = threading.Event()

    def list_levels(self):
        levels_meta = {}
        levels_json = os.path.join(HERE, 'data', 'levels.json')
        if os.path.exists(levels_json):
            try:
                with open(levels_json, encoding='utf-8') as fp:
                    levels_meta = json.load(fp)
            except Exception:
                levels_meta = {}
        out = []
        if os.path.isdir(DATA_DIR):
            for fn in sorted(os.listdir(DATA_DIR)):
                if not fn.endswith('.json'):
                    continue
                lv = fn[:-5].upper()
                meta = levels_meta.get(lv) or {}
                out.append({
                    'level': lv,
                    'map': meta.get('map') or '',
                    'name': meta.get('name') or lv,
                })
        return out

    def load_map_db(self, level):
        if not level:
            return None, None
        path = os.path.join(DATA_DIR, '%s.json' % level.upper())
        if not os.path.isfile(path):
            return None, None
        with open(path, encoding='utf-8') as fp:
            db = json.load(fp)
        notes = db.setdefault('notes', {})
        for k in ('rooms', 'zones', 'points'):
            notes.setdefault(k, {})
        db.setdefault('points', [])
        fx, fy = mapview.resolve_flip(db, self.cfg, self.orientation)
        db['_default_flip'] = {'x': fx, 'y': fy}
        return db, path

    def get_state_payload(self):
        info = gamelog.latest(self.cfg.get('log_path'))
        ans = seedinfo.answer(info, self.cfg.get('seed_lib'))
        trial = (info.get('trial') or '').upper() if info else None

        with self.lock:
            if self.follow_game and trial:
                if os.path.isfile(os.path.join(DATA_DIR, '%s.json' % trial)):
                    self.current_level = trial
            elif not self.current_level and trial:
                if os.path.isfile(os.path.join(DATA_DIR, '%s.json' % trial)):
                    self.current_level = trial
            active_level = self.current_level

        seed_markers = []
        if ans.get('ok') and ans.get('data'):
            if not active_level or (trial and trial == active_level):
                seed_markers = markers.collect(ans.get('data'))

        has_trial_map = bool(trial and os.path.isfile(os.path.join(DATA_DIR, '%s.json' % trial)))
        return {
            'version': VERSION,
            'hotkey': self.hotkey_label,
            'is_admin': self.is_admin,
            'follow_game': self.follow_game,
            'active_level': active_level,
            'trial_has_map': has_trial_map,
            'gamelog': info,
            'gamelog_summary': gamelog.summary(info),
            'seed': {
                'ok': bool(ans.get('ok')),
                'level': ans.get('level'),
                'seed': ans.get('seed'),
                'players': ans.get('players'),
                'difficulty': ans.get('difficulty'),
                'text': ans.get('text') or '',
                'notes': ans.get('notes') or [],
            },
            'seed_markers': seed_markers,
        }

    def save_note(self, level, kind, key, text):
        if kind not in ('rooms', 'zones', 'points') or not key:
            return False, '无效的备注类型或键名'
        with self.lock:
            db, path = self.load_map_db(level)
            if not db or not path:
                return False, '找不到关卡数据: %s' % level
            db.pop('_default_flip', None)
            bucket = db.setdefault('notes', {}).setdefault(kind, {})
            text = (text or '').strip()
            if text:
                bucket[str(key)] = text
            else:
                bucket.pop(str(key), None)
            with open(path, 'w', encoding='utf-8') as fp:
                json.dump(db, fp, ensure_ascii=False, separators=(',', ':'))
        return True, '已保存备注 (%s: %s)' % (kind, key)


def make_handler(app_state):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass

        def _send_json(self, data, status=200):
            body = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, filepath):
            if not os.path.isfile(filepath):
                self.send_error(404, 'File Not Found')
                return
            mime, _ = mimetypes.guess_type(filepath)
            if filepath.endswith('.js'):
                mime = 'application/javascript; charset=utf-8'
            elif filepath.endswith('.css'):
                mime = 'text/css; charset=utf-8'
            elif filepath.endswith('.html'):
                mime = 'text/html; charset=utf-8'
            with open(filepath, 'rb') as fp:
                data = fp.read()
            self.send_response(200)
            self.send_header('Content-Type', mime or 'application/octet-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            qs = urllib.parse.parse_qs(parsed.query)

            if path == '/api/state':
                return self._send_json(app_state.get_state_payload())

            if path == '/api/levels':
                return self._send_json({'levels': app_state.list_levels()})

            if path == '/api/map':
                lv = (qs.get('level') or [''])[0].strip().upper()
                if not lv:
                    lv = app_state.current_level
                db, _ = app_state.load_map_db(lv)
                if not db:
                    return self._send_json({'ok': False, 'error': '未找到关卡 %s 的地图数据' % lv}, 404)
                with app_state.lock:
                    app_state.current_level = lv
                return self._send_json({'ok': True, 'map': db})

            if path in ('/', '/index.html'):
                return self._send_file(os.path.join(WEB_DIR, 'index.html'))
            rel = path.lstrip('/')
            if '..' in rel or rel.startswith('/'):
                self.send_error(403)
                return
            return self._send_file(os.path.join(WEB_DIR, rel))

        def do_POST(self):
            parsed = urllib.parse.urlparse(self.path)
            path = parsed.path
            length = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(length) if length > 0 else b'{}'
            try:
                payload = json.loads(raw.decode('utf-8'))
            except Exception:
                payload = {}

            if path == '/api/note':
                lv = (payload.get('level') or app_state.current_level or '').upper()
                kind = payload.get('kind')
                key = payload.get('key')
                text = payload.get('text') or ''
                ok, msg = app_state.save_note(lv, kind, key, text)
                return self._send_json({'ok': ok, 'message': msg}, 200 if ok else 400)

            if path == '/api/config':
                if 'follow_game' in payload:
                    app_state.follow_game = bool(payload['follow_game'])
                    app_state.cfg['follow_game'] = app_state.follow_game
                    mapview.write_config({'follow_game': app_state.follow_game})
                if 'level' in payload and payload['level']:
                    with app_state.lock:
                        app_state.current_level = str(payload['level']).upper()
                return self._send_json({'ok': True, 'follow_game': app_state.follow_game})

            if path == '/api/window/hide':
                if app_state.win_ctrl:
                    app_state.win_ctrl.hide_and_restore_game()
                return self._send_json({'ok': True})

            if path == '/api/window/quit':
                self._send_json({'ok': True})
                app_state.shutdown_event.set()
                return

            self.send_error(404)

    return Handler


def find_chromium_browser():
    candidates = [
        shutil.which('msedge'),
        r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
        shutil.which('chrome'),
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def parse_win_size(geo_str):
    try:
        w, h = [int(v) for v in str(geo_str or '1440x960').lower().split('x')]
        return max(900, w), max(560, h)
    except Exception:
        return 1440, 960


def run_hotkey_loop(cfg, win_ctrl, stop_event):
    key = (cfg.get('hotkey') or 'ctrl+a').strip()
    if not hotkey or key.lower() in ('none', 'off', ''):
        return None
    q = queue.Queue()
    listener = hotkey.Listener(key, q)
    listener.start()

    def _worker():
        while not stop_event.is_set():
            try:
                kind, payload = q.get(timeout=0.15)
            except queue.Empty:
                continue
            if kind == 'hotkey':
                win_ctrl.toggle()
            elif kind == 'ready':
                print('全局快捷键已就绪: %s' % payload, flush=True)
            elif kind == 'error':
                print('快捷键错误: %s' % payload, flush=True)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return listener


def main(argv=None):
    ap = argparse.ArgumentParser(description='OPP Web 交互式地图与种子工具')
    ap.add_argument('target', nargs='?', help='初始关卡编号（如 PSA_MT01），省略则自动跟随游戏日志')
    ap.add_argument('--port', type=int, default=0, help='HTTP 端口（默认自动分配空闲端口）')
    ap.add_argument('--browser', action='store_true', help='使用普通浏览器标签页打开而非独立窗口')
    ap.add_argument('--log', metavar='FILE', help='指定 OPP.log 路径')
    ap.add_argument('--seed-lib', metavar='FILE', help='指定 seed.py 路径')
    ap.add_argument('--hotkey', metavar='KEY', help='全局快捷键，如 ctrl+a / F8 / none')
    ap.add_argument('--no-hotkey', action='store_true', help='禁用全局快捷键')
    ap.add_argument('--flip', choices=('none', 'x', 'y', 'xy'), default=None, help='强制镜像方式')
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    mapview.enable_dpi_awareness()

    ok, why = mapview.lock_instance('Local\\OPP_mapview')
    if not ok:
        msg = '%s。\n请直接按快捷键（如 Ctrl+A）呼出已运行的窗口，或在任务管理器结束旧进程。' % why
        print(msg, flush=True)
        if os.name == 'nt' and ctypes is not None:
            try:
                ctypes.windll.user32.MessageBoxW(None, msg, 'OPP Map Tool', 0x40)
            except Exception:
                pass
        return 1

    cfg = mapview.load_config()
    if args.log:
        cfg['log_path'] = args.log
    if args.seed_lib:
        cfg['seed_lib'] = args.seed_lib
    if args.hotkey:
        cfg['hotkey'] = args.hotkey
    if args.no_hotkey:
        cfg['hotkey'] = 'none'
    if args.flip:
        cfg['flip'] = args.flip

    initial_level = args.target.upper() if args.target else None
    if not initial_level:
        info = gamelog.latest(cfg.get('log_path'))
        if info and info.get('trial'):
            cand = info['trial'].upper()
            if os.path.isfile(os.path.join(DATA_DIR, '%s.json' % cand)):
                initial_level = cand
        if not initial_level:
            levels = sorted(f[:-5] for f in os.listdir(DATA_DIR) if f.endswith('.json'))
            if levels:
                initial_level = 'PSA_MT01' if 'PSA_MT01' in levels else levels[0]

    app_state = AppState(cfg, initial_level=initial_level, pinned=bool(args.target))

    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(app_state))
    port = server.server_address[1]
    url = 'http://127.0.0.1:%d/' % port
    print('OPP Map Web Server running at %s' % url, flush=True)

    srv_thread = threading.Thread(target=server.serve_forever, daemon=True)
    srv_thread.start()

    title_marker = 'OPP Map Tool'
    win_ctrl = Win32WindowController(
        title_marker=title_marker,
        topmost=cfg.get('always_topmost', True),
        activate=cfg.get('activate_on_hotkey', True),
    )
    app_state.win_ctrl = win_ctrl

    hk_listener = run_hotkey_loop(cfg, win_ctrl, app_state.shutdown_event)
    w, h = parse_win_size(cfg.get('window'))

    used_pywebview = False
    if not args.browser:
        try:
            import webview  # type: ignore
            used_pywebview = True
            webview.create_window(
                title='%s [%s]' % (title_marker, VERSION),
                url=url,
                width=w,
                height=h,
                on_top=bool(cfg.get('always_topmost', True)),
            )

            def _on_shown():
                time.sleep(0.3)
                win_ctrl.show_and_focus()

            webview.start(_on_shown)
            app_state.shutdown_event.set()
        except ImportError:
            used_pywebview = False

    if not used_pywebview:
        browser_exe = None if args.browser else find_chromium_browser()
        proc = None
        if browser_exe:
            profile_dir = os.path.join(HERE, 'data', 'cache', 'web_profile')
            os.makedirs(profile_dir, exist_ok=True)
            cmd = [
                browser_exe,
                '--app=%s' % url,
                '--user-data-dir=%s' % profile_dir,
                '--window-size=%d,%d' % (w, h),
                '--disable-extensions',
                '--no-first-run',
                '--no-default-browser-check',
            ]
            proc = subprocess.Popen(cmd)
            for _ in range(30):
                time.sleep(0.15)
                if win_ctrl.find_hwnd():
                    win_ctrl.show_and_focus()
                    break
        else:
            import webbrowser
            webbrowser.open(url)

        try:
            while not app_state.shutdown_event.is_set():
                if proc is not None and proc.poll() is not None:
                    break
                time.sleep(0.25)
        except KeyboardInterrupt:
            pass
        finally:
            if proc is not None and proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass

    if hk_listener:
        hk_listener.stop()
    server.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
