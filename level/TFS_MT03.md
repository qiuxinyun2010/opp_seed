# TFS_MT03 正向推理：seed → 六个阀门点位

> 输入 `level_seed`（+ 人数 / 难度），**只输出本局 6 个阀门点位**：
> actor、房间、坐标，按分区 A1/A2/A3/B1/B2/B3 排列。
> 实现：`../seed.py` 的 `_predict_tfs_mt03()`；静态池与坐标：`../data/tfs_mt03.json`；
> 实测：`../test.txt` 第 564–577 行（527527、41041，均 Easy / 1P）。
> 完整反编译取证见 `release/coop/TFS_MT03/TFS_MT03_FORWARD.md`，
> 类布局见 `release/coop/TFS_MT03/RBFirePumpObjectiveCoordinator.md`。

```powershell
python seed.py TFS_MT03 527527
python seed.py TFS_MT03 527527 --trace
python seed.py TFS_MT03 41041 --json
python seed.py --selftest                 # 166/166，含本关 12 条样本
```

```text
TFS_MT03  seed=527527  salt=527
  A1  MT03_TF_Gas_ValvePanel_BP_Section_A1_03   RBRoom_West_Storage   (-780, 1365, 1)
  A2  MT03_TF_Gas_ValvePanel_BP_Section_A2_05   RBRoom_West_PuppetWorshop   (-5075, -1329.9, -25)
  A3  MT03_TF_Gas_ValvePanel_BP_Section_A3_1    RBRoom_Ext_ReceivingDocks_Stairs_Slave_1   (-1280, -2250, 150)
  B1  MT03_TF_Gas_ValvePanel_BP_Section_B1_08   RBRoom_East_Storage   (-480, 3230, 0)
  B2  MT03_TF_Gas_ValvePanel_BP_Section_B2_07   RBRoom_East_Laundry   (-795, 3920, 0.8)
  B3  MT03_TF_Gas_ValvePanel_BP_Section_B3_5    RBRoom_Ext_LoadingDocks_Storage   (1435, 6635, 200)
```

---

## 0. 结论先行

六个分区互相独立，每区只做 **一次** 由 seed 决定的抽取：

| 用途 | 表达式 | 出处 |
|---|---|---|
| 名字种子 `cs` | `seed_chain(["PersistentLevel", "MT03_FirePump_ObjCoord_BP_Section"+区])` | `sub_140503B80` |
| 关卡盐 | `salt = level_seed % 1000` | `sub_1402D29E0` |
| **本局阀门** | `j = RandSeeded(cs + 61390 + N, N, salt)` → `Valves[j]` | `0x1434B3F7B` |

`N` 是该区 `Valves` 条数（B3=6、B2=8、B1=4、A3=6、A1=6、A2=6）；
`+N` 是 `sub_1434B3330` 里的**当前候选池长度** `LODWORD(v191[1])`，不是抽取序号。
`RandSeeded(seed, N) = (mix64(seed, salt) & 0xFFFF) % N`。

**另外三个盐在本关全部退化为常数**（关卡静态配置决定，见 §2.2）：
`94922`（选区，池长 1 → 0）、`3156`（补足区数，余池为空 → 不触发）、
`39135`（状态主选，`IsStateA` 之后有效池只剩 1 个 → 0）。
因此本关只有 `61390` 这一次抽取由 seed 决定答案。

> 池序必须是 `TFS_LD_MT03_B00.json` 里 `Sections[0].Valves` 的**原始顺序**：
> B2 为 `07,01,02,03,04,5,05,06`，A3 跳号 4，B3 末尾 `6,5`；
> 不是名字字典序。`data/tfs_mt03.json` 已按原序保存。

### 两份实测（actor 级 12/12）

| 区 | `cs` | N | `cs+61390+N` | 527527 (salt 527) | 41041 (salt 41) |
|---|---|---:|---|---|---|
| B3 | `0x6F706C98` | 6 | `0x6F715C6C` | j=5 → `B3_5` | j=3 → `B3_4` |
| B2 | `0x48436C45` | 8 | `0x48445C1B` | j=0 → `B2_07` | j=4 → `B2_04` |
| B1 | `0x3A95DBEF` | 4 | `0x3A96CBC1` | j=3 → `B1_08` | j=1 → `B1_03` |
| A3 | `0x16148CC7` | 6 | `0x16157C9B` | j=0 → `A3_1` | j=1 → `A3_2` |
| A1 | `0x53F32BB0` | 6 | `0x53F41B84` | j=2 → `A1_03` | j=4 → `A1_05` |
| A2 | `0x413F8C1E` | 6 | `0x41407BF2` | j=4 → `A2_05` | j=4 → `A2_05` |

---

## 1. 取证链（与 TSR_MT02 同套路：先读引擎，再回归）

```text
1  地图 JSON：6 个 FirePump_ObjCoord_BP_C（各 1 组 × 1 Section）；
              36 个 TF_Gas_ValvePanel_BP_C + 36 个 ValvePanelComponent_BP_C
2  类链：宽类名 0x1466E569C → UClass sub_140881C30（size 11280）
        → CDO sub_1426EE3B0：主 vfptr off_1459D12E0
3  vtable slot 249 @0x1459D1AA8 = sub_1434B3330 ← 本关主随机化函数
   （兄弟类 RBWaterValveObjectiveCoordinator 的 slot 249 是 sub_143803600）
4  逐段反编译 sub_1434B3330：4 个盐立即数 + 池 + 状态写入
5  辅助函数逐一读出语义：
        sub_140503B80  GetSeed          sub_1402D29E0  RandSeeded
        sub_1404FF400  IntByDifficulty  sub_1419BF030  BoolByDifficulty
        sub_1402BF7F0  FRandomSettings 的 k
        sub_1402947F0  PrepareState     sub_140B47990  IsStateA
        sub_1437DD5F0  写组件状态        sub_1434B56D0  状态 1 判定谓词
6  sub_1414A0D40（RBRandomizable UClass 注册）读到 UFunction 名：
        qword_146E7D7F8 = FName "IsStateA"，qword_146E7D800 = "PrepareState"，
        qword_146E7D810 = "SetState" …
7  用 527527 / 41041 正向回归（12/12）
```

所有常数都来自代码与关卡 JSON，实测只用于最后证伪，没有扫参数 / 枚举偏移 / 按样本挑分支。

---

## 2. 正向算法

### 2.1 名字链与 salt

`sub_140503B80(coord, 0)`：Actor 分支到 `ULevel` 即止，
`cs = |crc32_fname(coord) + |crc32_fname("PersistentLevel") + 0||`（`seedcore.seed_chain`）。
全局种子 `dword_146E2E5C4` 只通过 `% 1000` 进入 `RandSeeded`，
所以 `S` 与 `S+1000` 等价。人数 / 难度走 `sub_1404FF400` / `sub_1419BF030`
（都读 `sub_141D2A240()+628 = EffectiveNumberOfPlayers`），本关配置无分档覆盖。

### 2.2 关卡静态配置把 4 个盐里的 3 个退化掉

| 输入 | 值 | 后果 |
|---|---|---|
| `ValveSectionGroupConfig.Num` / 每组 `Sections.Num` | 1 / 1 | `runtime.Num()=1`，entry 下标 `v82=0` |
| `MinimumValveInSection` | 1 | `sub_1404FF400` → 1 |
| `NumberOfValveSections` | 1（实例覆盖 native CDO 的 2） | `3156` 补池循环条件不成立 |
| `runtime entry +8`（区可用） | 1 | 36/36 组件 `PipeArrangements[0].AllowedByDifficulty` 回落 `NormalLocalValue=true` |
| `ValvePerSectionRandomSettings` | Min/MaxRatio=0，Min/MaxCount=1 | `sub_1402BF7F0` → `k=1` |
| `MinimumDistanceBetweenValves` | 0（native CDO `+4856`） | `0 <= dist²` 恒真 |
| `PipeArrangements` 条数 | 1（36/36） | `61390` 首抽即通过 |

于是 `94922`：`RandSeeded(cs+94922+0, 1) = 0`；`3156`：余池空、目标数已满足，整段跳过。

### 2.3 `61390` 强制阀门循环（`0x1434B3F50–0x1434B41A8`）

```text
k    = sub_1402BF7F0(ValvePerSectionRandomSettings, cs + v82, N, 0) = 1
pool = copy(Sections[0].Valves)                    # +24 数组，JSON 原序，N 项
pos  = []                                          # 已强制阀门坐标
while forced.Num() < k and pool 非空:
    draw = v82 * runtime.Num() + (cs + 61390) + pool.Num()
         = cs + 61390 + len(pool)                  # 0x1434B3F7B
    j    = RandSeeded(draw, len(pool), salt)
    v    = pool[j]
    ok   = PipeArrangements 全 AllowedByDifficulty and minDist² <= |P_v − P_p|² (∀p∈pos)
    if ok: PrepareState(v, 1); pos.add(P_v); forced.add(v)
    else:  rejected.add(v)
    RemoveAtSwap(pool, j)
其余全部 PrepareState(v, 0)
```

本关 `minDist²=0`、首抽 `pos` 为空、36/36 阀门可用 ⇒ **首抽必中、循环只跑一轮**，
即 §0 的公式。`RemoveAtSwap` 之后的池不参与答案。

### 2.4 `PrepareState` → `IsStateA` → `39135` 退化

`sub_1402947F0(v, a2, 0)` 写 helper state `= 2 - a2`：
强制阀门 `a2=1` → **StateA(1)**，其余 `a2=0` → **StateB(2)**。
主循环重建有效池时调 `sub_140B47990` = UFunction **`IsStateA`**，
于是 `valid = [j]`（长度 1），`RandSeeded(cs+39135+0, 1) = 0`，主阀门仍是 `j`。
`sub_1437DD5F0` 给 `j` 写组件状态 **1**、其余写 **4**；
`sub_1434B56D0`（本类 vtable slot 250）正是判 `component+5916 == 1` 的谓词。

### 2.5 兄弟类 WaterValve 实现的差别

`sub_143803600` 属于 `RBWaterValveObjectiveCoordinator`（本关未用）。
两者盐常量相同但对象布局不同，按 vfptr 与 runtime 偏移区分：

| | FirePump（本关 `sub_1434B3330`） | WaterValve（`sub_143803600`） |
|---|---|---|
| 61390 的 seed | `cs + 61390 + pool.Num()` | `i + cs + 61390 + v83*N` |
| runtime 数据 | `+11256`（Num `+11264`） | `+10424`（Num `+10432`） |
| 距离过滤 | `+4856` `MinimumDistanceBetweenValves` | `vtable+1872` 的全局 R |
| 收尾 | `sub_1434B4BB0` | `sub_143804B00` |

---

## 3. 实测回归

| 判据 | 结果 |
|---|---|
| 527527 actor 级（`../test.txt` 564–570） | 6/6 |
| 41041 actor 级（`../test.txt` 571–577） | 6/6 |
| 14014 / 90090 房间级（`../test.txt` 58–64、338–344） | 12/12 |
| `S` 与 `S+1000` 等价 | 一致 |
| `python seed.py --selftest` 全库 | **166/166** |

`--trace` 会打印每区 `cs / N / draw_seed / idx → actor`，不进入 `view()` / CLI 点位输出。

---

## 4. 代码位置索引

| 地址 | 作用 |
|---|---|
| `0x1459D1AA8` | 主 vtable slot 249 → `sub_1434B3330` |
| `0x1434B33AB` | `cs = sub_140503B80(coord, 0)` |
| `0x1434B33DD` / `3B5D` / `3CB0` / `3CBF` | `cs+94922` / `cs+3156` / `cs+61390` / `cs+39135` |
| `0x1434B3750` / `3AD0` | `MinimumValveInSection` / `NumberOfValveSections` → `sub_1404FF400` |
| `0x1434B3C81` / `3C86` | 复制 `ValvePerSectionRandomSettings`（`+4056`） / 读 `+4856` |
| `0x1434B3EEA` | `k = sub_1402BF7F0(settings, cs+v82, N, 0)` |
| `0x1434B3F7B` | `j = RandSeeded(v82*runtime.Num() + v179 + pool.Num(), pool.Num())` |
| `0x1434B40AF` / `425B` | `PrepareState(v,1)` / 其余 `PrepareState(v,0)` |
| `0x1434B3DCE` / `3E48` | `39135` 主选 / `sub_1437DD5F0` 写组件状态 |
| `0x1434B4BB0` | 收尾（VisOn/VisOff/材质联动） |
| `0x1402947F0` | `PrepareState`：helper state `= 2 - a2` |
| `0x140B47990` | `IsStateA()`：`qword_146E7D7F8` + 接口 thunk `vtbl+544` |
| `0x1414A0D40` | `RBRandomizable` 注册，写出 `IsStateA` / `PrepareState` / `SetState` 等 UFunction 名 |
| `0x1404FF400` / `0x1419BF030` | `FIntByDifficulty::Get` / `FBoolByDifficulty::Get` |
| `0x1402BF7F0` / `0x1402D29E0` / `0x140503B80` | k / `RandSeeded` / `GetSeed` |
| `0x1434B56D0` | 本类 slot 250 谓词：`component+5916 == 1` |

---

## 5. 边界

- **输出口径**：`predict('TFS_MT03', seed)` 只返回 `{'valves': [...]}`，
  每项 `section / actor / room / coordinates / coordinate_type`；
  `view()` / CLI / `--json` 只铺 6 个点位，不带 preselect / main / coordinator_seed 等中间量。
- **难度 / 人数**：本关 `bLocalOverrideFor1P/2P/3P` 与 `bOverrideEasy/Hard/Insane` 全 false，
  一律回落 `NormalLocalValue`，代码路径与 1P/Easy 相同；但只有 Easy/1P 的实测。
- **运行期量**：`IsStateA` 依赖 `PrepareState` 调用顺序，按反编译控制流推演，未做运行时 hook。
  若游戏改动 `FRandomSettings`（`k>1`）或 `MinimumDistanceBetweenValves>0`，
  需把 §2.3 的循环与距离判断重新接回 `seed.py`（当前按本关常量折叠为单次抽取）。
- 只有两份 actor 级实测；样本外泛化建议再补 1–2 局完整记录。

---

## 6. 参考

- `../seed.py` `_predict_tfs_mt03()`、`../seedcore.py`、`../data/tfs_mt03.json`、
  `../data/samples.json`、`../test.txt`
- `release/coop/TFS_MT03/TFS_MT03_FORWARD.md`（完整正向推导与地址表）
- `release/coop/TFS_MT03/RBFirePumpObjectiveCoordinator.md`（类布局 / 属性偏移 / vtable）
- `../SEED_FORMULAS.md`、`../FUNC_INDEX.md`
- 关卡数据：`paks/MAP/Maps/ToyFactoryShipping/TFS_LD_MT03_B00.json`、
  `paks/LD_json/LD/Coordinators/FirePump_ObjCoord_BP.json`
