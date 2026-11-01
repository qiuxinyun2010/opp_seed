# opp_seed — 种子解析交付脚本

按「关卡 + 关卡种子」推理这一局的信息。本目录已独立成 git 仓库 `opp_seed`，可单独
clone / 更新；原 outlast 工作目录里的 `release/home/`、`release/coop/` 等分析产物不在
本仓库内。下文出现的 `release/coop/...`、`release/map*/...` 路径均指那个原始工作目录。

```
opp_seed/
  seed.py        ★ 入口：python seed.py <关卡> <种子> [--players N] [--difficulty X]
  seedcore.py      逆向出的随机原语（GetSeed / RandSeeded / RandBool / lookup3 mix / CHJ 选房与密码）
  gameshow.py      FPI_MT02 的 GameShow 模型（房间 / 图案 / 答案 / 数字串）
  cluegame.py      RES_MT01 的谋杀案模型（房间 / 凶器 / 凶手 三个数）
  mannequin.py     SMC_MT02 的人偶配对模型（4 个人偶下半身的房间 / 区域 / 坐标）
  seeddata.py      静态数据载入层：data/*.json → 与原来同名的常量
  data/
    chj_mt02.json     CHJ_MT02 协调器组 / 符号 actor / 房间 / 符号中文名
    mhs_mt01.json     MHS_MT01 区与图案家族 / 每房间去重开关 / 投影符号候选表（坐标 + 所在房间）
    tsr_mt01.json     TSR_MT01 候选桶 / 桶名 / 强制房间 / 码位坐标
    fpi_mt01.json     FPI_MT01 三组候选 / 图案表 / 放映机坐标 / 固定放映机
    psa_mt01.json     PSA_MT01 图案池 / 起始钥匙 / 钥匙房坐标 / 钥匙生成点 / 录像盘
    tfs_mt03.json     TFS_MT03 Sections 原始顺序 / 阀门候选 / 坐标
    room_centers.json 各 map 的房间中心参考点
    samples.json      --selftest 的全部实测样本
```

### 数据与代码的分界

- **`data/*.json`**：候选池、名称映射、坐标、实测样本 —— 这些是「事实」，由
  `paks/MAP/...` 与实测推导而来，游戏更新后重新生成即可，不需要改代码。
  每个文件里都有 `_source` / `_note` 说明来源和已知限制。
- **`seed.py` / `seedcore.py`**：随机原语调用、salt、名字链、关卡判定；以及只对某个
  seed 成立、带「未验证」警告的模型开关（如 `TFS_MAIN_SECOND`）。这类东西和算法
  写在一起才看得懂，所以**不**外置。

`seeddata.py` 载入时会把 JSON 数组还原成原来的类型（tuple、int 键），并做最基本的
结构校验（缺字段、桶表长度不一致会直接报 `SeedDataError`）。改 JSON 时不要动字段名。

## 用法

```powershell
cd <本仓库目录>       # 即 opp_seed/

python seed.py --list
python seed.py --selftest                  # 全部已接入样本：95/95

python seed.py DTS_MT01 252252             # 3 个调频器 / 3 条线索 / 最终模型位置
python seed.py FPI_MT01 335335             # 放映机坐标 / 录像盘 / 图案
python seed.py TFS_MT03 14014              # 六个阀门的位置与坐标（单样本路径模型）
python seed.py TSR_MT01 695695             # 字母数字码位及坐标 / 接线密码
python seed.py FPI_MT02 189189             # 教学关 + 2 个正式回合
python seed.py FPI_MT02 189189 --players 3 # 讲台 4 个 → 每回合 4 个房间
python seed.py FPI_MT02 189189 --difficulty normal
python seed.py FPI_MT02 189189 --max-fake 2   # 手动指定每区假翻板上限
python seed.py FPI_MT02 189189 --json      # 机器可读
python seed.py FPI_MT02 189189 --out r.json

python seed.py RES_MT01 339339             # 谋杀案：ROOM / WEAPON / KILLER
python seed.py CHJ_MT01 592592             # 3 个谜题房间 + 每间 4 位密码
python seed.py CHJ_MT01 592592 --trace     # 附带分区抽取过程

python seed.py MHS_MT01 707707             # 3 个图案 + 房间 + 3 位密码（+ 坐标）
python seed.py MHS_MT01 707707 --trace     # 附带抽取池大小与房间去重剔除过程

python seed.py SMC_MT02 453453             # 4 个人偶下半身所在房间（按颜色，含教学关）
python seed.py SMC_MT02 453453 --trace     # 附带组洗牌 / 距离过滤 / 抽取过程

python seed.py PSA_MT01 219219             # 最短路径上每把钥匙 + 录像盘的房间与坐标
python seed.py PSA_MT01 219219 --trace     # 附带节点房间抽取与距离过滤过程

python seed.py RES_MT02 176176             # 水疗度假村：26 颗宝石（人偶 / 类别 / 坐标）
python seed.py RES_MT02 69069 --tuto       # 再加教学段 51 人偶的类别图
python seed.py RES_MT02 69069 --difficulty hard
```

### PSA_MT01 输出

```text
$ python seed.py PSA_MT01 219219
PSA_MT01  警察局阁楼 · 图案钥匙与录像盘  (PoliceStationAttic)
seed = 219219   salt = 219   Easy   1P
  1：梅花=RBRoom_ReelStorage (307.3, 624.8, 1087.9)
  2：五角星=RBRoom25_2 (-1318.8, 806.3, 139.2)
  3：录像盘=RBRoom_DetectiveOffices03_50 (1590.3, 630.1, 407.5)
```

- 只输出**最短路径**：依次要拿的钥匙 + 最后一步的录像盘，每行是「房间 + 该 actor 的坐标」。
- 第 1 步不列起始那把钥匙（位置固定，不随机）。
- 坐标为钥匙生成点 / 录像盘 `RootComponent` 的位置（`coordinate_type = actor`）。
- 关卡是固定 7 节点的二叉钥匙树（节点 1 起始，4..7 是叶子，录像盘随机落在某个叶子），
  所以「最短路径」= 录像盘所在叶子的钥匙依赖链，不是几何寻路。
- `RBRoom_ChiefOfficeSideRoom_22` / `RBRoom_Infirmary_7` 会显示成点位图里用的
  `RBRoom_OfficeBathroom_24` / `RBRoom_3`。
- 完整逆向链见 `release/coop/PSA_MT01/PSA_MT01.md`。

### DTS_MT01 输出

```text
$ python seed.py DTS_MT01 252252
调频器：
  1. Store (Photo-Booth) (2289.9, 10110.1, 50)
  2. UppSewer_CorridorRightGenerator_01 (7883, 13041.6, -0.1)
  3. Room-14-33 (Electric Room) (2245.5, 10193.1, -335)
线索：
  Body = Women
  Weapon = A1 = CHAINSAW
  Room = IRISH PUB (RBRoom_Pub_Master)
最终模型：
  RBRoom_Pub_Slave01 (6840, 8853.5, 350)
```

- 调频器可对任意合法 seed 计算，`252252`、`61061` 两条样本均命中；
- 三条逻辑线索为 `Body`、组合后的 `Weapon`、`Room`；
- 武器、房间和最终模型只对已有完整实测线索的 seed 输出；其他 seed 显式显示 `未闭环`；
- 完整逆向链和证据见 `release/coop/DRS_MT01/DRS_MT01.md`。

### RES_MT01 输出

```
$ python seed.py RES_MT01 339339
RES_MT01  水疗度假村 · 推理谋杀案  (ResortSpa)
seed = 339339   salt = 339   Easy   1P
  ROOM   7   （犯罪现场：Break Room / ClueRoom_BreakRoom）
  WEAPON 1   （武器陈列里编号 1 的那件）
  KILLER 6   （缺肢组合一致、编号 6 的人体模型）
```

- `ROOM`：真血终点那个房间的编号，脚本还给出房间名，省得自己找
- `WEAPON`：武器陈列里同款武器的编号（样本里 1 = 平底锅）
- `KILLER`：缺肢组合一致的人体模型编号；缺肢是哪几处仍要靠 lodge 的参考模型对照

### FPI_MT02 输出

```
$ python seed.py FPI_MT02 189189
FPI_MT02  游乐场 · 在真人秀中幸存  (FunParkIllusion)
seed = 189189   salt = 189   Easy   1P
  [阶段1 教学] Hourglass      Sharing    答案 9   数字 5+1+3
  [阶段2 第1回合]
    Wall Of Eyes   Sharing    答案 5   数字 1+3+1
    Space Station  Dumbbells  答案 5   数字 1+4
  [阶段3 第2回合]
    Child Dorm     Book       答案 6   数字 4+2
    Carrots Storage Apple      答案 4   数字 1+2+1
```

- `图案` = 讲台/翻板上方那个图标（答案只累加**同一图案**的翻板）
- `答案` = 该房间要按的个位数；`数字` = 各翻板的数字，加起来就是答案
- 数字顺序有时与实物顺序相反（`FlipboardsBySection` 内的板顺序未验证），**和**不受影响

### CHJ_MT01 输出

```
$ python seed.py CHJ_MT01 592592
CHJ_MT01  法院 · 让正义天平倾斜  (CourthouseJudicial)
seed = 592592   salt = 592   Easy   1P
  [1] RBRoom_West_PrivateOffice      密码 2671
  [2] RBRoom_East_Museum             密码 4815
  [3] RBRoom_West_Blueprints         密码 2351
```

### MHS_MT01 输出

```
$ python seed.py MHS_MT01 884884
MHS_MT01  黑帮据点 · 找到 3 个投影房间  (MobsterHideoutSyndicate)
seed = 884884   salt = 884   Easy   1P
  [骷髅 Skull       ] RBRoom_DrugLab_2F_WalkwayRoom                  密码 806  (DrugLab_4) (1578.3, -849.9, 450)
  [三角 TriangleCircle] RBRoom_Shipyard_01                             密码 869  (Shipyard_2) (2407, 2623.5, 0.5)
  [五角星 Pentagram   ] RBRoom_Train_2ndFloor_Cooridor_01               密码 245  (TrainDepot_7) (-2313.7, 2899.4, 450)
```

- **图案**：`DrugLab` 恒为骷髅、`Shipyard` 恒为三角、`TrainDepot` 在螺旋/五角星/太阳里按
  `RandSeeded(46541, 3)` 抽 —— 4/4 对实测。
- **密码**：3 位、数字互不重复，`Draw(GetSeed(投影符号) + GetSeed(协调器))`；**11/11 实测命中**。
- **房间（含 `[区_序号]`）**：来自「10 选 1」的前置随机化，
  `base = crc32_fname("Projection Actors") + GetSeed(协调器)`，
  池 = 该区 10 个候选按**关卡 actor 顺序**（全名字典序 `_1,_10,_2…_9`）。
  `TrainDepot` 额外开了 `bLimitOneObjectivePerRoom`：与前面候选共房间的会被剔掉
  （`_1`/`_9` 同 `RBRoom_Train_Bridge_02`、`_7`/`_8` 同 `RBRoom_Train_Room_03`），
  **池 10 → 8**，`RandSeeded` 的模随之变小 —— 这是之前抽不准 TrainDepot 的唯一原因。
  `--trace` 会打印 base、池大小和被剔除的候选号。抽取 **12/12** 对实测。
- 括号里是投影符号 actor 的后缀和它的 `RootComponent` 坐标。

### SMC_MT02 输出

```
$ python seed.py SMC_MT02 453453
SMC_MT02  商场 · 4 个人偶按颜色配对下半身  (ShoppingMallCarrefour)
seed = 453453   salt = 453   Easy   1P
  [Red 红     EastShoppingMall ] RBRoom_EastCorridorRDC_Store4_3              (6166, -196.6, 0)
  [Green 绿   EastShoppingMall ] RBRoom_DepartmentStore_EastSide_2F           (5233.6, -3109, 500)
  [Blue 蓝    WestShoppingMall2] RBRoom_WestCorridorRDC_Store1                (-3090.5, -1468.1, 34.9)
  [Tutorial 教学  SecurityRoom ] RBRoom_DepartmentStore_Central_SecurityRoom  (-364.6, -4143.1, 450)
```

- 每行 = **一种颜色的人偶下半身在哪个房间**（教学关恒在 `SecurityRoom`，不参与随机）。
- 坐标为布置点 actor 的 `RootComponent` 位置（`coordinate_type = actor`）。

**算法**：4 个类型各取 1 → 洗牌组顺序 → 每组先剔除「离任一已选目标同层 50 m 内」的候选 → 再抽。
所谓「3 个人偶分散到东西两个区域」是这条距离规则的副作用，不是 section 硬约束
（300 seed 抽样 298 次东西各半）。详见 `release/coop/SMC_MT02/SMC_MT02.md`。

### RES_MT02 输出

```text
$ python seed.py RES_MT02 176176
RES_MT02  水疗度假村 · 焚毁莉莉娅的遗物  (ResortSpa)
seed = 176176   salt = 176   Easy   1P
类别配额（分区 25 颗的展开）：Ruby=5  Sapphire=13  Emerald=8
  mandatory  RBRoom_Building_Room3              红宝石  RE_MannequinTrap_Setup_BP_15   (-139.2, -829.9, 369.2)
  mandatory  RBRoom_RestaurantLounge_Master     红宝石  RE_MannequinTrap_Setup_BP_214  (-977.1, -3279.3, 683.2)
  section1   RBRoom_West1F_GameRoom             蓝宝石  RE_MannequinTrap_Setup_BP_129  (-2071.7, 4694.8, 219.2)
  ...
  共 26 颗宝石
```

- 每行 = **该人偶身上是真宝石 + 颜色 + 宝石挂点坐标**；`mandatory` 是固定房（类别恒为红）。
- 分区 4 段：房间按 `RandFraction(GetSeed(room)+479582)` 排序后**轮流**分配，类别从配额桶里抽。
- `--tuto` 额外打印教学段 51 个人偶的颜色表（偶序号=蓝、奇序号=绿）；
  「哪 6 个人偶带宝石」仍未解。详见 `release/home/RES_MT02.md`。

## 坐标输出

涉及房间或点位的 JSON 结果同时包含 `coordinates = [X, Y, Z]`：

- `coordinate_type = actor`：具体放映机、阀门或黑光码的 `RootComponent` 坐标；
- `coordinate_type = room_center`：只预测到房间时使用的房间中心参考点，不代表某块翻板或道具的精确位置。

文本输出也在对应房间或目标后显示 `(X, Y, Z)`。

## 参数说明

| 参数 | 作用 | 备注 |
|---|---|---|
| `--players 1/2/3` | `NumActiveConsoles`：1P=2 / 2P=3 / 3P=4 个讲台（= 每回合房间数） | 1P 已实测；2P/3P 按关卡配置实现，**未实测** |
| `--difficulty` | 难度档（easy/normal/hard/insane） | 只对 `IntByDifficulty` 的字段生效；**只有 easy 1P 有实测样本** |
| `--max-fake N` | 覆盖「每区假翻板上限」 | 默认取 `gameshow.MAX_FAKE = 3` |
| `--digits N` | CHJ 密码位数 | 默认 4 |
| `--trace` | 打印 CHJ 分区抽取过程 | |
| `--json` / `--out` | 机器可读输出 | |

### 为什么 `MAX_FAKE = 3`（重要）

关卡 JSON 里 `MaxFakeFlipboards` 是 `IntByDifficulty`：
`Easy=0、Normal=3`，且 **Easy 没有写 Override 标志**。
`sub_1404FF400` 判断「有没有这一档」看的是 **Override 标志**而不是值，
于是 Easy 局会**回落到 Normal 的 3**。这就是为什么实测的 Easy 局等于 `MaxFake=3`。

同一机制也解释了 `NumActiveConsoles`：Default=4，1P/2P/3P 分别写了 Override（2/3/4），
所以按人数取值是可靠的。

## 支持状态

| 关卡 | 内容 | 状态 |
|---|---|---|
| `CHJ_MT01` | 法院 · 让正义天平倾斜 | 房间 + 4 位密码 + 坐标 |
| `FPI_MT01` | 游乐场 · 匹配录像盘与放映机 | 放映机坐标 + 录像盘 + 图案 |
| `TFS_MT03` | 玩具工厂 · 开启六个阀门 | 六个阀门坐标；有效路径仅 1 条样本，标记 PART |
| `FPI_MT02` | 游乐场 · 在真人秀中幸存 | 房间 + 图案 + 答案 + 房间参考坐标 |
| `RES_MT01` | 水疗度假村 · 推理谋杀案 | 房间 / 凶器 / 凶手 + 犯罪现场参考坐标 |
| `CHJ_MT02` | 法院 · 判决被起诉者 | 已验证 seed 的投影密码与坐标，标记 PART |
| `MHS_MT01` | 黑帮据点 · 找到 3 个投影房间 | 图案 + 房间 + 3 位密码（TrainDepot 池按房间去重 10→8），抽取 12/12、密码 11/11 |
| `TSR_MT01` | 电视台屋顶 · 密码接线面板 | 字母数字码位坐标 + 接线密码 |
| `SMC_MT02` | 商场 · 4 个人偶按颜色配对下半身 | 颜色 → 下半身房间 + 区域 + 布置点坐标（教学关固定） |
| `PSA_MT01` | 警察局阁楼 · 图案钥匙与录像盘 | 最短路径上每把钥匙 + 录像盘的房间与坐标；2 条样本（219219 / 958958），全 salt 扫描 0 失败 |
| `DTS_MT01` | 闹市区 · 调频线索与目标人体模型 | 3 个调频器可泛化；两条完整样本可输出 3 线索与最终模型，其他 seed 标记未闭环，PART |
| `RES_MT02` | 水疗度假村 · 焚毁莉莉娅的遗物 | 主轴段 26 颗宝石（人偶 / 类别 / 坐标，实测 2/2）；教学段**颜色**可查（`--tuto`，实测 8/10），「哪 6 个人偶」未解，PART |
| `SRR_MT01` | 郊区住宅区 · 撬开富豪宅的密码盘 | **5 个密码盘所在房间 + 各自 4 位密码**（本局 3 栋为主，另外 2 栋标「备用」；不给贴花位）；选房/密码 12/12 实测，`groupSeed` 为唯一自洽解 |
| `CHJ_MT03` | 法院 · 贿赂其余可收买的法官 | TODO |

新增关卡：在 `seed.py` 的 `LEVELS` 里加一条；随机原语复用 `seedcore.py`；
如果又是 `RBGameShowObjectiveCoordinator` 系（GameShow），直接复用 `gameshow.py`，只换关卡数据；
`GatherAndDeliver_Mannequin` 系（人偶上下半身配对）复用 `mannequin.py`，只换候选表与协调器名。
关卡静态表加到 `data/<关卡>.json`，在 `seeddata.py` 里加对应的常量与校验，再在 `seed.py`
顶部 import 进来；实测样本统一加到 `data/samples.json`。

## 数据来源

- 反编译：`TOT.exe.i64`（IDA，基址 `0x140000000`）；原始地址写在 `seedcore.py`/`gameshow.py` 注释里
- 静态配置：`paks/MAP/Maps/<Map>/<Trial>_B00.json`、`paks/LD/*.cpp`（蓝图默认值）
- 分析过程与踩坑：`release/coop/GUIDE.md`；FPI_MT02 细节：`release/coop/FPI_MT02/FPI_MT02.md`；
  DTS_MT01 细节：`release/coop/DRS_MT01/DRS_MT01.md`

## 已知边界

1. 种子只通过 `seed % 1000` 进入公式：`S` 与 `S+1000` 结果完全一样。
2. FPI_MT02 依赖「回合序号从 0 开始、按阶段 2→3 顺序推进」；跳关会错位。
3. 2P/3P、normal/hard/insane 未实测。
4. `FlipboardsBySection` 内板顺序未知（只影响「哪块板显示哪个数字」，不影响答案）。
5. `SMC_MT02` 只有 1 条实测（Easy / 1P，seed=453453）：颜色↔人偶类型（红=A/绿=B/蓝=C）是
   反推出来的；房间集合不受影响，但若「组初始顺序」不是 A B C D，绿/蓝会对调。另外
   「3 个人偶分散到东西两个区域」是距离规则的副作用而非硬约束（约 300 局里有 2 局会全挤东侧）。
6. `DTS_MT01` 的 3 个随机调频器已对任意 seed 交付；武器、房间和最终模型目前只对
   `252252`、`61061` 两条完整样本输出。缺失 DTR MapSet 的 `ObjectiveTypeIndex` 默认值，
   未知 seed 不做人体模型拟合。
7. `PSA_MT01` 有 2 条实测（Easy / 1P，seed=219219、958958）：7 个节点的图案、已记录房间、
   录像盘叶子都对上了，火焰房是预测值。停尸房 `RBRoom_Morgue_Master` 的第二个钥匙生成点
   `PSA_MT01_KeySpawner_Morgue_2` 不在 `PSA_MT01_B00` 里，而在 `PSA_LD_Items` 子关卡
   （`SceneComp.RelativeLocation = -794.6382, 2209.8171, 139.12964`），补进
   `data/psa_mt01.json` 后 999 个 salt 全部有解（旧表有 118/999 ≈ 11.8% 的 seed 会报
   `ModelUnresolved`）。只有 easy/1P 有样本。
8. `SRR_MT01` 有 3 条实测（Easy / 1P，seed=894894、512512、745745）：选房与 4 位密码 12/12。
   其中「抽密码房」的 `GetSeed(setup)` 没有从二进制里直接定位到，现用
   `|crc(RBObjectiveCoordinatorGroup2) + |crc(MultiroomPuzzle_Coordinator_House1_BP)||`
   这个自洽解（在「池 H1..H5 × 670+ 名字链」里三样本同时命中的唯一解），第四个样本可能推翻它。
   正因为这条没定死，`view()` 除了本局 3 栋，还把**另外 2 栋的密码盘**一起列出来（标「（备用）」，
   同时在 `spare` 字段里给机器读）：万一判错的正好是哪 3 栋，5 组密码都摆在那儿照样能试。
   输出**只到「密码盘房间 + 4 位密码」这一层**，贴花位（第几位读哪个房间）不再输出；
   内部仍算了 `slots`，需要时可以直接取 `predict()` 的原始结果。
