# RBUseQuestItemsObjectiveCoordinator

> 类专属锚点速查。通用取证方法（PE 节表映射、xrefs、`+0x24` 规则、IDA 勾选 Unicode）不在此重复。
> 本文对象 = FPC_MT02 出票机随机分布协调器的**原生基类**：
> `SimpleTicketBooth_CoordBP_C` → `SimpleQuestItem_ObjCoord_BP_C` → **本类**（`/Script/OPP`）。

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.RBUseQuestItemsObjectiveCoordinator`（`SimpleQuestItem_ObjCoord_BP_C` 的 `SuperStruct`） |
| 二进制 | `TOT.exe`（base `0x140000000`，`.text = 0x140001000–0x145065E2D`） |
| 类名宽串 | `0x1466E545C` = `ARBUseQuestItemsObjectiveCoordinator`；反射名 `0x1466E545E` = `RBUseQuestItemsObjectiveCoordinator`（同串 +2） |
| UClass 构造 | `sub_1409362E0`，类大小 `14200 = 0x3778`，对齐 `8`，flags `0x10000004`，缓存 `qword_146E8D9E0` |
| CDO 构造 | `sub_142A4A000`（ClassConstructor thunk，`jmp 0x1409A1640`）→ `sub_1409A1640`；析构 `sub_1433CE980` |
| 属性描述符表 | `0x145E159A0–0x145E161F8`（42 条描述符，34 条非 0 偏移），PropPointers `0x145E16200–0x145E16348`（42 项，NULL@`0x145E16350`） |
| UFUNCTION 表 | `0x145E14E30`（14 项，注册器 `sub_1427126A0` → `sub_14048DA90(class, table, 0xE)`） |
| 主 vfptr | `&off_14598D950`（306 槽：`0x14598D950–0x14598E2D8`），写于对象 `+0x000` |
| 次表 | `+0x230`（560）= `off_14598E2E0`（10 槽）、`+0x238`（568）= `off_14598E330`（5 槽） |
| 父类 | `RBBaseObjectiveCoordinator`（ctor `sub_1407D9A20`，size `3816`，vtable `off_14594BE70`，293 槽） |

## 1. 取证链

```text
类名宽串 0x1466E545E
  → 代码 xref（`0x140936373 lea rdx`）→ sub_1409362E0（UClass 惰性构造，sub_14035AFB0 调用点 0x140936388）
  → 参数："/" + L"RBUseQuestItemsObjectiveCoordinator" + &qword_146E8D9E0
          + sub_1427126A0(UFUNCTION 注册) + 14200 + 8 + 0x10000004
  → 构造 thunk sub_142A4A000 → CDO 构造 sub_1409A1640
  → 函数体首 3 行写入 *a1 = &off_14598D950
                       a1+0x230 = off_14598E2E0
                       a1+0x238 = off_14598E330
  → 展开主表 306 项：slot 273 (+0x888) = sub_1402AF2D0   ← SpawnerActors 随机化
```

汇编级复核（`sub_1409362E0`，无需 IDA 即可在 TOT.exe 里复现）：

```text
0x140936326  lea rcx, [0x142629270]              ; 栈参 +0x50（各 UClass 注册共用的 helper）
0x140936332  lea rcx, [0x142A4A000]              ; 栈参 +0x48 = ClassConstructor
0x140936354  mov dword [rsp+0x30], 0x10000004    ; ClassFlags
0x14093635C  mov dword [rsp+0x28], 8             ; align
0x140936364  mov dword [rsp+0x20], 0x3778        ; sizeof = 14200
0x14093636C  lea rcx, [0x14686E07E]              ; "/"
0x140936373  lea rdx, [0x1466E545E]              ; 反射名
0x14093637A  lea r8,  [0x146E8D9E0]              ; 静态类缓存
0x140936381  lea r9,  [0x1427126A0]              ; UFUNCTION 注册器
0x140936388  call sub_14035AFB0
0x142A4A000  mov rdx,rcx / mov rcx,[rcx] / jmp sub_1409A1640
```

`0x1409363A7` 起还有**另一段**同型注册（size `0x1790`、名字 `0x14662610C`、缓存
`qword_146E91800`、注册器 `sub_1427126D0`）——相邻类，勿混。
析构 `sub_1433CE980` 同样写 `+0`/`+0x230`/`+0x238` 三个 vfptr，可反证表首。

```text
属性名（ASCII）→ 搜指向该名的 8 字节指针 → 命中处即描述符
  → 描述符 +0x24 = 属性偏移（bool 项是位掩码，字节偏移靠 ctor 写入判定）
  → 与 sub_1409A1640 的 a1+XXXX 对照
```

- 同名属性会出现在多张表：`SpawnerActorsRandomizationSetup` 还命中 `0x145C3BF40`（偏移 4680，属另一类）；
  本类的表项是 `0x145E15EA8`（偏移 4096）。判别法：描述符偏移必须落进本类 `3816..14184`。
- `SpecificItemSpawners` / `QuestItemRuntimeInfos` / `ItemSpawners` 等 TArray 在 PropPointers 里是
  **两项**（数组外壳 offset=0 + 内层元素 offset=N），统计属性以非 0 项为准。

## 2. 属性 + 偏移

类大小 `14200`；父类属性止于 `3816`，本类属性自 `3816` 起。
`.rdata` 里 `0x145E159A0–0x145E161F8` 共 42 条描述符，
`0x145E16200–0x145E16348` 是对应的 42 项 PropPointers。按 `+0x24 > 0` 过滤得到
34 条有效偏移（含 14 个 bool 的 `1`）；另 8 条 `offset=0` 是 7 个 TArray 的
「数组外壳 + 内层元素」外壳项（如 `QuestItemClasses` 同时命中 `0x145E159A0`/`0x145E159D8`）
加一条 `UnderlyingType`（枚举内层属性）。`0x145E16350` 为 NULL 结尾，`0x145E16358` 存
`sub_1409362E0`（StaticClass 指针）。

| 属性名 | 描述符 VA | 偏移 | 说明 / CDO 默认 |
|---|---|---|---|
| `QuestItemClasses` | `0x145E159D8` | 3816 | TArray（Num@3824），元素 TSubclassOf |
| `ItemClassForAllContainers` | `0x145E15A08` | 3832 | TSubclassOf（8B） |
| `ItemSpawnerClass` | `0x145E15A40` | **3840** | TSubclassOf，slot 273 读它做按类收集 |
| `SpecificItemSpawners` | `0x145E15AA8` | **3848** | TArray（Num@3856），显式表分支 |
| `bStartWithSpawnersEnabled` | `0x145E15AD8` | 3864 | bool；CDO=1 |
| `bUseItemsForCompletionCount` | `0x145E15B10` | 3865 | bool；CDO=1 |
| `bUseItemsCountForMaxInteractionsCount` | `0x145E15B48` | 3866 | bool；CDO=0 |
| `bUseDestinationCountForItemCount` | `0x145E15B80` | 3867 | bool；CDO=0 |
| `bResetDestinationNumberOfItemsUsed` | `0x145E15BB8` | 3868 | bool；CDO=0 |
| `bOnlyShowIconOnItemEnabled` | `0x145E15BF0` | 3869 | bool；CDO=0 |
| `FixedSpawnedItemCount` | `0x145E15C28` | 3872 | FIntByDifficulty（200B）；mode=4 / hasValue@3936=1 / value@3940=0 |
| `bOverride_FixedSpawnedItemCount` | `0x145E15C58` | 4072 | bool |
| `MissingObjectiveCompletedPlayerEvent` | `0x145E15CC0` | 4073 | 枚举（1B，非 bool） |
| `bRemoveAllItemsOnCompleted` | `0x145E15CF0` | 4074 | bool；CDO=0 |
| `bSpawnItemsOnCoordoStarted` | `0x145E15D28` | 4075 | bool；CDO=1 |
| `bOnlyCountSpawnedItems` | `0x145E15D60` | 4076 | bool；CDO=0 |
| `bManageInteractions` | `0x145E15D98` | 4077 | bool；CDO=1 |
| `bAutoDiscoverNewPickups` | `0x145E15DD0` | 4078 | bool；CDO=0 |
| `bAdoptExistingSpawnedItem` | `0x145E15E08` | 4079 | bool；CDO=0 |
| `ItemChainingCoordinator` | `0x145E15E40` | 4080 | 对象指针（8B） |
| `bUseSpawnerActorsRandomization` | `0x145E15E70` | **4088** | bool，slot 273 的开关（`&1`） |
| `SpawnerActorsRandomizationSetup` | `0x145E15EA8` | **4096** | FRBPrimaryActorsRandomizationSetup（1648B，见 §4） |
| `GoToUsableDeviceText` | `0x145E15ED8` | 5744 | FText（16B） |
| `MaxNumberOfQuestItems` | `0x145E15F00` | 5768 | int32；CDO=3 |
| `bSetAutoManagedItemsIconsWhenCompleted` | `0x145E15F28` | 5772 | bool；CDO=0 |
| `QuestItemSpawnerUISettings` | `0x145E15F60` | 5776 | 2768B |
| `QuestItemPickupUISettings` | `0x145E15F90` | 8544 | 2768B |
| `DestinationDeviceUISettings` | `0x145E15FC0` | 11312 | 2768B |
| `OnQuestItemPickedUp` | `0x145E15FF0` | 14080 | 多播委托（16B） |
| `QuestItemRuntimeInfos` | `0x145E16050` | 14096 | TArray（Num@14104） |
| `ItemSpawners` | `0x145E160B0` | 14120 | TArray（Num@14128），slot 275 清空 |
| `QuestDestinations_Server` | `0x145E16110` | 14136 | TArray |
| `DestinationDeviceWithIcons_Client` | `0x145E16170` | 14152 | TArray |
| `ObjectiveActorsWithIcons_Client` | `0x145E161D0` | 14168 | TArray（末项，止于 14184） |
| （未注册） | — | 14184 | ctor 清零 16B；14200 = 14184+16 |

加粗项是随机分布链路直接读取的字段；`sub_1409A1640` 的写入（3816/3832/3848 清零、3864=`0x0101`、
3866 dword=0、4074 dword=`0x01000100`、4078 word=0、5712=`2000.0f,2000.0f`、5768=3、5772=0）
与上表偏移逐项吻合。

**bool 读法**：所有 bool 描述符的 `+0x24` 恒为 `1`（`UBoolProperty` 的位掩码/尺寸，
不是字节偏移；`+0x28` 恒为 `0x3778` = 类大小）。表中 3864–3869、4072、4074–4079、4088、5772
的字节偏移是由「描述符顺序 + ctor 一次写多字节 + 相邻非 bool 属性的对齐」推出的：
`WORD@3864 = 0x0101` ⇒ 3864/3865 各为 1，`DWORD@3866 = 0` ⇒ 3866–3869 为 0，
`DWORD@4074 = 0x01000100` ⇒ 4075/4077 为 1、4074/4076 为 0，`WORD@4078 = 0`。
即本类每个 bool **独占 1 字节**、未打包成位域（这与 `RBProjectionCodeCoordinator` 的位域口径不同）。

### 2.1 随机分布专用视图（FPC_MT02 出票机）

| 字段 | 偏移 | Canals 实例值 | Office 实例值 |
|---|---|---|---|
| `ItemSpawnerClass` | 3840 | `FPC_TriggerableTicketDispenser_01_A_BP_C` | `..._01_B_BP_C` |
| `SpecificItemSpawners` | 3848 | 空（走按类收集） | 空 |
| `bUseSpawnerActorsRandomization` | 4088 | 1 | 1 |
| `SpawnerActorsRandomizationSetup.DesiredCount` | 4096 | 5 | 5 |
| `SpawnerActorsRandomizationSetup.DistanceBetweenSameObjectives` | 5104 | 1500.0 | 1500.0 |
| `ItemSpawners` | 14120 | 运行期结果（5 台） | 运行期结果（5 台） |

### 2.2 CDO 默认值（`sub_1409A1640` 逐条复原）

`FIntByDifficulty` / `FFloatByDifficulty` 均为 200B：`{mode@+0, hasValue@+64, value@+68}`。
ctor 对 `FixedSpawnedItemCount`(3872) 和 setup(4096) 内 8 段逐段写默认值：

| 起始偏移 | 字段 | mode | hasValue | value |
|---:|---|---:|---:|---|
| 3872 | `FixedSpawnedItemCount` | 4 | 3936 = 1 | 3940 = 0 |
| 4096 | `DesiredCount` | 4 | 4160 = 1 | 4164 = -1 |
| 4296 / 4496 | `DesiredStateCount.MinRatio` / `MaxRatio` | 5 | 4360 / 4560 = 1 | 4364 / 4564 = `-1.0f` |
| 4696 / 4896 | `DesiredStateCount.MinCount` / `MaxCount` | 4 | 4760 / 4960 = 1 | 4764 / 4964 = -1 |
| 5104 | `DistanceBetweenSameObjectives` | 5 | 5168 = 1 | 5172 = `2000.0f` |
| 5312 | `DistanceBetweenDifferentObjectives` | 5 | 5376 = 1 | 5380 = `2000.0f` |
| 5512 | `ZDistanceBetweenObjectivesOverride` | 5 | 5576 = 1 | 5580 = `-1.0f` |
| 5712 / 5716 | 运行期距离缓存 | — | — | `2000.0f` / `2000.0f` |

其余：`MaxNumberOfQuestItems` = 3（5768）、`bSetAutoManagedItemsIconsWhenCompleted` = 0（5772）、
三个 `FObjectiveUISettings` 由 `sub_1405D51B0` 初始化（5776 / 8544 / 11312）、
`OnQuestItemPickedUp` 与 5 个 TArray、末尾 16B 全清零（14080–14199）、
**`+805 = 1`**（父类字段，决定 slot 249 先派发 slot 273，见 §3.0）。

## 3. vtable

`sub_1409A1640` 写入的三个 vfptr：主 `*a1 = &off_14598D950`、`a1+0x230 = off_14598E2E0`、
`a1+0x238 = off_14598E330`；`sub_1433CE980`（析构）重复写同三值。

- 主表 `0x14598D950`，**306 槽**（`0x14598D950–0x14598E2D8`），后接 `0x14598E2E0` 次表；
  父表 `0x14594BE70` 293 槽 → 本类新增 13 槽（293–305）。
- 本类三表连续区间 = `0x14598D950–0x14598E358`；其后到 `0x14598E9D8` 的 NULL 为止是相邻类表（勿混）。
  ⚠️ 若只按「连续 .text 指针」扫表会得到 **529 槽**，那是把后面相邻类的表也并进来了；
  正确边界来自 ctor 的 `+0x230`/`+0x238` 两个 vfptr，不能靠 NULL 定界。
- 次表 1（`+0x230`）`0x14598E2E0`：10 槽，仅 slot 6 覆写（`sub_1433CEB10`，`this-0x230` 的 deleting dtor）；
  父表为 `0x14594C7A0`（同为 10 槽）。
- 次表 2（`+0x238`）`0x14598E330`：5 槽，slot 1 覆写（`sub_1433CEB50`，`this-0x238` 的 deleting dtor）、
  slot 4 为本类新增（`sub_1433CE5E0`）；父表 `0x14594C7F0` 只有 4 槽。

### 3.0 继承未覆写、但随机化链路会用到的槽

| slot | 虚调用偏移 | 函数 | 作用 |
|---:|---|---|---|
| 219 | `+0x6D8` | `sub_141DA4D70` | 候选来源：显式软引用表 `+728` 或按类迭代世界 actor |
| 249 | `+0x7C8` | `sub_1402AE7F0` | `ObjectiveActors` 随机化入口（盐 `L"Objective Actors"`） |
| 250 | `+0x7D0` | `sub_140751F60` | 候选有效性谓词 |
| 256 | `+0x800` | `sub_140751DA0` | 候选数组 getter = slot219 ∩ slot250 |

> 别把 `sub_14361C230` 的「slot 557 / +0x1168」套到本表：它属于另一张 vtable
> （真正表首 `0x145A20C90`，FUNC_INDEX §7 有过基址纠正），不是本类的槽。

`sub_1402AE7F0`（slot 249，父类实现）是本类的派发中枢，反编译 `fn_1402AE7F0.c` 可逐行复核：

```text
if (coord+3283 != 1) {
    if (coord+805 == 1)  vtable[273](coord)   // +0x888，CDO 把 +805 置 1 ⇒ 先抽 spawner
    if (coord+1346 & 1)                        // bUseObjectiveActorsRandomization
        Num@+736 > 0 ? sub_1402AF490(setup=+1352, +728, "Objective Actors")
                     : sub_1402B0070(setup=+1352, +704, "Objective Actors")
    if (coord+805 == 0)  vtable[273](coord)   // 否则放到后面
    vtable[275](coord)                         // +0x898 → sub_1402AEA00
    coord+3452 = 1
}
```

`sub_1402AEA00`（slot 275）把 `ItemSpawners@14120` 的 `Num@14128` 清零，再依次调
`vtable+2344/+2352`；仅当 `bSpawnItemsOnCoordoStarted@4075 == 0` 时补调 `vtable+2400`。

### 3.1 相对父类 `off_14594BE70` 的覆写槽（24 项）

槽 VA = `0x14598D950 + 8*slot`（下表 `+0xNNN` 即槽内偏移）。
下表只列 slot < 293 的 24 项；`vt_dump.py --diff` 全表共 37 项 OVR，另 13 项见 §3.2。

| slot | 槽 VA | 函数 | 已知作用 |
|---:|---|---|---|
| 0 | `+0x000` | `sub_1433CEAE0` | deleting dtor（→ `sub_1433CE980`） |
| 14 | `+0x070`（`0x14598D9C0`） | `sub_1407016A0` | 用宽串 `L"SecondaryActorRandom"`（`0x1467432FC`）经 `sub_140701C40` 拼后缀 → `sub_140702370` 写 `DesiredCount.ValueName`（pak 里表现为 `...SecondaryActorRandomDesiredCount`）；同时把 setup `+1616/+1620` 距离缓存刷成 `2000.0f` |
| 56 | `+0x1C0` | `sub_1437D38B0` | 取本类 UClass 做属性查找（`QuestItemRuntimeInfos` / `ItemSpawners`） |
| 75 | `+0x258` | `sub_143993F80` | |
| 140 | `+0x460` | `sub_1437D3DE0` | |
| 190 | `+0x5F0` | `sub_1437D3990` | |
| 217 | `+0x6C8` | `sub_1437D6720` | |
| 220 | `+0x6E0` | `sub_1406963D0` | |
| 225 | `+0x708` | `sub_1437D3F00` | |
| 227 | `+0x718` | `sub_1437D6D20` | |
| 235 | `+0x758` | `sub_1406963B0` | |
| 236 | `+0x760` | `sub_1437D6DB0` | |
| 246 | `+0x7B0` | `sub_1437D6E60` | |
| 261 | `+0x828` | `sub_1437D4F40` | |
| 262 | `+0x830` | `sub_1437D5660` | |
| 270 | `+0x870` | `sub_1437D5D10` | |
| 271 | `+0x878` | `sub_1437D6440` | |
| 272 | `+0x880` | `sub_1437D4880` | |
| **273** | **`+0x888`** | **`sub_1402AF2D0`** | **SpawnerActors 随机化（盐 `L"Item Spawner"`，门 `+4088&1`，类 `+3840`，setup `+4096`）** |
| 275 | `+0x898` | `sub_1402AEA00` | 清空 `ItemSpawners`(+14120)，调 `+2344/+2352/+2400` |
| 283 | `+0x8D8` | `sub_1437D4760` | |
| 284 | `+0x8E0` | `sub_1437D4710` | |
| 289 | `+0x908` | `sub_142629270` | 空实现 |
| 290 | `+0x910` | `sub_1433CB240` | |

> slot 249（`+0x7C8 = sub_1402AE7F0`，盐 `"Objective Actors"`）**不是覆写**，沿用父类实现。

### 3.2 本类新增槽（293–305）

| slot | 槽 VA | 函数 | 已知作用 |
|---:|---|---|---|
| 293 | `+0x928` | `sub_1402AF990` | spawner 随机化后处理（读 setup+1640 = `DesiredStateSetObjects.Num()`） |
| 294 | `+0x930` | `sub_1402AEA80` | 启停 spawner 物件（`bManageInteractions@4077` / `bStartWithSpawnersEnabled@3864` / `ItemSpawners@14120`） |
| 295 | `+0x938` | `sub_1407528C0` | |
| 296 | `+0x940` | `sub_1437D6C50` | |
| 297 | `+0x948` | `sub_1437D3F20` | |
| 298 | `+0x950` | `sub_1437D4120` | |
| 299 | `+0x958` | `sub_1437D4180` | |
| 300 | `+0x960` | `sub_1437D48D0` | item spawner 抽取（`RandSeeded(GetSeed(this)+i)`，见 FUNC_INDEX） |
| 301 | `+0x968` | `sub_1437D6870` | |
| 302 | `+0x970` | `sub_1437D6970` | |
| 303 | `+0x978` | `sub_1437D6A20` | |
| 304 | `+0x980` | `sub_140753D00` | |
| 305 | `+0x988` | `sub_1437D6D00` | |

### 3.3 UFUNCTION 表（`0x145E14E30`，14 项）

`sub_1427126A0` 反汇编：`call sub_1409362E0` → `lea rdx,[0x145E14E30]` → `mov r8d,0xE` →
`jmp sub_14048DA90`。按 `ue_funcs.tsv` 的 `5e14e30` 组解出 14 个名字（RVA + `0x140000000`）：

| # | 名称 | 入口 VA |
|---:|---|---|
| 0 | `GetActiveSpawnerCount` | `0x143993C80` |
| 1 | `OnAutoDiscoverPickup_Server` | `0x143993D40` |
| 2 | `OnDeferredConditionMet_Server` | `0x143993700` |
| 3 | `OnItemSpawnerSpawnedItemInfosChanged_Server` | `0x143993CA0` |
| 4 | `OnPanelInteractionCompletedChanged` | `0x1439937A0` |
| 5 | `OnPawnKilled` | `0x143993DE0` |
| 6 | `OnPlayerDisconnect` | `0x143853030` |
| 7 | `OnPlayerDoAction` | `0x143993890` |
| 8 | `OnPlayerStoppedOperating` | `0x143993990` |
| 9 | `OnQuestItemDropped_Server` | `0x143993A80` |
| 10 | `OnQuestItemPickedUp_Server` | `0x143993B80` |
| 11 | `OnQuestItemUsedOnItemChanged` | `0x143852F40` |
| 12 | `OnRep_QuestItemRuntimeInfos` | `0x143914140` |
| 13 | `OnSpawnedObjectiveItemEnabledChanged` | `0x143853110` |

## 4. `SpawnerActorsRandomizationSetup`（`+4096`，1648B）内部偏移

每个 `FIntByDifficulty` / `FFloatByDifficulty` 占 200B：`{mode@+0, hasValue@+64, value@+68}`。

| setup 内偏移 | 协调器绝对偏移 | 字段 | CDO 默认 |
|---:|---:|---|---|
| +0 | 4096 | `DesiredCount` | mode 4 / hasValue 1 / value -1 |
| +200 | 4296 | `DesiredStateCount.MinRatio` | mode 5 / value `-1.0f` |
| +400 | 4496 | `DesiredStateCount.MaxRatio` | mode 5 / value `-1.0f` |
| +600 | 4696 | `DesiredStateCount.MinCount` | mode 4 / value -1 |
| +800 | 4896 | `DesiredStateCount.MaxCount` | mode 4 / value -1 |
| +1000–1005 | 5096–5101 | bools：`bSplitByObjectiveType` / `bUseRoomGroupsAsObjectiveType` / `bUseOtherCoordoActorsForDistance`@1002 / `bLimitOneObjectivePerRoom`@1003 / `bAllowRandomizionInMissionImportantSection`@1004 / `bOverrideDistanceBetweenSameObjectives`@1005 | — |
| +1008 | 5104 | `DistanceBetweenSameObjectives` | mode 5 / value `2000.0f`（FPC_MT02 覆写为 1500） |
| +1208 | 5304 | `bOverrideDistanceBetweenDifferentObjectives` | — |
| +1216 | 5312 | `DistanceBetweenDifferentObjectives` | mode 5 / value `2000.0f` |
| +1416 | 5512 | `ZDistanceBetweenObjectivesOverride` | mode 5 / value `-1.0f` |
| +1616 / +1620 | 5712 / 5716 | 同区 / 异区距离运行期缓存 | `2000.0f` / `2000.0f` |
| +1628 | 5724 | 异区半径 R 的运行期缓存（FUNC_INDEX §5.13） | — |
| +1632 | 5728 | `DesiredStateSetObjects`（TArray；Num@+1640 = 协调器 5736） | 空 |

合计 `1632 + 16 = 1648B`，正好接到 `GoToUsableDeviceText@5744`。

依据：`sub_1402AF2D0` 读 `+4088&1`、`+3840`、`+3848`、`+4096`，盐 `L"Item Spawner"`（`0x1466F52CE`，
crc32 = `0xFB1A1645`）；`sub_140701C40` 读 `a1+1005/+1008/+1208/+1216` 并写 `+1616/+1620`；
`sub_1402AF990` 读 `+5736`（= setup+1640）。字段表 `0x145CC8AC8` 见 FUNC_INDEX §5.13。

## 5. BP 侧

| BP 类 | 关系 |
|---|---|
| `SimpleQuestItem_ObjCoord_BP_C` | `SuperStruct = RBUseQuestItemsObjectiveCoordinator`（`/Script/OPP`，`paks/LD_json/.../SimpleQuestItem_ObjCoord_BP.json`） |
| `SimpleTicketBooth_CoordBP_C` | `SuperStruct = SimpleQuestItem_ObjCoord_BP_C`（`paks/LD/Coordinators/SimpleTicketBooth_CoordBP.cpp`） |
| FPC_MT02 实例 | `MT02_SimpleTicketBooth_CoordBP_Canals` / `..._Office`（`FPC_MT02_B00.json`，DesiredCount=5） |

BP 只提供默认值覆盖（`ItemSpawnerClass`、`DesiredCount=5`、`DistanceBetweenSameObjectives=1500`），
字段偏移全部落在本类 `3816..14184` 区间，二进制里没有额外的 BP 布局。

## 6. 备注

- **两个入口共用 `+4096`**：slot 14 写 `DesiredCount.ValueName`（前缀 `L"SecondaryActorRandom"`），
  slot 249→273 用盐 `L"Item Spawner"` 抽 spawner。FPC_MT02 出票机的种子公式
  （Canals `"Item Spawner"` 5/5、Office 仍有残差）若继续不闭环，slot 14 构造的
  `...SecondaryActorRandomDesiredCount` 名字链是下一条候选。
- `sub_1402AF2D0` 在 `.rdata` 被 5 张 vtable 引用（`0x14598E1D8`/`0x145999258`/`0x1459B5168`/
  `0x1459D8D68`/`0x145A17478`），是本类与 4 个兄弟协调器共用的基类实现；只有第一处属于本类主表。
- 主表 306 槽 vs 父类 293 槽：新增 13 槽全部在 293–305；次表 1 长度 10 与父类一致，次表 2 由 4 槽增至 5 槽。
- 描述符步长不固定（`0x28`/`0x30`/`0x38` 混排），扫指针比固定步长可靠；TArray 的 `Num` 在 `Data+8`。
- `sub_1402AF2D0` 没有静态 caller，完全靠 vtable 间接派发；分析时不要尝试找直接调用点。
- 派生类 `RBBlacklightDetectableQuestItemCoordinator`（size `0x4580`）的 ctor `sub_1428C6B90`
  先调本类 `sub_1409A1640`，再改主表为 `off_14598BA50`、两张次表为 `off_14598C3E0`/`off_14598C430`，
  并在 `+14200` 写接口 vtable `off_14598C450`——本类对象尾部正好是 14200，可作为尺寸封口的旁证。

## 7. 复现命令与校验结果

工作目录 = 仓库根（`TOT.exe` 所在目录），工具来自 `release/coop/tmp/`：

```powershell
python release\coop\tmp\pe_probe.py str RBUseQuestItemsObjectiveCoordinator utf16   # → .rdata 0x1466E545E
python release\coop\tmp\scan_props.py 0x145E159A0 0x145E16200                     # 34 条非 0 偏移描述符
python release\coop\tmp\vt_dump.py 0x14598D950 --diff 0x14594BE70 306             # 37 个 OVR 槽
python release\coop\tmp\vt_dump.py 0x14598E2E0 --diff 0x14594C7A0 10              # 次表 1：仅 slot 6 OVR
python release\coop\tmp\vt_dump.py 0x14598E330 --diff 0x14594C7F0 5               # 次表 2：slot 1/4 OVR
python release\coop\tmp\vt_dump.py 0x14598D950 --find 0x1402AF2D0                 # slot 273 @0x14598E1D8
```

实测闭环：

| 项 | 结果 |
|---|---|
| 类名宽串 / UClass 构造 | `0x1466E545E` / `sub_1409362E0`（`0x3778`=14200、align 8、flags `0x10000004`） |
| 属性表 | 42 条描述符 / 42 项 PropPointer（其中 34 条 `+0x24 > 0`）、NULL@`0x145E16350`，非 0 偏移与 ctor 逐项一致 |
| 尺寸封口 | 末项 `14168 + 16 = 14184`，ctor 再清 16B → `14200` |
| vtable | 父表 293 槽；本类主表 306 槽（裸扫 529 槽含邻类）；两处次表 10 / 5 槽 |
| 关键槽 | slot 273 = `sub_1402AF2D0`（`0x14598E1D8`）、slot 275 = `sub_1402AEA00` |
| UFUNCTION | `0x145E14E30` × 14 项，注册器 `sub_1427126A0`（`mov r8d,0xE`） |

`sub_1409A1640` 的 `a1+XXXX` 写入同时给出 CDO 默认值与 bool 布局，是本文偏移表最硬的证据。
