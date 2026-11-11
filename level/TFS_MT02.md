# TFS_MT02 正向：seed → 任务钥匙点位

> 输入任意 `level_seed` + 人数（1/2/3）+ 难度，**只输出每个钥匙的点位**。
> 交付实现：`../seed.py`（`TFS_MT02_POOLS` / `_predict_tfs_mt02`），已纳入 `--selftest`；
> 取证探针：`temp/tfs_mt02_predict.py`；候选池与坐标：`../ui/data/maps/TFS_MT02.json`；
> 类布局：`../class/TFS_MT02_Coordinators.md`、`../class/RBUseQuestItemsObjectiveCoordinator.md`；
> 实测：`../test.txt` 第 578–589 行（698698 / 462462 / 777777，均 Easy / 1P）。

```powershell
python seed.py TFS_MT02 698698                       # 1P：只列本局 2 把钥匙点位
python seed.py TFS_MT02 698698 --players 3          # 2P/3P：列 4 把
python seed.py TFS_MT02 698698 --json               # 标准极简视图 points
python seed.py --selftest                           # 176/176，含本关 9 条
python temp\tfs_mt02_predict.py --scan              # 半径 R 的 9/9 有效区间
```

```text
TFS_MT02  seed=698698  salt=698  → Pink
  C  TFS_KeyModule_Spawner_C_BP_PinkKeyIntro_8              (二选一门 PinkGate2)
  D  TFS_KeyModule_Spawner_D_BP_PinkKey_InventoryRecords_2   (固定门 PinkGate)
TFS_MT02  seed=462462  salt=462  → Green
  A  TFS_KeyModule_Spawner_A_BP_GreenIntro_12               (二选一门 GreenGate3_3)
  B  TFS_KeyModule_Spawner_B_BP_GreenKey_Foreman_8           (固定门 GreenGate)
TFS_MT02  seed=777777  salt=777  → Green
  A  TFS_KeyModule_Spawner_A_BP_GreenIntro_12               (二选一门 GreenGate3_3)
  B  TFS_KeyModule_Spawner_B_BP_GreenKey_Storage_1           (固定门 GreenGate)
```

---

## 0. 结论先行

1P 局只启用 **1 条推车线**（Green 西 / Pink 东），所以一局只刷 **2 把钥匙**：一把「Intro 钥匙」开二选一门，一把「固定门钥匙」开固定门。
`test.txt` 每局恰好记录 2 个点位，与此一致。

| 用途 | 表达式 | 出处 |
|---|---|---|
| 关卡盐 | `salt = level_seed % 1000`（`S` 与 `S+1000` 等价） | `sub_1402D29E0` |
| **推车线** | `base_c = crc32_fname("Objective Actors") + GetSeed("MT02_B00_PushCart_ObjCoord_BP")`；`idx = RandSeeded(base_c, 2, salt)` → 2 个起点池 | `sub_1402AE7F0` / `sub_1402B05C0` |
| **每把钥匙** | `base_k = crc32_fname("Item Spawner") + GetSeed(该池协调器)`；`idx = RandSeeded(base_k, |pool|, salt)` → `pool[idx]` | `sub_1402AF2D0`（vtable slot 273） |
| 池 | 该 `ItemSpawnerClass` 的全部 actor，按名字不区分大小写字典序升序 | `sub_1402B46B0` |
| 抽取前排除 | `sub_1402B4CA0`：以同侧已放置目标为参照，尾→头 swap 删除「水平距离 < R 且 |ΔZ| ≤ 200」的候选 | 调用点 `0x1402B0B92` |
| **二选一门** | `base_g = crc32_fname("Objective Actors") + GetSeed(Intro 协调器)`；`idx = RandSeeded(base_g, 2, salt)` | 同引擎推断，**无实测校验** |

`GetSeed(coord) = |crc32_fname(coord) + GetSeed("PersistentLevel")|`；`RandSeeded(seed, N) = (uint16)mix64(seed, salt) % N`（`seedcore.py`）。

---

## 1. 取证链（承接类分析）

```text
1  地图 JSON：4 个 SimpleQuestItem_ObjCoord_BP_C → RBUseQuestItemsObjectiveCoordinator；
              68 个 TFS_KeyModule_Spawner_A/B/C/D_BP_C；6 个钥匙门；4 个 RBPushCartSpawner
2  类链：RBUseQuestItemsObjectiveCoordinator 主 vtable off_14598D950，slot 273 @0x14598E1D8
        = sub_1402AF2D0（SpawnerActors 随机化）
3  反编译 sub_1402AF2D0（0x1B7）：
        if (coord+4088 & 1)                              // bUseSpawnerActorsRandomization
            class = coord+3840                          // ItemSpawnerClass
            salt  = L"Item Spawner"（xmmword_1466F52CE，26B=13 宽字符）
            sub_140A61C30(setup=coord+4096, coord, &class, &salt)   // 按类收集 → 通用引擎
        否则 sub_1402AF490(coord+3848 显式表, ...)
4  通用引擎 sub_1402B05C0（0x22F2，已在 FPB_MT03 / CHJ_MT02 复刻）：
        排序 sub_1402B46B0 → 分类趟 → sub_1402B4CA0 跨协调器排除 → 分桶抽取
        base = crc32_fname(盐) + GetSeed(coord)（+ 已选数；本关 DesiredCount=1 ⇒ +0）
        idx  = RandSeeded(base, |pool|, salt)；RemoveAtSwap
5  汇编复核调用点 0x1402B0B92（sub_1402B05C0 → sub_1402B4CA0）：
        0x1402B0B46  movss xmm0, [rdi+0x65c]           ; a6 = setup+1628「异区半径 R」缓存
        0x1402B0B4E  mov   r8b, [rdi+0x3ea]            ; a3 = setup+1002 bUseOtherCoordoActorsForDistance
        0x1402B0B5C  movss [rsp+0x28], xmm0            ; → a6 = R
        0x1402B0B74  mov   dword [rsp+0x30], 0x43480000 ; → a7 = 200.0f
6  反编译 sub_1402B4CA0：v21=池 Num，v22=v21--，从尾部取 v23；
        命中 → memcpy 把池尾搬到 v22 处、Num-- ⇒ **尾→头 swap 删除**（会改变池序）
7  推车线：PushCart_ObjCoord_BP_C 的 PrimaryActorsRandomizationSetup.DesiredCount
        = 2（1P 覆盖为 1），slot 249 = sub_1402AE7F0，盐 "Objective Actors"
8  用 698698 / 462462 / 777777 回归：6 个钥匙点位 + 3 个推车线 = 9/9
```

所有盐名、`GetSeed` 链、池序、坐标、`DesiredCount` 都来自代码或关卡 JSON；**唯一拟合量**是 `R`（见 §5）。

---

## 2. 关卡静态配置（`$..._B00.json` + UI 派生）

`MT02_RBObjectiveCoordinatorGroup.ConcurrentCoordinators` 顺序：

```text
MT02_B00_PushCart_ObjCoord_BP
MT02_SimpleQuestItem_ObjCoord_BP_GreenSide_Intro   (A · 12 个候选 · 钥匙 QuestItem_A)
MT02_SimpleQuestItem_ObjCoord_BP_PinkSide_Intro    (C · 10 个候选 · 钥匙 QuestItem_C)
MT02_SimpleQuestItem_ObjCoord_BP_GreenSide_A       (B · 29 个候选 · 钥匙 QuestItem_B)
MT02_SimpleQuestItem_ObjCoord_BP_PinkSide_B        (D · 17 个候选 · 钥匙 QuestItem_D)
```

⇒ **Intro（A/C）先于固定门（B/D）**，因此 B/D 的候选池会受同侧 Intro 已放置点的影响。

| 池 | 协调器 | 候选数 | 目标门 |
|---|---|---:|---|
| A | `..._GreenSide_Intro` | 12 | `GreenGate2_1` / `GreenGate3_3`（二选一） |
| B | `..._GreenSide_A` | 29 | `GreenGate`（固定） |
| C | `..._PinkSide_Intro` | 10 | `PinkGate2` / `PinkGate3`（二选一） |
| D | `..._PinkSide_B` | 17 | `PinkGate`（固定） |

4 个协调器均 `bUseSpawnerActorsRandomization=1`、`SpawnerActorsRandomizationSetup.DesiredCount=1`、
`bSplitByObjectiveType / bUseRoomGroupsAsObjectiveType / bLimitOneObjectivePerRoom=1`；
`SpecificItemSpawners` 为空 ⇒ 走按类收集。Intro 池另把 `DistanceBetweenSame/DifferentObjectives` 覆写为 0。

`MT02_B00_PushCart_ObjCoord_BP`：`NumberOfUnlockableRailGates=0`（本关不用轨道门随机化）、
`PrimaryActorsRandomizationSetup.DesiredCount=2 / 1P=1`。

---

## 3. 正向算法

### 3.1 推车线（决定刷哪一侧）

```text
base_c = crc32_fname("Objective Actors") + GetSeed("MT02_B00_PushCart_ObjCoord_BP")
       = 0x61F064CE
pool_c = [MT02_RBPushCartSpawner_EastSide_Pink, MT02_RBPushCartSpawner_WestSide_Green]  # 名字典序
idx    = RandSeeded(base_c, 2, salt)
side   = Pink if idx==0 else Green
```

3/3 命中：698698→Pink（idx 0）、462462/777777→Green（idx 1）。
地图里另有 2 个 `*RailGoal*` 终点 spawner，本模型按「2 个起点」建模（1P 只启用 1 台车）；4 个对象如何过滤为 2 个尚未从代码定标。

### 3.2 两把钥匙（按 Intro → 固定门顺序）

```text
for k in (intro, fixed):
    base_k = (crc32_fname("Item Spawner") + GetSeed(COORDS[k])) & 0xFFFFFFFF
    pool   = sorted(该 ItemSpawnerClass 的全部 actor, key=str.lower)
    pool   = purge(pool, 已放置目标, R, 200.0)   # 尾→头 swap 删除
    idx    = RandSeeded(base_k, |pool|, salt)
    pick   = pool[idx]
    已放置目标.append(坐标(pick))
```

`purge` 的条件：`(Δx² + Δy²) < R² 且 |Δz| ≤ 200`。Intro 池是当侧第一个目标，参照列表为空 ⇒ 整池参与抽取。

四个 `base_k`（`crc32_fname("Item Spawner") = 0xFB1A1645`）：

| 池 | `GetSeed(coord)` | `base_k` | 全池 N |
|---|---|---|---:|
| A | `0x6F744032` | `0x6A8E5677` | 12 |
| B | `0x514D30B6` | `0x4C6746FB` | 29 |
| C | `0x3ED68BA3` | `0x39F0A1E8` | 10 |
| D | `0x14E0E22A` | `0x0FFAF86F` | 17 |

### 3.3 二选一门（无实测）

```text
base_g = crc32_fname("Objective Actors") + GetSeed(Intro 协调器)
idx    = RandSeeded(base_g, 2, salt)
门     = [GreenGate2_1, GreenGate3_3] 或 [PinkGate2, PinkGate3] 的 idx 项
```

输出：698698→`PinkGate2`、462462 / 777777→`GreenGate3_3`。`test.txt` 未记录门，**该行只是模型输出，不算回归**。

### 3.4 任意 seed / 人数 / 难度

**seed**：`GetSeed` 只由对象名链决定，`RandSeeded` 只吃 `salt = seed % 1000`，所以对任意
`[1, 2^32-1]` 的 seed 都是同一个纯函数；`S` 与 `S+1000` 输出相同（脚本校验范围）。

**人数**：`TFS_LD_MT02_B00.json` 的 `FIntByDifficulty` 分档实测（`temp/tfs_mt02_difficulty.py`）：

| 配置项 | 默认 | 1P | 2P | 3P |
|---|---:|---:|---:|---:|
| `PushCart...PrimaryActorsRandomizationSetup.DesiredCount` | 2 | 1 | 2 | 2 |
| `PushCart...FixedMaxCount` | 2 | 1 | 2 | 2 |
| `NumberOfUnlockableRailGates` | 0 | 0 | 0 | 0 |
| 4 个钥匙协调器 `SpawnerActorsRandomizationSetup.DesiredCount` | 1 | 无覆盖 | 无覆盖 | 无覆盖 |
| Intro 协调器 `PrimaryActorsRandomizationSetup.DesiredCount` | 1 | 1 | 1 | 1 |

⇒ **人数不改变任何钥匙池的 base / 池长 / `DesiredCount` / 排除半径**，四个点位的计算与人数无关；
只改「本局要完成几台推车」。`sub_1402D29E0`（`RandSeeded`）不含人数参数，人数只在
`sub_1404FF400` / `sub_1419BF030` 读 `EffectiveNumberOfPlayers` 时分档取值。

脚本口径（**外推，无 2P/3P 实测**）：

- `players=1`：`cart_side_1p` 一侧的 2 把钥匙标为有效任务点位；
- `players=2/3`：推车数 2，两侧 4 把钥匙都标为有效。

**难度**：5 个协调器实例的分档里**没有** `bOverrideEasy/Hard/InsaneLocalValue`，
按 `seedcore.int_by_difficulty` 的回落语义所有难度都取 `NormalLocalValue`，输出不变
（脚本仍接受并校验 `easy/normal/hard/insane`）。

---

## 4. 实测回归（`../test.txt:578–589`）

| seed | salt | 推车线 | Intro 钥匙 | 固定门钥匙 | 结果 |
|---:|---:|---|---|---|---|
| 698698 | 698 | Pink ✓ | `..._C_BP_PinkKeyIntro_8` ✓ | `..._D_BP_PinkKey_InventoryRecords_2` ✓ | 3/3 |
| 462462 | 462 | Green ✓ | `..._A_BP_GreenIntro_12` ✓ | `..._B_BP_GreenKey_Foreman_8` ✓ | 3/3 |
| 777777 | 777 | Green ✓ | `..._A_BP_GreenIntro_12` ✓ | `..._B_BP_GreenKey_Storage_1` ✓ | 3/3 |

合计 **9/9**（6 个钥匙点位 + 3 个推车线）。

### 4.1 698698 的 D 池为什么不是「最简模型」的结果

不加排除趟时，`RandSeeded(0x0FFAF86F, 17, 698698) = 6` → `PinkKey_Electrical_1`；
实测是 `PinkKey_InventoryRecords_2`。加入 `sub_1402B4CA0` 后：

```text
参照点 = C 抽中的 PinkKeyIntro_8
尾→头剔除 4 个近邻：Laundry_3, Laundry_1, Electrical_3, Electrical_1
池 17 → 13（swap 删除同时重排池序）
RandSeeded(base_D, 13, 698698) = 10 → PinkKey_InventoryRecords_2  ✓
```

Green 侧的 `GreenIntro_12` 与所有 29 个 B 候选距离都 > R，B 池保持 29 ⇒ 462462 / 777777 直接命中「大概率」点位。

### 4.2 `test.txt` 里 B 池的「小概率」

462462 的 `Foreman_7`、777777 的 `Storage_2` 恰好是 **池长 22（29−7）** 时 `RandSeeded(base_B, 22, salt)` 的结果。
本模型用完整 29 池且无排除，命中记录中的「大概率」；这些「小概率」未纳入回归。

---

## 5. 参数来源与边界

| 参数 | 值 | 证据等级 |
|---|---|---|
| 盐名 `"Item Spawner"` | 宽串 `0x1466F52CE` | 代码（`sub_1402AF2D0` 反编译） |
| 盐名 `"Objective Actors"` | 通用引擎 | 代码 / `FUNC_INDEX.md`（CHJ_MT02 24/24 锁定） |
| `GetSeed` 链、池序、`RemoveAtSwap`、排除顺序 | `PersistentLevel → coord`、`sub_1402B46B0`、尾→头 swap | 代码 / 既有 15+ 关卡复刻 |
| `a7 = 200.0f` | `0x43480000` | **调用点汇编常量** |
| `a6 = R` | `[setup+0x65c]` = `+1628` 异区半径缓存 | 汇编；值由 `sub_1433AACD0` 全局默认给出 |
| **R 数值** | 脚本取 `4096.0`；9/9 有效区间 `4070..4330`（step 10） | ⚠️ **唯一拟合量**：3 个用例反推，尚未从配置表/CDO 定标 |
| 推车线池 = 2 个起点 | 3/3 命中 | 模型假设；`ObjectiveActorClasses` 实际收集到 4 个 spawner |
| 二选一门公式 | 同引擎推断 | **无实测** |

其它边界（**回答「任意 seed / 人数」时的置信度分级**）：

- **4 个钥匙候选位（任意 seed）**：公式是纯函数、静态配置无人数/难度分档覆盖，`RandSeeded` 不含人数 ⇒ 可信度较高；但只有 3 局样本证伪过，且 `R` 是拟合量，属于外推。
- **1P 哪 2 把算有效任务点位**：由推车线公式决定，3/3 实测支持；仍是推断（「每局只记录一侧」也可能只是记录不全）。
- **2P/3P**：仅从 `DesiredCount`（1P=1、2P/3P=2）推出「两侧都有效」，**无实测**；两侧同时激活时 `sub_1402B4CA0` 的参照列表是否跨侧共享也未定标 ⇒ 2P/3P 输出仅供定位参考。
- 只有 3 局 Easy/1P 实测；`S` 与 `S+1000` 等价；`RandSeeded(seed=0)` 会退化成 `rand()`（本关 4 个 base 均非 0）。
- 难度对本关输出无影响（无 `bOverride*`，回落 Normal）；`seedcore.int_by_difficulty` 的回落坑在其它关卡仍需按档处理。
- `bSplitByObjectiveType / bUseRoomGroupsAsObjectiveType / bLimitOneObjectivePerRoom=1` 的分组趟在本模型里**没有**改变基址或池序（统一 `+0`、房间数自增、分组先抽组等假设均已试过并证伪）。
- 已接入交付版 `seed.py`，但 `R` 仍是拟合量、门与 2P/3P 无实测；`predict()` 只返回 `key_points`，
  默认文本/`view()` 只铺点位，不带推车线、门、base 等中间量（`--trace` 走 stderr）。

---

## 6. 复现与参考

```powershell
cd c:\Users\DELL\AppData\Local\Temp\outlast\opp_seed
python seed.py TFS_MT02 698698                          # 交付版：只列钥匙点位
python seed.py TFS_MT02 698698 --players 3              # 人数
python seed.py --selftest                               # 含本关 9 条回归
cd ..
python temp\tfs_mt02_predict.py --scan                  # R 敏感区间（取证探针）
```

中间探针（只读）：`temp/tfs_mt02_forward.py`（最简模型 5/6）、`tfs_mt02_forward2.py`（距离/变体）、
`tfs_mt02_forward3.py`（池长/分组）、`tfs_mt02_offsets.py`（统一偏移）、`tfs_mt02_groupseed.py`（房间数）、
`tfs_mt02_purge.py`（排除半径扫描）、`tfs_mt02_side.py`（推车线）、`tfs_mt02_difficulty.py`（人数/难度分档）、
`tfs_mt02_helpers.py` / `tfs_mt02_groups.py`（地图组件标志）。

IDA MCP 复核清单：`decompile_function(0x1402AF2D0)`、`decompile_function(0x1402B4CA0)`、
`temp/tfs_mt02_disasm.py 0x1402B0B20 0x1402B0B9A`（调用点参数）、
`decompile_function(0x1433AACD0)`（全局默认 R 来源）。

参考：`../class/TFS_MT02_Coordinators.md`（类布局 / 属性 / vtable）、
`../class/RBUseQuestItemsObjectiveCoordinator.md`（主类全表）、
`../class/FORENSICS_METHODS.md`、`../FUNC_INDEX.md` §5.13 / §5.14、
`../SEED_FORMULAS.md` §FPC_MT02、`../seed.py` `_fpb_draw` / `_predict_fpc_mt02`、
`level/TFS_MT03.md`（同地图正向推导范例）。
