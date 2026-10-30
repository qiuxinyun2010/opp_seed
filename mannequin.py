# -*- coding: utf-8 -*-
"""SMC_MT02「商场 · 4 个人偶上半身配上对应颜色的下半身」模型。

算法来源（TOT.exe，基址 0x140000000）：

    base   = crc32_fname("Objective Actors") + GetSeed(协调器)          # 0x1402B05C0
    groups = 按人偶类型分组：A/B/C 各 11 个候选，D（教学）1 个           # 0x1402C30C0
             组顺序 = 关卡 actor 顺序里各类型首次出现的顺序 = A B C D
    洗牌   = for i in 0..n-1: j = RandSeeded(base + i, 剩余组数) → RemoveAtSwap   (n = 4)
    抽取   = for k, g in enumerate(洗牌后的组):
                 本组候选先剔除「离任一已选目标太近」的                  # 0x1402B3C30
                 j = RandSeeded(base + n + k, 剔除后剩余数)
                 pick = 候选表[j]                                       # RemoveAt 保序
    太近   = 水平距离 < 5000（50 m）且 |ΔZ| <= 垂直容差

所谓「3 个人偶分散到 2 个区域」不是 section 规则，而是这条距离约束的副作用
（300 个 seed 抽样：298 次东+西，2 次全挤东侧）。

细节与边界见 release/coop/SMC_MT02/SMC_MT02.md。
随机原语复用 seedcore.py。
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import seedcore as sc  # noqa: E402

COORDINATOR = 'SMC_MT02_AuroraMannequin'
TAG = 'Objective Actors'

# 组的初始顺序 = 关卡 actor 顺序里各类型首次出现的顺序（实测 11×A + 11×B + 11×C + 1×D）
SETUP_TYPES = ['A', 'B', 'C', 'D']
TUTORIAL_TYPE = 'D'

# 颜色 ↔ 类型：由 seed=453453 实测反推（上半身 BP 在 MapSet 下未导出，读不到颜色）。
# 若组初始顺序不是 A B C D，房间集合不变，但绿/蓝会对调 —— 需要第二条实测才能钉死。
COLORS = {'A': 'Red', 'B': 'Green', 'C': 'Blue', 'D': 'Tutorial'}
COLORS_ZH = {'A': '红', 'B': '绿', 'C': '蓝', 'D': '教学'}

# 距离约束（0x1402B3C30）：关卡配置里两个值都是 5000（SMC_LD_MT02_B00.json:6330-6340）
DIST_XY = 5000.0
# 垂直容差：属性真值未读出。本关 ΔZ 只有「同层 ≤ 36.7 / 跨层 ≥ 415.1」两档，
# 取 (36.7, 415.1) 内任意值结果完全相同（300 个 seed 验证 0 差异），这里取 200。
DIST_Z = 200.0

# (布置点 actor, 房间, 区域, RootComponent 坐标)，顺序 = 关卡 actor 顺序
CANDIDATES = {
    'A': [
        ('SMC_MT02_ManneqinSetup_TypeA_BP10_20', 'RBRoom_EastCorridorRDC_Store1_Master', 'EastShoppingMall', [1845.4, -1302.9, 1.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP11_2', 'RBRoom_EastCorridorRDC_Store3_Master', 'EastShoppingMall', [2086.9, 1166.6, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP2_2', 'RBRoom_DepartmentStore_EastSide_1F', 'EastShoppingMall', [4252.2, -2929.8, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP3_11', 'RBRoom_EastCorridorRDC_Store2_Master', 'EastShoppingMall', [3172.9, -1699.5, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP4_2', 'RBRoom_EastCorridorRDC_Store4_3', 'EastShoppingMall', [6166.0, -196.6, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP5_5', 'RBRoom_EastCorridorRDC_StoreClosed_2', 'EastShoppingMall', [1855.8, 1525.2, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP6_8', 'RBRoom_WestCorridorRDC_Store3_Master', 'WestShoppingMall2', [-2844.1, 270.5, 35.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP7_11', 'RBRoom_WestCorridorRDC_Store1', 'WestShoppingMall2', [-3094.6, -1458.1, 35.7]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP8_14', 'RBRoom_WestCorridorRDC_Store2', 'WestShoppingMall2', [-2454.1, -1901.2, 35.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP9_17', 'RBRoom_DepartmentStore_WestSide', 'WestShoppingMall2', [-4331.7, -3041.1, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeA_BP_8', 'RBRoom_DepartmentStore_EastSide_2F', 'EastShoppingMall', [5218.6, -3106.4, 500.0]),
    ],
    'B': [
        ('SMC_MT02_ManneqinSetup_TypeB_BP10_20', 'RBRoom_EastCorridorRDC_Store1_Master', 'EastShoppingMall', [1801.8, -1291.9, 1.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP11_2', 'RBRoom_EastCorridorRDC_Store3_Master', 'EastShoppingMall', [2046.6, 1172.9, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP2_2', 'RBRoom_DepartmentStore_EastSide_1F', 'EastShoppingMall', [4232.5, -2929.5, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP3_5', 'RBRoom_EastCorridorRDC_Store2_Master', 'EastShoppingMall', [3173.2, -1715.0, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP4_2', 'RBRoom_EastCorridorRDC_Store4_3', 'EastShoppingMall', [6168.9, -262.9, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP5_5', 'RBRoom_EastCorridorRDC_StoreClosed_2', 'EastShoppingMall', [1810.4, 1549.4, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP6_8', 'RBRoom_WestCorridorRDC_Store3_Master', 'WestShoppingMall2', [-2874.1, 296.6, 35.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP7_11', 'RBRoom_WestCorridorRDC_Store1', 'WestShoppingMall2', [-3051.4, -1453.7, 34.9]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP8_14', 'RBRoom_WestCorridorRDC_Store2', 'WestShoppingMall2', [-2496.6, -1897.7, 35.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP9_17', 'RBRoom_DepartmentStore_WestSide', 'WestShoppingMall2', [-4336.2, -3084.4, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeB_BP_2', 'RBRoom_DepartmentStore_EastSide_2F', 'EastShoppingMall', [5233.6, -3109.0, 500.0]),
    ],
    'C': [
        ('SMC_MT02_ManneqinSetup_TypeC_BP10_20', 'RBRoom_EastCorridorRDC_Store1_Master', 'EastShoppingMall', [1842.6, -1278.9, 1.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP11_2', 'RBRoom_EastCorridorRDC_Store3_Master', 'EastShoppingMall', [2086.5, 1182.5, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP2_2', 'RBRoom_DepartmentStore_EastSide_1F', 'EastShoppingMall', [4256.7, -2924.5, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP3_5', 'RBRoom_EastCorridorRDC_Store2_Master', 'EastShoppingMall', [3177.8, -1685.3, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP4_2', 'RBRoom_EastCorridorRDC_Store4_3', 'EastShoppingMall', [6163.3, -229.0, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP5_5', 'RBRoom_EastCorridorRDC_StoreClosed_2', 'EastShoppingMall', [1837.6, 1545.3, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP6_8', 'RBRoom_WestCorridorRDC_Store3_Master', 'WestShoppingMall2', [-2853.6, 304.5, 35.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP7_11', 'RBRoom_WestCorridorRDC_Store1', 'WestShoppingMall2', [-3090.5, -1468.1, 34.9]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP8_14', 'RBRoom_WestCorridorRDC_Store2', 'WestShoppingMall2', [-2458.4, -1899.9, 36.7]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP9_17', 'RBRoom_DepartmentStore_WestSide', 'WestShoppingMall2', [-4336.4, -3035.6, 0.0]),
        ('SMC_MT02_ManneqinSetup_TypeC_BP_2', 'RBRoom_DepartmentStore_EastSide_2F', 'EastShoppingMall', [5213.4, -3119.1, 500.0]),
    ],
    'D': [
        ('SMC_MT02_ManneqinSetup_TypeD_BP_2', 'RBRoom_DepartmentStore_Central_SecurityRoom', 'SecurityRoom', [-364.6, -4143.1, 450.0]),
    ],
}


def _swap_remove(items, index):
    items[index] = items[-1]
    items.pop()


def too_close(a, b, dist_xy=DIST_XY, dist_z=DIST_Z):
    """0x1402B3C30：水平 < dist_xy 且 |ΔZ| <= dist_z → 太近，候选被剔除。"""
    ax, ay, az = a[3]
    bx, by, bz = b[3]
    if dist_xy <= 0:
        return False
    if (ax - bx) ** 2 + (ay - by) ** 2 >= dist_xy * dist_xy:
        return False
    if dist_z < 0:
        return True
    return abs(az - bz) <= dist_z


def predict(level_seed, dist_xy=DIST_XY, dist_z=DIST_Z, trace=False):
    if not 0 < level_seed <= sc.M32:
        raise ValueError('seed 必须在 [1, 2^32-1]')

    types = list(SETUP_TYPES)
    n = len(types)
    base = (sc.crc32_fname(TAG) +
            sc.seed_chain(['PersistentLevel', COORDINATOR])) & sc.M32

    # 1) 组顺序洗牌（0x1402C30C0）
    order = list(types)
    shuffled = []
    for i in range(n):
        pick = sc.rand_seeded((base + i) & sc.M32, len(order), level_seed)
        shuffled.append(order[pick])
        _swap_remove(order, pick)

    # 2) 逐组：先按距离过滤本组候选，再用 base+n+k 抽（k = 全局已选数）
    pools = {t: list(CANDIDATES[t]) for t in types}
    selected, picks, steps = [], [], []
    for letter in shuffled:
        pool = pools[letter]
        removed = 0
        for sel in selected:
            keep = []
            for cand in pool:
                if too_close(cand, sel, dist_xy, dist_z):
                    removed += 1
                else:
                    keep.append(cand)
            pool = keep
        pools[letter] = pool
        k = len(selected)
        if not pool:
            picks.append({'type': letter, 'color': COLORS[letter],
                          'color_name': COLORS_ZH[letter], 'room': None,
                          'section': '?', 'actor': None, 'coordinates': None,
                          'coordinate_type': None, 'candidate_index': None,
                          'pool_size': 0, 'removed': removed, 'order': k,
                          'tutorial': letter == TUTORIAL_TYPE})
            steps.append((letter, k, None, 0, removed))
            continue
        pick = sc.rand_seeded((base + n + k) & sc.M32, len(pool), level_seed)
        actor, room, section, xyz = pool[pick]
        item = {'type': letter, 'color': COLORS[letter],
                'color_name': COLORS_ZH[letter], 'room': room,
                'section': section, 'actor': actor, 'coordinates': list(xyz),
                'coordinate_type': 'actor', 'candidate_index': pick,
                'pool_size': len(pool), 'removed': removed, 'order': k,
                'tutorial': letter == TUTORIAL_TYPE}
        picks.append(item)
        selected.append(pool[pick])
        steps.append((letter, k, item, len(pool), removed))

    if trace:
        print('  SMC base=%d  组顺序=%s（初始 %s）'
              % (base, ''.join(shuffled), ''.join(types)))
        for letter, k, item, size, nremoved in steps:
            if item is None:
                print('    k=%d %s 候选被过滤空（剔除 %d）' % (k, letter, nremoved))
                continue
            print('    k=%d %s seed=%d 池=%d（剔除 %d）idx=%d -> %s'
                  % (k, letter, (base + n + k) & sc.M32, size, nremoved,
                     item['candidate_index'], item['room']))

    picks.sort(key=lambda item: item['type'])
    sections = [item['section'] for item in picks]
    return {
        'base': base,
        'group_order': shuffled,
        'mannequins': picks,
        'sections': sections,
        'spread': len(set(sections)),
    }


if __name__ == '__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        sys.exit(0)
    seed = int(argv[0])
    result = predict(seed, trace='--trace' in argv)
    for item in result['mannequins']:
        print('  [%-8s %-18s] %-44s %-42s%s'
              % (item['color'], item['section'], item['room'], item['actor'],
                 ' (%g, %g, %g)' % tuple(item['coordinates'])))
