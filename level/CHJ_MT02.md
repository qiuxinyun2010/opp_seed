# CHJ_MT02 正向推理：seed → 投影点位 / 图案 / 密码

> 输入 `level_seed`，输出 5 个「图案 → 投影 actor → 房间 → 三位密码」。
> 类级锚点（属性偏移、vtable）与取证细节见 `../class/RBProjectionCodeCoordinator.md`；本文 §0 只列顺序，不展开。

关卡数据：`paks/MAP/Maps/CourthouseJudicial/CHJ_LD_MT02_B00.json`；静态表：`opp_seed/data/chj_mt02.json`。

## 0. 方法流程（简述）

类级取证细节（类名宽串 → UClass 构造 → CDO 构造写 vfptr → 扫 `.rdata` 函数指针得 vtable；ASCII 属性名 → 描述符 `+0x24` 得偏移）见 `../class/RBProjectionCodeCoordinator.md`，此处只列本关走的顺序。

```text
1  地图 JSON   CHJ_LD_MT02_B00.json
               → 3 个 "Type": "Projections_Coordinator_BP_C" 实例：Name / Outer / Class / Properties
               → Class → 蓝图 JSON → SuperStruct = /Script/OPP.RBProjectionCodeCoordinator
2  类分析      属性+偏移表：+17272 门控、+17280 CodeProjectorsRandomizationSetup、
               +4248 SpecificCodeProjectors.Num、+4256 CodeProjectorActorClass、
               +4264 PossibleClueGroups
               vtable 主入口 &off_145A3FA40 → 本类虚函数清单
3  回到 JSON   每实例 Properties 的关键覆盖项：CodeProjectorActorClass(A/B/C)、
               PossibleClueGroups(2/2/1)、CodeProjectorsRandomizationSetup.DesiredCount、
               DistanceBetweenSameObjectives、SpecificContainerActors
4  对位        ★ 函数清单来自 vtable；属性偏移只用来在已知函数体里核对引用，
               不靠 xrefs 到偏移反找函数
               +17280 → sub_1436E7F70(slot 273) 传给收集器
               +4248  → 决定盐名 "Objective Actors"
               +4264/+4272 → sub_1436E95F0(slot 249) 读取
5  静态分析    sub_1436E7F70 → sub_140A61C30 → sub_1402B05C0（阶段 A）
               sub_1436E95F0 + sub_1436E8B40 / sub_1436E8450 / sub_143705510 / sub_1436EA3D0（阶段 B）
               → .text 立即数 46541 / 99041 / 86549 / 38541 / 34561
               → 三段式落位 → 代入 level_seed % 1000 → 实测回归
```

## 1. 与 seed 无关的静态输入

`RandSeeded` 只掺 `level_seed % 1000`；下列全部在开局前确定。

| 项 | 值 |
|---|---|
| 盐名 | `"Objective Actors"`（CDO 无 `SpecificCodeProjectors` → `sub_1436E7F70` 走 fallback） |
| `crc32_fname("Objective Actors")` | `1040402497` = `0x3E034841` |
| `crc32_fname("PersistentLevel")` | `1275710498` = `0x4C09CC22` |
| 原语 | `crc32_fname`=`sub_141CBDC30`、`GetSeed`=`sub_140503B80`、`RandSeeded`=`sub_1402D29E0` |

三个协调器实例各自独立跑一遍全流程（各自的 base、池、setup、计数器），配额 `2+2+1 = 5`：

| 区域 | 协调器 `Name` | `GetSeed` | `base` | 池前缀 / 大小 | 图案组 `PossibleClueGroups` | 距离阈值 | 槽位 |
|---|---|---:|---:|---|---|---:|---:|
| YellowSide | `MT02_Projections_Coordinator_BP_YellowSide` | 901211921 | 1941614418 | `A` / 21 | `[Skull, Spiral]` | 1200 | 2 |
| BlueSIde | `MT02_Projections_Coordinator_BP_BlueSIde` | 776001568 | 1816404065 | `B` / 21 | `[Pentagram, Sun]` | 1200 | 2 |
| Tuto | `MT02_Projections_Coordinator_BP_Tuto` | 1098487065 | 2138889562 | `C` / 1 | `[TriangleCircle]` | 120 | 1 |

- 池 = 世界内 `CHJ_MT02_ProjectionSymbol_BP_<前缀>_*` actor，按**名字序**（`sub_1402B46B0`）。
- `GetSeed(o) = abs32((crc32_fname(name) + GetSeed("PersistentLevel")) & M32)`，Level 分支终止于 `+0`。
- 房间名/坐标是几何后处理，不参与 seed 推理。

## 2. 两个阶段的映射

```text
阶段 A  前置随机化  sub_1436E7F70 → sub_140A61C30 → sub_1402B05C0
        输入 base = crc32(盐名) + GetSeed(协调器)      ← 三段式第一式
        输出 选中的真投影器 → setup.DesiredStateSetObjects
              = CodeProjectorsRandomizationSetup(+17280) 内 +1632 = 绝对 +18912

阶段 B  主循环      sub_1436E95F0
        读 +18912 得投影器池 v107；读 PossibleClueGroups(+4264/+4272) 得图案组池
        逐槽位 i 抽「图案组 / 组内 ClueName / 真投影器 / 密码」
```

阶段 A 与阶段 B 不是流水线：各自取三段式里的式子，但 B 的数据依赖 A 的产出。

## 3. 阶段 A：投影点位

```text
base = crc32_fname("Objective Actors") + GetSeed(协调器)
pool = 本区前缀的所有机位 actor，名字序
for k = 0 .. DesiredCount-1:
    idx   = RandSeeded(base + k, |pool|, level_seed % 1000)
    actor = pool[idx]                       ← 第二式
    pool[idx] = pool[-1]; pool.pop()        ← 第三式（末尾换删）
    按 DistanceBetweenSameObjectives(A/B=1200, C=120) 从后向前剔除近邻，同样换删
```

`sub_1402B05C0` 的 `0x1402B163E` 组装 `v246 = crc32(盐) + GetSeed(a2,0)`，`0x1402B1833` 取 `v246 + 已选数`，`0x1402B1941` 换删，距离过滤 `sub_1402B3C30`。

输出写入 `+18912`，阶段 B 的 `sub_1436E8B40` 从这里读回。

> 距离剔除的删除语义是**从后向前末尾交换删除**，写成保序删除会整体错位（旧模型 17/20，本语义 20/20）。

## 4. 阶段 B：图案、重排、密码

`sub_1436E95F0` 先构造三个池：

| 局部变量 | 来源 | 内容 |
|---|---|---|
| `v108` | `sub_1436E8450` | 容器列表，数量 `v2` = 槽位数 |
| `v107` | `sub_1436E8B40` | 真投影器池（读 `+18912`；未随机化时退回 `+4240/+4256`） |
| `v105` | `sub_143705510(v105, a1+4264, a1+4272)` | 深拷 `PossibleClueGroups`，顺序 = CDO 数组序，每组含 `ClueNames[3]` |

预处理：带标记的候选先写 `GetSeed + 34561` 密码并移出池；`v44 = (|v107| - v2)/v2`，池裁剪到 `v2*(v44+1)`。本关 `2 真 / 2 容器` → `v44 = 0`，假投影分支走不到。

### 逐槽位 `i = 0 .. 槽位数-1` 的四个抽取点

| 抽取点 | 第一式 `base` / `T` | 第二式 `X` | 第三式 `F` |
|---|---|---|---|
| 图案**组** | `0` | `i + 46541` | `sub_1437055A0` 换删 |
| 组内 `ClueName` | `0` | `i + 86549` | `sub_1434BADB0` 删除 |
| **真投影器重排** | `0` | `i + 99041` | `sub_142C48E40` 换删 |
| 三位**密码** | `GetSeed(real) + GetSeed(协调器) + i` | `38541 + k` (`k=0,1,2`) | 池 `0..9` 末尾换删 |

写成公式（`salt = level_seed % 1000`，所有 `RandSeeded` 都带它）：

```text
g        = RandSeeded(i + 46541, |v105|, salt)          ; 图案组
clueName = RandSeeded(i + 86549, |ClueNames[g]|, salt)  ; 组内具体贴图
real     = v107[RandSeeded(i + 99041, |v107|, salt)]    ; 真投影器，抽后换删
base_i   = GetSeed(real) + GetSeed(协调器) + i
code_i   = Draw(base_i):
               pool = [0..9]
               for k in 0..2:
                   j = RandSeeded(base_i + 38541 + k, |pool|, salt)
                   digit[k] = pool[j]; pool[j] = pool[-1]; pool.pop()
```

`sub_140B20020(real, clueName)` 写图案，`sub_1434468F0(real, code_i)` 写密码，`sub_1436EA4F0` 绑定第 `i` 个容器；组池每轮换删已用组。

**注意**：`seed.py` 把「组 → 组内 ClueName」两层折叠成组名（`groups` 直接用 `Skull/Spiral/…`），反编译里还有 `86549` 这一层，只影响贴图变体，不影响玩家看到的图案符号。假投影分支常量 `99042+i+j` / `86550+i+j` / 假码 `GetSeed(fake)+j+(coordSeed+1+i)` 本关不生效。

## 5. 复现（`seed = 20020`）

```powershell
python opp_seed/seed.py CHJ_MT02 20020 --trace
```

| 槽 | 区域 | 图案 | 投影 actor | 密码 |
|---:|---|---|---|---|
| 0 | A | Spiral | `A3` | 752 |
| 1 | A | Skull | `A6` | 017 |
| 0 | B | Sun | `B16` | 136 |
| 1 | B | Pentagram | `B24` | 037 |
| 0 | C | TriangleCircle（教学） | `C_4` | 973 |

房间/坐标由 `CHJ_MT02_SYMBOL_COORDS` 与 `CHJ_MT02_ROOM_IN_GAME` 补齐，与 seed 无关。

## 6. 校验与边界

| 项 | 结果 |
|---|---|
| 实测回归 | 24/24（713713 / 620620 / 20020 / 135135 共 20 条 + 样本外 711711 3P 4 条） |
| `python opp_seed/seed.py --selftest` | 150/150 |

- 静态可得：全部 base、常量、池顺序、抽取与删除语义；**无自由偏移量**。
- 需运行期的只有 `level_seed % 1000`（作为 `RandSeeded` 的 salt）；`base` 与 seed 无关，故末三位相同的 seed 结果完全一致。
- 池顺序来自 CDO / 名字序；若某关候选池含运行期排除（本关没有），静态推理就不能闭环——这是与 `CHJ_MT03` 的区别。
- 两个历史坑：距离剔除写成保序删除（应换删）、漏掉主循环 `99041` 真投影器重排。
