# RBVariatorAction_ReplaceForBurningBarrels（按 Tag 收集可替换 actor）

> 类专属锚点速查。通用取证方法见 `FORENSICS_METHODS.md`；协调器侧见 `RBSecondaryBurningBarrelsObjectiveCoordinator.md`；
> 结论侧见 `BurningBarrel_SeedDeterminism.md`。
> 本文对象 = 变数 `BurningBarrelSecondaryObjective` 真正决定**火桶落点**的变数动作类，
> 以及它继承的通用替换状态机 `URBVariatorAction_ReplaceActors`。
> 核心结论：**"按 Tag 收集"不是读静态点位表**，而是运行时 `TActorIterator` 遍历世界 actor、
> 读 `AActor::Tags`、到变数管理器校验 Tag、先随机预筛、再用接口/组件判有效性、`AddUnique` 入池。
> 取证工具：`rea` 的 IDA adapter（反编译 / xrefs / 字符串表）+ 本地只读 PE 扫表（vtable、描述符表、字符串）。

## 0. 类锚点

| 项 | 值 |
|---|---|
| 通用类 | `URBVariatorAction_ReplaceActors`；宽串 `0x14665E0D8`，反射名 `0x14665E0DA` |
| 通用类 UClass 构造 | `sub_140B57000` / `sub_1427CFCC0`（同名 StaticClass getter），size **928**，静态缓存 `qword_146E8E908`，父类 `sub_1402ED700` |
| 通用类 CDO | `sub_140B57100`（只调用 `sub_1408224A0`，**不写自己的 vfptr**） |
| 火桶类 | `URBVariatorAction_ReplaceForBurningBarrels`；宽串 `0x1466735FA`，反射名 `0x1466735FC` |
| 火桶类 UClass 构造 | `sub_1408EC450`，size **936**（仅比父类多 8 字节），静态缓存 `qword_146E8E948`，父类 UClass 构造 = `sub_140B57000` ⇒ **确认直接继承** |
| 火桶类 CDO | `sub_140B57110`：vfptr `off_145E21960`，`a1+928 = 0`（`PopulateStep = None`） |
| 接口 | `URBReplacedActorInterface`；宽串 `0x1467FCB5A`，反射名 `0x1467FCB5C`；StaticClass `sub_140896060`（size 40，flags `0x10010101`，缓存 `qword_146E7ECA8`，UFUNCTION 注册器 `sub_1426E7020`） |
| 配置结构体 | `VariatorReplaceActorStruct`（ASCII 名 `0x1464B5A73`，xref `0x145E20438`）；**size `0x90` = 144 字节/项** |
| 枚举 | `EVariatorReplaceActorsPopulateStep`（表 `0x145E20000` 起）、`EVariatorReplaceForBurningBarrelsPopulateStep`（`0x1465071A0`） |
| 状态机主函数 | `sub_1437E6510`（size `0x2739`），switch 1..21+；火桶类 vtable **slot 96** |
| 抽取常数 | `65464321 = 0x3E6E801`，在 `.text` 仅 `0x1437E767F` 一处作为 `RandSeeded` 立即数（`0x14345B724` 的另一处是无关函数里的巧合数据） |

火桶专用枚举项（字符串 VA）：

| 枚举项 | VA |
|---|---|
| `None` | `0x14657B5B0` |
| `InitialServer` | `0x1464EFF25` |
| `InitialClient` | `0x1464A8B1C` |
| `FilterReplaceableListByHeatSourceProximity` | `0x146480D42` |
| `FilterReplaceableListByFreezingZone` | `0x14657A673` |
| `Done` | `0x14657D1AD` |

`InitialServer` / `InitialClient` 说明状态机是**服务端算、客户端复现**；两个过滤步骤说明过滤依赖运行时热源与冻结区。

## 1. 取证链

```text
本地按 UTF-16LE 扫全部 "URBVariatorAction*" 宽串
  → 反射名 = 宽串 +2（去 A/U 前缀）
  → rea xrefs(0x14665E0DA) → sub_140B57000 / sub_1427CFCC0（通用类 UClass 构造）
    rea xrefs(0x1466735FC) → sub_1408EC450（火桶类 UClass 构造）
  → 反编译两者：火桶类参数里父类 UClass 构造正是 sub_140B57000
  → 火桶类 ClassConstructor sub_140B57110 → *a1 = &off_145E21960
  → 本地展开 off_145E21960 的 qword 段（.text 范围 0x140001000–0x145065E2D）
      slot 92-96 = 0x1437E8F00 / 0x1437E9510 / 0x1437E9D40 / 0x1437E9E90 / 0x1437E6510
      slot 97 = 0（表终止）
  → 本地搜 8 字节值 0x1437E6510：6 处命中（0x145E21840 / 21C60 / 22010 / 22420 / 227A0 / 22C60）
      ⇒ 同族派生类共用同一状态机实现
  → rea procedure_callers(sub_1402D29E0 = RandSeeded) → 0x1437E 簇
  → 反编译 sub_1437E6510：case 21 出现 sub_1402D29E0(*(a1+720) + 65464321, 池长)
  → 本地搜常数 65464321 → 0x1437E767F 确认唯一抽取点
```

```text
属性链（+0x24 规则）：
  属性名 ASCII → 描述符 → +0x24 = 偏移
  → 与 sub_143504F80 / sub_1435054B0 的实参 a4+96 / a4+112 / a4+120 逐项对照
  → 与状态机 case 1 的 "配置项每项 144 字节、+136 是 UClass 指针" 对照
```

## 2. 类族（宽串扫描得到，均未逐个反编译）

`URBVariatorAction_ReplaceActors`（基类）、`...ReplaceForBurningBarrels`、
`...ReplaceForChemicalShock`、`...ReplaceForChemicalShockConditional`、
`...ReplaceForChemicalShockZoneBoundaries`、`...ReplaceForChemicalShockZoneEmptyRooms`、
`...ReplaceForMannequinTraps`、`...ItemContainerReplacement`；
枚举 `EVariatorReplaceActorsPopulateStep`、`EVariatorReplaceForBurningBarrelsPopulateStep`、
`EVariatorReplaceForMannequinTrapsPopulateStep`；结构体 `VariatorReplaceActorStruct`。

## 3. 属性 + 偏移

### 3.1 `VariatorReplaceActorStruct`（表 `0x145E201F8–0x145E20388`，144B）

| 属性 | 描述符 VA | 偏移 | 反编译实参对照 |
|---|---|---:|---|
| `ReplaceRequiredTags` (`TArray<FName>`) | `0x145E20220` | **`+0x60`** | `sub_143504F80` 的 `a4+96` → `sub_1435054B0` 的 a2 |
| `bAnyOfTheRequiredTags` | `0x145E20250` | bool 位 | `*(a4+112)` → `bAnyRequiredTags` |
| `bAllowRandomizedActors` | `0x145E20288` | bool 位 | |
| `bVerticalOnly` | `0x145E202C0` | bool 位 | |
| `bFlipAroundYAxis` | `0x145E202F8` | bool 位 | |
| `ReplaceDeniedTags` | `0x145E20358` | **`+0x78`** | `sub_143504F80` 的 `a4+120` → `sub_1435054B0` 的 a4 |
| `ReplacedActorClass` | `0x145E20388` | **`+0x88`** | 状态机 case 1：`v12 = *(配置数组 + 144*i + 136)`，按该 UClass 建迭代器 |

> +0x60 / +0x70 / +0x78 / +0x88 与 `sub_143504F80`、`sub_1435054B0`、case 1 三处实参同时吻合，
> 且 `+0x88` 是 144 字节项的最后 8 字节 ⇒ 这张表就是状态机每项 144B 的配置结构。
> 注意 `0x145E201F8`（`ReplaceRequiredTags` 偏移 0）与 `0x145E20330`（`ReplaceDeniedTags` 偏移 0）
> 属于**相邻 struct**，同名属性会跨表重复，必须按已知偏移挑表（`FORENSICS_METHODS.md` §3.2）。

### 3.2 另一份更大的配置 struct（表 `0x145E20480` 起）

`ReplacingActorClassRef` `+0x28`、`ReplacementData` `+0x58`、
`BlockableRequiredTags` `+0x70`、`bBlockableAnyRequiredTags`、`BlockableDeniedTags` `+0x88`、
`bAllowDoubleSidedSpawn`、`HidespotRequiredTags` `+0xA0`、`bHidespotAnyRequiredTags`、
`HidespotDeniedTags` `+0xB8`、`HidespotReplacementRemovalRequiredTags`、
`bPopulateBeforeSecondaryObjective`、`bIncludeInsideVerticalHidespot`、
`bIncludeEnabledInsideVerticalHidespot`、`bExcludeMissionImportantSections`。

### 3.3 第三张表（`0x145E25A50` 起，紧邻 `ETrapsCameraPopulateStep` 枚举）

`ReplaceableRequiredTags` `+0x28`、`bAnyRequiredTags`、`ReplaceableProhibitedTags` `+0x40`、
`NumberToReplaced` `+0x50`、`NumberToReplacedOnFullTrial` `+0x118`、
`bSpecificNumberToReplacedOnFullTrial`、`DistanceFromStartingSAS` `+0x1E4`、
`DistanceBetweenObjectives` `+0x1E8`、`bOnlyConsideredObjectiveCloseIfInSameRoom`、
`DistanceBetweenContainers` `+0x1F0`、`bIgnoreNonCollisionableContainer`、
`DistanceFromLedgeMarkers` `+0x1F8`、`SideDistanceFromLedgeMarkers` `+0x1FC`。

### 3.4 状态机对象字段与 `AActor::Tags`

`sub_1437E6510(__int64 *a1, ...)` 中，**`a1[N]` 是 `__int64` 索引，字节偏移 = 8N**：

| 伪代码写法 | 字节偏移 | 含义 |
|---|---:|---|
| `a1 + 81`（传给 `sub_143504F80` 的 a5） | `+648` | 输出候选池 `TArray`；Num 在 `+656` |
| `a1[11]`（case 1 的 `v10`） | `+88` | 配置数组 Data，每项 144B |
| `*((_BYTE *)a1 + 106)` | `+106` | 传给收集函数的 bool 开关 |
| `*((_DWORD *)a1 + 180)` | `+720` | **seed 字段**（case 21 的 `RandSeeded` base） |
| `*((_BYTE *)a1 + 920)` 一带 | `+920` | `PopulateStep` 枚举 |
| `*((int *)a1 + 231)` | `+924` | 当前步骤索引（144B/项） |

> 修正：早前笔记把 `a1[11]` 误记成 `+704`（把索引 88 当字节）；按 `__int64*` 换算应为 `+88`。
> 同理 `a1 + 81` = `+648`，不是 81 字节。

`sub_1435054B0(actor, required, bAny, denied)` 直接读 `actor+384`（Tags.Data）/ `actor+392`（Tags.Num），
与 `AActor::Tags` 布局一致。

## 4. vtable / 接口表

### 4.1 火桶类主 vfptr `off_145E21960`

| slot | 函数 | 备注 |
|---:|---|---|
| 92 | `0x1437E8F00` | 状态机族成员 |
| 93 | `0x1437E9510` | 状态机族成员 |
| 94 | `0x1437E9D40` | 状态机族成员 |
| 95 | `0x1437E9E90` | 状态机族成员 |
| **96** | **`sub_1437E6510`** | **通用 Populate 状态机主循环（switch 1..21+）** |
| 97 | `0` | 表终止；其后是 UClass 元数据 |

`sub_1437E6510` 在 6 处同类数据表中被引用（`0x145E21840`、`0x145E21C60`、`0x145E22010`、
`0x145E22420`、`0x145E227A0`、`0x145E22C60`），证实这一族派生类共享实现，火桶只换枚举与配置。

### 4.2 `URBReplacedActorInterface` UFUNCTION 表

`opp_seed/ue_funcs.tsv` 记的是 RVA，下表已加 base `0x140000000`：

| 组 | 表 VA | 函数 | 实现 VA |
|---:|---|---|---|
| 1070 | `0x145D590B0` | `CanBeReplaced` | `0x143953E50` |
| 1070 | 同上 | `GetReplacementRelativeTransform` | `0x143953FC0` |
| 1070 | 同上 | `SetCanBeReplaced` | `0x143953D50` |
| 1071 | `0x145D595C8` | `CanBeReplaced` | `0x142A27540` |
| 1071 | 同上 | `GetReplacementRelativeTransform` | `0x142A275A0` |
| 1071 | 同上 | `SetCanBeReplaced` | `0x142A27600` |
| 547 / 548 | `0x145BCB5D0` / `0x145BCE7A8` | `BP_GetReplacementActor` / `BP_IsReplaced` | `0x143A4BC0` / `0x1429C0D0` 等 |
| 1303 | `0x145E34A60` | `SetupLinkedActorsFromExistingRandomizableLinks` | `0x142DC9240` |

## 5. 收集链函数

| 函数 | 作用 |
|---|---|
| `sub_140120320` | 构造 `TActorIterator<AActor>`（注册 `/Script/Engine.Actor`，size 560，`sub_140021C60` 遍历 World actor 列表） |
| `sub_1404A7180` | 迭代器步进 |
| `sub_1435033A0` | 从 actor 取 Tag/FName 列表（`sub_1402C4BB0` / `sub_1402C4BA0` 转 FName） |
| **`sub_1435054B0`** | **Tag 判定核心**：读 `+384/+392`；Required 按 `bAnyOfTheRequiredTags` 走 OR / AND；Denied 命中即否 |
| `sub_143505570` | Tag 还需在全局管理器登记：`sub_141421FE0` → `sub_14017E380(manager, tag)` → `sub_143810F20(manager, tag)` |
| **`sub_143504F80`** | **主收集（case 1）**：迭代器 → 取 Tags → 管理器校验 → `sub_1407F9240` / `sub_14394DD30` / `sub_140B47990`（随机化组件有效性）→ `sub_1413C1460`（网络角色）→ **随机预筛**（`sub_1417F12F0` 取比例，`< 0.99989998` 淘汰）→ `sub_1435054B0` → `sub_141DC7330` 入池 |
| `sub_1435060A0` | case 2 `GatherFromBlockedActorsReplacement`：从管理器 `+208` / `+224` 两组列表取 actor，两套 Tag 规则分别填入两个输出数组 |
| `sub_143954150` | 接口调用：`sub_140896060` 取接口 UClass → `sub_143AC6F90` → vtable+48（即 `CanBeReplaced(bool)`） |
| `sub_141DC7330` | `TArray::AddUnique`（线性去重后追加） |
| `sub_141CB2D20` | 取全局对象：GameEngine → GameInstance → `+576`；其 `+208`/`+224` 是两组 actor 列表（**疑为变数管理器，类名未确认**） |
| `sub_14350xxx` | 各 `FilterReplaceableListBy*`（隐藏点 / 路点 / 门 / 楼梯 / 容器 / 目标 / AI 刷怪点 / 变数限制区） |
| `sub_14018C680` | case 19：名字序 introsort |
| `sub_1404FF400` | case 21：`FIntByDifficulty` 按人数取数量上限 |
| `sub_1402D29E0` | `RandSeeded` |
| `sub_140474200` | `TArray::RemoveAt`（抽取后移除，保序） |

反编译里可见的状态机日志格式串（用于按版本复核 case 编号）：

```text
"%s: GatherFromPossibleReplacement, %i availables"                     (case 1)
"%s: GatherFromBlockedActorsReplacement, %i availables"                 (case 2)
"%s: FilterReplaceableListByHidespotProximity, %i available"            (case 3)
"%s: GatherFromInsideVerticalHidespotsReplacement"                       (case 9)
"%s: FilterReplaceableListByObjectivesProximity"                         (case 11)
"%s: FilterReplaceableListByAISpawnerProximity"                          (case 16)
"%s out of %i actors, %i were gathered by random and out of those %i %s matched the tags"
                                                                       (sub_143504F80)
```

## 6. 收集流程（正向）

```text
InitialServer
  1. 按 VariatorReplaceActorStruct(i).ReplacedActorClass(+0x88) 建 TActorIterator
  2. 每个 actor 取 AActor::Tags(+384/+392)
  3. Tag 在全局管理器登记校验（sub_143505570）
  4. 随机预筛（"gathered by random"）+ 组件有效性 + 网络角色检查
  5. ReplaceRequiredTags(+0x60) / bAnyOfTheRequiredTags / ReplaceDeniedTags(+0x78)
     → sub_1435054B0 判定
  6. AddUnique 入候选池（+648）
  7. case 2 从管理器 +208/+224 补 BlockedActor；case 3..18 多维邻近过滤
  8. case 19 名字序排序；case 21 FIntByDifficulty 取数量
     → RandSeeded(*(a1+720) + 65464321, |pool|) → RemoveAt → 替换成火桶
InitialClient / Done（服务端结果复制）
```

## 7. 运行时尚未静态化的输入

静态关卡数据无法还原的四项（这也是"只给 seed 无法预测位置"的直接原因，详见
`BurningBarrel_SeedDeterminism.md`）：

1. `TActorIterator` 顺序 = World actor 列表的运行时顺序（关卡加载顺序 + 动态生成/销毁），
   不是 pak JSON 的数组序。
2. **随机预筛**：`sub_143504F80` 内 `v64 < 0.99989998` 淘汰，日志明写 `gathered by random`。
3. **Tag 登记状态**：`sub_143505570` 要求 Tag 在管理器里登记；管理器 `+208`/`+224` 的
   BlockedActor 列表由其它变数/系统运行时填充。
4. 接口 / 组件有效性：`CanBeReplaced`、随机化组件 `IsValid`、网络角色检查，
   都可能因本局其它变数而变。

## 8. 备注 / 校验

- `sub_1437E6510` 的 case 21 抽取用的是通用 `EVariatorReplaceActorsPopulateStep` 状态机；
  火桶专用枚举只有 6 个值，其专用状态机函数未单独钉死，但常数 `65464321` 在 `.text` 唯一，
  强烈暗示复用同一抽取尾部。此点标为**高置信推断，非实测闭环**。
- IDA adapter 不支持 `read_bytes` / `resolve_containing_procedure`；`search_strings(detail=complete)`
  在 `BurningBarrel` 上返回过大，需 `detail=summary` + `inspect_analysis_view(native-inventory)` 分页。
  并发 MCP 请求会打断 IDA MCP stdio，务必串行。
- 本地复现锚点：

```text
0x14665E0D8 / 0x1466735FA / 0x1467FCB5A = 三个宽类名
off_145E21960 slot 96 = 0x1437E6510，slot 97 = 0
0x145E20220+0x24 = 0x60；0x145E20358+0x24 = 0x78；0x145E20388+0x24 = 0x88
0x1437E767F = 唯一 65464321 立即数
```

校验：vtable slot、三处描述符偏移、6 处状态机引用、宽串类族清单、UFUNCTION RVA→VA 均已复跑一致。
