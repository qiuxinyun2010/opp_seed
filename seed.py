# -*- coding: utf-8 -*-
"""按「关卡 + 关卡种子」推理这一局的有用信息。

用法：
    python seed.py --list
    python seed.py FPI_MT02 189189                      # 房间 / 图案 / 答案
    python seed.py FPI_MT02 189189 --players 3          # 1/2/3 人（讲台数不同）
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
    python seed.py FPI_MT02 189189 --json
    python seed.py --selftest

模块：
    seedcore.py   逆向出的随机原语（GetSeed / RandSeeded / RandBool / lookup3 mix …）
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
    SAMPLES_CHJ, SAMPLES_CHJ_MT02, SAMPLES_RES, SAMPLES_SMC, SAMPLES_GS,
    SAMPLES_TSR, SAMPLES_FPI_MT01, SAMPLES_TFS, SAMPLES_MHS,
    SAMPLES_MHS_PICK, TFS_SAMPLE_ROOMS, SAMPLES_PSA,
    CHJ_MT02_COORDS, CHJ_MT02_ACTORS, CHJ_MT02_ROOMS_20020,
    CHJ_MT02_SYMBOL_NAMES, MHS_SYMBOL_NAMES, MHS_ZONES, MHS_ZONE_BY_KEY,
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


def _fmt_coordinates(coordinates):
    if not coordinates:
        return ''
    return ' (%g, %g, %g)' % tuple(coordinates)


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
                'room': rooms.get(group),
                'actor': actor,
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
            raise ModelUnresolved(
                'PSA_MT01：%s 只导出一个钥匙生成点，但该 seed 把它选成了「还要再出一把钥匙」'
                '的中间节点。游戏运行时可能还有未导出的内部 spawn slot，'
                '本脚本不猜第二个点，故不输出结果（约 12%% 的 seed 会命中）' % parent)
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


def predict(level_id, seed, players=1, difficulty='easy', max_fake=None,
            digits=4, trace=False):
    key = resolve(level_id)
    cfg = LEVELS[key]
    result = {'level': key, 'name': cfg['name'], 'map': cfg['map'],
              'seed': seed, 'salt': seed % 1000,
              'players': players, 'difficulty': difficulty}

    if cfg.get('keylockedrooms'):
        result.update(_predict_psa_mt01(seed, trace=trace))
        return result

    if cfg.get('dts'):
        result.update(_predict_dts_mt01(seed, trace=trace))
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


def render(result):
    if 'frequency_panels' in result:
        lines = ['调频器：']
        for index, panel in enumerate(result['frequency_panels'], 1):
            lines.append('  %d. %s%s' % (
                index, panel['room'], _fmt_coordinates(panel['coordinates'])))
        lines.append('线索：')
        for clue in result['clues']:
            lines.append('  %s = %s' % (clue['name'], clue['value']))
        lines.append('最终模型：')
        target = result['target_model']
        if target['status'] == 'unresolved':
            lines.append('  未闭环')
        else:
            lines.append('  %s%s' % (
                target['room'], _fmt_coordinates(target['coordinates'])))
        return '\n'.join(lines)

    head = '%s  %s  (%s)' % (result['level'], result['name'], result['map'])
    lines = [head,
             'seed = %d   salt = %d   %s   %dP'
             % (result['seed'], result['salt'],
                result.get('difficulty', 'easy').title(),
                result.get('players', 1))]
    if result.get('notes'):
        for n in result['notes']:
            lines.append('! ' + n)
        if not any(key in result for key in
                   ('rounds', 'projectors', 'valves', 'connections',
                    'projections', 'clue', 'rooms', 'patterns', 'mannequins',
                    'path')):
            return '\n'.join(lines)
    if 'path' in result:
        for index, step in enumerate(result['path'], 1):
            lines.append('  %d：%s=%s%s'
                         % (index, step['symbol_name_zh'], step['room'],
                            _fmt_coordinates(step['coordinates'])))
        return '\n'.join(lines)
    if 'projectors' in result:
        for item in result['projectors']:
            lines.append('  [盘%d] %-40s %-8s(%s)%s'
                         % (item['reel_index'], item['room'], item['symbol'],
                            item['symbol_name_zh'],
                            _fmt_coordinates(item['coordinates'])))
        return '\n'.join(lines)
    if 'valves' in result:
        for item in result['valves']:
            lines.append('  [%s] %-42s %s%s'
                         % (item['section'], item['room'], item['actor'],
                            _fmt_coordinates(item['coordinates'])))
        return '\n'.join(lines)
    if 'connections' in result:
        lines.append('  面板种子 %d   数字错位 %d'
                     % (result['panel_seed'], result['number_rotation']))
        for item in result['connections']:
            lines.append('  [%s]' % item['code'])
            lines.append('    字母 %-2s %-14s%s'
                         % (item['letter'], item['letter_room'],
                            _fmt_coordinates(item['letter_coordinates'])))
            lines.append('    数字 %-2s %-14s%s'
                         % (item['number'], item['number_room'],
                            _fmt_coordinates(item['number_coordinates'])))
        return '\n'.join(lines)
    if 'mannequins' in result:
        for item in result['mannequins']:
            if item['room'] is None:
                lines.append('  [%-8s] <候选被距离规则过滤空>' % item['color'])
                continue
            lines.append('  [%s %-4s %-18s] %-44s%s'
                         % (item['color'], item['color_name'], item['section'],
                            item['room'],
                            _fmt_coordinates(item['coordinates'])))
        return '\n'.join(lines)
    if 'patterns' in result:
        for item in result['patterns']:
            lines.append('  [%s %-12s] %-46s 密码 %s  (%s)%s'
                         % (item['pattern_name'], item['pattern'],
                            item['room'], item['code'],
                            item['actor'].rsplit('_BP_', 1)[-1],
                            _fmt_coordinates(item['coordinates'])))
        return '\n'.join(lines)
    if 'projections' in result:
        for item in result['projections']:
            stage = '教学 ' if item['tutorial'] else ''
            room = item['room'] or '房间未验证'
            short_actor = item['actor'].rsplit('_BP_', 1)[-1]
            lines.append('  [%s%s] %-34s 密码 %s  (%s)%s'
                         % (stage, item['symbol_name'], room, item['code'],
                            short_actor, _fmt_coordinates(item.get('coordinates'))))
        return '\n'.join(lines)
    if 'clue' in result:
        lines.extend(cg.describe(result['seed']))
        lines.append('  犯罪现场坐标%s'
                     % _fmt_coordinates(result['clue'].get('crime_scene_coordinates')))
        return '\n'.join(lines)
    if 'rounds' in result:
        tut = result.get('tutorial')
        if tut:
            r = tut[0]
            lines.append('  [阶段1 教学] %-14s %-10s 答案 %d   数字 %s%s'
                         % (r['room_name'], r['symbol'], r['answer'],
                            '+'.join(str(x) for x in r['digits']),
                            _fmt_coordinates(r.get('coordinates'))))
        for rd in result['rounds']:
            if rd.get('failed') or not rd['rooms']:
                lines.append('  [阶段%d] 该回合准备失败（脚本未覆盖的边界）'
                             % rd['stage'])
                continue
            lines.append('  [阶段%d 第%d回合]' % (rd['stage'], rd['round'] + 1))
            for r in rd['rooms']:
                lines.append('    %-14s %-10s 答案 %d   数字 %s%s'
                             % (r['room_name'], r['symbol'], r['answer'],
                                '+'.join(str(x) for x in r['digits']),
                                _fmt_coordinates(r.get('coordinates'))))
        return '\n'.join(lines)
    for room in result.get('rooms', []):
        if 'code' in room:
            lines.append('  [%d] %-30s 密码 %s%s'
                         % (room['index'], room['room'], room['code'],
                            _fmt_coordinates(room.get('coordinates'))))
        else:
            lines.append('  [%d] %s%s'
                         % (room['index'], room['room'],
                            _fmt_coordinates(room.get('coordinates'))))
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
    print('自检：%d/%d 通过' % (total - bad, total))
    return bad == 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='按关卡 + 关卡种子推理这一局数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='例：python seed.py FPI_MT02 189189 --players 2')
    ap.add_argument('level', nargs='?', help='关卡编号，如 FPI_MT02 / CHJ_MT01')
    ap.add_argument('seed', nargs='?', type=int, help='关卡种子（6 位数）')
    ap.add_argument('--players', type=int, default=1, choices=(1, 2, 3),
                    help='玩家人数（默认 1；影响讲台/房间数）')
    ap.add_argument('--difficulty', default='easy',
                    choices=('easy', 'normal', 'hard', 'insane'),
                    help='难度（默认 easy）')
    ap.add_argument('--max-fake', type=int, default=None,
                    help='手动指定每区假翻板上限（默认按关卡配置）')
    ap.add_argument('--digits', type=int, default=4, help='密码位数（默认 4）')
    ap.add_argument('--list', action='store_true', help='列出已支持关卡')
    ap.add_argument('--json', action='store_true', help='输出 JSON')
    ap.add_argument('--out', metavar='FILE', help='把 JSON 写入文件')
    ap.add_argument('--trace', action='store_true', help='打印抽取过程')
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
                  or cfg.get('keylockedrooms'))
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
                         args.max_fake, args.digits, args.trace)
    except KeyError:
        print('未知关卡：%s（用 --list 查看）' % args.level, file=sys.stderr)
        return 2
    except ModelUnresolved as exc:
        print('! %s' % exc, file=sys.stderr)
        return 2

    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fp:
            json.dump(result, fp, ensure_ascii=False, indent=2)
        print('已写入 %s' % args.out)
        return 0

    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json
          else render(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
