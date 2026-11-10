# seed 能否正向确定火桶位置

> 结论型文档，串起本目录三篇：
> `RBSecondaryBurningBarrelsObjectiveCoordinator.md`（协调器 / CDO 配置）、
> `RBVariatorAction_ReplaceForBurningBarrels.md`（按 Tag 收集 / 属性 / vtable）、本文（判定与下一步）。
> 通用取证方法见 `FORENSICS_METHODS.md`，通用种子公式见 `opp_seed/SEED_FORMULAS.md` 与 `FUNC_INDEX.md`；
> 地图工具侧的静态候选点口径见 `ui/README.md` §9。
> **状态：静态取证已做到"算法形状闭环"，尚无可用预测公式，也无实测样本闭环。**

## 0. 判定

| 问题 | 判定 | 依据等级 |
|---|---|---|
| seed 是否参与火桶抽取 | **是** | 实测：`RandSeeded` 调用点 + 唯一常数 |
| 仅凭 seed 能否确定位置 | **不能** | 实测：多处运行时输入（§3） |
| 给定完整输入能否复现 | **理论可以** | 推断：全链路确定性、服务端统一计算 |
| 现在能否给出 seed→坐标公式 | **不能** | base 来源 / 池顺序 / 预筛阈值未闭环 |
| 地图工具里的 579 个点是不是本局火桶 | **不是**，是静态候选全集 | `ui/data/variator_points/PSB_MT01.json` |

## 1. seed 参与的证据（实测）

`sub_1437E6510`（通用 Populate 状态机，size `0x2739`）的 case 21：

```text
idx = RandSeeded(*((_DWORD *)a1 + 180) + 65464321, |pool|)
         = sub_1402D29E0(*(a1+720) + 0x3E6E801, 池长)
```

- `0x1437E767F` 是 `.text` 里唯一把 `65464321` 当立即数的位置（另一处 `0x14345B724`
  是无关函数里的巧合数据）。该常数不属于 `SEED_FORMULAS.md` 里任何已知 `L` 值。
- `RandSeeded` = `sub_1402D29E0`（`FUNC_INDEX.md:66`）：splitmix 双盐混合取 `(uint16) % N`，
  **盐 = 全局 `dword_146E2E5C4 % 1000 = level_seed % 1000`**。
  注意：盐不是显式第三个实参；`SEED_FORMULAS.md:12` 写成 `RandSeeded(seed_arg, |池|, level_seed%1000)`
  是概念形式，Hex-Rays 在此只显示 2 个实参。
- `GetSeed(obj)` = `sub_140503B80`（沿 Outer 链递归 `|crc32(FName) + GetSeed(Outer)|`），
  `crc32_fname` = `sub_141CBDC30`（`FUNC_INDEX.md:72/108`）。
- 火桶枚举 `InitialServer` / `InitialClient` ⇒ **服务端算完复制结果**，客户端不独立重算。

**未闭环**：`*(a1+720)` 这个 seed 字段的初始化点尚未定位，所以 `base` 是
`GetSeed(?) + crc32(盐名?)` 中的哪一项还不确定。

## 2. 全链路（正向）

```text
Variator Active: BurningBarrelSecondaryObjective            ← OPP.log
  → URBVariatorAction_ReplaceForBurningBarrels / InitialServer
  → TActorIterator(ReplacedActorClass) 遍历 World actor
  → AActor::Tags(+384/+392) + 管理器 Tag 登记校验
  → 随机预筛（"gathered by random"）
  → Required/Denied Tag 判定（VariatorReplaceActorStruct +0x60/+0x70/+0x78）
  → AddUnique 入候选池（+648）
  → 补 BlockedActor（管理器 +208/+224）
  → 多维邻近过滤：热源 1500、冻结区、隐藏点、路点、门、楼梯、容器、目标、AI 刷怪点
  → 名字序 introsort（case 19）
  → FIntByDifficulty 按人数取数量（case 21；1P=2 / 2P=4）
  → idx = RandSeeded(*(a1+720) + 65464321, |pool|) → 移除 → 替换成火桶
  → InitialClient / Done
```

CDO 数值（`BurningBarrel_Secondary_ObjCoordBP.json`）：`NumberToSpawn = 8`、
`bUseFixedMaxCount = true`（Default 4 / 1P 2 / 2P 4）、`MinDistance2D = 1000`、
`MinDistance2DBetweenHeatSources = 1500`、`ReplaceRequiredTags = ["RoomForBarrelInteraction","RoomForBarrel"]`。

`seed=781781` 那局（`PSB_MT01`、1P、`programCREATOR`/Normal）日志出现至少 6 个
`BurningBarrel_SecondaryObjective_BP_C_*` 实例，与"预生成 8 个候选 / 同时激活 2 个"相容；
**日志不打印坐标**。

## 3. 为什么只给 seed 不够

| 输入 | 来源 | 静态可得 | 说明 |
|---|---|---|---|
| 关卡 / 地图 | `GameStageInfo` 的 Trial ID | 是 | 决定候选池的全集 |
| seed | `GameStageInfo` / `StageReady` | 是 | 经 `RandSeeded` 内部全局盐进入 |
| 完整变数列表 | `Variator Active` 逐行 | 是（日志） | 冻结区、热源、隐藏点封闭等由其它变数产生 |
| 人数 | `EffectiveNumberOfPlayers` | 是（日志） | `FixedMaxCount` 分档 |
| **候选池迭代序** | `TActorIterator` / World actor 列表 | **否** | 关卡加载顺序 + 动态生成/销毁，不是 pak JSON 数组序 |
| **随机预筛** | `sub_143504F80`（`< 0.99989998`） | **否** | 阈值/比例来源未定位，池在 Tag 判定前已被 RNG 改过 |
| **Tag 登记 / BlockedActor** | 全局管理器 `+208`/`+224` | **否** | 由其它变数与系统运行时填充 |
| **接口 / 组件有效性** | `CanBeReplaced`、随机化组件 `IsValid`、网络角色 | **否** | 依本局状态而变 |
| **其它动态对象** | 冻结区、热源、封闭隐藏点 | **否** | 例：带 ColdSnap 的局会改变火桶可用池 |
| **seed 字段 base** | `*(a1+720)` 初始化 | 未闭环 | `GetSeed` 链 / 盐名未知 |

只要有一项运行时量不同，`|pool|`、池顺序或过滤结果就不同 ⇒ 同一个 seed 可得不同落点。

## 4. 与已能预测关卡的差异

| | 通用 `ObjectiveActors` 链 | 火桶链 |
|---|---|---|
| 入口 | `sub_1402B05C0`（`RandomizeObjectiveActors`） | `sub_1437E6510`（`VariatorReplaceActors` 状态机） |
| 候选池 | 协调器里的**显式静态数组** `ObjectiveActors[]` | 运行时按 Tag 遍历 **World actor** |
| 排序 | `sub_1402B46B0` 名字典序 | `sub_14018C680` introsort（case 19） |
| 过滤 | 静态坐标 + 固定距离 | 热源 / 冻结区 / 隐藏点 / 路点等运行时量 |
| 抽取 | `RandSeeded(base + 已选数 + L, 剩余池)`，`RemoveAtSwap` | `RandSeeded(base + 65464321, 池长)`，`RemoveAt` 保序 |
| 闭环情况 | `SEED_FORMULAS.md` 有 24/24、12/12、6/6 等拟合 | 无样本、无公式 |

⇒ 火桶属于比 `FPB_MT03` 区域 2「排除集静态未闭环」更难的情形：**池本身是运行时量**。

## 5. 闭环状态清单

**已闭环（实测）**

- 类链：协调器 / 动作类 / 接口 / 枚举 / 配置结构体的 UClass、size、CDO、vfptr；
  火桶类 vtable slot 96 = `sub_1437E6510`。
- 配置：`VariatorReplaceActorStruct` 144B 字段偏移与 `sub_143504F80` 实参逐项吻合；
  CDO 的 Tag / 数量 / 距离参数来自解包资产。
- 收集链：`TActorIterator` → Tags → 管理器校验 → 随机预筛 → Required/Denied → AddUnique。
- 抽取：常数 `65464321` 与 `RandSeeded` 调用点唯一，盐 = `level_seed % 1000`。
- 静态候选全集：PSB_MT01 579 个火桶候选（151 可交互、492 可替换）、89 个隐藏点。

**未闭环（推断或缺失）**

- 火桶**专用**状态机函数（与 `sub_1437E6510` 同簇、带 HeatSource/FreezingZone 日志者）未单独钉死；
  "复用同一抽取尾部"是高置信推断，非实测。
- `*(a1+720)` base 的初始化、盐名。
- 随机预筛阈值来源（`sub_1417F12F0`）、管理器 Tag 表与 `+208`/`+224` 列表填充时机。
- `TActorIterator` 顺序与 World actor 列表的可复现性。
- 实测样本：同 seed 重复局的池大小与坐标对比。

## 6. 下一步取证顺序

1. 反编译 `0x1437E` / `0x1437F` / `0x14380` 簇中日志含 `HeatSourceProximity` / `FreezingZone`
   的函数，钉死火桶专用状态机与它的抽取常数。
2. 追 `sub_1437E6510` 中 `a1+720` 的初始化点，确认 `base = GetSeed(?) + crc32(盐名?)`。
3. 反编译 `sub_1417F12F0`（预筛比例）、`sub_14017E380` / `sub_143810F20`（管理器 Tag 查表）。
4. 实证：固定 seed / program / 变数 / 人数重复开两局，对比
   `GatherFromPossibleReplacement, %i availables` 的计数与火桶实例位置；
   再加 ColdSnap 或改人数观察池变化。日志无坐标 ⇒ 需 Frida hook `SpawnActor`
   或读 `RBHeatSourceComponent` 位置。
5. 有了 ≥2 组样本再拟合 `base` / `L`，才谈得上写进 `seed.py`。

## 7. 校验锚点（不依赖 IDA）

```text
off_145E21960 slot 96 = 0x1437E6510，slot 97 = 0
0x1437E767F = 唯一 65464321 立即数
0x145E20220+0x24 = 0x60；0x145E20358+0x24 = 0x78；0x145E20388+0x24 = 0x88
0x1466E54A6 / 0x1466735FA / 0x14665E0D8 / 0x1467FCB5A = 四个宽类名
```

```powershell
python -c "import struct,re; d=open('d:/workspace/outlast/TOTClient-Win64-Shipping.exe','rb').read(); pe=struct.unpack_from('<I',d,0x3c)[0]; ns=struct.unpack_from('<H',d,pe+6)[0]; osz=struct.unpack_from('<H',d,pe+20)[0]; secs=[struct.unpack_from('<IIII',d,pe+24+osz+40*i+8) for i in range(ns)]; f2v=lambda f: 0x140000000+next((v+(f-r) for vs,v,rs,r in secs if r<=f<r+rs),0); v2f=lambda va: next((r+(va-0x140000000-v) for vs,v,rs,r in secs if v<=va-0x140000000<v+rs),None); print('SLOT96',hex(struct.unpack_from('<Q',d,v2f(0x145E21960)+96*8)[0])); print('CONST',[hex(f2v(m.start())) for m in re.finditer(re.escape(struct.pack('<I',65464321)),d)])"
```

期望输出：`SLOT96 0x1437e6510`、`CONST ['0x14345b724', '0x1437e767f']`。

> PE 节表读取的易错点：节表项起始是 `e_lfanew + 24 + SizeOfOptionalHeader + 40*i`，
> 而 VirtualSize/VirtualAddress/SizeOfRawData/PointerToRawData 在**项内 +8**；
> 从 +0 读会把 8 字节节名当 DWORD，导致所有 VA 换算错误。
