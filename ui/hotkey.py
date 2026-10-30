# -*- coding: utf-8 -*-
"""hotkey.py — Windows 全局快捷键（低级键盘钩子，**只观察不吞键**）。

支持组合键：`M` / `ctrl+m` / `ctrl+shift+m` / `alt+F9` / `F8`。
游戏里按 Ctrl+M 游戏照常收到键，我们只是额外收到一次通知；钩子装在本进程，
不注入游戏、不读内存。

    q = queue.Queue()
    hk = Listener('ctrl+m', q)      # 回调通过队列交给 Tk 线程
    hk.start()                      # ... 轮询 q.get_nowait()
    hk.stop()

队列里的事件：
    ('ready', 'Ctrl+M')     钩子装好了
    ('hotkey', 'Ctrl+M')    按下了
    ('error', '原因')       装不上 / 键名认不出
    ('stopped', None)       线程退出

Windows only；其它平台 start() 直接失败并把错误塞进队列，不影响主程序。

注意：Windows 的 UIPI 会拦住「低权限进程的钩子去监听高权限窗口的按键」。
如果 OPP 是右键「以管理员身份运行」的，本工具也必须以管理员身份运行，否则按什么都没反应。
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import queue
import re
import threading
import time

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
WM_KEYUP = 0x0101
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
HC_ACTION = 0

VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12          # Alt
VK_LWIN = 0x5B
VK_RWIN = 0x5C

_VK_NAMES = {
    'ESC': 0x1B, 'ESCAPE': 0x1B, 'TAB': 0x09, 'SPACE': 0x20,
    'ENTER': 0x0D, 'RETURN': 0x0D, 'INSERT': 0x2D, 'DELETE': 0x2E,
    'HOME': 0x24, 'END': 0x23, 'PAGEUP': 0x21, 'PAGEDOWN': 0x22,
    'UP': 0x26, 'DOWN': 0x28, 'LEFT': 0x25, 'RIGHT': 0x27,
    'BACKQUOTE': 0xC0, 'TILDE': 0xC0, 'MINUS': 0xBD, 'EQUALS': 0xBB,
}

_MOD_ALIASES = {
    'CTRL': 'ctrl', 'CONTROL': 'ctrl',
    'ALT': 'alt', 'MENU': 'alt',
    'SHIFT': 'shift',
    'WIN': 'win', 'SUPER': 'win', 'META': 'win', 'CMD': 'win',
}
MOD_ORDER = ('ctrl', 'alt', 'shift', 'win')


class KBDLLHOOKSTRUCT(ctypes.Structure):
    """ctypes.wintypes 里**没有**这个结构体，必须自己声明。

    以前直接写 wt.KBDLLHOOKSTRUCT，回调里每次 cast 都抛 AttributeError，
    又被 except 吞掉 —— 钩子装上了、日志也没错，但按键永远不触发。
    """
    _fields_ = [('vkCode', wt.DWORD), ('scanCode', wt.DWORD), ('flags', wt.DWORD),
                ('time', wt.DWORD), ('dwExtraInfo', ctypes.c_void_p)]


def vk_of(name):
    """'M' / 'F8' / 'F12' / 'ESC' → 虚拟键码；认不出返回 None。"""
    if not name:
        return None
    key = str(name).strip().upper()
    if key in _VK_NAMES:
        return _VK_NAMES[key]
    if len(key) == 1 and (key.isalpha() or key.isdigit()):
        return ord(key)
    if key.startswith('F') and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x70 + n - 1
    return None


def parse(name):
    """'ctrl+m' → (vk, {'ctrl'}, 'Ctrl+M')；认不出返回 (None, mods, 原字符串)。"""
    raw = (name or '').strip()
    if not raw:
        return None, set(), ''
    mods, key = set(), ''
    for part in [p for p in re.split(r'[+\s]+', raw) if p]:
        alias = _MOD_ALIASES.get(part.upper())
        if alias:
            mods.add(alias)
        else:
            key = part
    vk = vk_of(key)
    label = '+'.join([m.title() for m in MOD_ORDER if m in mods] + [key.upper()])
    return vk, mods, (label or raw)


def _mods_down():
    """当前按住的修饰键名集合，例如 {'ctrl'}（GetAsyncKeyState 比 ll 钩子的 flags 更靠谱）。

    注意：这里**必须返回集合**。以前返回的是 {'ctrl': True/False, ...} 这种字典，
    然后 `mods.issubset(have)` —— set.issubset 比的是字典的**键**，{'ctrl'} 永远算子集，
    于是修饰键判断形同虚设：配了 ctrl+a，光按 a 也触发。
    """
    try:
        user32 = ctypes.windll.user32

        def down(vk):
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)

        have = set()
        if down(VK_CONTROL):
            have.add('ctrl')
        if down(VK_SHIFT):
            have.add('shift')
        if down(VK_MENU):
            have.add('alt')
        if down(VK_LWIN) or down(VK_RWIN):
            have.add('win')
        return have
    except Exception:
        return set()


def is_admin():
    """本进程是否管理员权限（游戏以管理员跑时必须同为管理员，钩子才收得到键）。"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class Listener(threading.Thread):
    """在独立线程里装 WH_KEYBOARD_LL，按键时往 queue 里塞事件。"""

    def __init__(self, hotkey='M', out=None, preload=True):
        super().__init__(daemon=True)
        self.hotkey = hotkey
        self.vk, self.mods, self.label = parse(hotkey)
        self.out = out if out is not None else queue.Queue()
        self.preload = preload
        self.hook = None
        self.tid = None
        self._proc = None
        self._stop = False
        self._down = False
        self._last = 0.0

    # -- 内部
    def _emit(self, kind, payload=None):
        try:
            self.out.put_nowait((kind, payload))
        except queue.Full:
            pass

    def _match(self):
        have = _mods_down()                 # 集合：{"ctrl"} / {"shift","ctrl"} / set()
        if self.mods:
            return self.mods.issubset(have)  # 配了的修饰键必须都在按着
        # 没配修饰键就只认「干净」的单击，Ctrl+A 之类不会误触发（Shift 不算）
        return not (have & {'ctrl', 'alt', 'win'})

    def _callback(self, n_code, w_param, l_param):
        if n_code == HC_ACTION and w_param in (WM_KEYDOWN, WM_SYSKEYDOWN):
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == self.vk and not self._down and self._match():
                    self._down = True
                    now = time.time()
                    if now - self._last > 0.12:       # 按住不放的重复消息
                        self._last = now
                        self._emit('hotkey', self.label)
            except Exception as exc:                  # noqa: BLE001 - 别静默死掉
                self._emit('error', '读键盘事件失败：%s: %s' % (type(exc).__name__, exc))
        elif n_code == HC_ACTION and w_param in (WM_KEYUP, WM_SYSKEYUP):
            try:
                info = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if info.vkCode == self.vk:
                    self._down = False
            except Exception:
                pass
        return ctypes.windll.user32.CallNextHookEx(None, n_code, w_param, l_param)

    def run(self):
        self._down = False
        if self.vk is None:
            self._emit('error', '快捷键 %r 认不出来（用单字母 / Ctrl+M / F1~F12）' % self.hotkey)
            return
        try:
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32
        except AttributeError:
            self._emit('error', '全局快捷键只在 Windows 上可用')
            return

        self.tid = kernel32.GetCurrentThreadId()
        proc_type = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_int, wt.WPARAM, wt.LPARAM)
        self._proc = proc_type(self._callback)
        # 64 位下句柄是 8 字节，不声明会按 int 截断导致 ERROR_MOD_NOT_FOUND(126)
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, proc_type, ctypes.c_void_p, wt.DWORD]
        user32.SetWindowsHookExW.restype = ctypes.c_void_p
        user32.UnhookWindowsHookEx.argtypes = [ctypes.c_void_p]
        user32.CallNextHookEx.argtypes = [ctypes.c_void_p, ctypes.c_int, wt.WPARAM, wt.LPARAM]
        user32.CallNextHookEx.restype = ctypes.c_ssize_t

        self.hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, None, 0)
        if not self.hook:
            code = kernel32.GetLastError()
            hint = '' if is_admin() else '；如果游戏是管理员权限运行，本工具也要用管理员身份启动'
            self._emit('error', '安装键盘钩子失败（错误码 %d）%s' % (code, hint))
            return
        self._emit('ready', self.label)

        msg = wt.MSG()
        try:
            while not self._stop and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_QUIT:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))
        finally:
            if self.hook:
                user32.UnhookWindowsHookEx(self.hook)
                self.hook = None
            self._emit('stopped', None)

    def stop(self):
        self._stop = True
        self._down = False
        try:
            if self.tid:
                ctypes.windll.user32.PostThreadMessageW(self.tid, WM_QUIT, 0, 0)
        except Exception:
            pass


def main(argv=None):
    """命令行自检：按快捷键就在控制台打一行（排查快捷键问题时先跑这个）。"""
    import argparse
    import sys

    ap = argparse.ArgumentParser(description='全局快捷键自检')
    ap.add_argument('-k', '--key', default='ctrl+m')
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    vk, mods, label = parse(args.key)
    print('解析 %r → vk=%s mods=%s label=%s' % (args.key, vk, sorted(mods), label))
    print('当前权限：%s' % ('管理员' if is_admin() else '普通用户（若游戏是管理员，这里收不到键）'))

    out = queue.Queue()
    hk = Listener(args.key, out)
    hk.start()
    print('监听 %s（Ctrl+C 退出）……' % label)
    try:
        while True:
            kind, payload = out.get()
            if kind == 'error':
                print('错误：%s' % payload)
                return 1
            if kind == 'ready':
                print('钩子已就绪：%s' % payload)
            elif kind == 'hotkey':
                print('按下 %s  %s' % (payload, time.strftime('%H:%M:%S')))
    except KeyboardInterrupt:
        hk.stop()
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
