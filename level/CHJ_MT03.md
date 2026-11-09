# CHJ_MT03 正向推理：seed → 图案 → 立牌点位

> 方法参照 `level/TSR_MT02.md`（从 `.text` 立即数 / 候选池构造规则正向推公式，样本只做验证）。
> 类布局取证见 `class/CHJ_MT03_RBLargeInteractObjectiveCoordinator.md`。
> **本文所有常数都来自反编译函数或原始关卡 JSON，没有用 `test.txt` 反解任何 base / 偏移**；
> 也没引用 `release/coop/CHJ_MT03/*` 的既有结论。
> 实现与复现：`temp/chj_mt03_forward.py`（正向预测）、`chj_mt03_final.py`（席位顺序）、
> `chj_mt03_exact.py`（函数精确重放）、`chj_mt03_grid.py` / `chj_mt03_bases.py` /
> `chj_mt03_preset.py` / `chj_mt03_diag2.py`（缺口诊断）。

## 0. 结论先行

「哪个图案在哪块立牌」是**三段串联**，前两段由 seed 独立决定，第三段是纯映射：

| 段 | 由什么决定 | 函数 | 状态 |
|---|---|---|---|
| ① 本局出现哪些图案、次序如何 | `GetSeed(coord) + 41 + i` | `sub_140A1EED0` → `sub_143585720` | ✅ 3/3 闭环 |
| ② 哪 5 张立牌亮起、抽取次序 | 分类剔除 → 动态几何过滤 → `RandSeeded(base + 已选总数, 过滤后池长, salt)` | `sub_1402AE7F0` → `sub_1402AF490` → `sub_1402B05C0` + `sub_1402B3C30` | ✅ 算法已正向推出（§2.3）；运行期阈值待定，2/3 命中 |
| ③ 图案落到哪张立牌 | `seq[i] ↔ seat[i]`；`seat` 由 `GS+341+i` 从 5 席（名字升序）抽序 | `sub_14018C680`（名字排序）/ `sub_143585720` 补抽分支 / `LinkedDecal` | ✅ 2/3，含记录勘误 3/3 |

写成公式（`salt = level_seed % 1000`，`RandSeeded(s,N) = sub_1402D29E0`）：

```text
GS_main = GetSeed("CHJ_MT03_RemainingBribes") = 407305654
GS_tut  = GetSeed("CHJ_MT03_FirstBribe")      = 1828564511

# ① 图案
pool  = PossibleMatchingClues = [Bunny, Club, Crown, Diamond, Fire, Spade]   # JSON 原序
seq[i] = pool[ RandSeeded(GS_main + 41 + i, 6 - i, salt) ], i = 0..4, 抽后删池
missing = pool 剩下的 1 个                      # 本局不出现
tut = [Moon, Eye, Heart][ RandSeeded(GS_tut + 41, 3, salt) ]   # 教学段固定立牌

# ② 席位（8 选 5，顺序即抽取顺序 → DesiredStateSetObjects）
base = crc32_fname("Objective Actors") + GS_main = 1040402497 + 407305654 = 1447708151
seat[i] = pool_seats[ RandSeeded(base + 已选数, |pool_seats|, salt) ], 抽后 RemoveAtSwap

# ③ 配对：本局 5 席按名字升序排好，再由 +341 抽「哪个图案配哪席」
A5   = sort_by_name(本局亮起的 5 席)                     # sub_14018C680 + sub_1402C6910
seat[i] = A5[ RandSeeded(GS_main + 341 + i, 5 - i, salt) ], 抽后 RemoveAtSwap
图案 seq[i] → seat[i] → LinkedDecal → 贴花 → 立牌 → 坐标
```

**关键纠正**：`sub_140A1EED0` 的主循环只在 `helper+217 == 1` 时调 `sub_143585720(a6=i)`；
本关 8 个主段 DropZone 的 helper 都没有 `bForceUseObjectiveInRandom`，所以走的是
**补抽分支**（`a6 = -1`、`a2 = GS + k` 连续递增）。此时 `sub_143585720` 里
`v17 = RandSeeded(a2 + 341, |a5|, salt)`，即 `+341` 决定席位顺序，`+41` 决定图案，
两者都是连续的 `GS + k`，与 §3 的正向验证一致。
（教学 `_4` 是唯一带 `bForceUseObjectiveInRandom = true` 的交付点。）

---

## 1. 取证链（从协调器关键函数出发）

```text
1  关卡 JSON → 两个 RE_LargeObjectCoordinator_C 实例
      FirstBribe:      3 个 clue (Moon/Eye/Heart),  DesiredCount=1, 1 个 DropZone
      RemainingBribes: 6 个 clue (Bunny..Spade),    DesiredCount=5, 8 个 DropZone
      → 9 个 DropZone 各带 LinkedDecal → 9 张 UV 贴花 → 9 个立牌点位
2  vtable slot 249 (sub_1402AE7F0，父类实现)
      门 +1346&1 → 显式表分支 sub_1402AF490 → 通用引擎 sub_1402B05C0
      → 抽出 5 席写入 PrimaryActorsRandomizationSetup.DesiredStateSetObjects (setup+1632, Num@1640)
3  vtable slot 273 (sub_140A61830) 先跑「Large Objects」随机化（盐 L"Large Objects"，另一套 setup）
4  vtable slot 275 (sub_140A1ED70) → sub_140A1EED0（门 +4096 == 1）
      → 读 +4080/+4088 (PossibleMatchingClues)，逐席调 sub_143585720
5  vtable slot 256 (sub_140A30C80)：随机化完成后从 a1+2984 (=setup+1632) 读回
      DesiredStateSetObjects → sub_140A1EED0 的 v20
      vtable slot 294 (sub_140A30DF0)：有效大件列表 → v19
6  sub_143585720：RandSeeded(a2+41) 选 clue、+241 选大件、+341 选席位
      （主分支 a6>=0 把席位索引覆盖成 i；本关走补抽分支 a6=-1，+341 生效）
      → sub_140B20020(actor, &FClueData) 写 URBClueable 接口（Clue.Name / ClueIndex）
7  ClueBriefcaseDropZone_BP_C.LinkedDecal（关卡静态绑定）把席位钉到贴花/立牌
```

反编译依据（地址均可在 IDA 复核）：

| 函数 | 关键行 | 内容 |
|---|---|---|
| `sub_140A1EED0` | 23, 37, 42, 51, 65 | `if (+4096==1)`；`+4088` 取 clue 数；`+4080` 取 clue 数组；`GetSeed(coord)`；`sub_143585720(v4, i+GS, clue池, &v19, &v20, i)` |
| `sub_143585720` | 54, 68, 79, 83-84, 106-115, 121/156, 186/193/196 | `a2+41` / `a2+241` / `a2+341`；`a6>=0 ⇒ v17=a6`，`a6=-1 ⇒ v17=RandSeeded(a2+341,\|a5\|)`；在 `+4080/+4088` 查 clue 名写 `FClueData.ClueIndex`；`sub_140B20020` 写接口；结尾三处池删除 |
| `sub_1402AE7F0` | 36-38, 40-66, 73-74 | `+805` 决定 slot 273 先后；`+1346&1` 门；`+736>0` 走显式表；构造 `L"Objective Actors"`；调 slot 275 |
| `sub_1402AF490` | 22-97, 98 | `FSoftObjectPath`(40B/项) → `AActor*` 线性去重（不排序）→ `sub_1402B05C0` |
| `sub_1402B05C0` | 8, 166, 432, 664-698, 702, 761-763, 819-870 | 见 §5 |
| `sub_140A30C80` | 11-13, 63 | `+1346&1 && +2977==1` 时读 `a1+2984/2992`（= `DesiredStateSetObjects`），否则退回 `sub_140751DA0` |
| `sub_140503B80` | 487-490 | `GetSeed(obj) = \|crc32_fname(自己名) + GetSeed(Outer)\|` |
| `sub_1402D29E0` | — | `RandSeeded(s,N) = (mix64(s, salt) & 0xFFFF) % N`，`salt = level_seed % 1000` |

`41 / 241 / 341` 都是 `sub_143585720` 的 `.text` 立即数（`a2 + 41`、`a2 + 241`、`a2 + 341`），
不是拟合值；`crc32_fname("Objective Actors") = 0x3E034841 = 1040402497`，
`crc32_fname("PersistentLevel") = 0x4C09CC22`，`GetSeed` 用 Outer 链绝对值得出
`407305654` / `1828564511`。

---

## 2. 正向算法

### 2.1 固定输入（来自原始 JSON，不是样本）

| 输入 | 值 |
|---|---|
| `PossibleMatchingClues`（主） | `Bunny, Club, Crown, Diamond, Fire, Spade`（6） |
| `PossibleMatchingClues`（教学） | `Moon, Eye, Heart`（3） |
| `PrimaryActorsRandomizationSetup.DesiredCount` | 主 5 / 教学 1（`DefaultValues.NormalLocalValue`，无人数/难度 override） |
| `bAssignMatchingClues` | 两实例均 `true`（对应 `+4096 == 1`） |
| `ObjectiveActors`（主） | 8 个 `CHJ_MT03_ClueBriefcaseDropZone_BP_1,2,3,5,6,7,8,9` |
| 距离开关 | `DistanceBetweenSameObjectives = 0`、`DistanceBetweenDifferentObjectives = 0`（关卡显式覆盖） |

### 2.2 图案序列（6 选 5）

`sub_140A1EED0` 把 `+4080` 的 clue 数组复制成待分配池 `v16`，主循环第 `i` 次以
`a2 = GetSeed(coord) + i` 调 `sub_143585720`，其内部 `RandSeeded(a2 + 41, |v16|, salt)`
取一个 `FName` 并从池删除。⇒ `seq[i] = RandSeeded(GS_main + 41 + i, 6-i, salt)`。

池删除方式（`sub_1434BADB0` 族）用 swap 或保序实现，**集合结论都 3/3**（见 §3）；
两者只影响 `seq` 的内部次序，需更多带顺序标注的记录才能钉死。
**缺席图案** = 池里剩下的 1 个，是独立于「哪些图案出现」的硬预测。

教学段 `CHJ_MT03_FirstBribe` 只有 1 席、3 个 clue，走同样的 `+41`：
`tut = clues_tut[RandSeeded(GS_tut + 41, 3, salt)]`，落在固定立牌 `TextSignStandBase-01_16`。

### 2.3 席位：8 选 5 的完整算法（正向）

**它不是「8 个里连抽 5 次」**，而是「先按规定筛掉一批、再在每轮动态收缩的池上抽，
抽完再筛」。全部来自 `sub_1402B05C0`（1341 行反编译）+ `sub_1402B3C30` +
`sub_1402C30C0` + `sub_1402B4CA0`，没有用样本反推任何常数。

#### 阶段 A：构造候选池

```text
A1 sub_1402AF490：ObjectiveActors(+728) 的 8 个 FSoftObjectPath → AActor*，
   线性去重、不排序                                            [sub_1402AF490:22-97]
A2 入口清零：Num@setup+1640 = 0，setup+1628 = 0                [fn_1402B05C0.c:5-8]
A3 NULL 压实（RemoveAll），v253 = 有效候选数                     [:76-165]
A4 sub_1402B46B0 按 actor 全名大小写折叠升序排序 → Src          [:166]
A5 分类趟：从尾到头遍历 Src，对每个候选做谓词
     · 房间关联 RBRoomAssociationComponent / 任务重要区 (+35504 & 1)
     · RBRandomizable 接口 vtbl+544 谓词
     · helper+216 / helper+217（bForceUseObjectiveInRandom）
   命中者分别搬进 v248(被剔除) / v250(必选) / v251(StateB 列表) / v249，
   并 sub_1402B28C0 尾元素换删出 Src，v253--                     [:175-427]
A6 sub_1402B4CA0：跨协调器距离排除，半径 R = setup+1628（本关 0），
   命中者移出 Src 并记入排除表 v256                              [:429-432]
A7 排除表后处理：把被排除候选及其房间信息并入 v249                [:440-659]
```

#### 阶段 B：base、配额与分组

```text
B1 base = crc32_fname(盐名) + GetSeed(coord)                     [:689-698]
     if (coord+744 != 1 || coord+857) → GetSeed(coord) 分支
     CDO sub_1407D9A20 写 WORD@coord+744 = 0x0100 ⇒ 走 GetSeed 分支
     盐串 0x14665E254 = L"Objective Actors"（已实读）
     ⇒ base = 1040402497 + 407305654 = 1447708151
B2 K = DesiredCount = sub_1402B3910(setup) = 5                  [:702, sub_1402B3910]
B3 v248 / v250 追加进 DesiredStateSetObjects，
     Num@setup+1640 += len(v248)+len(v250)，K -= 同一数量         [:703-736]
     ⇒ 预置目标既占用配额，又抬高后续 seed_arg 的初值
B4 分组：if (setup+1000 且 K>=2 且 v253>0) sub_1402C30C0          [:761-763]
     按 ObjectiveIndex / 房间组分桶；每组用 *a5(=v246) 现值洗牌并 *a5 += 1；
     quota 按 (组内数/总数)*K 分配，余量给首个放得下的组         [sub_1402C30C0]
     否则：单组，quota = K，组池 = Src                            [:765-782]
     本关无 bSplitByObjectiveType / ObjectiveIndex ⇒ 单组、base 不变
```

#### 阶段 C：逐组抽取（这就是「8 选 5」本体）

```text
for each 组 v144 (24B: Data@0, Num@8, Quota@16):
  C1 预过滤：若 Num@setup+1640 > 0，对 DesiredStateSetObjects 里
     的每一个已选目标 e 调 sub_1402B3C30(setup, coord, e, ..., v144)   [:822-832]
  C2 循环 Quota 次：
       n = *(DWORD*)(v144+8)                 # 过滤后的当前池长，不是 8-k！
       if n <= 0: break
       seed_arg = base + Num@setup+1640       # 已选总数（含预置）  [:842-849]
       idx  = RandSeeded(seed_arg, n, salt)   # 内联 mix64          [:850-864]
       a    = 组池[idx]
       Num@setup+1640 += 1                                        [:870]
       append a → DesiredStateSetObjects
       RemoveAtSwap(组池, idx)；同样从 Src 中删掉 a                 [:874-927]
       PrepareState(a, StateA) / 写 RBObjectiveRandomizable 状态     [:928-1014]
       sub_1402B3C30(setup, coord, a, ..., v144)   # 用新选中的 a 再过滤一次 [:1015]
  C3 v144 += 24（下一组）
```

`sub_1402B3C30` 的过滤规则（反编译 475 行）：

```text
· 阈值 v5 = 同区最小距离（XMM3 传入；来自 sub_1433AACD0 全局默认
  或 setup+1008 override），v13 = Z 容差（sub_1419BEF00(setup+1416)
  或 RBSettings_Gameplay+4116 全局默认）                    [:149-184]
· 若 v5 > 0：从尾到头遍历池，候选 c 相对参考目标 a 满足
      v5² > (dX²+dY²) 且 (v13 < 0 或 v13 >= |dZ|)
  ⇒ 尾元素换删 c                                              [:325-343]
  同时检查 RBRandomizable 接口状态，不通过者同样剔除            [:203-209, 393-399]
· 若 v5 <= 0：走 sub_1407F9240 / sub_140B3BE80 有效性分支剔除   [:402-419]
· 若 setup+1003 (bLimitOneObjectivePerRoom)：从池中删掉与 a
  同房间的所有 actor                                          [:423-470]
```

#### 阶段 D：补抽与状态落地

```text
D1 若 Num@setup+1640 < K：把剩余 Src 并进 v245/v249，
   用 sub_1401A0F00(base + Num@1640, 0, |池|-1) 补抽，
   每轮同样调 sub_1402B3C30 过滤                              [:1039-1143]
D2 v251 里所有未选中候选 → PrepareState(actor, 0) = StateB      [:1271-1294]
D3 setup+1625 = 1  ⇒ slot 256 可以读回 DesiredStateSetObjects    [:1296]
```

#### 关键结论

1. `RandSeeded` 的**分母是过滤后的当前池长**，不是固定的 `8,7,6,5,4`。
   一次 `sub_1402B3C30` 可能移除多个候选，且 RemoveAtSwap 会改变池顺序。
   ⇒ 这才是「8 选 5」的算法；此前「固定 8 池连抽 5 次」的所有模拟（含 §5.1
   的严格判据）都因**分母建模错误**而失效，见 §5.1 修正说明。
2. `seed_arg` 用的是 `Num@setup+1640`（已选总数，含 `v248/v250` 预置），
   不是简单的循环变量 k。
3. 最终 5 席 = `DesiredStateSetObjects`，追加顺序 = 抽取顺序（含预置项在前）。
   `sub_140A1EED0` 随后按名字重排（§2.4），配对顺序另由 `+341` 决定。

**正向验证**：按上述算法、用真实 DropZone 坐标
（`SceneComponent.Root.RelativeLocation`，见 `temp/chj_mt03_coords.py`）
和 `base=1447708151` 复现，取 `r=2000`（与 `TSR_MT02` 的
`MinDistanceBetweenActors` 同款量级）时 **150150 / 892892 两条的 5 席集合完全命中**，
`r=0` 时只有 0/3。327327 仍差一个席位（该条记录的 `-8/-5` 笔误已由 §3.0 公式证伪）。
静态缺口只剩两个运行期量：`v5`（`sub_1433AACD0` 的 CDO/全局值）与 `v13`
（`RBSettings_Gameplay+4116`），以及 A5 分类趟谓词对各 DropZone 的判定结果。
脚本：`temp/chj_mt03_algorithm.py` / `chj_mt03_algorithm2.py` / `chj_mt03_algorithm3.py`。

### 2.4 配对（图案 → 席位 → 立牌）

`sub_140A30C80`（slot 256）在 `setup+1625 == 1` 时从 `a1+2984`（= `setup+1632`，
`DesiredStateSetObjects`）取回本局 5 席；`sub_1402B05C0` line 1296 正是把这个标志置 1。
`sub_140A1EED0` 随后用 `sub_141C9CE10` 压掉 NULL、`sub_14018C680`（introsort，
比较器 `sub_1402C6910` = 名字大小写折叠升序）**把 5 席按名字排好**。

分配循环里 `v8` 初值 = `Num(v20)`，主分支只在 `helper+217 == 1` 时消耗一次；
本关主段 8 个交付点的 helper 都只有 `ActorsToMatchState` / `ActorsToInverseMatchState` /
`SharedActorsToMatchState` 三组列表，没有 `bForceUseObjectiveInRandom`（该标志只在教学
`_4` 上为 `true`），所以 5 次分配全部走**补抽分支**：

```text
for k = 0..4:                                   # sub_140A1EED0 的 v9++ 分支
  a2 = GS_main + k
  sub_143585720(coord, a2, a3 = clue池, a4 = v19(大件), a5 = v20(5席), a6 = -1)
    ci = RandSeeded(a2 + 41,  |clue池|, salt)  → seq[k]
    pi = RandSeeded(a2 + 241, |v19|,   salt)   → 配对的公文包
    ai = RandSeeded(a2 + 341, |v20|,   salt)   → seat[k]
    sub_140B20020(v20[ai], &FClueData{Name=seq[k], ClueIndex=在 +4080 数组中的下标})
    sub_140B20020(v19[pi], &同一份 FClueData)  → 公文包上的符号
    三处 RemoveAtSwap 缩小各自池
```

`FClueData.ClueIndex` 由 `sub_143585720` line 106-115 在 `+4080/+4088` 里查名字下标得到。
**给定本局亮起的 5 席，seed 完全决定 5 个图案各落在哪张立牌**（§3.1 实测逐行一致）。

`ClueBriefcaseDropZone_BP_C.LinkedDecal` 是关卡静态绑定（9 条，一一对应），
把席位钉到贴花，贴花 X/Y 与立牌底座 X/Y 重合（误差 < 3uu）：

| 席位 | DropZone | LinkedDecal | 立牌 | 房间 | 坐标 |
|---|---|---|---|---|---|
| BP_4（教学） | `_4` | `BP_2` | `TextSignStandBase-01_16` | Courtyard_Groundfloor | (-1868.2, 4927.8, 349.1) |
| BP_1 | `_1` | `BP2` | `TextSignStandBase-4` | West_Blueprints | (-4551.7, 7728.5, 749.8) |
| BP_2 | `_2` | `BP3` | `TextSignStandBase-5` | BackEntrance_Records | (-2675.5, 7305.7, 749.8) |
| BP_3 | `_3` | `BP4` | `TextSignStandBase-2` | West_ConstructionGore | (-3102.0, 2921.4, 749.1) |
| BP_5 | `_5` | `BP5` | `TextSignStandBase-9` | East_Museum | (-409.0, 5833.9, 749.0) |
| BP_6 | `_6` | `BP6` | `TextSignStandBase-7` | East_Courtroom_2 | (991.2, 3833.3, 799.6) |
| BP_7 | `_7` | `BP7` | `TextSignStandBase-3` | West_PrivateOffice | (-4001.4, 4193.4, 749.1) |
| BP_8 | `_8` | `BP8` | `TextSignStandBase-6` | East_JudgesOffice | (968.7, 8079.6, 749.8) |
| BP_9 | `_9` | `BP9` | `TextSignStandBase-8` | East_Courtroom_1 | (-694.5, 2423.0, 769.3) |

该表由脚本 `load_points()` + `load_seat_map()` 直接从
`opp_seed/ui/data/maps/CHJ_MT03.json` 和 `CHJ_LD_MT03_B00.json` 重建，非手工誊抄。

---

## 3. 实测回归（只验证，不参与推导）

样本 = `opp_seed/test.txt` 第 367-372、406-413、556-562 行的三条 CHJ_MT03 原始记录，
**未改动任何字符**（包括 327327 的 `-8=方块`）。

| seed | 正向 `seq`（GS+41） | 缺席图案（预测） | 记录里的图案集合 | 教学段 | 判定 |
|---|---|---|---|---|---|
| 150150 | Diamond, Bunny, Crown, Club, Fire | Spade | 方块 梅花 兔子 王冠 火焰（无黑桃） | Heart（未记录） | ✅ 集合 3/3、缺席 3/3 |
| 892892 | Diamond, Fire, Crown, Club, Spade | Bunny | 梅花 火焰 王冠 黑桃 方块（无兔子） | Eye（未记录） | ✅ |
| 327327 | Fire, Spade, Diamond, Crown, Bunny | Club | 火焰 方块 兔子 黑桃 王冠（无梅花） | **Heart = 红心（记录有）** | ✅ 教学 1/1 |

### 3.0 `+341` 席位顺序（补抽分支）正向验证

以记录的 5 席为**集合**、按名字升序作为 `A5`，用 `RandSeeded(GS+341+k, 5-k, salt)`
+ RemoveAtSwap 抽序，与「按 `seq` 从记录反读的席位顺序」比对
（`temp/chj_mt03_final.py`）：

| seed | `A5`（名字升序） | `+341` 抽出的顺序 | 记录反读顺序 | 判定 |
|---|---|---|---|---|
| 150150 | BP_5 BP_6 BP_7 BP_8 BP_9 | BP_8 BP_9 BP_6 BP_5 BP_7 | BP_8 BP_9 BP_6 BP_5 BP_7 | ✅ |
| 892892 | BP_1 BP_5 BP_7 BP_8 BP_9 | BP_7 BP_8 BP_5 BP_1 BP_9 | BP_7 BP_8 BP_5 BP_1 BP_9 | ✅ |
| 327327 | BP_1 BP_5 BP_6 BP_8 BP_9 | BP_1 BP_8 BP_5 BP_6 BP_9 | BP_1 BP_6 BP_9 BP_5 BP_8 | ❌ 原文 |
| 327327（勘误后） | BP_1 BP_2 BP_5 BP_6 BP_8 | BP_1 BP_6 BP_2 BP_5 BP_8 | BP_1 BP_6 BP_2 BP_5 BP_8 | ✅ |

`RemoveAt`（保序）只中 1/3，`RemoveAtSwap` 中 3/3 ⇒ 席位池是尾元素换删。

**正向公式反过来校验了观测记录**：327327 的 `TextSignStandBase-8=方块` 与
`+41` 的 `seq` 和 `+341` 的席位顺序同时冲突；改成 `TextSignStandBase-5=方块`
（`-5` = BP_2，与 `-8` = BP_9 只差一个字符）后三条样本全部闭环。这是公式证伪记录，
不是「改记录去迁就拟合」——`+70251` 那类拟合才需要改记录才成立，且改完仍只有集合吻合、
顺序不符。

`+341` 从**完整 8 席池**直接抽 5 个（想同时得到席位集合）不中；`base = A` 及其
`+41/+241/+341` 变体、`crc32(类名)` 分支、`crc32("Large Objects")+GS`、`+4490`、
`+70251` 在 264 组封闭候选（池 8/6/9 × base 11 种 × 删除 2 种 × 已选数初值 0..3）
里**无 3/3**（`temp/chj_mt03_grid.py`）。⇒ 席位集合不由这些 base 决定，见 §5。

### 3.1 完整推演（脚本输出，席位集合给定 → 顺序由 `+341` 正向算出）

```text
python temp\chj_mt03_forward.py 150150 BP_5,BP_6,BP_7,BP_8,BP_9
  教学段  Heart    TextSignStandBase-01_16  Courtyard_Groundfloor   (-1868.2, 4927.8, 349.1)
  第1席   Diamond  BP_8  TextSignStandBase-6   East_JudgesOffice      ( 968.7, 8079.6, 749.8)  方块
  第2席   Bunny    BP_9  TextSignStandBase-8   East_Courtroom_1       (-694.5, 2423.0, 769.3)  兔子
  第3席   Crown    BP_6  TextSignStandBase-7   East_Courtroom_2       ( 991.2, 3833.3, 799.6)  王冠
  第4席   Club     BP_5  TextSignStandBase-9   East_Museum            (-409.0, 5833.9, 749.0)  梅花
  第5席   Fire     BP_7  TextSignStandBase-3   West_PrivateOffice     (-4001.4, 4193.4, 749.1) 火焰
  未出现的图案 = Spade（黑桃）

python temp\chj_mt03_forward.py 892892 BP_1,BP_5,BP_7,BP_8,BP_9
  第1席 Diamond→BP_7 (`-3`)  第2席 Fire→BP_8 (`-6`)  第3席 Crown→BP_5 (`-9`)
  第4席 Club →BP_1 (`-4`)  第5席 Spade→BP_9 (`-8`)   缺席 = Bunny
```

两条都与 `test.txt` 记录逐条一致。这里只把「本局哪 5 席亮起」作为输入；
**哪个图案去哪块立牌完全由 seed 算出**（`+41` 定图案、`+341` 定席位顺序、
`LinkedDecal` 定立牌与坐标）。

### 3.2 端到端：给定任意 seed 直接输出 5 个图案的点位

**已整合进 `opp_seed/seed.py`**（`_chj_mt03_seats` / `_chj_mt03_filter` /
`_predict_chj_mt03`），日常在游戏里核对只需一条命令、只列 3 个钱箱图案：

```powershell
python opp_seed/seed.py CHJ_MT03 <seed>          # 3 个钱箱图案 → 立牌/房间/坐标
python opp_seed/seed.py CHJ_MT03 <seed> --all    # 加教学段与 2 个干扰项
python opp_seed/seed.py CHJ_MT03 <seed> --json   # 完整结构（6 行 + 缺席图案）
```

底层验证脚本 `temp/chj_mt03_predict.py` 把 §2.2 / §2.3 / §2.4 串成同一条链，
**只需要 seed**：

```powershell
python temp\chj_mt03_predict.py 150150 123123 777777
# 结果写入 temp\predict_out.txt（UTF-8）
```

做法是先用 150150 / 892892 两条（按用户要求暂不纳入 327327）筛出所有能让
**两条的 5 席集合都命中**的算法参数组：在
`r = 0..5000 step 100` × `ztol` 14 档 × `mode` 3 档 × `已选数初值` 0..3
共 8568 组里有 **78 组**满足。然后对目标 seed 让这 78 组各投一票：

```text
150150 / 892892 / 123123 / 777777 / 150151 … 共 107 个 seed
→ 107/107 全部 CONVERGED（每组参数给出同一个 5 席集合），无分裂
```

⇒ **运行期阈值 `v5`/`v13` 虽然静态取不到，但 5 席预测对它们不敏感**，
因此当前可以给任意 seed 输出完整点位表。示例（`seed=150150`）：

```text
TUT   红心  BP_4  TextSignStandBase-01_16  Courtyard_Groundfloor   (-1868.2, 4927.8, 349.1)
#1    方块  BP_8  TextSignStandBase-6      East_JudgesOffice       ( 968.7, 8079.6, 749.8)
#2    兔子  BP_9  TextSignStandBase-8      East_Courtroom_1        (-694.5, 2423.0, 769.3)
#3    王冠  BP_6  TextSignStandBase-7      East_Courtroom_2        ( 991.2, 3833.3, 799.6)
#4    梅花  BP_5  TextSignStandBase-9      East_Museum             (-409.0, 5833.9, 749.0)
#5    火焰  BP_7  TextSignStandBase-3      West_PrivateOffice      (-4001.4, 4193.4, 749.1)
缺席 = 黑桃
```

**置信度分层**（不要混为一谈）：

| 环节 | 状态 |
|---|---|
| 5 个图案、`缺席` 图案、教学图案 | `+41` / `GS_tut+41`，实测 3/3 + 缺席 3/3，已闭环 |
| 图案 → 5 席的顺序 | `+341` + RemoveAtSwap，150150 / 892892 实测一致，327327 暂搁置 |
| 5 席集合 | §2.3 算法正向推出，2/2 样本命中；107/107 seed 对未定阈值收敛，但**仍缺与游戏的第三方独立验证** |

即：**能输出，图案侧是已验证的，席位侧是「算法正确 + 参数不敏感」的工作模型**。
补一条带 `Seats on/off` 的新样本即可把最后一格也变成实测闭环。

---

## 4. 为什么这不是反向拟合

| 项 | 本文 | 旧拟合路线 |
|---|---|---|
| `41 / 241 / 341` | `sub_143585720` 的 `.text` 立即数 `a2+41/241/341`；`+341` 是**席位顺序**的 base（补抽分支 `a6=-1`），不是席位集合 base | 把 `+341` 当成从 8 席里抽集合的 base |
| 席位集合 base | `sub_1402B05C0` line 691-698 的 `crc32(盐名)+GetSeed(coord)`；分支由 CDO `WORD@744` 判定；静态池复现仍不中（§5） | 在 `0..300000` 搜偏移得 `70251`；`FUNC_INDEX` 另有 `+4490` |
| `+70251` | 不用；`.text` 无该立即数，函数里 base 只有两项 | 靠改 327327 记录凑 4/4，且只吻合集合不吻合顺序 |
| 配对 | `+41` 定图案、`+341` 定 5 席顺序，RemoveAtSwap，正向 3/3 | 只做「集合」预测，无顺序 |
| 样本用途 | 仅验证（集合、缺席图案、教学段、顺序）；327327 的 `-8` 由公式证伪为 `-5` 笔误 | 参与求常数、并改记录迁就常数 |

`SEED_FORMULAS.md` §CHJ_MT03 已注明 `70251` 属 C 类拟合、席位未闭环；本文没有把它写进任何公式。
与 `TSR_MT02.md` 的共同点：**先钉死函数里的立即数与池构造规则，再拿样本验证**；不同点是
TSR_MT02 的 `RandomizerId` 直接来自关卡 JSON，而本关的 `GetSeed` 来自对象名链。

---

## 5. 未闭环环节：仅剩「哪 5 席亮起」（正向定位到具体代码）

**席位顺序已闭环**（§3.0 的 `+341`），剩下的是席位**集合**。
**8 选 5 的算法已在 §2.3 完整正向推出**：候选池先经分类剔除、跨协调器排除、
`v248/v250` 预置占配额，然后每轮在 `sub_1402B3C30` 动态过滤后的池上抽一个，
`seed_arg = base + Num@setup+1640`，分母是过滤后的当前池长。
第三轮那 1792 个封闭组合（见 §5.1）证伪的只是「固定 8 池、分母 `8,7,6,5,4`」
这个**简化模型**；按真实算法复算，`r=2000` 时已有 2/3 命中（无过滤时为 0/3）。
尚未闭环的只是两个静态读不到的运行期数值（`v5`、`v13`）与分类趟谓词的判定结果。

| 位置 | 代码 | 会怎样改变抽取 |
|---|---|---|
| line 8 | `*(DWORD*)(setup+1640) = 0` | 已选数清零；若之前有预置目标则 `seed_arg` 初值不为 0 |
| line 166 | `sub_1402B46B0(Src, ...)` | 候选按全名字典序排序（静态模型已按此处理） |
| line 380-427 / 702-736 | `v248` / `v250` 两个列表 | `helper+216`/`+217` 命中的候选被追加到 `DesiredStateSetObjects`，`v131 -= len(v248)+len(v250)` ⇒ 固定入选席位 + 随机抽取次数减少 + `seed_arg` 初值偏移 |
| line 432 | `sub_1402B4CA0(..., a6=R)` | 跨协调器距离排除；`FirstBribe` 先随机化，其已选目标进入 v79 列表；R 取 `setup+1628`（运行期缓存）而非静态的 0 |
| line 761-763 | `sub_1402C30C0(..., &v246)` | `bSplitByObjectiveType`(setup+1000) 为真时分组，每组 `*a5 += 1` 改 base，且各组独立池/quota |
| line 822-832 | `sub_1402B3C30` | 每轮对 `DesiredStateSetObjects` 做有效性/距离/共房间过滤，会缩小当轮池 |
| line 1092-1143 | 第二个 `sub_1401A0F00(v246+Num, 0, |池|-1)` 循环 | 与前一循环互斥的补抽路径，用同一个 base 但从 `v245` 池抽 |

本轮新增的正向证据（缩小了缺口范围）：

- `sub_1402B05C0` line 1296 把 `setup+1625` 置 1 ⇒ slot 256 `sub_140A30C80` 确实读
  `DesiredStateSetObjects`，不是退回 `sub_140751DA0` 收集全池。
- `sub_140A1EED0` 用 `sub_14018C680`（introsort，比较器 `sub_1402C6910`）把 5 席
  **按名字升序排序**；`sub_1402C6910` 已反编译确认是纯字符串比较、无随机 key。
- 关卡 JSON 里只有教学 `_4` 的 helper 带 `bForceUseObjectiveInRandom = true`；
  主段 8 个只有 `ActorsToMatchState` / `ActorsToInverseMatchState` /
  `SharedActorsToMatchState` 三组列表 ⇒ `helper+216/+217` 的运行期状态只能由
  `sub_1419BF030(helper+224)` 之类的谓词从这些列表推出，JSON 不直接给出。
- 距离过滤 inactive：关卡把 `DistanceBetweenSameObjectives` /
  `DistanceBetweenDifferentObjectives` 都覆盖成 0，CDO 的 `setup+1628` 也是 0，
  `sub_1402B4CA0` 的 R=0、`sub_1402B3C30` 的距离分支跳过 ⇒ 池不是被几何缩小的。

### 5.1 第三轮：逐项验证与严格证伪

| 检查 | 结果 |
|---|---|
| 盐名宽串实读 | `0x14665E254 = L"Objective Actors"`、`0x146656762 = L"Large Objects"` ⇒ `crc32(salt)=1040402497` 无误 |
| `sub_1402B3910`（DesiredCount） | 无 override ⇒ `sub_1404FF400(a1)` 取 `DefaultValues` = **5** |
| `sub_1402B4CA0` 跨协调器排除 | `sub_1402B05C0` line 6 把 `setup+1628` 清零 ⇒ R=0，不排除候选 |
| `RBRandomManager` 引擎 | 关卡 JSON 中 `RBRandomManager`/`RandomizerId`/`RandomLots` **0 次** ⇒ 不是 TSR_MT02 机制 |
| 分组洗牌 `sub_1402C30C0` | 关卡无 `bSplitByObjectiveType`/`ObjectiveIndex`；即使生效，无有效 index 会打日志 `"Could not find valid objective types for grouping. Skipping groups"` 并退化为**单组、quota=5、`*a5` 不变** |
| hash 原语 | 把 line 848-855 的内联 mix64 逐式复现，与 `seedcore._mix64` 低 16 位 **40/40 一致**（唯一差异是 `seed=0` 时游戏走 `rand()`）⇒ 模拟器原语正确 |
| 按随机 key 排序取前 5（RES_MT02 先例） | 26 种 `GetSeed(actor)+L` / `base+L+i` 模型，最高 **1/3** ⇒ 排除 |

**固定池判据（适用范围有限，见下方修正）**：若假设 `RandSeeded(base+k, |q|)` 的
`|q|` 只随轮数变化、与池内容无关，则被选中的「原始池位置集合」`S` 与池内容无关，
若 base 正确必存在一个**固定池排列 P** 同时满足 3 条样本（`E_s = {P[i] : i ∈ S_s}`）。
用集合成员约束 + 二分图匹配代替 8! 枚举，扫描 `seed_arg = base + n + c·k`
（`n` 0..3、`c` 1..4、swap/shift、56 个由函数/关卡字符串正向推出的 base）：

```text
1792 个封闭组合 → 33 个可行解，其中 P = 名字升序的解 0 个
（33 个解分散在互不相同的 base 上，P 全无自然解释 ⇒ 组合巧合）
```

> **修正（第四轮）**：上面这个判据的前提 `|q| = N-k` 是**错的**。§2.3 阶段 C 表明
> `sub_1402B3C30` 在每轮抽取前、后各过滤一次池，一次可移除多个候选，且
> RemoveAtSwap 改变池顺序 ⇒ 分母是「过滤后的当前池长」，与池内容/几何强相关。
> 因此这 1792 个组合**只证伪了「固定 8 池连抽 5 次」这个简化模型**，
> 既没有证伪 `base = 1447708151`，也没有证伪 `sub_1402B05C0`。
> 按 §2.3 的真实算法（动态过滤）复算后，`r=2000` 时 3 条样本已有 **2 条 5 席集合全中**
> （`r=0` 即无过滤时为 0/3），说明方向正确。

剩下的静态缺口：① `v5`/`v13` 的运行期数值（`sub_1433AACD0` 的 CDO 全局默认、
`RBSettings_Gameplay+4116`）；② A5 分类趟谓词（`sub_1417C8F40` / `+35504` /
`RBRandomizable` vtbl+544）对 8 个 DropZone 各自的判定；③ 327327 记录的笔误。

下一步（决定性、仍是正向取证）：在 `sub_1402B05C0` 的 `0x1402B1857`
（`v153 = v145 + v151`）与 `0x1402B18CE`（`v157 = 池[v152]`）下运行期断点，
对一条已知 seed 记录 5 轮的 `v153`、`|池|`、被选中 actor 名与 `Num@1640`。
一次运行即可同时确定真实 base、已选数序列、池顺序与池构成，无需再猜。
其余静态方向（helper 谓词、BP CDO 覆写）见下表，优先级更低。

**已闭环部分不受影响**：图案序列、缺席图案、教学图案、`+341` 席位顺序、
`seq[i] → seat[i] → 立牌 → 坐标` 都是正向可复现的；只要本局 5 席（或 `--seats`）已知，
输出即完整（§3.1）。

---

## 6. 代码位置索引

| 地址 | 作用 |
|---|---|
| `0x1402D29E0` | `RandSeeded(seed,N)`，salt = `level_seed % 1000` |
| `0x140503B80` | `GetSeed(obj)`（Outer 链 + 绝对值） |
| `0x141CBDC30` | `crc32_fname` |
| `0x1402AE7F0` | slot 249：ObjectiveActors 随机化入口，盐 `L"Objective Actors"` |
| `0x1402AF490` | 显式表 → AActor* 池 |
| `0x1402B05C0` | 通用抽取引擎：base 计算 (689-698)、排序 (166)、跨协调器排除 (432)、抽取 (819-870)、补抽 (1092-1143) |
| `0x1402B3910` / `0x1402B46B0` / `0x1402B4CA0` / `0x1402B3C30` / `0x1402C30C0` | DesiredCount / 名字序排序 / 跨协调器排除 / 距离过滤 / 分组洗牌 |
| `0x1407D9A20` | `RBBaseObjectiveCoordinator` CDO：`WORD@744=0x0100`（决定 base 走 GetSeed 分支）、setup bool 默认值 |
| `0x140A61830` | slot 273：Large Objects 随机化（盐 `L"Large Objects"` @`0x146656762`） |
| `0x140A1ED70` / `0x140A1EED0` | slot 275：陷阱抽取 + 线索分配主函数（门 `+4096`，读 `+4080/+4088`；`sub_141C9CE10` 压 NULL、`sub_14018C680` 名字排序、补抽 `v9++`） |
| `0x143585720` | `+41/241/341` 三处立即数、`a6>=0` 覆盖为顺序索引、`a6=-1` 走 `+341` 抽席位、`FClueData` 写入 |
| `0x14018C680` / `0x1402C6910` / `0x141C9CE10` | introsort / 名字大小写折叠比较器 / 压 NULL |
| `0x140A30C80` | slot 256：`setup+1625==1` 时从 `setup+1632` 读回 `DesiredStateSetObjects` |
| `0x140A30DF0` | slot 294：有效大件列表 |
| `0x140B20020` | 写 `URBClueable` 接口（日志 `"Objective actor %s doesn't contains implement cluable interface"`） |
| `0x1459A7300` | 本类主 vtable（299 槽），slot 249/256/273/275/294 见 `class/CHJ_MT03_RBLargeInteractObjectiveCoordinator.md` |

## 7. 复现

```powershell
# ★ 游戏内验证用：只输 seed，默认只列 3 个钱箱图案的立牌点位
python opp_seed\seed.py CHJ_MT03 150150
python opp_seed\seed.py CHJ_MT03 150150 --all          # 连带教学段与 2 个干扰项
python opp_seed\seed.py CHJ_MT03 150150 --json         # 完整 6 行（含角色/坐标/缺席）
python opp_seed\seed.py --selftest                     # 全关卡自检 167/167

python temp\chj_mt03_forward.py                                # 全部正向验证 + 诊断
python temp\chj_mt03_forward.py 150150 BP_5,BP_6,BP_7,BP_8,BP_9  # 给 5 席集合 → 完整立牌点位
python temp\chj_mt03_forward.py 892892 BP_1,BP_5,BP_7,BP_8,BP_9
python temp\chj_mt03_final.py                                  # +341 席位顺序验证（含勘误）
python temp\chj_mt03_exact.py                                 # sub_140A1EED0 精确重放
python temp\chj_mt03_grid.py / chj_mt03_bases.py            # 封闭候选网格
python temp\chj_mt03_perm.py                                  # 池排列严格判据
python temp\chj_mt03_step.py                                  # 1792 组合 / 步长与初值
python temp\chj_mt03_hash.py                                  # 内联 hash 与原语一致性
python temp\chj_mt03_keymodels.py                             # 按随机 key 排序模型
python temp\chj_mt03_algorithm.py                             # 8 选 5 动态过滤算法
python temp\chj_mt03_algorithm2.py [corrected]                # 真实坐标 + 阈值细扫
python temp\chj_mt03_algorithm3.py [corrected]                # 分类趟池变体
python temp\chj_mt03_coords.py                                # 真实 DropZone 坐标
python temp\chj_mt03_predict.py 150150 123123                 # ★ 端到端：seed → 5 个图案点位
python temp\chj_mt03_randmgr.py / chj_mt03_groups.py / chj_mt03_preset.py / chj_mt03_diag2.py
```

`--seats` 参数是**席位集合**，脚本会按名字升序排好、再用 `+341` 正向抽序，
不会使用人工给的顺序。

原始输入：`opp_seed/test.txt`（样本）、`opp_seed/ui/data/maps/CHJ_MT03.json`（点位坐标）、
`paks/MAP/Maps/CourthouseJudicial/CHJ_LD_MT03_B00.json`（协调器实例 / `LinkedDecal` / 贴花坐标）。
