# 分区（Zones）清单与判定逻辑

> 本文件是「分区」这件事的唯一说明 + 现状盘点。改分区之前先看这里，改完回来更新对应行。
> 统计时间：2026-10-30（数字取自 `data/maps/*.json` 的 `zones` / `points` 实际字段）。

## 1. 什么是分区

**分区 = 任务区域（task area），不是点位分类，也不是楼层。**

- 玩家按区推进：做完一个区的任务 → 去下一个区；
- 同一类任务会**重复出现在不同分区**（每区一轮 / 每区一件）；
- 分区数量由**任务物或任务轮次**决定：2 台推车 = 2 区、4 个人偶 = 4 区、4 把图案钥匙 = 4 区、4 轮钱箱 = 1 固定 + 3 随机区；
- 分区的**标记就是该区任务物的位置**（钱箱 / 推车 / 钥匙 / 人偶 / 票机…），因为玩家要做的就是这个任务物；
- 一个区里可以有**多个候选点位**（随机抽一个生效），所以「1 区 1 点」不是硬性要求；反过来「1 区 1 点」也可能只是候选只有一个。

典型对照：

| 关卡 | 分区数 | 为什么是这个数 |
|---|---|---|
| TFS_MT02 | 2 | 要推 2 台车，Green / Pink 各 1 台 |
| PSB_MT01 | 3 | 要找 3 把图案钥匙，每个区域 1 把（未做） |
| ORI_MT01 | 4 | 要搬 4 个人偶，4 个人偶在 4 个区域 |
| PSO_MT01 | 4 | 4 个区各 1 把钥匙 |
| DRS_MT03 | 4（候选 11） | 一局 4 轮钱箱任务：第 1 轮固定 + 第 2–4 轮随机 |

## 2. 默认逻辑与特殊逻辑

- **默认：按任务区域划分。** 定区数量 → 定每区任务物 → 用任务物所在房间/实例名做 `zones`。
- **特殊逻辑必须显式声明**：在 `data/points/<关卡>.json` 的 `_说明` 里写清「本关不按任务区域分，原因是……」，并在 `zones[].note` 里说明该区含义。
  已声明的特例：
  - `DRS_MT01`：按**房间**划分（每个任务房间 = 一个区，区内是该房间的人偶模型候选）。理由：钥匙/线索只给房间，玩家先到房间再找对应武器的模型；一局启用 30 个模型、模型散在 34 个房间，按武器分会串房间。
- 分区名、`note` 用中文写玩家能直接用的信息（本区有几个任务物、要做什么、随机规则）。

## 3. 现状盘点（33 张图 / 122 个分区）

### A. 已按任务区域划分（基本符合定义）

| 关卡 | 地图 | 点位 | 分区 | 分区逻辑 | 备注 |
|---|---|---|---|---|---|
| TFS_MT02 | ToyFactoryShipping | 74 | 2 | 2 台推车 → Green（西）/ Pink（东） | 每区 1 车、2 道钥匙门 |
| TFW_MT03 | ToyFactoryWarehouse | 34 | 4 | 4 条生产线 → A/B/C/D | 每区 1 图案锁 + 1 酸桶 |
| ORS_MT01 | OrphanageServices | 41 | 2 | 2 个出票区 → 服务区 / 教堂区 | 每区 2 桶 |
| FPC_MT02 | FunParkCanal | 71 | 2 | 2 个售票亭 → Canals / Offices | 每区 5 张票 |
| DRS_MT03 | DowntownRiotSewers | 20 | 11 | 4 轮钱箱任务，1 钱箱 = 1 分区 | 第 1 轮固定 + 3 随机 |
| PSO_MT01 | PoliceStationOffices | 89 | 4 | 4 个区各 1 把钥匙 | — |
| POLICESTATION_T02 | PoliceStation | 65 | 4 | 4 道钥匙门 → 门 1…门 4 | 顺序开门 |
| RES_MT02 | ResortSpa | 318 | 4 | 4 个 section，每区 6–7 个人偶 | — |
| ORI_MT01 | OrphanageInstitution | 12 | 5 | 4 个人偶区 + Intro 固定区 | ⚠ 多 1 个 Intro，待确认是否合并 |
| MHS_MT01 | MobsterHideoutSyndicate | 45 | 5 | 3 个投影符号区 + 金库主目标 + 后坞交付 | ⚠ 后 2 个是任务链节点，不是随机任务区 |
| FPI_MT01 | FunParkIllusion | 16 | 4 | 中庭固定放映机 + 第 0/1/2 组 | ⚠ 中庭是固定点 |
| CHJ_MT03 | CourthouseJudicial | 9 | 4 | 7 个法官按翼/庭院分布 | ⚠ 按地理切，不是按"每区几把钥匙" |
| SRR_MT01 | SuburbRiotResidential | 136 | 6 | A–E 五组密码房 + F 其它 | ⚠ 多一个"其它"兜底区 |
| FPB_MT01 | FunParkBarn | 53 | 4 | **分区 = 人偶所在区域**：一局 4 个人偶、每区 1 个，26 个候选按所在房间聚成 4 片，每片带自己的解锁开关 | 关卡数据无 section 命名，区域名用序号 + 房间列表 |
| PF_LD_T12 | PrisonFarm | 114 | 2 | 密码任务分 A / B 两区（四位密码各 2 位） | 猪头 17、阀门 14 是独立任务，不分区 |
| MHS_MT03 | MobsterHideoutSyndicate | 20 | 3 | 3 片区域各藏 3 个毒品（共 9）：赌场 / Chemco 实验室 / 列车编组场 | 每区候选桶 6/8/5，每局各选 3 个 |
| MHS_MT02 | MobsterHideoutSyndicate | 31 | 1 | 毒气桶全部集中在一片区域（毒品实验室），不分区 | 29 个桶 + 2 个泵/容器（泵在列车编组场，供灌注） |
| SRR_MT03 | SuburbRiotResidential | 22 | 3 | 3 轮 3 区（完成一区解锁下一区）：富人区房屋 / 学校教学楼 / 学校后院 | 每区 6 个翻牌器；4 个轮次闸门无房间故不带分区 |

### B. 按地理/设施切，需要复核

| 关卡 | 地图 | 点位 | 分区 | 现在的逻辑 | 疑问 |
|---|---|---|---|---|---|
| DRS_MT01 | DowntownRiotSewers | 104 | 35 | 一房一区（34 房间）+ 调频器区 | 已声明为特例，但 35 个区是否仍太碎 |
| PSB_MT03 | PoliceStationBasement | 60 | 3 | 射击场军械库 / 停尸房体育馆 / 车库后巷 | 任务是投 10 个箱，3 区是否等于任务区 |
| SMC_MT02 | ShoppingMallCarrefour | 13 | 6 | 中庭 / 中央百货撤离 / 东西侧店铺 / 东西侧百货 | 任务是 4 个人偶配对，按建筑切可能不对 |
| SRR_MT02 | SuburbRiotResidential | 63 | 3 | 别墅车库 / 住宅与校门 / 校区 | 任务是调频器 + 发电机 |
| PSA_MT01 | PoliceStationAttic | 48 | 5 | 起点钥匙 / 钥匙房 / 钥匙房 / 目标与撤离 / 其它区域 | 含"其它区域"兜底区 |

### C. 还没分区或还没配点位

| 关卡 | 地图 | 现状 | 待办 |
|---|---|---|---|
| PSB_MT01 | PoliceStationBasement | 0 点位 / 0 分区 | 应为 **3 区 / 3 把图案钥匙**，待做 |
| CHJ_MT01 | CourthouseJudicial | 0 / 0 | 待配点位 |
| CHJ_MT02 | CourthouseJudicial | 0 / 0 | 待配点位 |
| FPI_MT02 | FunParkIllusion | 0 / 0 | 只有 seed 模型（GameShow），待配地图点位 |
| RES_MT01 | ResortSpa | 0 / 0 | 待配点位（谋杀案推理） |
| TFS_MT03 | ToyFactoryShipping | 0 / 0 | 待配点位（六个阀门） |
| CHouse_T04 | Courthouse | 68 | 0 | 硫酸桶 13 + 密码房 52 箱，两段任务没有区域划分 | 需要时可加区 |
| ShoppingMall_LD_B00 | ShoppingMall | 49 | 0 | 保险丝（15 个箱子 + 2 个面板）与喷泉阀门（8 站 + 24 面板），两段任务没有区域划分 | 需要时可加 A/B 区 |
| TSR_MT01 | TelevisionStudioRooftop | 8 点位 / **0 分区** | 待分区 |
| TSR_MT02 | TelevisionStudioRooftop | 19 点位 / **0 分区** | 待分区 |

## 4. 后续处理顺序（建议）

1. 先补 8 个空/无分区的关卡（C 组），它们现在连图例都没有；
2. 再复核 B 组 5 关，按「任务区域」重划；
3. 最后处理 A 组里 5 处 ⚠（ORI 的 Intro、MHS 的交付节点、FPI 的固定点、CHJ_MT03 的翼、SRR_MT01 的"其它"）——这些是"要不要把固定/流程节点也算一个区"的口径问题，定一次口径批量改。

## 5. 怎么重新统计

```powershell
cd <仓库>\ui
python -c "import glob,io,json,os;[print('%-22s zones=%-3d points=%-4d rooms_zoned=%-3d map=%s'%(os.path.basename(p)[:-5],len(json.load(io.open(p,encoding='utf-8')).get('zones') or []),len(json.load(io.open(p,encoding='utf-8')).get('points') or []),sum(1 for r in json.load(io.open(p,encoding='utf-8')).get('rooms') or [] if r.get('zone')),json.load(io.open(p,encoding='utf-8')).get('map'))) for p in sorted(glob.glob('data/maps/*.json'))]"
```

改完某关的分区后，请同步更新本文对应行（分区数 + 逻辑一句话）。
