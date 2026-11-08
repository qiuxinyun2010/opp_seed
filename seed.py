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
    python seed.py CHJ_MT03 327327                      # 图案立牌点位（各图案在哪块立牌）
    python seed.py CHJ_MT03 327327 --seats BP_1,BP_2,BP_5,BP_6,BP_8
    python seed.py MHS_MT01 707707                       # 3 个图案 + 房间 + 3 位密码
    python seed.py MHS_MT01 707707 --trace               # 附带抽取池与房间去重
    python seed.py TSR_MT01 695695                      # 字母数字位置 / 接线密码
    python seed.py TSR_MT02 726726                      # 本局可用的刻录机点位（按抽取顺序）
    python seed.py TSR_MT02 726726 --trace              # 附带每轮候选池与抽取序号
    python seed.py FPI_MT01 335335                      # 放映机坐标 / 录像盘 / 图案
    python seed.py TFS_MT03 14014                       # 六阀门位置与坐标
    python seed.py FPB_MT03 249249                      # 区域1/3 各 4 个移动靶点位
    python seed.py FPC_MT02 710710                      # Canals 区 5 个出票机点位
    python seed.py SMC_MT02 453453                      # 4 个人偶下半身所在房间（按颜色）
    python seed.py SMC_MT02 453453 --trace              # 附带组洗牌与距离过滤过程
    python seed.py PSA_MT01 219219                      # 最短路径：每把钥匙 + 录像盘的房间与坐标
    python seed.py DTS_MT01 252252                      # 3 个调频器 / 3 条线索 / 最终模型
    python seed.py SR_Trial 485485                      # 第2阶段：4 间密码房点位 + 4 位密码
    python seed.py PF_Trial 701701                      # 拧阀门点位+拧格数 + 密码房逐位数字
    python seed.py SRR_MT02 909909                      # 三轮调频：图案 / 台点位 / 陷阱
    python seed.py SRR_MT02 909909 --trace              # 附带选中集与记录绘制过程
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
    level/*.md    逐关取证与算法文档（如 level/TSR_MT02.md）
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
    SAMPLES_TSR, SAMPLES_TSR_MT02, SAMPLES_FPI_MT01, SAMPLES_TFS, SAMPLES_MHS,
    SAMPLES_MHS_PICK, TFS_SAMPLE_ROOMS, SAMPLES_PSA, SAMPLES_SRR,
    SAMPLES_SRR_MT02,
    SRR_HOUSES, SRR_HOUSE_ORDER, SRR_ROOM_COMPONENTS, SRR_ROOM_CENTERS,
    SRR_MT02_COORDS, SRR_MT02_SECTION1, SRR_MT02_PATTERN_ZH, SRR_MT02_TUNERS,
    CHJ_MT02_COORDS, CHJ_MT02_ACTORS,
    CHJ_MT02_SYMBOL_NAMES, CHJ_MT02_SYMBOL_COORDS, CHJ_MT02_SYMBOL_ROOMS,
    MHS_SYMBOL_NAMES, MHS_ZONES, MHS_ZONE_BY_KEY,
    MHS_SYMBOLS, TSR_BUCKETS, TSR_BUCKET_NAMES, TSR_MANDATORY_ROOM,
    TSR_MT02_CONVERTERS, TSR_MT02_LOTS, TSR_MT02_FIXED, TSR_MT02_COORDS,
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
    'FPB_MT03': {
        'name': '游乐场谷仓 · 击倒移动靶开闸门',
        'english': 'Drop the moving targets to open the gates',
        'map': 'FunParkBarn',
        'kind': 'SimpleObjectiveCoordinator',
        'movingtargets': True,
        'partial': True,     # 区域4（出口闸门）记录不全，未闭环
        'doc': 'release/coop/FPB_MT03/FPB_MT03.md',
    },
    'FPC_MT02': {
        'name': '游乐场运河 · 赎回自由（Canals 区出票机）',
        'english': 'Redeem Your Freedom',
        'map': 'FunParkCanal',
        'kind': 'TicketBooth',
        'ticketbooth': True,
        'partial': True,     # 只闭环第 1 区域 Canals；Office 区未闭环，不输出
        'coordinator': 'MT02_SimpleTicketBooth_CoordBP_Canals',
        'doc': 'release/home/FPC_MT02.md',
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
    'TSR_MT02': {
        'name': '电视台屋顶 · 接管电视广播（可用刻录机点位）',
        'english': 'Take over the TV Broadcast',
        'map': 'TelevisionStudioRooftop',
        'kind': 'RBRandomManager/RandomizationLot',
        'coordinator': 'RBRandomManager_1',
        'converters': True,
        'doc': 'level/TSR_MT02.md',
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
    'SRR_MT02': {
        'name': '郊区住宅区 · 调频图案三轮匹配',
        'english': 'Tune the frequency panels to the displayed patterns (3 rounds)',
        'map': 'SuburbRiotResidential',
        'kind': 'OrderedClueFrequency',
        'coordinator': 'SRR_MT02_OrderedClueFrequency_RichDistrict',
        'freqclue': True,
        'doc': 'release/coop/SRR_MT02/ANALYSIS.md',
    },
    'SR_TRIAL': {
        'name': '骚乱郊区 · 找密码开安全屋',
        'english': 'Find A Way To Open The Panic Room (phase 2: passcode rooms)',
        'map': 'SuburbRiot',
        'kind': 'MultiroomPuzzle',
        'coordinator': 'SR_B02_ObjCoord_MultiRoomPuzzle',
        'srtrial': True,   # 只推第 2 阶段：4 间密码房 + 4 位密码
        'doc': 'release/coop/SR_Trial/SR_Trial.md',
    },
    'PF_TRIAL': {
        'name': '监狱农场 · 拧阀门与密码房',
        'english': 'PrisonFarm trial: valve maze + passcode cells',
        'map': 'PrisonFarm',
        'kind': 'ValveMaze+MultiroomPuzzle',
        'pftrial': True,
        'doc': 'release/coop/PF_Trial/PF_Trial.md',
    },
    'CHJ_MT03': {
        'name': '法院 · 贿赂其余可收买的法官',
        'english': 'Bribe the remaining judges (match briefcases to sign patterns)',
        'map': 'CourthouseJudicial',
        'kind': 'SignBoards',
        'coordinator': 'CHJ_MT03_RemainingBribes',
        'signboards': True,
        'doc': 'release/coop/CHJ_MT03/CHJ_MT03.md',
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
    'TSR2': 'TSR_MT02', 'TSR-MT02': 'TSR_MT02',
    'CONVERTER': 'TSR_MT02', 'CONVERTERS': 'TSR_MT02',
    'CASSETTE': 'TSR_MT02', 'BROADCAST': 'TSR_MT02',
    'FPI1': 'FPI_MT01', 'DIAPORAMA': 'FPI_MT01',
    'FPB': 'FPB_MT03', 'FPB3': 'FPB_MT03', 'BARN': 'FPB_MT03',
    'MOVINGTARGET': 'FPB_MT03', 'MOVINGTARGETS': 'FPB_MT03',
    'FPC': 'FPC_MT02', 'FPC2': 'FPC_MT02', 'CANAL': 'FPC_MT02',
    'CANALS': 'FPC_MT02', 'TICKET': 'FPC_MT02', 'TICKETS': 'FPC_MT02',
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
    'SRR2': 'SRR_MT02', 'SRR-MT02': 'SRR_MT02', 'FREQ': 'SRR_MT02',
    'FREQUENCY': 'SRR_MT02', 'ORDEREDCLUE': 'SRR_MT02',
    'ORDEREDCLUEFREQUENCY': 'SRR_MT02', 'TUNER': 'SRR_MT02', 'TUNERS': 'SRR_MT02',
    'SR': 'SR_TRIAL', 'SRT': 'SR_TRIAL', 'SRTRIAL': 'SR_TRIAL',
    'PANIC': 'SR_TRIAL', 'PANICROOM': 'SR_TRIAL', 'B02': 'SR_TRIAL',
    'PF': 'PF_TRIAL', 'PFTRIAL': 'PF_TRIAL', 'PRISON': 'PF_TRIAL',
    'PRISONFARM': 'PF_TRIAL', 'B04': 'PF_TRIAL', 'B05': 'PF_TRIAL',
    'VALVEMAZE': 'PF_TRIAL', 'CELLS': 'PF_TRIAL',
}

# ---------------------------------------------------------------------------
# 关卡静态数据
# ---------------------------------------------------------------------------
# 候选池 / 名称映射 / 坐标 / 实测样本都在 data/*.json，由 seeddata.py 载入；
# 这里只留下与算法写在一起才看得懂的参数（名字链、路径开关、salt）。
#
#   data/mhs_mt01.json        MHS_MT01 图案家族 + 投影符号候选表（0x1436E95F0 的输入）
#   data/tsr_mt01.json        TSR_MT01 候选桶 / 桶名 / 强制房间 / 码位坐标
#   data/tsr_mt02.json        TSR_MT02 19 台刻录机坐标 / 两批 RandomLots / 实测样本
#   data/fpi_mt01.json        FPI_MT01 三组候选 / 图案表 / 放映机坐标
#   data/tfs_mt03.json        TFS_MT03 Sections 原始顺序 / 阀门候选 / 坐标
#   data/chj_mt02.json        CHJ_MT02 协调器组 / 符号 actor / 房间
#   data/psa_mt01.json        PSA_MT01 图案表 / 房间生成点 / 录像盘
#   data/srr_mt01.json        SRR_MT01 协调器 Sections / 房间组件 / 密码盘坐标
#   data/srr_mt02.json        SRR_MT02 三协调器池序 / SectionIndex / 调频器坐标
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


# ---------------------------------------------------------------------------
# TSR_MT02（电视台屋顶 · 接管电视广播）：19 台有限次数刻录机 → 本局可用的点位
# ---------------------------------------------------------------------------
# 正向链路（取证与三条实测回归见 level/TSR_MT02.md）：
#   vtable off_1459A8690 slot 201 = sub_1426325E0「Randomize」
#     → 遍历 RBRandomManager.RandomLots@600（元素 960 B，Num@608）
#     → sub_14019F790(lot, manager, force) = 单批次随机化核心
#       0x14019FBB6  v44 = *(lot+920) + 345 → sub_1401A0F00(v44, Min, Max) 算 K
#       0x14019FF06  sub_1401A0F00(*(lot+920) + k + 148, 0, |cand|-1) 抽第 k 台
#       0x1401A068C  2 - RandBool(i + *(lot+920) + 51946)（BaseState=0 时的兜底）
#       sub_1404FF400 按人数取 Values1P/2P/3P、按难度 override 取 Min/Max
#       sub_1402D29E0 = RandSeeded(seed, N, level_seed % 1000)
#   候选池每轮按原索引重建，只排除「已选中」与 3D 距离 < MinDistanceBetweenActors；
#   池顺序是关卡 actor 加载序（字典序），不是 JSON 里 RandomActors 的数组序。
# 之前按样本反解 32 位 base 的路线全部作废：base 不是 GetSeed+crc32，
# 就是关卡数据里的 RandomizerId 加上述调用点立即数。
TSR_MT02_K_SEED_OFFSET = 345
TSR_MT02_DRAW_SEED_OFFSET = 148
TSR_MT02_FALLBACK_SEED_OFFSET = 51946


def _tsr_mt02_state_value(name):
    return {'NotApplicable': 0, 'StateA': 1, 'StateB': 2, 'Ignored': 3}.get(name, 0)


def _tsr_mt02_count(lot, field, players, difficulty):
    """sub_1404FF400：FIntByDifficulty → 当前人数/难度下的激活数量界。

    本关 Values1P/2P/3P 的 override 全为空、四个难度档也只有 Normal 被
    override，因此任何 (人数, 难度) 都取 DefaultValues.NormalLocalValue
    （Lot0 = 3/9，Lot1 = 1/1）。overrides 字段留给别的关卡复用。
    """
    ov = lot.get('overrides') or {}
    per_player = (ov.get('players') or {}).get(str(players)) or {}
    if field in per_player:
        return per_player[field]
    per_diff = (ov.get('difficulty') or {}).get(difficulty) or {}
    if field in per_diff:
        return per_diff[field]
    return lot[field]


def _tsr_mt02_dist2(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def _predict_tsr_mt02(level_seed, players=1, difficulty='easy', trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    salt = level_seed % 1000
    tr = [] if trace else None
    rows = []
    for conv in TSR_MT02_CONVERTERS:
        rows.append({
            'actor': conv['actor'],
            'short': conv['short'],
            'coordinates': [conv['x'], conv['y'], conv['z']],
            'active': False,
            'state': 'StateB',
            'lot': None,
            'order': None,
            'fixed': False,
        })
    by_actor = {row['actor']: row for row in rows}
    lots_info = []
    for lot in TSR_MT02_LOTS:
        names = lot['actors']
        R = lot['randomizer_id']
        lo = _tsr_mt02_count(lot, 'min_activation', players, difficulty)
        hi = _tsr_mt02_count(lot, 'max_activation', players, difficulty)
        K = lo + sc.rand_seeded(R + TSR_MT02_K_SEED_OFFSET,
                                hi - lo + 1, level_seed)
        d2 = lot['min_distance'] ** 2
        chosen = []
        draws = []
        for k in range(K):
            cand = []
            for i, name in enumerate(names):
                if i in chosen:
                    continue
                pos = TSR_MT02_COORDS[name]
                if any(_tsr_mt02_dist2(pos, TSR_MT02_COORDS[names[j]]) < d2
                       for j in chosen):
                    continue
                # MinDistanceFromSAS 两批都是 0，SAS 点集不参与过滤
                cand.append(i)
            if not cand:
                break
            idx = sc.rand_seeded(R + k + TSR_MT02_DRAW_SEED_OFFSET,
                                 len(cand), level_seed)
            p = cand[idx]
            chosen.append(p)
            row = by_actor[names[p]]
            row.update({'active': True, 'state': lot['desired_state'],
                        'lot': lot['name'], 'order': k + 1,
                        'fixed': bool(lot.get('fixed'))})
            draws.append({'k': k, 'candidates': len(cand), 'idx': idx,
                          'actor': names[p]})
            if tr is not None:
                tr.append('%s k=%d K=%d |cand|=%d seed=%d idx=%d -> %s'
                          % (lot['name'], k, K, len(cand),
                             R + k + TSR_MT02_DRAW_SEED_OFFSET, idx,
                             row['short']))
        # 未选中的机器写 BaseState；只有 BaseState=NotApplicable(0) 时才走
        # 2 - RandBool(i + R + 51946) 兜底，本关两批都是 StateB，不触发。
        if _tsr_mt02_state_value(lot['base_state']) == 0:
            for i, name in enumerate(names):
                row = by_actor[name]
                if row['active']:
                    continue
                state = 2 - sc.rand_bool(
                    i + R + TSR_MT02_FALLBACK_SEED_OFFSET, level_seed)
                row['state'] = 'StateA' if state == 1 else 'StateB'
                row['active'] = state == 1
                row['lot'] = lot['name']
        else:
            for name in names:
                row = by_actor[name]
                if not row['active']:
                    row['state'] = lot['base_state']
                    row['lot'] = lot['name']
        lots_info.append({
            'name': lot['name'], 'randomizer_id': R,
            'min_activation': lo, 'max_activation': hi, 'K': K,
            'selected': len(chosen), 'min_distance': lot['min_distance'],
            'salt': salt, 'actors': [names[i] for i in chosen],
            'draws': draws,
        })
    if tr is not None:
        for info in reversed(lots_info):
            tr.insert(0, '%s: R=%d Min/Max=%d/%d K=%d 实选=%d'
                      % (info['name'], info['randomizer_id'],
                         info['min_activation'], info['max_activation'],
                         info['K'], info['selected']))
    active_order = [a for info in lots_info for a in info['actors']]
    # 19 台全表只用于上面的正向计算；对外只返回本局可用的点位（按抽取顺序）。
    converters = [by_actor[a] for a in active_order]
    return {
        'converters': converters,      # 只含 StateA，顺序 = 抽取顺序（Lot0 → Lot1）
        'active_order': active_order,  # 同上，纯 actor 名列表
        'lots': lots_info,
        'notes': [
            'BP_2 由 Lot1（Min=Max=1）固定刷新，与 seed 无关。',
            '只返回本局可用的刻录机；19 台静态全表在 data/tsr_mt02.json。',
        ],
        'trace': tr,
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


# FPB_MT03（游乐场谷仓 · 移动靶）：sub_1402AE7F0 → sub_1402AF490 → sub_1402B05C0。
# 池按名字典序升序 → 分类趟（必选 swap 删除）→ 逐抽
# idx = RandSeeded(crc32_fname("Objective Actors") + GetSeed(协调器) + 已选数, 池剩余)
# 每抽后按 DistanceBetweenSameObjectives=1000 剔除近邻（|ΔZ| <= z_tol=105）。
# 只输出区域1/3：两 seed（249249/520520）各 4/4 逐靶闭环，且不含经验排除集。
# 区域2/4 未闭环（sub_1402B4CA0 用运行期位置、区域4 记录不全），不输出。
# 轨道端点/相位点位来自 release/coop/FPB_MT03 反编译成果，见 FPB_MT03_SEED.md。
FPB_MT03_AREAS = ('MT03_FirstDoor_Target', 'MT03_ThirdDoor_Target')
FPB_MT03_SAMPLES = {
    249249: {
        'MT03_FirstDoor_Target': {'FunParkBarn_DropTarget_FirstGate-25',
                                  'FunParkBarn_DropTarget_FirstGate-01',
                                  'FunParkBarn_DropTarget_FirstGate-5',
                                  'FunParkBarn_DropTarget_FirstGate-4'},
        'MT03_SecondDoor_Target': {'FunParkBarn_DropTarget_SecondGate-13',
                                   'FunParkBarn_DropTarget_SecondGate-8',
                                   'FunParkBarn_DropTarget_SecondGate-6',
                                   'FunParkBarn_DropTarget_SecondGate-16'},
        'MT03_ThirdDoor_Target': {'FunParkBarn_DropTarget_ThirdGate-8',
                                  'FunParkBarn_DropTarget_ThirdGate-26',
                                  'FunParkBarn_DropTarget_ThirdGate-4',
                                  'FunParkBarn_DropTarget_ThirdGate-12'},
    },
    520520: {
        'MT03_FirstDoor_Target': {'FunParkBarn_DropTarget_FirstGate-25',
                                  'FunParkBarn_DropTarget_FirstGate-6',
                                  'FunParkBarn_DropTarget_FirstGate-01',
                                  'FunParkBarn_DropTarget_FirstGate-4'},
        'MT03_SecondDoor_Target': {'FunParkBarn_DropTarget_SecondGate-17',
                                   'FunParkBarn_DropTarget_SecondGate-15',
                                   'FunParkBarn_DropTarget_SecondGate-13',
                                   'FunParkBarn_DropTarget_SecondGate-8'},
        'MT03_ThirdDoor_Target': {'FunParkBarn_DropTarget_ThirdGate-8',
                                  'FunParkBarn_DropTarget_ThirdGate-9',
                                  'FunParkBarn_DropTarget_ThirdGate-14',
                                  'FunParkBarn_DropTarget_ThirdGate-30'},
    },
}


def _fpb_data():
    with open(os.path.join(_HERE, 'data', 'fpb_mt03.json'), encoding='utf-8') as fp:
        return json.load(fp)


# 短名 -> (轨道端点A, 轨道端点B, 同步类型, 细分档N)；R=RandomTarget / C=CDO默认 / N=Noise
# 来源：paks/MAP/Maps/FunParkBarn/FPB_MT03_B00.json 的 TranslationMovable_BP_n。
FPB_MT03_TRACKS = {
    'FirstGate-01': ((9940.7,12395.4,216.3), (9873,12420.1,216.3), 'C', 10),
    'FirstGate-11': ((9376.3,14327.8,333.5), (9376.3,14327.8,202.3), 'R', 4),
    'FirstGate-12': ((9198.9,14917.3,346.7), (9362.1,14917.4,346.7), 'R', 4),
    'FirstGate-16': ((11755.8,12196.5,410.2), (11755.8,12402.9,410.2), 'R', 5),
    'FirstGate-17': ((11158.6,11145.1,317.7), (10974.8,11145.2,317.7), 'R', 4),
    'FirstGate-19': ((10264.2,14612.3,419.8), (10439.9,14612.5,419.8), 'R', 5),
    'FirstGate-2': ((9514.6,13070.6,203), (9514.7,13240.1,203), 'R', 5),
    'FirstGate-20': ((9889.6,13542.3,377.9), (9889.5,13691.1,377.1), 'R', 4),
    'FirstGate-21': ((9889.7,13039.3,377.1), (9889.7,13194.2,377.1), 'R', 4),
    'FirstGate-23': ((11411.9,13117.1,377.9), (11191.1,13117.2,377.9), 'C', 10),
    'FirstGate-24': ((11177.2,11632.7,376.9), (11330.5,11785.8,376.9), 'C', 10),
    'FirstGate-25': ((11757.8,12727.7,343), (11757.7,12899,343), 'R', 4),
    'FirstGate-3': ((10749.6,14036.8,375.8), (10749.7,14273.4,375.8), 'C', 10),
    'FirstGate-4': ((9514.8,13523.5,203), (9515,13693.5,203), 'R', 5),
    'FirstGate-5': ((10751,13598.5,375.9), (10751.1,13835.2,375.9), 'C', 10),
    'FirstGate-6': ((11784.5,14355.8,353.1), (11784.6,14355.8,229.7), 'R', 3),
    'FirstGate-7': ((11502.8,11958,376.9), (11651.2,12106.2,376.9), 'C', 10),
    'FirstGate-8': ((9371.1,11423.3,439.3), (9371.2,11423.4,259.8), 'R', 4),
    'FirstGate-9': ((10946.8,13116.8,377.9), (10735,13116.9,377.9), 'C', 10),
    'ThirdGate-10': ((5139.8,12286.1,386.5), (5323.5,12292,390.2), 'R', 4),
    'ThirdGate-12': ((6720.6,13873.3,377.3), (6501.6,13892.5,377.3), 'C', 10),
    'ThirdGate-14': ((5312.4,12927.8,284.4), (5315.1,12789.5,284.4), 'R', 4),
    'ThirdGate-26': ((4143.3,11622.9,364.2), (4143.3,11431.2,364.2), 'R', 4),
    'ThirdGate-27_11': ((6017.7,13051.4,229.8), (5879.7,13060.7,229.8), 'R', 4),
    'ThirdGate-28': ((5401.6,11627.7,378.6), (5388.7,11480.1,378.6), 'R', 4),
    'ThirdGate-29': ((5077,11754,378.6), (5063.9,11904.6,378.6), 'R', 4),
    'ThirdGate-3': ((4275.5,14336.2,390.8), (4275.5,14336.2,225.7), 'R', 4),
    'ThirdGate-30': ((4305,14759.5,246.8), (4496.8,14759.5,246.8), 'R', 4),
    'ThirdGate-31': ((6257.8,13917.8,377.2), (6041.9,13936.8,377.2), 'C', 10),
    'ThirdGate-4': ((5104.1,14339.1,411), (5104.1,14339.1,229.6), 'R', 4),
    'ThirdGate-6': ((6171.8,12856,364.1), (6185,12675.2,364.1), 'R', 4),
    'ThirdGate-7': ((6730.1,11481,296.1), (6733.4,11641.7,296.1), 'R', 4),
    'ThirdGate-8': ((6607.8,10933.7,241.9), (6463.8,10933.7,241.9), 'R', 4),
    'ThirdGate-9': ((5494.4,10641.6,346.4), (5646.4,10641.6,346.4), 'R', 4),
}


def _fpb_track(name):
    row = FPB_MT03_TRACKS.get(name.replace('FunParkBarn_DropTarget_', ''))
    return ([list(row[0]), list(row[1])], row[2], row[3]) if row else (None, None, None)


def _fpb_phase_pos(name, level_seed, k=0):
    """RandomTarget 相位点位：sub_1435FEB20 / sub_1435FF2E0 / sub_1435FED70。

    comp+0x134 构造默认值 -1；p = 2*RandSeeded(-1+k, N/2+1, seed) [+1 当 k 偶]，
    pos = A + (B-A)*p/(N+1)。k 为运行期周期序号，这里默认取 k=0。
    """
    track, typ, N = _fpb_track(name)
    if not track:
        return None
    A, B = track
    if typ != 'R':
        return list(A)
    v2 = float(N + 1)
    s = (0xFFFFFFFF + k) & sc.M32
    if not s:
        return None                                  # 引擎退化 rand()，不可预测
    if k & 1:
        p = 2 * sc.rand_seeded(s, (int(v2 - 0.5) >> 1) + 1, level_seed)
    else:
        v3 = int(-0.5 - v2) >> 1
        p = 0 if v3 > -2 else 2 * sc.rand_seeded(s, ~v3 & 0xFFFF, level_seed) + 1
    t = p / float(N + 1)
    return [A[i] + (B[i] - A[i]) * t for i in range(3)]


def _fpb_purge(pool, ref, coords, dxy, dz):
    """sub_1402B3C30：尾→头剔除「水平 < dxy 且 |ΔZ| <= dz」的候选（swap 删除）。"""
    i = len(pool) - 1
    while i >= 0:
        a = coords[pool[i]]
        if dxy > 0 and (a[0] - ref[0]) ** 2 + (a[1] - ref[1]) ** 2 < dxy * dxy \
                and (dz < 0 or abs(a[2] - ref[2]) <= dz):
            pool[i] = pool[-1]
            pool.pop()
        i -= 1


def _fpb_draw(area, coord, level_seed, z_tol, trace):
    """sub_1402B05C0 单区域复刻：返回（选中列表[必选在前, 其后为抽中顺序], base）。"""
    pool = sorted(area['coords'], key=str.lower)      # sub_1402B46B0 名字典序升序
    coords = {k: tuple(v) for k, v in area['coords'].items()}
    force, exclude = set(area['force']), set(area.get('exclude', ()))
    picked = []                                       # v250 必选（尾→头遇到序）
    for remover in (force, exclude):                  # ① 分类趟；② sub_1402B4CA0 趟
        i = len(pool) - 1
        while i >= 0:
            if pool[i] in remover:
                if remover is force:
                    picked.append(pool[i])
                pool[i] = pool[-1]
                pool.pop()
            i -= 1
    result = list(picked)                             # v248（无 helper 恒选）本关恒空
    base = (sc.crc32_fname(area['salt']) +
            sc.seed_chain([sc.LEVEL_OBJECT, coord])) & sc.M32
    for name in picked:                               # 必选先各剔除一轮近邻
        _fpb_purge(pool, coords[name], coords, area['dist'], z_tol)
    quota = area['count'] - len(result)
    k = 0
    while pool and quota > 0:
        seed = (base + len(result)) & sc.M32
        n = len(pool)
        idx = sc.rand_seeded(seed, n, level_seed)
        pick = pool[idx]
        pool[idx] = pool[-1]
        pool.pop()
        result.append(pick)
        quota -= 1
        _fpb_purge(pool, coords[pick], coords, area['dist'], z_tol)
        if trace is not None:
            trace.append('  %s 抽#%d seed=%d N=%d idx=%d → %s'
                         % (area['zone'], k, seed, n, idx, pick))
        k += 1
    return result, base


def _fpb_key(name):
    x = name.rsplit('-', 1)[-1].split('_')[0]
    return (int(x) if x.isdigit() else 0, name)


def _predict_fpb_mt03(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    data = _fpb_data()
    tr = [] if trace else None
    areas = []
    for coord in FPB_MT03_AREAS:
        area = dict(data['areas'][coord], salt=data.get('salt', 'Objective Actors'))
        names, base = _fpb_draw(area, coord, level_seed, data['z_tol'], tr)
        targets = []
        for n in sorted(names, key=_fpb_key):
            track, _, _ = _fpb_track(n)
            targets.append({
                'name': n, 'short': n.rsplit('-', 1)[-1],
                'coordinates': list(area['coords'][n]),
                'track': track,                       # 轨道两端（静态资产）
                'phase': _fpb_phase_pos(n, level_seed),   # k=0 相位点位（seed 驱动）
            })
        areas.append({'coord': coord, 'zone': area['zone'], 'base': base,
                      'targets': targets})
    return {'moving_targets': areas, 'trace': tr}


# FPC_MT02（游乐场运河 · 赎回自由）：两个售票亭协调器各自随机启用 5 个出票机。
# 只整合已闭环的第 1 区域 Canals（41 个 A 型候选 + 固定教学机）。
# 反编译链路与验证见 release/home/FPC_MT02.md：
#   sub_1402AF2D0（bUseSpawnerActorsRandomization，setup@协调器+4096，
#     盐名宽串 @0x1466F52CE = "Item Spawner"）→ sub_140A61C30（按
#     ItemSpawnerClass 收集世界 actor）→ sub_1402B05C0（名字典序 →
#     base=crc32_fname(盐)+GetSeed(协调器) → idx=RandSeeded(base+已选数,|池|)
#     → RemoveAtSwap → sub_1402B3C30 按 1500 剔除近邻）。
# 与 FPB_MT03 的 _fpb_draw 是同一个引擎，直接复用；z_tol=-1 表示不限制 ΔZ。
# ⚠️ Office 区（28 个 B 型候选）两条实测 seed 都未闭环，不输出。
FPC_MT02_SAMPLES = {
    710710: {'MT03_FPC_TriggerableTicketDispenser_01_BP_Intro',
             'MT02_FPC_TriggerableTicketDispenser_01_BP_CanalA_2',
             'FPC_TriggerableTicketDispenser_01_A_BP_58',
             'FPC_TriggerableTicketDispenser_01_A_BP_42',
             'MT02_FPC_TriggerableTicketDispenser_01_BP_CanalA_13'},
}


def _fpc_data():
    with open(os.path.join(_HERE, 'data', 'fpc_mt02.json'), encoding='utf-8') as fp:
        return json.load(fp)


def _predict_fpc_mt02(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    data = _fpc_data()
    tr = [] if trace else None
    names, base = _fpb_draw(data, data['coord'], level_seed, -1.0, tr)
    return {
        'ticket_points': [{'name': n, 'coordinates': list(data['coords'][n])}
                          for n in names],
        'base': base,
        'notes': ['仅第 1 区域 Canals 的 5 个出票机；Office 区未闭环，不输出'],
        'trace': tr,
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


# CHJ_MT02 前置随机化（sub_1402B05C0）+ 主循环（sub_1436E95F0），反编译证据与
# 验证见 release/coop/CHJ_MT02/CHJ_MT02.md §4。713713/620620/20020/135135 的
# actor+密码 20 条 + 711711（3P）外部验证 4 条共 24/24 全中：
#   前置：base = crc32_fname("Objective Actors") + GetSeed(协调器)；
#   机位候选池 = actor 名字序（Yellow/Blue 各 21、Tuto 1），逐个抽取：
#       idx = RandSeeded(base + 已抽数, 池剩余)（末尾交换删除），
#   随后按 DistanceBetweenSameObjectives（Yellow/Blue=1200uu、Tuto=120uu）
#   剔除近邻候选——sub_1402B3C30 语义为「从后向前、末尾交换删除」。
#   主循环每容器槽位 i：符号组 RandSeeded(i+46541)、真投影器 RandSeeded(i+99041)
#   各自交换删除抽出配对，密码 Draw(GetSeed(投影器) + GetSeed(协调器) + i)。
#   真投影器多于容器时走假投影分支 v44=(n-c)/c（盐 99042+i+j / 86550+i+j，
#   尾部裁剪到 c*(v44+1)）；本关常态 2 抽 2 容器 v44=0，走不到。
CHJ_MT02_SETUPS = {
    # coordinator: (机位前缀, DistanceBetweenSameObjectives)
    'MT02_Projections_Coordinator_BP_YellowSide': ('A', 1200.0),
    'MT02_Projections_Coordinator_BP_BlueSIde': ('B', 1200.0),
    'MT02_Projections_Coordinator_BP_Tuto': ('C', 120.0),
}
CHJ_MT02_PICK_SALT = 'Objective Actors'   # 前置种子基盐名（24/24 锁定；同分发
                                          # 路径的 "Projection Actors/Containers"
                                          # 字符串未生效）
CHJ_MT02_SYMBOL_SALT = 46541              # 符号组抽签 RandSeeded(i+46541)
CHJ_MT02_REAL_SALT = 99041                # 真投影器重排 RandSeeded(i+99041)
# 游戏内实测房间显示名（actor 所在房与投影落点可能不同），其余用 symbol_rooms
CHJ_MT02_ROOM_IN_GAME = {
    'CHJ_MT02_ProjectionSymbol_BP_A2': 'RBRoom_West_ConstructionGore',
    'CHJ_MT02_ProjectionSymbol_BP_A3': 'West_ConstructionGore',
    'CHJ_MT02_ProjectionSymbol_BP_A6': 'RBRoom_West_PrivateOffice',
    'CHJ_MT02_ProjectionSymbol_BP_A19': 'RBRoom_West_Blueprints',
    'CHJ_MT02_ProjectionSymbol_BP_B4': 'RBRoom_EastCorridor_1_Slave_2',
    'CHJ_MT02_ProjectionSymbol_BP_B14': 'RBRoom_East_Museum',
    'CHJ_MT02_ProjectionSymbol_BP_B16': 'East_BathRoom_Crawlspace',
    'CHJ_MT02_ProjectionSymbol_BP_B24': 'Main_CourtRoom_Balcony',
    'CHJ_MT02_ProjectionSymbol_BP_C_4': 'RBRoom_BackEntrance_Stairs',
}
# 实测样本（release/coop/CHJ_MT02/test.txt、release/coop/test.txt）：
# symbol -> (actor 短名或 None=未实测, 密码)
CHJ_MT02_SAMPLES_EXTRA = {
    135135: {'Skull': ('A2', '820'), 'Spiral': ('A19', '067'),
             'Pentagram': ('B4', '219'), 'Sun': ('B14', '874'),
             'TriangleCircle': ('C_4', '408')},
    711711: {'Spiral': (None, '410'), 'Sun': (None, '569'),
             'Pentagram': (None, '185'), 'TriangleCircle': (None, '340')},
}


def _chj_mt02_pool(letter):
    prefix = 'CHJ_MT02_ProjectionSymbol_BP_' + letter
    return sorted(a for a in CHJ_MT02_SYMBOL_COORDS if a.startswith(prefix))


def _chj_mt02_pick(letter, coord_name, count, threshold, level_seed):
    """前置 Actor Randomization：抽 count 个真投影器（含距离剔除）。"""
    level_crc = sc.crc32_fname('PersistentLevel')
    base = (sc.crc32_fname(CHJ_MT02_PICK_SALT) +
            sc.seed_of_object(coord_name, level_crc)) & sc.M32
    remaining = _chj_mt02_pool(letter)
    picked = []
    while remaining and len(picked) < count:
        index = sc.rand_seeded((base + len(picked)) & sc.M32,
                               len(remaining), level_seed)
        actor = remaining[index]
        remaining[index] = remaining[-1]
        remaining.pop()
        picked.append(actor)
        if threshold > 0:
            loc = CHJ_MT02_SYMBOL_COORDS[actor]
            for i in range(len(remaining) - 1, -1, -1):
                other = CHJ_MT02_SYMBOL_COORDS[remaining[i]]
                if math.dist(loc, other) < threshold:
                    remaining[i] = remaining[-1]
                    remaining.pop()
    return picked


def _predict_chj_mt02(level_seed, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    level_crc = sc.crc32_fname('PersistentLevel')
    projections = []
    for coord_name, groups, tutorial in CHJ_MT02_COORDS:
        letter, threshold = CHJ_MT02_SETUPS[coord_name]
        picked = _chj_mt02_pick(letter, coord_name, len(groups),
                                threshold, level_seed)
        coord_seed = sc.seed_of_object(coord_name, level_crc)
        clues = list(groups)
        order = list(picked)
        for i in range(len(groups)):
            group_index = sc.rand_seeded(i + CHJ_MT02_SYMBOL_SALT,
                                        len(clues), level_seed)
            group = clues[group_index]
            clues[group_index] = clues[-1]
            clues.pop()
            real_index = sc.rand_seeded(i + CHJ_MT02_REAL_SALT,
                                       len(order), level_seed)
            actor = order[real_index]
            order[real_index] = order[-1]
            order.pop()
            base = (sc.seed_of_object(actor, level_crc) + coord_seed + i) & sc.M32
            code = _chj_mt02_draw_code(base, level_seed)
            projections.append({
                'symbol': group,
                'symbol_name': CHJ_MT02_SYMBOL_NAMES[group],
                'room': CHJ_MT02_ROOM_IN_GAME.get(actor)
                        or CHJ_MT02_SYMBOL_ROOMS.get(actor),
                'actor': actor,
                'coordinates': CHJ_MT02_SYMBOL_COORDS.get(actor),
                'coordinate_type': 'actor',
                'code': code,
                'tutorial': tutorial,
            })
            if trace:
                print('    CHJ2 %s 槽%d 符号=%s 投影器=%s 密码=%s'
                      % (letter, i, group, actor.split('_BP_')[-1], code))
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


# ---------------------------------------------------------------------------
# SRR_MT02（SuburbRiotResidential）：OrderedClueFrequency 调频图案三轮
# ---------------------------------------------------------------------------
# 模型定稿见 release/coop/SRR_MT02/ANALYSIS.md（test.txt 9/9 纯 seed 全闭环）。
# 链路（REA 反编译）：
#   选中集  sub_1402B05C0：显式表 → sub_1402B46B0 名字典序排序 → SectionIndex 分桶
#           → bSplit 时 sub_1402C30C0 组洗牌（每组自增计数器）→ quota(DesiredCount)
#           → 组内 RandSeeded(v246+已选数, |池|) swap 抽取 + sub_1402B3C30 距离过滤
#           （水平<Distance 剔除、swap 删除、从尾到头、跨组预过滤）
#           v246 = crc32_fname("Objective Actors") + GetSeed(coord) + 组数
#   绑定    sub_14361C230：显式表序∩选中集 → intro-sort（k<0.5 换末尾）→
#           SectionIndex 分桶（插入序）→ 组洗牌（GetSeed+g）→ quota(显示屏数=3)
#           记录 off=v69+v68：台 cs+243551+off、图案 cs+223551+off（cs=GetSeed+组数）
#           剩余台配陷阱图案 cs+253526+j
SRR2_PATTERN_OFFSET = 223551   # 显示图案
SRR2_TUNER_OFFSET = 243551     # 显示台
SRR2_TRAP_OFFSET = 253526      # 陷阱图案
SRR2_PICK_SALT = 'Objective Actors'
SRR2_ACTOR_PREFIX = 'FrequencyMatchBlacklit_'


def _srr2_sec(name):
    return 1 if name in SRR_MT02_SECTION1 else 0


def _srr2_quota(sizes, want):
    """sub_1402C30C0 的 quota 分配：+1 循环 → 比例 → 余量给首个放得下的组。"""
    ng = len(sizes)
    quota = [0] * ng
    total = sum(sizes)
    remain, i, extra = want, 0, 0
    while True:
        if i < ng:
            quota[i] += 1
        extra = remain - 1
        can_continue = remain >= 2
        more_groups = (i + 1) < ng
        i += 1
        remain -= 1
        if not (more_groups and can_continue):
            break
    if extra > 0:
        for j in range(ng):
            if extra <= 0:
                break
            ratio = (sizes[j] / total) * want
            if ratio > 1.0:
                bump = (int(2 * (ratio - 1.0) + 0.5)) >> 1
                if extra < bump:
                    bump = extra
                quota[j] += bump
                extra -= bump
    if extra != 0:
        for j in range(ng):
            if sizes[j] >= quota[j] + extra:
                quota[j] += extra
                break
    return quota


def _srr2_pop_swap(pool, idx):
    v = pool[idx]
    pool[idx] = pool[-1]
    pool.pop()
    return v


def _srr2_filter_swap(pool, picked, threshold):
    """sub_1402B3C30：从尾到头遍历，水平距离 < threshold 者 swap 剔除。"""
    if threshold <= 0:
        return
    px, py = SRR_MT02_TUNERS[picked][1][:2]
    for i in range(len(pool) - 1, -1, -1):
        if i >= len(pool):
            continue
        qx, qy = SRR_MT02_TUNERS[pool[i]][1][:2]
        if (qx - px) ** 2 + (qy - py) ** 2 < threshold * threshold:
            _srr2_pop_swap(pool, i)


def _srr2_select_set(key, level_seed, trace=False):
    """sub_1402B05C0 选中集：名字序分桶 → 组洗牌 → 抽取+距离过滤。"""
    salt = level_seed % 1000
    conf = SRR_MT02_COORDS[key]
    init = (sc.crc32_fname(SRR2_PICK_SALT)
            + sc.seed_chain(['PersistentLevel', conf['coord']])) & sc.M32
    pool = sorted(conf['pool'])
    buckets = {0: [], 1: []}
    first_seen = []
    for name in pool:
        sec = _srr2_sec(name)
        if sec not in first_seen:
            first_seen.append(sec)
        buckets[sec].append(name)
    pre = [list(buckets[sec]) for sec in first_seen if buckets[sec]]
    counter = init
    out = []
    if conf['split']:
        rem = list(pre)
        for _ in range(len(pre)):
            out.append(_srr2_pop_swap(rem, sc.rand_seeded(counter, len(rem), salt)))
            counter = (counter + 1) & sc.M32
    else:
        out = [list(pool)]
    quotas = _srr2_quota([len(g) for g in out], conf['desired'])
    base = counter & sc.M32
    threshold = conf['distance']
    selected, count = [], 0
    for gi, group in enumerate(out):
        gp = list(group)
        for s in selected:
            _srr2_filter_swap(gp, s, threshold)
        for _ in range(quotas[gi]):
            if not gp:
                break
            pick = _srr2_pop_swap(gp, sc.rand_seeded((base + count) & sc.M32,
                                                     len(gp), salt))
            selected.append(pick)
            count += 1
            _srr2_filter_swap(gp, pick, threshold)
    if trace:
        print('  [%s] 选中集=%s' % (key, ' '.join(selected)))
    return selected


def _srr2_intro_sort(items, level_seed):
    """sub_14361C230 n<=8 选择排序变体：找最后一个 k<0.5 的换到末尾。"""
    salt = level_seed % 1000
    arr = list(items)
    for end in range(len(arr) - 1, 0, -1):
        best = 0
        for j in range(1, end + 1):
            key = sc.rand_fraction(sc.seed_chain(['PersistentLevel', arr[j]]), salt)
            if key < 0.5:
                best = j
        arr[best], arr[end] = arr[end], arr[best]
    return arr


def _srr2_records(key, level_seed, sorted_sel, trace=False):
    """sub_14361C230 记录循环 + 陷阱循环。sorted_sel 为全名列表。"""
    salt = level_seed % 1000
    conf = SRR_MT02_COORDS[key]
    buckets = {0: [], 1: []}
    first_seen = []
    for name in sorted_sel:
        sec = _srr2_sec(name.replace(SRR2_ACTOR_PREFIX, ''))
        if sec not in first_seen:
            first_seen.append(sec)
        buckets[sec].append(name)
    groups = [buckets[sec] for sec in first_seen if buckets[sec]]
    gs = sc.seed_chain(['PersistentLevel', conf['coord']])
    cs = (gs + len(groups)) & sc.M32
    rem = list(groups)
    out = []
    for i in range(len(groups)):
        out.append(_srr2_pop_swap(rem, sc.rand_seeded((gs + i) & sc.M32, len(rem), salt)))
    quotas = _srr2_quota([len(g) for g in out], 3)
    pool = list(conf['patterns'])
    rows, leftover, record = [], [], 0
    for gi, group in enumerate(out):
        members = list(group)
        inner = 0
        while inner < quotas[gi] and record < 3:
            off = inner + record
            tuner = _srr2_pop_swap(members, sc.rand_seeded(
                (cs + SRR2_TUNER_OFFSET + off) & sc.M32, len(members), salt))
            pattern = _srr2_pop_swap(pool, sc.rand_seeded(
                (cs + SRR2_PATTERN_OFFSET + off) & sc.M32, len(pool), salt))
            rows.append((tuner, pattern, record))
            record += 1
            inner += 1
        leftover.extend(members)
    for j, tuner in enumerate(leftover):
        pattern = _srr2_pop_swap(pool, sc.rand_seeded(
            (cs + SRR2_TRAP_OFFSET + j) & sc.M32, len(pool), salt))
        rows.append((tuner, pattern, -1))
    if trace:
        for tuner, pattern, order in rows:
            print('    %s = %s %s' % (tuner.replace(SRR2_ACTOR_PREFIX, ''),
                                      pattern,
                                      '显示%d' % (order + 1) if order >= 0 else '陷阱'))
    return rows, cs


def _predict_srr_mt02(level_seed, trace=False):
    rounds = []
    for index, key in enumerate(('Rich', 'School', 'SasExit'), 1):
        selected = _srr2_select_set(key, level_seed, trace=trace)
        # 绑定输入序 = 显式表序 ∩ 选中集（vtable+2048 getter 按表序重组，9/9 实测定稿）
        table_order = [name for name in SRR_MT02_COORDS[key]['pool']
                       if name in set(selected)]
        sorted_sel = _srr2_intro_sort([SRR2_ACTOR_PREFIX + name
                                       for name in table_order], level_seed)
        rows, cs = _srr2_records(key, level_seed, sorted_sel, trace=trace)
        tuners = []
        display = []
        for full, pattern, order in rows:
            name = full.replace(SRR2_ACTOR_PREFIX, '')
            room, coords = SRR_MT02_TUNERS[name]
            tuners.append({
                'id': name,
                'actor': full,
                'room': room,
                'coordinates': [round(float(c), 1) for c in coords],
                'pattern': pattern,
                'pattern_zh': SRR_MT02_PATTERN_ZH[pattern],
                'order': order,
            })
            if order >= 0:
                display.append(pattern)
        tuners.sort(key=lambda item: (item['order'] < 0, item['order']))
        rounds.append({
            'round': index,
            'key': key,
            'coordinator': SRR_MT02_COORDS[key]['coord'],
            'cs': cs,
            'display': display,
            'display_zh': [SRR_MT02_PATTERN_ZH[p] for p in display],
            'tuners': tuners,
        })
    return {'tuner_rounds': rounds}


# ---------------------------------------------------------------------------
# SR_Trial（SuburbRiot_T08_B02）第 2 阶段：4 间密码房 + 4 位密码
# ---------------------------------------------------------------------------
# 只推第 2 阶段「找密码」（MultiroomPuzzle）：4 间房各 1 张数字贴花，按位次拼密码。
# 链路（release/coop/SR_Trial/SR_Trial.md §4，反编译证据 evidence/）：
#   抽房  sub_14374E420：Sections 按 JSON 顺序逐区抽 1 间（MinimumPuzzleRoomsInSection=1），
#         idx = RandSeeded(剩余需求 + 28042, 区内房间数)，保序删除；补位 28088 本关走不到
#   顺序  同函数原地洗牌：key = RandFraction(compSeed(room)) < 0.5（无 134123 偏移），
#         n<=8 选择排序「最后一个 key<0.5 者换到末尾」→ 位次 = 洗牌后数组的逆序
#   数字  sub_143620E70：共享池 0..9（全 4 间房共用），第 k 位
#         digit = pool[RandSeeded(compSeed(room) + k + 7168, |pool|)]，memmove 保序删除
#   位次  sub_143621120 对本关恒 -1（每区 1 间 < 需求 4）⇒ 位次只由 k 决定
SR_SECTIONS = [
    ['RBRoom_Mansion2nd_GameRoom_Reward', 'RBRoom_Mansion2nd_Fireplace'],  # [0]
    ['RBRoom_Mansion1st_Office', 'RBRoom_Mansion1st_Bathroom_Reward'],     # [1]
    ['RBRoom_Mansion1st_Laundry', 'RBRoom_Mansion1st_Garage'],             # [2]
    ['RBRoom_Mansion2nd_EscortBedroom'],                                   # [3] 唯一房必中
]
SR_ROOM_LABEL = {
    'RBRoom_Mansion2nd_GameRoom_Reward': 'GameRoom',
    'RBRoom_Mansion2nd_Fireplace': 'Lounge',          # 802802 现场显示名
    'RBRoom_Mansion1st_Office': 'Office',
    'RBRoom_Mansion1st_Bathroom_Reward': 'Washroom',  # 802802 现场显示名
    'RBRoom_Mansion1st_Laundry': 'Laundry',
    'RBRoom_Mansion1st_Garage': 'Garage',
    'RBRoom_Mansion2nd_EscortBedroom': 'Bedroom',
}
SR_PICK_OFFSET = 28042     # sub_14374E420 抽房：RandSeeded(剩余 + 28042, |池|)
SR_FILL_OFFSET = 28088     # 同函数补位（本关每区 1 间抽满，走不到，仅备查）
SR_DIGIT_OFFSET = 7168     # sub_143620E70：RandSeeded(seed + 7168, |池|)

# 实测样本（release/coop/SR_Trial/test.txt）：{seed: {房间: (数字, 位次)}, password}
SR_SAMPLES = {
    485485: {
        'rooms': {'RBRoom_Mansion2nd_EscortBedroom': (0, 1),
                  'RBRoom_Mansion1st_Office': (8, 2),
                  'RBRoom_Mansion2nd_GameRoom_Reward': (5, 3),
                  'RBRoom_Mansion1st_Garage': (6, 4)},
        'password': '0856',
    },
    500500: {
        'rooms': {'RBRoom_Mansion1st_Office': (0, 1),
                  'RBRoom_Mansion2nd_GameRoom_Reward': (9, 2),
                  'RBRoom_Mansion1st_Laundry': (8, 3),
                  'RBRoom_Mansion2nd_EscortBedroom': (3, 4)},
        'password': '0983',   # 记录原文 0984 为笔误，逐房数字拼出 0983
    },
    166166: {
        'rooms': {'RBRoom_Mansion2nd_EscortBedroom': (2, 1),
                  'RBRoom_Mansion1st_Office': (5, 2),
                  'RBRoom_Mansion2nd_GameRoom_Reward': (3, 3),
                  'RBRoom_Mansion1st_Laundry': (6, 4)},
        'password': '2536',
    },
    802802: {
        'rooms': {'RBRoom_Mansion2nd_EscortBedroom': (0, 1),
                  'RBRoom_Mansion1st_Garage': (4, 2),
                  'RBRoom_Mansion1st_Bathroom_Reward': (9, 3),
                  'RBRoom_Mansion2nd_Fireplace': (1, 4)},
        'password': '0491',   # 现场显示名 Lounge=Fireplace、Washroom=Bathroom_Reward
    },
}


def _sr_shuffle_rooms(rooms, level_seed, trace=False):
    """sub_14374E420 处理顺序洗牌（n<=8 分支，无 134123）；位次取洗牌后数组的逆序。"""
    salt = level_seed % 1000
    frac = {r: sc.rand_fraction(sc.room_component_seed(r), salt) for r in rooms}
    out = list(rooms)
    end = len(out) - 1
    while end > 0:
        best = 0
        for j in range(1, end + 1):
            if frac[out[j]] < 0.5:
                best = j              # 最后一个 key<0.5 的元素
        if best != end:
            out[best], out[end] = out[end], out[best]
        end -= 1
    if trace:
        print('    SR 洗牌 frac=%s'
              % {SR_ROOM_LABEL[r]: round(frac[r], 4) for r in rooms})
    return out


def _predict_sr_trial(level_seed, trace=False):
    """第 2 阶段：4 间密码房点位（含数字/位次）+ 4 位密码。"""
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    salt = level_seed % 1000
    # ① 抽房：JSON 区序、每区 1 间
    pools = {i: list(p) for i, p in enumerate(SR_SECTIONS)}
    picked, remaining = [], 4
    for sid in range(len(SR_SECTIONS)):
        if remaining <= 0:
            break
        pool = pools[sid]
        for _ in range(min(len(pool), 1)):
            idx = sc.rand_seeded(remaining + SR_PICK_OFFSET, len(pool), salt)
            room = pool.pop(idx)              # 保序删除
            picked.append(room)
            if trace:
                print('    SR 抽房 section=%d 剩余=%d idx=%d/%d -> %s'
                      % (sid, remaining, idx, len(pool) + 1, SR_ROOM_LABEL[room]))
            remaining -= 1
            if remaining <= 0:
                break
    # ② 位次 = 洗牌后数组的逆序
    order = _sr_shuffle_rooms(picked, level_seed, trace=trace)[::-1]
    if trace:
        print('    SR 抽中 = %s' % [SR_ROOM_LABEL[r] for r in picked])
        print('    SR 位次 = %s' % [SR_ROOM_LABEL[r] for r in order])
    # ③ 共享数字池逐位抽（k = 位次下标）
    pool = list(range(10))
    slots = []
    for k, room in enumerate(order):
        comp = sc.room_component_seed(room)
        idx = sc.rand_seeded((comp + k + SR_DIGIT_OFFSET) & sc.M32, len(pool), salt)
        digit = pool.pop(idx)                 # 保序删除
        slots.append({'id': room, 'room': room, 'label': SR_ROOM_LABEL[room],
                      'digit': digit, 'position': k + 1})
        if trace:
            print('    SR k=%d %-10s compSeed=%-10d seed=%-10d pool=%2d idx=%d -> %d'
                  % (k, SR_ROOM_LABEL[room], comp,
                     (comp + k + SR_DIGIT_OFFSET) & sc.M32,
                     len(pool) + 1, idx, digit))
    return {'slots': slots,
            'password': ''.join(str(s['digit']) for s in slots)}


# ---------------------------------------------------------------------------
# PF_Trial（PrisonFarm · PF_LD_T12_B04 阀门迷宫 + PF_LD_T12_B05 密码房）
# ---------------------------------------------------------------------------
# 两个阶段各自闭环（release/coop/PF_Trial/PF_Trial.md 及其 §12，样本 test.txt）：
#   拧阀门  sub_1437DE200（URBValveSystemMazeCoordinator::Randomize）：
#     cs = GetSeed(PF_B04_ObjCoord_ValveSystemMaze)
#     Section A–D 启用（E 的 Values2P=false ⇒ 1P/2P 局禁用，正是“4 个区域”；3P+ 启用）
#     槽 0=A 走固定位（ValveSystemLots FixedOrder=0 → ValveSystem_BP17_2）；
#     其余槽 lot = 池[RandSeeded(cs+234659+槽位,|池|)]（RemoveAtSwap），
#               阀 = lot[RandSeeded(cs+4324+槽位,|候选|)]
#     input=2（ForceInputIndex）；output=[0,1,3][RandSeeded(cs+387+槽位,3)]
#     拧格数 = (output−input) mod 4（701701: A1-B1-C1-D2 ✓）
#   密码房  sub_14374E420 / sub_1436FE410 / sub_143620E70（与 SR_Trial 同链）：
#     每区抽 1 间 idx = RandSeeded(剩余+28042,|池|)（保序删除）
#     位次 k = 单比特洗牌逆序；数字 = 共享池 0..9 第 k 位
#       digit = pool[RandSeeded(compSeed(room)+k+7168,|pool|)]（保序删除）
#     逐房数字已 4/4 闭环；4 位密码拼接序（区域分组 2+2）未闭环，只出逐房数字。
PF_VALVE_SECTIONS = ['A', 'B', 'C', 'D', 'E']  # 1P/2P 只启用 A–D
PF_LOTS = {
    'F': {'loc': 'Basement', 'valves': ['ValveSystem_BP17_2']},
    'L1': {'loc': 'Basement',
           'valves': ['ValveSystem_BP9', 'ValveSystem_BP11',
                      'ValveSystem_BP7', 'ValveSystem_BP6']},
    'L2': {'loc': 'Basement',
           'valves': ['ValveSystem_BP4', 'ValveSystem_BP3',
                      'ValveSystem_BP8']},
    'L3': {'loc': 'Laundry 1F',
           'valves': ['ValveSystem_BP24', 'ValveSystem_BP22']},
    'L4': {'loc': 'BlockA 1F',
           'valves': ['ValveSystem_BP2', 'ValveSystem_BP_2',
                      'ValveSystem_BP12', 'ValveSystem_BP10']},
}
PF_LOT_POOL = ['L1', 'L4', 'L2', 'L3']   # 固定位删除后的有效池（701701 唯一反解）
PF_VALVE_COORD = 'PF_B04_ObjCoord_ValveSystemMaze'
PF_FORCE_INPUT = 2      # ValveSystemMaze_Coord_BP CDO：ForceInputIndex=2
PF_LOT_DRAW = 234659    # 0x394A3 抽 lot
PF_VALVE_DRAW = 4324    # 0x10E4 lot 内抽阀门
PF_DIR_DRAW = 387       # 0x183 方向（[0,1,2,3]去 input 后 3 选 1）
PF_VALVE_COORDS = {
    'ValveSystem_BP2': (-3263.0, -1405.0, 0.0),
    'ValveSystem_BP3': (-1066.0, 4119.0, -550.0),
    'ValveSystem_BP4': (-95.0, 3497.0, -550.0),
    'ValveSystem_BP6': (39.62335, 1998.0, -699.9374),
    'ValveSystem_BP7': (1053.0, 1447.0, -699.9374),
    'ValveSystem_BP8': (-1735.0, 3378.0, -550.0),
    'ValveSystem_BP9': (706.0, 755.0, -549.7999),
    'ValveSystem_BP10': (-3825.0, 1850.3577, 0.0),
    'ValveSystem_BP11': (382.0, 635.0, -699.9999),
    'ValveSystem_BP12': (-4245.0, 1030.0, 0.0),
    'ValveSystem_BP22': (-2698.0, 729.0, 0.125099),
    'ValveSystem_BP24': (-1222.0, 942.0, 0.125099),
    'ValveSystem_BP_2': (-4625.0, 40.0, 0.0),
    'ValveSystem_BP17_2': (-98.38454, 1698.0004, -550.0),
}
# 密码房：PF_B05_ObjCoord_MultiroomPuzzle 的 Sections（JSON 序），每区抽 1 间
PF_CELL_SECTIONS = [
    ['RBRoom_BlockA_Cell_103', 'RBRoom_BlockA_Cell_102',
     'RBRoom_BlockA_Cell_104', 'RBRoom_BlockA_Cell_105'],
    ['RBRoom_BlockA_Cell_106', 'RBRoom_BlockA_Cell_107'],
    ['RBRoom_BlockB_Cell_101', 'RBRoom_BlockB_Cell_102', 'RBRoom_BlockB_Cell_103',
     'RBRoom_BlockB_Cell_104', 'RBRoom_BlockB_Cell_105', 'RBRoom_BlockB_Cell_109',
     'RBRoom_BlockB_Cell_110'],
    ['RBRoom_BlockB_Cell_107', 'RBRoom_BlockB_Cell_108'],
]
PF_PICK_OFFSET = 28042   # sub_14374E420 抽房（同 SR）
PF_DIGIT_OFFSET = 7168   # sub_143620E70 写数字（同 SR）

# 实测样本（release/coop/PF_Trial/test.txt，Easy 1P）：
#   阀门 A1-B1-C1-D2（A 固定 BP17_2；B=BP11 C=BP8 D=BP22）
#   密码房 A103=0 A106=8 B105=2 B108=3（记录括号 = 位次 k）
PF_SAMPLES = {
    701701: {
        'valves': {'A': ('ValveSystem_BP17_2', 1), 'B': ('ValveSystem_BP11', 1),
                   'C': ('ValveSystem_BP8', 1), 'D': ('ValveSystem_BP22', 2)},
        'cells': {'A103': 0, 'A106': 8, 'B105': 2, 'B108': 3},
    },
}


def _pf_cell_label(room):
    return room.replace('RBRoom_BlockA_Cell_', 'A').replace('RBRoom_BlockB_Cell_', 'B')


def _predict_pf_trial(level_seed, players=1, trace=False):
    """PF_Trial：拧阀门（点位+拧格数）+ 密码房逐位数字。"""
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')
    salt = level_seed
    # ---------- (1) 拧阀门（sub_1437DE200）----------
    cs = sc.seed_chain(['PersistentLevel', PF_VALVE_COORD])
    active = PF_VALVE_SECTIONS[:4] + (['E'] if players >= 3 else [])
    pool = list(PF_LOT_POOL)
    slot_lot = {0: 'F'}                     # FixedOrder=0 固定位 -> 槽 0（A）
    for s in range(1, len(active)):
        idx = sc.rand_seeded(cs + PF_LOT_DRAW + s, len(pool), salt)
        lot = pool[idx]
        pool[idx] = pool[-1]                # RemoveAtSwap
        pool.pop()
        slot_lot[s] = lot
    valves = []
    for s, sec in enumerate(active):
        lot = PF_LOTS[slot_lot[s]]
        cands = lot['valves']
        vi = sc.rand_seeded(cs + PF_VALVE_DRAW + s, len(cands), salt)
        actor = cands[vi]
        output = [0, 1, 3][sc.rand_seeded(cs + PF_DIR_DRAW + s, 3, salt)]
        turns = (output - PF_FORCE_INPUT) % 4
        valves.append({
            'section': sec, 'lot': slot_lot[s], 'location': lot['loc'],
            'actor': actor, 'candidate_index': vi,
            'input': PF_FORCE_INPUT, 'output': output, 'turns': turns,
            'answer': '%s%d' % (sec, turns),
            'coordinates': PF_VALVE_COORDS[actor], 'coordinate_type': 'actor',
        })
        if trace:
            print('    PF 阀门 %s slot=%d lot=%s idx=%d -> %s in=%d out=%d -> %s'
                  % (sec, s, slot_lot[s], vi, actor,
                     PF_FORCE_INPUT, output, valves[-1]['answer']))
    # ---------- (2) 密码房（sub_14374E420 / sub_143620E70）----------
    pools = {i: list(p) for i, p in enumerate(PF_CELL_SECTIONS)}
    picked, remaining = [], 4
    for sid in range(len(PF_CELL_SECTIONS)):
        if remaining <= 0:
            break
        p = pools[sid]
        idx = sc.rand_seeded(remaining + PF_PICK_OFFSET, len(p), salt)
        room = p.pop(idx)                   # 保序删除
        picked.append(room)
        if trace:
            print('    PF 抽房 section=%d 剩余=%d idx=%d/%d -> %s'
                  % (sid, remaining, idx, len(p) + 1, _pf_cell_label(room)))
        remaining -= 1
    # 位次 k = 单比特洗牌逆序（同 SR_Trial）
    frac = {r: sc.rand_fraction(sc.room_component_seed(r), salt) for r in picked}
    arr = list(picked)
    end = len(arr) - 1
    while end > 0:
        best = 0
        for j in range(1, end + 1):
            if frac[arr[j]] < 0.5:
                best = j
        if best != end:
            arr[best], arr[end] = arr[end], arr[best]
        end -= 1
    order = arr[::-1]
    pool10 = list(range(10))
    slots = []
    for k, room in enumerate(order):
        comp = sc.room_component_seed(room)
        idx = sc.rand_seeded((comp + k + PF_DIGIT_OFFSET) & sc.M32,
                             len(pool10), salt)
        digit = pool10.pop(idx)             # 保序删除
        slots.append({'id': room, 'room': room, 'label': _pf_cell_label(room),
                      'area': 'BlockA' if '_BlockA_' in room else 'BlockB',
                      'digit': digit, 'position': k + 1})
        if trace:
            print('    PF k=%d %-6s comp=%-10d pool=%2d idx=%d -> %d'
                  % (k, _pf_cell_label(room), comp, len(pool10) + 1, idx, digit))
    notes = ['密码房逐位数字已闭环；4 位密码的拼接序（按区域 2+2）未闭环，'
             '只输出逐房数字。']
    if players >= 3:
        notes.append('3P+ 局启用 E 区为模型外推（2P 覆写语义），未实测。')
    return {'valves': valves, 'slots': slots, 'notes': notes}


# ---------------------------------------------------------------------------
# CHJ_MT03 图案立牌（REA/IDA 反编译链，4/4 实测样本）
#   sub_143585720：ci=RandSeeded(GS+k+41,|池|) 图案 / ai=RandSeeded(GS+k+341,|A|)
#   席位，均尾元素换删；A = 亮起的 5 席按名升序。教学走 sub_140A1EED0 强制位
#   （GS_tut+41）。详见 release/coop/CHJ_MT03/CHJ_MT03.md。
# ---------------------------------------------------------------------------
CHJ_MT03_COORD = 'CHJ_MT03_RemainingBribes'
CHJ_MT03_TUT_COORD = 'CHJ_MT03_FirstBribe'
CHJ_MT03_CLUES = ['Bunny', 'Club', 'Crown', 'Diamond', 'Fire', 'Spade']
CHJ_MT03_CLUES_TUT = ['Moon', 'Eye', 'Heart']
CHJ_MT03_ZH = {'Bunny': '兔子', 'Club': '梅花', 'Crown': '王冠', 'Diamond': '方块',
               'Fire': '火焰', 'Spade': '黑桃', 'Moon': '月亮', 'Eye': '眼睛',
               'Heart': '红心'}
CHJ_MT03_TUTORIAL = ('BP_4', 'TextSignStandBase-01_16',
                     'RBRoom_Courtyard_Groundfloor', (-1868.19, 4927.84, 349.12))
CHJ_MT03_POINTS = [
    ('BP_1', 'TextSignStandBase-4', 'RBRoom_West_Blueprints',
     (-4551.65, 7728.53, 749.81)),
    ('BP_2', 'TextSignStandBase-5', 'RBRoom_BackEntrance_Records',
     (-2675.49, 7305.67, 749.81)),
    ('BP_3', 'TextSignStandBase-2', 'RBRoom_West_ConstructionGore',
     (-3101.95, 2921.42, 749.15)),
    ('BP_5', 'TextSignStandBase-9', 'RBRoom_East_Museum',
     (-408.98, 5833.95, 748.99)),
    ('BP_6', 'TextSignStandBase-7', 'RBRoom_East_Courtroom_2',
     (991.19, 3833.25, 799.57)),
    ('BP_7', 'TextSignStandBase-3', 'RBRoom_West_PrivateOffice',
     (-4001.40, 4193.41, 749.15)),
    ('BP_8', 'TextSignStandBase-6', 'RBRoom_East_JudgesOffice',
     (968.68, 8079.62, 749.81)),
    ('BP_9', 'TextSignStandBase-8', 'RBRoom_East_Courtroom_1',
     (-694.54, 2423.04, 769.25)),
]
CHJ_MT03_BY_ZONE = {row[0]: row for row in CHJ_MT03_POINTS}
CHJ_MT03_BY_STAND = {row[1]: row[0] for row in CHJ_MT03_POINTS}
# 8 选 5：idx=RandSeeded(crc32_fname('Objective Actors')+GetSeed+70251+k, |池|)，
# 尾元素换删（4 样本席位集 4/4，其中 184184/327327 为样本外验证；详见 CHJ_MT03.md §3.2）
CHJ_MT03_SEAT_OFF = 70251
# 实测样本（opp_seed/test.txt；327327 的 -8=方块 系 -5=方块 笔误，CHJ_MT03.md §4 勘误）
CHJ_MT03_SAMPLES = {
    556556: {'tutorial': 'Heart',
             'mapping': {'BP_7': 'Club', 'BP_2': 'Spade', 'BP_9': 'Fire',
                         'BP_6': 'Crown', 'BP_8': 'Bunny'}},
    892892: {'tutorial': None,
             'mapping': {'BP_1': 'Club', 'BP_8': 'Fire', 'BP_5': 'Crown',
                         'BP_9': 'Spade', 'BP_7': 'Diamond'}},
    184184: {'tutorial': 'Eye',
             'mapping': {'BP_1': 'Club', 'BP_5': 'Bunny', 'BP_3': 'Fire',
                         'BP_9': 'Spade', 'BP_6': 'Diamond'}},
    327327: {'tutorial': 'Heart',
             'mapping': {'BP_1': 'Fire', 'BP_2': 'Diamond', 'BP_5': 'Crown',
                         'BP_6': 'Spade', 'BP_8': 'Bunny'}},
}


def _chj_mt03_gs():
    outer = sc.crc32_fname('PersistentLevel')
    return (sc.seed_of_object(CHJ_MT03_COORD, outer),
            sc.seed_of_object(CHJ_MT03_TUT_COORD, outer))


def _chj_mt03_draw(pool, base, count, level_seed):
    """sub_143585720 的抽取：idx=RandSeeded(base+k,|池|)，尾元素换删。"""
    pool = list(pool)
    out = []
    for k in range(count):
        if not pool:
            break
        idx = sc.rand_seeded((base + k) & sc.M32, len(pool), level_seed)
        out.append(pool[idx])
        pool[idx] = pool[-1]
        pool.pop()
    return out, pool


def _chj_mt03_seats(level_seed):
    """8 选 5：seed 直接推出本局亮起的 5 个席位（抽取序）。"""
    gs_main, _ = _chj_mt03_gs()
    base = (sc.crc32_fname('Objective Actors') + gs_main
            + CHJ_MT03_SEAT_OFF) & sc.M32
    picked, _ = _chj_mt03_draw([r[0] for r in CHJ_MT03_POINTS], base, 5,
                              level_seed)
    return picked


def _predict_chj_mt03(level_seed, seats=None):
    gs_main, gs_tut = _chj_mt03_gs()
    tut = CHJ_MT03_CLUES_TUT[sc.rand_seeded((gs_tut + 41) & sc.M32, 3, level_seed)]
    seq, rest = _chj_mt03_draw(CHJ_MT03_CLUES, gs_main + 41, 5, level_seed)
    missing = rest[0] if rest else None

    if seats is None:
        seats = _chj_mt03_seats(level_seed)
        source = 'seed 推算'
    else:
        source = '--seats'
    norm = []
    for s in seats or []:
        z = s if s in CHJ_MT03_BY_ZONE else CHJ_MT03_BY_STAND.get(s)
        if z is None:
            raise ModelUnresolved('未知席位：%s（BP_x 或立牌名）' % s)
        if z not in norm:
            norm.append(z)

    rows = []
    tz, tstand, troom, txyz = CHJ_MT03_TUTORIAL
    rows.append({'pattern': tut, 'pattern_zh': CHJ_MT03_ZH[tut], 'role': '教学',
                 'zone': tz, 'stand': tstand, 'room': troom,
                 'coordinates': [round(c, 2) for c in txyz]})
    role = {}
    for c in seq[:3]:
        role[c] = '钱箱'
    for c in seq[3:]:
        role[c] = '干扰项'
    if norm:
        pool = sorted(norm, key=lambda z: [r[0] for r in CHJ_MT03_POINTS].index(z))
        picked, _ = _chj_mt03_draw(pool, gs_main + 341, 5, level_seed)
        for k, z in enumerate(picked):
            _, stand, room, xyz = CHJ_MT03_BY_ZONE[z]
            rows.append({'pattern': seq[k], 'pattern_zh': CHJ_MT03_ZH[seq[k]],
                         'role': role.get(seq[k], ''), 'zone': z, 'stand': stand,
                         'room': room, 'coordinates': [round(c, 2) for c in xyz]})
    else:
        for c in seq:
            rows.append({'pattern': c, 'pattern_zh': CHJ_MT03_ZH[c],
                         'role': role.get(c, ''), 'zone': None, 'stand': None,
                         'room': '（席位待定）', 'coordinates': None})
    return {'signboards': rows, 'missing': missing,
            'missing_zh': CHJ_MT03_ZH[missing],
            'clue_order': seq, 'seats_source': source}


def predict(level_id, seed, players=1, difficulty='easy', max_fake=None,
            digits=4, trace=False, tuto=False, seats=None):
    key = resolve(level_id)
    cfg = LEVELS[key]
    result = {'level': key, 'name': cfg['name'], 'map': cfg['map'],
              'seed': seed, 'salt': seed % 1000,
              'players': players, 'difficulty': difficulty}

    if cfg.get('signboards'):
        result.update(_predict_chj_mt03(seed, seats=seats))
        return result

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

    if cfg.get('freqclue'):
        result.update(_predict_srr_mt02(seed, trace=trace))
        return result

    if cfg.get('srtrial'):
        result.update(_predict_sr_trial(seed, trace=trace))
        return result

    if cfg.get('pftrial'):
        result.update(_predict_pf_trial(seed, players=players, trace=trace))
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
        projections, notes = _predict_chj_mt02(seed, trace=trace)
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

    if cfg.get('movingtargets'):
        result.update(_predict_fpb_mt03(seed, trace=trace))
        return result

    if cfg.get('ticketbooth'):
        result.update(_predict_fpc_mt02(seed, trace=trace))
        return result

    if cfg.get('switchboard'):
        result.update(_predict_tsr_mt01(seed, trace=trace))
        return result

    if cfg.get('converters'):
        result.update(_predict_tsr_mt02(seed, players=players,
                                        difficulty=difficulty, trace=trace))
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
           'difficulty': result.get('difficulty', 'easy'),
           'answer': None, 'points': []}
    points = out['points']

    if 'jewels' in result:                                  # RES_MT02
        for item in result['jewels']:
            points.append(_point(item['room'], item['gem_cn'], item['spawner'],
                                 _actor_coords(item)))

    elif 'converters' in result:                            # TSR_MT02
        # predict 已只给可用点位；这里按抽取顺序原样铺成 point
        shorts = []
        for row in result['converters']:
            label = '刻录机（固定）' if row['fixed'] else '刻录机'
            points.append(_point(row['short'], label, row['actor'],
                                 row['coordinates'], active=True,
                                 state=row['state'], fixed=row['fixed'],
                                 order=row['order'], lot=row['lot']))
            shorts.append(row['short'])
        out['answer'] = '可用刻录机：%s' % ' '.join(shorts)
        out['active'] = shorts
        out['lots'] = [{'name': i['name'], 'K': i['K'],
                        'selected': i['selected'],
                        'min_distance': i['min_distance']}
                       for i in result['lots']]

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
        # 每个房间一条点位：第几阶段 / 目标图案 / 答案与数字串 / 假板数 / 坐标
        # 房间与图案都用游戏里的英文标注（墙上/翻板上写的就是这些），方便对着找
        def add_room(stage, r):
            digits = '+'.join(str(d) for d in (r.get('digits') or []))
            label = '第%d阶段 · %s' % (stage, r['symbol'])
            detail = '答案 %s' % r['answer']
            if digits:
                detail += '（%s）' % digits
            if r.get('fakes'):
                detail += ' · 假板%d / 真板%d' % (r['fakes'], r.get('true_boards') or 0)
            points.append(_point(r['room'], label, None, r.get('coordinates'),
                                 answer=r['answer'], detail=detail, stage=stage,
                                 room_name=r.get('room_name'),
                                 symbol=r['symbol'], symbol_zh=r.get('symbol_zh'),
                                 digits=r.get('digits'), fakes=r.get('fakes')))

        for r in result.get('tutorial') or []:
            add_room(1, r)
        for rd in result['rounds']:
            for r in rd['rooms']:
                add_room(rd.get('stage') or (rd['round'] + 2), r)
        out['rounds'] = [{'stage': rd.get('stage'), 'rooms': rd['rooms']}
                         for rd in result['rounds']]
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
        # 每个图案一个点位（actor 房间 + 精确坐标）并附密码
        for item in result['projections']:
            label = item['symbol_name']
            if item.get('tutorial'):
                label += '（教学）'
            points.append(_point(item['room'], label, item['actor'],
                                 _actor_coords(item), answer=item['code']))
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

    elif 'valves' in result and 'slots' in result:          # PF_Trial 两阶段
        for item in result['valves']:
            points.append(_point(item['actor'], item['answer'], item['actor'],
                                 _actor_coords(item),
                                 detail='拧%d格' % item['turns']))
        for slot in result['slots']:
            point = _point(slot['room'], slot['label'], slot['id'])
            point['answer'] = slot['digit']
            points.append(point)
        out['answer'] = ('阀门 %s；密码房 %s' % (
            '-'.join(v['answer'] for v in result['valves']),
            ' '.join('%s=%d' % (x['label'], x['digit'])
                     for x in result['slots'])))

    elif 'valves' in result:                                # TFS_MT03
        for item in sorted(result['valves'], key=lambda x: x['section']):
            points.append(_point(item['room'], item['section'], item['actor'],
                                 _actor_coords(item)))

    elif 'moving_targets' in result:                        # FPB_MT03：仅区域1/3
        for area in result['moving_targets']:
            for item in area['targets']:
                points.append(_point(
                    item['name'], area['zone'], item['name'], item['coordinates'],
                    zone=area['zone'], short=item['short'],
                    track=item['track'], phase=item['phase']))

    elif 'ticket_points' in result:                         # FPC_MT02
        for item in result['ticket_points']:
            points.append(_point(item['name'], '出票机', item['name'],
                                 item['coordinates']))
        if result.get('notes'):
            out['note'] = result['notes'][0]

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

    elif 'tuner_rounds' in result:                          # SRR_MT02
        # 每台调频器一个点位：显示台按上屏顺序在前，陷阱台随后
        summary = []
        answers = []
        for rd in result['tuner_rounds']:
            rows = []
            for tuner in rd['tuners']:
                role = ('显示%d' % (tuner['order'] + 1)
                        if tuner['order'] >= 0 else '陷阱')
                points.append(_point(
                    tuner['room'],
                    '第%d轮 %s %s' % (rd['round'], role, tuner['pattern_zh']),
                    tuner['id'], tuner.get('coordinates'),
                    pattern=tuner['pattern'], round=rd['round']))
                if tuner['order'] >= 0:
                    rows.append('%s=%s' % (tuner['pattern_zh'], tuner['id']))
            summary.append('%d:%s' % (rd['round'], '-'.join(rd['display_zh'])))
            answers.append([rd['round'], rows])
        out['answer'] = '  '.join(summary)
        out['rounds'] = [{'round': num, 'answers': rows}
                         for num, rows in answers]

    elif 'slots' in result:                                 # SR_Trial 第 2 阶段
        # 只输出：4 间密码房点位（房间 + 数字）+ 最终密码
        for slot in result['slots']:
            point = _point(slot['room'], slot['label'], slot['id'])
            point['answer'] = slot['digit']
            points.append(point)
        out['answer'] = result['password']

    elif 'signboards' in result:                            # CHJ_MT03
        # 每个图案一个点位：图案（角色）+ 立牌 + 房间 + 坐标
        for item in result['signboards']:
            label = item['pattern_zh']
            if item.get('role'):
                label += '（%s）' % item['role']
            points.append(_point(item['room'], label, item['stand'],
                                 item['coordinates'], pattern=item['pattern'],
                                 role=item.get('role'), zone=item.get('zone'),
                                 detail=item['stand']))
        if result.get('seats_source'):
            out['answer'] = ' '.join('%s=%s' % (s['pattern_zh'], s['zone'])
                                     for s in result['signboards']
                                     if s.get('zone'))
            out['note'] = '缺 %s；8 选 5 席位集来源：%s' % (
                result['missing_zh'], result['seats_source'])
        else:
            brief = '/'.join(s['pattern_zh'] for s in result['signboards']
                             if s.get('role') == '钱箱')
            decoy = '/'.join(s['pattern_zh'] for s in result['signboards']
                             if s.get('role') == '干扰项')
            out['answer'] = '%s（教学）  钱箱=%s  干扰项=%s  缺=%s' % (
                result['signboards'][0]['pattern_zh'], brief, decoy,
                result['missing_zh'])
            out['note'] = (result.get('notes') or ['缺 %s' % result['missing_zh']])[0]

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
    if v.get('level') == 'FPB_MT03':                  # 只输出区域1/3 的点位
        lines = ['FPB_MT03  seed=%d' % v['seed']]
        cur = None
        for p in v.get('points') or []:
            if p.get('zone') != cur:
                cur = p['zone']
                lines.append(cur)
            c = p['coordinates']
            lines.append('  %-5s (%g, %g, %g)' %
                         (p.get('short') or p.get('label') or '', *c))
        return '\n'.join(lines)
    if v.get('level') == 'TSR_MT02':              # 只输出本局可用的刻录机点位
        lines = ['TSR_MT02  seed=%d  %dP  %s  salt=%d'
                 % (v['seed'], v.get('players', 1), v.get('difficulty', 'easy'),
                    v['seed'] % 1000)]
        if v.get('answer'):
            lines.append('  %s' % v['answer'])
        for lot in v.get('lots') or []:
            lines.append('  [%s] K=%d 实选=%d 距离阈值=%g'
                         % (lot['name'], lot['K'], lot['selected'],
                            lot['min_distance']))
        lines.append('  %-16s %-26s %-6s %s'
                     % ('刻录机(*=固定)', '坐标 (x, y, z)', '批次', '顺序'))
        for p in v.get('points') or []:
            c = p['coordinates']
            name = p['room'] + ('*' if p.get('fixed') else '')
            lines.append('  %-16s (%8g, %8g, %6g)   %-6s %s'
                         % (name, c[0], c[1], c[2],
                            p.get('lot') or '-',
                            ('第%d抽' % p['order']) if p.get('order') else '-'))
        return '\n'.join(lines)
    lines = ['%s  %s  (%s)  seed=%d  %dP'
             % (v['level'], v['name'], v['map'], v['seed'],
                v.get('players', 1))]
    if v.get('answer'):
        lines.append('  答案：%s' % v['answer'])
    if v.get('note'):
        lines.append('  ! %s' % v['note'])
    for index, point in enumerate(v.get('points') or [], 1):
        tail = ''
        if point.get('detail'):
            tail = '  %s' % point['detail']
        elif point.get('answer') is not None:
            tail = '  密码 %s' % point['answer']
        if point.get('reel') is not None:
            tail = '  盘%d' % point['reel']
        if point.get('coordinates'):
            tail += '  (%s)' % ', '.join('%g' % c for c in point['coordinates'])
        room = point.get('room_name') or point['room']
        lines.append('  %2d. %-8s %s%s'
                     % (index, point.get('label') or '', room, tail))
    for rd in v.get('rounds') or []:
        if not rd.get('answers'):
            continue
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
        rows = {r['symbol']: r for r in predict('CHJ_MT02', seed)['projections']}
        for symbol, code in expect.items():
            total += 1
            ok = rows.get(symbol, {}).get('code') == code
            bad += 0 if ok else 1
            if verbose:
                print('  CHJ2 %-7d %-16s 预测=%s 实测=%s %s'
                      % (seed, symbol, rows.get(symbol, {}).get('code', '---'),
                         code, 'OK' if ok else 'MISMATCH'))
        for symbol, actor in CHJ_MT02_ACTORS.get(seed, {}).items():
            total += 1
            got_actor = rows.get(symbol, {}).get('actor', '')
            ok = got_actor == actor
            bad += 0 if ok else 1
            if verbose:
                print('  CHJ2 %-7d %-16s 预测=%s 实测=%s %s'
                      % (seed, symbol + '.actor', got_actor or '---', actor,
                         'OK' if ok else 'MISMATCH'))
    for seed, expect in CHJ_MT02_SAMPLES_EXTRA.items():
        rows = {r['symbol']: r for r in predict('CHJ_MT02', seed)['projections']}
        for symbol, (actor, code) in expect.items():
            total += 1
            ok = rows.get(symbol, {}).get('code') == code
            bad += 0 if ok else 1
            if verbose:
                print('  CHJ2 %-7d %-16s 预测=%s 实测=%s %s'
                      % (seed, symbol, rows.get(symbol, {}).get('code', '---'),
                         code, 'OK' if ok else 'MISMATCH'))
            if actor is not None:
                total += 1
                got_actor = rows.get(symbol, {}).get('actor', '')
                ok = got_actor.split('_BP_')[-1] == actor
                bad += 0 if ok else 1
                if verbose:
                    print('  CHJ2 %-7d %-16s 预测=%s 实测=%s %s'
                          % (seed, symbol + '.actor', got_actor or '---',
                             actor, 'OK' if ok else 'MISMATCH'))
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
    # SR_Trial 第 2 阶段：4 间密码房 + 4 位密码
    for seed, sample in SR_SAMPLES.items():
        res = predict('SR_Trial', seed)
        got = {s['id']: (s['digit'], s['position']) for s in res['slots']}
        total += 1
        ok = res['password'] == sample['password'] and got == sample['rooms']
        bad += 0 if ok else 1
        if verbose:
            print('  SRT %-7d 密码=%s 期望=%s 逐房数字%s %s'
                  % (seed, res['password'], sample['password'],
                     'OK' if got == sample['rooms'] else 'MISMATCH: %s' % got,
                     'OK' if ok else 'MISMATCH'))
    # PF_Trial：拧阀门（点位+拧格数）+ 密码房逐位数字
    for seed, sample in PF_SAMPLES.items():
        res = predict('PF_Trial', seed)
        got_v = {v['section']: (v['actor'], v['turns']) for v in res['valves']}
        got_c = {x['label']: x['digit'] for x in res['slots']}
        total += 1
        ok = got_v == sample['valves'] and got_c == sample['cells']
        bad += 0 if ok else 1
        if verbose:
            print('  PFT %-7d 阀门=%s 密码房=%s %s'
                  % (seed, got_v, got_c, 'OK' if ok else 'MISMATCH'))
    # SRR_MT02：三轮调频器↔图案绑定（纯 seed，含选中集）
    for seed, expect in SAMPLES_SRR_MT02:
        result = predict('SRR_MT02', seed)
        for rd in result['tuner_rounds']:
            got = {t['id']: t['pattern'] for t in rd['tuners']}
            want = expect[rd['key']]
            total += 1
            ok = got == want
            bad += 0 if ok else 1
            if verbose:
                print('  SRR2 %-7d %-8s 预测=%s 实测=%s %s'
                      % (seed, rd['key'], got, want, 'OK' if ok else 'MISMATCH'))
    # FPB_MT03：区域1/3 移动靶集合（两 seed 4/4；区域2/4 未闭环不计）
    for seed, expect in FPB_MT03_SAMPLES.items():
        got = {a['coord']: {t['name'] for t in a['targets']}
               for a in predict('FPB_MT03', seed)['moving_targets']}
        for coord in FPB_MT03_AREAS:
            total += 1
            ok = got[coord] == expect[coord]
            bad += 0 if ok else 1
            if verbose:
                show = lambda s: ','.join(sorted(
                    (n.split('Gate-')[-1] for n in s), key=int))
                print('  FPB %-7d %-22s 预测=%-16s 实测=%-16s %s'
                      % (seed, coord, show(got[coord]), show(expect[coord]),
                         'OK' if ok else 'MISMATCH'))
    # FPC_MT02：Canals 区 5 个出票机（710710 5/5；Office 区未闭环不计）
    for seed, expect in FPC_MT02_SAMPLES.items():
        got = {p['name'] for p in predict('FPC_MT02', seed)['ticket_points']}
        total += 1
        ok = got == expect
        bad += 0 if ok else 1
        if verbose:
            show = lambda s: ','.join(sorted(n.rsplit('_', 1)[-1] for n in s))
            print('  FPC %-7d 预测=%-22s 实测=%-22s %s'
                  % (seed, show(got), show(expect), 'OK' if ok else 'MISMATCH'))
    # CHJ_MT03：图案→立牌点位（4 样本含 R6 修正后的 327327）
    for seed, expect in CHJ_MT03_SAMPLES.items():
        res = predict('CHJ_MT03', seed)
        got = {s['zone']: s['pattern'] for s in res['signboards']
               if s['zone'] != 'BP_4'}
        tut = res['signboards'][0]['pattern']
        total += 2
        ok_map = got == expect['mapping']
        ok_tut = expect['tutorial'] is None or tut == expect['tutorial']
        bad += 0 if ok_map else 1
        bad += 0 if ok_tut else 1
        if verbose:
            print('  CHJ3 %-7d 点位 %s / 教学=%s %s'
                  % (seed, 'OK' if ok_map else 'MISMATCH:%s' % got, tut,
                     'OK' if ok_tut else 'MISMATCH'))
    # TSR_MT02：predict 只返回可用点位；实测只记了一部分机器，所以同时核对
    # 「正向完整集」与「observed ⊆ 正向完整集」。
    for seed, players, difficulty, observed, expected in SAMPLES_TSR_MT02:
        res = predict('TSR_MT02', seed, players, difficulty)
        got = {c['actor'] for c in res['converters'] if c['active']}
        fixed = TSR_MT02_FIXED in got
        shown = view(res)['points']
        # predict 与 view 都不得夹带不可用点位
        ok_clean = (len(res['converters']) == len(got)
                    and all(c['active'] for c in res['converters'])
                    and len(shown) == len(got)
                    and all(p.get('active') for p in shown))
        ok_full = got == expected and ok_clean
        ok_obs = observed.issubset(got)
        total += 3
        bad += (0 if ok_full else 1) + (0 if ok_obs else 1) + (0 if fixed else 1)
        if verbose:
            print('  TSR2 %-7d 可用集+视图 %s / 记录覆盖 %s / BP_2 固定 %s'
                  % (seed, 'OK' if ok_full else 'MISMATCH:%d台' % len(got),
                     'OK' if ok_obs else 'MISMATCH',
                     'OK' if fixed else 'MISMATCH'))
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
    ap.add_argument('--seats', metavar='LIST',
                    help='CHJ_MT03：本局亮起的 5 个席位（BP_x 或立牌名，逗号分隔）')
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
                  or cfg.get('puzzle') or cfg.get('srtrial')
                  or cfg.get('freqclue') or cfg.get('movingtargets')
                  or cfg.get('ticketbooth') or cfg.get('signboards')
                  or cfg.get('converters'))
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
        seats = ([x.strip() for x in args.seats.split(',') if x.strip()]
                 if args.seats else None)
        result = predict(args.level, args.seed, args.players, args.difficulty,
                         args.max_fake, args.digits, args.trace, args.tuto,
                         seats=seats)
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
