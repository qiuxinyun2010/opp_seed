# -*- coding: utf-8 -*-
"""The Outlast Trials —— 从 TOT.exe 逆向出来的确定性随机原语。

    sub_140503B80  GetSeed(obj)         |crc32(FName) + seed(Outer)|
    sub_141CBDC30  crc32_fname          每个 16 位字符走 4 步 CRC32
    sub_1402D29E0  RandSeeded(seed, N)  混入 dword_146E2E5C4 % 1000 后取 (uint16)hash % N
    sub_1413F08D0  RandBool(seed)       同一个 64 位混合，取最低位
    lookup3 mix    0x14320CF6D          c = 0x9E3779B9 的 9 步 Jenkins mix（32 位环绕）
    FRandomStream  lcg_state            state = state*196314165 + 907633515

每个函数的来源地址写在注释里，方便回查反编译。
"""

M32 = 0xFFFFFFFF
M64 = 0xFFFFFFFFFFFFFFFF

LEVEL_OBJECT = 'PersistentLevel'
ROOM_COMPONENT = 'RBPuzzleRoomComponent_0'

# ---------------------------------------------------------------------------
# FName / GetSeed
# ---------------------------------------------------------------------------
_CRC_TAB = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = ((_c >> 1) ^ 0xEDB88320) if (_c & 1) else (_c >> 1)
    _CRC_TAB.append(_c & M32)


def crc32_fname(name):
    """FName 的 CRC32：每个字符按 4 字节 [lo, hi, 0, 0] 喂进标准 CRC32。

    ⚠️ 别用 zlib.crc32(name.encode('utf-16-le'))（每字符 2 步）—— 那是错的，
    会得到全错的种子。校验：crc32_fname('PersistentLevel') == 0x4C09CC22。
    """
    crc = M32
    for ch in name:
        u = ord(ch) & 0xFFFF
        crc = _CRC_TAB[(crc ^ (u & 0xFF)) & 0xFF] ^ (crc >> 8)
        crc = _CRC_TAB[(crc ^ (u >> 8)) & 0xFF] ^ (crc >> 8)
        crc = _CRC_TAB[crc & 0xFF] ^ (crc >> 8)
        crc = _CRC_TAB[crc & 0xFF] ^ (crc >> 8)
    return (~crc) & M32


def seed_of_object(name, outer_seed=0):
    """GetSeed 的名字兜底分支：|crc(name) + seed(outer)|（取绝对值的 32 位）。"""
    v = (crc32_fname(name) + outer_seed) & M32
    return v if v < 0x80000000 else (0x100000000 - v) & M32


def seed_chain(names_outer_to_inner, base=0):
    """名字链：['PersistentLevel', 'Actor', 'Component'] → GetSeed(组件)。"""
    s = base
    for n in names_outer_to_inner:
        s = seed_of_object(n, s)
    return s


# ---------------------------------------------------------------------------
# 随机原语
# ---------------------------------------------------------------------------
def _mix64(seed, salt):
    """sub_1402D29E0 / sub_1413F08D0 共用的 64 位混合，返回 32 位 v3。"""
    a = (0xBF58476D1CE4E5B9 * ((seed ^ (seed >> 30)) & M64)) & M64
    a ^= a >> 27
    g = (salt % 1000) & M64
    b = (0xBF58476D1CE4E5B9 * g) & M64
    b ^= b >> 27
    v5 = (((0x94D049BB133111EB * a) & M64) ^
          ((0x94D049BB133111EB * b) & M64)) & M64
    t = (v5 ^ (v5 >> 31)) & M64
    v6 = (0xBF58476D1CE4E5B9 * (t ^ (t >> 30))) & M64
    u = (v6 ^ (v6 >> 27)) & M64
    v7 = (((321982955 * u) & M64) ^
          (((0x94D049BB133111EB * u) & M64) >> 31)) & M64
    return v7 & M32


def rand_seeded(seed, n, salt=0):
    """sub_1402D29E0(seed, N)：返回 [0, N)。

    salt 传关卡种子即可（内部只取 % 1000）。
    seed == 0 时游戏里走 rand()（不可预测），这里返回 0。
    """
    if not n or not seed:
        return 0
    return (_mix64(seed & M32, salt) & 0xFFFF) % n


def rand_seeded_range(seed, lo, hi, salt=0):
    """sub_1401A0F00(seed, lo, hi) -> [lo, hi]。"""
    if hi - lo < 0:
        return lo
    span = (hi - lo + 1) & 0xFFFF
    if span == 0:
        return lo
    return lo + (rand_seeded(seed, span, salt) % span)


def rand_bool(seed, salt=0):
    """sub_1413F08D0：同一个混合，取最低位。"""
    if not salt:
        return 0
    return _mix64(seed & M32, salt) & 1


def jenkins_mix(a, b):
    """0x14320CF6D 起的 lookup3 mix（c 固定 0x9E3779B9），全 32 位环绕。"""
    a &= M32
    b &= M32
    c = 0x9E3779B9
    v6 = ((b - a) ^ (a >> 13)) & M32
    v7 = ((c - a - v6) ^ (v6 << 8)) & M32
    v8 = ((a - v6 - v7) ^ (v7 >> 13)) & M32
    v9 = ((v6 - v7 - v8) ^ (v8 >> 12)) & M32
    v10 = ((v7 - v8 - v9) ^ (v9 << 16)) & M32
    v11 = ((v8 - v9 - v10) ^ (v10 >> 5)) & M32
    v12 = ((v9 - v10 - v11) ^ (v11 >> 3)) & M32
    v13 = ((v10 - v11 - v12) ^ (v12 << 10)) & M32
    v14 = (v11 - (v13 + v12)) & M32
    return ((v13 >> 15) ^ v14) & M32


# FRandomStream（部分关卡用，保留以便复用）
def lcg_step(state):
    return (state * 196314165 + 907633515) & M32


def get_fraction(state):
    import struct
    bits = (state >> 9) | 0x3F800000
    return struct.unpack('<f', struct.pack('<I', bits))[0] - 1.0


def rand_range(state, n):
    if n <= 0:
        return 0, state
    state = lcg_step(state)
    return int(n * get_fraction(state)), state


def select_subset(candidates, seed, count, salt=0):
    """sub_1437E5100：抽 count 个不重复项，保序删除。"""
    pool = list(candidates)
    picked = []
    state = (seed + salt) & M32
    for _ in range(count):
        if not pool:
            break
        idx, state = rand_range(state, len(pool))
        picked.append(pool.pop(idx))
    return picked


# ---------------------------------------------------------------------------
# FIntByDifficulty（sub_1404FF400）—— 注意：判断用的是「Override 标志」而不是值
# ---------------------------------------------------------------------------
def int_by_difficulty(block, difficulty='normal'):
    """从 IntByDifficulty 块里取当前难度生效的整数值。

    block 形如 {'bOverrideEasyLocalValue': False, 'EasyLocalValue': 0,
                'bOverrideNormalLocalValue': True, 'NormalLocalValue': 3, ...}

    ⚠️ 游戏里的坑：某个难度没写 Override（标志 false）时**不会**用 0，
    而是往下一档回落（easy→normal→hard→insane）。所以「Easy=0」这种配置
    在 Easy 局里实际生效的是 Normal 的值。
    """
    order = [('easy', 'EasyLocalValue'), ('normal', 'NormalLocalValue'),
             ('hard', 'HardLocalValue'), ('insane', 'InsaneLocalValue')]
    want = {'easy': 0, 'normal': 1, 'hard': 2, 'insane': 3}.get(difficulty, 1)
    for i, (tag, key) in enumerate(order):
        if i < want:
            continue
        if block.get('bOverride%sLocalValue' % tag.capitalize()):
            return block.get(key)
    for tag, key in reversed(order):          # 全都没配 → 取最后一档（default）
        if key in block:
            return block.get(key)
    return 0


# ---------------------------------------------------------------------------
# CHJ_MT01（法院 · 让正义天平倾斜）：LargePuzzleRoom 分支
#   sub_14374E420 选分区/房间；sub_1436FE410 生成 4 位密码
# ---------------------------------------------------------------------------
CHJ_MT01_SECTIONS = [
    ['RBRoom_West_ConstructionGore', 'RBRoom_West_PrivateOffice',
     'RBRoom_West_Bureau', 'RBRoom_West_OfficeConstruction'],
    ['RBRoom_East_Courtroom_1', 'RBRoom_East_Courtroom_2',
     'RBRoom_East_Museum', 'RBRoom_East_BreakRoom'],
    ['RBRoom_East_JudgesOffice'],
    ['RBRoom_West_Maintenance', 'RBRoom_West_Blueprints'],
]


def _rand_bool_chj(seed, salt):
    return rand_seeded((seed + 93405) & M32, 2, salt) & 1


def _section_keys(n, salt):
    pool = list(range(n))
    keys = []
    for _ in range(n):
        i = rand_seeded(48688, len(pool), salt) % len(pool)
        keys.append(pool.pop(i))
    return keys


def _sort_sections(keys, salt):
    """sub_14374E420 的插入排序变体（元素带 count 与 key）。"""
    e = [{'id': i, 'cnt': 0, 'key': keys[i]} for i in range(len(keys))]
    for end in range(len(e) - 1, 0, -1):
        best = 0
        for j in range(1, end + 1):
            if e[best]['cnt'] == e[j]['cnt']:
                take = _rand_bool_chj(e[best]['key'], salt)
            else:
                take = e[best]['cnt'] < e[j]['cnt']
            if take:
                best = j
        if best != end:
            e[best], e[end] = e[end], e[best]
    return [x['id'] for x in e]


def pick_rooms(level_seed, sections=None, want=3, trace=False):
    """关卡种子 → 本局谜题房间（按抽取顺序）。

    盐：分区排序 48688 / 相似度 93405 / 填充 (剩余数 + 28088)。
    """
    if sections is None:
        sections = CHJ_MT01_SECTIONS
    salt = level_seed % 1000
    keys = _section_keys(len(sections), salt)
    order = _sort_sections(keys, salt)
    pools = {i: list(s) for i, s in enumerate(sections)}
    picked, remaining = [], want
    for sid in order:
        if remaining <= 0:
            break
        pool = pools[sid]
        if not pool:
            continue
        idx = rand_seeded(remaining + 28088, len(pool), salt) % len(pool)
        room = pool.pop(idx)
        picked.append(room)
        if trace:
            print('   section %d (n=%d) salt=%d idx=%d -> %s'
                  % (sid, len(pool) + 1, remaining + 28088, idx, room))
        remaining -= 1
    if trace:
        print('   keys=%s order=%s' % (keys, order))
    return picked


def room_component_seed(room, level_name=None, component=None):
    """GetSeed(房间组件) = |crc(组件名) + |crc(房间名) + crc(关卡名)||。"""
    level_name = level_name or LEVEL_OBJECT
    component = component or ROOM_COMPONENT
    return seed_of_object(component, seed_of_object(room, crc32_fname(level_name)))


def passcode(level_seed, room, digits=4, level_name=None, component=None):
    """sub_1436FE410：digit_i = pool[ RandSeeded(compSeed + i + 7168, |pool|) ]。

    pool 每间重置为 0..9，抽走即删（保序）。
    """
    salt = level_seed % 1000
    comp = room_component_seed(room, level_name, component)
    pool = list(range(10))
    out = []
    for i in range(digits):
        idx = rand_seeded((comp + i + 7168) & M32, len(pool), salt)
        out.append(pool.pop(idx))
    return ''.join(str(d) for d in out)
