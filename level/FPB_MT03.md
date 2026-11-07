# FPB_MT03 正向推理：seed → 4 区移动靶点位

> 输入 `level_seed`，输出四个区域各 4/4/4/3 个被选中的移动靶（含初始坐标、轨道端点、相位点位）。
> 关卡：`Destroy Futterman Targets to Open the Gates`（`LEVELS.md:89`），地图 `FunParkBarn`。
> 类级锚点见 `../class/FunPark_DamageableButton_BP_chain.md`、`../class/RBOperatable.md`；取证方法与校验锚点见 `../class/FORENSICS_METHODS.md`。
> **状态：区域 1 / 3 已闭环（249249、520520 各 4/4 逐靶命中）；区域 2 抽取公式确定、但抽取前排除集静态未闭环；区域 4 记录不全。**
> 本文只整理结论，不修改 `seed.py` / `data/fpb_mt03.json`。VA 基址 `0x140000000`；路径相对工作区根 `outlast/`。

## 0. 结论速查

| 区域 | 协调器 | 候选池 | DesiredCount | 同区距离 | base（与 seed 无关） | 状态 |
|---|---|---:|---:|---:|---:|---|
| 1 | `MT03_FirstDoor_Target` | 19 | 4 | 1000 | `1743173840` | ✅ 闭环 |
| 2 | `MT03_SecondDoor_Target` | 13 | 4 | 1000 | `2142285531` | ⚠ 抽取闭环、排除集未闭环 |
| 3 | `MT03_ThirdDoor_Target` | 15 | 4 | 1000 | `1639930988` | ✅ 闭环 |
| 4 | `MT03_EscapeGate_Target` | 12 | 3（1P 档 4） | 800 | `2183421141` | ❌ 实测记录不全 |

- `base = crc32_fname("Objective Actors") + GetSeed(协调器名)`，只由盐名与协调器名决定。
- **seed 只通过 `level_seed % 1000` 进入 `RandSeeded`**；它决定每次抽取的 `idx`，以及轨道相位。
- 靶子本身是 `FunParkCanal_Drop_DamageableButton_BP_LeftCanal_C` ×59，1:1 挂在 `TranslationMovable_BP_C` 上沿轨道滑动；"点位"= 静态初始坐标 + 轨道两端 + 运行期相位位置。

## 1. 数据来源

| 类别 | 文件 | 内容 |
|---|---|---|
| 关卡实例 | `pak/Maps/FunParkBarn/FPB_MT03_B00.json` | 59 靶、59 移动件、4 个 `RBSimpleObjectiveCoordinator` 实例（`ObjectiveActors[]`、setup） |
| 关卡脚本 | `pak/Maps_cpp/FunParkBarn/FPB_MT03_B00.cpp` | 只引用 4 个协调器与门计数变量，无随机化逻辑 |
| 候选/坐标/经验参数 | `opp_seed/data/fpb_mt03.json` | 4 区 `coords`、`force`、`exclude`、`count`、`dist`、`z_tol=105`、盐名 |
| 推理实现 | `opp_seed/seed.py:635-825` | `_fpb_draw`、`_fpb_purge`、`_fpb_phase_pos`、`FPB_MT03_TRACKS` |
| 原语 | `opp_seed/seedcore.py` | `crc32_fname` / `seed_chain` / `rand_seeded` |
| 实测 | `opp_seed/test.txt:477-536` | 249249 / 520520 / 317317 三样本 |
| 函数索引 | `opp_seed/FUNC_INDEX.md:48-60,73-87,227,258-277,357-369` | 反编译函数与 setup 布局 |
| UI 几何 | `opp_seed/ui/data/points/FPB_MT03.json`、`ui/ZONES.md:73` | 59 点坐标 / A–D 四区（一层·二层 × 东·西），**不含任何 seed 映射字段** |

⚠ `seed.py:124,641` 与 `data/fpb_mt03.json:4` 引用的 `release/coop/FPB_MT03/FPB_MT03.md`、`FPB_MT03_SEED.md` 在本工作区不存在。

## 2. 取证链（IDA + pak）

```text
pak: FPB_MT03_B00.json
  → 4 × RBSimpleObjectiveCoordinator，bUseObjectiveActorsRandomization=true
  → ObjectiveActors[] 显式候选表（19 / 13 / 15 / 12）
  → PrimaryActorsRandomizationSetup:
       DesiredCount=4/4/4/3；bOverrideDistanceBetweenSameObjectives=true；
       DistanceBetweenSameObjectives=1000/1000/1000/800
       （没有 Different 字段 → 跨协调器半径 R 走全局默认）

IDA: sub_1402AE7F0（coord+1346 门控入口）
  → sub_1402AF490（FSoftObjectPath → AActor*，不排序）
  → sub_1402B05C0（通用抽取引擎, 0x22F2）
       line 426   sub_1402B46B0   名字典序升序
       line 429-433 R = setup+1208? sub_1419BEF00(setup+1216) : sub_1433AACD0（全局默认）
                     缓存到 setup+1628
       line 689-691 sub_1402B4CA0(排除表, coord, setup+1002, 0, &池, R, 200.0, 0)
       line 950    v246 = 组数 + sub_140503B80(coord, 0)   ← GetSeed
       line 1694   setup+1625 = 1（抽取完成标志）
  → RandSeeded(sub_1402D29E0) + RemoveAtSwap(sub_1402B28C0)
    + sub_1402B3C30（距离剔除）
```

### 跨协调器排除趟（区域 2 的关键）

| 函数 | 证据 | 结论 |
|---|---|---|
| `sub_1402B4CA0` | line 97–103 | `a3 = setup+1002` 决定 v79 来源：`1` → `sub_140695380` 全局收集；`0` → 协调器 vtable+1768（`sub_1406954E0`） |
| 同上 | line 275–296 | 候选位置取 `RBObjectiveActorComponent +320` 指针的 `+480`（`__m128`），即**运行期世界位置** |
| 同上 | line 306 | `sub_141D1E3B0(v79, …, 位置, …, 半径参数, &输出)` 找半径 R 内最近目标，命中即 swap 移出池 |
| `sub_1406957D0` | line 38–51 | 仅当 `setup+1625==1` 才把 `setup+1632` 的已选数组并入 v79；抽取前该位被 `sub_1402B05C0` line 266 清零 |
| 同上 | line 56–67 | vtable+1752（`sub_140B0A0F0`）按类收集世界 objective actor，过滤含 `helper+216`、`RBRandomizable vtbl+544` 谓词 |
| `sub_1405D4E10` | FUNC_INDEX:73 | 组件构造 6336B，`WORD@+572` 决定位置源；`+480` 为运行期位置缓存 |
| `sub_141D1E3B0` | line 1076 | 同样从 `+480` 读 `__m128` 位置 |
| `sub_1433AACD0` | 全文 | 全局默认距离：从 `sub_141DA96D0()+4092/+4104` 或 `sub_1402E1DA0()+952/+964` 取 float |

即：**排除集 = f(v79 列表内容, 每个靶的运行期 `+480` 位置, R)**，两者都不是 pak 里的静态量。

## 3. 与 seed 无关的静态输入

| 项 | 值 |
|---|---|
| 盐名 | `"Objective Actors"`，`crc32_fname = 1040402497 = 0x3E034841` |
| `GetSeed` | `seed_chain(['PersistentLevel', 协调器名])`：`|crc32_fname(name) + 外层 seed|`（`sub_140503B80`） |
| `RandSeeded` | splitmix 双盐混合 → `(uint16) % N`，盐 = `level_seed % 1000`；`seed==0` 退化 `rand()` |
| 名字序 | `sub_1402B46B0`，大小写不敏感字典序 |
| Z 容差 | `z_tol = 105`（`sub_1402B3C30` 剔除条件：水平 < `dist` 且 `|ΔZ| <= 105`） |
| force | 区域1 `FirstGate-01, -25`；区域2 `SecondGate-13`（分类趟必选，尾→头 swap 删除） |
| 轨道 | 59 台 `TranslationMovable_BP_C`；`MovementTime=5`、`RandomTargetIdleRatio=0.5`、`RandomTargetSubdivisionCount=10`（`pak/LD/Movables/TranslationMovable_BP.cpp`） |
| 相位 | `p = 2*RandSeeded(-1+k, N/2+1, seed)`（k 偶时 +1），`pos = A + (B-A)*p/(N+1)`；`sub_1435FEB20/2E0/D70` |

`opp_seed/seed.py:682-717` 的 `FPB_MT03_TRACKS` 收录轨道两端 `(A, B)`、同步类型 `R/C/N` 与细分档 `N`；`C/N` 类用端点 A，`R` 类才按相位算。

## 4. 抽取算法（`seed.py:762-797` 复刻）

```text
pool    = sorted(区域 coords, key=str.lower)
picked  = 尾→头分类趟：force 移入结果；随后 sub_1402B4CA0 排除趟移出（区域2 用经验 exclude 代替）
result  = picked
base    = crc32_fname("Objective Actors") + seed_chain(['PersistentLevel', coord])
for name in picked:
    purge(pool, coords[name], dist=1000, dz=105)        # 必选先各剔除一轮近邻
while pool and quota > 0:
    idx   = RandSeeded(base + len(result), |pool|, level_seed % 1000)
    pick  = pool[idx]; pool[idx] = pool[-1]; pool.pop()  # RemoveAtSwap
    result.append(pick); quota -= 1
    purge(pool, coords[pick], dist, dz)                  # 从后向前、末尾交换删除
```

`purge` 对应 `sub_1402B3C30`；删除语义必须是 **swap**，写成保序删除会整体错位。

## 5. 实测与复现

### 5.1 三个样本（`test.txt`）

| seed | 区域1 | 区域2 | 区域3 | 区域4 |
|---:|---|---|---|---|
| 249249 | `25, 01, 5, 4` | `13, 8, 6, 16` | `8, 26, 4, 12` | `20, 22`（仅 2 个，记录不全） |
| 520520 | `25, 6, 01, 4` | `17, 15, 13, 8` | `8, 9, 14, 30` | `25, 24, 18` |
| 317317 | — | `11, 5, 13, 4` | — | — |

### 5.2 seed=249249 逐抽 trace

| 区域 | base | 抽次 | seed | N | idx | 选中 |
|---|---:|---:|---:|---:|---:|---|
| 1 | 1743173840 | 0 | 1743173842 | 11 | 3 | `FirstGate-4` |
| 1 | | 1 | 1743173843 | 7 | 9 | `FirstGate-5` |
| 2 | 2142285531 | 0 | 2142285532 | 7 | 0 | `SecondGate-6` |
| 2 | | 1 | 2142285533 | 6 | 3 | `SecondGate-8` |
| 2 | | 2 | 2142285534 | 3 | 3 | `SecondGate-16` |
| 3 | 1639930988 | 0 | 1639930988 | 13 | 10 | `ThirdGate-4` |
| 3 | | 1 | 1639930989 | 11 | 8 | `ThirdGate-8` |
| 3 | | 2 | 1639930990 | 9 | 3 | `ThirdGate-26` |
| 3 | | 3 | 1639930991 | 7 | 1 | `ThirdGate-12` |

区域 1 补上 force `01/25`、区域 2 补上 force `13` 后，与 `test.txt` 完全一致（8/8 逐靶）。区域 3 无 force，4 次抽完即 4/4。

### 5.3 520520

区域1：`#0 seed=1743173842 N=12 idx=11 → -6`、`#1 …843 N=10 idx=3 → -4` + force `01/25` ⇒ 4/4。
区域3：`…988 N=13 idx=8 → -30`、`…989 N=11 idx=10 → -8`、`…990 N=7 idx=2 → -14`、`…991 N=5 idx=4 → -9` ⇒ 4/4。

复现命令：`python seed.py FPB_MT03 249249 --trace`（`seed.py` 只输出区域 1/3）。

## 6. 区域 2 的未闭环点

### 6.1 定量证据

`data/fpb_mt03.json` 的 `exclude = {SG-10, SG-18, SG-4}` 是 249249/520520 两样本联合唯一解的经验定标：

| seed | 用经验 exclude | 不用 exclude | 实测命中 |
|---:|---|---|---:|
| 249249 | `13, 6, 8, 16` **4/4** | `13, 4, 8, 18` 2/4 | `13, 8, 6, 16` |
| 520520 | `13, 17, 15, 8` **4/4** | `13, 4, 12, 18` 1/4 | `17, 15, 13, 8` |
| 317317 | `13, 3, 6, 12` **1/4** | `13, 3, 6, 10` 1/4 | `11, 5, 13, 4` |

317317 实测选中了被经验排除的 `SG-4`，直接证伪排除集的普适性 → **排除集 seed 依赖**。注意三行 `base` 完全相同（2142285531），所以差异**不在抽取公式，只在排除趟**。

### 6.2 静态几何假设的证伪

按"区域 1/3/4 已选目标"计算每个 SecondGate 候选的最小 3D 距离（249249）：

| 候选 | 最近距离 | 最近目标 | 经验 exclude |
|---|---:|---|---|
| `SG-18` | 432.1 | `FG-4` | ✅ |
| `SG-16` | 495.9 | `FG-4` | ❌ 保留 |
| `SG-8` | 523.3 | `TG-12` | ❌ 保留 |
| `SG-4` | 534.2 | `TG-8` | ✅ |
| `SG-10` | 694.6 | `FG-01` | ✅ |
| `SG-17` | 807.0 | `FG-01` | ❌ 保留 |
| `SG-3` | 902.0 | `TG-8` | ❌ 保留 |

520520 的前几项几乎一致（18=432.1、16=495.9、4=534.2、10=694.6）。被排除的三项并不构成"距离最小的三个"，`SG-16`/`SG-8` 更近却保留 → 排除集不是简单的"离已选目标太近"静态几何阈值。这也解释了 `data/fpb_mt03.json:4` 所述"三样本检验否定根坐标/轨道代理全部静态几何假设"。

### 6.3 根因

- v79 列表由 `sub_1406957D0` 动态刷新，其世界 actor 过滤谓词（`helper+216`、`RBRandomizable vtbl+544`）依赖其它协调器的随机状态（seed 驱动）；
- `+480` 是**运行期世界位置**，靶沿轨道滑动，位置由 seed 决定的相位和周期 `k` 决定；
- `sub_141D1E3B0` 只排除"在 v79 里找得到半径 R 内最近目标"的候选，因此排除集随 v79 与运行期位置变化。

**结论**：区域 2 的 `base`、抽取顺序、距离剔除都已闭环；唯一缺的是排除趟的两个运行期输入。

## 7. 区域 4 与口径冲突

- `MT03_EscapeGate_Target`：`DesiredCount.DefaultValues=3`、`Values1P=4`、`DistanceBetweenSameObjectives=800`，池 12 个 `ThirdGate-*`。`test.txt` 249249 只记 2 个靶、520520 记 3 个，样本不足以闭环；`seed.py:123` 标 `partial=True`。
- 口径冲突：`FUNC_INDEX.md:7-8` 称"并入 FPB_MT03 闭环（三区域 6/6）"，而 `seed.py:639-641`、`data/fpb_mt03.json:4` 明确"区域 2/4 未闭环"；`FUNC_INDEX.md` 引用的 `§5.14` 正文缺失（文件止于第 13 条）。**以代码与数据文件为准。**
- 类 CDO 的 `RandomSeed`（LeftCanal `2083139261`、RightCanal `1543793506`、Child `1516456114` 等）与 `GetSeed`/`RandSeeded` 关卡种子体系的关系**未取证**，勿套用（见 `../class/FunParkCanal_Drop_DamageableButton_BP_RightCanal.md:6`）。

## 8. 待办 / 突破方向

1. 在随机化时刻 dump 每个靶 `RBObjectiveActorComponent +480` 的世界坐标与 v79 列表（IDA 断点 / 运行时脚本）——唯一缺失的输入；
2. 补 317317 的区域 1/3/4 实测，反推排除集随 seed 的变化规律；
3. 按四个协调器实际执行顺序模拟：`setup+1625` 完成标志、`helper+216` / `RBRandomizable vtbl+544` 过滤、`sub_140695380` 全局收集分支（`setup+1002`）；
4. 用 `seed.py:_fpb_phase_pos()` 确定运行期周期 `k`，把轨道相位代入位置，替代静态初始坐标；
5. 闭环后同步修正 `FUNC_INDEX.md` 的"三区域 6/6"表述并补齐 `§5.14`，再把 `seed.py:FPB_MT03_AREAS` 扩到 4 区。

## 9. 校验锚点

| 校验 | 期望 |
|---|---|
| `crc32_fname("PersistentLevel")` | `0x4C09CC22` |
| `crc32_fname("Objective Actors")` | `0x3E034841` |
| 区域1/2/3/4 base | `1743173840` / `2142285531` / `1639930988` / `2183421141` |
| `python seed.py FPB_MT03 249249` | 区域1 `01,4,5,25`；区域3 `4,8,12,26` |
| `python seed.py FPB_MT03 520520` | 区域1 `01,4,6,25`；区域3 `8,9,14,30` |
| 区域2（用经验 exclude） | 249249 `13,6,8,16`；520520 `13,17,15,8`；317317 **不闭环** |

`seed.py --selftest` 的 150/150 不含 FPB_MT03 区域 2/4；本文的复现结果由独立脚本对 `_fpb_draw()` 直接调用得到，未改动交付脚本。
