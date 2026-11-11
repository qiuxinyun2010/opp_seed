# TFS_MT02 钥匙门钥匙点位与协调器类

> 类专属锚点速查。通用取证方法（PE 节表映射、xrefs、`+0x24` 规则、IDA 勾选 Unicode）见 `FORENSICS_METHODS.md`，不在此重复。
> 取证链与文档体例参照 `RBProjectionCodeCoordinator.md`；钥匙点位主类的完整布局另见 `RBUseQuestItemsObjectiveCoordinator.md`（本文只做复核并补本关实例）。
> 对象 = `TOT.exe`（base `0x140000000`，`.text = 0x140001000–0x145065E2D`）。

## 0. 工具可用性确认（先做）

| 项 | 结果 |
|---|---|
| `ida-pro-mcp` | **可用**。`check_connection` → `Successfully connected to IDA Pro (open file: TOT.exe)`；`get_xrefs_to` / `decompile_function` / `data_read_dword` / `data_read_qword` / `get_function_by_address` 实测正常 |
| `rea` | **可用**。`binary_session` → `open=true`，provider `ida`（IDA MCP adapter v1，attached、selected=true）；`analyze_function` / `search_procedures` / `xrefs` 等组声明可用 |
| 受限项 | `current_document` 是 Hopper 专有，provider `ida` 不支持；`disassemble_function` 与 REA `procedure_assembly` 对本库函数返回 `None`（`Output validation error: None is not of type 'string'`）；`list_strings_filter` / REA `search_strings` 全量枚举超时 |
| 替代方案 | `release/coop/tmp/pe_probe.py`（串/指针/描述符）、`scan_props.py`（属性表）、`vt_dump.py`（vtable）直接读 `TOT.exe`；汇编用 capstone 脚本 `temp/tfs_mt02_disasm.py`；函数语义用 IDA `decompile_function` |
| 一致性校验 | `data_read_dword(0x145D3D22C) = 69`，与 `FORENSICS_METHODS.md` §4 的 `OnPanelActiveChangedEvent` 锚点一致 ⇒ 本 IDB 与参考文档口径相同、`+0x24` 规则成立 |

---

## 1. 地图 JSON 分析

### 1.1 涉及文件

| 类别 | 路径（相对仓库根） | 大小 / 内容 |
|---|---|---|
| 主地图 | `paks/MAP/Maps/ToyFactoryShipping/TFS_LD_MT02_B00.json` | 111,004,441 B，缩进式 UE 对象数组（115 种顶层 `Type`） |
| 分层地图 | `.../TFS_LD_MT02_AI.json`、`_Gates.json`、`_Traps.json`、`_Lighting.json`、各 `_BuiltData.json`、`TFS_LD_Shared_MT01_MT02.json`、`TFS_LD_Shared_MT02_MT03.json`、`TFS_LD_AreaCalc_MT02.json` | 关卡拆分的子层，主任务数据在 `B00` |
| UI 派生 | `opp_seed/ui/data/maps/TFS_MT02.json` | 71,864 B：74 `points`、66 `rooms`、118 `doors`、19 `stairs`、2 `zones`、2 `floors` |
| 点位定义 | `opp_seed/ui/data/points/TFS_MT02.json` | 6 `point_types`（`key_a/b/c/d` + `key_gate` + `cart`）、2 `zones` |
| 蓝图 | `paks/LD_json/LD/Coordinators/PushCart_ObjCoord_BP.json` / `.cpp`、`SimpleQuestItem_ObjCoord_BP.json`；`paks/LD_json/LD/Operatable/QuestItems/ToyFactory_QuestItem_A..D_BP.json`、`KeyItemDestination_Device_Base_BP.json` | BP 类与 CDO 默认值 |
| 简报数据 | `paks/LD_json/LD/Objectives/BriefingTV/NarrativeScreen_DataTables/TFS2/TV_TFS2_DT1.json`、`TV_TFS2_Shuttle.json` | 只含 `TFS_MT02` 文本，不含协调器 |

### 1.2 主地图顶层对象（本关相关）

| `Type` | 数量 | 作用 |
|---|---:|---|
| `TFS_KeyModule_Spawner_A/B/C/D_BP_C` | 12 / 29 / 10 / 17 | 钥匙候选位（共 68） |
| `KeyItemDestination_Device_Base_BP_C` + `KeyItemDestination_PanelComponent_BP_C` | 6 + 6 | 钥匙门与 `ItemClass` 判定 |
| `SimpleQuestItem_ObjCoord_BP_C` | 4 | 钥匙随机化协调器实例 |
| `PushCart_ObjCoord_BP_C` / `RBPushCartSpawner` | 1 / 4 | 推车协调器与起终点 |
| `RBObjectiveCoordinatorGroup` / `ExitStage_ObjCoord_BP_C` | 1 / 1 | 并发组 / 出口阶段 |
| `RBRandomizableHelperComponent` / `RBObjectiveActorComponent` | 87 / 75 | 随机化标记组件 |
| `Rail_ForPushable_BP_C` | 120 | 推车轨道 |

### 1.3 74 个点位 = 68 钥匙候选位 + 6 钥匙门

`ui/data/maps/TFS_MT02.json` 的 `points` 按 `zone` / `key` 统计：A 区 `key_a=12`、`key_b=29`、`key_gate=3`；B 区 `key_c=10`、`key_d=17`、`key_gate=3`。

| 池 | 候选位（`TFS_KeyModule_Spawner_*`） | 房间前缀分组 | 钥匙类 | 目标门（`KeyItemDestination_PanelComponent.ItemClass`） |
|---|---|---|---|---|
| A | 12 | `GreenIntro_1..12` | `ToyFactory_QuestItem_A_BP_C` | `GreenGate2_1` / `GreenGate3_3`（二选一） |
| B | 29 | `GreenKey_DollAssembly 3, Foreman 8, Processing 3, Security 3, Sorting 3, Storage 3, SumpPump 3, Workshop 3` | `ToyFactory_QuestItem_B_BP_C` | `GreenGate`（固定） |
| C | 10 | `PinkKeyIntro_1..10` | `ToyFactory_QuestItem_C_BP_C` | `PinkGate2` / `PinkGate3`（二选一） |
| D | 17 | `PinkKey_Bathroom 4, Compactor 2, Electrical 3, InventoryRecords 3, Laundry 3, RecalledProducts 2` | `ToyFactory_QuestItem_D_BP_C` | `PinkGate`（固定） |

6 个门坐标（`p` / `room` / `zone`）：

| 门 | 坐标 | room | zone |
|---|---|---|---|
| `MT02_KeyItemDestination_Device_Base_BP_GreenGate` | `(-3318, 2275, 0.1)` | 1 | A |
| `..._GreenGate2_1` | `(-2159, -1578, 0.1)` | 40 | A |
| `..._GreenGate3_3` | `(-3954, -1601, -14.9)` | 40 | A |
| `..._PinkGate` | `(-3748, 3194, 0.1)` | 47 | B |
| `..._PinkGate2` | `(802, 5241, 0.1)` | 32 | B |
| `..._PinkGate3` | `(-1589, 5490, 0.1)` | 31 | B |

4 个推车点：`MT02_RBPushCartSpawner_WestSide_Green` / `WestRailGoal_Green` / `EastSide_Pink` / `EastRailGoal_Pink`（`points` 里不画，只作参考标记）。

### 1.4 任务链

`MT02_RBObjectiveCoordinatorGroup` 的 `ConcurrentCoordinators` = `MT02_B00_PushCart_ObjCoord_BP` + 4 个 `MT02_SimpleQuestItem_ObjCoord_BP_*`；`NextObjectiveCoordinator` = `MT02_B03_ExitStage_ObjCoord_BP`；`bAutoStartOnStageStarted=true`。
提示文本：`"Find the key in the indicated room to unlock each gate blocking the cart."`

---

## 2. 涉及到的协调器类是什么

| 角色 | 蓝图类 → 原生父类（`/Script/OPP`） | 实例数 | 是否管本关钥匙点位 |
|---|---|---:|---|
| **钥匙随机化（主）** | `SimpleQuestItem_ObjCoord_BP_C` → **`RBUseQuestItemsObjectiveCoordinator`** | 4 | **是**：决定一局 4 把钥匙刷在哪个候选位、二选一门开哪一道 |
| 推车 / 轨道门（辅） | `PushCart_ObjCoord_BP_C` → **`RBPushCartObjectiveCoordinator`** | 1 | 否：只管推车目标与 `NumberOfUnlockableRailGates`（本关被覆盖为 0） |
| 并发组织 | `RBObjectiveCoordinatorGroup` | 1 | 否（组合 5 个协调器，本文不做布局取证） |
| 出口阶段 | `ExitStage_ObjCoord_BP_C` | 1 | 否 |

`SuperStruct` 证据：`PushCart_ObjCoord_BP.json:14-17`、`SimpleQuestItem_ObjCoord_BP.json:14-17`。

### 2.1 四个钥匙协调器实例配置（`TFS_LD_MT02_B00.json`）

| 实例 | `QuestItemClasses`@3816 | `ItemSpawnerClass`@3840 | `ObjectiveActors`（门） | `SpawnerActorsRandomizationSetup`@4096 |
|---|---|---|---|---|
| `..._GreenSide_A` | `ToyFactory_QuestItem_B_BP_C` | `TFS_KeyModule_Spawner_B_BP_C` | `..._GreenGate` | `DesiredCount=1`、`bSplitByObjectiveType=1`、`bUseRoomGroupsAsObjectiveType=1`、`bLimitOneObjectivePerRoom=1` |
| `..._GreenSide_Intro` | `ToyFactory_QuestItem_A_BP_C` | `TFS_KeyModule_Spawner_A_BP_C` | `..._GreenGate2_1` + `..._GreenGate3_3` | 同上，另 `DistanceBetweenSame/DifferentObjectives=0` |
| `..._PinkSide_B` | `ToyFactory_QuestItem_D_BP_C` | `TFS_KeyModule_Spawner_D_BP_C` | `..._PinkGate` | 同 GreenSide_A |
| `..._PinkSide_Intro` | `ToyFactory_QuestItem_C_BP_C` | `TFS_KeyModule_Spawner_C_BP_C` | `..._PinkGate2` + `..._PinkGate3` | 同 GreenSide_Intro |

4 个实例均 `bUseSpawnerActorsRandomization=true`，且未显式设置 `SpecificItemSpawners`@3848（沿用 BP CDO 空数组 ⇒ 走按类收集）；`PrimaryActorsRandomizationSetup.DesiredCount=1` ⇒ 二选一门只启用 1 道。
即**一局 4 把钥匙**（每池抽 1 个候选位）+ **4 道有效门**（Green 固定 + 二选一，Pink 固定 + 二选一）。

### 2.2 推车协调器实例

`MT02_B00_PushCart_ObjCoord_BP`：`PushableCartClass=Pushable_OnRail_Toys_BP_C`；
`NumberOfUnlockableRailGates` 被**实例覆盖为 0**（`DefaultValues` / `1P` / `2P` / `3P` 全 0），而 BP CDO 是 4 / 2 / 3 / 4；
`PrimaryActorsRandomizationSetup.DesiredCount=2`（1P=1）。
⇒ 本关的「钥匙门」**不是** `RBPushCartObjectiveCoordinator` 的轨道门随机化机制，而是 §2.1 的 `ObjectiveActors` + `KeyItemDestination_PanelComponent.ItemClass` 链。

---

## 3. `RBUseQuestItemsObjectiveCoordinator`（钥匙点位主类）

### 3.1 锚点（本轮复核，详见 `RBUseQuestItemsObjectiveCoordinator.md`）

| 项 | 值 |
|---|---|
| 宽类名 / 反射名 | `0x1466E545C` = `ARBUseQuestItemsObjectiveCoordinator`；`0x1466E545E` = 反射名（同串 +2） |
| UClass 构造 | `sub_1409362E0`（`0x140936388 call sub_14035AFB0`；`0x140936373 lea rdx,[0x1466E545E]`），size `14200=0x3778`、align 8、flags `0x10000004`、cache `qword_146E8D9E0` |
| ClassConstructor / CDO | thunk `sub_142A4A000` → `sub_1409A1640`；析构 `sub_1433CE980` |
| 属性描述符表 | `0x145E159A0–0x145E161F8`，42 条；`scan_props.py` 实测 34 条非 0 偏移，与既有文档逐项一致 |
| UFUNCTION 表 | `0x145E14E30`（14 项，注册器 `sub_1427126A0`） |
| 主 vfptr | `off_14598D950`，**306 槽**（裸扫 529 槽会把相邻类并入） |
| 次表 | `+0x230` = `off_14598E2E0`（10 槽）、`+0x238` = `off_14598E330`（5 槽） |
| 父类 | `RBBaseObjectiveCoordinator`，CDO `sub_1407D9A20`（`*a1=&off_14594BE70`、`+560`、`+568`；size 3816），父表 293 槽 |

IDA 复核：`get_xrefs_to(0x1466E545E)` → `0x140936373`（`sub_1409362E0`）；
`data_read_dword(0x145E15A64) = 3840`、`0x145E15E94 = 1`、`0x145E15ECC = 4096`，与 `scan_props` 逐项一致。

### 3.2 本关直接读取的属性偏移

| 属性 | 描述符 VA | 偏移 | 本关值 / 用途 |
|---|---|---:|---|
| `QuestItemClasses` | `0x145E159D8` | 3816 | 每实例 1 个 `ToyFactory_QuestItem_A..D_BP_C` |
| `ItemSpawnerClass` | `0x145E15A40` | **3840** | 对应的 `TFS_KeyModule_Spawner_X_BP_C`，slot 273 按类收集候选 |
| `SpecificItemSpawners` | `0x145E15AA8` | **3848** | 空 ⇒ 走按类收集分支（Num@3856） |
| `bUseSpawnerActorsRandomization` | `0x145E15E70` | **4088** | 1，slot 273 的开关 |
| `SpawnerActorsRandomizationSetup` | `0x145E15EA8` | **4096** | 1648B；`DesiredCount=1`、`bSplitByObjectiveType` / `bUseRoomGroupsAsObjectiveType` / `bLimitOneObjectivePerRoom` 均 1 |
| `MaxNumberOfQuestItems` | `0x145E15F00` | 5768 | CDO=3，实例未覆盖；每局实际刷出量由 `DesiredCount=1` + 单个 `QuestItemClass` 决定 |
| `ItemSpawners` | `0x145E160B0` | **14120** | 运行期结果（Num@14128），slot 275 清空 |
| `QuestDestinations_Server` | `0x145E16110` | 14136 | 运行期目标设备数组（本关对应 `KeyItemDestination_*` 门） |
| `ObjectiveActorsWithIcons_Client` | `0x145E161D0` | 14168 | 末项；`14168+16 = 14184`，ctor 再清 16B → 类大小 14200 |

bool 描述符的 `+0x24` 恒为 `1`（位掩码，非字节偏移）；本类 bool **独占 1 字节**、未打包成位域（见既有文档 §2.2）。

### 3.3 vtable 关键槽（`off_14598D950` 为 slot 0）

| slot | 槽 VA / 虚调用偏移 | 函数 | 作用 |
|---:|---|---|---|
| 219 | `+0x6D8` | `sub_141DA4D70` | 候选池来源：显式软引用表 / 世界 actor 按类迭代 |
| **249** | `+0x7C8` = `0x14598E118` | `sub_1402AE7F0` | 派发中枢（盐 `L"Objective Actors"`），先调 slot 273 再调 slot 275；本关二选一门对应此链的 `ObjectiveActors` 随机化分支（`DesiredCount=1`） |
| 250 | `+0x7D0` | `sub_140751F60` | 候选有效性谓词 |
| 256 | `+0x800` | `sub_140751DA0` | 候选数组 getter = slot219 ∩ slot250 |
| **273** | `+0x888` = `0x14598E1D8` | **`sub_1402AF2D0`** | **SpawnerActors 随机化**（盐 `L"Item Spawner"`、门 `+4088&1`、类 `+3840`、setup `+4096`）⇒ 本关 4 把钥匙点位 |
| 275 | `+0x898` | `sub_1402AEA00` | 清空 `ItemSpawners`(+14120)，调 `+2344/+2352/+2400` |
| 293–305 | `+0x928` 起 | `sub_1402AF990` 等 | 本类新增 13 槽：spawner 抽取后处理、启停 spawner 等 |

复核：`vt_dump.py 0x14598D950 --find 0x1402AF2D0` → `slot 273 @0x14598E1D8`；`vt_dump.py 0x14598D950 306` → slot 249 = `sub_1402AE7F0`。
`sub_1402AF2D0` 无静态 caller，完全靠 vtable 间接派发；4 个钥匙实例共用同一 `SimpleQuestItem_ObjCoord_BP_C` 蓝图类，因此共用这张表。

---

## 4. `RBPushCartObjectiveCoordinator`（本轮新增取证）

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.RBPushCartObjectiveCoordinator`（`PushCart_ObjCoord_BP_C` 的 `SuperStruct`） |
| 宽类名 / 反射名 | `0x1466E524A` = `ARBPushCartObjectiveCoordinator`；`0x1466E524C` = 反射名（+2） |
| UClass 构造 | `sub_1407FAFA0`（size `0xb9`，`0x1407FB048 call sub_14035AFB0`） |
| 类大小 / flags / 缓存 | `7104 = 0x1BC0` / `0x10000005` / `qword_146E7CB70` |
| ClassConstructor | `sub_14095DEB0`（thunk `mov rdx,rcx / mov rcx,[rcx] / jmp sub_14095DEC0`）→ CDO 构造 `sub_14095DEC0` |
| 属性描述符表 | `0x145D450E0–0x145D454A0`（16 条：8 条数值偏移 + 8 条 bool 位掩码） |
| UFUNCTION 表 | `off_145D44EA0`，2 项，注册器 `sub_142A234E0` → `sub_14048DA90(class, table, 2)` |
| 主 vfptr | `&off_145A46740`（293 槽） |
| 次表 / 接口表 | `+560` = `off_145A47070`（10 槽）、`+568` = `off_145A470C0`（4 槽）、`+3816` = `&off_145A470E0` |
| 父类 | `RBBaseObjectiveCoordinator`，CDO `sub_1407D9A20`（size 3816，主表 `off_14594BE70` 293 槽） |

### 4.1 取证链

```text
宽类名 0x1466E524A / 反射名 0x1466E524C
  → IDA get_xrefs_to(0x1466E524C)：4 处，其中 sub_1407FAFA0（size 0xb9）为 UClass 惰性构造
  → capstone 反汇编 sub_1407FAFA0 读栈参：
       [rsp+0x20]=0x1BC0(7104)  [rsp+0x28]=8  [rsp+0x30]=0x10000005
       [rsp+0x40]=0x1467D45C6 = L"Game"（配置名，不是类名，勿混）
       [rsp+0x48]=0x14095DEB0（ClassConstructor）  [rsp+0x50]=0x142629270
       rcx="/"  rdx=0x1466E524C  r8=qword_146E7CB70  r9=sub_142A234E0
  → sub_142A234E0 反编译：sub_14048DA90(sub_1407FAFA0(), &off_145D44EA0, 2)
  → ClassConstructor thunk sub_14095DEB0 → CDO 构造 sub_14095DEC0
  → 首调父类 sub_1407D9A20，随后写 *a1=&off_145A46740、a1+560/+568、a1+3816
  → 属性名 ASCII → pe_probe.py ptr → 描述符 +0x24 = 偏移 → 与 CDO 的 a1+XXXX 逐项对照
```

### 4.2 属性 + 偏移

类大小 7104；父类止于 3816，`+3816` 是本类新增的接口 vfptr（8B），ctor 再清 `+3824` 的 16B ⇒ 本类属性自 **3840** 起。

| 属性名 | 描述符 VA | `+0x24` | 说明 / CDO 默认 |
|---|---|---:|---|
| `PushableCartClass` | `0x145D450E0` | 3840 | `TSubclassOf`（8B），CDO=0 |
| `NumberOfUnlockableRailGates` | `0x145D45118` | **3848** | `FIntByDifficulty`（200B）；CDO mode@3848=4 / hasValue@3912=1 / value@3916=2；BP CDO 4，1P=2、2P=3、3P=4；**本关实例=0** |
| `MinDistanceBetweenUnlockableRailGates` | `0x145D45148` | **4048** | `FFloatByDifficulty`（200B）；CDO mode@4048=5 / hasValue@4112=1 / value@4116=`1000.0f` |
| `bAutomaticalyEnablePushable` | `0x145D45178` | 1（位掩码） | 字节 **4248** = 1 |
| `bOnlyUseCartGoalManagers` | `0x145D451B0` | 1 | 字节 4249 = 0 |
| `bUsePushCartCompletedEvent` | `0x145D451E8` | 1 | 字节 4250 = 0 |
| `bResetSplineProgressOnLink` | `0x145D45220` | 1 | 字节 4251 = 0 |
| `bClearAutoMove` | `0x145D45258` | 1 | 字节 4252 = 0（4253–4255 对齐） |
| `PushCartUISettings` | `0x145D45290` | 4256 | `FObjectiveUISettings` 2768B，由 `sub_1405D51B0` 初始化 → 7024 |
| `AutoUntoggleActors` | `0x145D452F0` | 7024 | `TArray`（Num@7032） |
| `PushCartInfos` | `0x145D45350` | 7040 | `TArray`（Num@7048），`OnRep_PushCartInfos` 同步 |
| `IconTargets_Local` | `0x145D453B0` | 7056 | `TArray`（Num@7064） |
| `ReplacementInfosToSetup_Server` | `0x145D45410` | 7072 | `TArray`（Num@7080） |
| `bCheatAutoMoveOnCompletion` | `0x145D45440` | 1（位掩码） | 字节 **7088** = 1 |
| `CheatAutoMoveSpeed` | `0x145D45478` | 7092 | float，CDO `3000.0f` |
| `bCheatAutoMoveIgnoreCollisions` | `0x145D454A0` | 1（位掩码） | 字节 **7096** = 0；`7096+8` 对齐 → 类大小 **7104** |

尺寸闭环：`3816 +8 (接口 vfptr) +16 = 3840 → +8 = 3848 → +200 = 4048 → +200 = 4248 → +8 = 4256 → +2768 = 7024 → 4×16 = 7088 → +1+4+1+对齐 = 7104`。
bool 的 `+0x24=1` 是 `UBoolProperty` 位掩码；上表字节偏移由「描述符顺序 + CDO 一次写多字节（`WORD/DWORD`）+ 相邻非 bool 属性对齐」推出：`BYTE@4248=1`、`DWORD@4249=0`、`BYTE@7088=1`、`BYTE@7096=0`。

IDA 复核：`data_read_dword(0x145D4513C) = 3848`、`data_read_dword(0x145D452B4) = 4256`。

### 4.3 CDO 默认值（`sub_14095DEC0` 摘要）

```text
sub_1407D9A20(a1)                      ; 父类 CDO：*a1=&off_14594BE70, +560, +568, +3808=-1, +3283=0
*(_OWORD*)(a1+3824) = 0
*a1 = &off_145A46740 ; a1+560 = off_145A47070 ; a1+568 = off_145A470C0 ; a1+3816 = &off_145A470E0
a1+3840 = 0                             ; PushableCartClass
a1+3848(mode)=4, a1+3912=1, a1+3916=2   ; NumberOfUnlockableRailGates
a1+4048(mode)=5, a1+4112=1, a1+4116=1000.0f ; MinDistanceBetweenUnlockableRailGates
a1+4248=1, DWORD@4249=0                 ; 5 个 bool
sub_1405D51B0(a1+4256)                  ; PushCartUISettings
4 个 TArray (7024/7040/7056/7072) 清零
a1+7088=1, a1+7092=3000.0f, a1+7096=0
```

### 4.4 vtable

`sub_14095DEC0` 写入四个 vfptr：主 `*a1 = &off_145A46740`、次表 `+560/+568`、接口表 `+3816`。

| 表 | 首址 | 槽数 | 定界依据 |
|---|---|---:|---|
| 主表 | `0x145A46740` | **293** | 连续 `.text` 指针扫描；与父类 `off_14594BE70` 同为 293 槽 ⇒ **本类未新增主槽** |
| 次表 1 | `0x145A47070` | 10 | `+560` 起，到下一 vfptr `0x145A470C0` |
| 次表 2 | `0x145A470C0` | 4 | `+568` 起，到下一 vfptr `0x145A470E0` |
| 接口表 | `0x145A470E0` | 裸扫 211 项 | `+3816`（父类大小处）新增；后续连续 `.text` 指针含相邻类表，**不能靠 NULL 定界** |

⚠️ 裸扫 `vt()` 会得到 225 / 215 / 211 项（次表 1 起），那是把后面所有邻类表并进来了；正确边界来自 CDO 的三个 vfptr。同理钥匙主类裸扫 529 槽、真实 306 槽。

相对父类 `off_14594BE70` 的 **21 个覆写槽**（`vt_dump.py 0x145A46740 --diff 0x14594BE70`；slot 以 `0x145A46740` 为 0）：

| slot | 槽 VA | 函数 | 已知作用 |
|---:|---|---|---|
| 0 | `0x145A46740` | `sub_143704570` | deleting dtor |
| 56 | `0x145A46900` | `sub_1436F7360` | 按 `RBUseQuestItems` 的 slot 56 同型推断：取本类 UClass 做属性查找 |
| 75 | `0x145A46998` | `sub_14394AF60` | |
| 103 | `0x145A46A78` | `sub_140B06B00` | |
| 140 | `0x145A46BA0` | `sub_1436F73F0` | |
| 190 | `0x145A46D30` | `sub_1436F7A00` | |
| 215 | `0x145A46DF8` | `sub_1436F89E0` | |
| 217 | `0x145A46E08` | `sub_1436F92E0` | |
| 226 | `0x145A46E50` | `sub_1436F91C0` | |
| 227 | `0x145A46E58` | `sub_1436F9250` | |
| 228 | `0x145A46E60` | `sub_1436F90B0` | |
| 229 | `0x145A46E68` | `sub_140109C80` | |
| 256 | `0x145A46F40` | `sub_14083FBE0` | |
| 261 | `0x145A46F68` | `sub_1436F8370` | |
| 262 | `0x145A46F70` | `sub_1436F8890` | |
| 270 | `0x145A46FB0` | `sub_1436F89F0` | |
| 271 | `0x145A46FB8` | `sub_1436F8EE0` | |
| 275 | `0x145A46FD8` | `sub_14083ED60` | |
| 276 | `0x145A46FE0` | `sub_140B06B90` | |
| 289 | `0x145A47048` | `sub_142629270` | 空实现 |
| 290 | `0x145A47050` | `sub_1437045A0` | |

- 次表 1（10 槽）仅 slot 6 覆写 = `sub_1437045B0`（`this-0x230` deleting dtor）；
- 次表 2（4 槽）仅 slot 1 覆写 = `sub_1437045F0`；
- **slot 249 / 250 / 273 均未覆写**，沿用 `RBBaseObjectiveCoordinator` 的实现：父表 slot 249 = `sub_1402AE7F0`（随机化派发中枢）、slot 250 = `sub_140751F60`、slot 273 = `sub_1400011A0`（空实现）。`RBUseQuestItemsObjectiveCoordinator` 把 slot 273 覆写成 `sub_1402AF2D0`（钥匙 spawner 随机化），**两张表的 slot 273 不要混**。

### 4.5 UFUNCTION 表（`off_145D44EA0`，2 项）

`ue_funcs.tsv` 的 `5d44ea0` 组（RVA + `0x140000000` = 入口 VA）：

| # | 名称 | thunk 入口 |
|---:|---|---|
| 0 | `OnRep_PushCartInfos` | `0x14394AED0` |
| 1 | `OnTargetTriggerBeginOverlap` | `0x14394AC10` |

---

## 5. 备注与陷阱

1. **`disassemble_function` / REA `procedure_assembly` 对本 IDB 返回 `None`**，改用 capstone 读 PE 字节（`temp/tfs_mt02_disasm.py`）+ IDA `decompile_function`；`list_strings_filter` / REA `search_strings` 全量枚举超时，改用 `pe_probe.py str/ptr` 扫 PE。
2. **UClass 栈参 `+0x40 = 0x1467D45C6` 是 `L"Game"`**（`0x1467D45C4 = L"/Game"`），不是类名；类名宽串在 `0x1466E524A`。`RBUseQuestItems` 的同一栈参也是这个值。
3. **按名字指针挑表**：`pe_probe.py ptr 0x1464DA721`（`NumberOfUnlockableRailGates`）→ 描述符 `0x145D45118`（3848），`ptr 0x1464D6D7B`（`PushCartUISettings`）→ `0x145D45290`（4256）；判别依据是偏移落在本类 `3816..7104`。`Game`/`bIsOn`/`OnLinkedTriggered` 在 `0x145D45590+` 属相邻类，勿并入本类属性表。
4. **BP 类在 exe 中无符号**：`TFS_KeyModule_Spawner_*`、`KeyItemDestination_*`、`SimpleQuestItem_ObjCoord_BP_C`、`PushCart_ObjCoord_BP_C` 均无独立 UClass 构造 / vtable；它们的字段偏移只在 pak 的 `BlueprintGeneratedClass.ChildProperties`，运行期计算。本文偏移全部来自它们的**原生父类**。
5. **两个「门」概念要分开**：`RBPushCartObjectiveCoordinator.NumberOfUnlockableRailGates`（轨道门数量，本关 0）与 6 个 `KeyItemDestination_Device_Base_BP_C` 钥匙门（由 `QuestItemClasses` + `ItemClass` 控制）互不隶属。
6. `TArray` 的 `Num` 在 `Data+8`；bool 描述符 `+0x24=1` 是位掩码，字节偏移靠 ctor 写入判定（本文 §4.2 已逐项推出）。

---

## 6. 校验与复现

| 项 | 结果 |
|---|---|
| `data_read_dword(0x145D3D22C)` | 69（参考文档锚点） |
| `data_read_dword(0x145D4513C)` / `0x145D452B4` | 3848 / 4256 |
| `data_read_qword(0x145A46740)` | `0x143704570`（deleting dtor） |
| `get_xrefs_to(0x1466E524C)` | `sub_1407FAFA0`、`sub_1402B05C0`、`sub_1402B3C30`、`sub_140A701F0` |
| `scan_props.py 0x145E159A0 0x145E16200` | 34 条非 0 偏移，与 `RBUseQuestItemsObjectiveCoordinator.md` 全表一致 |
| `vt_dump.py 0x14598D950 --find 0x1402AF2D0` | slot 273 @ `0x14598E1D8` |
| 尺寸闭环 | 末字段 `bCheatAutoMoveIgnoreCollisions`@7096（1B）→ 7097 按 align 8 上取整 = **7104**（本类）；**14200** = `14184 + 16`（钥匙类） |

```powershell
cd c:\Users\DELL\AppData\Local\Temp\outlast
python temp\tfs_mt02_map_probe.py      > temp\tfs_mt02_probe_out.txt     # 111MB 地图流式统计
python temp\tfs_mt02_coord_dump.py    > temp\tfs_mt02_coord_out.txt     # 协调器实例 / 钥匙池 / UI 点位
python temp\tfs_mt02_disasm.py 0x1407FAFA0 0x1407FB059                  # UClass 构造栈参
cd release\coop\tmp
python pe_probe.py str RBPushCartObjectiveCoordinator utf16
python scan_props.py 0x145D450E0 0x145D454B0
python scan_props.py 0x145E159A0 0x145E16200
python vt_dump.py 0x145A46740 --diff 0x14594BE70 400
python vt_dump.py 0x145A47070 --diff 0x14594C7A0 10
python vt_dump.py 0x145A470C0 --diff 0x14594C7F0 4
python vt_dump.py 0x14598D950 --find 0x1402AF2D0
```

IDA MCP 侧：`check_connection`、`get_xrefs_to(0x1466E524C)`、`decompile_function(0x1407FAFA0)`、`decompile_function(0x14095DEC0)`、`decompile_function(0x142A234E0)`、`decompile_function(0x1407D9A20)`。

### 边界

- 本文只做静态取证：地图 JSON 配置 + 类布局 + vtable。**seed → 钥匙点位的正向推导另见 `../level/TFS_MT02.md`**（`temp/tfs_mt02_predict.py`，9/9 回归）。
- `opp_seed/test.txt:578–589` 有 3 局 TFS_MT02 实测（698698、462462、777777，均 Easy/1P），每局记录单侧 2 个钥匙点位；正向文档已把这 6 个点位 + 3 条推车线纳入回归。
- 难度 / 人数：4 个钥匙协调器的 `SpawnerActorsRandomizationSetup` 中 `MinCount` / `MaxCount` 三档均 `bLocalOverrideFor1P/2P/3P=true`，数值由 BP 默认给出；本文未展开 `FIntByDifficulty::Get` 的分档结果。
- 关联参考：`class/RBProjectionCodeCoordinator.md`（方法模板）、`class/RBUseQuestItemsObjectiveCoordinator.md`（主类全表）、`class/FORENSICS_METHODS.md`（通用陷阱）、`level/TFS_MT02.md`（本关正向推导）、`level/TFS_MT03.md`（同地图 MT03 的正向推导范例）、`ui/ZONES.md`。
