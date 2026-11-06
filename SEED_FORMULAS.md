# Seed 随机化公式汇总

本文档整理所有已验证关卡的随机化公式，统一使用游戏术语。

## 0. 统一形式（三段式）

所有已验证关卡的抽取都落在同一个形状上。

```text
base     = Σ GetSeed(对象) + crc32(盐名)                  // 各项 32 位模加；GetSeed 项 1~2 个，盐名可缺省(=0)
seed_arg = base + 已选数 + L                             // L = 本调用点的字面量，可为 0
idx      = RandSeeded(seed_arg, |池|, level_seed % 1000)  // 抽出后 RemoveAtSwap
```

- **base 的组成逐调用点不同**，不是「盐 + 协调器」一条配方：FPI_MT01 是盐 + 1 个 GetSeed，
  CHJ_MT02 密码段是 2 个 GetSeed（无盐名），CHJ_MT02 图案段是**空 base**。完整清单见下表。
- `L` 也是**调用点**的属性：同一关的不同抽取各有各的 L
  （FPI_MT01 组洗牌 `+0/+1/+2`、组内选目标 `+4/+5/+6`；CHJ_MT02 是 46541 / 99041 / 38541）。
- `已选数` 是该协调器内部的累计计数，跨阶段连续。



各抽取点的实测组成（§0 的完整清单）：

| 关卡 / 段 | base 组成 | L | 验证 |
|---|---|---|---|
| FPI_MT01 组洗牌 / 组内选目标 | `crc32("Objective Actors")` + `GetSeed(MT01_GatherAndDeliver_Simple_BP)` | 0 / +1 | ✅ 335335 |
| FPI_MT01 图案 | `GetSeed(MT01_SingleCode_ObjCoord_BP)`，无盐名 | 0 | ✅ |
| CHJ_MT02 选机位 | `crc32("Objective Actors")` + `GetSeed(协调器)` | 0 | ✅ 24/24 |
| CHJ_MT02 图案组 / 真投影器 | **空**（base = 0） | 46541 / 99041 | ✅ 24/24 |
| CHJ_MT02 密码 | `GetSeed(机位) + GetSeed(协调器)`，两个 GetSeed、无盐名 | +38541（+k） | ✅ 24/24 |
| MHS_MT01 符号 | `crc32("Projection Actors")` + `GetSeed(协调器)` | 0 | ✅ |
| MHS_MT01 密码 | `GetSeed(符号) + GetSeed(协调器)` | +38541 | ✅ |
| CHJ_MT03 图案 / 配对 | `GetSeed(协调器)`，无盐名 | 41 / 341 | ✅ 4/4 |
| CHJ_MT03 席位 | `crc32("Objective Actors")` + `GetSeed(协调器)` | — | ❌ 未闭环 |
| TFS_MT03 阀门 | `GetSeed(协调器)`，无盐名 | 61390 | ✅ |
| RES_MT02 房间 | `GetSeed(房间)`，无盐名 | 479582 | ✅ |

旧写法里的「偏移」不是 base 的第三项：它要么是上表的 `L`（A 类，`.text` 里能搜到立即数），
要么是 `GetSeed` 多一跳（B 类，须满足 `crc32(child) = O` 或 `crc32(child) = 2^32 − 2S − O`），
要么是纯拟合（C 类，如 CHJ_MT03 的 70251）。




## 核心概念

- **`crc32(名字)`**：FName 的 CRC32（每个字符按 `[lo, hi, 0, 0]` 喂进标准 CRC32）
- **`GetSeed(对象)`**：沿 Outer 链递归：`GetSeed(obj) = |crc32(自己的名字) + GetSeed(Outer)|`，Outer 为空时 `+0`
- **`RandSeeded(种子, 池大小, level_seed)`** = `sub_1402D29E0`，返回 `[0, 池大小)` 的下标
- **RemoveAtSwap**：`pool[idx] = pool[-1]; pool.pop()`（末尾交换删除）
- **`|x|`**：32 位绝对值（`x < 0x80000000 ? x : 0x100000000 - x`）
- **`level_seed`**：关卡种子（用户输入）
- **`M32 = 0xFFFFFFFF`**：32 位截断掩码

## 标准公式（即 §0 三段式）

```
base = crc32(盐名) + GetSeed(协调器名)            // 不含偏移
第 k 次抽取: idx = RandSeeded(base + 已选数 + L, 剩余池大小, level_seed % 1000)
             选完后 RemoveAtSwap 缩小池
```


---

## FPI_MT01（3组各选1个目标）

**紧凑形式：**

```
base = crc32("Objective Actors") + GetSeed("MT01_GatherAndDeliver_Simple_BP")
```

**展开形式（GetSeed 递归展开）：**

```
base = crc32("Objective Actors") + GetSeed("MT01_GatherAndDeliver_Simple_BP")
     = crc32("Objective Actors") + |crc32("MT01_GatherAndDeliver_Simple_BP") + GetSeed("PersistentLevel")|
     = crc32("Objective Actors") + |crc32("MT01_GatherAndDeliver_Simple_BP") + |crc32("PersistentLevel") + 0||
```

抽取：

```
// 第一阶段：洗牌3个组
idx = RandSeeded(base + 0, 3, level_seed)    // 选第1个组
idx = RandSeeded(base + 1, 2, level_seed)    // 从剩2个组中选
idx = RandSeeded(base + 2, 1, level_seed)    // 最后1个

// 第二阶段：每组内选1个目标（注意是 +4/+5/+6，不是 +3/+4/+5）
idx = RandSeeded(base + 4, 第1组候选数, level_seed)
idx = RandSeeded(base + 5, 第2组候选数, level_seed)
idx = RandSeeded(base + 6, 第3组候选数, level_seed)
```

盐名 = `"Objective Actors"`，`已选数` 序列 = `0,1,2,4,5,6`（阶段2 相当于 L=+1，见 §0 组成表）。

| 环节 | 值 |
|---|---|
| `crc32("Objective Actors")` | `0x3E034841` = 1040402497 |
| `crc32("MT01_GatherAndDeliver_Simple_BP")` | `0x3D2180C0` = 1025605824 |
| `crc32("PersistentLevel")` | `0x4C09CC22` = 1275710498 |
| `GetSeed(协调器)` = `\|0x3D2180C0 + 0x4C09CC22\|` | `\|2301316322\|` → **发生翻转** → 1993650974 |
| `base` | 1040402497 + 1993650974 = **3034053471** |

```text
阶段1 组洗牌    : base+0, base+1, base+2      （池 3→2→1）
阶段2 组内选目标: base+4, base+5, base+6      （池 = 该组候选，逐抽换删）
阶段3 图案      : 换协调器！GetSeed("MT01_SingleCode_ObjCoord_BP") = 2071778403
                 seed_arg = 该 GetSeed + i，i = 0..3，L = 0
```


### 反汇编来源链（sub_1402AE7F0）

公式来自 `sub_1402B05C0` 核心引擎，调用链如下：

```
sub_1402AE7F0 (入口)
  │
  │  ① 门控: if ((coordinator+1346) & 1)        // bUseObjectiveActorsRandomization
  │
  │  ② 构造盐名字符串 "Objective Actors"（硬编码）:
  │       *(v5)      = xmmword_14665E254          // 16字节
  │       *(v5+16)   = xmmword_14665E264          // 16字节
  │       *(v5+32)   = 0                          // null结尾
  │
  │  ③ 两个分支（二选一）:
  │       sub_1402B0070(coordinator+1352, coordinator, coordinator+704, &salt)  // 按类收集
  │       sub_1402AF490(coordinator+1352, coordinator, coordinator+728, &salt)  // 显式表
  │
  └─→ sub_1402B05C0 (核心引擎)
        │
        │  ④ 算 base:
        │       if (coordinator+744 != 1 || coordinator+857)
        │           v246 = crc32_fname(salt) + GetSeed(coordinator)
        │       else
        │           v246 = crc32_fname(salt) + crc32_fname(coord_name)
        │
        │  ⑤ 抽取:
        │       idx = RandSeeded(v246 + 已选数, 剩余池大小, level_seed)
        │       RemoveAtSwap
```

**关键偏移量**（`sub_1402AE7F0` 中）：

| 偏移 | 含义 |
|---|---|
| `coordinator+1346` | `bUseObjectiveActorsRandomization`（门控） |
| `coordinator+1352` | `PrimaryActorsRandomizationSetup`（setup 结构体） |
| `coordinator+704` | `ObjectiveActorClasses`（按类收集时的类列表） |
| `coordinator+728` | 显式候选表 |
| `coordinator+744` | `ObjectiveType`（决定 base 公式分支） |
| `coordinator+857` | 分支辅助标志 |

---

## CHJ_MT02（投影机位，24/24 全中验证）

三个协调器（每区域独立）：
- `MT02_Projections_Coordinator_BP_YellowSide`（黄区，距离阈值 1200）
- `MT02_Projections_Coordinator_BP_BlueSIde`（蓝区，距离阈值 1200）
- `MT02_Projections_Coordinator_BP_Tuto`（教学区，距离阈值 120）

**分三步：先选点位，再分配图案，最后算密码。**

### 第一步：选投影机位

```
base = crc32("Objective Actors") + GetSeed(协调器名)
     = crc32("Objective Actors") + |crc32(协调器名) + |crc32("PersistentLevel") + 0||
```

池 = 该区域前缀（如 `CHJ_MT02_ProjectionSymbol_BP_A_*`）的所有 actor，按名字排序。

```
循环 count 次（count = 该区域的图案组数）：
    idx = RandSeeded(base + 已选数, 池剩余, level_seed)
    选中池[idx]，RemoveAtSwap
    距离过滤：从后向前删掉距选中点 < 阈值 的其他候选
```

### 第二步：给每个机位分配图案

对第 i 个机位（i = 0, 1, 2, ...）：

```
group_idx = RandSeeded(i + 46541, 图案组剩余, level_seed)   → 选图案组，RemoveAtSwap
real_idx  = RandSeeded(i + 99041, 机位剩余, level_seed)     → 选机位，RemoveAtSwap
```

### 第三步：算密码

```
base2 = GetSeed(机位actor) + GetSeed(协调器名) + i
digit = RandSeeded(base2 + 38541 + k, 10, level_seed)       → k = 0,1,2 三位数字
```

**三步的 base 组成各不相同**：第一步 = `盐 + GetSeed(协调器)`；第二步 base 为空（纯 `i + L`）；
第三步 = `GetSeed(机位) + GetSeed(协调器)`（无盐名）。对照 §0 组成表。

---

## DTS_MT01（面板随机化）

```
base = crc32("Objective Actors") + GetSeed(DTS_PANEL_COORDINATOR)
     = crc32("Objective Actors") + |crc32(DTS_PANEL_COORDINATOR) + |crc32("PersistentLevel") + 0||
```

偏移 = 0。

---

## MHS_MT01（投影符号，10选1）

```
base = crc32("Projection Actors") + GetSeed(协调器名) + 0
     = crc32("Projection Actors") + |crc32(协调器名) + |crc32("PersistentLevel") + 0|| + 0
```

盐名 = `"Projection Actors"`（不是 "Objective Actors"），偏移 = 0。

---

## CHJ_MT03（8选5席位，**未闭环**）

按 §0 三段式，base 只能是：

```
base = crc32("Objective Actors") + GetSeed("CHJ_MT03_RemainingBribes")
     = 1040402497 + 407305654 = 1447708151
```

`+70251` 属 **C 类拟合**，不应写进公式：

- `.text` 与 `.rdata` 内 70251（0x1126B）立即数 **0 命中**（同文档其它常量 46541/99041/61390/479582 等均 1~2 命中）；
- 「GetSeed 多一跳」的两个候选值 `crc32(child) = 70251` / `3480285737` 在 297 万对象名 + 51 万字符串字面量中均无命中；
- 原始记录下 `+70251` 仅 3/4（`0..300000` 内匹配 3 条样本的偏移有 3 个，偶然期望 1.7 个），
  4/4 依赖修改 327327 记录（`-8` → `-5`），而 CDO 权威绑定是 `-8 = BP_9`；
- 偏移 0 下，9 席中任意 8 席排列 / 9 席全排都无法同时解释 4 条原始记录 → 差异不在池顺序。

结论：正确 base 为 1447708151，缺口在**抽取序列的运行期状态**（池构成、已选数初值、
`sub_1402B4CA0` 跨协调器排除、`sub_1402B3C30` 距离过滤）。详见 `CHJ_MT03/CHJ_MT03_REA.md` §4–§5。

---

## TFS_MT03（阀门选择）

```
base = GetSeed("MT03_FirePump_ObjCoord_BP_Section" + 区)          // 没有盐名
     = |crc32("MT03_FirePump_ObjCoord_BP_Section" + 区) + |crc32("PersistentLevel") + 0||
seed_arg = base + L,  L = 61390（.text 立即数，A 类）
```

**没有盐名！** 61390 是调用点位移，不是 base 的第三项。

---

## SRR_MT02（频闪灯）

```
base = crc32("Objective Actors") + GetSeed(协调器名)
     = crc32("Objective Actors") + |crc32(协调器名) + |crc32("PersistentLevel") + 0||
```

偏移 = 0。

---

## RES_MT02（房间排序）

```
base = GetSeed(房间名)                                  // 没有盐名
     = |crc32(房间名) + |crc32("PersistentLevel") + 0||
seed_arg = base + L,  L = 479582（.text 立即数，A 类；用 RandFraction 排序）
```

**没有盐名！** 479582 同样是调用点位移。

---

## 汇总表

| 关卡 | 盐名 | base 附加项 | 调用点 L | GetSeed(协调器) | 验证 |
|---|---|---|---|---|---|
| FPI_MT01 | `"Objective Actors"` | 无 | 0 / +1 | `MT01_GatherAndDeliver_Simple_BP` | ✅ 1 样本 |
| CHJ_MT02 | `"Objective Actors"`（仅选机位段） | 密码段为 2×GetSeed | 46541 / 99041 / 38541 | 各区域协调器 | ✅ 24/24 |
| DTS_MT01 | `"Objective Actors"` | 无 | 0 | `DTS_PANEL_COORDINATOR` | ✅ |
| MHS_MT01 | `"Projection Actors"` | 无 | 0 | 各区域协调器 | ✅ |
| CHJ_MT03 | `"Objective Actors"` | **无（70251 属 C 类拟合）** | — | `CHJ_MT03_RemainingBribes` | ❌ 席位未闭环 |
| SRR_MT02 | `"Objective Actors"` | 无 | 223551 / 243551 / 253526 | 各区域协调器 | ✅ |
| TFS_MT03 | **无** | 无 | 61390 | `MT03_FirePump_ObjCoord_BP_Section` + 区 | ✅ |
| RES_MT02 | **无** | 无 | 479582 | 各房间名 | ✅ |

## 关键结论

1. **标准模式**：`base = Σ GetSeed(对象) + crc32(盐名)`（GetSeed 项 1~2 个、盐名可缺省），
   `seed_arg = base + 已选数 + L`；三项都按**调用点**取，没有全关卡通用的常数
2. 旧文档里的「偏移」应拆成三类（见 §0）：**A 调用点字面量**（46541/99041/38541/61390/479582 等，
   `.text` 有立即数）、**B GetSeed 多一跳**（需满足 `crc32(child) = O` 或 `2^32−2S−O`，目前 0 例）、
   **C 拟合**（70251，无立即数、无对象名对应）
3. **盐名**可以是 `"Objective Actors"`、`"Projection Actors"`，甚至**没有盐名**（直接 `GetSeed + 常量`）
4. **GetSeed 的 Outer 链**统一为 `PersistentLevel → 协调器名`
5. **抽取**统一为 `RandSeeded(base + 已选数 + L, 池大小, level_seed)` + RemoveAtSwap

---

## FPC_MT02（待破解）

**推测公式（按 §0 三段式）：**

```
base = crc32("Item Spawner") + GetSeed("MT02_SimpleTicketBooth_CoordBP_Canals")
     = crc32("Item Spawner") + |crc32("MT02_SimpleTicketBooth_CoordBP_Canals") + |crc32("PersistentLevel") + 0||
seed_arg = base + 已选数 + L,  L = ???（优先在 .text 里找立即数，而不是拟合）
```

抽取：

```
idx = RandSeeded(base + 0, 41, level_seed)    // 从41个候选中选第1个
idx = RandSeeded(base + 1, 40, level_seed)    // 从剩40个中选第2个
idx = RandSeeded(base + 2, 39, level_seed)    // 从剩39个中选第3个
idx = RandSeeded(base + 3, 38, level_seed)    // 从剩38个中选第4个
idx = RandSeeded(base + 4, 37, level_seed)    // 从剩37个中选第5个
```

**未确定**：偏移 `???`（可能非零），盐名是否正确（`"Item Spawner"`），以及分类趟（`bForceUseObjectiveInRandom`）是否改变候选池。

### 反汇编来源链（sub_1402AF2D0）

与 FPI_MT01 的 `sub_1402AE7F0` 完全同构：

```
sub_1402AF2D0 (入口)
  │
  │  ① 门控: if ((coordinator+4088) & 1)        // bUseSpawnerActorsRandomization
  │
  │  ② 构造盐名字符串 "Item Spawner"（硬编码）:
  │       xmmword_1466F52CE + xmmword_1466F52DE
  │
  │  ③ 两个分支（二选一）:
  │       sub_140A61C30(coordinator+4096, coordinator, coordinator+3840, &salt)  // 按类收集
  │       sub_1402AF490(coordinator+4096, coordinator, coordinator+3848, &salt)  // 显式表
  │
  └─→ sub_1402B05C0 (同一个核心引擎)
        │
        │  ④ 算 base: v246 = crc32_fname(salt) + GetSeed(coordinator)
        │  ⑤ 抽取:   idx = RandSeeded(v246 + 已选数, 剩余池大小, level_seed)
```

**关键偏移量**（`sub_1402AF2D0` 中）：

| 偏移 | 含义 | 对比 FPI_MT01 |
|---|---|---|
| `coordinator+4088` | `bUseSpawnerActorsRandomization`（门控） | FPI 是 +1346 |
| `coordinator+4096` | `SpawnerActorsRandomizationSetup`（setup） | FPI 是 +1352 |
| `coordinator+3840` | `ItemSpawnerClass`（按类收集的类） | FPI 是 +704 |
| `coordinator+3848` | 显式候选表 | FPI 是 +728 |
| `coordinator+744` | `ObjectiveType`（决定 base 公式分支） | 同 FPI |

**核心引擎 `sub_1402B05C0` 是同一个**，公式结构应该完全一致。差异可能在 GetSeed 的 Outer 链或分类趟行为。
