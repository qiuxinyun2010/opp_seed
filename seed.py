# -*- coding: utf-8 -*-
"""按「关卡 + 关卡种子」推理这一局的有用信息。

用法：
    python seed.py --list
    python seed.py FPI_MT02 189189                      # 房间 / 图案 / 答案
    python seed.py FPI_MT02 189189 --players 3          # 1-4 人（讲台数不同：2/3/4/4）
    python seed.py FPI_MT02 189189 --difficulty easy    # easy / normal / hard / insane
    python seed.py CHJ_MT01 592592                      # 谜题房间 + 4 位密码
    python seed.py CHJ_MT01 592592 --trace              # 附带分区抽取过程
    python seed.py CHJ_MT02 20020                       # 投影符号 / 房间 / 3 位密码
    python seed.py MHS_MT01 707707                       # 3 个图案 + 房间 + 3 位密码
    python seed.py MHS_MT01 707707 --trace               # 附带抽取池与房间去重
    python seed.py TSR_MT01 695695                      # 字母数字位置 / 接线密码
    python seed.py FPI_MT01 335335                      # 放映机坐标 / 录像盘 / 图案
    python seed.py TFS_MT03 14014                       # 六阀门位置与坐标
    python seed.py SMC_MT02 453453                      # 4 个人偶下半身所在房间（按颜色）
    python seed.py SMC_MT02 453453 --trace              # 附带组洗牌与距离过滤过程
    python seed.py PSA_MT01 219219                      # 最短路径：每把钥匙 + 录像盘的房间与坐标
    python seed.py DTS_MT01 252252                      # 3 个调频器 / 3 条线索 / 最终模型
    python seed.py RES_MT02 176176                      # 水疗度假村：26 颗宝石（人偶 / 类别 / 坐标）
    python seed.py RES_MT02 69069 --tuto                # 再加教学段 51 人偶的类别图
    python seed.py RES_MT02 69069 --difficulty hard
    python seed.py FPI_MT02 189189 --json
    python seed.py --selftest

模块：
    seedcore.py   逆向出的随机原语（GetSeed / RandSeeded / RandBool / RandFraction / lookup3 mix …）
    gameshow.py   FPI_MT02 的 GameShow 模型
    mannequin.py  SMC_MT02 的人偶配对模型（分组/洗牌/距离过滤/抽取）
    seeddata.py   静态数据载入层（data/*.json → 同名常量）
    data/*.json   关卡候选池 / 名称映射 / 坐标 / 实测样本，可单独更新不改代码
"""
import argparse
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import seedcore as sc
import gameshow as gs
import cluegame as cg
import mannequin as mq
from seeddata import (
    ROOM_CENTERS,
    RES_MT02_COORDINATORS, RES_MT02_POOL,
    SAMPLES_CHJ, SAMPLES_CHJ_MT02, SAMPLES_RES, SAMPLES_SMC, SAMPLES_GS,
    SAMPLES_TSR, SAMPLES_FPI_MT01, SAMPLES_TFS, SAMPLES_MHS,
    SAMPLES_MHS_PICK, TFS_SAMPLE_ROOMS, SAMPLES_PSA, SAMPLES_SRR,
    SRR_HOUSES, SRR_HOUSE_ORDER, SRR_ROOM_COMPONENTS, SRR_ROOM_CENTERS,
    CHJ_MT02_COORDS, CHJ_MT02_ACTORS, CHJ_MT02_ROOMS_20020,
    CHJ_MT02_SYMBOL_NAMES, CHJ_MT02_SYMBOL_COORDS, CHJ_MT02_SYMBOL_ROOMS,
    MHS_SYMBOL_NAMES, MHS_ZONES, MHS_ZONE_BY_KEY,
    MHS_SYMBOLS, TSR_BUCKETS, TSR_BUCKET_NAMES, TSR_MANDATORY_ROOM,
    TSR_SPLIT_ROOMS, TSR_CLUE_COORDS, FPI_FIXED_PROJECTOR, FPI_GROUPS,
    FPI_SYMBOLS, FPI_SYMBOL_NAMES_ZH, FPI_PROJECTOR_COORDS,
    TFS_SECTION_ORDER, TFS_SECTIONS, TFS_VALVE_COORDS,
    PSA_SYMBOLS, PSA_SYMBOL_NAMES_ZH, PSA_START_ROOM, PSA_START_KEY,
    PSA_ROOM_POSITIONS, PSA_ROOM_SPAWNERS, PSA_FILM_REELS, PSA_ROOM_ALIASES,
)

# ---------------------------------------------------------------------------
# 关卡注册表
# ---------------------------------------------------------------------------
LEVELS = {
    'CHJ_MT01': {
        'name': '法院 · 让正义天平倾斜',
        'english': 'Tilt the Scales of Justice',
        'map': 'CourthouseJudicial',
        'kind': 'LargePuzzleRoom',
        'coordinator': 'MT01_LargePuzzleRoom_ObjCoord_BP_FullMap2',
        'sections': sc.CHJ_MT01_SECTIONS,
        'want': 3,
        'passcode': True,
        'digits': 4,
        'doc': 'release/home/CHJ_MT01.md',
    },
    'FPI_MT01': {
        'name': '游乐场 · 匹配录像盘与放映机',
        'english': 'Match film reels to the correct projectors',
        'map': 'FunParkIllusion',
        'kind': 'DiaporamaCode',
        'projectors': True,
        'doc': 'release/coop/FPI_MT01/FPI_MT01.md',
    },
    'TFS_MT03': {
        'name': '玩具工厂 · 开启六个阀门',
        'english': 'Gas the Factory',
        'map': 'ToyFactoryShipping',
        'kind': 'FirePump',
        'firepump': True,
        'partial': True,
        'doc': 'release/coop/TFS_MT03/TFS_MT03.md',
    },
    'FPI_MT02': {
        'name': '游乐场 · 在真人秀中幸存',
        'english': 'Survive the Game Show',
        'map': 'FunParkIllusion',
        'kind': 'GameShow',
        'coordinator': gs.COORDINATOR,
        'gameshow': True,
        'doc': 'release/coop/FPI_MT02/FPI_MT02.md',
    },
    'RES_MT01': {
        'name': '水疗度假村 · 推理谋杀案',
        'english': 'Murder Mystery (identify the killer, weapon, crime scene)',
        'map': 'ResortSpa',
        'kind': 'ClueGame',
        'coordinator': cg.COORDINATOR,
        'cluegame': True,
        'doc': 'release/coop/RES_MT01/RES_MT01.md',
    },
    'CHJ_MT02': {
        'name': '法院 · 判决被起诉者',
        'english': 'Sentence the Prosecuted',
        'map': 'CourthouseJudicial',
        'kind': 'ProjectionCode',
        'projection': True,
        'partial': True,
        'doc': 'release/coop/CHJ_MT02/CHJ_MT02.md',
    },
    'MHS_MT01': {
        'name': '黑帮据点 · 找到 3 个投影房间',
        'english': 'Find the 3 projection rooms and enter the codes',
        'map': 'MobsterHideoutSyndicate',
        'kind': 'ProjectionsMobster',
        'coordinator': 'MT01_Projections_Coordinator_BP_DrugLab',
        'mhs': True,
        'doc': 'release/home/MHS_MT01.md',
    },
    'SMC_MT02': {
        'name': '商场 · 4 个人偶按颜色配对下半身',
        'english': 'Reunite the mannequins (match each torso to its legs by color)',
        'map': 'ShoppingMallCarrefour',
        'kind': 'GatherAndDeliverMannequin',
        'coordinator': mq.COORDINATOR,
        'mannequin': True,
        'doc': 'release/coop/SMC_MT02/SMC_MT02.md',
    },
    'PSA_MT01': {
        'name': '警察局阁楼 · 图案钥匙与录像盘',
        'english': 'Open the symbol-locked rooms and recover the film reel',
        'map': 'PoliceStationAttic',
        'kind': 'KeyLockedRooms',
        'keylockedrooms': True,
        'doc': 'release/coop/PSA_MT01/PSA_MT01.md',
    },
    'TSR_MT01': {
        'name': '电视台屋顶 · 密码接线面板',
        'english': 'Switchboard',
        'map': 'TelevisionStudioRooftop',
        'kind': 'SwitchBoard',
        'switchboard': True,
        'doc': 'release/coop/TSR_MT01/TSR_MT01.md',
    },
    'DTS_MT01': {
        'name': '闹市区 · 调频线索与目标人体模型',
        'english': 'Use Clues to Locate and Return the Right Mannequin',
        'map': 'DowntownSewer',
        'kind': 'FrequencyClues',
        'dts': True,
        'partial': True,
        'doc': 'release/coop/DRS_MT01/DRS_MT01.md',
    },
    'RES_MT02': {
        'name': '水疗度假村 · 焚毁莉莉娅的遗物',
        'english': "Burn Liliana's Relics",
        'map': 'ResortSpa',
        'kind': 'CollectJewels',
        'jewels': True,
        'partial': True,     # 教学段「哪 6 个人偶」未解
        'coordinator': 'MT02_CollectingJewels_MainAuction',
        'doc': 'release/home/RES_MT02.md',
    },
    'SRR_MT01': {
        'name': '郊区住宅区 · 撬开富豪宅的密码盘',
        'english': 'Crack the keypads of the rich houses',
        'map': 'SuburbRiotResidential',
        'kind': 'MultiroomPuzzle',
        'puzzle': True,
        'doc': 'release/home/SRR_MT01.md',
    },
    'CHJ_MT03': {
        'name': '法院 · 贿赂其余可收买的法官',
        'map': 'CourthouseJudicial',
        'kind': 'MiniTrial',
        'sections': None,
        'todo': '同上',
    },
}

ALIASES = {
    'CHJ': 'CHJ_MT01', 'MT01': 'CHJ_MT01', 'CHJ-MT01': 'CHJ_MT01',
    'TILT': 'CHJ_MT01',
    'FPI': 'FPI_MT02', 'MT02': 'FPI_MT02', 'GAMESHOW': 'FPI_MT02',
    'SHOW': 'FPI_MT02',
    'RES': 'RES_MT01', 'SPA': 'RES_MT01', 'MURDER': 'RES_MT01',
    'CLUE': 'RES_MT01',
    'TSR': 'TSR_MT01', 'SWITCHBOARD': 'TSR_MT01',
    'FPI1': 'FPI_MT01', 'DIAPORAMA': 'FPI_MT01',
    'TFS': 'TFS_MT03', 'VALVES': 'TFS_MT03',
    'MHS': 'MHS_MT01', 'MOBSTER': 'MHS_MT01', 'SYNDICATE': 'MHS_MT01',
    'PROJECTION': 'MHS_MT01',
    'SMC': 'SMC_MT02', 'SMC2': 'SMC_MT02', 'MANNEQUIN': 'SMC_MT02',
    'MANNEQUINS': 'SMC_MT02', 'MALL': 'SMC_MT02', 'CARREFOUR': 'SMC_MT02',
    'DTS': 'DTS_MT01', 'DRS': 'DTS_MT01', 'DRS_MT01': 'DTS_MT01',
    'DOWNTOWN': 'DTS_MT01', 'DOWNTOWNSEWER': 'DTS_MT01',
    'PSA': 'PSA_MT01', 'POLICE': 'PSA_MT01', 'ATTIC': 'PSA_MT01',
    'POLICESTATION': 'PSA_MT01', 'KEYLOCKED': 'PSA_MT01',
    'RES2': 'RES_MT02', 'RES-MT02': 'RES_MT02', 'JEWEL': 'RES_MT02',
    'JEWELS': 'RES_MT02', 'RELIC': 'RES_MT02', 'LILIANA': 'RES_MT02',
    'SRR': 'SRR_MT01', 'SUBURB': 'SRR_MT01', 'HOUSES': 'SRR_MT01',
    'KEYPAD': 'SRR_MT01', 'KEYPADS': 'SRR_MT01', 'MULTIROOM': 'SRR_MT01',
}

# ---------------------------------------------------------------------------
# 关卡静态数据
# ---------------------------------------------------------------------------
# 候选池 / 名称映射 / 坐标 / 实测样本都在 data/*.json，由 seeddata.py 载入；
# 这里只留下与算法写在一起才看得懂的参数（名字链、路径开关、salt）。
#
#   data/mhs_mt01.json        MHS_MT01 图案家族 + 投影符号候选表（0x1436E95F0 的输入）
#   data/tsr_mt01.json        TSR_MT01 候选桶 / 桶名 / 强制房间 / 码位坐标
#   data/fpi_mt01.json        FPI_MT01 三组候选 / 图案表 / 放映机坐标
#   data/tfs_mt03.json        TFS_MT03 Sections 原始顺序 / 阀门候选 / 坐标
#   data/chj_mt02.json        CHJ_MT02 协调器组 / 符号 actor / 房间
#   data/psa_mt01.json        PSA_MT01 图案表 / 房间生成点 / 录像盘
#   data/srr_mt01.json        SRR_MT01 协调器 Sections / 房间组件 / 密码盘坐标
#   data/room_centers.json    各 map 的房间中心参考点
#   data/samples.json         全部 --selftest 实测样本
# ---------------------------------------------------------------------------


# MHS_MT01：投影符号 actor 名 = MT01_ProjectionSymbol_BP_<区>_<候选序号>
MHS_SYMBOL_PREFIX = 'MT01_ProjectionSymbol_BP_'
# 「10 选 1」= 通用引擎 sub_1402B05C0：base = crc32_fname(盐名) + GetSeed(协调器) + 偏移。
# 盐名是引擎在「显式候选列表非空」分支上用的那个（宽串 @0x14665E230），不是任务名；
# DesiredCount 恒为 1，只抽一次，所以偏移恒为 0。
MHS_PICK_SALT = 'Projection Actors'
MHS_PICK_OFFSET = 0

# TSR_MT01：候选顺序来自 TSR_LD_MT01_B00，删除语义为 RemoveAtSwap。
TSR_ACTOR_PREFIX = 'MT01_Clue_BlackLightable_SwitchBoard_BP_'
TSR_PANEL_CHAIN = ['PersistentLevel', 'MT01_SwitchesBoard_Base_BP_Studio5',
                   'SwitchBoard_PanelComponent_BP']
# 候选桶（池顺序 = RemoveAtSwap 删除顺序）、桶名、强制房间与码位坐标见 data/tsr_mt01.json

# FPI_MT01：候选顺序来自 FunParkIllusion_B00；坐标为放映机 RootComponent。
FPI_COORDINATOR_CHAIN = ['PersistentLevel', 'MT01_GatherAndDeliver_Simple_BP']
FPI_SINGLE_CODE_CHAIN = ['PersistentLevel', 'MT01_SingleCode_ObjCoord_BP']
# 分组候选、图案表与放映机坐标见 data/fpi_mt01.json

# TFS_MT03：原始 Sections[].Valves 顺序；第二次抽取基于 RemoveAtSwap 后的池。
# 阀门候选表、Sections 原始顺序与坐标见 data/tfs_mt03.json。
# 下面这条是「第二次抽取还是第一次抽取生效」的路径选择，只有一条实测样本支撑：
TFS_MAIN_SECOND = {'A1', 'B2', 'B3'}  # 仅由 seed=14014 样本确定，见 partial 标记。

# PSA_MT01：7 节点钥匙树（节点 1 起始，4..7 是叶子），录像盘随机落在某个叶子房。
# 0x143582F60  节点图案   RandSeeded(38322 + node)；先用 45834 起连续弃牌把 10 → 8。
# 0x143583800  父房钥匙生成点 RandSeeded(320239 + node)（在该房的两个生成点里抽）。
# 0x143583530  下一个钥匙房 RandSeeded(38342 + node + attempt)，
#              距离 < MinDistanceBetweenKeyAndRoom 就重抽（最多 20 次）。
# 0x1435820D0  录像盘叶子 RandSeeded(98639, 4)（seed 常量由折叠的 hash 反解得到）。
# 距离用的是 RBRoom 的 Brush 根坐标，不是生成点/录像盘自己的坐标。
PSA_DROP_SEED_BASE = 45834
PSA_SYMBOL_SEED_BASE = 38322
PSA_SPAWN_SEED_BASE = 320239
PSA_ROOM_SEED_BASE = 38342
PSA_FILM_SEED = 98639
PSA_MIN_DISTANCE = 2000.0  # KeyLockedRooms_ObjCoord_BP_2.MinDistanceBetweenKeyAndRoom

DTS_PANEL_COORDINATOR = 'DRS_MT01_Frequency_ObjCoord_BP2'
DTS_PANELS = [
    ('FrequencyMatchPanel_DTS_Child10_14', 'Garage', (3939.4, 9602.3, 400.0)),
    ('FrequencyMatchPanel_DTS_Child11_37', 'Sewer_MainCorridor_Slave02', (5188.8, 7904.4, -333.8)),
    ('FrequencyMatchPanel_DTS_Child12_11', 'Room-22-7', (5154.2, 10984.2, -350.0)),
    ('FrequencyMatchPanel_DTS_Child13_2', 'Room-22-7', (5932.3, 10651.7, -352.6)),
    ('FrequencyMatchPanel_DTS_Child14_5', 'Room-12-27', (3364.8, 7632.8, -335.0)),
    ('FrequencyMatchPanel_DTS_Child16_2', 'Room-8-3', (3392.0, 8747.6, -335.0)),
    ('FrequencyMatchPanel_DTS_Child15_8', 'Room-14-33 (Electric Room)', (2245.5, 10193.1, -335.0)),
    ('FrequencyMatchPanel_DTS_Child17_2', 'Store (Photo-Booth)', (2289.9, 10110.1, 50.0)),
    ('FrequencyMatchPanel_DTS_Child18_5', 'MotelCommonBathroom', (3175.6, 11643.0, 350.0)),
    ('FrequencyMatchPanel_DTS_Child19_8', 'MotelRoom101', (4698.7, 11668.8, 350.2)),
    ('FrequencyMatchPanel_DTS_Child20_14', 'UppSewer_CorridorRightGenerator_01', (7883.0, 13041.6, -0.1)),
    ('FrequencyMatchPanel_DTS_Child21_17', 'BankVault', (7483.6, 11481.5, 15.0)),
    ('FrequencyMatchPanel_DTS_Child22', 'Room-12-27', (4475.6, 7060.5, -335.0)),
    ('FrequencyMatchPanel_DTS_Child23', 'MotelLaundry_Master', (6520.2, 11707.5, 350.5)),
    ('FrequencyMatchPanel_DTS_Child2_5', 'Garage', (4252.0, 8777.2, 400.0)),
    ('FrequencyMatchPanel_DTS_Child4_2', 'WorkerFashion_Master', (6302.7, 9963.7, 400.0)),
    ('FrequencyMatchPanel_DTS_Child5_5', 'Room-10-21', (6790.7, 8089.1, -335.0)),
    ('FrequencyMatchPanel_DTS_Child6_8', 'Room-9-18', (5863.3, 7208.4, -335.0)),
    ('FrequencyMatchPanel_DTS_Child9_26', 'Room-26-6', (3110.6, 8425.9, 500.0)),
]
DTS_SAMPLES = {
    252252: {
        'weapon_code': 'A1',
        'weapon': 'CHAINSAW',
        'room': 'IRISH PUB',
        'clue_room': 'RBRoom_Pub_Master',
        'target_actor': 'DTR_MT01_ManneqinSetup_Chainsaw_BP3_13',
        'target_room': 'RBRoom_Pub_Slave01',
        'target_coordinates': (6840.0, 8853.5, 350.0),
    },
    61061: {
        'weapon_code': 'B2',
        'weapon': 'SCYTHE',
        'room': 'GARAGE',
        'clue_room': 'RBRoom_Garage',
        'target_actor': 'DTR_MT01_ManneqinSetup_Scythe_BP5_5',
        'target_room': 'RBRoom_Garage',
        'target_coordinates': (4610.1, 9922.8, 15.0),
    },
}
DTS_PANEL_SAMPLES = {
    252252: ('FrequencyMatchPanel_DTS_Child17_2',
             'FrequencyMatchPanel_DTS_Child20_14',
             'FrequencyMatchPanel_DTS_Child15_8'),
    61061: ('FrequencyMatchPanel_DTS_Child9_26',
            'FrequencyMatchPanel_DTS_Child5_5',
            'FrequencyMatchPanel_DTS_Child17_2'),
}

# RES_MT02：主轴段 0x1433B49B0 / 教学段 0x1433B5BC0（见 release/home/RES_MT02.md）
# 四个 seed 常量是硬编码在 0x1433B49B0 里的偏移，直接调 RandSeeded/RandRangeInt/RandFraction。
RES_MT02_MAIN = 'MT02_CollectingJewels_MainAuction'
RES_MT02_TUTO = 'MT02_CollectingJewels_Tuto'
RES_SEED_MANDATORY = 820351        # 0x1433B4B81  pick_spawner(counter + 820351)
RES_SEED_SECTION_SPAWNER = 279412  # 0x1433B506C  pick_spawner(counter + 279412)
RES_SEED_ROOM_ORDER = 479582       # 0x1433B4F6D  RandFraction(GetSeed(room) + 479582)
RES_SEED_CLASS_PICK = 823203       # 0x1433B50BF  RandRangeInt(counter + 823203, 0, len-1)
RES_GEM_CN = {'Ruby': '红宝石', 'Sapphire': '蓝宝石', 'Emerald': '绿宝石'}

# 主轴段实测：人偶 → 宝石类别（seed=176176，2/2 命中）
RES_MT02_SAMPLES = {
    176176: [
        ('RE_MannequinTrap_Setup_BP160', 'Ruby'),
        ('RE_MannequinTrap_Setup_BP_295', 'Sapphire'),
    ],
}
# 教学段实测：(seed, 人偶, 颜色) 8 条，BP_139 两局都与模型相反，单独记录不计分
RES_MT02_TUTO_SAMPLES = [
    (176176, 'RE_MannequinTrap_Tutorial_BP_96', 'Emerald'),
    (176176, 'RE_MannequinTrap_Tutorial_BP_106', 'Sapphire'),
    (176176, 'RE_MannequinTrap_Tutorial_BP_111', 'Sapphire'),
    (69069, 'RE_MannequinTrap_Tutorial_BP_106', 'Sapphire'),
    (69069, 'RE_MannequinTrap_Tutorial_BP_115', 'Sapphire'),
    (69069, 'RE_MannequinTrap_Tutorial_BP_84', 'Emerald'),
    (69069, 'RE_MannequinTrap_Tutorial_BP_117', 'Emerald'),
    (69069, 'RE_MannequinTrap_Tutorial_BP_109', 'Emerald'),
]


def _tsr_room(name):
    if name.startswith('Tutorial_'):
        return 'Studio5'
    markers = [('_Rooftop_', 'Rooftop'), ('_Studio3_', 'Studio3'),
               ('_Studio_4_', 'Studio4'), ('_AudioVisual_', 'Audiovisual'),
               ('_Office_', 'Offices'), ('_Storage_', 'Storage')]
    for marker, room in markers:
        if marker in name:
            return room
    raise ValueError('未知 TSR 码位房间：' + name)


def _tsr_swap_remove(items, index):
    items[index] = items[-1]
    items.pop()


def _tsr_candidates(original, excluded, used_rooms, mandatory, split_rooms):
    candidates = list(enumerate(original))
    for name in excluded:
        for index, (_, candidate) in enumerate(candidates):
            if candidate == name:
                _tsr_swap_remove(candidates, index)
                break
    for index in range(len(candidates) - 1, -1, -1):
        room = _tsr_room(candidates[index][1])
        if (mandatory and room != mandatory) or (
                not mandatory and split_rooms and room in used_rooms):
            _tsr_swap_remove(candidates, index)
    return candidates


def _predict_tsr_mt01(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    panel_seed = sc.seed_chain(TSR_PANEL_CHAIN)
    remaining_buckets = list(range(len(TSR_BUCKETS)))
    used_letters, used_numbers = [], []
    used_rooms, used_groups = set(), set()
    connections, direct_numbers = [], []

    for round_index, remaining in enumerate((3, 2, 1)):
        pick = sc.rand_seeded(panel_seed + 124 + remaining,
                              len(remaining_buckets), level_seed)
        bucket_index = remaining_buckets[pick]
        _tsr_swap_remove(remaining_buckets, pick)
        original = TSR_BUCKETS[bucket_index]
        chosen = []
        for half in range(2):
            excluded = used_letters + used_numbers
            if half:
                excluded = [original[chosen[0]]] + excluded
            candidates = _tsr_candidates(
                original, excluded, used_rooms,
                TSR_MANDATORY_ROOM[bucket_index] if half == 0 else None,
                TSR_SPLIT_ROOMS[bucket_index])
            if not candidates:
                raise RuntimeError('TSR_MT01 候选池为空')
            pick = sc.rand_seeded(panel_seed + 523 + 2 * round_index + half,
                                  len(candidates), level_seed)
            original_index, name = candidates[pick]
            chosen.append(original_index)
            used_rooms.add(_tsr_room(name))

        if TSR_MANDATORY_ROOM[bucket_index] and sc.rand_bool(
                remaining + panel_seed + 58507, level_seed):
            chosen.reverse()
        number_name = original[chosen[0]]
        letter_name = original[chosen[1]]
        used_numbers.append(number_name)
        used_letters.append(letter_name)

        code_seed = panel_seed + 535 - round_index + min(chosen)
        groups = [group for group in range(3) if group not in used_groups]
        group = groups[sc.rand_seeded(code_seed + 4431, len(groups), level_seed)]
        used_groups.add(group)
        input_col = sc.rand_seeded(code_seed + 33898, 5, level_seed)
        output_col = sc.rand_seeded(code_seed + 9872, 5, level_seed)
        direct_letter = chr(ord('A') + 5 * group + input_col)
        direct_number = '%02d' % (10 * group + output_col + 1)
        direct_numbers.append(direct_number)
        connections.append({
            'round': round_index + 1,
            'bucket': TSR_BUCKET_NAMES[bucket_index],
            'bucket_index': bucket_index,
            'candidate_indices': chosen,
            'letter_actor': TSR_ACTOR_PREFIX + letter_name,
            'letter_room': _tsr_room(letter_name),
            'letter_coordinates': TSR_CLUE_COORDS[TSR_ACTOR_PREFIX + letter_name],
            'number_actor': TSR_ACTOR_PREFIX + number_name,
            'number_room': _tsr_room(number_name),
            'number_coordinates': TSR_CLUE_COORDS[TSR_ACTOR_PREFIX + number_name],
            'coordinate_type': 'actor',
            'direct_letter': direct_letter,
            'direct_number': direct_number,
            'code_seed': code_seed & sc.M32,
            'group': group,
            'input_column': input_col,
            'output_column': output_col,
        })

    rotation = sc.rand_seeded_range(panel_seed + 60121, 1,
                                    len(connections) - 1, level_seed)
    for index, connection in enumerate(connections):
        connection['number'] = direct_numbers[(index + rotation) % len(connections)]
        connection['letter'] = connection['direct_letter']
        connection['code'] = connection['letter'] + '-' + connection['number']
        if trace:
            print('  TSR round=%d bucket=%s indices=%s code_seed=%d '
                  'group=%d cols=%d/%d direct=%s final=%s'
                  % (connection['round'], connection['bucket'],
                     connection['candidate_indices'], connection['code_seed'],
                     connection['group'], connection['input_column'],
                     connection['output_column'],
                     connection['direct_letter'] + '-' + connection['direct_number'],
                     connection['code']))
    return {
        'panel_seed': panel_seed,
        'number_rotation': rotation,
        'connections': connections,
        'codes': [connection['code'] for connection in connections],
    }


def _predict_fpi_mt01(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    coordinator_seed = sc.seed_chain(FPI_COORDINATOR_CHAIN)
    selection_seed = (sc.crc32_fname('Objective Actors') + coordinator_seed) & sc.M32
    single_code_seed = sc.seed_chain(FPI_SINGLE_CODE_CHAIN)
    group_order = list(range(3))
    shuffled_order = []
    for index in range(3):
        pick = sc.rand_seeded(selection_seed + index, len(group_order), level_seed)
        shuffled_order.append(group_order[pick])
        _tsr_swap_remove(group_order, pick)

    selected = []
    selected_count = 1
    for group_index in shuffled_order:
        candidates = FPI_GROUPS[group_index]
        pick = sc.rand_seeded(selection_seed + 3 + selected_count,
                              len(candidates), level_seed)
        actor, room = candidates[pick]
        selected.append({'actor': actor, 'room': room,
                         'objective_index': group_index, 'candidate_index': pick})
        selected_count += 1

    assignment_order = [dict(FPI_FIXED_PROJECTOR)] + list(reversed(selected))
    projectors = []
    for index, projector in enumerate(assignment_order):
        symbol_index = sc.rand_seeded(single_code_seed + index,
                                      len(FPI_SYMBOLS), level_seed)
        symbol = FPI_SYMBOLS[symbol_index]
        item = dict(projector)
        item.update({
            'reel_index': index + 1,
            'symbol': symbol,
            'symbol_name_zh': FPI_SYMBOL_NAMES_ZH[symbol],
            'symbol_index': symbol_index,
            'coordinates': FPI_PROJECTOR_COORDS[item['actor']],
            'coordinate_type': 'actor',
        })
        projectors.append(item)
        if trace:
            print('  FPI1 reel=%d group=%d candidate=%s room=%s symbol=%s xyz=%s'
                  % (item['reel_index'], item['objective_index'],
                     item.get('candidate_index', 'fixed'), item['room'], symbol,
                     item['coordinates']))
    return {
        'coordinator_seed': coordinator_seed,
        'selection_seed': selection_seed,
        'single_code_seed': single_code_seed,
        'group_order': shuffled_order,
        'projectors': projectors,
        'codes': ['%d:%s' % (p['reel_index'], p['symbol']) for p in projectors],
    }


def _tfs_candidate(section, index, path):
    suffix, room = TFS_SECTIONS[section][index]
    actor = 'MT03_TF_Gas_ValvePanel_BP_Section_' + section + '_' + suffix
    return {'actor': actor, 'room': room, 'candidate_index': index, 'path': path,
            'coordinates': TFS_VALVE_COORDS[actor], 'coordinate_type': 'actor'}


def _predict_tfs_mt03(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    valves = []
    for section in TFS_SECTION_ORDER:
        coordinator = 'MT03_FirePump_ObjCoord_BP_Section' + section
        coordinator_seed = sc.seed_chain(['PersistentLevel', coordinator])
        count = len(TFS_SECTIONS[section])
        first_index = sc.rand_seeded(coordinator_seed + 61390, count, level_seed)
        remaining = list(range(count))
        remaining[first_index] = remaining[-1]
        remaining.pop()
        second_pick = sc.rand_seeded(coordinator_seed + 39135,
                                     len(remaining), level_seed)
        second_index = remaining[second_pick]
        use_second = section in TFS_MAIN_SECOND
        selected_index = second_index if use_second else first_index
        selected = _tfs_candidate(section, selected_index,
                                  '39135' if use_second else '61390')
        selected.update({'section': section, 'coordinator_seed': coordinator_seed,
                         'preselect_index': first_index, 'main_index': second_index,
                         'main_pool_index': second_pick})
        valves.append(selected)
        if trace:
            first = _tfs_candidate(section, first_index, '61390')
            second = _tfs_candidate(section, second_index, '39135')
            print('  TFS %s seed=%d 61390=%s 39135=%s selected=%s xyz=%s'
                  % (section, coordinator_seed, first['actor'], second['actor'],
                     selected['actor'], selected['coordinates']))
    return {
        'valves': valves,
        'notes': ['TFS_MT03 的有效路径仅由 seed=14014 单样本确定；'
                  '其他 seed 需用新实测复核 TFS_MAIN_SECOND。'],
    }


# 仅预测到房间时，附房间中心参考点；具体 actor 使用上面的精确坐标。


def _attach_room_coordinates(item, map_name, room_key='room'):
    room = item.get(room_key)
    coordinates = ROOM_CENTERS.get(map_name, {}).get(room)
    if coordinates is not None:
        item['coordinates'] = coordinates
        item['coordinate_type'] = 'room_center'
    return item


def resolve(level_id):
    key = (level_id or '').upper().replace('_', '-')
    key = key.replace('-', '_')
    if key in LEVELS:
        return key
    alias = ALIASES.get(key) or ALIASES.get(key.replace('_', ''))
    if alias:
        return alias
    raise KeyError(level_id)


def _chj_mt02_draw_code(base, level_seed):
    """sub_1436EA3D0：三位数字池抽签，使用末尾交换删除。"""
    pool = list(range(10))
    digits = []
    for k in range(3):
        index = sc.rand_seeded((base + 38541 + k) & sc.M32,
                               len(pool), level_seed)
        digits.append(str(pool[index]))
        pool[index] = pool[-1]
        pool.pop()
    return ''.join(digits)


def _predict_chj_mt02(level_seed):
    actors = CHJ_MT02_ACTORS.get(level_seed)
    if actors is None:
        return [], [
            'CHJ_MT02 的前置候选过滤/补位尚未泛化；当前只接入了已验证的 '
            '713713、620620、20020，未对该 seed 输出未经验证的房间或密码。'
        ]

    level_crc = sc.crc32_fname('PersistentLevel')
    rooms = CHJ_MT02_ROOMS_20020 if level_seed == 20020 else {}
    projections = []
    for coord_name, groups, tutorial in CHJ_MT02_COORDS:
        clues = list(groups)
        coord_seed = sc.seed_of_object(coord_name, level_crc)
        for i in range(len(groups)):
            group_index = sc.rand_seeded(i + 46541, len(clues), level_seed)
            group = clues[group_index]
            actor = actors[group]
            base = (sc.seed_of_object(actor, level_crc) + coord_seed + i) & sc.M32
            projections.append({
                'symbol': group,
                'symbol_name': CHJ_MT02_SYMBOL_NAMES[group],
                'room': rooms.get(group) or CHJ_MT02_SYMBOL_ROOMS.get(actor),
                'actor': actor,
                'coordinates': CHJ_MT02_SYMBOL_COORDS.get(actor),
                'coordinate_type': 'actor',
                'code': _chj_mt02_draw_code(base, level_seed),
                'tutorial': tutorial,
            })
            clues[group_index] = clues[-1]
            clues.pop()
    return projections, []


def _mhs_pattern(zone, level_seed, slot=0):
    """0x1436E95F0：先抽 clue 组 RandSeeded(slot + 46541, |PossibleClueGroups|)。"""
    groups = zone[2]
    if isinstance(groups, str):
        return groups
    return groups[sc.rand_seeded(slot + 46541, len(groups), level_seed)]


def _mhs_symbol_name(zone_key, short):
    return MHS_SYMBOL_PREFIX + zone_key + '_' + short


def _mhs_code(coord_name, symbol_name, level_seed, slot=0):
    """0x1436EA3D0：base = GetSeed(符号) + GetSeed(协调器) + slot。

    三个协调器的 CodeProjectorsRandomizationSetup.DesiredCount 都是 1，所以 slot 恒为 0。
    """
    level_crc = sc.crc32_fname('PersistentLevel')
    base = (sc.seed_of_object(symbol_name, level_crc) +
            sc.seed_of_object(coord_name, level_crc) + slot) & sc.M32
    return _chj_mt02_draw_code(base, level_seed)


def _mhs_pool(zone_key, limit_one_per_room):
    """抽取池 = data 里的候选表（已是关卡 actor 顺序），必要时先按房间去重。

    sub_1402B3C30：三个协调器的 DistanceBetween*Objectives 都是 bOverride=true 但没给
    值 → 距离阈值 v5 <= 0 → 跳过距离分支，落到 `sub_140B3BE80(coord, cand)`
    → `RemoveAt(pool, i, 1)` 那个循环，把「和已保留候选共房间」的候选删掉
    （bLimitOneObjectivePerRoom）。本关只有 TrainDepot 开了这条：
    _1/_9 同在 RBRoom_Train_Bridge_02、_7/_8 同在 RBRoom_Train_Room_03，
    保留靠前者 → 池 10 → 8，RandSeeded 的模也随之从 10 变 8。
    """
    candidates = MHS_SYMBOLS[zone_key]
    if not limit_one_per_room:
        return list(candidates), []
    kept, seen, dropped = [], set(), []
    for row in candidates:
        if seen & set(row[4]):
            dropped.append(row[0])
            continue
        seen |= set(row[4])
        kept.append(row)
    return kept, dropped


def _predict_mhs_mt01(level_seed, trace=False):
    salt_crc = sc.crc32_fname(MHS_PICK_SALT)
    level_crc = sc.crc32_fname('PersistentLevel')
    patterns = []
    for zone_key, coord_name, _clue_groups, limit_one in MHS_ZONES:
        pool, dropped = _mhs_pool(zone_key, limit_one)
        base = (salt_crc + sc.seed_of_object(coord_name, level_crc)
                + MHS_PICK_OFFSET) & sc.M32
        index = sc.rand_seeded(base, len(pool), level_seed)
        short, texture, room, coordinates, _rooms = pool[index]
        pattern = _mhs_pattern(MHS_ZONE_BY_KEY[zone_key], level_seed)
        actor = _mhs_symbol_name(zone_key, short)
        patterns.append({
            'zone': zone_key,
            'pattern': pattern,
            'pattern_name': MHS_SYMBOL_NAMES[pattern],
            'texture': texture,
            'candidate_index': index,
            'pool_size': len(pool),
            'actor': actor,
            'room': room,
            'coordinates': list(coordinates),
            'coordinate_type': 'actor',
            'code': _mhs_code(coord_name, actor, level_seed),
        })
        if trace:
            print('  MHS %-11s base=%d idx=%d/%d -> %s 图案=%s 密码=%s%s'
                  % (zone_key, base, index, len(pool), actor, pattern,
                     patterns[-1]['code'],
                     '  (房间去重剔除 #%s)' % ',#'.join(dropped) if dropped else ''))
    return {'patterns': patterns}


class ModelUnresolved(RuntimeError):
    """模型命中已知的数据缺口：宁可报错也不输出未验证的结果。"""


def _psa_room(room):
    """内部 RBRoom 名 → 玩家/点位图用的显示名。"""
    return PSA_ROOM_ALIASES.get(room, room)


def _psa_distance(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _psa_swap_remove(items, index):
    item = items[index]
    items[index] = items[-1]
    items.pop()
    return item


def _psa_draw_symbols(level_seed):
    """0x143582F60：10 个图案先弃到 8 个，再按节点 1..7 各抽 1 个。"""
    pool = list(PSA_SYMBOLS)
    seed = PSA_DROP_SEED_BASE
    while len(pool) > 8:
        _psa_swap_remove(pool, sc.rand_seeded(seed, len(pool), level_seed))
        seed += 1
    nodes = {}
    for node in range(1, 8):
        nodes[node] = _psa_swap_remove(
            pool, sc.rand_seeded(PSA_SYMBOL_SEED_BASE + node, len(pool), level_seed))
    return nodes


def _psa_draw_rooms(level_seed, trace=False):
    """0x1435820D0：节点 2..7 各选一个「未用过且离当前钥匙 ≥ 2000」的钥匙房。"""
    candidates = sorted((room for room in PSA_ROOM_POSITIONS
                         if room != PSA_START_ROOM), key=str.casefold)
    spawner_pools = {room: [dict(item) for item in items]
                     for room, items in PSA_ROOM_SPAWNERS.items()}
    rooms = {1: PSA_START_ROOM}
    key_spawns = {1: dict(PSA_START_KEY)}

    for node in range(2, 8):
        parent = rooms[node // 2]
        spawners = spawner_pools[parent]
        if not spawners:
            # 每个钥匙房都有 2 个生成点（停尸房第二个在 PSA_LD_Items 子关卡），
            # 正常不会走到这里；真出现说明 room_spawners 数据的点数不够。
            raise ModelUnresolved(
                'PSA_MT01：%s 的生成点池已耗尽，但该 seed 还要在这个房间再出一把钥匙。'
                '请检查 data/psa_mt01.json 的 room_spawners（每个房应有 2 个点）' % parent)
        spawn = _psa_swap_remove(
            spawners, sc.rand_seeded(PSA_SPAWN_SEED_BASE + node, len(spawners),
                                     level_seed))
        key_spawns[node] = spawn

        temporary = list(candidates)
        selected = None
        for attempt in range(20):
            index = sc.rand_seeded(PSA_ROOM_SEED_BASE + node + attempt,
                                   len(temporary), level_seed)
            room = temporary[index]
            distance = _psa_distance(spawn['coordinates'],
                                     PSA_ROOM_POSITIONS[room])
            if trace:
                print('  PSA node=%d parent=%s key=%s attempt=%d seed=%d index=%d '
                      'room=%s distance=%.3f'
                      % (node, parent, spawn['actor'], attempt,
                         PSA_ROOM_SEED_BASE + node + attempt, index, room,
                         distance))
            if distance >= PSA_MIN_DISTANCE:
                selected = room
                break
            _psa_swap_remove(temporary, index)  # RemoveAtSwap
        if selected is None:
            raise ModelUnresolved('PSA_MT01：节点 %d 连续 20 次都没抽到距离 ≥ %g 的房间'
                                  % (node, PSA_MIN_DISTANCE))
        candidates.remove(selected)
        rooms[node] = selected
    return rooms, key_spawns


def _predict_psa_mt01(level_seed, trace=False):
    """最短路径 = 录像盘所在叶子的钥匙依赖链（不含固定的起始眼睛钥匙）。"""
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    symbols = _psa_draw_symbols(level_seed)
    rooms, key_spawns = _psa_draw_rooms(level_seed, trace=trace)
    film_node = 4 + sc.rand_seeded(PSA_FILM_SEED, 4, level_seed)

    path_nodes = []
    node = film_node
    while node:
        path_nodes.append(node)
        node //= 2
    path_nodes.reverse()

    path = []
    for node in path_nodes:
        if node == 1:
            continue  # 节点 1 的眼睛钥匙位置固定，不算一步
        spawn = key_spawns[node]
        path.append({
            'symbol': symbols[node],
            'symbol_name_zh': PSA_SYMBOL_NAMES_ZH[symbols[node]],
            'room': _psa_room(rooms[node // 2]),  # 钥匙在父房里拿到
            'coordinates': list(spawn['coordinates']),
            'coordinate_type': 'actor',
            'actor': spawn['actor'],
            'kind': 'key',
            'opens_room': _psa_room(rooms[node]),
        })
    reel = PSA_FILM_REELS[rooms[film_node]]
    path.append({
        'symbol': 'FilmReel',
        'symbol_name_zh': PSA_SYMBOL_NAMES_ZH['FilmReel'],
        'room': _psa_room(rooms[film_node]),
        'coordinates': list(reel['coordinates']),
        'coordinate_type': 'actor',
        'actor': reel['actor'],
        'kind': 'film_reel',
    })
    return {'path': path, 'film_node': film_node}


def _res_conf(coordinator):
    return RES_MT02_COORDINATORS[coordinator]


def _res_mandatory_rooms():
    return [(m['room'], m['count'])
            for m in _res_conf(RES_MT02_MAIN)['mandatory_rooms']]


def _res_sections():
    return [{'count': s['count'], 'rooms': list(s['rooms'])}
            for s in _res_conf(RES_MT02_MAIN)['sections']]


def _res_distribution(coordinator=RES_MT02_MAIN):
    """ItemClassesDistributionDataOrderedByPrice：顺序 = 数组顺序（别排序）。

    主轴段是 红 0.2 / 蓝 0.5 / 绿 0.3，教学段只有 蓝 0.6 / 绿 0.4。
    """
    return [(d['class'].replace('_BP_C', '').replace('RE_', ''), d['value'])
            for d in _res_conf(coordinator)['distributions']]


def _res_pool(classes=('main',)):
    return [m for m in RES_MT02_POOL if m['pool'] in classes]


def _res_uid(m):
    """同名 actor 可能出现在不同子关卡，去重要带 level。"""
    return '%s:%s' % (m['level'], m['name'])


def _res_gem_point(m):
    """宝石挂点 = 人偶根 + ItemSpawnLocation（按 yaw 绕 Z 旋转）。"""
    offset = m.get('spawn_offset')
    if not offset:
        return (m['x'], m['y'], m['z'])
    ox, oy, oz = offset
    th = math.radians(m.get('yaw') or 0.0)
    c, s = math.cos(th), math.sin(th)
    return (round(m['x'] + ox * c - oy * s, 1),
            round(m['y'] + ox * s + oy * c, 1),
            round(m['z'] + oz, 1))


def _res_candidates(room, used=(), classes=('main',)):
    """房间里还没被占用的人偶，顺序 = (level, name)（近似关卡 actor 顺序）。"""
    out = [m for m in _res_pool(classes)
           if m.get('room') == room and _res_uid(m) not in used]
    out.sort(key=lambda m: (m['level'], m['name']))
    return out


def _res_class_slots(dist, total):
    """0x1433B4D72：n_i = (int)(2*d_i*total + 0.5) >> 1（cvtss2si 四舍五入到偶数）。"""
    slots = []
    for index, (_name, weight) in enumerate(dist):
        n = int(round(2.0 * float(weight) * total + 0.5)) >> 1
        slots.extend([index] * max(0, n))
    return slots


def _res_room_order(rooms, salt):
    """每个房间算 RandFraction(GetSeed(room) + 479582)，按 float 升序（0x1433B4F6D）。

    GetSeed(room) 的外层是关卡的 PersistentLevel，别用 seed_of_object 的默认 0。
    """
    keyed = [(sc.rand_fraction(
                (sc.seed_chain(['PersistentLevel', r]) + RES_SEED_ROOM_ORDER) & sc.M32,
                salt), r)
             for r in rooms]
    keyed.sort(key=lambda pair: pair[0])
    return keyed


def _res_tuto_order():
    """教学段 51 人偶的排序：比较器 0x1402C6910 = actor 名字大小写折叠升序。"""
    return sorted(_res_pool(('tutorial',)),
                  key=lambda m: (m['name'].upper(), m['name']))


def _res_tuto_class_map(level_seed):
    """教学段每个人偶的颜色（`0x1433B5BC0`，给 51 个人偶逐个分配类别）。

        v4 = GetSeed(协调器) = |crc32(名字) + crc32(PersistentLevel)|   # 与关卡种子无关
        for k in 0..50:
            i   = RandSeeded(v4 + k, len(剩余))                        # 逐次抽签
            cls = k % Num(类别)                                        # bAlternatePricesUniformly

    返回 {name: (序号, 类别)}；类别表取协调器自己的 distributions（蓝/绿两项）。
    注意 a1+0x3728 是**全量 51 个**，所以每个人偶都有颜色；「哪 6 个有宝石」是另一套上游选择。
    """
    v4 = sc.seed_chain(['PersistentLevel', RES_MT02_TUTO])
    salt = level_seed % 1000
    dist = [name for name, _weight in _res_distribution(RES_MT02_TUTO)]
    pool = list(_res_tuto_order())
    out = {}
    for k in range(len(pool)):
        index = sc.rand_seeded((v4 + k) & sc.M32, len(pool), salt)
        out[pool.pop(index)['name']] = (k, dist[k % len(dist)])
    return out


def _res_tuto_table(level_seed):
    """教学段类别图（按抽取序号排）。"""
    cmap = _res_tuto_class_map(level_seed)
    rows = []
    for m in _res_tuto_order():
        k, gem = cmap[m['name']]
        rows.append({'k': k, 'gem': gem, 'gem_cn': RES_GEM_CN.get(gem, gem),
                     'spawner': m['name'], 'room': m.get('room'),
                     'coordinates': list(_res_gem_point(m))})
    return rows


def _res_item(source, room, gem, pick, counter, n_candidates):
    return {
        'source': source,
        'room': room,
        'gem': gem,
        'gem_cn': RES_GEM_CN.get(gem, gem),
        'spawner': pick['name'],
        'spawner_level': pick['level'],
        'counter': counter,
        'n_candidates': n_candidates,
        'coordinates': list(_res_gem_point(pick)),
        'coordinate_type': 'actor',
    }


def _predict_res_mt02(level_seed, difficulty='easy', trace=False, tuto=False):
    salt = level_seed % 1000
    dist = _res_distribution()
    items, tr = [], []

    # 1) 固定房（MandatoryRoomsSpawnData）：类别恒为 dist[0]，用自己的 counter
    used = set()
    counter = 0
    for room, block in _res_mandatory_rooms():
        for _ in range(sc.int_by_difficulty(block, difficulty)):
            cands = _res_candidates(room, used=used)
            if not cands:
                tr.append('mandatory %-32s 没有空余人偶' % room)
                continue
            seed = (counter + RES_SEED_MANDATORY) & sc.M32
            pick = cands[sc.rand_seeded(seed, len(cands), salt)]
            items.append(_res_item('mandatory', room, dist[0][0], pick, counter, len(cands)))
            used.add(_res_uid(pick))
            tr.append('mandatory %-32s seed=%d/%d -> %s %s'
                      % (room, seed, len(cands), pick['name'], dist[0][0]))
            counter += 1

    # 2) 类别桶：把 Distribution 按总需求整数化，再抽签 + swap-remove
    sections = _res_sections()
    total = sum(sc.int_by_difficulty(s['count'], difficulty) for s in sections)
    slots = _res_class_slots(dist, total)
    slot_counts = {name: slots.count(index) for index, (name, _w) in enumerate(dist)}
    tr.append('sections total=%d  slots=%d  %s' % (total, len(slots), slot_counts))
    if len(slots) < total:
        tr.append('!! 类别桶少于总需求：游戏会报 Random rooms distributions error 并放弃')

    # 3) 分区：counter 从 0 重新起算（0x1433B4F12），房间是轮流拿而不是随机
    counter = 0
    for si, sec in enumerate(sections, 1):
        want = sc.int_by_difficulty(sec['count'], difficulty)
        if want <= 0:
            continue
        keyed = _res_room_order(sec['rooms'], salt)
        tr.append('section %d: want=%d rooms=%d' % (si, want, len(keyed)))
        if trace:
            for key, room in keyed:
                tr.append('    key=%.6f %s' % (key, room))
        for k in range(want):
            room = keyed[k % len(keyed)][1]       # 轮流，不是随机（0x1433B505C）
            cands = _res_candidates(room, used=used)
            if not cands:
                tr.append('    [%s] 没有空余人偶，跳过（counter 不前进）' % room)
                continue
            seed = (counter + RES_SEED_SECTION_SPAWNER) & sc.M32
            pick = cands[sc.rand_seeded(seed, len(cands), salt)]
            r = sc.rand_seeded_range((counter + RES_SEED_CLASS_PICK) & sc.M32,
                                     0, len(slots) - 1, salt)
            gem = dist[slots.pop(r)][0]
            items.append(_res_item('section%d' % si, room, gem, pick, counter, len(cands)))
            used.add(_res_uid(pick))
            tr.append('    [%s] #%d seed=%d/%d -> %s %s'
                      % (room, counter, seed, len(cands), pick['name'], gem))
            counter += 1

    result = {
        'jewels': items,
        'class_slot_counts': slot_counts,
        'section_total': total,
        'trace': tr if trace else [],
    }
    if tuto:
        result['tutorial_jewels'] = _res_tuto_table(level_seed)
    return result


def _predict_dts_mt01(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    coordinator_seed = sc.seed_chain(['PersistentLevel', DTS_PANEL_COORDINATOR])
    panel_seed = (sc.crc32_fname('Objective Actors') + coordinator_seed) & sc.M32
    remaining = list(DTS_PANELS)
    panels = []
    for index in range(3):
        pool_index = sc.rand_seeded(panel_seed + index, len(remaining), level_seed)
        actor, room, coordinates = remaining[pool_index]
        panels.append({
            'room': room,
            'coordinates': list(coordinates),
            'actor': actor,
        })
        remaining[pool_index] = remaining[-1]
        remaining.pop()
        if trace:
            print('  DTS panel=%d seed=0x%08X index=%d room=%s actor=%s'
                  % (index + 1, (panel_seed + index) & sc.M32,
                     pool_index, room, actor))

    sample = DTS_SAMPLES.get(level_seed)
    if sample:
        clues = [
            {'name': 'Body', 'value': 'Women'},
            {'name': 'Weapon', 'value': '%s = %s'
             % (sample['weapon_code'], sample['weapon'])},
            {'name': 'Room', 'value': '%s (%s)'
             % (sample['room'], sample['clue_room'])},
        ]
        target = {
            'status': 'resolved_from_verified_clues',
            'actor': sample['target_actor'],
            'room': sample['target_room'],
            'coordinates': list(sample['target_coordinates']),
        }
    else:
        clues = [
            {'name': 'Body', 'value': 'Women'},
            {'name': 'Weapon', 'value': '未闭环'},
            {'name': 'Room', 'value': '未闭环'},
        ]
        target = {'status': 'unresolved'}
    return {
        'frequency_panels': panels,
        'clues': clues,
        'target_model': target,
    }


# ---------------------------------------------------------------------------
# SRR_MT01：郊区住宅区 · 撬开富豪宅的密码盘
# ---------------------------------------------------------------------------
# 已闭环（894894→4369/5623/9217、512512→6459/8612/3159、745745→1840/8726/8102）：
#   选 3 栋   sub_1437E5100(RandomizeActorArray)：池=H1..H5，抽 3，保序删除；
#             idx_j = RandSeeded(GetSeed(setup) + j + 45151, |池|)
#   抽房      sub_14374E420 分区抽房：idx = RandSeeded(剩余需求 + 28042, |该区房间|)
#   处理顺序  sub_14374E420 尾部容器 introsort(key = RandFraction(GetSeed(组件))>=0.5)，
#             n<=8 走选择排序；密码按「逆序」消费
#   数字      digit_k = pool[RandSeeded(compSeed(room_k) + k + 7168, |pool|)]，池=0..9 保序删除
SRR_DRAW_OFFSET = 45151     # sub_1437E5100：抽密码房
SRR_PICK_OFFSET = 28042     # sub_14374E420：分区抽房
SRR_FILL_OFFSET = 28088     # sub_14374E420：兜底补位（本关用不到）
SRR_DIGIT_OFFSET = 7168     # sub_143620E70：逐位抽数字


def _srr_house_seed():
    """GetSeed(抽签 setup) 的暂定解：|crc(组名) + |crc(House1 协调器名) + 0||。

    在「池 [H1..H5] × 670+ 名字链构造」中是三样本同时命中的唯一解；
    setup 对象的真实身份未定位，第四个样本可推翻它（见 SRR_MT01.md §6.1）。
    """
    return sc.seed_of_object(
        'RBObjectiveCoordinatorGroup2',
        sc.seed_of_object('MultiroomPuzzle_Coordinator_House1_BP', 0))


def _srr_draw_houses(salt, trace=False):
    """本局 3 个密码房，返回抽中顺序的 tag 列表（如 ['H1', 'H3', 'H4']）。"""
    group_seed = _srr_house_seed()
    pool = list(SRR_HOUSE_ORDER)
    picked = []
    for j in range(3):
        index = sc.rand_seeded((group_seed + j + SRR_DRAW_OFFSET) & sc.M32,
                               len(pool), salt)
        picked.append(pool.pop(index))
        if trace:
            print('  SRR 抽密码房 j=%d idx=%d/%d -> %s'
                  % (j, index, len(pool) + 1, picked[-1]))
    return picked


def _srr_pick_rooms(house, salt, trace=False):
    """按 Sections 顺序抽房（可重复：两个 Section 可以指向同一间房）。"""
    sections = house['sections']
    pools = [list(sec['rooms']) for sec in sections]
    picked = []
    remaining = house['count']
    for sid, section in enumerate(sections):
        for _ in range(max(0, min(section['min'], remaining))):
            pool = pools[sid]
            if not pool:
                break
            index = sc.rand_seeded((remaining + SRR_PICK_OFFSET) & sc.M32,
                                   len(pool), salt)
            picked.append(pool.pop(index))
            if trace:
                print('    sect%d 剩余=%d idx=%d/%d -> %s'
                      % (sid, remaining, index, len(pool) + 1, picked[-1]))
            remaining -= 1
    for sid in range(len(sections)):           # 兜底补位
        while remaining > 0 and pools[sid]:
            index = sc.rand_seeded((remaining + SRR_FILL_OFFSET) & sc.M32,
                                   len(pools[sid]), salt)
            picked.append(pools[sid].pop(index))
            remaining -= 1
    return picked


def _srr_comp_seed(room):
    """GetSeed(RBPuzzleRoomComponent) = |crc(组件名) + |crc(房间名) + crc(PersistentLevel)||"""
    component = SRR_ROOM_COMPONENTS.get(room, 'RBPuzzleRoomComponent_0')
    return sc.seed_of_object(component,
                             sc.seed_of_object(room, sc.crc32_fname('PersistentLevel')))


def _srr_sel_sort_bit(items, bits):
    """sub_1435F7860 小范围（n<=8）选择排序：每轮把「最后一个 bit=0」换到区间末尾。"""
    out = list(items)
    end = len(out) - 1
    while end > 0:
        cand = 0
        for j in range(1, end + 1):
            if bits[out[j]] == 0:
                cand = j
        out[cand], out[end] = out[end], out[cand]
        end -= 1
    return out


def _srr_process_order(rooms, salt):
    """贴花位的处理顺序 = 容器排序（key=RandFraction(compSeed)>=0.5）的逆序。"""
    bits = {room: 1 if sc.rand_fraction(_srr_comp_seed(room), salt) >= 0.5 else 0
            for room in rooms}
    return list(reversed(_srr_sel_sort_bit(rooms, bits))), bits


def _srr_digits(order, salt, trace=False):
    """4 位密码：pool 每局重置为 0..9，逐位抽走即删。"""
    pool = list(range(10))
    out = []
    for k, room in enumerate(order):
        base = _srr_comp_seed(room)
        index = sc.rand_seeded((base + k + SRR_DIGIT_OFFSET) & sc.M32,
                               len(pool), salt)
        digit = pool.pop(index)
        out.append(digit)
        if trace:
            print('    k=%d %-42s compSeed=%d pool=%d idx=%d -> %d'
                  % (k, room, base, len(pool) + 1, index, digit))
    return ''.join(str(d) for d in out)


def _predict_srr_mt01(level_seed, trace=False):
    salt = level_seed % 1000
    selected = _srr_draw_houses(salt, trace=trace)
    houses = []
    for coordinator in sorted(SRR_HOUSES):
        house = SRR_HOUSES[coordinator]
        picked = _srr_pick_rooms(house, salt, trace=trace)
        order, bits = _srr_process_order(picked, salt)
        code = _srr_digits(order, salt, trace=trace)
        slots = []
        for k, room in enumerate(order, 1):
            slot = {'index': k, 'room': room, 'digit': int(code[k - 1])}
            center = SRR_ROOM_CENTERS.get(room)
            if center:
                slot['coordinates'] = list(center)
                slot['coordinate_type'] = 'room_center'
            slots.append(slot)
        entry = {
            'coordinator': coordinator,
            'tag': house['tag'],
            'pad': house['pad'],
            'pad_room': house.get('pad_room'),
            'selected': house['tag'] in selected,
            'rooms': picked,
            'order': order,
            'bits': bits,
            'code': code,
            'slots': slots,
        }
        if house.get('pad_coordinates'):
            entry['coordinates'] = list(house['pad_coordinates'])
            entry['coordinate_type'] = 'actor'
        if trace:
            print('  [%s]%s 密码盘=%s 贴花位=%s 密码=%s'
                  % (entry['tag'], '' if entry['selected'] else '（未激活）',
                     entry['pad'], ' -> '.join(order), code))
        houses.append(entry)
    return {'selected': selected, 'houses': houses}


def predict(level_id, seed, players=1, difficulty='easy', max_fake=None,
            digits=4, trace=False, tuto=False):
    key = resolve(level_id)
    cfg = LEVELS[key]
    result = {'level': key, 'name': cfg['name'], 'map': cfg['map'],
              'seed': seed, 'salt': seed % 1000,
              'players': players, 'difficulty': difficulty}

    if cfg.get('jewels'):
        result.update(_predict_res_mt02(seed, difficulty, trace=trace, tuto=tuto))
        return result

    if cfg.get('keylockedrooms'):
        result.update(_predict_psa_mt01(seed, trace=trace))
        return result

    if cfg.get('dts'):
        result.update(_predict_dts_mt01(seed, trace=trace))
        return result

    if cfg.get('puzzle'):
        result.update(_predict_srr_mt01(seed, trace=trace))
        return result

    if cfg.get('gameshow'):
        mf = max_fake if max_fake is not None else gs.MAX_FAKE
        result['consoles'] = gs.CONSOLES.get(players, 4)
        result['max_fake'] = mf
        notes = []
        if difficulty != 'easy' and max_fake is None:
            notes.append('难度 %s 未实测，MaxFake 仍按 %d 计算'
                         '（可用 --max-fake 覆盖）' % (difficulty, mf))
        if notes:
            result['notes'] = notes
        tut = gs.predict_tutorial(seed, mf)
        result['tutorial'] = tut['rooms'] if not tut['failed'] else None
        result['rounds'] = gs.predict(seed, players, max_fake=mf)
        for room in result['tutorial'] or []:
            _attach_room_coordinates(room, cfg['map'])
        for round_data in result['rounds']:
            for room in round_data['rooms']:
                _attach_room_coordinates(room, cfg['map'])
        return result

    if cfg.get('cluegame'):
        info = cg.predict(seed)
        scene = {'room': info['crime_scene']}
        _attach_room_coordinates(scene, cfg['map'])
        info['crime_scene_coordinates'] = scene.get('coordinates')
        info['crime_scene_coordinate_type'] = scene.get('coordinate_type')
        result['clue'] = info
        return result

    if cfg.get('projection'):
        projections, notes = _predict_chj_mt02(seed)
        result['projections'] = projections
        for item in projections:
            # 机位 actor 坐标优先，只有拿不到精确坐标时才退回房间中心
            if not item.get('coordinates'):
                _attach_room_coordinates(item, cfg['map'])
        if notes:
            result['notes'] = notes
        return result

    if cfg.get('projectors'):
        result.update(_predict_fpi_mt01(seed, trace=trace))
        return result

    if cfg.get('firepump'):
        result.update(_predict_tfs_mt03(seed, trace=trace))
        return result

    if cfg.get('switchboard'):
        result.update(_predict_tsr_mt01(seed, trace=trace))
        return result

    if cfg.get('mhs'):
        result.update(_predict_mhs_mt01(seed, trace=trace))
        return result

    if cfg.get('mannequin'):
        info = mq.predict(seed, trace=trace)
        result.update(info)
        result['notes'] = [
            '颜色↔人偶类型（红=A/绿=B/蓝=C）由 seed=453453 单样本反推：'
            '房间集合不受影响，但若组的初始顺序不是 A B C D，绿/蓝会对调。',
            '「3 个人偶分散到东西两个区域」是「同层水平 50 m 内不许有第二个目标」'
            '的副作用（300 seed 抽样 298 次东西各半），不是硬约束。',
        ]
        if info['spread'] < 3:
            result['notes'].append(
                '本局只落在 %d 个区域（%s），罕见但可能发生。'
                % (info['spread'], ' + '.join(sorted(set(info['sections'])))))
        return result

    if cfg.get('sections') is None:
        result['notes'] = ['该关卡还不能从 seed 推理：%s' % cfg.get('todo', '')]
        return result

    rooms = sc.pick_rooms(seed, sections=cfg['sections'],
                          want=cfg['want'], trace=trace)
    result['rooms'] = []
    for i, room in enumerate(rooms, 1):
        item = {'index': i, 'room': room}
        _attach_room_coordinates(item, cfg['map'])
        if cfg.get('passcode'):
            item['code'] = sc.passcode(seed, room, cfg.get('digits', digits))
        result['rooms'].append(item)
    return result


def _point(room, label=None, id_=None, coords=None, **extra):
    point = {}
    if id_:
        point['id'] = id_
    point['room'] = room
    if label:
        point['label'] = label
    if coords:
        point['coordinates'] = [round(float(c), 1) for c in coords]
    point.update(extra)
    return point


def _actor_coords(item, key='coordinates'):
    """房间中心留给地图按 room 索引；actor 级点位才带坐标（同房多点时必须）。"""
    if item.get('coordinate_type') == 'room_center':
        return None
    return item.get(key)


def view(result):
    """把内部推理结构压成 UI 用的极简视图。

    只保留三样东西：
      answer  —— 整关一个答案串（"1=王冠 2=红心" / "room=9 weapon=5" / "螺旋=752"）
      points  —— 任务点位 [{id?, room, label?, coordinates?}]，数组顺序即执行顺序
      rounds  —— 仅多轮关卡 [{round, answers}]
      spare   —— 仅 SRR_MT01：没抽中的那几栋的密码（抽签判错时的兜底）
    """
    out = {'level': result['level'], 'name': result['name'],
           'map': result['map'], 'seed': result['seed'],
           'players': result.get('players', 1),
           'answer': None, 'points': []}
    points = out['points']

    if 'jewels' in result:                                  # RES_MT02
        for item in result['jewels']:
            points.append(_point(item['room'], item['gem_cn'], item['spawner'],
                                 _actor_coords(item)))

    elif 'path' in result:                                  # PSA_MT01
        for step in result['path']:
            points.append(_point(step['room'], step['symbol_name_zh'],
                                 step.get('actor'), _actor_coords(step)))

    elif 'frequency_panels' in result:                      # DTS_MT01
        for panel in result['frequency_panels']:
            points.append(_point(panel['room'], '调频器', panel.get('actor'),
                                 _actor_coords(panel)))
        target = result['target_model']
        if target.get('room'):
            points.append(_point(target['room'], '目标人偶', target.get('actor'),
                                 _actor_coords(target)))
        out['answer'] = ' '.join('%s=%s' % (c['name'], c['value'])
                                 for c in result['clues'])

    elif 'rounds' in result:                                # FPI_MT02
        rounds = []
        tut = result.get('tutorial') or []
        if tut:
            rounds.append({'round': 0,
                           'answers': [str(r['answer']) for r in tut]})
        for rd in result['rounds']:
            rounds.append({'round': rd['round'] + 1,
                           'answers': [str(r['answer']) for r in rd['rooms']]})
        out['rounds'] = rounds
        return out

    elif 'clue' in result:                                  # RES_MT01
        ans = result['clue']['answers']
        out['answer'] = 'room=%d weapon=%d killer=%d' % (
            ans['room'], ans['weapon'], ans['killer'])

    elif 'connections' in result:                           # TSR_MT01
        for item in result['connections']:
            points.append(_point(item['letter_room'], item['letter'],
                                 None, item.get('letter_coordinates')))
            points.append(_point(item['number_room'], item['number'],
                                 None, item.get('number_coordinates')))

    elif 'projections' in result:                           # CHJ_MT02
        out['answer'] = ' '.join('%s=%s' % (i['symbol_name'], i['code'])
                                  for i in result['projections'])

    elif 'patterns' in result:                              # MHS_MT01
        out['answer'] = ' '.join('%s=%s' % (i['pattern_name'], i['code'])
                                  for i in result['patterns'])

    elif 'mannequins' in result:                            # SMC_MT02
        for item in result['mannequins']:
            if item.get('room'):
                points.append(_point(item['room'], item['color_name'],
                                     item.get('actor'), _actor_coords(item)))

    elif 'projectors' in result:                            # FPI_MT01
        items = sorted(result['projectors'], key=lambda x: x['reel_index'])
        for item in items:
            points.append(_point(item['room'], item['symbol_name_zh'],
                                 item.get('actor'), _actor_coords(item),
                                 reel=item['reel_index']))
        out['answer'] = ' '.join('%d=%s' % (i['reel_index'], i['symbol_name_zh'])
                                 for i in items)

    elif 'valves' in result:                                # TFS_MT03
        for item in sorted(result['valves'], key=lambda x: x['section']):
            points.append(_point(item['room'], item['section'], item['actor'],
                                 _actor_coords(item)))

    elif 'houses' in result:                                # SRR_MT01
        # 只要「哪个房间的密码盘」+ 4 位密码：激活的 3 栋在前，另外 2 栋随后（标备用）
        active = [h for h in result['houses'] if h['selected']]
        spare = [h for h in result['houses'] if not h['selected']]
        for house in active + spare:
            is_spare = not house['selected']
            point = _point(house['pad_room'],
                           '%s 密码盘%s' % (house['tag'], '（备用）' if is_spare else ''),
                           house['pad'], _actor_coords(house))
            point['answer'] = house['code']
            if is_spare:
                point['spare'] = True
            points.append(point)
        out['answer'] = ' '.join('%s=%s' % (h['tag'], h['code']) for h in active)
        if spare:
            out['spare'] = [{key: house.get(key) for key in
                             ('tag', 'code', 'pad', 'pad_room', 'coordinates')
                             if house.get(key)} for house in spare]

    else:                                                   # CHJ_MT01 等
        for room in result.get('rooms') or []:
            point = {'room': room['room']}
            if room.get('code'):
                point['answer'] = room['code']
            points.append(point)

    if not out['answer']:
        out['answer'] = None
        if not points:
            notes = result.get('notes') or []
            if notes:
                out['note'] = notes[0]
    return out


def render(result):
    """CLI 文本输出。predict() 的原始结果或 view() 的视图都能传。"""
    v = view(result) if 'salt' in result else result
    lines = ['%s  %s  (%s)  seed=%d  %dP'
             % (v['level'], v['name'], v['map'], v['seed'],
                v.get('players', 1))]
    if v.get('answer'):
        lines.append('  答案：%s' % v['answer'])
    if v.get('note'):
        lines.append('  ! %s' % v['note'])
    for index, point in enumerate(v.get('points') or [], 1):
        tail = ''
        if point.get('answer'):
            tail = '  密码 %s' % point['answer']
        if point.get('reel') is not None:
            tail = '  盘%d' % point['reel']
        lines.append('  %2d. %-8s %s%s'
                     % (index, point.get('label') or '', point['room'], tail))
    for rd in v.get('rounds') or []:
        name = '教学' if rd['round'] == 0 else '第%d轮' % rd['round']
        lines.append('  [%s] %s' % (name, '  '.join(rd['answers'])))
    return '\n'.join(lines)


def selftest(verbose=True):
    bad = total = 0
    for seed, expect in SAMPLES_CHJ:
        got = {r['room']: r['code'] for r in predict('CHJ_MT01', seed)['rooms']}
        for room, code in expect.items():
            total += 1
            ok = got.get(room) == code
            bad += 0 if ok else 1
            if verbose:
                print('  CHJ %-7d %-30s 预测=%s 实测=%s %s'
                      % (seed, room, got.get(room, '---'), code,
                         'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_CHJ_MT02:
        got = {r['symbol']: r['code']
               for r in predict('CHJ_MT02', seed)['projections']}
        for symbol, code in expect.items():
            total += 1
            ok = got.get(symbol) == code
            bad += 0 if ok else 1
            if verbose:
                print('  CHJ2 %-7d %-16s 预测=%s 实测=%s %s'
                      % (seed, symbol, got.get(symbol, '---'), code,
                         'OK' if ok else 'MISMATCH'))
    for seed, (expect, scene) in SAMPLES_RES:
        info = cg.predict(seed)
        total += 1
        ok = info['answers'] == expect and info['crime_scene'] == scene
        bad += 0 if ok else 1
        if verbose:
            print('  RES %-7d 预测=%s/%s 实测=%s/%s %s'
                  % (seed, info['answers'], info['crime_scene'],
                     expect, scene, 'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_GS:
        res = predict('FPI_MT02', seed)
        got = {}
        if res.get('tutorial'):
            r = res['tutorial'][0]
            got[(1, r['room'])] = (r['symbol'], r['answer'])
        for rd in res['rounds']:
            for r in rd['rooms']:
                got[(rd['stage'], r['room'])] = (r['symbol'], r['answer'])
        for stage, rooms in expect.items():
            for room, want in rooms.items():
                total += 1
                have = got.get((stage, room))
                ok = have == want
                bad += 0 if ok else 1
                if verbose:
                    print('  FPI %-7d 阶段%d %-34s 预测=%s 实测=%s %s'
                          % (seed, stage, room, have, want,
                             'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_TSR:
        got = predict('TSR_MT01', seed)
        total += 1
        ok = got['codes'] == expect
        bad += 0 if ok else 1
        if verbose:
            print('  TSR %-7d 预测=%s 实测=%s %s'
                  % (seed, ','.join(got['codes']), ','.join(expect),
                     'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_FPI_MT01:
        got = predict('FPI_MT01', seed)['projectors']
        for item, wanted in zip(got, expect):
            total += 1
            actual = (item['room'], item['reel_index'], item['symbol'])
            ok = (actual == wanted and
                  item['coordinates'] == FPI_PROJECTOR_COORDS[item['actor']])
            bad += 0 if ok else 1
            if verbose:
                print('  FPI1 %-7d %-40s 预测=%s 实测=%s %s'
                      % (seed, item['room'], actual, wanted,
                         'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_TFS:
        got = predict('TFS_MT03', seed)['valves']
        for item, (section, actor) in zip(got, expect):
            total += 1
            ok = (item['section'] == section and item['actor'] == actor and
                  item['room'] == TFS_SAMPLE_ROOMS[section] and
                  item['coordinates'] == TFS_VALVE_COORDS[actor])
            bad += 0 if ok else 1
            if verbose:
                print('  TFS %-7d %-3s 预测=%s/%s 实测=%s %s'
                      % (seed, section, item['room'], item['actor'], actor,
                         'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_SMC:
        got = {item['color']: item['room']
               for item in predict('SMC_MT02', seed)['mannequins']}
        for color, room in expect.items():
            total += 1
            ok = got.get(color) == room
            bad += 0 if ok else 1
            if verbose:
                print('  SMC %-7d %-9s 预测=%-46s 实测=%-46s %s'
                      % (seed, color, got.get(color, '---'), room,
                         'OK' if ok else 'MISMATCH'))
    for seed, zone, short, code in SAMPLES_MHS:
        coord_name = MHS_ZONE_BY_KEY[zone][1]
        got = _mhs_code(coord_name, _mhs_symbol_name(zone, short), seed)
        total += 1
        ok = got == code
        bad += 0 if ok else 1
        if verbose:
            print('  MHS %-7d %-11s %-24s 预测=%s 实测=%s %s'
                  % (seed, zone, _mhs_symbol_name(zone, short), got, code,
                     'OK' if ok else 'MISMATCH'))
    # 「10 选 1」：759759 的 TrainDepot 没有记密码，符号由房间记忆反推，同样算一条
    for seed, zone, short in SAMPLES_MHS_PICK:
        item = {p['zone']: p
                for p in predict('MHS_MT01', seed)['patterns']}.get(zone)
        total += 1
        ok = item is not None and item['actor'] == _mhs_symbol_name(zone, short)
        bad += 0 if ok else 1
        if verbose:
            print('  MHS %-7d %-11s pick 预测=%-26s 实测=%-26s %s'
                  % (seed, zone, item['actor'] if item else '---',
                     _mhs_symbol_name(zone, short), 'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_PSA:
        got = [(step['symbol'], step['room'], step['coordinates'])
               for step in predict('PSA_MT01', seed)['path']]
        total += 1
        ok = got == expect
        bad += 0 if ok else 1
        if verbose:
            print('  PSA %-7d 预测=%s 实测=%s %s'
                  % (seed, got, expect, 'OK' if ok else 'MISMATCH'))
    for seed, expect in SAMPLES_SRR:
        result = predict('SRR_MT01', seed)
        pads = {house['pad']: house for house in result['houses']}
        got_tags = sorted(house['tag'] for house in result['houses']
                          if house['selected'])
        want_tags = sorted(pads[pad]['tag'] for pad in expect)
        total += 1
        ok = got_tags == want_tags
        bad += 0 if ok else 1
        if verbose:
            print('  SRR %-7d 选房 预测=%-12s 实测=%-12s %s'
                  % (seed, ' '.join(got_tags), ' '.join(want_tags),
                     'OK' if ok else 'MISMATCH'))
        for pad, (room, code) in sorted(expect.items()):
            house = pads[pad]
            got_code = house['code']
            got_room = house['pad_room']
            total += 1
            ok = got_code == code and (room is None or got_room == room)
            bad += 0 if ok else 1
            if verbose:
                print('  SRR %-7d %-28s 预测=%s@%-40s 实测=%s@%-40s %s'
                      % (seed, house['tag'], got_code, got_room, code,
                         room or '(未记)', 'OK' if ok else 'MISMATCH'))
    for seed, expected_panels in DTS_PANEL_SAMPLES.items():
        result = predict('DTS_MT01', seed)
        panels = tuple(item['actor'] for item in result['frequency_panels'])
        sample = DTS_SAMPLES[seed]
        target = result['target_model']
        total += 1
        ok = (panels == expected_panels and len(result['clues']) == 3 and
              target.get('actor') == sample['target_actor'] and
              target.get('room') == sample['target_room'] and
              target.get('coordinates') == list(sample['target_coordinates']))
        bad += 0 if ok else 1
        if verbose:
            print('  DTS %-7d 调频器=%s 模型=%s %s'
                  % (seed, ','.join(item['room']
                                    for item in result['frequency_panels']),
                     target.get('actor', '---'), 'OK' if ok else 'MISMATCH'))
    # RES_MT02 主轴段：人偶 -> 宝石类别
    for seed, expect in RES_MT02_SAMPLES.items():
        got = {item['spawner']: item['gem']
               for item in predict('RES_MT02', seed)['jewels']}
        for name, gem in expect:
            total += 1
            ok = got.get(name) == gem
            bad += 0 if ok else 1
            if verbose:
                print('  RES2 %-7d %-34s 预测=%-9s 实测=%-9s %s'
                      % (seed, name, got.get(name, '---'), gem,
                         'OK' if ok else 'MISMATCH'))
    # RES_MT02 教学段：人偶 -> 颜色（BP_139 两局都与模型相反，未收入样本）
    cache = {}
    for seed, name, gem in RES_MT02_TUTO_SAMPLES:
        cmap = cache.setdefault(seed, _res_tuto_class_map(seed))
        total += 1
        ok = cmap[name][1] == gem
        bad += 0 if ok else 1
        if verbose:
            print('  RES2 %-7d 教学 %-6s 预测=%-9s 实测=%-9s %s'
                  % (seed, name.rsplit('_', 1)[-1], cmap[name][1], gem,
                     'OK' if ok else 'MISMATCH'))
    print('自检：%d/%d 通过' % (total - bad, total))
    return bad == 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='按关卡 + 关卡种子推理这一局数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='例：python seed.py FPI_MT02 189189 --players 2')
    ap.add_argument('level', nargs='?', help='关卡编号，如 FPI_MT02 / CHJ_MT01')
    ap.add_argument('seed', nargs='?', type=int, help='关卡种子（6 位数）')
    ap.add_argument('--players', type=int, default=1, choices=(1, 2, 3, 4),
                    help='玩家人数 1-4（默认 1；影响讲台/房间数）')
    ap.add_argument('--difficulty', default='easy',
                    choices=('easy', 'normal', 'hard', 'insane'),
                    help='难度（默认 easy）')
    ap.add_argument('--max-fake', type=int, default=None,
                    help='手动指定每区假翻板上限（默认按关卡配置）')
    ap.add_argument('--digits', type=int, default=4, help='密码位数（默认 4）')
    ap.add_argument('--list', action='store_true', help='列出已支持关卡')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    ap.add_argument('--out', metavar='FILE', help='把 JSON 写入文件')
    ap.add_argument('--trace', action='store_true', help='打印抽取过程（走 stderr）')
    ap.add_argument('--debug', action='store_true',
                    help='JSON 里附带 debug 字段（完整内部推理结构）')
    ap.add_argument('--tuto', action='store_true',
                    help='RES_MT02：附带教学段 51 个人偶的类别图')
    ap.add_argument('--selftest', action='store_true', help='用已知样本自检')
    args = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

    if args.list:
        for key, cfg in LEVELS.items():
            ok = (bool(cfg.get('sections')) or cfg.get('gameshow')
                  or cfg.get('cluegame') or cfg.get('projection')
                  or cfg.get('switchboard') or cfg.get('projectors')
                  or cfg.get('firepump') or cfg.get('mhs')
                  or cfg.get('mannequin') or cfg.get('dts')
                  or cfg.get('keylockedrooms') or cfg.get('jewels')
                  or cfg.get('puzzle'))
            status = 'PART' if cfg.get('partial') else ('OK' if ok else 'TODO')
            print('%-10s [%-4s] %-24s %s'
                  % (key, status, cfg['name'], cfg['map']))
        return 0

    if args.selftest:
        return 0 if selftest() else 1

    if not args.level or args.seed is None:
        ap.print_help()
        return 2

    try:
        result = predict(args.level, args.seed, args.players, args.difficulty,
                         args.max_fake, args.digits, args.trace, args.tuto)
    except KeyError:
        print('未知关卡：%s（用 --list 查看）' % args.level, file=sys.stderr)
        return 2
    except ModelUnresolved as exc:
        print('! %s' % exc, file=sys.stderr)
        return 2

    for line in result.get('trace') or []:
        print(line, file=sys.stderr)

    data = view(result)
    if args.debug:
        data['debug'] = result

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        print('已写入 %s' % args.out)
        return 0

    print(json.dumps(data, ensure_ascii=False, indent=2) if args.json
          else render(data))
    return 0


if __name__ == '__main__':
    sys.exit(main())
