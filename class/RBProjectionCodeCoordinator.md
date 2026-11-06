# RBProjectionCodeCoordinator

> 类专属锚点速查。通用取证方法（PE 节表映射、xrefs、`+0x24` 规则、IDA 勾选 Unicode）不在此重复。

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.RBProjectionCodeCoordinator`（`Projections_Coordinator_BP_C` 的 `SuperStruct`） |
| 类名宽串 | `0x1466E6062` = `ARBProjectionCodeCoordinator`；反射名 `0x1466E6064` = `RBProjectionCodeCoordinator` |
| UClass 构造 | `sub_1408853B0`，类大小 `18968`，缓存 `qword_146E7BB60` |
| 属性描述符表 | `0x145D3D200–0x145D3D800` |
| 主 vfptr | `&off_145A3FA40` |

## 1. 取证链

```text
类名宽串 0x1466E6064
  → xrefs → sub_1408853B0（UClass 惰性构造）
  → 读其 sub_14035AFB0 调用的参数：构造函数指针 sub_14293D1A0
  → thunk → sub_14293D1B0（CDO 构造）
  → 函数体内写入 *a1 = &off_145A3FA40        ← vftable 入口
  → 展开该表 → 0x145A402C8 = sub_1436E7F70
```

```text
属性名（ASCII）→ 搜指向该名的 8 字节指针 → 命中处即描述符
  → 描述符 +0x24 = 属性偏移
  → 与 sub_1436E7F70 / sub_14293D1B0 里的 a1+XXXX 对照
```

## 2. 属性 + 偏移

| 属性名 | 描述符 VA | 偏移 |
|---|---|---|
| `OnPanelActiveChangedEvent` | `0x145D3D208` | 69 |
| `WrongPasscodeDamage` | `0x145D3D210` | 3816 |
| `PasscodeNumberOfDigits` | `0x145D3D240` | 4016 |
| `SpecificContainerActors` | `0x145D3D2A0` | **4216**（Num@4224） |
| `ContainerActorClass` | `0x145D3D2D0` | 4232 |
| `SpecificCodeProjectors` | `0x145D3D338` | **4240**（Num@4248） |
| `CodeProjectorActorClass` | `0x145D3D368` | **4256** |
| `PossibleClueGroups` | `0x145D3D3D0` | 4264 |
| `SpecificPanelComponentTag` | `0x145D3D400` | 4280 |
| `DecoderItemSpawners` | `0x145D3D458` | 4288 |
| `NumberOfDecoderItemSpawned` | `0x145D3D488` | 4304 |
| `SpecificObjectiveComponentTag` | `0x145D3D4B8` | 4504 |
| `GoToUsableObjectiveText` | `0x145D3D4E0` | 4512 |
| `DeliveryZoneUISettings` | `0x145D3D508` | 4536 |
| `PickupObjectiveUISettings` | `0x145D3D538` | 7304 |
| `PickupOnConveyorUISettings` | `0x145D3D568` | 10072 |
| `bShowDecoderItemIcons` | `0x145D3D598` | 1（位掩码） |
| `DecoderItemObjectiveUISettings` | `0x145D3D5D0` | 12848 |
| `bUseContainerActorsRandomization` | `0x145D3D600` | 1（位掩码）；字节 `15616` |
| `ContainerActorsRandomizationSetup` | `0x145D3D638` | **15624** |
| `bUseCodeProjectorsRandomization` | `0x145D3D668` | 1（位掩码）；字节 `17272` |
| `CodeProjectorsRandomizationSetup` | `0x145D3D6A0` | **17280** |
| `ObjectiveLargePanelInteractComponent` | `0x145D3D6D0` | 18928 |
| `DecoderItems` | `0x145D3D730` | 18936 |
| `DecoderItemsIconActors` | `0x145D3D790` | 18952 |

加粗项与 `sub_1436E7F70` 伪代码偏移精确吻合；`sub_14293D1B0` 初始化到 `+18952`、对象大小 `18968`。

注：`TArray` 的 `Num` 在 `Data+8`，故 `+4248` = `SpecificCodeProjectors.Num()`；bool 位域的 `+0x24` 是位掩码而非字节偏移。

## 3. vtable

`sub_14293D1B0` 写入的 vfptr：主 `*a1 = &off_145A3FA40`，另有 `a1+560 = off_145A40380`、`a1+568 = off_145A403D0`。

按 `.text = 0x140001000–0x145065E2D` 扫描 `.rdata` 连续函数指针段：

| 区段 | 项数 | 归属 |
|---|---|---|
| `0x145A3F2E0–0x145A3F990` | 215 | `RBPrisonGuard`（相邻类，勿混） |
| `0x145A3FA20–0x145A40370` | 299 | **本类**，主 vfptr 自 `0x145A3FA40` 起 |
| `0x145A40380–0x145A407F8` | 144 | 本类次表 |

### 本类虚函数清单（`0x1436Exxx` 簇；slot 以 `0x145A3FA40` 为 0）

| slot | 槽 VA | 函数 | 已知作用 |
|---:|---|---|---|
| 14 | `0x145A3FAB0` | `sub_1436E7AB0` | |
| 56 | `0x145A3FC00` | `sub_1436E7A20` | 取本类 UClass 做属性查找 |
| 98 | `0x145A3FD50` | `sub_1436E6DA0` | |
| 131 | `0x145A3FE58` | `sub_1436E6DA0` | |
| 171 | `0x145A3FF98` | `sub_1436E6DA0` | |
| 190 | `0x145A40030` | `sub_1436E8FD0` | |
| 219 | `0x145A40118` | `sub_1436E9320` | |
| 220 | `0x145A40120` | `sub_1436E9100` | |
| 227 | `0x145A40158` | `sub_1436E88E0` | |
| 246 | `0x145A401F0` | `sub_1436E95B0` | |
| **249** | `0x145A40208` | **`sub_1436E95F0`** | 主随机化（图案组 / 真投影器 / 密码链） |
| 261 | `0x145A40268` | `sub_1436E8240` | |
| 262 | `0x145A40270` | `sub_1436E8710` | |
| 268 | `0x145A402A0` | `sub_1436E8A30` | |
| 270 | `0x145A402B0` | `sub_1436E8960` | |
| 271 | `0x145A402B8` | `sub_1436E8A80` | |
| **273** | `0x145A402C8` | **`sub_1436E7F70`** | 前置派发（构造盐名、调收集器） |
| 277 | `0x145A402E8` | `sub_1436E7BD0` | |
| 284 | `0x145A40320` | `sub_1436E9540` | |
| 293 | `0x145A40368` | `sub_1436E8E60` | |

次表：`0x145A40730`（slot 118）= `sub_1436EA630`。

**表外成员**（非虚，需另用 call graph / 常量 xrefs 定位）：`sub_1436EA3D0`（三位密码 `Draw`）、`sub_1436E8450` / `sub_1436E8B40`（列表读取）。

## 4. 备注

- `sub_1427FD9C0` / `sub_143703530` 写 `&off_145A3F2E0`，追 `sub_140895820` 得 `L"RBPrisonGuard"`、size 1440 —— 相邻类，不是本类构造。
- 同名属性会出现在多张表：`ContainerActorsRandomizationSetup` 还命中 `0x145B64980`（偏移 12640），须按已知偏移挑表。
- 描述符步长不固定（本表 `0x30` / `0x68` 交替）；扫指针比固定步长可靠。
- `sub_1436E7F70` 无静态 caller：经 vftable 间接派发。

校验：CHJ_MT02 24/24、MHS_MT01 pick 12/12 与 code 11/11、`seed.py --selftest` 150/150。
