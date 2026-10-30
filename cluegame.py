# -*- coding: utf-8 -*-
"""RES_MT01「Murder Mystery」（Resort Spa · 推理谋杀案）—— seed → 房间 / 凶器 / 凶手 三个数。

逆向来源（TOT.exe）：
    RBClueGameObjectiveCoordinator 的类加载 sub_1408E4410（size 4232，属性表 0x145B2C7E8）
    sub_14320B590  协调器初始化（虚函数）：
        ① v = GetSeed(协调器实例)
        ② 复制 ClueRooms（16 个）→ Fisher-Yates 洗牌（i 从 16 到 2，共 15 次抽样，每次 ++v）
        ③ 按 SubObjectives 顺序给每个子目标写 RandomClueIndex(+0xF18)：
               RandomClueIndex = RandSeeded(v++, NumberOfClues(+0xEE8))
           SubObjectives 顺序 = Room(9) → Weapon(6) → Killer(9)
        ④ 答案 = RandomClueIndex + 1
           犯罪现场房间 = 洗牌后数组里下标 == Room 的那个 ClueRoom
    sub_143209730 / sub_14320A590  把结果分发给房间/武器/人体模型

实测：seed 339339 → Room=7(ClueRoom_BreakRoom) / Weapon=1(frying pan) / Killer=6
"""
import seedcore as sc

M32 = sc.M32

COORDINATOR = 'RBClueGameObjectiveCoordinator_1'   # 关卡里的实例名（不是类名！）
LEVEL_OBJECT = sc.LEVEL_OBJECT

# 关卡 JSON：RBClueGameObjectiveCoordinator_1.ClueRooms（数组顺序，不能排序）
CLUE_ROOMS = [
    ('ClueRoom_SilentAuction', 'Silent Auction'),
    ('ClueRoom_ChangingRoom', 'Changing Room'),
    ('ClueRoom_FineArts', 'Fine Arts'),
    ('ClueRoom_Maintenance', 'Maintenance'),
    ('ClueRoom_Manager', 'Manager'),
    ('ClueRoom_Office', 'Office'),
    ('ClueRoom_SaunaExterior', 'Sauna Exterior'),
    ('ClueRoom_SaunaSpa', 'Sauna Spa'),
    ('ClueRoom_SauneSnow', 'Sauna Snow'),
    ('ClueRoom_Telephones', 'Telephones'),
    ('ClueRoom_Janitor', 'Janitor'),
    ('ClueRoom_Storage', 'Storage'),
    ('ClueRoom_Locker', 'Locker'),
    ('ClueRoom_GameRoom', 'Game Room'),
    ('ClueRoom_Cloak', 'Cloak'),
    ('ClueRoom_BreakRoom', 'Break Room'),
]

# SubObjectives 顺序 + 各自 NumberOfClues（武器 6 种、房间/凶手各 9 个候选）
SUBOBJECTIVES = [('room', 9), ('weapon', 6), ('killer', 9)]


def shuffle(items, seed, salt):
    """与 sub_14320B590 同序的 Fisher-Yates：i 从 n 到 2，先抽 seed 再自增。"""
    a = list(items)
    i = len(a)
    while i >= 2:
        j = sc.rand_seeded(seed, i, salt)
        seed = (seed + 1) & M32
        if i - 1 != j:
            a[i - 1], a[j] = a[j], a[i - 1]
        i -= 1
    return a, seed


def predict(level_seed, actor=None):
    """返回 {'coord_seed', 'rooms', 'indexes', 'answers', 'crime_scene'}。

    answers: {'room': 1..9, 'weapon': 1..6, 'killer': 1..9}
    crime_scene: 犯罪现场那个 ClueRoom（有编号的房间之一）
    """
    salt = level_seed % 1000
    seed = sc.seed_of_object(actor or COORDINATOR,
                             sc.crc32_fname(LEVEL_OBJECT))
    rooms, v = shuffle(CLUE_ROOMS, seed, salt)
    idx = {}
    for name, clues in SUBOBJECTIVES:
        idx[name] = sc.rand_seeded(v, clues, salt)
        v = (v + 1) & M32
    scene = rooms[idx['room']]
    return {
        'coord_seed': seed,
        'salt': salt,
        'rooms': [r[0] for r in rooms],
        'indexes': idx,
        'answers': {k: x + 1 for k, x in idx.items()},
        'crime_scene': scene[0],
        'crime_scene_name': scene[1],
    }


def describe(level_seed):
    """给 CLI 用的一行行文本。"""
    r = predict(level_seed)
    a = r['answers']
    return [
        ('  ROOM   %d   （犯罪现场：%s / %s）'
         % (a['room'], r['crime_scene_name'], r['crime_scene'])),
        '  WEAPON %d   （武器陈列里编号 %d 的那件）' % (a['weapon'], a['weapon']),
        '  KILLER %d   （缺肢组合一致、编号 %d 的人体模型）' % (a['killer'], a['killer']),
    ]
