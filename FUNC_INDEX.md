# TOT.exe 反编译函数索引（跨关卡交叉验证）

> 目的：把 `release/home`、`release/coop`、`opp_seed` 三个目录里**所有成功分析案例**涉及的
> 反编译函数/数据符号汇成一张索引，方便交叉验证与新关卡复用（同一函数被多份文档分析时合并列出各自出处）。
> 目标二进制：TOT.exe（`TOTClient-Win64-Shipping.exe`，base `0x140000000`，sha256 `2cd37c88…a4192e`）。
> 生成：2026-11-02，扫描范围 = 三目录全部分析 .md + 交付脚本注释（不含 tools/tmp 拟合脚本的临时结论）。
> 修订：2026-11-04，并入 FPB_MT03 闭环（三区域 6/6）：§2 新增 sub_1402B4CA0 真实语义与
> FRBPrimaryActorsRandomizationSetup 布局等条目；§5 新增第 13/14 条重大修正（复用前必读）。
> 产物位置：`release/coop/FUNC_INDEX.md`（其余目录只读）。

## 0. 使用说明

- **出处缩写**：`home/X.md` = `release/home/X.md`；`coop/X/X.md` = `release/coop/X/X.md`；
  `O/seedcore.py` = `opp_seed/seedcore.py`；脚本注释以文件名列出。
- ctrl-F 地址（如 `0x1435F7E90`）或符号（如 `sub_143620E70`）直达条目；§5 常量表反查偏移。
- ⚠️ 标记 = 文档间口径冲突或历史误记，见 §6。
- 复现公式中的 `salt = dword_146E2E5C4 % 1000 = 关卡种子 % 1000`；`RandSeeded(seed,N)` 等价实现见
  `opp_seed/seedcore.py`（各交付脚本自带同源实现）。

## 1. 链路总览（角色速查）

| 链 | 函数序列 | 用于 |
|---|---|---|
| 随机原语 | `1402D29E0` RandSeeded · `1413F02F0` RandFraction · `1413F08D0` RandBool · `1401A0F00` RandRange · `140503B80` GetSeed · `141CBDC30` crc32_fname · `14270F020` 原始 hash · `14320CF6D` lookup3 | 全部关卡 |
| ObjectiveActors 通用随机化 | `1402AE7F0` 入口 → `1402AF490`（显式表）/`1402B0070`（按类）→ `1402B05C0` 抽取引擎（⚠️ a1=setup 结构体，§5.13）→ `1402C30C0` 分组洗牌 → `1402B3C30` 距离/房间过滤 → `1402B4CA0` 跨协调器距离排除（分类趟后，§5.14） | SMC/CHJ/PSO/DRS/SRR02/FPI01/FPB03… |
| MultiroomPuzzle 密码 | `1435F7E90` 编排 → `14374E420` 调度/抽房/洗牌 → `1436FD080`→`1436FE410` 逐房 → `143621120` order → `143620E70` 写数字；贴花 `1436FEB10`；标牌 `1435F7860` | CHJ_MT01 / SRR_MT01 / SR_Trial |
| ProjectionCode 投影密码 | `1436E7F70` 前置派发 → `1436E8B40`/`1436E8450` 列表 → `1436E95F0` 主随机化（46541 符号组 / 99041 真投影器 / 86549 变体；假投影 99042/86550）→ `1436EA3D0` 三位密码（+38541+k）；池删除 `1437056A0`/`142C48E40`；写回 `1434468F0` | CHJ_MT02 / MHS_MT01 |
| OrderedClueFrequency 调频 | `14361C230` 主函数 → `14361CE40` 上屏抽样 / `14361CFA0` 配对赋值（`14361DF10`）；前置 `1402B05C0` 族 | SRR_MT02 / SR_Trial 1&3 阶段 / DTS / PSB / PSO |
| GameShow 真人秀 | `14320C8F0` 设种子 → `14320CEB0` 回合准备 / `14320F140` 教学 → `14320F4E0`/`14320FB00` 数字串 | FPI_MT02 |
| ClueGame 谋杀推理 | `14320B590` 初始化（洗 16 房+3 子目标）→ `143209730`/`14320A590` 分发 | RES_MT01 |
| 钥匙树 | `1435820D0` 主流程 → `143582F60`/`143583870` 图案 → `143583800` 生成点 → `143583530` 钥匙房 | PSA_MT01 |
| 珠宝/人偶 | `1433B49B0` 主循环 → `1433B58F0` pick_spawner → `1433B5BC0` 教学段 | RES_MT02 |

## 2. 主表（按地址升序；函数 + 内部指令点 + 数据符号）

### 2.1 函数

| 地址 | 符号 | 含义 | 出处 | 偏移/备注 |
|---|---|---|---|---|
| 0x1400E2B60 | sub_1400E2B60 | 投影器池交换删除（与 sub_142C48E40 同类） | coop/MHS_MT01 | |
| 0x140120320 | sub_140120320 | 按类/按 Outer 过滤的世界 actor 迭代器 | home/PSO_MT01 | 受 a1+704/712、a1+864 控制 |
| 0x140143A50 | sub_140143A50 | 取 actor 名的比较器（sub_1402B46B0 用） | home/SR_TRIAL §12.3 | |
| 0x14018C680 | sub_14018C680 | Algo::Introsort（首/尾/谓词）；RES_MT02 对 {actor,float key} 记录按 +8 排序 | home/RE_METHOD、home/RES_MT02、coop/RES_MT02 | |
| 0x1401A0F00 | sub_1401A0F00 | RandRangeInt/RandRange(id,min,max)→[lo,hi]；真实收尾 splitmix 双盐，321982955=0x133111EB | home/SR_TRIAL §11.12、coop/RES_MT02、O/seedcore.py | |
| 0x1402873A0 | sub_1402873A0 | 巨型函数(0x9EB1)，内含大量 GetSeed | coop/PSB_MT01/evidence/ADDR | 唯一调用者 0x141D15460 |
| 0x1402947F0 | sub_1402947F0 | **PrepareState(候选,state,0)**：helper state = 2−state（1=StateA / 2=StateB），并转发 UFunction PrepareState/SetState | level/TFS_MT03.md、coop/TFS_MT03_FORWARD.md | 与 sub_140B47990(IsStateA) 配对 |
| 0x1402A53F0 | sub_1402A53F0 | 取 actor 组件 / 过滤取值辅助 | home/CHJ_MT02、home/MHS_MT01、coop/RES_MT02 | |
| 0x1402AE7F0 | sub_1402AE7F0 | 通用 ObjectiveActors 随机化入口(0x206)：门控 coord+1346(0x542)&1；显式列表非空→sub_1402AF490，否则迭代器 | CHJ_MT03、DRS、FPI_MT01、PSB、SMC、SRR_MT02、dts_mt01.py 等 10+ | 盐名 "Objective Actors" |
| 0x1402AF490 | sub_1402AF490 | 显式候选表分支(0x2D3)：FSoftObjectPath 数组→AActor*（40B/项，软引用解析+IsA+线性去重，**不排序**） | 同上 9+ | 池序=ObjectiveActors 序 |
| 0x1402AF770 | sub_1402AF770 | 候选队列 | home/PSB_MT01 | |
| 0x1402B0070 | sub_1402B0070 | 分组分支(0x547)：按 ObjectiveActorClasses 解析世界 actor / 盐名传递中转 | coop/SMC_MT02、coop/PSB_MT01/ADDR、coop/SRR_MT02、dts_mt01.py | |
| 0x1402B05C0 | sub_1402B05C0 | **通用抽取引擎** RandomizeObjectiveActors(0x22F2)：⚠️ **a1 = FRBPrimaryActorsRandomizationSetup 结构体指针（协调器+1352），不是协调器**（§5.13）；a2=协调器。显式表→NULL 压实→**sub_1402B46B0 名字典序排序**→分类（helper+216 剔除/+217 必选，实测均 false；无 RBRandomizable→恒选）→**sub_1402B4CA0 跨协调器距离排除（分类趟后）**→分桶抽取：idx=RandSeeded(v246+已选总数, 池剩余) RemoveAtSwap + sub_1402B3C30 距离过滤（swap、尾→头、跨组预过滤）。v246=crc32_fname(盐名)+GetSeed(coord)+组数（bSplit 时组洗牌自增） | 15+ 文档（CHJ_MT02/03、DRS、FPI_MT01、MHS、PSB、PSO、SMC、SRR_MT02、SR_Trial、DTS、FPB_MT03、mannequin.py…） | SR_Trial B03 拟合 v240=45991+seed，见 ⚠️；CHJ_MT02 24/24 锁定盐名 "Objective Actors"；CHJ_MT03 实测有效基址=base+4490；SRR_MT02 选中集 6/6 钉死名字序+组数自增+swap 过滤（ANALYSIS.md）；**FPB_MT03 三区域 6/6（base 公式复证，2026-11-04）** |
| 0x1402B0814 | sub_1402B0814 | 建组前预过滤（0x1402b0814–0x1402b0b39）：尾→头遍历，命中者 Src[i]=Src[count-1];count-- | coop/DRS_MT01（fit_prefilter/fit_pool_search） | |
| 0x1402B28C0 | sub_1402B28C0 | **RemoveAtSwap**（末位交换删除） | home/MHS_MT01、home/SR_TRIAL §12.7、coop/SRR_MT02/ANALYSIS.md | ⚠️ 旧记"RemoveAt 保序"有误：SRR_MT02 9/9 序列反演钉死 swap（勘误 §5.10） |
| 0x1402B2930 | sub_1402B2930 | PrepareState/关闭未通过候选（只置 state=1/2，不赋图案） | home/CHJ_MT02、home/SRR_MT02 | |
| 0x1402B3910 | sub_1402B3910 | DesiredCount 取值 | coop/CHJ_MT03、home/SR_TRIAL §11.9 | +0/+600/+800 三段 fallback |
| 0x1402B3C30 | sub_1402B3C30 | 候选有效性+距离过滤+共房间剔除(0xA78)；阈值 v5<=0 跳过距离分支→sub_140B3BE80；距离剔除=从后向前末尾交换删除（CHJ_MT02 17→20/20 锁定；SRR_MT02 6/6 复证） | 8+（SMC：水平<5000 且 \|ΔZ\|≤容差剔除；CHJ_MT02：DistanceBetweenSameObjectives Y/B=1200、Tuto=120；SRR_MT02：水平<1000，Z∈[399,400.5] 等价水平） | bLimitOneObjectivePerRoom 开关 a1+1003 |
| 0x1402B46B0 | sub_1402B46B0 | introsort：按对象全名/actor 名大小写不敏感字典序 | home/SR_TRIAL §12.3、coop/DRS_MT01、dts_mt01.py、coop/SRR_MT02/ANALYSIS.md | 比较器 sub_140143A50。SRR_MT02：sub_1402B05C0 抽取前对候选池排序（选中集模型依赖） |
| 0x1402B4C10 | sub_1402B4C10 | 名字哈希/crc32_fname 备选种子分支 | home/MHS_MT01 §3.1、home/SRR_MT02、home/SR_TRIAL §11.14 | coord+0x2e8==1 时 |
| 0x1402B4CA0 | sub_1402B4CA0 | **跨协调器目标距离排除**(0x921，⚠️§5.14 修正，旧记「可达性预过滤」有误)：sub_1402B05C0 分类趟后另跑一趟尾→头；对每个候选取组件位置（RBObjectiveActorComponent +320→+480）调 sub_141D1E3B0 在 v79 列表中找半径 R=DistanceBetweenDifferentObjectives（setup+1208 开关/+1216 值；缺省走 sub_1433AACD0 全局默认）内最近的已放置目标，命中→swap 移出池并进排除表 | FPB_MT03（区域2 闭环定标）、RES_MT02（「过滤不可用/已占用人偶」即此机制）、CHJ_MT02 §9 | a3=setup+1002（bUseOtherCoordoActorsForDistance）：1→v79=sub_140695380 全局收集，0→v79=协调器 vtable+1768（sub_1406954E0）；a6=R；a7=200.0f 仅推车分支半径。多协调器同图关卡「模型对不上」优先查此机制 |
| 0x1402BF7F0 | sub_1402BF7F0 | 每区随机数量 k（整数区间或比例区间两形态） | level/TFS_MT03.md、coop/TFS_MT03_FORWARD.md | |
| 0x1402C30C0 | sub_1402C30C0 | 分组+组洗牌+按比例分配 quota(0x1644)：按 ObjectiveIndex/类型/房间组分桶（插入序），组弹出 idx=RandSeeded(*a5,|rem|) RemoveAtSwap 且 **每组 *a5+=1**（→ 基址+组数）；quota 三步：+1 循环→比例 extra=(int(2*(ratio-1)+0.5))>>1→余量给首个放得下的组。a3=显示屏数/DesiredCount | 10+（CHJ_MT02/03、DRS、FPI_MT01、MHS、PSB、PSO、SMC、SRR_MT02、SR_Trial、mannequin.py） | SRR_MT02 定稿：记录阶段 a3=3→[2,1]、抽取阶段 a3=6→[3,3]（3+3 来源）；Rich 单组 cs=GetSeed+1、School/SasExit 双组 cs=GetSeed+2 |
| 0x1402C6910 | sub_1402C6910 | 排序比较器：actor 名字大小写折叠升序 | home/RE_METHOD、RES_MT02 系、O/seed.py | |
| 0x1402CB480 | sub_1402CB480 | RandSeeded(GetSeed(a1)+90681,\|pool\|) 取 1 个 int | coop/PSB_MT01/ADDR | |
| 0x1402CDD90 | sub_1402CDD90 | 逐 actor：RandSeeded(GetSeed(actor)+\|pool\|+90601,\|pool\|)+RemoveAt | coop/PSB_MT01/ADDR | |
| 0x1402D29E0 | sub_1402D29E0 | **RandSeeded**(seed,N)→[0,N)：splitmix 双盐混合取 (uint16)%N；盐=dword_146E2E5C4%1000 | **全部文档** | seed==0 退化 rand() |
| 0x14035AFB0 | sub_14035AFB0 | 对象构造(0x1838)，结果存 qword_146E601F0 | home/FPI_MT02 | |
| 0x140474200 | sub_140474200 | TArray::RemoveAt(idx,n,shrink)（生成点数组 swap-remove） | home/RE_METHOD、coop/PSA_MT01 | |
| 0x140474270 | sub_140474270 | 候选数组 swap-remove | level/TFS_MT03.md、coop/TFS_MT03_FORWARD.md | |
| 0x14048DA90 | sub_14048DA90 | 注册 UFUNCTION 表 | home/FPI_MT02、coop/FPI_MT02 | (class,&off_145C05950,4) |
| 0x1404FF400 | sub_1404FF400 | **FIntByDifficulty**：判「有没有这一档」看 Override 标志而非值，缺档往下一档回落 | O/seedcore.py、O/README、RES_MT02 系、CHJ_MT03、PSB | |
| 0x140503B80 | sub_140503B80 | **GetSeed**(obj)=\|crc32(FName)+seed(Outer)\| 递归 Outer 链取绝对值；快路径 UFunction→接口→名字兜底 | **全部文档** | 含 RBRandomSeedGeneratorInterface 覆写分支（sub_14268B040） |
| 0x1405D4E10 | sub_1405D4E10 | RBObjectiveActorComponent 构造（6336B，主 vtable off_145A24D80）：WORD@+572=0x0100 → **+572=0（位置源=组件+480 直读）、+573=1（默认参与跨协调器距离过滤，sub_141D1E3B0 门槛）**；+480 为运行期位置缓存 | FPB_MT03 | |
| 0x140601E10 | sub_140601E10 | RandSeeded+读写 +0x660/+0x668 候选函数（查证非线索分配） | coop/CHJ_MT03 §6.2 | 同族见 0x1433F7A00 等 |
| 0x1406954E0 | sub_1406954E0 | RBSimpleObjectiveCoordinator vtable+1768（slot 221）：v79 列表 getter = 先刷新（sub_1406957D0）再返回 | FPB_MT03 | |
| 0x1406957D0 | sub_1406957D0 | v79 列表刷新器：①自身随机化已完成（setup+1625==1）时并入自身已选目标；②vtable+1752（sub_140B0A0F0）按类收集世界 objective actor，再过滤（协调器+3452 完成标志直通 / helper+216 / RBRandomizable vtbl+544 谓词） | FPB_MT03 | |
| 0x140753460 | sub_140753460 | vtable+0x800(slot 256) 实现体：布尔谓词（读 RBPlayerState，比较 a1+857） | home/PSB_MT01_Q2 | |
| 0x1407D2720 | sub_1407D2720 | FRandomStream 连续抽（FPI_MT02 随机源排查用） | home/FPI_MT02 §5 | |
| 0x1407D9920 | sub_1407D9920 | RBSimpleObjectiveCoordinator 构造（size 6656，主 vtable off_1459FD160；自身属性自 +3816 起） | FPB_MT03 | |
| 0x1407D9A20 | sub_1407D9A20 | RBBaseObjectiveCoordinator 构造（size 3816，父 vtable off_14594BE70）：内嵌 FRBPrimaryActorsRandomizationSetup@+1352 的 CDO 默认值（§5.13 布局） | FPB_MT03、PSA 系 | |
| 0x1407F9240 | sub_1407F9240 | sub_1402B3C30 内判定 | home/MHS_MT01 | |
| 0x1407FAB20 | sub_1407FAB20 | UClass 懒加载→sub_14035AFB0 | home/FPI_MT02、coop/FPI_MT02 | |
| 0x140817D80 | sub_140817D80 | RBBlacklightDetectableQuestItemCoordinator 类 getter | coop/RES_MT02、RES_MT02.py | size 0x4580 |
| 0x1408191C0 | sub_1408191C0 | RBObjectiveCoordinatorGroup StaticClass | home/SRR_MT01 | |
| 0x140882CB0 | sub_140882CB0 | RBKeyLockedRoomsCoordinator 类 getter | coop/PSA_MT01 | 类大小 9600 |
| 0x1408E4410 | sub_1408E4410 | RBClueGameObjectiveCoordinator 类懒加载 | home/RES_MT01、coop/RES_MT01、O/cluegame.py | size 4232；属性表 0x145B2C7E8 |
| 0x140935E60 | sub_140935E60 | RBSimpleObjectiveCoordinator StaticClass（宽串类名 @0x1466E5CAC；size 6656） | FPB_MT03 | |
| 0x140938DA0 | sub_140938DA0 | 父类构造（ClueGame 链） | coop/RES_MT01 | |
| 0x1409EC340 | sub_1409EC340 | 从后续逻辑行候选排除已有目标行 | coop/TSR_MT01 | |
| 0x140A1ED70 | sub_140A1ED70 | 对有效列表执行 29 次陷阱抽取 | coop/DRS_MT01 | RandSeeded(coordSeed+36041+i) |
| 0x140A30DF0 | sub_140A30DF0 | 构造当前有效人体模型列表 | coop/DRS_MT01 | |
| 0x140A61830 | sub_140A61830 | 读取 LargePickupActorsRandomizationSetup | coop/DRS_MT01 | |
| 0x140A61C30 | sub_140A61C30 | 迭代器派发/回退分支(0x358)：TActorIterator 按类收集候选 | home/CHJ_MT02、MHS、DRS | 盐名回退 "Objective Actors" |
| 0x140ADBA30 | sub_140ADBA30 | 按下标 swap-remove | coop/RES_MT02、coop/TSR_MT01 | |
| 0x140AFCE40 | sub_140AFCE40 | 8 字节数组 swap-remove | coop/PSA_MT01 | |
| 0x140B3BB00 | sub_140B3BB00 | RBObjectiveCoordinatorGroup CDO 构造 | home/SRR_MT01 | vtable off_145A25780 |
| 0x140B3BDD0 | sub_140B3BDD0 | 取 ObjectiveIndex | home/SR_TRIAL §11.8 | FindComponentByClass+vtbl+544 |
| 0x140B3BE80 | sub_140B3BE80 | 「候选和已保留的撞房间吗」判定 | home/MHS_MT01、O/seed.py、mhs_mt01.py | bLimitOneObjectivePerRoom |
| 0x140B47990 | sub_140B47990 | IsValid(候选)：取 ObjectiveActor 组件读 bool | TFS 系 | |
| 0x140B55BF0 | sub_140B55BF0 | 固定房取 dist[0]（恒第 1 类） | coop/RES_MT02 §8 | |
| 0x1413A76D0 | sub_1413A76D0 | 从主候选池稳定删除已选项 | coop/PSA_MT01 | |
| 0x1413F02F0 | sub_1413F02F0 | **RandFraction**(seed)→[0,1)：同混合取 (uint16)/65536；洗牌/排序比较器 f(seed)>=0.5 | 多处（SR_Trial/RES/PSO/PSB…） | |
| 0x1413F08D0 | sub_1413F08D0 | **RandBool**(seed)：同混合取最低位 | O/seedcore、gameshow、psb | |
| 0x141480350 | — | ARBLargeObjectTrackerCoordinator 静态类 getter | coop/CHJ_MT03 §6.2 | |
| 0x1419BEF00 | sub_1419BEF00 | IntByDifficulty/阈值取值器 | coop/SMC_MT02 | >0 用配置值，否则回落 RBSettings_Gameplay+4116 |
| 0x141C49310 | sub_141C49310 | 取字符串 | home/SR_TRIAL §11.14 | |
| 0x141C9CE10 | sub_141C9CE10 | ⚠️ 两说：home 记 TArray::RemoveAll(..,nullptr)；coop/RES_MT02 记 {actor,float key} 按 +8 introsort | home/RE_METHOD、home/RES_MT02 vs coop/RES_MT02 | 见 §6 |
| 0x141CBDC30 | sub_141CBDC30 | **crc32_fname**：FName CRC32，每 16 位字符 [lo,hi,0,0] 4 步标准 CRC32 | **全部文档** | 表 dword_146CCCA80；crc('PersistentLevel')=0x4C09CC22 |
| 0x141D15460 | sub_141D15460 | 0x1402873A0 的唯一调用者 | coop/PSB_MT01/ADDR | |
| 0x141D1E3B0 | sub_141D1E3B0 | 可达性校验（RBPushCartSpawner 列表） | home/CHJ_MT02 | |
| 0x141D1E3B0 | sub_141D1E3B0 | **半径内最近目标查找**(0xB40)：普通 actor 用其 RBObjectiveActorComponent（+573==1 才参与；+572==1 时位置=+168 引用→其+320→+480，否则组件+480 直读）；RBPushCartSpawner 走轨道样条（RBRailForPushableComponent，+672/+680 的 176B 段）；Z 窗口与水平半径同值 | FPB_MT03 | sub_1402B4CA0 的判定核心 |
| 0x141D247D0 | sub_141D247D0 | room.GetActorsByTag(tag=15,&out) | coop/RES_MT02 | |
| 0x141D9B720 | sub_141D9B720 | 字符串拼接（标牌文本链） | home/SR_TRIAL §8① | |
| 0x141DA4D70 | sub_141DA4D70 | 候选池来源(vtable+1752)：SpecificItemSpawners 遍历+世界 actor 迭代 | home/PSO_MT01 | 40B 步长遍历 a1+728 |
| 0x14268B040 | sub_14268B040 | RBRandomSeedGeneratorInterface 虚调用 | home/SRR_MT01 §6.1 | 静态无法定值 |
| 0x1426B9A40 | sub_1426B9A40 | 类注册壳（拷 9 条接口 vtable） | coop/RES_MT02 | 源 off_145B39DA0 |
| 0x1426B9FB0 | sub_1426B9FB0 | RBObjectiveCoordinatorGroup NativeFunc 表/构造 | home/SRR_MT01、home/PSO_MT01 | 类大小 3920 |
| 0x14270F020 | sub_14270F020 | 原始 seeded hash（RandSeeded 内部混合） | coop/PSA_MT01、TFS 系 | (uint16)hash%count |
| 0x142713210 | sub_142713210 | 构造 thunk（ClueGame） | coop/RES_MT01 | |
| 0x142713220 | sub_142713220 | RBClueGameObjectiveCoordinator 构造 | coop/RES_MT01 | 父类 sub_140938DA0 |
| 0x142857BC0 | sub_142857BC0 | 协调器构造（KeyLockedRooms） | coop/PSA_MT01 | 主 vtable 0x145A025E0 |
| 0x14285B5B0 | sub_14285B5B0 | ", " 分隔符（标牌文本链） | home/SR_TRIAL §8① | |
| 0x1428C6B80 | sub_1428C6B80 | 默认值初始化器（0x3788~0x3968 清零） | coop/RES_MT02 | |
| 0x1428C6B90 | sub_1428C6B90 | 构造（QuestItemCoordinator） | coop/RES_MT02 | 主 vtable off_14598BA50 |
| 0x1429E5510 | sub_1429E5510 | 类 init（注册 UFUNCTION）→sub_14048DA90 | FPI_MT02 系 | |
| 0x142B69630 | sub_142B69630 | memcpy 局部副本（标牌文本链） | home/SR_TRIAL §8① | |
| 0x142C48E40 | sub_142C48E40 | 投影器池交换删除（RemoveAtSwap）⚠️ 旧文档误写 RemoveAt 保序 | home/CHJ_MT02、MHS 系 | 引擎内联版 0x1402b1909 |
| 0x142F5DA80 | sub_142F5DA80 | 尾部覆盖删除（RemoveAtSwap，汇编确认） | coop/DRS_MT01 | |
| 0x143209730 | sub_143209730 | 分发：房间 | home/RES_MT01、coop/RES_MT01、O/cluegame.py | |
| 0x14320A590 | sub_14320A590 | 分发：凶手（缺肢/编号排列分配） | 同上 | |
| 0x14320B590 | sub_14320B590 | ClueGame 初始化核心(vtable 槽 275)：ClueRooms(16) Fisher-Yates 15 次→3 子目标 RandomClueIndex(+0xF18)=RandSeeded(v++,NumberOfClues(+0xEE8))，答案=+1 | home/RES_MT01、coop/RES_MT01、O/cluegame.py、RES_MT01/probe.py | |
| 0x14320C8F0 | sub_14320C8F0 | 设置本局种子 this+0x1828=GetSeed(this)（虚槽 14） | FPI_MT02 系、O/gameshow.py | |
| 0x14320C940 | sub_14320C940 | 翻板收集→FlipboardsBySection | FPI_MT02 系 | |
| 0x14320CEB0 | sub_14320CEB0 | PrepareRound：正式回合准备（选房/假板/图案/答案/应用） | FPI_MT02 系、O/gameshow.py | v=lookup3_mix(回合序号,本局种子)；偏移 0xD98/0x1828/0x1068/0x1788/0x17D8 |
| 0x14320CF6D | — | lookup3 mix（c=0x9E3779B9，9 步 Jenkins，32 位环绕） | O/seedcore.py、gameshow.py | |
| 0x14320EDD0 | sub_14320EDD0 | 回合推进 SetRoundIndex(this+0xD98+1) | FPI_MT02 系 | |
| 0x14320F140 | sub_14320F140 | 教学回合准备（bIsTutorial==1，单分区 slots=板数-1） | FPI_MT02 系 | |
| 0x14320F4E0 | sub_14320F4E0 | 数字串生成入口（建 [1..9] 池） | FPI_MT02 系 | |
| 0x14320FB00 | sub_14320FB00 | 数字串生成核心：递归+Fisher-Yates（RandSeeded(seed,k) k=9..2）凑 sum==ans、相邻不同 | FPI_MT02 系 | |
| 0x143226860 | sub_143226860 | 翻板洗牌辅助（TArray 拷贝） | home/RES_MT01 | |
| 0x1433A39B0 | sub_1433A39B0 | vtable 定位工具示例 | coop/DRS_MT01/which_vtable.py | 工具示例 |
| 0x1433a3bad | — | RBBaseObjectiveCoordinator 另一条：GetSeed+65118+i | coop/DRS_MT01/bruteforce_k.py | |
| 0x1433AA480 | AddObjectiveActor | actor→RemainingObjectives(+3464)，预算+3480 | home/DTS_MT01 | |
| 0x1433AACD0 | sub_1433AACD0 | DistanceBetweenDifferentObjectives 全局默认值：RBSettings 系 +952（协调器+744 ObjectiveType==0）/+964（非 0），<0 回落管理器 +4092/+4104 | FPB_MT03 | |
| 0x1433B49B0 | sub_1433B49B0 | RES_MT02 主轴段主循环：固定房+类别桶+分区轮流派发 | RES_MT02 系、O/seed.py | counter 分区循环从 0 重新起算 |
| 0x1433B58F0 | sub_1433B58F0 | pick_spawner(room,seed)：GetActorsByTag(15)→过滤→RandSeeded 抽 | RES_MT02 系 | |
| 0x1433B5BC0 | sub_1433B5BC0 | 教学段 assign_class_by_spawner：51 人偶逐次抽取分配类别 | RES_MT02 系、home/RE_METHOD、res_mt02_tuto_fit.py | v4=GetSeed(协调器)（与关卡种子无关）；cls=k%Num 或 RandSeeded(v8+438361) |
| 0x1433B64E0 | sub_1433B64E0 | 逐人偶补类别+写 TrappedSpawners | coop/RES_MT02 | RandSeeded(738368+i)；未闭环 |
| 0x1433B6B80 | sub_1433B6B80 | BP_SetTrappedSpawnersEnabled 实现 | RES_MT02 系、home/RE_METHOD | vtable+0x950 |
| 0x1433B6CC0 | sub_1433B6CC0 | 收集全部 spawner | home/RE_METHOD | vtable+0x944 |
| 0x1433CD330 | sub_1433CD330 | RemoveAtSwap | coop/TSR_MT01 | |
| 0x1433CD3E0 | sub_1433CD3E0 | TArray::AddUnique | coop/RES_MT02 | |
| 0x1433F7A00 | sub_1433F7A00 | 同 0x140601E10 族（查证非线索分配） | coop/CHJ_MT03 §6.2 | |
| 0x1433F86E0 | sub_1433F86E0 | 列表拷贝（TArray\<TSoftObjectPtr\> 40B/元素，保序） | home/MHS_MT01、coop/MHS_MT01 | |
| 0x143416200 | sub_143416200 | "Level Seed: %d" 打印 | home/SR_TRIAL §11.12 | 证实 dword_146E2E5C4=关卡种子 |
| 0x1434468F0 | sub_1434468F0 | 写回密码数组/把密码写回投影器 | home/CHJ_MT02、coop/MHS_MT01/ADDR | |
| 0x1434BADB0 | sub_1434BADB0 | **RemoveAtSwap**（memcpy(dst, src+Num-1, 8)）；假投影循环内取走 clue 变体 / SRR_MT02 图案池删除 | coop/CHJ_MT02/CHJ_MT02.md §4、coop/SRR_MT02/ANALYSIS.md | |
| 0x14357FC30 | sub_14357FC30 | 激活钥匙房与门设备 | coop/PSA_MT01 | |
| 0x1435820D0 | sub_1435820D0 | RBKeyLockedRoomsCoordinator 主流程：7 节点钥匙树/选录像盘叶子 | PSA 系 | RandSeeded(98639,4)；图案 10→8 弃牌自 45834 起 |
| 0x143582C4D | (内部点) | 录像盘叶子抽取（常量折叠 0xF1F56F239AC38BC2） | PSA 系 | 反解 seed=98639（2^21 唯一解） |
| 0x143582F60 | sub_143582F60 | 为节点选「图案+生成点」 | PSA 系 | 图案 RandSeeded(38322+node) |
| 0x143583530 | sub_143583530 | 选下一个钥匙房（距离≥2000 接受，≤20 次尝试） | PSA 系 | RandSeeded(38342+node+attempt) |
| 0x143583800 | sub_143583800 | 从父房生成点池抽 1 个并 swap-remove | PSA 系 | RandSeeded(320239+node) |
| 0x143583870 | sub_143583870 | 从图案池抽一个图案 | coop/PSA_MT01 | seed=38322+node |
| 0x14358EA00 | sub_14358EA00 | OrderedClue 集合函数 | coop/SRR_MT02 | a1+9392 调频器、a1+9408 显示屏 |
| 0x14359A520 | sub_14359A520 | 候选房间列表 introsort（名字字典序） | home/SR_TRIAL、coop/SR_Trial | 比较键 *(actor+0xA8)；byte_145E47280 tolower |
| 0x1435DA9D0 | sub_1435DA9D0 | ARBMinigameRoomsObjectiveCoordinator::Randomize | home/RE_METHOD、drs_data.py | RandSeeded(GetSeed+66066+groupIdx+picked)；⚠️ 66066 归属此函数 |
| 0x1435dafc5 | — | RBMinigameRoomsObjectiveCoordinator | coop/DRS_MT01/bruteforce_k.py | GetSeed+61670+i |
| 0x1435F7860 | sub_1435F7860 | 标牌文本副本洗牌（只影响标牌显示） | home/SR_TRIAL §8①、SRR_MT01、sr_trial*.py | key=RandFraction(GetSeed(item)+134123)≥0.5（134123@0x1435F7AD7）；n<=8 选择排序「最后一个 bit=0 换末尾」；逆序拼接 |
| 0x1435F7E90 | sub_1435F7E90 | **MultiroomPuzzle 编排入口 / 协调器每步 Setup**：调度(sub_14374E420)→初始化 0..9 数字池(+11392)→选 Section(67620)→标牌 | **home/SRR_MT01 §5 + home/SR_TRIAL §7（双文档互证）** | +11408/+11416 |
| 0x143617580 | sub_143617580 | 收集候选后转交 sub_1402B05C0 | home/PSO_MT01、dts_mt01.py | |
| 0x143617640 | sub_143617640 | 同上 | home/PSO_MT01 | |
| 0x14361A4E0 | sub_14361A4E0 | 旧 L"Operatable" 入口（实测对不上，已弃用） | dts_mt01.py | |
| 0x14361C230 | sub_14361C230 | **协调器随机化主函数**(0xC0D)：vtable+2048 取候选→intro-sort（n≤8 选择排序变体：每轮取最后一个 RandFraction(GetSeed(actor))<0.5 者换末尾）→分组/抽取。分组路径（+7273≠1）：sub_1402C30C0(组, a3=显示屏数3)→记录循环 off=v69+v68（台 cs+243551+off、图案 cs+223551+off、cs=GetSeed+组数）→剩余台配陷阱 cs+253526+j | 6+（PSB/PSO/SRR_MT02/SR_Trial/DTS…） | 多协调器类共用地址；常量 243551/223551/253526/924519/264069/850321/951320。SRR_MT02 三轮均走分组路径（配了 AlternatePairs 但 +7273=0），绑定输入序=显式表序∩选中集（9/9） |
| 0x14361CE40 | sub_14361CE40 | 索引列表生成/无放回顺序抽样（i=RandSeeded(a4,剩余)、保序删除、++a4） | PSB/PSO/SR_Trial | 上屏 924519(代码)/924523(拟合)，见 ⚠️。仅配对/其他类路径使用；OrderedClueFrequency（SRR_MT02）显示顺序=记录序，不经此函数 |
| 0x14361CFA0 | sub_14361CFA0 | 配对路径（*(coord+7273)==1：ObjectiveIndexAlternatePairs） | 同上 | GetSeed+223551。⚠️ SRR_MT02 配了 AlternatePairs 但 +7273=0 未走（曾误判，见 §5.11） |
| 0x14361D450 | sub_14361D450 | 结果数组新增元素 | coop/PSB_MT01/ADDR | |
| 0x14361DF10 | sub_14361DF10 | ObjectiveIndexAlternatePairs[idx] 查询 | home/SR_TRIAL §11.8 | |
| 0x143620E70 | sub_143620E70 | **写数字**：idx=RandSeeded(seed+7168,\|pool\|)；digit=pool[idx]；memmove 保序删除 | CHJ_MT01、SRR_MT01、SR_Trial、evidence/sub_143620E70.c | digit→贴花+636、order→+644 |
| 0x143621120 | sub_143621120 | **贴花 order 计算**：section+216>=需求才进入两分支，否则 -1 | 同上、evidence/sub_143621120.c | 分支偏移 +11332 / +594 |
| 0x1436E7F70 | sub_1436E7F70 | 前置 Actor Randomization 派发(0x2ca)：容器(+15616)/投影器(+17272) 两路 | home/CHJ_MT02、MHS 系 | 显式列表→sub_1402AF490，否则 sub_140A61C30；两路盐名串 "Projection Containers"(0x1466657A0)/"Projection Actors"(0x14665E230)，实测种子基未生效（生效者为 "Objective Actors"） |
| 0x1436E8450 | sub_1436E8450 | 取容器列表（SpecificContainerActors 显式表 a1+4216，40B/项软引用） | coop/MHS_MT01/ADDR、coop/CHJ_MT02 | |
| 0x1436E8B40 | sub_1436E8B40 | 读 a1+18912 前置输出列表（真投影器，仅 DesiredCount 个） | home/CHJ_MT02、coop/CHJ_MT02 | 未启用随机化时改走 a1+4240 显式表 |
| 0x1436E95F0 | sub_1436E95F0 | **RBProjectionCodeCoordinator 主随机化**：clue 组 RandSeeded(slot+46541)、真投影器 RandSeeded(i+99041) 重排配对、密码 Draw、假投影循环（v44=(n-c)/c，盐 99042+i+j/86550+i+j，尾部裁剪 c*(v44+1)） | CHJ_MT02、MHS 系、O/seed.py | base=GetSeed(符号)+GetSeed(协调器)+slot；container 分支 OFF=34561 |
| 0x1436EA3D0 | sub_1436EA3D0 | **三位密码 Draw3**：digit_k=pool[RandSeeded(base+38541+k,\|pool\|)]，末尾交换删除 | CHJ_MT02、MHS 系、O/seed.py | 三位互不重复 |
| 0x1436EA4F0 | sub_1436EA4F0 | 投影器↔容器绑定 | coop/MHS_MT01/ADDR | |
| 0x1436FCBB0 | sub_1436FCBB0 | 收集可用房间 | home/SR_TRIAL、coop/SR_Trial | 调用点 0x14374E879 |
| 0x1436FD080 | sub_1436FD080 | 每间房 Setup→落一次 digits[k] | home/SR_TRIAL §10.3、coop/SR_Trial | 调用点 0x14374E974/F9B1/F9F6 |
| 0x1436FD200 | sub_1436FD200 | 容器入口（+456 接口判定）→sub_1436FE410 | CHJ_MT01、home/SR_TRIAL §2 | 另分支 MultiroomPuzzle「一次分配全部贴花」 |
| 0x1436FE410 | sub_1436FE410 | **单房逐位**：k=digits.Num、order=sub_143621120、digit=sub_143620E70(...,GetSeed(房)+k)、digits[k]=digit | CHJ_MT01、SRR_MT01、SR_Trial、O/seedcore、evidence/sub_1436FE410.c | 共享池 coord+11392 |
| 0x1436FEB10 | sub_1436FEB10 | 房内抽 1 张贴花 | CHJ_MT01、SRR_MT01、home/SR_TRIAL | RandSeeded(compSeed+1000+j-1,n) |
| 0x143705510 | sub_143705510 | 拷贝 PossibleClueGroups 槽位列表（16B TArray/项） | coop/CHJ_MT02/CHJ_MT02.md §4 | |
| 0x1437055A0 | sub_1437055A0 | clue 组槽位交换删除 | coop/CHJ_MT02/CHJ_MT02.md §4 | |
| 0x1437056A0 | sub_1437056A0 | 数字池交换删除（RemoveAtSwap） | CHJ_MT02、MHS 系 | |
| 0x143708DC0 | sub_143708DC0 | 同 0x140601E10 族 | coop/CHJ_MT03 §6.2 | |
| 0x143742330 | sub_143742330 | 同上（通用按类型随机取 actor 类） | coop/CHJ_MT03 §6.2 | |
| 0x14374E420 | sub_14374E420 | **MultiroomPuzzle/SimplePuzzleRoomCoordinator 调度**：收集房间→名字字典序→逐区抽房→randomID+排序→补位→数组洗牌→逐房 Setup | SRR_MT01、SR_Trial、O/seedcore、O/seed.py、coop/SR_Trial/evidence | 抽房 28042@0x14374EA20、补位 28088@0x14374F80F、randomID 48688@0x14374F0F1、RandBool(+93405)@0x14374F1A2；洗牌无 134123 |
| 0x143771DF0 | sub_143771DF0 | TArray Reserve（只容量计算+重分配） | home/SR_TRIAL §9 | |
| 0x14378EBC0 | sub_14378EBC0 | 按逻辑行和输入/输出侧读取插孔数组 | coop/TSR_MT01 | |
| 0x14378ECD0 | sub_14378ECD0 | 按 RowIndex/ColumnIndex 注册并排序插孔 | coop/TSR_MT01 | |
| 0x14378F780 | sub_14378F780 | 生成一条字母/数字连接 | coop/TSR_MT01 | group=+4431、inputColumn=+33898(5)、outputColumn=+9872(5) |
| 0x14378FBA0 | sub_14378FBA0 | 密码生成主函数（桶选择/码位/连接/数字错位） | coop/TSR_MT01 | 码位 +523+2*round+half；连接 +535-round+min(原始下标)；旋转 +60121 |
| 0x143790B40 | sub_143790B40 | 从过滤后桶内候选选一个码位 | coop/TSR_MT01 | |
| 0x143790E20 | sub_143790E20 | 排除已用码位/强制房间/跨房间过滤 | coop/TSR_MT01 | |
| 0x1437B67A0 | sub_1437B67A0 | ⚠️ 属 RBToyMachineLargeObjectCoordinator（盐 "Large Objects"），旧 DRS 分析误用 | coop/DRS_MT01、dts_mt01.py | 见 §6 |
| 0x1437B8040 | — | 交付校验：carried+168∈+3464 且面板在互动清单 | home/DTS_MT01 | |
| 0x1437B8680 | sub_1437B8680 | 同 sub_1437B67A0 | coop/DRS_MT01 | |
| 0x1437D48D0 | sub_1437D48D0 | "item spawner" 协调器 RandSeeded(GetSeed(this)+i)；亦属 0x140601E10 族 | coop/DRS_MT01/drs_data.py、coop/CHJ_MT03 | |
| 0x1437E5100 | sub_1437E5100 | **RandomizeActorArray**(UFUNCTION)：抽 count 个不重复项，idx=RandSeeded(GetSeed(setup)+j+45151,\|池\|) 保序删除 | SRR_MT01、O/seedcore、O/seed.py | SRR「5 选 3」；DesiredCount=setup+48 |
| 0x1437E6510 | sub_1437E6510 | 同 0x140601E10 族 | coop/CHJ_MT03 §6.2 | |
| 0x1434B3330 | sub_1434B3330 | **RBFirePumpObjectiveCoordinator 主 vtable slot 249**：TFS_MT03 分区/阀门随机化主函数（本关实际使用） | level/TFS_MT03.md、coop/TFS_MT03_FORWARD.md、O/seed.py | 61390 强制抽 `RandSeeded(cs+61390+pool.Num(), pool.Num())`；PrepareState→IsStateA 使 39135 退化为 0 |
| 0x143803600 | sub_143803600 | RBWaterValveObjectiveCoordinator 的同类实现（兄弟类，本关未用） | coop/TFS_MT03_FORWARD.md | `i+cs+61390`；runtime 数据 +10424 |
| 0x14381A7C0 | sub_14381A7C0 | 同族：RandSeeded(GetSeed(this)+78392+i) | coop/DRS_MT01/drs_data.py | |
| 0x14383FF20 | sub_14383FF20 | ObjectiveIndexAlternatePairs 的 setter | home/PSO_MT01 | 注册项 0x145CD0538 |
| 0x143882790 | GetClue | 线索读取 UFunction（蓝图） | coop/CHJ_MT03 §6.2 | 无直接 CALL（ProcessEvent 调用） |
| 0x143882800 | SetClue | 线索写入 UFunction（蓝图） | coop/CHJ_MT03 §6.2 | 无直接 CALL（ProcessEvent 调用）；图案分配用 RandSeeded(coord_seed+offset+k) + RemoveAtSwap，offset ∈ {5318,…,95291} 9 选 1 |
| 0x143947420 | sub_143947420 | 设给标牌（标牌文本链） | home/SR_TRIAL §8① | |
| 0x143993600 | sub_143993600 | 「是否保留该 spawner」判定 | home/RE_METHOD、RES_MT02 系 | IsA(Interface)+vtbl+0x220 |

### 2.2 函数内关键指令点（非函数条目）

| 地址 | 含义 | 出处 |
|---|---|---|
| 0x1402b0814–0x1402b0b39 | sub_1402B05C0 建组前预过滤循环（尾→头 swap 删除） | coop/DRS_MT01 |
| 0x1402b163e / 0x1402b164d | v240/base = crc32_fname(盐名)+GetSeed(coord) 装配点；esi=crc32_fname 结果（0x1402B161E NOT esi），call 0x140503B80=GetSeed | MHS/ADDR、dts_mt01.py、panelseed.py、CHJ_MT03 capstone |
| 0x1402b17fe / 0x1402b1812 | 组计数 / selectedCount | MHS/ADDR |
| 0x1402b1833 | RandSeeded 内联点：idx=RandSeeded(seed+已选数,剩余池) | MHS/ADDR、panelseed.py |
| 0x1402b07e9 / 0x1402b0b92 | R 装配与跨区排除调用点：setup+1208==1 ? R=FFloatByDifficulty(setup+1216) : sub_1433AACD0(协调器)，缓存 setup+1628；随后调 sub_1402B4CA0(out, 协调器, setup+1002, 0, &池, R, 200.0f, 0) | FPB_MT03 |
| 0x14361c34c–0x14361c6a4 | sub_14361C230 intro-sort n≤8 选择排序变体（最后一个 k<0.5 换末尾） | coop/SRR_MT02/ANALYSIS.md |
| 0x14361c985–0x14361cc02 | sub_14361C230 记录循环：off=v69+v68，台 243551+off / 图案 223551+off | coop/SRR_MT02/ANALYSIS.md |
| 0x14361cd6c–0x14361cdaa | sub_14361C230 陷阱循环：cs+253526+j 配组剩余台 | coop/SRR_MT02/ANALYSIS.md |
| 0x1402b18c3 / 0x1402b1909 | hash%count / RemoveAtSwap | MHS/ADDR、panelseed.py |
| 0x1402b1af0 | 调 sub_1402B3C30 | MHS/ADDR |
| 0x1402B2217 | 取人调用 sub_1401A0F00：id=v240+6+k（汇编级证实） | home/SR_TRIAL §11.13 |
| 0x1402b3f69 / 0x1402b3d15 | 距离过滤判定点 / v13 读取点(coord+1416) | coop/SMC_MT02 |
| 0x14361CA08 / 0x14361CA55 | 尸体/调频器抽取 + RemoveAt（偏移 243551） | PSB 系 |
| 0x14361CA7C / 0x14361CA8D | 图案/钥匙抽取 + RemoveAt(bKeepOrder=1)（偏移 223551） | PSB 系 |
| 0x14361c95c / 0x14361c967 | v120=+243551 / v123=+223551 装载点 | psb_mt01.py |
| 0x14361C3C1 | ucomiss（intro-sort 比较器 0.5 阈值证据） | PSO/pso_probe.py |
| 0x1433B4B81 / 0x1433B506C | pick_spawner(counter+820351 / +279412) | RES_MT02 系 |
| 0x1433B4F6D / 0x1433B50BF | 房间序 RandFraction(GetSeed(room)+479582) / 类别 RandRangeInt(counter+823203) | RES_MT02 系 |
| 0x1433B4D72–0x1433B4D88 | 类别桶整数化 n=(int)(2*d*total+0.5)>>1（cvtss2si 四舍五入到偶数） | RES_MT02 系 |
| 0x1433B4F12 / 0x1433B505C / 0x1433B4F37 | 分区 counter 从 0 起 / 房间轮流 / room_order introsort | RES_MT02 系 |
| 0x143582C4D | 录像盘叶子抽取（折叠常量 0xF1F56F239AC38BC2→seed=98639） | PSA 系 |
| 0x1435F7AD7 | 134123 偏移装载点（sub_1435F7860 内） | coop/SR_Trial/evidence/scan |
| 0x14374EA20 / 0x14374F80F | 28042 抽房 / 28088 补位 RandSeeded 调用点 | coop/SR_Trial/evidence/scan |
| 0x14374F0F1 / 0x14374F1A2 | 48688 randomID / 93405 RandBool | 同上 |
| 0x14374EDD8 起 | GetSeed/RandFraction 成对（洗牌比较器，无 134123） | 同上 |
| 0x1435DAA2A / 0x1433B5D6E | GetSeed+66066 / counter+438361（RES_MT02 教学段常量点） | coop/RES_MT02 |

### 2.3 [data] 全局数据符号

| 地址 | 符号 | 含义 | 出处 |
|---|---|---|---|
| 0x145947650 | off_145947650 | RBClueGameObjectiveCoordinator 主 vtable | coop/RES_MT01 |
| 0x14594BE70 | off_14594BE70 | RBBaseObjectiveCoordinator 父类 vtable | coop/PSA_MT01 |
| 0x14598BA50 | off_14598BA50 | QuestItemCoordinator 主 vtable | coop/RES_MT02 |
| 0x1459A7300 | — | 人偶类 vtable 基址（指定环 vtable[297]，激活=261） | home/DTS_MT01 |
| 0x1459FD160 | off_1459FD160 | RBSimpleObjectiveCoordinator 主 vtable（slot 219=+1752 世界 actor 迭代→sub_140B0A0F0；slot 221=+1768 v79 getter→sub_1406954E0） | FPB_MT03 |
| 0x145A025E0 | off_145A025E0 | RBKeyLockedRoomsCoordinator 主 vtable | coop/PSA_MT01 |
| 0x145A20C88 / 0x145A21DF8 | — | sub_14361C230 所在 vtable(slot 558) / 基类 vtable 引用 | home/PSB_MT01_Q2 |
| 0x145A25780 | off_145A25780 | RBObjectiveCoordinatorGroup vtable | home/SRR_MT01 |
| 0x145B2C7E8 | — | RBClueGameObjectiveCoordinator 属性表 | O/cluegame.py |
| 0x145B2F600 | — | RBBaseObjectiveCoordinator 属性描述符表（ObjectiveActors@+728、ObjectiveType@+744、PrimaryActorsRandomizationSetup@+1352 等） | FPB_MT03 |
| 0x145B39DA0 | off_145B39DA0 | 接口 vtable 源表（9 条） | coop/RES_MT02 |
| 0x145C04F80 | — | FRBGameShowSection 属性表（名字指针 0x28 步长） | home/FPI_MT02 |
| 0x145C05950 | off_145C05950 | UFUNCTION 表（Cheat_CompleteRound 等 4 项） | FPI_MT02 系 |
| 0x145CC8AC8 | — | FRBPrimaryActorsRandomizationSetup 属性描述符表（完整布局见 §5.13） | FPB_MT03 |
| 0x145CD0538 | — | ObjectiveIndexAlternatePairs 属性注册项 | home/PSO_MT01 |
| 0x145E47280 | byte_145E47280 | tolower 映射表（名字比较用） | home/SR_TRIAL |
| 0x1464d9b13 / 0x1464d9b28 | — | 宽串 "bAssignMatchingClues" / "PossibleMatchingClues" | coop/CHJ_MT03 |
| 0x146656762 | xmmword_146656762 | 宽串 "Large Objects"（人体模型盐） | dts_mt01.py、fit_mannequin.py |
| 0x14665E230 | — | 宽串 "Projection Actors"（盐名） | CHJ_MT02、MHS 系、O/seed.py |
| 0x14665E254 | — | 宽串 "Objective Actors"（盐名） | SRR_MT02、MHS、PSB、SMC、dts |
| 0x14665E264 | — | srr02_probe 默认读取的相邻串 | srr02_probe.py |
| 0x1466657A0 | — | 宽串 "Projection Containers"（盐名） | CHJ_MT02、MHS 系 |
| 0x1466E5170 | — | 宽串 L"ARBGameShowObjectiveCoordinator" | home/FPI_MT02 |
| 0x1466E5CAC | — | 宽串 L"RBSimpleObjectiveCoordinator" | FPB_MT03 |
| 0x1466e4d5a | — | 宽串 ARBLargeObjectTrackerCoordinator 类名 | coop/CHJ_MT03 |
| 0x1467638F2 | — | 宽串 "Possible Clue Groups for coordo %s has invalid index %i" | coop/PSB_MT01/ADDR |
| 0x14689EE02 | — | 宽串 "Ordered Clue Actors"（仅日志，非盐名） | coop/PSB_MT01/ADDR |
| 0x1469E5240 | — | .rdata 本地化表（首字 0x0000→空串分支 ~CRC32w=0） | home/SR_TRIAL §11.13 |
| 0x146CCCA80 | dword_146CCCA80 | 标准 CRC32 查表（poly 0xEDB88320） | home/CHJ_MT01 |
| 0x146E2E5C4 | dword_146E2E5C4 | **全局关卡种子（Level Seed）**；RandSeeded 盐=%1000 | **全部文档**（打印点 sub_143416200） |
| 0x146E601F0 | qword_146E601F0 | UClass 懒加载结果存储 | home/FPI_MT02 |
| 0x146E71B38 | qword_146E71B38 | RBObjectiveCoordinatorGroup 静态类 | home/PSO_MT01 |
| 0x146E8D9E0 | qword_146E8D9E0 | RBUseQuestItemsObjectiveCoordinator 静态类(14200) | home/PSO_MT01 |

## 3. 常量偏移速查

| 常量 | 语义 | 所属 |
|---|---|---|
| 1000 | 房内贴花抽取 compSeed+1000 | sub_1436FEB10 |
| 11332 / 594 | order 两分支偏移 | sub_143621120 |
| 7168 | 逐位数字 RandSeeded(compSeed+k+7168) | sub_143620E70 |
| 28042 / 28088 | 分区抽房 / 补位 | sub_14374E420 |
| 48688 / 93405 | section randomID / 排序 RandBool(randomID+93405) | sub_14374E420 |
| 134123 | 标牌副本洗牌 key 偏移 | sub_1435F7860 |
| 34561 / 46541 / 99041 | container OFF / clue 组 / 真投影器 | sub_1436E95F0 |
| 38541 | 三位密码 Draw3 | sub_1436EA3D0 |
| 223551 / 243551 / 253526 | 显示图案(+v69+v68) / 显示台(+off) / 陷阱图案(+j) | sub_14361C230（分组路径）、sub_14361CFA0（配对路径同值） |
| 924519 / 924523 | 上屏目标乱序（代码 / SR_Trial 拟合 +4） | sub_14361CE40 |
| 264069 / 850321 / 951320 | 备用目标乱序 / 备选补充 ×2 | sub_14361CE40 |
| 45151 | SRR 选 3 栋 | sub_1437E5100 |
| 38322 / 45834 / 320239 / 38342 / 98639 | PSA 图案 / 弃牌 / 生成点 / 钥匙房(+attempt) / 录像盘 | 0x143582xxx 族 |
| 820351 / 279412 / 479582 / 823203 / 438361 / 738368 | RES_MT02 固定房 / 分区人偶 / 房间序 / 类别 / 教学交替 / 补类别 | 0x1433B4-6 族 |
| 66066 / 61670 / 78392 / 65118 | MinigameRooms / 同族 ×3（DRS） | 0x1435DA9D0 等 |
| 61390 / 39135 | TFS 预选 / 主选 | sub_143803600 |
| 523 / 535 / 4431 / 33898 / 9872 / 60121 | TSR 码位 / 连接 / group / in / out / 旋转 | 0x14378-9 族 |
| 36041 / 90601 / 90681 | DRS 陷阱 / PSB 巨型函数族 ×2 | 0x140A1ED70 / 0x1402CDD90 等 |
| 45991 | SR_Trial B03 v240 拟合（= ~CRC32w(盐名)） | sub_1402B05C0 |

## 4. 交叉验证热点（同一函数、多文档互证）

| 函数 | 互证文档 | 价值 |
|---|---|---|
| **0x1435F7E90** | home/SRR_MT01.md §5（编排入口：调度→数字池+11392→选 Section→标牌）+ home/SR_TRIAL.md §7（协调器每步 Setup：67620 选 section、+11408/+11416） | 用户指定示例；两文档语义互补，合并即完整 |
| sub_14374E420 / sub_1436FE410 / sub_143620E70 / sub_143621120 / sub_1436FEB10 / sub_1436FD200 | CHJ_MT01 + SRR_MT01 + SR_Trial + evidence/*.c（三关同一 MultiroomPuzzle 族） | 密码链四层语义逐层互证（抽取→order→数字→贴花） |
| sub_1436E95F0 / sub_1436EA3D0 / sub_1437056A0 / sub_142C48E40 / sub_1436E7F70 | CHJ_MT02 + MHS_MT01 + O/seed.py | 同 RBProjectionCodeCoordinator 类，两关交叉验证 |
| sub_1402B05C0 / sub_1402AE7F0 / sub_1402AF490 / sub_1402C30C0 / sub_1402B3C30 / **sub_1402B4CA0** | 10+ 关卡文档（FPB_MT03 第二轮补齐 4CA0 跨区距离排除语义，§5.13/§5.14） | 通用引擎，被几乎所有协调器类复用；多协调器同图关卡的池排除必须先查 4CA0 |
| sub_14361C230 族 | PSB + PSO + SRR_MT02 + SR_Trial + DTS | 同地址多协调器类共用，语义随类不同（见 §6） |
| sub_14320CEB0 / sub_14320FB00 族 | coop/FPI_MT02 + O/gameshow.py + evidence/REA.md | GameShow 回合/数字串 |
| sub_14320B590 | coop/RES_MT01 + O/cluegame.py + RES_MT01/probe.py | ClueGame 洗牌+答案 |
| sub_1433B49B0/1433B5BC0 族 | coop/RES_MT02 + home/RES_MT02 + O/seed.py + res_mt02*.py | 珠宝主轴/教学段 |
| sub_1437E5100 | home/SRR_MT01 + O/seedcore + O/seed.py | SRR 5 选 3 |
| sub_14378FBA0 族 | coop/TSR_MT01 + TSR_MT01.py | 接线密码 |
| sub_1434B3330 | TFS_MT03 + level/TFS_MT03.md + O/seed.py | 阀门（正向模型） |
| sub_143582xxx 族 | PSA_MT01 + psa_mt01.py + O/seed.py | 钥匙树 |
| GetSeed/RandSeeded/crc32_fname/RandFraction/RandBool | **三目录全部** | 原语无分歧，可直接复用 seedcore 实现 |

## 5. 已知冲突 / 历史修正（复用前必读）

1. **sub_14374E420 抽房偏移**：旧 CHJ_MT01 记 28088 为抽房偏移 —— 实为**补位**偏移；
   抽房=28042（home/SR_TRIAL §10.1 修正；CHJ 每区不同 section 时两偏移恰好等价才没暴露）。
2. **sub_1435F7860 的 134123**：只影响标牌文本副本；处理顺序的洗牌在 sub_14374E420 内，
   比较器 `RandFraction(GetSeed(房间))` **无 +134123**（home/SR_TRIAL §10.2）。
3. **sub_14361CE40 上屏偏移**：代码读 924519，实测拟合 924523（+4，仅 B02/B03_Rich 两点支持）。
4. **sub_1402B05C0 盐名/v240**：多数关 = crc32_fname("Objective Actors")+GetSeed（+组数，
   bSplit 组洗牌自增；SRR_MT02 6/6 复证）；MHS 显式列表分支 = "Projection Actors"；
   SR_Trial B03 约束求解得 **45991+GetSeed**（盐名实值未定位）。
5. **0x141C9CE10 语义两说**：home 记 TArray::RemoveAll，coop/RES_MT02 记 {actor,key} introsort
   （疑与 sub_14018C680 混淆），复用前需重核。
6. **sub_1437B67A0/1437B8680**：属 RBToyMachineLargeObjectCoordinator（"Large Objects" 盐），
   旧 DRS 分析误套用到人体模型阶段（coop/DRS_MT01 §5 已标注）。
7. **sub_142C48E40 删除语义**：旧文档误写 RemoveAt 保序，实为 RemoveAtSwap（MHS/CHJ_MT02 修正）。
8. **66066 常量归属**：属于 sub_1435DA9D0（MinigameRooms），勿与 RES_MT02 教学段混用
   （home/RE_METHOD §7 提醒）。
9. **sub_14361C230 多义**：同一地址被 OrderedClueFrequency / UseQuestItems / CorpseSearch 等
   协调器类共用，引用时必须连同关卡/类名一起记。
10. **sub_1402B28C0 删除语义**：旧文档记"RemoveAt 保序"，SRR_MT02 9/9 序列反演钉死
    **RemoveAtSwap**（coop/SRR_MT02/ANALYSIS.md §8.4）。凡引用旧"保序"记载处以此为准。
11. **SRR_MT02 路径误判**：曾判 School/SasExit 走 sub_14361CFA0 配对路径（因配了
    ObjectiveIndexAlternatePairs）——实际 `coord+7273` 开关=0，三轮全走分组路径；
    "csdelta 待校准"框架整体作废（cs=GetSeed+组数，组洗牌自增，无需拟合）。
    配置陷阱教训：AlternatePairs 配了 ≠ 走配对路径，以开关读取点为判据。
12. **OrderedClueFrequency 无"上屏抽样"**：SRR_MT02 显示顺序 = 记录循环序（v68），
    不经 sub_14361CE40（924519/924523 只对 PSB/PSO/SR_Trial 类路径有效，见 §5.3）。
13. **★ sub_1402B05C0 的 a1 是 FRBPrimaryActorsRandomizationSetup 结构体指针**（协调器+1352），
    不是协调器本体（FPB_MT03 2026-11-04 以属性描述符表 0x145B2F600/0x145CC8AC8 实证）。
    历史文档的 "coord+1000~1632" 运行期偏移实为 setup 内偏移，完整布局：
    bools@+1000-1005（bSplitByObjectiveType / bUseRoomGroupsAsObjectiveType /
    **bUseOtherCoordoActorsForDistance**@1002 / bLimitOneObjectivePerRoom@1003 /
    bAllowRandomizionInMissionImportantSection@1004 / bOverrideDistanceBetweenSameObjectives@1005）
    → DistanceBetweenSameObjectives@+1008 → bOverrideDistanceBetweenDifferentObjectives@+1208
    → DistanceBetweenDifferentObjectives@+1216 → ZDistanceBetweenObjectivesOverride@+1416
    →（运行期 R 缓存@+1628）→ DesiredStateSetObjects（已选数组）@+1632。
    每个 FFloatByDifficulty/FIntByDifficulty 200B：{mode@+0, hasValue@+64, value@+68}。
    协调器级偏移（在协调器上直读）：+728 ObjectiveActors、+744 ObjectiveType、
    +680 ExclusiveMissionIds、+1346 bUseObjectiveActorsRandomization、+1352 setup 本体。
    属性偏移映射法：.rdata 描述符 +0x24=偏移（结构体属性 +0x28=类指针），按 0x38 步长走表。

