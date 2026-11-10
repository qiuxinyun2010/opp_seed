# RBSecondaryBurningBarrelsObjectiveCoordinator

> 类专属锚点速查。通用取证方法（PE 节表映射、xrefs、`+0x24` 规则、IDA 勾选 Unicode）见 `FORENSICS_METHODS.md`。
> 本文对象 = 变数 `BurningBarrelSecondaryObjective` 的火桶次要目标协调器**原生基类**：
> `BurningBarrel_Secondary_ObjCoordBP_C` → **本类**（`/Script/OPP`）。
> **位置不由本类决定**：候选池构造、随机抽取与 actor 替换在 `URBVariatorAction_ReplaceForBurningBarrels`，
> 见 `RBVariatorAction_ReplaceForBurningBarrels.md`；seed 能否确定位置见 `BurningBarrel_SeedDeterminism.md`。
> 取证工具：`rea` 的 IDA adapter（`open_binary` 打开 `TOTClient-Win64-Shipping.exe`，`.i64` 不被 rea 接受）
> + 本地只读 PE 扫表（rea IDA adapter 无 `read_bytes`，并发请求还会打断 MCP stdio，故 vtable / 描述符表改用本地 `struct.unpack` 复现）。

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.RBSecondaryBurningBarrelsObjectiveCoordinator` |
| 二进制 | `TOTClient-Win64-Shipping.exe`（base `0x140000000`，`.text = 0x140001000–0x145065E2D`） |
| 蓝图资产 | `pak/OPP/Content/LD/Coordinators/Secondary/BurningBarrel_Secondary_ObjCoordBP.json`（CDO）、`LD_blueprint/.../*.cpp`（`SuperStruct`） |
| 类名宽串 | `0x1466E54A6` = `ARBSecondaryBurningBarrelsObjectiveCoordinator`；反射名 `0x1466E54A8` = `RBSecondaryBurningBarrelsObjectiveCoordinator`（同串 +2） |
| UClass 构造 | `sub_1408EAA10`，类大小 **7568**，对齐 `8`，flags `0x10000004`，静态缓存 `qword_146E81700` |
| CDO 构造 | thunk `sub_1427D5000` → `sub_1427D5010`；父类构造 `sub_1409CBC60`；初始化写到 `a1+7560 = -1.0f` |
| 主 vfptr | `&off_145A61FC0` |
| 次表 | `+560` = `off_145A62930`，`+568` = `off_145A62980` |
| 父类 vtable | `RBBaseObjectiveCoordinator` = `off_14594BE70`（293 槽） |
| 与父类 diff | **32 个覆写槽**（§3） |

## 1. 取证链

```text
PE 里按 UTF-16LE 搜 "ARBSecondaryBurningBarrelsObjectiveCoordinator"
  → 文件偏移换算（PE 节表 +8 起读 VirtualSize/VirtualAddress/SizeOfRawData/PointerToRawData）
  → 宽串 0x1466E54A6；反射名 = +2 = 0x1466E54A8
  → rea xrefs(0x1466E54A8) → sub_1408EAA10（UClass 惰性构造）
  → 反编译读 sub_14035AFB0 参数："/"、L"RBSecondaryBurningBarrelsObjectiveCoordinator"、
      &qword_146E81700、size 7568、align 8、flags 0x10000004、ClassConstructor
  → ClassConstructor thunk sub_1427D5000 → CDO 构造 sub_1427D5010
  → 函数体：*a1 = &off_145A61FC0
             a1+560 = off_145A62930
             a1+568 = off_145A62980
             a1+7560 = -1.0f
  → 本地展开 0x145A61FC0 连续 qword 段，与 off_14594BE70 逐槽 diff
```

```text
候选池口径（另一条链，与本文互补）：
  pak CDO 的 ReplaceRequiredTags = ["RoomForBarrelInteraction", "RoomForBarrel"]
  → PSB_MT01 全部带该 Tag 的静态 actor 坐标
  → ui/variatorpoints.py → ui/data/variator_points/PSB_MT01.json
```

## 2. CDO 配置（`BurningBarrel_Secondary_ObjCoordBP.json` 权威值）

| 属性 | 值 | 含义 / 注意 |
|---|---|---|
| `ObjectiveActorClasses` | `BurningBarrel_SecondaryObjective_BP_C` | **运行时动态生成**，静态关卡 JSON 里没有这些 actor |
| `ReplaceRequiredTags` | `["RoomForBarrelInteraction", "RoomForBarrel"]` | 候选 actor 的必备 Tag；地图工具据此提静态全集 |
| `Tags` | `["AllowBurningBarrelsInteraction"]` | 协调器自身 Tag |
| `ReplaceActorClasses` | `Base_PropagandaPoster_BP_C`、`RBInvestigationPoint`、`Placeable_PsychosisMine_BP_C`、`DeadBody_Container_*` 等 | 可被替换成火桶的静态 actor 类 |
| `ReplaceOffsets` / `SpecialReplaceOffsets` |  Transform 数组（`RBDoor` 等有专用偏移） | 替换后的位置/朝向微调 |
| `NumberToSpawn` | `8`（`NormalLocalValue`） | 预生成/候选规模 |
| `bUseFixedMaxCount` | `true` | 启用按人数分档 |
| `FixedMaxCount` | Default `4`；**1P `2`**、2P `4`（`bLocalOverrideFor1P/2P` = true） | 同时激活上限；人数是位置预测的第 3 个必要输入 |
| `MinDistance2D` | `1000.0` | 候选点之间最小 2D 距离 |
| `MinDistance2DBetweenHeatSources` | `1500.0` | 热源之间最小距离（对应 `FilterReplaceableListByHeatSourceProximity`） |
| `DistanceBetweenOtherSecondaryObjectives` | `500.0` | 与其它次要目标的距离 |
| `DistanceBetweenOtherMainObjectives` | `500.0` | 与主目标的距离 |
| `DistanceBetweenWaypoint2D` | `100.0` | 与路点的距离 |
| `DistanceBetweenLedges` / `SideDistanceBetweenLedges` | `150.0` / `50.0` | 台阶边缘排除 |
| `DistanceBetweenMonsterClosetForward` | `200.0` | 怪物柜前方排除 |
| `bAutoStartOnStageStarted` | `true` | 与日志 `StageStarted` 后状态机启动一致 |
| `ObjectiveLevelText` | `Extinguish Burning Barrels ({CURRENT}/{MAX})` | HUD 文本键 `ExtinguishBurningBarrelsSecondaryObjective` |
| `ObjectiveWidgetIcon` | `objective_burningbarrels` | 目标图标 |

**勿混**：同一 CDO 里还有一整套 `LargeObject*` 字段（`LargeObjectNumberToSpawn = 12`、
`LargeObjectReplaceRequiredTags = ["RoomForLargeWaterBottle", "GoodHeightForLargeWaterBottle"]`、
`LargeObjectMinDistance2D = 300`），属于另一条大物体/大型容器链，不是普通火桶的 Tag 口径。

## 3. vtable

主表 `off_145A61FC0`，与 `RBBaseObjectiveCoordinator`（`off_14594BE70`）逐槽 diff 得 32 个覆写槽：

| slot | 函数 | slot | 函数 |
|---:|---|---:|---|
| 0 | `0x143746FA0` | 262 | `0x14356C540` |
| 56 | `0x14373CB50` | 263 | `0x14373E8C0` |
| 75 | `0x143961090` | 270 | `0x14356C5C0` |
| 104 | `0x14373C310` | 271 | `0x14356C8E0` |
| 220 | `0x14340B4A0` | 277 | `0x14356C310` |
| 226 | `0x14373C590` | 289 | `0x14356CBC0` |
| 227 | `0x14373E890` | 290 | `0x143497790` |
| 248 | `0x14373CBE0` | 293 | `0x14269EC20` |
| 261 | `0x14373C5C0` | 294 | `0x14356CA20` |
| 295 | `0x14356CA50` | 296 | `0x14356CA80` |
| 297 | `0x14373C7C0` | 298 | `0x143738E70` |
| 299 | `0x14373C9E0` | 300 | `0x14373CAE0` |
| 302 | `0x142629270` | 303 | `0x1426325B0` |
| 304 | `0x140109C80` | 305 | `0x1433AAFC0` |
| 306 | `0x1433AAD80` | 307 | `0x1400011A0` |
| 308 | `0x143746FD0` | 309 | `0x1430126D0` |

- `0x14356Cxxx` 簇已抽样反编译：写 `v5+1824/1840/1984` 的 UI 文本字段、取子协调器，
  **不是**随机化/抽取逻辑。
- `0x14373Cxxx` / `0x14373Exxx` 簇属于父类链上的其它目标协调器覆写，不是火桶特有。
- 结论：**候选池构造与抽取不在本类 vtable**。它们在 `URBVariatorAction_ReplaceForBurningBarrels`
  的主 vfptr `off_145E21960` slot 96 = `sub_1437E6510`（见另一篇文档）。

## 4. 静态候选点（供地图工具使用）

`ui/data/variator_points/PSB_MT01.json`（由 `ui/variatorpoints.py` 离线提取）：

| 图层 | 数量 | 说明 |
|---|---:|---|
| `barrels` | **579** | 全部带 `RoomForBarrel*` Tag 的静态 actor；其中 `151` 带 `RoomForBarrelInteraction`，`492` 属于 `ReplaceActorClasses` |
| `hidespots` | **89** | `Hidespot*` / `PhoneBooth*` / `*Locker*` 类静态 actor |

`barrels` 类型 top：`PropagandaFlyer-02_BP_C` 242、`Placeable_PsychosisMine_BP_C` 158、
`RBInvestigationPoint` 65、`Hidespot_Locker_Base_BP_C` 25、`DeadBody_Container_01_BP_C` 24。

> 这是**静态全集 / 候选池**，不等于本局实际刷出的火桶。日志 `seed=781781`（1P、programCREATOR/Normal）
> 里出现至少 6 个 `BurningBarrel_SecondaryObjective_BP_C_*` 实例，与 `NumberToSpawn=8`、`FixedMaxCount(1P)=2`
> 的"预生成 + 分批激活"口径相容；日志本身不打印坐标。

## 5. 备注 / 校验

- `sub_1408EAA10` 参数里出现的 `ffxSetPrintMessageCallback` 是 IDA 对某个地址的错误命名，
  按其它 `RB*` 类文档的类比，该位置实为 UFUNCTION 注册回调，不要当成 FFX 相关功能。
- 本文**未**逐条展开本类的 7568 字节属性描述符表；若需要属性偏移，按 `FORENSICS_METHODS.md` §3.2
  （属性名 ASCII → xrefs → 描述符 `+0x24`）补表。CDO 数值取自解包蓝图资产，属权威配置。
- `ui/README.md` §9 记录了地图工具里"火桶点位 / 隐藏点"图层的开关、类型过滤与数据口径。

本地复现锚点（不依赖 IDA）：

```text
0x1466E54A6  = UTF-16LE "ARBSecondaryBurningBarrelsObjectiveCoordinator"
0x1466E54A8  = 反射名 "RBSecondaryBurningBarrelsObjectiveCoordinator"
off_145A61FC0 主 vfptr；off_145A62930 / off_145A62980 次表
sub_1427D5010 写到 a1+7560，与 sizeof = 7568 一致
```

校验：vtable diff 32 槽、`data/variator_points/PSB_MT01.json` 579/89/151/492 四项计数、CDO 字段均已复跑一致。
