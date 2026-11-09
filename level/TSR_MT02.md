# TSR_MT02 正向推理：seed → 本局可用的刻录机点位

> 输入 `level_seed`（+ 人数/难度），输出本局 **可用（StateA）** 的
> `LimitedUseCassetteConverter_BP_C` 点位：actor、坐标、所属 Lot 与被抽中的序号，
> 按抽取顺序排列。关卡里共 19 台，静态全表只作为 `data/tsr_mt02.json` 的输入；
> `predict()` / `view()` / `render()` 一律只返回本局可用的点位。
> 实现：`../seed.py` 的 `_predict_tsr_mt02()`，静态表：`../data/tsr_mt02.json`。

```bash
python seed.py TSR_MT02 726726
python seed.py TSR_MT02 726726 --trace          # 每轮候选池 / seed / idx
python seed.py TSR_MT02 726726 --json
python seed.py TSR_MT02 726726 --players 3 --difficulty hard
python seed.py --selftest                      # 含本关 3 条样本，166/166
```

关卡数据：`pak/OPP/Content/Maps_json/TelevisionStudioRooftop/TSR_LD_MT02_B00.json`
（`RBRandomManager_1`）；坐标：`ui/data/cache/TelevisionStudioRooftop.points.TSR_MT02.json`；
实测记录：`../test.txt` 第 546–567 行。

---

## 0. 结论先行

**base 不是 `GetSeed + crc32(盐名)`。** 本关走 `RBRandomManager` 的
`FRandomizationLot` 引擎，seed 基址直接来自关卡数据里的 `RandomizerId`，
加三个 `.text` 调用点立即数：

| 用途 | 表达式 | 出处 |
|---|---|---|
| 本批要抽几台 `K` | `Min + RandSeeded(RandomizerId + 345, Max − Min + 1, salt)` | `0x14019FBB6` → `sub_1401A0F00` |
| 第 `k` 次抽哪台 | `cand[RandSeeded(RandomizerId + k + 148, \|cand\|, salt)]` | `0x14019FF06` → `sub_1401A0F00` |
| 未选中机器的兜底状态 | `2 − RandBool(i + RandomizerId + 51946)` | `0x1401A068C` |

其中 `salt = level_seed % 1000`（`sub_1402D29E0` 里读 `dword_146E2E5C4 % 0x3E8`）。

之前几轮按样本反解 32 位 `base` 的路线全部作废，包括 `705218`、
`GetSeed("RBLedgeMarker146") + 90601` 等拟合值——它们只是「记录不完整 +
几何约束使输出空间极小」造成的巧合。

---

## 1. 取证链

工具：`rea` → provider `ida`（IDA MCP adapter / ida-pro-mcp 1.30.0，连正在运行的
IDA 9.3 + `TOTClient-Win64-Shipping.exe.i64`），基址 `0x140000000`。
`procedure_pseudo_code` 反编译、`xrefs`、`search_strings` 可用；
`read_bytes` / `list_segments` 该 provider 未声明，改用 PE 节表 + Python/capstone 直读。

```text
1  地图 JSON  → 19 台 LimitedUseCassetteConverter_BP_C（坐标）
              → 1 个 RBRandomManager_1，Properties.RandomLots（2 批）
2  类名宽串  ARBRandomManager @0x1466FDD9A
              → xref 0x1414A28DB（注册块 sub_1414A2170）
              → UClass 懒构造 sub_1401A0E40（类大小 824）
              → thunk sub_1409BB890 → CDO 构造 sub_1409BB8A0（写 vfptr）
              → 主 vftable off_1459A8690，205 槽
3  ASCII 属性名 → 描述符表 0x145D4EFA0–0x145D50560，+0x24 取偏移
4  UFunction 注册表 off_145D4FF60（sub_142A25DA0 → sub_14048DA90(UClass,&table,2)）
              BP_ForceRandomization → sub_14370BE30（把 PendingRandomStates@792 apply 到 actor）
              BP_Randomize          → 0x14370BE10（BlueprintImplementableEvent 通用 thunk）
5  vtable 槽位交叉筛选：找出同时访问 RandomLots@600/608、SoloPlayLot@648 的槽
              slot 201 = sub_1426325E0  ← Randomize 主入口
              slot 202 = sub_14370C710 / slot 203 = sub_14370CFD0（成员查询）
6  sub_1426325E0 遍历 RandomLots（步长 960 B），对每个 lot 调
              sub_14019F790(lot, manager, force)  ← 单批随机化核心
7  反编译 sub_14019F790 得到 §2 的三处立即数与候选池构造规则
8  用 3 条实测样本正向回归
```

### 1.1 属性偏移表

`RBRandomManager`（类大小 824，vftable `off_1459A8690`）：

| 属性 | 偏移 | 属性 | 偏移 |
|---|---:|---|---:|
| `bAutoRandomize` / `bQueueApplyState` 位域 | 560 | `DoorLots` (TArray) | 568 |
| `ExecutionOrder` | 562 | `RandomGroups` | 584 |
| `WorldPopulatingStep` | 563 | **`RandomLots`** | **600**（Num@608） |
| `RandomConditionalSetups` | 616 | `AISetups` | 632 |
| `SoloPlayLot`（1P 专用） | 648 | `RestrictedSections` | 664 |
| `RandomManagerRoot` | 680 | `OnRandomizationCompleted` | 688 |
| 已 apply 标志（byte） | 704 | `PendingRandomStates` | 792 |

`FRandomizationLot`（**960 B**，由 `sub_1426325E0` 的 `960LL * Num` 与
`sub_14370C710` 的 `960LL` 双重确认）：

| 属性 | 偏移 | 属性 | 偏移 |
|---|---:|---|---:|
| `LotName` | 0 | `ConditionalActors` (FSoftObjectPath) | 8 |
| `ConditionalActorSetup` | 48 | `RandomActors` (TArray, Data@56 Num@64) | 56 |
| `RandomActorClasses` | 72 | `RestrictedSections` | 88 |
| `bDontChangeIgnoredActors` | 104 | `BaseState` | 105 |
| `DesiredState` | 106 | `MinActivationRatio` | 112 |
| `MaxActivationRatio` | 312 | `MinActivationCount` | 512 |
| `MaxActivationCount` | 712 | `MinDistanceBetweenActors` (float) | 912 |
| `MinDistanceFromSAS` (float) | 916 | **`RandomizerId`** | **920** |
| `RandomActorsStates_Server` | 928（Num@936/940） | `RandomizedActors` | 944（Num@952） |

四个 `FInt/FloatByDifficulty` 各 200 B，112→312→512→712→912 间隔整齐。

### 1.2 关卡里的两批 Lot

| | Lot0 | Lot1 |
|---|---|---|
| 台数 | 18 | 1（`LimitedUseCassetteConverter_BP_2`） |
| `RandomizerId` | **50822** | **12888** |
| `MinActivationCount` | 3 | 1 |
| `MaxActivationCount` | 9 | 1 |
| `MinDistanceBetweenActors` | 2000 | 0 |
| `MinDistanceFromSAS` | 0 | 0 |
| `BaseState` / `DesiredState` | StateB / StateA | StateB / StateA |
| `bDontChangeIgnoredActors` | false | false |

`RBRandomManager_1` 只序列化了 6 项：`bQueueApplyState=false`、
`ExecutionOrder=UsePopulatingOrderInstead`、**`WorldPopulatingStep=Gates`**、
`RandomLots`、`RandomManagerRoot`、`RootComponent`；`SoloPlayLot@648` 走 CDO 默认（空）。

**Lot1 的 `Min=Max=1` 且池里只有一台 ⇒ `BP_2` 恒为 StateA，与 seed 完全无关**，
这就是用户说的「固定刷新的那台」。

---

## 2. 正向算法

### 2.1 人数 / 难度如何参与（`sub_1404FF400`）

```text
v5 = *(sub_141D2A240() + 628)          // EffectiveNumberOfPlayers
a1[49..51] = Values1P/2P/3P 是否有任一难度 override（运行时缓存）

if 三张人数表都无 override → 返回 DefaultValues 的当前难度值 @68
else 按 v5 选 Values1P @104 / Values2P @140 / Values3P @176
表内：该难度 bOverrideXxxLocalValue=false → 回落 NormalLocalValue
```

本关 `bLocalOverrideFor1P/2P/3P` 全 `false`，`DefaultValues` 里只有
`bOverrideNormalLocalValue=true`（3/9 与 1/1），其余难度 override 全 `false`
⇒ **任何 (人数, 难度) 组合都取 3/9 与 1/1**。人数/难度机制存在于代码里，
但这张关卡表没有分档覆盖，所以只影响 `K` 的取值区间，不改变本关结果。

另有 `sub_1402BF7F0`（别的系统用）的 K 公式：
`K = Min + RandSeeded(seed_arg, Max−Min+1, salt)`，ratio 分支为
`round(count × ratio)`；其调用点 `0x140289EC8` 用 `GetSeed(obj) + 0x8493(33939)`。
**本关不经过它**，`sub_14019F790` 直接调 `sub_1401A0F00`。

### 2.2 单批抽取（`sub_14019F790`）

```text
R    = lot.RandomizerId
Min  = FIntByDifficulty(lot.MinActivationCount, players, difficulty)
Max  = FIntByDifficulty(lot.MaxActivationCount, players, difficulty)
K    = Min + RandSeeded(R + 345, Max − Min + 1, salt)      // sub_1401A0F00

for k = 0 .. K-1:
    cand = [ i for i in 0..N-1 按索引升序
             if i 未选中
             and actor[i] 实现 RBRandomizable 且未被其它系统占用
             and ∀已选 j: |P_i − P_j|² ≥ MinDistanceBetweenActors²
             and ∀SAS p:  |P_i − p|²  ≥ MinDistanceFromSAS² ]
    if cand 为空: break
    p = cand[ RandSeeded(R + k + 148, len(cand), salt) ]
    state[p] = DesiredState (StateA)

state[未选 i] = BaseState
if BaseState == NotApplicable(0):      // 本关不走
    state[i] = 2 − RandBool(i + R + 51946)
```

`sub_1401A0F00(seed, lo, hi) = lo + RandSeeded(seed, hi−lo+1, salt)`；
`RandSeeded(seed, N) = (mix64(seed, level_seed%1000) & 0xFFFF) % N`。

### 2.3 三个容易踩错的点

1. **池顺序 = 关卡 actor 加载顺序（全名字典序）**
   `BP10_36, BP11_39, …, BP19_17, BP2_5, BP3_8, …, BP9_29`，
   由 `sub_1401A1260` 解析 `RandomActors` 的 soft path 填进
   `RandomizedActors@944` 时按名字序得到。
   **不是**关卡 JSON 里 `RandomActors` 的数组序（BP2_5 … BP14）。
   用数组序模拟三条样本全部不符；用加载序三条全中。
2. **每轮重建候选、只排除已选**：不是 `RemoveAtSwap`，也不是「从池里删掉近邻」。
   候选始终按原索引升序；距离是 **3D 欧氏距离平方**，只与「已选中的」比较。
   `MinDistanceFromSAS=0` 时 SAS 过滤整段跳过。
3. **几何封顶**：K 由 seed 决定（本关 3..9），但 2000 距离约束使候选池在
   第 6 次抽取后必空，实际选中台数稳定为 **6 台 Lot0 + 1 台固定 = 7 台**。
   三个观测集合内部最小距离 2009 / 2293 / 2009 也都 ≥ 2000。

`bDontChangeIgnoredActors=false` ⇒ 不会写出 state=3 的「忽略」状态。
`BaseState=StateB`（非 NotApplicable）⇒ 未选中机器恒为 StateB，
`RandBool(…+51946)` 兜底在本关不触发。

---

## 3. 实测回归

记录只覆盖部分机器（`test.txt` 546–567），所以判据是 `observed ⊆ 正向可用集`。

| seed | K | 正向可用集（Lot0 抽取顺序，末尾 + 固定 BP_2） | 记录里缺的 |
|---|---:|---|---|
| 726726 | 6 | `BP9_29, BP2_5, BP18_14, BP7_23, BP6_20, BP15_5, BP_2` | `BP2_5` |
| 177177 | 7 | `BP17_11, BP10_36, BP13_45, BP6_20, BP11_39, BP9_29, BP_2` | `BP6_20`（另漏写 `BP_2`） |
| 7007 | 8 | `BP13_45, BP7_23, BP9_29, BP15_5, BP18_14, BP6_20, BP_2` | `BP9_29` |

`--trace` 的候选池大小（726726）：`18 → 16 → 10 → 6 → 3 → 2`；
177177 的 K=7、7007 的 K=8 都在第 7 次因候选池空而停止。

另验证 `726726 ≡ 1726 (mod 1000)` 结果完全一致（`salt` 等价类）。
`--selftest` 同时锁定「可用集 == 预期」「observed ⊆ 可用集」、
「`predict()['converters']` 与 `view()['points']` 都不夹带不可用点位」
以及 `BP_2` 必在可用集里；
当前全库 166/166 通过。

CLI / `--json` 只列本局可用点位（726726 共 7 台，按抽取顺序）：

```text
TSR_MT02  seed=726726  1P  easy  salt=726
  可用刻录机：BP9_29 BP2_5 BP18_14 BP7_23 BP6_20 BP15_5 BP_2
  [Lot0] K=6 实选=6 距离阈值=2000
  [Lot1] K=1 实选=1 距离阈值=0
  刻录机(*=固定)        坐标 (x, y, z)               批次     顺序
  BP9_29           (  3422.7,    -2303,    550)   Lot0   第1抽
  BP2_5            (  -851.9,     1998,  799.7)   Lot0   第2抽
  BP18_14          (   -1297,    -2458,     21)   Lot0   第3抽
  BP7_23           (    3183,      587,    550)   Lot0   第4抽
  BP6_20           (    2467,     3324,    550)   Lot0   第5抽
  BP15_5           (     523,    -1607,      6)   Lot0   第6抽
  BP_2*            (  1998.4,   2445.3,    900)   Lot1   第1抽
```

---

## 4. 代码位置索引

| 地址 | 作用 |
|---|---|
| `0x1459A8690` | `RBRandomManager` 主 vftable（205 槽） |
| `0x1426325E0` | slot 201 `Randomize`：遍历 5 类批次，`960LL*Num` 走 `RandomLots@600` |
| `0x14019F790` | 单批 Lot 随机化核心（三处 seed 常数 + 候选池 + 状态写入） |
| `0x14019FBB6` | `RandomizerId + 345` → K |
| `0x14019FF06` | `RandomizerId + k + 148` → 抽取 idx |
| `0x1401A068C` | `i + RandomizerId + 51946` → `RandBool` 兜底 |
| `0x1401A0F00` | `RandSeededRange(seed, lo, hi)` |
| `0x1402D29E0` | `RandSeeded(seed, N)`，salt = `dword_146E2E5C4 % 1000` |
| `0x1404FF400` | `FIntByDifficulty::Get`（按人数表 + 难度 override） |
| `0x140503B80` | `GetSeed`（本关主链路不用） |
| `0x1402B2930` | `PrepareState(actor, state==1, manager)` |
| `0x14370BE30` | `BP_ForceRandomization` 实现：apply `PendingRandomStates@792` |
| `0x145D4FF60` | UFunction 注册表（`BP_ForceRandomization` / `BP_Randomize`） |
| `0x146E2E5C4` | 全局关卡种子（86 处 RIP 引用全为读，无人数/难度叠加） |

## 5. 尚未覆盖 / 备注

- 难度、人数对其它关卡的分档覆盖（`Values1P/2P/3P`、四档 override）没有实测样本；
  `data/tsr_mt02.json` 的 `overrides` 字段与 `_tsr_mt02_count()` 已按
  `sub_1404FF400` 的语义留好接口，其它关卡可直接复用。
- `MinDistanceFromSAS > 0` 时的 SAS 点集（`sub_1402C5780` / `sub_141D40CC0`）
  本关用不到，代码里留了注释但没实现过滤。
- 录像带容器 `SatelliteCassetteContainer`、播出目标、结束键等点位由其它协调器负责，
  不在本关输出范围（见 `ui/data/points/TSR_MT02.json` 的 `_ignored_point_types`）。
- `ARBCassetteConvertObjectiveCoordinator`（蓝图父类 `SatelliteConvert_ObjCoord_BP_C`）
  只管覆写任务逻辑，**不决定刻录机点位**；其类大小 22592、vftable
  `off_1459989D0`（300 槽）在早期分析里已记录，别与 `RBRandomManager` 混用。
