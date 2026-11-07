# RBOperatable（C++ 基类链）

> `FunParkCanal_Drop_DamageableButton_BP_RightCanal_C` 的 C++ 终端基类。本文记录类注册、对象布局、静态属性偏移、三张 vtable 与 27 项 UFunction。
> 蓝图层见 `FunPark_DamageableButton_BP_chain.md`，取证方法见 `FORENSICS_METHODS.md`。VA 基址 `0x140000000`。

## 速查表

| 项 | 值 |
|---|---|
| 反射名 | `RBOperatable` = `0x14658BBD1`，注册表项 `0x145DE93C0/93C8` |
| UClass 构造 | `sub_1409354A0`（`qword_146E71FE8` 缓存），类大小 **1608**、对齐 8 |
| UFunction 注册 | `sub_142712310` → `sub_14048DA90(..., &off_145CCA080, 27)` |
| ClassConstructor | `sub_140668E10` → `sub_140668E20`（CDO 构造，0x4D7） |
| 析构 / vptr 写回 | `sub_1433A13A0`（0x12D） |
| 主 vfptr | `&off_1459800B0` |
| 次 vfptr | `a1+560 = off_1459808E0`、`a1+1192 = off_145980980` |
| 属性描述符表 | `0x145C58E00`（`RBInteractible`，步长 0x38） |
| 父类链 | `RBInteractible`(1192) → `Actor`(560) → `Object`(40) |

## 1. 取证链

```text
ASCII "RBOperatable" 0x14658BBD1
  → xrefs → 0x145DE93C8（8 字节名字指针）
  → 同注册项 0x145DE93C0 = sub_1409354A0（UClass 惰性构造）
  → sub_14035AFB0 参数解出：size=1608、UFunction 注册回调、ClassConstructor、父类 UClass 构造
  → sub_140668E20（CDO）写 *a1=&off_1459800B0 / a1+560 / a1+1192
  → 析构 sub_1433A13A0 写回同三值并释放 a1[197]/[191]/[189]/[187]/[185]/[182]/[179]/[176]/[154]
属性名 ASCII → xrefs → 描述符 +0x24 = 偏移（步长 0x38）
```

`sub_14035AFB0` 调用参数（由 `sub_1409354A0`、`sub_140821820`、`sub_141231180` 三方对照）：

| # | 参数 | `RBOperatable` | 语义 |
|---:|---|---|---|
| 1 | 包名 | `"/"` | 父类 `Actor` 为 `L"/Script/Engine"` |
| 2 | 宽类名 | `L"RBOperatable"` | 父类分别 `L"RBInteractible"` / `L"Actor"` / `L"Object"` |
| 3 | 静态类缓存 | `&qword_146E71FE8` | `qword_146E673B8` / `qword_1470F5A78` / `qword_146F7D3A0` |
| 4 | UFunction 注册 | `sub_142712310`(27 项) | `sub_1429F2FF0` / `sub_142AC2920` |
| 5 | **类大小** | **1608** | 1192 / 560 / 40 |
| 10 | ClassConstructor | `sub_140668E10` | `sub_1429F35C0` / `sub_140C2A0B0` |
| 13 | 父类 UClass 构造 | `sub_140821820` | `sub_141231180` / `sub_14035B3C0` |
| 14 | 顶层 Object 构造 | `sub_14035B3C0` | 三个调用相同 |

## 2. 继承链与对象布局

| 层 | 类 | 大小 | UClass 构造 | CDO / ClassConstructor |
|---|---|---:|---|---|
| 1 | `UObject` | 40 | `sub_14035B3C0` | `sub_142A53290` |
| 2 | `AActor` | 560 | `sub_141231180` | `sub_140C2A0B0` |
| 3 | `ARBInteractible` | 1192 | `sub_140821820` | `sub_1429F35C0` → `sub_140669300` |
| 4 | `ARBOperatable` | **1608** | `sub_1409354A0` | `sub_140668E10` → `sub_140668E20` |

| 区间 | 内容 |
|---|---|
| `+0..560` | `UObject` / `AActor`；主 vfptr 在 `+0` |
| `+560` | 接口 vfptr #1 = `off_1459808E0` |
| `+568..1191` | `RBInteractible` 属性（§3 表） |
| `+1192` | 接口 vfptr #2 = `off_145980980` |
| `+1200..1608` | `RBOperatable` 自有属性 |
| `+1608..` | 三层蓝图类属性，运行时 `FProperty` 追加 |

`sub_140668E20` 中出现的 `a1 + N` 偏移（CDO 初始化点，可用来核对属性）：

```text
50 560 688 1192 1200 1204 1208 1216 1220 1224 1227 1232 1240 1244 1249 1252 1256
1264 1280 1288 1304 1320 1321 1336 1352 1353 1368 1384 1385 1392 1400 1408 1416
1424 1432 1440 1448 1456 1464 1472 1480 1496 1512 1528 1544 1560 1576 1592 1600
```

末点 `+1600`（8B）恰好收在类大小 1608；`+688` 与 `InteractionZoneBox` 静态偏移吻合，`+560/+1192` 是 vfptr。

## 3. 属性 + 偏移

表 `0x145C58E00` 属 `RBInteractible`（偏移全部落在 568–1104 < 1192），步长 0x38；描述符命中处 `+0x24` 即属性偏移。规则用 `RBProjectionCodeCoordinator.md` 的 `0x145D3D208/210` 校准过（69 / 3816）。

| 属性 | 描述符 VA | 偏移 | 属性 | 描述符 VA | 偏移 |
|---|---|---:|---|---|---:|
| `IsInteractible` | `0x145C58E00` | **568** | `bCanBlockSelfInteraction` | `0x145C58E68` | 1（位掩码） |
| `InteractionZoneBox` | `0x145C58EA0` | **688** | `AdditionalInteractZoneBox` | `0x145C58F00` | 696 |
| `InteractionMesh` | `0x145C58F30` | **712** | `bNPCInteractOnInvestigation` | `0x145C58F60` | 1（位掩码） |
| `MaxNumberOfInteractors` | `0x145C58F98` | 724 | `bInteruptOnInteractRelease` | `0x145C58FC0` | 1 |
| `bIgnoreCollisionWhileInteracting` | `0x145C58FF8` | 1 | `bIgnoreCollisionWithThisActorWhileInteracting` | `0x145C59030` | 1 |
| `bCanInteractWhileLookingBack` | `0x145C59068` | 1 | `bCanBeInteractedWhileMovingLargeObject` | `0x145C590A0` | 1 |
| `bDropLargeObjectOnInteraction` | `0x145C590D8` | 1 | `bCradleLargeObjectOnInteraction` | `0x145C59110` | 1 |
| `bCanBeInteractedWhileInPsychosis` | `0x145C59148` | 1 | `MinDelayBetweenInteractions` | `0x145C59180` | 736 |
| `InteractionText` | `0x145C591D0` | 744 | `PlayerInteractionData` | `0x145C591F8` | 768 |
| `NPCInteractionData` | `0x145C59228` | 848 | `CameraPitchLimit` | `0x145C59288` | 936 |
| `bCanLookBack` | `0x145C592B8` | 1 | `StartInteractionSoundEvent` | `0x145C592F0` | 952 |
| `ActionInteractionSoundEvent` | `0x145C59320` | 984 | `EndInteractionSoundEvent` | `0x145C59350` | 1016 |
| `OnInteractorChangedEvent` | `0x145C59380` | 1048 | `OnDoAction` | `0x145C593B0` | 1064 |
| `ParentInteractible` | `0x145C59410` | 1096 | **`InteractibleRootComponent`** | `0x145C59440` | **1104** |

- `InteractibleRootComponent` 由 xref `0x145C59440` + `data_read_dword(0x145C59464)=1104` 单独确认（在扫描窗口外一项）。
- `AdditionalInteractZoneBox` 在 `0x145C58ED0` 另有一项 `+0x24=0`，取 `0x145C58F00` 的 696。
- 描述符项含两个名字指针（属性名 + RepNotify 名），如 `bIsInteractible`/`OnRep_IsInteractible` @ `0x145C1FDB8/DC0`；bool 的 `+0x24` 是位掩码而非字节偏移。
- `IsInteractible` 的 RepNotify 名是 `OnRep_IsInteractive`（表 A 首项）。

### 同名属性多表辨析（按类大小挑表）

| 名字 | 命中 | +0x24 | 判定 |
|---|---|---:|---|
| `InteractibleRootComponent` | `0x145C59440` | **1104** | 本链，落在 1192 内 |
| `InteractibleRootComponent` | `0x145B9E380` | 600 | 表 B（含 `OnItemTrapped`/`SpawnedItemInfos`/`ContainerPriorityWeight`，容器类），排除 |
| `InteractionMesh` | `0x145C58F30` / `0x145B9E350` | 712 / 592 | 取 712 |
| `InteractionZoneBox` | `0x145C58EA0` / `0x145CE9880` / 代码 `sub_14068C090` | 688 | 取 688 |
| `randomSeed` | 16 处（0x145B1C508…0x145D132C8） | 0–20 | 全为结构体字段，无 1200–1608 项，非本链属性 |

## 4. vtable

`sub_140668E20` 与 `sub_1433A13A0` 同时写入，确认三个 vfptr：

| 表 | 基址 | 槽数 | 范围 | 说明 |
|---|---|---:|---|---|
| 主 vtable | `off_1459800B0` | **281** | `0x1459800B0–0x145980978` | `AActor` 主表 + 本类覆写 |
| 接口表 #1（`a1+560`） | `off_1459808E0` | 19 | 主表 slot 262 起至表尾 | 与主表共享尾部；具体接口名未确证 |
| 接口表 #2（`a1+1192`） | `off_145980980` | **245** | `0x145980980–0x145981128` | 具体接口名未确证 |

主表尾后一个 qword 为 0 作分隔；表 #2 之后同样以 0 收尾（扫表窗口内共 511 个函数指针），勿把相邻类的表并进来。

### 本类覆写槽位（按函数地址簇）

| 簇 | 表 | slot : 函数 |
|---|---|---|
| `0x1433A19xx`（`RBOperatable`） | 主表 | `0:0x1433A1900` `221:0x1433A1930` `222:0x1433A1950` `233:0x1433A1970` `234:0x1433A1990` `265:0x1433A19A0` |
| 同上 | 表 #2 | `4:0x1433A19E0` `227:0x1433A1930` `228:0x1433A1950` `239:0x1433A1970` `240:0x1433A1990` |
| `0x143618xxx`（`RBInteractible`） | 主表 | `210:0x143618990` `217:0x143618CC0` `229:0x143618D20` `239:0x143618B20` `240:0x143618A90` `241:0x143618890` `242:0x1436187A0` `243:0x1436185C0` `250:0x143618C80` `252:0x143618D40` `257:0x143618A00` `258:0x143618A50` `259:0x143619020` `260:0x143619440` `261:0x143618FC0` `264:0x143618DB0` |
| 同上 | 表 #2 | `0:0x143618F30` `1:0x143618E90` `2:0x143618E80` `3:0x143618E40` |

主表首尾：`0:0x1433A1900, 1:0x1426325B0, 2:0x14046DFC0, …, 279:0x1426325B0, 280:0x141D1BF30`。
表 #2 首尾：`0:0x143618F30, …, 243:0x14050E4E0, 244:0x14075ADD0`。

接口表 #1 完整 19 槽：

| slot | 函数 | slot | 函数 | slot | 函数 |
|---:|---|---:|---|---:|---|
| 0 | `0x1413EE490` | 7 | `0x14269EC20` | 14 | `0x1426325B0` |
| 1 | `0x143565DE0` | 8 | `0x142629270` | 15 | `0x1400011A0` |
| 2 | `0x143618DB0` | 9 | `0x143565BC0` | 16 | `0x14050E480` |
| 3 | `0x1433A19A0` | 10 | `0x1426992D0` | 17 | `0x1426325B0` |
| 4 | `0x1430126D0` | 11 | `0x1400011A0` | 18 | `0x141D1BF30` |
| 5 | `0x14269EC20` | 12 | `0x1426325B0` | | |
| 6 | `0x143565BA0` | 13 | `0x14299C440` | | |

## 5. UFunction 表

`off_145CCA080`（27 项，由 `sub_142712310` 注册；`off_145CC88E0` 是接口 2 项的另一张表）。表项步长 0x10：`{名字指针, thunk VA}`。

| 函数 | thunk | 函数 | thunk |
|---|---|---|---|
| `BP_CancelTimedReset` | `0x14390C440` | `BP_CanOperateWith` | `0x14390C090` |
| `BP_ForceCompletion` | `0x14390BE20` | `BP_ForceDesiredProgression` | `0x14390BD10` |
| `BP_ForceInteraction` | `0x14390C460` | `BP_ForceState` | `0x14390BE40` |
| `BP_GetCurrentProgressionRatio` | `0x14148CB10` | `BP_ResetCompletedState` | `0x14390BE00` |
| `BP_SetIsDenyInteraction` | `0x14390C500` | `BP_ShouldProgressShowMaxedOut` | `0x14148CAE0` |
| `DefaultTestPhysicsClearance` | `0x14390C370` | `IsCompleted` | `0x14390C420` |
| `IsCurrentlyBeingOperated` | `0x14390C5A0` | `Multicast_ForceCompletion` | `0x14390C140` |
| `Multicast_ForceState` | `0x14390BF90` | `Multicast_OnCompletedOperation` | `0x14390C180` |
| `Multicast_OnStopInteractOperatable` | `0x140B3C1A0` | `Multicast_OnTimedReset` | `0x14390C160` |
| `Multicast_ResetCompletedState` | `0x14390BEE0` | `OnRep_bStateOn` | `0x14390C2B0` |
| `OnRep_bStateOn_Callback` | `0x14390C290` | `OnRep_Completed` | `0x14390C330` |
| `OnRep_Completed_Callback` | `0x14390C310` | `OnRep_CurrentOperateTime` | `0x14390C2F0` |
| `OnRep_CurrentOperateTime_Callback` | `0x14390C2D0` | `OnRep_ForceDesiredOperateTime` | `0x14390BCF0` |
| `OnRep_IsDenyInteraction` | `0x14390C350` | | |

接口 `RBObjectiveRandomizable`（`off_145CC88E0`，`sub_1426E6990` 注册 2 项）：

| 函数 | thunk |
|---|---|
| `GetObjectiveTypeIndex` | `sub_14390B750` |
| `ShouldDiscardOtherObjectiveActorForRandomization` | `sub_14390B6A0` |

反编译这两个 thunk 可见只是 `ProcessEvent` 存根；**0x14390B/C 簇是 BlueprintEvent 派发簇，不是 C++ vtable 本类簇**（后者是 `0x1433A19xx` / `0x143618xxx`），勿混。

## 6. 备注

- 两张接口表的具体接口名未确证（`PointerOffset`/`bImplementedByK2` 属于蓝图侧接口描述，不等同于 C++ 接口 vptr）。
- 主表 281 槽中大量 `0x1426325B0` / `0x142629270` / `0x1400011A0` 是引擎通用桩（`sub_142629270` 直接 `return 0`）。
- `sub_1400456C0`（`sub_141AA1DF0(a2, a1+432, 0, 0)`）是 `RBOperatable` 与 `RBInteractible` 共用的参数 12 回调；`sub_142629270` 是共用参数 11 的空函数。
- 校验：`0x145D3D22C=69`、`0x145D3D234=3816`、`0x145C1FDDC=1`、`0x145C59464=1104`。详见 `FORENSICS_METHODS.md`。
