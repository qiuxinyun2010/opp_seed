# RBRandomizableHelperComponent

> 类专属锚点速查。通用取证方法（PE 节表映射、xrefs、`+0x24` 规则、IDA 勾选 Unicode）见 `FORENSICS_METHODS.md`，不在此重复。
> 本文对象 = 关卡随机化/变体系统里挂在「可被随机开关的 actor」上的**状态组件**，是跨关卡通用环节，不是某个协调器的私有实现。
> 二进制：`TOT.exe`（base `0x140000000`）。所有偏移为组件自身偏移，不是宿主 actor 或协调器偏移。

| 项 | 值 |
|---|---|
| 类标识 | `/Script/OPP.URBRandomizableHelperComponent`（`UActorComponent` 派生） |
| 类大小 | **464 = 0x1D0**，对齐 8，flags `0x10000000` |
| 宽类名 / 反射名 | UTF-16 `0x146624616`；注册用宽串 `L"URBRandomizableHelperComponent"` |
| UClass 注册 | `sub_1414A0D40:277-284`（`sub_140B6E940(..., L"URBRandomizableHelperComponent", 464, 1860914212)` + `sub_1409DD990(sub_140B47BD0, sub_142A24B20, ...)`) |
| 惰性注册（多处） | `sub_1402B2930:70-86`、`sub_1402947F0:105-122`、`sub_1402CB480:159-176`、`sub_1402B05C0:356-374`：`sub_14035AFB0("/", L"RBRandomizableHelperComponent", &qword_146E7D920, sub_142A24AF0, 464, 8, 0x10000000, ..., sub_140B47C10, ...)` |
| 静态类缓存 | `qword_146E7D920` |
| CDO 构造 | `sub_140B47C10`（写 vfptr 与全部默认值）；注册 thunk `sub_140B47BD0` |
| 主 vfptr | `&off_145A52920`，写于组件 `+0x000` |
| 次表 / 接口表 | `+0x28`(40) = `off_145A52D40`；`+0xB8`(184) = `off_145A52D70`、`+0xC0`(192) = `off_145A52D90`、`+0xC8`(200) = `off_145A52DC0`（3 个接口） |
| 属性描述符 | 组件属性集中在 `0x145D4CED8–0x145D4D3B0`；`IsAllowedObjectiveForRandom` 描述符 `0x145D4D088`（+0x24=224） |
| 配套接口 | `RBRandomizable`（UInterface，size 40，注册 `sub_1414A0D40:254-268`，缓存 `qword_146E7D7E0`） |

## 0. 为什么要单独成文（通用性）

| 维度 | 数据 | 取证 |
|---|---|---|
| 地图实例 | `paks/MAP/Maps` 下 **2985** 个 JSON 中 **951** 个含本组件，共 **117,387** 个实例，分布 **35** 个地图组（Resort / MobsterHideout / DowntownRiot / TelevisionStudio / ShoppingMall / Courthouse / PoliceStation / ToyFactory / FunPark / Orphanage…） | `python temp/rb_helper_count.py` |
| BP 类定义 | `paks/LD/**/*.cpp` 1177 个中 **144** 个显式引用本组件 | 文本统计 |
| 通用抽取引擎 | `sub_1402B05C0`（`RandomizeObjectiveActors`）的分类趟直接读本组件 `+216/+217`，出现在 CHJ_MT02/03、DRS、FPI_MT01、MHS、PSB、PSO、SMC、SRR_MT02、SR_Trial、DTS、FPB_MT03 等 **15+ 关卡文档** | `FUNC_INDEX.md:52` |
| 状态机下游 | `PrepareState` / `IsStateA` 是 TFS_MT03、CHJ_MT03、home/CHJ_MT02、home/SRR_MT02 等关卡正向模型的公共步骤 | `FUNC_INDEX.md:46,55`；`level/TFS_MT03.md:136-143`；`level/CHJ_MT03.md:205` |
| 蓝图事件 | BP 侧通过 `RBRandomizableHelper.OnRandomStateChangedEvent` 绑定状态变化（FunPark 按钮链等） | `class/FunPark_DamageableButton_BP_chain.md:70,92-93`；`ui/README.md:191,405,523` |

结论：凡是要解释「这局哪些任务点位有效」，几乎都会遇到本组件；把它按**类级锚点**单独整理，避免在每关文档里重复推偏移。

## 1. 取证链

```text
宽类名 0x146624616 / ASCII 反射名
  → sub_1414A0D40:277-284 的 UClass 注册表项（size 464, off_145D4DF88, ctor sub_140B47BD0）
  → 多处 sub_14035AFB0 惰性注册给出同一 size 与 CDO sub_140B47C10
  → 反编译 sub_140B47C10：*v1 = &off_145A52920、a1+40/+184/+192/+200 四张次表、
      以及全部字段默认值（+216 WORD=0、+224=6、+320=0x01010101、+328=300.0f …）
  → 属性名 ASCII → 指向名字的 qword → 描述符 +0x24 = 偏移
      （IsAllowedObjectiveForRandom@224、ActorsToMatchState@296、
        ActorsToInverseMatchState@312、SharedActorsToMatchState@376、
        SharedActorsToMatchStateGroupName@392、bForceUseObjectiveInRandom bool）
  → 接口函数 FName 列表 sub_1414A0D40:262-268
  → 消费者：sub_1402B05C0 / sub_1402B2930 / sub_1402947F0 / sub_1402B2E50 /
            sub_1402CB480 / sub_1402CDD90 / sub_140B47990
```

`pe_probe.py desc` 的对齐基准取 `0x145D4D088`（`IsAllowedObjectiveForRandom`），
步长 `0x30`；`+0x24=1` 的条目是 **bool 位掩码**，字节偏移要靠 CDO 写入或既有实测确认，
不要当成「偏移 1」。

## 2. 属性 + 偏移

类大小 464；`UActorComponent` 父类占前 ~184 字节，本类字段自 `+184` 起。

| 偏移 | 属性 / 语义 | 类型与 CDO 默认 | 证据 |
|---:|---|---|---|
| `+216` | `ERandomState`：`0=None / 1=StateA / 2=StateB` | WORD 清零 | CDO line 15；`sub_1402CB480:180` 读 BYTE 作 0/1/2 匹配；`TFS_MT03.md:138-139` |
| `+217` | `bForceUseObjectiveInRandom`（必选标志） | WORD 高字节，CDO=0；描述符 `0x145D4D050`（+0x24=1，bool） | `sub_1402B05C0:379`；`FUNC_INDEX.md:52`「+217 必选」；`CHJ_MT03.md:236-239`（只在教学 `_4` 为 true） |
| `+224` | `IsAllowedObjectiveForRandom` | `FConfigurableBool`；CDO `BYTE@224=6`、`+320=0x01010101`（4 档全 true）、`+282/283=1` ⇒ 默认取值为 **true** | 描述符 `0x145D4D088`；取值器 `sub_1419BF030` |
| `+296` | `ActorsToMatchState` | `TArray<FSoftObjectPath>`（16B），与状态一致才可用 | 描述符 `0x145D47C80`（+0x24=296） |
| `+312` | `ActorsToInverseMatchState` | 同上，状态**相反**才可用 | 描述符 `0x145D47CE0`（+0x24=312） |
| `+320` | 4 个难度默认值 | `0x01010101` | CDO line 25 |
| `+322` / `+323` | 状态传播开关 | `+322==1` 才传播；`a2==1 \|\| !+323` 时传播第二组 | `sub_1402B2E50:79,303` |
| `+328` | 300.0f | float | CDO line 27 |
| `+344` / `+352` | 第一组解析后的 actor 数组 / Num | `TArray`（40B/项） | `sub_1402B2E50:81-84` |
| `+360` / `+368` | 第二组解析后的 actor 数组 / Num | 同上 | `sub_1402B2E50:305-307` |
| `+376` | `SharedActorsToMatchState` | `TArray`（外壳项 +0x24=0，内层 376） | 描述符 `0x145D4D350` |
| `+392` | `SharedActorsToMatchStateGroupName` | FName/FString | 描述符 `0x145D4D380` |
| `+456` | 末尾字段 | CDO 清零 | CDO line 37 |

同表邻近的 UFUNCTION / 委托名：`BP_IsStateA`、`BP_SetIsStateA`、`BP_ShouldBeIgnoredForLots`、
`GatherAllLinkedInverseActors`、`SelectLinkedActors`、`OnRep_RandomState`、`bToggleActorOnStateA`
（`0x145D4CED8–0x145D4D0B8`）。附近还有 `ERandomState::{None,StateA,StateB}`、
`bStateA`、`PrepareState`、`SetState`，属于接口/其它随机化类，勿混。

## 3. 接口与 UFunction

`RBRandomizable` 接口（`sub_1414A0D40:254-268`，缓存 `qword_146E7D7E0`，size 40）：

| FName 全局 | 名字 | 用途 |
|---|---|---|
| `qword_146E7D7E8` | `GetStateName` | 调试/日志 |
| `qword_146E7D7F0` | `IsRandomStateSet` | 状态是否已设置 |
| `qword_146E7D7F8` | `IsStateA` | **主循环重建有效池的谓词** |
| `qword_146E7D800` | `PrepareState` | 写状态 |
| `qword_146E7D808` | `SetShouldBeIgnoredForLots` | 批次剔除 |
| `qword_146E7D810` | `SetState` | 写状态 |
| `qword_146E7D818` | `ShouldBeIgnoredForLots` | 批次剔除查询 |

- `sub_140B47990` = `IsStateA` 的 C++ 包装：`sub_141983CE0(a1[2], qword_146E7D7F8, 1)` 找 UFunction →
  `call [vt+544]` → 返回 `bool & 1`；找不到则经 `sub_143AC6F90` 取接口对象调 `+24` 槽。
- 组件通过 `call [vt+1584]` 从宿主 actor 取回（`sub_1402947F0:123`、`sub_1402CB480:177`），
  这是「actor → helper」的标准取法。
- BP 侧另有 `OnRandomStateChangedEvent` 组件委托，`FunPark_DamageableButton_BP_chain.md` 有绑定实例。

## 4. 状态模型（三态）

```text
PrepareState(actor, 1) ─→ helper state = 2−1 = 1 = StateA   （被选中/启用）
PrepareState(actor, 0) ─→ helper state = 2−0 = 2 = StateB   （未选中/关闭）
```

- `sub_1402947F0` / `sub_1402B2930`：`URBRandomizable::PrepareState` 包装，
  取组件 → `sub_1402B2E50(comp, 2−state)` → `sub_14052F3F0(comp, 2−state)` →
  通过 FName `PrepareState` / `SetState` 转发给宿主 actor；找不到组件时打日志
  `"URBRandomizable::PrepareState was call on object %s that is not randomizable ..."`。
- `sub_1402B2E50(comp, a2)`：**把关联对象标记为本批次忽略，而不是给它们写状态值**。
  门控 `!byte_146E40448 && comp+322==1`（CDO `+320=0x01010101` ⇒ `+322=+323=1`）；
  遍历 `comp+344`（Num@+352，对应 `ActorsToMatchState`）的 40B/项软引用数组，
  解析成 actor 且实现 `RBRandomizable` 接口后，调 UFunction
  **`SetShouldBeIgnoredForLots(true)`**（FName `qword_146E7D808`，`call [vt+544]`，
  `v75=1` 恒定，见 `:270-275`）；仅当 `a2==1 || !comp+323`（即 StateA，或「不只在 StateA」）
  时，再对 `comp+360`（Num@+368，对应 `ActorsToInverseMatchState`）做完全相同的调用
  （`:475-480`）。所以「Inverse」体现在**门控条件**与 BP 侧
  `bOnlyUseInverseMatchActorsOnStateA`，不在转发参数里；传播方向是候选→关联对象，
  **代码里没有关联对象回写候选状态的路径**。这就是三组状态引用产生跨系统联动的地方。
- `sub_140B47990` = `IsStateA`：主循环用它在抽取后重建「有效池」，
  `TFS_MT03.md:136-143` 记录了由此引发的 `39135` 退化（有效池只剩 1 个）。
- 注意区分：TFS_MT03 里 `sub_1437DD5F0` 写的「组件状态 1 / 4」与
  `sub_1434B56D0` 判的 `component+5916 == 1` 属于**另一套协调器组件状态**，
  不是本组件的 `+216`。

## 5. 与通用抽取引擎 `sub_1402B05C0` 的接口

`sub_1402B05C0` 是跨关卡共用的 `RandomizeObjectiveActors`（`FUNC_INDEX.md:52`）：
名字序排序 → 分类趟 → 跨协调器距离排除 → 分组/quota → 逐组抽 `RandSeeded(v246+已选总数, 池剩余)`
+ `RemoveAtSwap` → `sub_1402B3C30` 距离/状态/同房间过滤。本组件在其中的作用点：

| 位置 | 判定 | 结果 |
|---|---|---|
| 分类趟 `:379-390` | `comp+217 == 1` | 写入 `v250` **强制预选**（占用配额、抽选起点提前） |
| 分类趟 `:389` | `!sub_1419BF030(comp+224)`（即 `IsAllowedObjectiveForRandom` 为 false） | 走 `LABEL_76` 进普通池 `v251` 或按分支剔除 |
| 分类趟 `:393-407` | 无 `RBRandomizable` 接口 / `RBReplacedActorInterface` 状态 | 分流到 `v248`/`v250`/`v251` |
| `:702-736` | `v248`/`v250` 预选数组先写进结果 `setup+1632`，并减少剩余 `DesiredCount` | 最终席位 = 预选项 + 抽取项 |
| `:1027-1038` | `Src` 剩余项并入 `v251` | 补足循环从 `v251` 取 |
| `sub_1402B3C30:203-209,393-399` | 每次抽取后再查 `RBRandomizable` 状态 | 不通过者从池中 swap 剔除（分母随之变化） |
| `:1271-1294` / `sub_1402B2930` | 未选中候选 `PrepareState(actor, 0)` | 统一置 StateB |

`FUNC_INDEX.md:52` 的既有实测记「`+216` 剔除 / `+217` 必选，实测均 false」——
即多数关卡这两个分支不触发；`CHJ_MT03.md:236-239` 也只在教学点位见到
`bForceUseObjectiveInRandom=true`。**因此不要默认 41/87 个候选全部等价**：
是否触发要先看地图 JSON 里该组件导出的属性（未导出即用 CDO 默认），
再看同 seed 上游变体链写入的 `+216/+217`。

## 6. 上游随机组链（状态由谁写）

```text
sub_1402CDD90   关卡级随机组选择
    RandSeeded(GetSeed(actor) + pool.Num + 90601, pool.Num) + RemoveAt   [FUNC_INDEX.md:65]
    → 抽到一个 RBRandomGroup（PSB_LD_Traps 里是 SoundTrap_RandomGroup_C，191 组 / 925 成员）
sub_1402CB480   组内状态配置
    遍历 group+592 配置表（40B/项，Num@+600），按 comp+216 的 0/1/2 匹配模式筛可用配置
    RandSeeded(GetSeed(group) + 90681, 可用配置数)   [FUNC_INDEX.md:64]
    → 对组内每个成员 sub_1402947F0(actor, bit==1, 0) 写 StateA/StateB
sub_1402B2E50   状态沿 ActorsToMatch/Inverse/Shared 传播到其它 actor 的 helper
```

相关静态配置：`SoundTrap_RandomGroup_C : URBRandomGroup`（`paks/LD/Obstacle/SoundTrap_RandomGroup.cpp`），
BP CDO 有 `bOnlyUseInverseMatchActorsOnStateA` / `VariatorType` / `DisabledItemContainerDistance`；
`RBObstacleVariatorComponent`、`RBRoomAssociationComponent` 与
`ERandomGroupIgnoreRule::{RandomGroup,AnyRandomActor,AllRandomActor}` 同属这套系统。
`90601 / 90681 / 36041` 是这套随机组/陷阱函数族的常数（`FUNC_INDEX.md:310`）。

`RBRandomGroup` 类锚点（跨关通用）：宽类名 `0x146708C9C`，UClass `sub_140895D60`
（`sub_14035AFB0("/", L"RBRandomGroup", &qword_146E7D768, sub_1426E6F60, 640, 8, ...)`），
CDO `sub_1406388F0` → `sub_140638900`（vtable `off_145A4C420`，次表 `+560/+568/+576`，
`+584`=1，`+592` Root 组件，`+600` 本组件实例并把 `+320/+323` 清零），
UFUNCTION 表 `off_145D4B9C0`（7 项，注册器 `sub_1426E6F60`）。
状态配置属性名 `RandomActorsSetup`（描述符 `0x145D4FB08/FB38`，内层偏移 72/16）与
`RandomActorsStates_Server`（`0x145D4F3D8`，偏移 928/88）已定位；
191 个 BP 实例与 BP CDO 都未导出该数组，它对应 `sub_1402CB480` 里 `a1+592/+600`
的 40B/项配置表（状态位数组@+16、长度@+24）——这是「按 seed 定状态」的静态输入，
从 `.uasset` 字节码或一次运行期 dump 可补。

该表的构造链（跨关通用）：`sub_1402CEA50(group, out)` 遍历 `group+576` 的
`RandomActors`（40B/项，Num@`+584`），对每个成员取 `RBObstacleVariatorComponent`
（`call [vt+1584]`）读 **`comp+192` 的 1 字节标签**，按标签分桶生成配置；
`sub_1402CB480` 用 `RandSeeded(GetSeed(group)+90681, 可用配置数)` 抽一条写入
`group+628`；`sub_1402B5BD0` 按选中配置里 `bits[i]==1` 的位数组落地状态。
`RBObstacleVariatorComponent` size 224、CDO `sub_140B3C0C0`
（`*(WORD*)(+192)=256` ⇒ 默认字节 0、`+216=-1.0f`）；标签通常由 BP 的
`OnWorldPopulateFinished` / `ConstructTags` / `InitializeRandomGroupTag` 写入，
故静态 JSON 看不到——这也是「同一 seed 下候选池被剔除」的最终来源。

### 6.1 `SoundTrap_RandomGroup_C` 类锚点

`paks/LD_json/LD/Obstacle/SoundTrap_RandomGroup.json`（21 个对象）与
`paks/LD/Obstacle/SoundTrap_RandomGroup.cpp`；原始资产在
`paks/LD_uasset/Obstacle/SoundTrap_RandomGroup.{uasset,uexp}`。

| 项 | 值 |
|---|---|
| 继承 / 接口 | `URBRandomGroup`（native，size 640，UClass `sub_140895D60`）；实现 `RBWorldPopulateInterface`（`bImplementedByK2`） |
| 组件 | `Root` / `DefaultSceneRoot`（SceneComponent，Mobility=Static）；`RBObstacleVariator`（`VariatorType=EObstacleVariatorType::SoundTraps`）；`RBRoomAssociation`（Static）；native `RandomizableHelperComponent` |
| 本组件 CDO 覆盖 | `bOnlyUseInverseMatchActorsOnStateA = True`、`DisabledItemContainerDistance = 500.0` |
| 变量 | `UberGraphFrame`、`LinkedTraps : TArray<URBObstacleVariatorComponent*>` |
| 函数（10） | `ExecuteUbergraph_SoundTrap_RandomGroup`、`TickSelected`（覆写 `RBEditorUtilityInterface`）、`OnWorldFullyLoaded`、`ReceiveBeginPlay`、`OnWorldPopulateFinished`、`OnComputeClearanceStep`、`UserConstructionScript`、`InitializeRandomGroupTag`、`ConstructTags`、`OnWorldPopulateFinishedTimeSliced` |
| 关键函数签名 | `InitializeRandomGroupTag(bAllHangingSoundTraps, AllRandomActors)`；`ConstructTags(CachedRandomActors, bHangingSoundTrapGroup)`；`OnWorldPopulateFinishedTimeSliced(ReturnValue)` |
| BP 行为（由函数局部变量名还原） | `ExecuteUbergraph` 调 native `GetRandomActors()` → 遍历成员、dynamic cast 到 `SoundTrap_Base_BP` / `RB_Sound_Trap` → `GetComponentByClass` 取变体组件 → `Array_Add` 进 `LinkedTraps`；`InitializeRandomGroupTag` / `ConstructTags` 用 `Array_AddUnique` / `Array_RemoveItem` / `Array_IsEmpty` 和 `Temp_name_Variable*` 给成员打 Actor Tags（`HangingSoundTrap` 等） |
| 关卡实例 | `PSB_LD_Traps.json` 里 191 个 `SoundTrap_RandomGroup_C`，每个都有 `RandomActors`（共 925 个成员，多为 `SoundTrap-Cans-01_BP*` 等） |

**要点**：这个 BP **不声明也不构造 `RandomActorsSetup`**——`ChildProperties` 只有
`UberGraphFrame` / `RBRoomAssociation` / `RBObstacleVariator` / `LinkedTraps`，
CDO 也没有该数组。它只负责「取成员 → 打 Tags → 收集 `LinkedTraps`」；
`+592` 的 40B/项状态配置表是 native 侧按成员标签构造的（§6）。
因此把它当成「候选池剔除的直接来源」是不准确的：它是同一套变体框架的一个类实例，
本关 41 具尸体的 36 条状态引用里只有 **2 条**直接指向 `SoundTrap_RandomGroup_C` 实例，
**0 条**指向这 925 个 `RandomActors` 成员。

## 7. 各关卡已验证行为（交叉引用）

| 关卡 | 已验证结论 | 来源 |
|---|---|---|
| TFS_MT03 | `PrepareState(v,1)→StateA`、其余 `PrepareState(v,0)→StateB`；`IsStateA` 重建有效池使 `39135` 退化；527527/41041 正向回归 12/12 | `level/TFS_MT03.md:74-84,115-143` |
| CHJ_MT03 | 未选中候选统一 `PrepareState(0)=StateB`；主段 8 个交付点只有三组状态列表、无 `bForceUseObjectiveInRandom`；`sub_1402B3C30` 过滤后分母动态变化，150150/892892 五席集合命中 | `level/CHJ_MT03.md:172-243` |
| SRR_MT02 | 名字序 + 组数自增 + swap 过滤 6/6；`sub_1402B05C0` 与 `sub_1402B2930` 成对出现 | `FUNC_INDEX.md:52,55` |
| FPB_MT03 | 三区域 6/6 复证 `v246` 基址公式；`sub_1402B4CA0` 跨协调器距离排除定标 | `FUNC_INDEX.md:52,60` |
| PSB_MT01 | 41 具尸体组件：20 具带 36 条跨层状态引用；`IsAllowedObjectiveForRandom` 仅 5 具导出 Hard/Insane 覆盖；3 把真钥匙图案正向 9/9，具体尸体待上游变体链补齐 | `release/coop/PSB_MT01/PSB_MT01_forward.md` §5.3 |
| FunPark 按钮链 | BP 绑定 `OnRandomStateChangedEvent`，导出 `IsStateA` / `PrepareState` / `SetState` / `ShouldBeIgnoredForLots` 等函数 | `class/FunPark_DamageableButton_BP_chain.md:70,92-93` |

### 7.1 判定「哪些 helper 与某个候选池有关」（通用方法）

一个关卡可能有数千个本组件实例（PSB_MT01 为 2322 个），但真正进入某个
`sub_1402B05C0` 候选池判定的只有候选 actor 自己。可按四层收敛：

1. **直接输入**：候选 actor（如 PSB 的 41 具尸体）自身的 helper —— 分类趟
   `sub_1402B05C0:378-421` 与每抽后 `sub_1402B3C30` 只读它们；
2. **一级传播目标**：这些 helper 的 `ActorsToMatchState@296` /
   `ActorsToInverseMatchState@312` / `SharedActorsToMatchState@376` 软引用指向的对象，
   由 `sub_1402B2E50` 接收状态（方向是候选→目标，**不回写**）。
   统计它们是否挂 helper：没挂的对象不实现 `RBRandomizable` 接口，传播时被跳过；
3. **二级链**：非候选宿主自己也带状态引用数组的 helper（PSB 全图 37 个带数组：
   21 个候选 + 16 个其它），构成链式传播；
4. **背景**：其余宿主（陷阱/装饰/灯具/海报…）多数只是随机组的被动成员，
   是否相关要用「候选引用是否命中该组成员列表」正向验证，不能凭同框架推断。

两个常见排除：slot 249 的 `PrimaryActorsRandomizationSetup` 通常只作用于
`ObjectiveActors`（PSB 里是 3 个 KID），不给 spawner 候选写状态；
`PrepareState` 的调用者里要区分「随机化之后的补足循环」（`sub_1402B05C0` 自身）
与「随机化之前的关卡级入口」（如 `sub_14019F790`），只有后者能决定分类趟看到的 `+216` 初值。

## 8. 常见坑

1. `+0x24=1` 的属性描述符是 **bool 位掩码**，不等于字节偏移 1；字节偏移用 CDO 写入点或既有实测定位。
   `bForceUseObjectiveInRandom` 描述符 `0x145D4D050` 只给出 bool 类型，把它对应到 `+217` 的依据是
   `FUNC_INDEX.md:52` 与 `CHJ_MT03.md:236-239` 的既有实测，不是描述符本身。
2. 地图 JSON 里组件对象的 `Properties` 常常**只导出与 CDO 不同的项**；`IsAllowedObjectiveForRandom` 导出
   `{"DefaultValues":{"bOverrideHardLocalValue":true,...}}` 只表示难度覆盖，不代表当前值。
3. `+216/+217` 是**运行期状态**，不出现在静态 JSON；同一 seed 下由 §6 的随机组链写入。
4. 别把本组件 `+216` 的 `ERandomState` 与 TFS_MT03 的 `component+5916 == 1`（另一套状态）混淆。
5. `sub_1402B4CA0` 是**跨协调器目标距离排除**（`FUNC_INDEX.md:60` 已勘误），不是「可达性预过滤」；
   多协调器同图关卡模型对不上时优先查它。
6. `sub_1419BF030` 是 `FBoolByDifficulty` 取值器：先按覆盖位算各难度，再按当前难度回落；
   难度/人数取 `sub_141D2A240()+628`（`TFS_MT03.md:99`）。

## 9. 复现与关联

```powershell
cd c:\Users\DELL\AppData\Local\Temp\outlast
python temp\rb_helper_count.py                              # 跨地图实例统计
python temp\rb_helper_scan.py                              # 属性描述符扫描
python release\coop\tmp\pe_probe.py str RBRandomizableHelperComponent both
python release\coop\tmp\pe_probe.py desc 0x145D4D050 12     # 对齐后的属性名/偏移
```

IDA 复核点：`decompile_function(0x1414A0D40)`（注册与 FName 列表）、`0x140B47C10`（CDO）、
`0x140B47990`（IsStateA）、`0x1419BF030`（BoolByDifficulty）、`0x1402B2E50`（状态传播）、
`0x1402947F0` / `0x1402B2930`（PrepareState）、`0x1402B05C0`（通用抽取引擎）、
`0x1402B3C30`（过滤）、`0x1402CB480` / `0x1402CDD90`（随机组链）。

关联：`FORENSICS_METHODS.md`、`FUNC_INDEX.md`、`SEED_FORMULAS.md`、
`class/RBUseQuestItemsObjectiveCoordinator.md`、`class/RBProjectionCodeCoordinator.md`、
`class/TFS_MT02_Coordinators.md`、`class/FunPark_DamageableButton_BP_chain.md`、
`level/TFS_MT03.md`、`level/CHJ_MT03.md`、`ui/README.md`、
`release/coop/PSB_MT01/PSB_MT01_forward.md` §5.3、`release/coop/PSB_MT01/RBCorpseSearchObjectiveCoordinator.md`。
