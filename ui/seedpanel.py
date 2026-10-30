# -*- coding: utf-8 -*-
"""seedpanel.py — 地图窗口右侧的「本局答案」面板。

读日志（gamelog）→ 推理（seedinfo）→ 显示。日志里一出现 Trial ID + Seed 就能算（不用等
StageReady）；主窗口轮询到日志变化时会带着 info 调 refresh()，这里不再自己读文件。
"""
from __future__ import annotations

import datetime
import os
import tkinter as tk

import gamelog
import seedinfo
from uifont import fnt

CARD = '#ffffff'
BG = '#f6f8fb'
INK = '#1f2c38'
MUTED = '#7d8b99'
ACCENT = '#0f766e'
WARN = '#b45309'

STATUS_NAME = {'loading': '加载中', 'ready': '准备中',
               'started': '进行中', 'ended': '已结束'}

_UNSET = object()


class SeedPanel(tk.Frame):
    """右侧栏：本局信息 + 推理结果。"""

    def __init__(self, master, log_path=None, seed_lib=None, width=440):
        super().__init__(master, bg=CARD, width=width,
                         highlightthickness=1, highlightbackground='#dbe3ec')
        self.pack_propagate(False)
        self.log_path = log_path
        self.seed_lib = seed_lib
        self.info = None
        self.answer = None

        head = tk.Frame(self, bg=CARD)
        head.pack(side='top', fill='x', padx=12, pady=(10, 2))
        tk.Label(head, text='SEED', bg=CARD, fg=ACCENT,
                 font=fnt(13, True)).pack(side='left')
        self.lbl_status = tk.Label(head, text='', bg=CARD, fg=MUTED, font=fnt(9))
        self.lbl_status.pack(side='right')

        self.lbl_meta = tk.Label(self, text='正在读取日志…', bg=CARD, fg=INK, anchor='w',
                                 justify='left', wraplength=width - 26,
                                 font=fnt(10))
        self.lbl_meta.pack(side='top', fill='x', padx=12)

        body = tk.Frame(self, bg=CARD)
        body.pack(side='top', fill='both', expand=True, padx=12, pady=(8, 0))
        self.text = tk.Text(body, bg='#fbfdff', fg='#1f2c38', bd=0, wrap='word',
                            font=fnt(9, mono=True), padx=8, pady=6,
                            insertwidth=0, highlightthickness=0)
        scroll = tk.Scrollbar(body, command=self.text.yview, width=10)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        self.text.pack(side='left', fill='both', expand=True)
        self.text.tag_configure('note', foreground=WARN)
        self.text.tag_configure('answer', foreground='#0f766e', font=fnt(9, True, mono=True))
        self.text.tag_configure('dim', foreground=MUTED)
        self.text.tag_configure('err', foreground='#dc2626')
        self.text.configure(state='disabled')

        foot = tk.Frame(self, bg=CARD)
        foot.pack(side='bottom', fill='x', padx=12, pady=8)
        tk.Button(foot, text='刷新 (R)', command=self.refresh, bd=0, padx=10, pady=3,
                  bg='#dbeafe', font=fnt(9)).pack(side='left')
        tk.Button(foot, text='复制全部', command=self.copy_all, bd=0, padx=10, pady=3,
                  bg='#dbeafe', font=fnt(9)).pack(side='left', padx=6)
        self.lbl_foot = tk.Label(self, text='', bg=CARD, fg=MUTED, anchor='w', font=fnt(8))
        self.lbl_foot.pack(side='bottom', fill='x', padx=12)

    # -- 刷新
    def refresh(self, info=_UNSET):
        """info 由主窗口传入（它已经在轮询日志）；不传就自己读一次。"""
        self.info = gamelog.latest(self.log_path) if info is _UNSET else info
        self.answer = seedinfo.answer(self.info, self.seed_lib)

        if self.info:
            status = STATUS_NAME.get(self.info['status'], '')
            self.lbl_status.config(text=status)
            self.lbl_meta.config(
                text='%s   ·   seed %d   ·   %dP   ·   %s\n%s（%s 读到）'
                     % (self.info['trial'], self.info['seed'], self.info['players'],
                        self.info['difficulty'], self.info['time'],
                        self.info['stage']))
        else:
            self.lbl_status.config(text='无对局')
            self.lbl_meta.config(text='日志里还没有 Trial ID / Seed（还没开一局，或日志路径不对）')

        self._set_text(self.answer.get('text') or '', self.answer.get('ok'))
        log = gamelog.find_path(self.log_path) or '(未找到 OPP.log)'
        self.lbl_foot.config(text='%s   %s' % (
            os.path.basename(log), datetime.datetime.now().strftime('%H:%M:%S')))
        return bool(self.answer and self.answer.get('ok'))

    def _set_text(self, content, ok):
        self.text.configure(state='normal')
        self.text.delete('1.0', 'end')
        for line in (content or '').splitlines():
            tag = ()
            if line.startswith('!'):
                tag = ('note',)
            elif not ok:
                tag = ('err',)
            elif '密码' in line or '答案' in line:
                tag = ('answer',)
            elif line.startswith('seed ='):
                tag = ('dim',)
            self.text.insert('end', line + '\n', tag)
        self.text.configure(state='disabled')

    def copy_all(self):
        content = self.text.get('1.0', 'end').strip()
        if not content:
            return
        try:
            self.winfo_toplevel().clipboard_clear()
            self.winfo_toplevel().clipboard_append(content)
        except tk.TclError:
            pass
        self.lbl_foot.config(text='已复制 %d 行' % len(content.splitlines()))

    def summary_line(self):
        return gamelog.summary(self.info)
