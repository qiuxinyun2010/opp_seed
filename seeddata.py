# -*- coding: utf-8 -*-
"""静态数据载入层：release/seed/data/*.json → 与原先写在 seed.py 里同名的常量。

数据口径（只放「大体量 + 可由 paks 重新生成」的表）：
    data/<关卡>.json        该关卡的候选池 / 名称映射 / 坐标
    data/room_centers.json  各 map 的房间中心参考点
    data/samples.json       --selftest 的实测样本

刻意留在代码里的东西（不是漏搬）：
    LEVELS / ALIASES        关卡注册表，里面的值引用了 seedcore/gameshow 的 Python 常量
    各种 salt、名字链、tag/offset、bucket 语义开关   与算法强耦合，挤到 JSON 里反而要
                            用 sd.tsr['split_rooms'][i] 这种下标读，可读性更差
    各关卡算法注释          逆向结论写在 predict_* 函数旁边才能就地看懂

JSON 里的数组在这里会被还原成原来的类型（tuple / int 键），所以 seed.py 的下游代码
不需要改动。
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

_cache = {}


class SeedDataError(RuntimeError):
    """数据文件缺失或字段不全。比裸 KeyError 更容易定位是哪个 JSON 少了什么。"""


def load(name):
    """载入 data/<name>.json（同一文件只读一次）。"""
    if name not in _cache:
        path = os.path.join(DATA_DIR, name + '.json')
        if not os.path.isfile(path):
            raise SeedDataError('缺少数据文件：%s' % path)
        with open(path, 'r', encoding='utf-8') as fp:
            try:
                _cache[name] = json.load(fp)
            except ValueError as exc:
                raise SeedDataError('数据文件不是合法 JSON：%s（%s）' % (path, exc))
    return _cache[name]


def _get(data, key, filename):
    if key not in data:
        raise SeedDataError('data/%s.json 缺少字段 %r' % (filename, key))
    return data[key]


def _check_len(values, key, expect, filename):
    got = len(values)
    if got != expect:
        raise SeedDataError('data/%s.json 的 %r 长度 %d 与候选桶数 %d 不一致'
                            % (filename, key, got, expect))


# ---------------------------------------------------------------------------
# 房间中心参考点（按 map 分组）
# ---------------------------------------------------------------------------
ROOM_CENTERS = load('room_centers')

# ---------------------------------------------------------------------------
# CHJ_MT02：法院 · 判决被起诉者
# ---------------------------------------------------------------------------
_chj2 = load('chj_mt02')
CHJ_MT02_COORDS = [
    (item['actor'], list(item['groups']), item['tutorial'])
    for item in _get(_chj2, 'coordinates', 'chj_mt02')
]
CHJ_MT02_ACTORS = {int(seed): actors
                   for seed, actors in _get(_chj2, 'actors', 'chj_mt02').items()}
CHJ_MT02_ROOMS_20020 = _get(_chj2, 'rooms_20020', 'chj_mt02')
CHJ_MT02_SYMBOL_NAMES = _get(_chj2, 'symbol_names', 'chj_mt02')
# 43 个投影图案机位的 actor 坐标 / 所在房间（由 ui/data/maps/CHJ_MT02.json 导出）
CHJ_MT02_SYMBOL_COORDS = _get(_chj2, 'symbol_coordinates', 'chj_mt02')
CHJ_MT02_SYMBOL_ROOMS = _get(_chj2, 'symbol_rooms', 'chj_mt02')

# ---------------------------------------------------------------------------
# MHS_MT01：黑帮据点 · 找到 3 个投影房间
# ---------------------------------------------------------------------------
_mhs = load('mhs_mt01')
MHS_SYMBOL_NAMES = _get(_mhs, 'symbol_names', 'mhs_mt01')
# (区, 协调器, 图案家族, 每房间至多一个目标)：字符串=只有一组（固定），
# 数组=PossibleClueGroups 顺序即抽取顺序；末位来自
# CodeProjectorsRandomizationSetup.bLimitOneObjectivePerRoom
MHS_ZONES = [(zone['zone'], zone['coordinator'], zone['clue_groups'],
              zone.get('limit_one_per_room', False))
             for zone in _get(_mhs, 'zones', 'mhs_mt01')]
MHS_ZONE_BY_KEY = {zone[0]: zone for zone in MHS_ZONES}
# (候选序号, 图案贴图, 主房间, RootComponent 坐标, [落在哪些房间 hull 里])
# 顺序 = 关卡 actor 顺序（全名字典序 _1,_10,_2…_9），**就是抽取池顺序**
MHS_SYMBOLS = _get(_mhs, 'symbols', 'mhs_mt01')

# ---------------------------------------------------------------------------
# TSR_MT01：电视台屋顶 · 密码接线面板
# ---------------------------------------------------------------------------
_tsr = load('tsr_mt01')
TSR_BUCKETS = _get(_tsr, 'buckets', 'tsr_mt01')
TSR_BUCKET_NAMES = _get(_tsr, 'bucket_names', 'tsr_mt01')
TSR_MANDATORY_ROOM = _get(_tsr, 'mandatory_room', 'tsr_mt01')
TSR_SPLIT_ROOMS = _get(_tsr, 'split_rooms', 'tsr_mt01')
_check_len(TSR_BUCKET_NAMES, 'bucket_names', len(TSR_BUCKETS), 'tsr_mt01')
_check_len(TSR_MANDATORY_ROOM, 'mandatory_room', len(TSR_BUCKETS), 'tsr_mt01')
_check_len(TSR_SPLIT_ROOMS, 'split_rooms', len(TSR_BUCKETS), 'tsr_mt01')
TSR_CLUE_COORDS = _get(_tsr, 'clue_coordinates', 'tsr_mt01')

# ---------------------------------------------------------------------------
# FPI_MT01：游乐场 · 匹配录像盘与放映机
# ---------------------------------------------------------------------------
_fpi = load('fpi_mt01')
FPI_FIXED_PROJECTOR = _get(_fpi, 'fixed_projector', 'fpi_mt01')
FPI_GROUPS = [[tuple(candidate) for candidate in group]
              for group in _get(_fpi, 'groups', 'fpi_mt01')]
FPI_SYMBOLS = _get(_fpi, 'symbols', 'fpi_mt01')
FPI_SYMBOL_NAMES_ZH = _get(_fpi, 'symbol_names_zh', 'fpi_mt01')
FPI_PROJECTOR_COORDS = _get(_fpi, 'projector_coordinates', 'fpi_mt01')

# ---------------------------------------------------------------------------
# TFS_MT03：玩具工厂 · 开启六个阀门
# ---------------------------------------------------------------------------
_tfs = load('tfs_mt03')
TFS_SECTION_ORDER = _get(_tfs, 'section_order', 'tfs_mt03')
TFS_SECTIONS = {section: [tuple(candidate) for candidate in candidates]
                for section, candidates in _get(_tfs, 'sections', 'tfs_mt03').items()}
TFS_VALVE_COORDS = _get(_tfs, 'valve_coordinates', 'tfs_mt03')

# ---------------------------------------------------------------------------
# PSA_MT01：警察局阁楼 · 图案钥匙与录像盘
# ---------------------------------------------------------------------------
_psa = load('psa_mt01')
PSA_SYMBOLS = _get(_psa, 'symbols', 'psa_mt01')
PSA_SYMBOL_NAMES_ZH = _get(_psa, 'symbol_names_zh', 'psa_mt01')
PSA_START_ROOM = _get(_psa, 'start_room', 'psa_mt01')
# 节点 1 的起始钥匙：StartingKeySpawner / StartingKeyRoom，不参与随机
PSA_START_KEY = _get(_psa, 'start_key', 'psa_mt01')
# 房间过滤距离用的 RBRoom Brush 根坐标 / 每房钥匙生成点 / 该房成为最终房时的录像盘
PSA_ROOM_POSITIONS = _get(_psa, 'room_positions', 'psa_mt01')
PSA_ROOM_SPAWNERS = _get(_psa, 'room_spawners', 'psa_mt01')
PSA_FILM_REELS = _get(_psa, 'film_reels', 'psa_mt01')
PSA_ROOM_ALIASES = _get(_psa, 'room_aliases', 'psa_mt01')
_missing = [room for room in PSA_ROOM_POSITIONS if room not in PSA_ROOM_SPAWNERS]
if _missing:
    raise SeedDataError('data/psa_mt01.json 的 room_spawners 缺少房间 %s'
                        % ','.join(sorted(_missing)))
if PSA_START_ROOM not in PSA_ROOM_POSITIONS:
    raise SeedDataError('data/psa_mt01.json 的 start_room 不在 room_positions 里')

# ---------------------------------------------------------------------------
# RES_MT02：水疗度假村 · 焚毁莉莉娅的遗物
# ---------------------------------------------------------------------------
_res2 = load('res_mt02')
RES_MT02_COORDINATORS = _get(_res2, 'coordinators', 'res_mt02')
# 318 个 RE_MannequinTrap 容器：name/level/pool(main|tutorial|base)/room/x,y,z/yaw/spawn_offset
RES_MT02_POOL = _get(_res2, 'pool', 'res_mt02')

# ---------------------------------------------------------------------------
# 实测样本（--selftest）
# ---------------------------------------------------------------------------
_samples = load('samples')
SAMPLES_CHJ = [(seed, expect)
               for seed, expect in _get(_samples, 'chj_mt01', 'samples')]
SAMPLES_CHJ_MT02 = [(seed, expect)
                    for seed, expect in _get(_samples, 'chj_mt02', 'samples')]
SAMPLES_MHS = [(seed, zone, short, code)
               for seed, zone, short, code in _get(_samples, 'mhs_mt01', 'samples')]
SAMPLES_MHS_PICK = [(seed, zone, short)
                    for seed, zone, short in _get(_samples, 'mhs_mt01_pick', 'samples')]
SAMPLES_RES = [(seed, (expect, scene))
               for seed, (expect, scene) in _get(_samples, 'res_mt01', 'samples')]
SAMPLES_SMC = [(seed, expect)
               for seed, expect in _get(_samples, 'smc_mt02', 'samples')]
# 阶段号在 JSON 里是字符串键，这里转回 int；每个房间的 (图案, 答案) 转回 tuple
SAMPLES_GS = [
    (seed, {int(stage): {room: tuple(want) for room, want in rooms.items()}
            for stage, rooms in rounds.items()})
    for seed, rounds in _get(_samples, 'fpi_mt02', 'samples')]
SAMPLES_TSR = [(seed, list(codes))
               for seed, codes in _get(_samples, 'tsr_mt01', 'samples')]
SAMPLES_FPI_MT01 = [(seed, [tuple(item) for item in expect])
                    for seed, expect in _get(_samples, 'fpi_mt01', 'samples')]
SAMPLES_TFS = [(seed, [tuple(item) for item in expect])
               for seed, expect in _get(_samples, 'tfs_mt03', 'samples')]
TFS_SAMPLE_ROOMS = _get(_samples, 'tfs_mt03_rooms', 'samples')
SAMPLES_PSA = [(seed, [(symbol, room, list(coordinates))
                       for symbol, room, coordinates in expect])
               for seed, expect in _get(_samples, 'psa_mt01', 'samples')]
# {密码盘 actor: (房间名或 None, 4 位密码)}
SAMPLES_SRR = [(seed, {pad: (value[0], str(value[1]))
                       for pad, value in expect.items()})
               for seed, expect in _get(_samples, 'srr_mt01', 'samples')]

# ---------------------------------------------------------------------------
# SRR_MT01：郊区住宅区 · 撬开富豪宅的密码盘
# ---------------------------------------------------------------------------
_srr = load('srr_mt01')
# 协调器（House1..House5）→ 密码盘 actor / 本局要选几间房 / 每个 Section 的候选房
SRR_HOUSES = _get(_srr, 'houses', 'srr_mt01')
SRR_HOUSE_ORDER = list(_get(_srr, 'house_order', 'srr_mt01'))
# 房间名 → RBPuzzleRoomComponent 组件名（compSeed 要用组件名算，不是房间名字本身）
SRR_ROOM_COMPONENTS = _get(_srr, 'room_components', 'srr_mt01')
SRR_ROOM_CENTERS = _get(_srr, 'room_centers', 'srr_mt01')
