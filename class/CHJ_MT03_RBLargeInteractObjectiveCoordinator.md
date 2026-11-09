# CHJ_MT03 立牌点位 → RBLargeInteractObjectiveCoordinator

> 从零重做的关卡取证：只读原始地图/LD/蓝图 JSON 与 `TOT.exe`，**未参考任何既有 CHJ_MT03 分析文档**。
> 方法参照 `opp_seed/class/RBProjectionCodeCoordinator.md`（类名宽串 → UClass 构造 → CDO → vfptr；属性名 → 描述符 `+0x24` → 偏移），通用陷阱见 `FORENSICS_METHODS.md`。
> 结论：**本关 9 个立牌点位（UV 显形图案）由 `RE_LargeObjectCoordinator_C` 的两个实例驱动，其原生基类是 `/Script/OPP.RBLargeInteractObjectiveCoordinator`**；不是 `RBProjectionCodeCoordinator`（投影密码，本关无实例），也不是 `RBBlacklightDetectableQuestItemCoordinator`（本关无实例）。

## 0. 工具可用性（先确认）

| 工具 | 结果 |
|---|---|
| `ida-pro-mcp check_connection` | **可用**：`Successfully connected to IDA Pro (open file: TOT.exe)` |
| `ida-pro-mcp get_metadata` | 可用：base `0x140000000`，size `0x7625000`，md5 `6e31f74d44d0198d7293e907f3392ef6`，filesize `0x71bcc00` |
| `ida-pro-mcp get_xrefs_to / data_read_dword / decompile_function / get_function_by_address` | 可用；`data_read_dword(0x145D3D22C) = 69`，与 `FORENSICS_METHODS.md` §4 锚点一致 ⇒ `+0x24` 规则在本库成立 |
| `ida-pro-mcp list_strings_filter` | 该库字符串表过大，多次请求超时；改用 `temp/mt03_probe.py` 直接按 PE 节表扫描字符串/指针 |
| `rea list_documents` | **可用**（最小接口）：provider = `ida` / IDA MCP adapter 1.30.0，文档 `C:\Users\DELL\AppData\Local\Temp\outlast\TOT.exe`，sha256 与 IDA 一致 |
| `rea binary_overview` / `search_procedures` | 请求超时 |
| `rea current_document` | `capability_unavailable`（IDA adapter 未声明该操作） |

⇒ 联合结论：**IDA 完全可用、rea 仅登记/枚举类接口部分可用**；本文所有反编译用 `ida-pro-mcp`，批量 `.rdata` 扫表用只读脚本 `temp/mt03_probe.py`（PE 节表：` .text 0x140001000–0x145065E2D`、`.rdata 0x145066000–0x146B1B9DC`），两者结果互校。

## 1. 地图 JSON 分析（原始素材）

| 文件 | 作用 / 本次读取结果 |
|---|---|
| `opp_seed/ui/data/maps/CHJ_MT03.json` | 关卡 UI 地图（48 个源子图、2 层、4 分区、9 个 `sign_stand` 点位） |
| `opp_seed/ui/data/points/CHJ_MT03.json` | 点位规则：`^TextSignStandBase-(?!(10\|11)_)`；说明立牌 = `TextSignStandBase-*` + `TextSignStandPost-*` 两个 actor，只取 Base |
| `paks/MAP/Maps/CourthouseJudicial/CHJ_LD_MT03_B00.json` | **主 LD**（29.6 MB / 2998 对象），全部协调器实例、贴花、公文包、交付点都在这里 |
| `paks/LD_json/LD/Coordinators/*.json` | BP → 原生类 `SuperStruct` 判定 |
| `paks/LD_json/LD/LargeObject/Briefcase/ClueBriefcase_BP.json` / `.cpp` | 公文包 `FClueData Clue {Name, ClueIndex, OverrideTexture}`、`ClueToTextureMap` |
| `paks/LD/LargeObject/Briefcase/ClueBriefcaseDropZone_BP.cpp` | 交付点 `FClueData Clue` + **`TSoftObjectPtr<UDecalActor> LinkedDecal`** |

`CourthouseJudicial` 目录里含 `Coordinator` 字样的是 `CHJ_LD_MT03_B00.json`（62 处）、`CHJ_LD_MT02_B00.json`、`CHJ_LD_MT01_B00.json`、`CHJ_LD_Blockout.json`、`CHJ_LA_CourtroomMain-01.json`；MT03 的 `CHJ_LD_AreaCalc_MT03.json` / `CHJ_LD_MT03_AI*.json` / `CHJ_SND_Sound.json` 只有事件引用，不定义协调器类。

### 1.1 9 个立牌点位 = 9 张 UV 贴花

`CHJ_LD_MT03_B00.json` 里有 9 个 `BlacklightableDecal_Clue_BP_C`，其 `NewDecalComponent.RelativeLocation` 与 `maps/CHJ_MT03.json` 的 9 个 `TextSignStandBase` 点位逐一重合（X/Y 误差 < 3uu，Z≈885 是牌面高度）：

| 立牌点位（UI） | 坐标（UI） | 对应贴花 | 贴花位置 | 区 |
|---|---|---|---|---|
| `TextSignStandBase-2` | (-3101.9, 2921.4) | `BlacklightableDecal_Clue_BP4` | (-3101.2, 2918.8, 884.2) | A |
| `TextSignStandBase-3` | (-4001.4, 4193.4) | `BlacklightableDecal_Clue_BP7` | (-4003.0, 4194.4, 875.7) | A |
| `TextSignStandBase-4` | (-4551.6, 7728.5) | `BlacklightableDecal_Clue_BP2` | (-4551.8, 7725.4, 885.1) | A |
| `TextSignStandBase-6` | (968.7, 8079.6) | `BlacklightableDecal_Clue_BP8` | (968.4, 8076.9, 904.1) | B |
| `TextSignStandBase-7` | (991.2, 3833.3) | `BlacklightableDecal_Clue_BP6` | (990.8, 3836.1, 948.4) | B |
| `TextSignStandBase-8` | (-694.5, 2423.0) | `BlacklightableDecal_Clue_BP9` | (-692.7, 2424.1, 923.9) | B |
| `TextSignStandBase-9` | (-409.0, 5833.9) | `BlacklightableDecal_Clue_BP5` | (-407.7, 5835.2, 881.0) | B |
| `TextSignStandBase-01_16` | (-1868.2, 4927.8) | `BlacklightableDecal_Clue_BP_2` | (-1865.4, 4926.4, 472.9) | C |
| `TextSignStandBase-5` | (-2675.5, 7305.7) | `BlacklightableDecal_Clue_BP3` | (-2675.8, 7301.9, 884.5) | D |

`TextSignStandBase-10_2` 无贴花、附近无法官席位，UI 规则用负向断言排除。贴花本体没有 `RBObjectiveActorComponent`，**不是**任务 actor；它们是被 `ClueBriefcaseDropZone_BP_C.LinkedDecal` 引用的视觉线索：9 个 `CHJ_MT03_ClueBriefcaseDropZone_BP_1..9` 各自 `LinkedDecal` 指向上面 9 张贴花之一，其 `Clue` 字段在关卡里全为 `null` ⇒ **图案是运行期分配的**。

### 1.2 关卡里的协调器实例（4 个）

| 实例名 | 类 | 原生基类 |
|---|---|---|
| `CHJ_MT03_Intro` | 原生 `RBSimpleObjectiveCoordinator` | 自身 |
| `CHJ_MT03_FirstBribe` | `RE_LargeObjectCoordinator_C`（`OPP/Content/MapSet/Resort/Blueprint/ResortTortureGame/…`，paks 未导出） | **`RBLargeInteractObjectiveCoordinator`** |
| `CHJ_MT03_RemainingBribes` | 同上 | **`RBLargeInteractObjectiveCoordinator`** |
| `CHJ_MT03_Delay_ObjCoord_BP` | `Delay_ObjCoord_BP_C` | `RBDelayObjectiveCoordinator` |
| `CHJ_MT03_ExitStage` | `ExitStage_ObjCoord_BP_C` | `RBExitStageObjectiveCoordinator` |

两个贿赂实例的属性逐项落在本类属性表（见 §3）：`LargePickupActors`、`SpecificLargePickupActors`、`PossibleMatchingClues`、`bAssignMatchingClues`、`LargePickupActorsRandomizationSetup`、`DeliveryZoneUISettings`、`PickupObjectiveUISettings`、`bShouldHidePickupIconsUntilPickedUp`；其余 `ObjectiveActors`、`bUseObjectiveActorsRandomization`、`PrimaryActorsRandomizationSetup`、`ObjectiveLevelText` 等属父类 `RBBaseObjectiveCoordinator`。实例中没有出现任何 BP 新增属性 ⇒ 判定其原生基类即本类（BP 只做默认值覆盖）。

导出蓝图中同样直接继承本类的有 `PickupAndUse_ObjCoord_BP_C`、`GatherAndDeliver_Simple_BP_C`；`GatherAndDeliver_ObjCoord_BP_C` → `PickupAndUse_ObjCoord_BP_C` → 本类。`RE_LargeObjectCoordinator_C` 与其确切 BP 层数因资产未导出无法再往上钉死，但**原生布局结论不依赖该链**。

### 1.3 两个实例的关键配置

| 字段 | `CHJ_MT03_FirstBribe` | `CHJ_MT03_RemainingBribes` |
|---|---|---|
| `PossibleMatchingClues` | `Moon, Eye, Heart`（3） | `Bunny, Club, Crown, Diamond, Fire, Spade`（6） |
| `bAssignMatchingClues` | `true` | `true` |
| `SpecificLargePickupActors` | `CHJ_MT03_ClueBriefcase_BP_A` | `…_B / _C / _D` |
| `ObjectiveActors` | `…DropZone_BP_4`（1 个，固定） | `…DropZone_BP_1,2,3,5,6,7,8,9`（8 个） |
| `bUseObjectiveActorsRandomization` | `true` | `true` |
| `PrimaryActorsRandomizationSetup.DesiredCount` | `1` | `5` |
| `LargePickupActorsRandomizationSetup.DesiredCount.ValueName` | `…FirstBribe.SecondaryActorRandomDesiredCount` | `…RemainingBribes.SecondaryActorRandomDesiredCount` |
| `ObjectiveMissionIndex` / `ExecutionTypeFlags` | `1` / `32` | `2` / `32` |
| `NextObjectiveCoordinator` | `CHJ_MT03_RemainingBribes` | `CHJ_MT03_Delay_ObjCoord_BP` |

**3 + 6 = 9 个 clue 名 = 9 张立牌图案 = 9 个 UI 点位**；关卡提示文本也是 "Start the generator to reveal the symbols, then bring the matching briefcase to the judge."（发电机 `Timed_GeneratorObjective_BP_2` 让 UV 贴花显形，公文包上的符号需与立牌图案一致）。

## 2. 类判定链（IDA 实证）

```text
PossibleMatchingClues 名字 VA 0x1464D9B28（ASCII，exe 内）
  → 8 字节指针 xref：0x145C73D40（TArray 外壳，offset=0）、0x145C73D68（内层，offset=4080）
  → 同表首项 0x145C73A30 = LargePickupActors(3816)，末项 0x145C741B0
  → PropPointers 0x145C741F0–0x145C74320（39 项），NULL@0x145C74328
  → 0x145C74330 = 0x140934D20  ← StaticClass / UClass 惰性构造
  → decompile(0x140934D20)：L"RBLargeInteractObjectiveCoordinator"、size 11448、
       align 8、flags 0x10000004、cache qword_146E69D80、UFUNCTION 注册器 sub_142712130
  → ClassConstructor thunk sub_1429F83C0 → CDO 构造 sub_1409FEA90
  → 首三行 *a1 = &off_1459A7300 / a1+560 = off_1459A7C60 / a1+568 = off_1459A7CB0
```

类名宽串 `0x1466E53C8 = ARBLargeInteractObjectiveCoordinator`，反射名 `0x1466E53CA`（同串 +2）；`get_xrefs_to(0x1466E53CA)` → `0x140934DB3`（`sub_140934D20` 内），与 StaticClass 指针闭环。
父类 CDO `sub_1407D9A20` = `RBBaseObjectiveCoordinator`（size 3816，父表 `off_14594BE70`，293 槽）；本类属性自 `3816` 起。

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.RBLargeInteractObjectiveCoordinator` |
| 类大小 | `11448 = 0x2CB8`（CDO 初始化到 `+11440`，末项 `11424+16=11440`，2 个 bool → 11442，对齐到 11448） |
| UClass 构造 / 缓存 | `sub_140934D20` / `qword_146E69D80` |
| ClassConstructor → CDO | `sub_1429F83C0` → `sub_1409FEA90` |
| 属性描述符表 | `0x145C73A30–0x145C741B0`（39 项），PropPointers `0x145C741F0–0x145C74320`，NULL@`0x145C74328` |
| UFUNCTION 表 | `off_145C732C0` × 10，注册器 `sub_142712130` → `sub_14048DA90(class, table, 0xA)` |
| 主 vfptr | `&off_1459A7300` |
| 次表 | `+0x230`(560) `off_1459A7C60`、`+0x238`(568) `off_1459A7CB0` |

## 3. 属性 + 偏移

`+0x24` 为属性偏移；`UBoolProperty` 的 `+0x24` 恒为 `1`（位掩码），`+0x28` 恒为 `11448`（类大小），**bool 的真实字节偏移由 CDO `sub_1409FEA90` 的写入 + 虚函数读取点反推**（每 bool 独占 1 字节，与 `RBUseQuestItemsObjectiveCoordinator` 口径一致）。TArray 的 `Num` 在 `Data+8`。

| 属性名 | 描述符 VA | `+0x24` | 实际字节偏移 / 说明 |
|---|---|---:|---|
| `LargePickupActors` | `0x145C73A30` | 3816 | **TSubclassOf（UClass\*，8B）**，按类收集大件的过滤类；不是 TArray（CDO 一条 `OWORD@3816` 同时清零了它和 `+3824`） |
| `SpecificObjectiveComponentTag` | `0x145C73A68` | 3824 | FName（8B） |
| `UnderlyingType` | `0x145C73A90` | 0 | 枚举内层 |
| `MissingObjectiveCompletedPlayerEvent` | `0x145C73AC0` | 3832 | 枚举（1B） |
| `SpecificLargePickupActors` | `0x145C73AF0` | 0 | TArray 外壳 |
| `SpecificLargePickupActors` | `0x145C73B20` | **3840** | TArray（Num@**3848**），slot 273 显式表分支 |
| `bUseAvailableLargePickupsForMaxCount` | `0x145C73B50` | 1 | **3856**（CDO 1） |
| `bSetNumberOfInteractionsOnPanel` | `0x145C73B88` | 1 | **3857**（CDO 1；关卡覆写 `false`） |
| `bManageObjectivesActivationWhenStarted` | `0x145C73BC0` | 1 | **3858**（0） |
| `bOnlyStepObjectiveWhenPanelIsCompleted` | `0x145C73BF8` | 1 | **3859**（0） |
| `bNeverCompleteObjective` | `0x145C73C30` | 1 | **3860**（0） |
| `bManageLargePickupInteractions` | `0x145C73C68` | 1 | **3861**（1） |
| `NumberOfTrappedPickups` | `0x145C73CA0` | 3864 | `FIntByDifficulty`(200B)：mode@3864=4、hasValue@3928=1、value@3932=0 |
| `LockingLargePickupActorClass` | `0x145C73CD0` | 4064 | TSubclassOf（8B） |
| `bUnlockAllLargePickupsOnStart` | `0x145C73D08` | 1 | **4072**（0） |
| `PossibleMatchingClues` | `0x145C73D40` | 0 | TArray 外壳 |
| `PossibleMatchingClues` | `0x145C73D68` | **4080** | TArray（Num@**4088**）＝立牌/公文包 clue 名池 |
| `bAssignMatchingClues` | `0x145C73D98` | 1 | **4096**（CDO 0；两实例覆写 `true`） |
| `GoToUsableObjectiveText` | `0x145C73DD0` | 4104 | FText（ctor 写 `+4104/+4112/+4120`） |
| `bUseLargePickupActorsRandomization` | `0x145C73DF8` | 1 | **4128**（CDO 靠对象零初始化为 0；见下方反证） |
| `LargePickupActorsRandomizationSetup` | `0x145C73E30` | **4136** | `FRBPrimaryActorsRandomizationSetup`(1648B)，见 §3.1 |
| `DeliveryZoneUISettings` | `0x145C73E60` | 5784 | 2768B，`sub_1405D51B0` 初始化 |
| `PickupObjectiveUISettings` | `0x145C73E90` | 8552 | 2768B，`sub_1405D51B0` 初始化 |
| `bOnlyOnePickupIconIfOnSameActor` | `0x145C73EC0` | 1 | **11320**（0） |
| `bOnlyIconsOnEnabledLargePickups` | `0x145C73EF8` | 1 | **11321**（0；slot 293 `sub_1435863C0` 读 `+11321 == 1`） |
| `bShowIconOnDestinationIfAllPickupsHeld` | `0x145C73F30` | 1 | **11322**（1） |
| `OnLargeObjectHandlerChanged` | `0x145C73F68` | 11328 | 多播委托（16B） |
| `OnLargeObjectUsed` | `0x145C73F98` | 11344 | 多播委托 |
| `OnMatchingClueLargeObjectUsed` | `0x145C73FC8` | 11360 | 多播委托（**clue 匹配成功事件**） |
| `AvailableLargePickups` | `0x145C73FF8` | 0 | TArray 外壳 |
| `AvailableLargePickups` | `0x145C74028` | **11376** | TArray（Num@11384） |
| `LockingLargePickupsActors` | `0x145C74058` | 0 | TArray 外壳 |
| `LockingLargePickupsActors` | `0x145C74088` | 11392 | TArray（Num@11400） |
| `TrappedLargePickups_Server` | `0x145C740B8` | 0 | TArray 外壳 |
| `TrappedLargePickups_Server` | `0x145C740E8` | 11408 | TArray（Num@11416） |
| `PreviousAvailablePickups` | `0x145C74118` | 0 | TArray 外壳 |
| `PreviousAvailablePickups` | `0x145C74148` | 11424 | TArray（Num@11432） |
| `bShouldHidePickupIconsUntilPickedUp` | `0x145C74178` | 1 | **11440**（CDO 0；两实例覆写 `true`） |
| `bOnlyShowIconIfPickupIsUnlocked` | `0x145C741B0` | 1 | **11441**（0） |

统计：39 条描述符 / 39 项 PropPointer，其中 32 条 `+0x24 > 0`（18 个真实偏移 + 14 个 bool 位掩码），7 条 `offset=0` 为 6 个 TArray 外壳 + `UnderlyingType`。区间内另有 `0x145C74030` / `0x145C74090` 两个名字指针是 `OnRep_*` UFUNCTION 名，**未进 PropPointers**，勿当属性。

**bool 字节反证**（比按描述符顺序机械推断可靠）：
- `DWORD@3856 = 0x101`、`WORD@3860 = 0x100` ⇒ 3856/3857=1，3858–3861 = 0/0/0/1，正好 6 个 bool 顺序。
- `sub_140A61830`(slot 273) 与 `sub_140A30DF0`(slot 294) 都读 `a1+4128 & 1` 作随机化开关 ⇒ `bUseLargePickupActorsRandomization` 实际在 **4128**（FText 占 4104–4127，setup 需 8 对齐到 4136）；若按「4104+16=4120」推会错 8 字节。
- `sub_140A1EED0` 读 `a1+4096 == 1` ⇒ `bAssignMatchingClues` 在 4096。
- ctor `BYTE@11320=0 / 11321=0 / 11322=1`、`WORD@11440=0` ⇒ 末尾 5 个 bool = 11320/11321/11322/11440/11441。

### 3.1 `LargePickupActorsRandomizationSetup`（+4136，1648B）

每个 `FIntByDifficulty` / `FFloatByDifficulty` 占 200B：`{mode@+0, hasValue@+64, value@+68}`，与兄弟类 `RBUseQuestItemsObjectiveCoordinator` 布局相同。

| setup 内偏移 | 绝对偏移 | 字段 | CDO 默认 |
|---:|---:|---|---|
| +0 | 4136 | `DesiredCount` | mode 4 / hasValue@4200=1 / value@4204=-1 |
| +200 | 4336 | `DesiredStateCount.MinRatio` | mode 5 / value@4404 = `-1.0f` |
| +400 | 4536 | `DesiredStateCount.MaxRatio` | mode 5 / value@4604 = `-1.0f` |
| +600 | 4736 | `DesiredStateCount.MinCount` | mode 4 / value@4804 = -1 |
| +800 | 4936 | `DesiredStateCount.MaxCount` | mode 4 / value@5004 = -1 |
| +1008 | 5144 | `DistanceBetweenSameObjectives` | mode 5 / value@5212 = `2000.0f` |
| +1216 | 5352 | `DistanceBetweenDifferentObjectives` | mode 5 / value@5420 = `2000.0f` |
| +1416 | 5552 | `ZDistanceBetweenObjectivesOverride` | mode 5 / value@5620 = `-1.0f` |
| +1616/+1620 | 5752/5756 | 距离运行期缓存 | `2000.0f` / `2000.0f`（`0x44FA000044FA0000`） |
| +1632 | 5768 | `DesiredStateSetObjects`（Num@5776） | 空 |

`4136+1648 = 5784` 正好接 `DeliveryZoneUISettings`。

### 3.2 UFUNCTION（`off_145C732C0`，10 项）

| # | 名称 | 入口 |
|---:|---|---|
| 0 | `GetAvailableLargePickups` | `0x1438E5310` |
| 1 | `IsValidDropOffDestination` | `0x1438E51F0` |
| 2 | `OnInteractibleAddedToWorld` | `0x1438E4D20` |
| 3 | `OnLargeObjectInteractionDoAction` | `0x1438E4EB0` |
| 4 | `OnLargePickupTrapTriggered` | `0x1438E5000` |
| 5 | `OnLargePickupUsedOnObject` | `0x1438E50A0` |
| 6 | `OnPickupHolderChanged` | `0x1438E4DC0` |
| 7 | `OnRep_AvailableLargePickups` | `0x1438E4D00` |
| 8 | `OnRep_LockingLargePickupsActors` | `0x1438E4CE0` |
| 9 | `UnlockAllLargePickups` | `0x1438E52F0` |

## 4. 虚函数表

CDO `sub_1409FEA90` 写入主 `*a1 = &off_1459A7300`、`+0x230 = off_1459A7C60`、`+0x238 = off_1459A7CB0`；主表自 `0x1459A7300` 连续 299 槽（到 `0x1459A7C50`，slot 299 处不再是指向 `.text` 的指针），父表 `off_14594BE70` 293 槽 ⇒ **本类新增 6 槽（293–298）**。⚠️ 继续裸扫会把 `0x1459A7CD8` 起的相邻类表并进来，边界必须靠 CDO 的两个次表 vfptr 定。

| 表 | 首址 | 槽数 | 与父表差异 |
|---|---|---:|---|
| 主表 | `0x1459A7300` | 299（`0x1459A7300–0x1459A7C50`） | 31 处 OVR，其中 <293 的 25 处 + 新增 6 槽 |
| 次表 1 | `0x1459A7C60` | 10 | 仅 slot 6 `sub_143462BE0`（deleting dtor）OVR |
| 次表 2 | `0x1459A7CB0` | 5 | slot 1 `sub_143462C20`、slot 4 `sub_143462C60` OVR（父表 `0x14594C7F0` 仅 4 槽） |

### 4.1 关键槽（slot 以 `0x1459A7300` 为 0，槽 VA = 首址 + 8×slot）

| slot | 槽 VA | 函数 | 作用 |
|---:|---|---|---|
| 0 | `0x1459A7300` | `sub_143462BB0` | deleting dtor |
| 14 | `0x1459A7370` | `sub_140AFA4A0` | 用宽串 `L"SecondaryActorRandom"`(`0x1467432FC`) 经 `sub_140701C40` 写 setup `+4136` 的 `DesiredCount.ValueName` ⇒ 关卡里的 `...SecondaryActorRandomDesiredCount` |
| 56 | `0x1459A74C0` | `sub_143583D70` | 取本类 UClass 做属性查找 |
| 219 | `0x1459A79D8` | `sub_141DA4D70` | 继承：候选来源（显式软引用表 / 按类迭代世界 actor） |
| 249 | `0x1459A7AC8` | `sub_1402AE7F0` | 继承：随机化派发中枢（盐 `"Objective Actors"`；先调 slot 273、再抽 `ObjectiveActors`、再调 slot 275） |
| 250 | `0x1459A7AD0` | `sub_140751F60` | 继承：候选有效性谓词 |
| 256 | `0x1459A7B00` | `sub_140A30C80` | OVR：候选数组 getter |
| **273** | `0x1459A7B88` | **`sub_140A61830`** | **OVR：大件拾取物随机化**。门 `+4128&1`；`SpecificLargePickupActors.Num@3848 > 0` 走显式表 `sub_1402AF490`，否则用 `LargePickupActors@3816`（TSubclassOf，先经 `RBLargePickup` UClass 校验）按类收集 `sub_140A61C30`；setup=`+4136`，盐 `L"Large Objects"`(`0x146656762`)；收尾 `sub_140A61AD0` 按 `LockingLargePickupActorClass@4064` 填 `LockingLargePickupsActors@11392` |
| **275** | `0x1459A7B98` | **`sub_140A1ED70`** | **OVR：陷阱大件 + 线索分配**。按 `NumberOfTrappedPickups@3864` 抽 `TrappedLargePickups_Server@11408`，末尾调 `sub_140A1EED0` |
| 277 | `0x1459A7BA8` | `sub_140A30BA0` | OVR |
| 284 | `0x1459A7BE0` | `sub_143585E00` | OVR |
| 289 / 290 | `0x1459A7C08` / `0x1459A7C10` | `sub_142629270` / `sub_14345DE40` | OVR（空实现 / 状态） |
| 293 | `0x1459A7C28` | `sub_1435863C0` | 新增：读 `+11321`（`bOnlyIconsOnEnabledLargePickups`）判定图标 |
| 294 | `0x1459A7C30` | `sub_140A30DF0` | 新增：大件候选收集（门 `+4128`、setup `+5761`/`+5768`） |
| 295 | `0x1459A7C38` | `sub_1435853B0` | 新增：同步 `AvailableLargePickups@11376` |
| 296 | `0x1459A7C40` | `sub_143585E60` | 新增 |
| 297 | `0x1459A7C48` | `sub_143586520` | 新增 |
| 298 | `0x1459A7C50` | `sub_143586900` | 新增 |

其余 OVR 槽（<293）：`0, 75, 103, 104, 140, 190, 216, 220, 227, 235, 246, 252, 261, 262, 270, 271`，函数分别 `sub_1438E54E0 / sub_140AFA550 / sub_143583F90 / sub_143583E50 / sub_143583F00 / sub_143586D80 / sub_14095CDF0 / sub_143586CC0 / sub_1413C2180 / sub_143586E00 / sub_14345DE30 / sub_1435841B0 / sub_143584C80 / sub_143584FF0 / sub_143585110`（按槽序）。

## 5. 立牌图案是怎么被协调器分配的（运行期链路）

```text
slot 249 sub_1402AE7F0（父类派发）
  ├─ slot 273 sub_140A61830  随机选中本轮的大件拾取物（公文包）
  │    盐 L"Large Objects"，setup+4136，门 +4128
  ├─ ObjectiveActors 随机化（父字段）：从 1 / 8 个 DropZone 抽 1 / 5 个
  └─ slot 275 sub_140A1ED70 → sub_140A1EED0
        门：+4096 == 1（bAssignMatchingClues，两实例均为 true）
        读 +4080 / +4088（PossibleMatchingClues.Data / Num），复制到待分配池
        对带 URBClueable 的 objective actor 逐个调 sub_143585720
           · RandSeeded(GetSeed(this) + 41 / +241 / +341) 取 clue / dropzone / pickup 索引
           · 在 +4080 数组里查该 FName 的位置写入 FClueData.ClueIndex
           · sub_140B20020(actor, &FClueData) 设置接口；不含接口时日志
             "Objective actor %s doesn't contains implement cluable interface"
        ⇒ ClueBriefcaseDropZone_BP_C.Clue / ClueBriefcase_BP_C.Clue（关卡里均为 null）
        ⇒ DropZone.LinkedDecal → 9 张 BlacklightableDecal_Clue_BP 立牌图案
        ⇒ 玩家开发电机 UV 显形，按图案把对应公文包送到法官身前交付点
```

证据：`sub_140A1EED0` 反编译第 23 行 `if (*(_BYTE *)(a1+4096)==1)`、第 37/42 行 `+4088` / `+4080`；`sub_143585720` 第 106/110 行读 `+4088` / `+4080` 并 `DWORD2(v51)=v25`（ClueIndex）。9 个 `LinkedDecal` 与 9 个 clue 名（3+6）数量一致，且 `OnMatchingClueLargeObjectUsed` 委托@11360 就是「图案匹配成功」事件。

## 6. 其它协调器（本关次要，不做布局展开）

| 实例 | BP | 原生类 / 导出 JSON |
|---|---|---|
| `CHJ_MT03_Intro` | — | `RBSimpleObjectiveCoordinator`（关卡里直接以原生类实例化） |
| `CHJ_MT03_Delay_ObjCoord_BP` | `Delay_ObjCoord_BP_C` | `RBDelayObjectiveCoordinator`（`paks/LD_json/LD/Coordinators/Delay_ObjCoord_BP.json`） |
| `CHJ_MT03_ExitStage` | `ExitStage_ObjCoord_BP_C` | `RBExitStageObjectiveCoordinator`（同目录 `ExitStage_ObjCoord_BP.json`） |

`Projections_Coordinator_BP_C`（→ `RBProjectionCodeCoordinator`）与 `BlacklightDetectionItemInteract_Coord_BP_C`（→ `RBBlacklightDetectableQuestItemCoordinator`）在 `CHJ_LD_MT03_B00.json` 里**均无实例**，本关立牌图案不归它们管；参考文档 `RBProjectionCodeCoordinator.md` 在这里只作为方法论模板。

## 7. 陷阱与复现

- **类名是 UTF-16 宽串**，ASCII 搜 `RBLargeInteractObjectiveCoordinator` 无果；`A`+类名在 `0x1466E53C8`，反射名 +2。IDA 未勾选 Unicode 时看不到宽串。
- **同名属性多表**：`PossibleMatchingClues` 的两个名字指针（`0x145C73D40` / `0x145C73D68`）分别是 TArray 外壳与内层；按 `+0x24 > 0` 取内层。
- **描述符步长不固定**（`0x28`/`0x30`/`0x38` 混排），扫指向名字池的 qword 比固定步长可靠。
- **`+0x24=1` 不是字节偏移**：本类 14 个 bool 的字节位置由 CDO 与虚函数的实际读取点确定；机械顺推会把随机化开关误判成 `4120`（实为 `4128`）。
- **vtable 边界**：主表 299 槽后紧跟两张次表，`0x1459A7CD8` 起是相邻类表；只按「连续 .text 指针」扫会多算。
- **BP 类无 exe 符号**：`RE_LargeObjectCoordinator_C` 未在 paks 导出、exe 内无字符串；结论靠「实例属性 ↔ 原生属性表逐项吻合」+「同族 BP 的 SuperStruct」交叉验证。

复现（工作目录 = 仓库根）：

```powershell
python temp\mt03_probe.py find PossibleMatchingClues
python temp\mt03_probe.py xref 0x1464D9B28
python temp\mt03_probe.py props 0x145C73A30 0x145C741C0
python temp\mt03_probe.py qw   0x145C74320 0x145C74340
python temp\mt03_probe.py vt   0x1459A7300 340 0x14594BE70
python temp\mt03_probe.py vt   0x1459A7C60 10 0x14594C7A0
python temp\mt03_probe.py vt   0x1459A7CB0 5  0x14594C7F0
python temp\mt03_probe.py wide Coordinator
```

IDA 侧复核：`decompile_function(0x140934D20)` / `(0x1409FEA90)` / `(0x140A61830)` / `(0x140A1EED0)` / `(0x143585720)`、`get_xrefs_to(0x1466E53CA)`、`data_read_dword(0x145D3D22C)=69`。

**本次校验**：类大小 11448 与末项 `11424+16+2` 封口一致；属性表 39/39 项、NULL 结尾、`StaticClass` 指回 `sub_140934D20`；CDO 三个 vfptr 与主/次表槽数自洽；9 立牌 = 9 贴花 = 9 `LinkedDecal` = 3+6 `PossibleMatchingClues`。
