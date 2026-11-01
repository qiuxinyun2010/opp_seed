# -*- coding: utf-8 -*-
"""FPI_MT02「Survive the Game Show」（游乐场 · 数图案）—— seed → 房间 / 图案 / 答案。

逆向来源（TOT.exe）：
    0x14320C8F0  this+0x1828 = GetSeed(协调器)          // 名字链，与关卡种子无关
    0x14320CEB0  PrepareRound(consoles)                 // 正式回合
    0x14320F140  教学回合（bIsTutorial == 1）
    0x14320F4E0 → 0x14320FB00                           // 「和恰为 N」的数字串
    0x14320C940  收集翻板 → FlipboardsBySection
    0x1402D29E0  RandSeeded(seed, N)
    0x1413F08D0  RandBool(seed)

一回合的种子链（同一个递增计数器 v）：
    ① 抽房间   RandSeeded(v++, 18)，去重 + 跳过上一回合用过的
    ② 假板数   RandSeeded(v++, min(板数-1, MaxFake)+1)，0 → 1
    ③ 目标图案 RandSeeded(v++, 9)，本回合内不重复
    ④ 答案     RandSeeded(v, 10)（0 或与上回合同房重复则重抽）→ 生成数字串
    ⑤ 应用     每块板 RandBool；假板换图案 + 随机数字；真板写图案与数字
                ⇒ 答案 = 目标图案板的数字之和
"""
import seedcore as sc

SECTIONS = [
    ('RBRoom_RabbitTortur', 'Rabbit Torture'),
    ('RBRoom_RabbitHole_CarrotsStorage', 'Carrots Storage'),
    ('RBRoom_RabbitHole_Bedroom_Master', 'Rabbit Bedroom'),
    ('RBRoom_RabbitHole_DinnerTable', 'Rabbit Dinner'),
    ('RBRoom15_9', 'Kitchen Storage'),
    ('RBRoom_QueenTrone', 'Queen Throne'),
    ('RBRoom_CreepyHands', 'Wall Of Hands'),
    ('RBRoom_Library', 'Library'),
    ('RBRoom_Storm', 'Storm'),
    ('RBRoom_UpsideDownStorm', 'Upside Storm'),
    ('RBRoom_UpsideDown_Church', 'Upside Church'),
    ('RBRoom_SpaceConsoleStation', 'Space Station'),
    ('RBRoom_UpsideUp_Church', 'Church'),
    ('RBRoom_ShowRoom_Master', 'Showroom'),
    ('RBRoom_Eyes', 'Wall Of Eyes'),
    ('RBRoom_Tesseract', 'Illusion Cube'),
    ('RBRoom_DinningIllusion', 'Illusion Dinner'),
    ('RBRoom_DarkMannequin', 'Child Dorm'),
]
ROOM_NAMES = dict(SECTIONS)
SYMBOLS = ['Apple', 'Book', 'BrushTeeth', 'Cleaning', 'Dumbbells',
           'Sharing', 'Sleep', 'WashHands', 'Water', 'Blank']
SYMBOL_ASSETS = ['FPI_MT02_Symbol-%s-01' % s for s in SYMBOLS[:9]] + \
                ['FPI_MT02_Symbol_Blank-01']

COORDINATOR = 'MT02_GameShowObjectiveCoordinator'
TUTORIAL_COORDINATOR = 'MT02_GameShowObjectiveCoordinator_Tuto'
BOARDS_PER_SECTION = 4          # 72 块正式翻板 / 18 分区
MAX_FAKE = 3                    # 见 README：Easy 档因未写 Override 回落 Normal=3
ROUNDS = 2
CONSOLES = {1: 2, 2: 3, 3: 4, 4: 4}   # NumActiveConsoles（Values1P/2P/3P 覆盖，4P 回落默认 4）

M32 = sc.M32


def gen_digits(left, slots, idx, seed, out, salt):
    """0x14320FB00：池 [1..9] 每层洗牌（RandSeeded(seed,k)，k=9..2），
    递归挑数字：sum == left、相邻不同、每层重新洗牌。"""
    if slots == idx:
        return left == 0
    avail = slots - idx
    if not (avail <= left <= 9 * avail):
        return False
    pool = list(range(1, 10))
    s = seed
    for k in range(9, 1, -1):
        j = sc.rand_seeded(s, k, salt)
        s = (s + 1) & M32
        if k - 1 != j:
            pool[k - 1], pool[j] = pool[j], pool[k - 1]
    for v in pool:
        if idx > 0 and v == out[idx - 1]:
            continue
        rem = left - v
        rest = slots - (idx + 1)
        if rest <= rem <= 9 * rest:
            out[idx] = v
            if gen_digits(rem, slots, idx + 1, sc.jenkins_mix(v, s), out, salt):
                return True
    return False


def try_digits(total, slots, seed, salt):
    out = [0] * slots
    return out if gen_digits(total, slots, 0, seed, out, salt) else None


class Coordinator(object):
    """一次任务里 RBGameShowObjectiveCoordinator 的状态（used / sums 跨回合保留）。"""

    def __init__(self, level_seed, players=1, actor=None,
                 boards=BOARDS_PER_SECTION, max_fake=MAX_FAKE):
        self.level_seed = level_seed
        self.players = players
        self.consoles = CONSOLES.get(players, 4)
        self.actor = actor or COORDINATOR
        self.boards = boards
        self.max_fake = max_fake
        self.seed = sc.seed_of_object(self.actor, sc.crc32_fname(sc.LEVEL_OBJECT))
        self.used = []
        self.sums = {}

    def prepare(self, round_idx):
        ls = self.level_seed
        salt = ls % 1000
        v = sc.jenkins_mix(round_idx & M32, self.seed)
        while self.used and len(SECTIONS) - len(self.used) < self.consoles:
            self.used.pop(0)

        src = []                                     # ① 抽房间
        for _ in range(self.consoles):
            while True:
                idx = sc.rand_seeded(v, len(SECTIONS), salt)
                v = (v + 1) & M32
                if idx not in src and idx not in self.used:
                    break
            src.append(idx)

        fakes = {}                                   # ② 假板数
        for idx in src:
            cap = min(self.boards - 1, self.max_fake)
            r = sc.rand_seeded(v, cap + 1, salt)
            v = (v + 1) & M32
            fakes[idx] = r if r else 1
            if cap <= 0:
                fakes[idx] = r

        syms = []                                    # ③ 目标图案
        for _ in src:
            while True:
                s = sc.rand_seeded(v, len(SYMBOLS) - 1, salt)
                v = (v + 1) & M32
                if s not in syms:
                    break
            syms.append(s)

        plan = []                                    # ④ 答案 + 数字串
        for i, idx in enumerate(src):
            prev = self.sums.get(idx, -1)
            free = self.boards - fakes[idx]
            got = None
            for _k in range(100):
                dseed = (v + 1) & M32
                cand = sc.rand_seeded(v, 10, salt)
                if cand == 0 or cand == prev:
                    v = (v + 1) & M32
                    continue
                if cand >= free:
                    v = (v + 2) & M32
                    digits = try_digits(cand, free, dseed, salt)
                    if digits:
                        got = (cand, digits)
                        break
                else:
                    v = (v + 1) & M32
            if got is None:                          # 1..9 兜底
                for cand in range(1, 10):
                    if cand == prev or cand < free:
                        continue
                    digits = try_digits(cand, free, (v + cand - 1) & M32, salt)
                    if digits:
                        got = (cand, digits)
                        v = (v + cand) & M32
                        break
            if got is None:
                return None
            self.sums[idx] = got[0]
            plan.append([idx, syms[i], got[0], got[1]])

        for item in plan:                            # ⑤ 应用（消耗种子）
            left = fakes[item[0]]
            for b in range(self.boards):
                if left <= 0 or left != self.boards - b:
                    flag = sc.rand_bool(v, salt)
                    v = (v + 1) & M32
                else:
                    flag = 1
                if left > 0 and flag:
                    while True:
                        s2 = sc.rand_seeded(v, len(SYMBOLS) - 1, salt)
                        v = (v + 1) & M32
                        if s2 != item[1]:
                            break
                    v = (v + 2) & M32
                    left -= 1

        self.used.extend(src)
        return [{'room': SECTIONS[i][0], 'room_name': SECTIONS[i][1],
                 'symbol': SYMBOLS[s], 'symbol_index': s,
                 'answer': ans, 'digits': digs}
                for i, s, ans, digs in plan]


def predict(level_seed, players=1, rounds=ROUNDS, max_fake=MAX_FAKE):
    """正式回合（第 2、3 阶段）。"""
    co = Coordinator(level_seed, players, max_fake=max_fake)
    out = []
    for r in range(rounds):
        rooms = co.prepare(r)
        out.append({'round': r, 'stage': r + 2, 'rooms': rooms or [],
                    'failed': rooms is None})
        if rooms is None:
            break
    return out


def predict_tutorial(level_seed, max_fake=MAX_FAKE):
    """教学回合（第 1 阶段）：只有一个分区，slots = 板数 - 1。"""
    salt = level_seed % 1000
    co = Coordinator(level_seed, 1, actor=TUTORIAL_COORDINATOR, max_fake=max_fake)
    slots = co.boards - 1
    v = sc.jenkins_mix(0, co.seed)
    sym = sc.rand_seeded(v, len(SYMBOLS) - 1, salt)
    v = (v + 1) & M32
    got = None
    for _k in range(100):
        dseed = (v + 1) & M32
        cand = sc.rand_seeded(v, 10, salt)
        if cand and cand >= slots:
            v = (v + 2) & M32
            digits = try_digits(cand, slots, dseed, salt)
            if digits:
                got = (cand, digits)
                break
        else:
            v = (v + 1) & M32
    if got is None:
        return {'round': -1, 'stage': 1, 'rooms': [], 'failed': True}
    return {'round': -1, 'stage': 1, 'failed': False,
            'rooms': [{'room': 'RBRoom_Circus', 'room_name': 'Hourglass',
                       'symbol': SYMBOLS[sym], 'symbol_index': sym,
                       'answer': got[0], 'digits': got[1]}]}
