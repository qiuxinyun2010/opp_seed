# FunPark DamageableButton 蓝图继承链

> 三层蓝图类的属性、CDO 默认值、UFunction 与接口对照。C++ 侧的静态偏移 / vtable 见 `RBOperatable.md`，目标类专属锚点见 `FunParkCanal_Drop_DamageableButton_BP_RightCanal.md`。
> 资产目录：`pak/LD/Operatable/ThrowableTargets/`（相对工作区根 `outlast/`）。

## 1. 链与文件

```text
/Script/OPP.RBOperatable (C++, 1608B)
  └ USimple_DamageableButton_BP_C            15 项新增属性 / 18 个 UFunction
      └ UFunPark_Drop_DamageableButton_BP_Child_C   12 项新增属性 / 13 个 UFunction
          ├ UFunParkCanal_Drop_DamageableButton_BP_LeftCanal_C   0 新增 / 2 UFunction
          └ UFunParkCanal_Drop_DamageableButton_BP_RightCanal_C  0 新增 / 2 UFunction  ★目标
旁支（不在链上）：UDamageableButton-01_BP_C : URBOperatable
```

| 类 | cpp | json | SuperStruct |
|---|---|---|---|
| `USimple_DamageableButton_BP_C` | `Simple_DamageableButton_BP.cpp` | `Simple_DamageableButton_BP.json` (92715B) | `Class'RBOperatable'` |
| `UFunPark_Drop_DamageableButton_BP_Child_C` | `FunPark_Drop_DamageableButton_BP_Child.cpp` | 同名 .json (48758B) | `BlueprintGeneratedClass'Simple_DamageableButton_BP_C'` |
| **目标类** | `FunParkCanal_Drop_DamageableButton_BP_RightCanal.cpp` | 同名 .json (15640B) | `BlueprintGeneratedClass'FunPark_Drop_DamageableButton_BP_Child_C'` |
| `..._LeftCanal_C` | 同名 .cpp | 同名 .json (15574B) | 同 `..._Child_C` |
| `UDamageableButton-01_BP_C` | `DamageableButton-01_BP.cpp` | 同名 .json (88634B) | `URBOperatable` |

`BlueprintGeneratedClass` 的 `ClassFlags` 五者一致：`CLASS_Config | CLASS_Optional | CLASS_ReplicationDataIsSetUp | CLASS_CompiledFromBlueprint | CLASS_HasInstancedReference`，`ClassConfigName=Engine`，`bCooked=true`。

## 2. 各层新增属性（JSON `ChildProperties`）

cpp 是 SDK 风格转储，会把 C++ 继承属性一并展开；**只有 JSON 的 `ChildProperties` 才是该类真正新增的实例字段**。

### 2.1 `USimple_DamageableButton_BP_C`（15 项）

| 属性 | Type | ElementSize | PropertyFlags / Inner |
|---|---|---:|---|
| `UberGraphFrame` | StructProperty | 16 | `Transient \| DuplicateTransient`，`ScriptStruct'PointerToUberGraphFrame'` |
| `RBPing` | ObjectProperty | 8 | `BlueprintVisible \| InstancedReference \| NonTransactional`，`RBPingComponent` |
| `Ngr_Temp_Sys_14_Obj_CrankSparkBurst` | ObjectProperty | 8 | 同上，`NiagaraComponent` |
| `RBOutline` | ObjectProperty | 8 | 同上，`RBOutlineComponent` |
| `RBDamageable` | ObjectProperty | 8 | 同上，`RBDamageableComponent` |
| `RBRandomizableHelper` | ObjectProperty | 8 | 同上，`RBRandomizableHelperComponent` |
| `RBObjectiveActor` | ObjectProperty | 8 | 同上，`RBObjectiveActorComponent` |
| `TriggerablesToTriggerOnHit` | ArrayProperty | 16 | `Inner: SoftObjectProperty(48B, RBTriggerable)` |
| `TriggerablesToUntriggerOnHit` | ArrayProperty | 16 | 同上 |
| `StaticMesh` | ObjectProperty | 8 | `Class'StaticMesh'` |
| `LinkedTranslationMovables` | ArrayProperty | 16 | `Inner: SoftObjectProperty(48B, TranslationMovable_BP_C)` |
| `LinkedRotationMovables` | ArrayProperty | 16 | `Inner: SoftObjectProperty(48B, RotationMovable_BP_C)` |
| `bDeactiveFullNetworkSyncChain` | BoolProperty | 1 | `ByteOffset=0, ByteMask=1, bIsNativeBool=true` |
| `bDeactivateOnlyManuallyLinkedActors` | BoolProperty | 1 | 同上 |
| `StimuliOffset` | StructProperty | 12 | `ScriptStruct'Vector'` |

cpp 里的其余属性（`OperateTime`、`bCanBeOperatedByInteraction`、`bAutoStopWhenCompleted`、`IsInteractible`、`InteractionZoneBox`、`InteractionMesh`、`InteractibleRootComponent`、`RandomSeed`、`RootComponent`、`InteractionText`、`PlayerInteractionData`、`CameraPitchLimit` 等）来自 C++ 基类，不是本层新增。

### 2.2 `UFunPark_Drop_DamageableButton_BP_Child_C`（12 项）

| 属性 | Type | ElementSize | 说明 |
|---|---|---:|---|
| `UberGraphFrame` | StructProperty | 16 | 蓝图 VM 帧 |
| `RBSound` | ObjectProperty | 8 | `RBSoundComponent`，`NonTransactional` |
| `Drop_Timeline` | ObjectProperty | 8 | `TimelineComponent` |
| `Drop_Timeline_DropAngle_5FCF367346504CA623763388BD3596BC` | FloatProperty | 4 | Timeline 生成字段（cpp 中为 private） |
| `Drop_Timeline__Direction_5FCF367346504CA623763388BD3596BC` | ByteProperty | 1 | `Enum'ETimelineDirection'` |
| `ActiveTargetSoundStart` | ObjectProperty | 8 | `AkAudioEvent`（`SFX_Objective_SlidingTarget_Interior_lp`） |
| `ActiveTargetSoundStop` | ObjectProperty | 8 | `AkAudioEvent`（`..._lp_Stop`） |
| `bInvertDropSide` | BoolProperty | 1 | `Edit \| BlueprintVisible` |
| `HitAnimPlaying` | BoolProperty | 1 | `DisableEditOnInstance` |
| `bDynamicDropSide` | BoolProperty | 1 | `Edit \| BlueprintVisible` |
| `bIsLoopingSound` | BoolProperty | 1 | `DisableEditOnInstance` |
| `bHasBeenHit` | BoolProperty | 1 | `DisableEditOnInstance` |

UClass 元数据（`Properties`）：`DynamicBindingObjects`（1 个 `ComponentDelegateBinding`，绑定 `RBRandomizableHelper.OnRandomStateChangedEvent`）、`Timelines`（`Drop_Timeline_Template`）、`SimpleConstructionScript`、`InheritableComponentHandler`、`UberGraphFunction`。

### 2.3 目标类 / LeftCanal（0 项）

两者 `BlueprintGeneratedClass` 条目**没有 `ChildProperties`**，只含 `Properties`（`SimpleConstructionScript`、`InheritableComponentHandler`）、`Children` / `FuncMap`（2 个函数）、`Interfaces`、`ClassDefaultObject`。即：只做 CDO 覆盖与接口实现，不新增实例字段。

## 3. CDO 默认值对照

| 类 | `RandomSeed` | 其它默认值（cpp） |
|---|---:|---|
| `UDamageableButton-01_BP_C` | 758509635 | `InitialLocation=(0,0,0)`、`Destination=(0,-2,0)`、`bLightIsOnButton=true`、`CanBeDamagedLightColor=(0,1,0,1)`、`CannotBeDamagedLightColor=(1,0,0,0)`、`OperateTime=0.01`、`bAutoStopWhenCompleted=true`、`bHasDeprecated=true` |
| `USimple_DamageableButton_BP_C` | 97264942 | `StaticMesh=FP_Target-HuntingRange-01`、`StimuliOffset=(0,50,0)`、`OperateTime=0.01`、`bCanBeOperatedByInteraction=false`、`bAutoStopWhenCompleted=true`、`bHasDeprecated=true` |
| `UFunPark_Drop_DamageableButton_BP_Child_C` | 1516456114 | `ActiveTargetSoundStart/Stop` 指向 `SFX_Objective_SlidingTarget_Interior_lp[_Stop]`；CDO `IsInteractible.ApplyDesiredStateCallback → IsInteractiveChangedCallback` |
| `..._LeftCanal_C` | 2083139261 | 与目标类同构 |
| **目标类** | **1543793506** | 同上 callback；`InteractionZoneBox`/`InteractionMesh`/`InteractibleRootComponent`/`RootComponent` 指向本类 CDO 的 `InteractionZone`/`InteractMesh`/`SceneComp` |

`IsInteractible` 的 `ApplyDesiredStateCallback` 在 `Child`/目标/Left 的 CDO 中都指向 `IsInteractiveChangedCallback`。

## 4. UFunction 清单

| 类 | 数量 | 函数 |
|---|---:|---|
| `USimple_DamageableButton_BP_C` | 18 | `ExecuteUbergraph_Simple_DamageableButton_BP`, `BndEvt__Simple_..._RBRandomizableHelper_K2Node_ComponentBoundEvent_2_OnRandomStateChangedEvent__DelegateSignature`, `BndEvt__DamageableButton-01_BP_RBDamageable_K2Node_ComponentBoundEvent_1_OnNumberOfHitsChanged__DelegateSignature`, `BndEvt__RBDamageable_K2Node_ComponentBoundEvent_0_OnNumberOfHitsChanged__DelegateSignature`, `SetState`, `SetShouldBeIgnoredForLots`, `PrepareState`, `UserConstructionScript`, `OnHIt`, `RefreshShineState`, `ShouldDisableNetworkSync`, `ReplacePingLocation`, `ShouldBeIgnoredForLots`, `IsStateA`, `GetStateName`, `IsRandomStateSet`, `CanBeActivedInSpectra`, `GetCustomSpectraBox` |
| `UFunPark_Drop_DamageableButton_BP_Child_C` | 13 | `ExecuteUbergraph_FunPark_Drop_DamageableButton_BP_Child`, `OnNetworkSyncPlayingStateChanged_Event`, `ReceiveBeginPlay`, `BndEvt__..._RBRandomizableHelper_K2Node_ComponentBoundEvent_0_OnRandomStateChangedEvent__DelegateSignature`, `Event_OnResetStage`, `Event_SnapToState`, `OnHIt`, `Drop_Timeline__UpdateFunc`, `Drop_Timeline__FinishedFunc`, `ComputeDynamicDropSide`, `UpdateLoopingSound`, `ShouldLoopingSoundBeActive`, `TryGetNetworkSyncComponent` |
| 目标类 / LeftCanal | 2 | `GetObjectiveTypeIndex`, `ShouldDiscardOtherObjectiveActorForRandomization` |

函数条目字段：`Type=Function`、`Outer` 指向本类 `BlueprintGeneratedClass`、`ChildProperties`（参数/返回值，含 `ElementSize`、`PropertyFlags`、`ByteMask`）、`FunctionFlags`（如 `FUNC_Event | FUNC_Public | FUNC_HasOutParms | FUNC_BlueprintCallable | FUNC_BlueprintEvent | FUNC_BlueprintPure | FUNC_Const`）。

## 5. 接口

| 类 | `Interfaces`（`bImplementedByK2=true`, `PointerOffset=0`） |
|---|---|
| `USimple_DamageableButton_BP_C` | `Class'RBRandomizable'`、`Class'RBSpectraSkillTarget'`（本次读到 2 项） |
| `UFunPark_Drop_DamageableButton_BP_Child_C` | 无 `Interfaces` 字段 |
| 目标类 / `..._LeftCanal_C` | `Class'RBObjectiveRandomizable'` |
| `UDamageableButton-01_BP_C` | `Class'RBRandomizable'` |

`PointerOffset=0` + `bImplementedByK2=true` 表示接口由蓝图 K2 实现，不占 C++ 接口 vptr（`RBOperatable.md` §4 的 `+560/+1192` 是另外两张 C++ 表）。

## 6. JSON 结构与运行时偏移

顶层是**数组**，元素为对象导出记录：`Function` / `BlueprintGeneratedClass` / CDO / `SceneComponent` / `StaticMeshComponent` / `RBInteractionZoneComponent` / `NiagaraComponent` / `SCS_Node` / `SimpleConstructionScript` / `InheritableComponentHandler` / `TimelineTemplate` / `CurveFloat` 等。

常见字段：`Type, Name, Flags(RF_*), Class, Outer{ObjectName,ObjectPath}, Package, Super, Properties, SuperStruct, Children, FuncMap, ClassFlags(CLASS_*), ClassWithin, ClassConfigName, Interfaces, bCooked, ClassDefaultObject, Template, ChildProperties, FunctionFlags(FUNC_*), ElementSize, PropertyFlags, FieldSize, ByteOffset, ByteMask, FieldMask, BoolSize, bIsNativeBool, Inner, Struct, PropertyClass`。

**不含**：属性运行时偏移（`Offset`）、实例大小、vtable / vfptr。因此蓝图层属性偏移只能运行时遍历 `ChildProperties` 按 `ElementSize` 累加并对齐；本次未验证运行期布局，不要据此推算具体数值。

## 7. 备注

- `UDamageableButton-01_BP_C` 是同父类旁支（`URBOperatable`），不是目标链的一环；其属性（`ButtonBase`、`TargetHitTimeline`、`ScoringPointsForFirstInteraction`、`InteractionCompleted` 等）勿并入目标类。
- 组件模板链：`目标 CDO → Child CDO → Simple CDO`，`InheritableComponentHandler` 只覆写 Niagara 组件模板。
- `RootComponent` 与 `InteractibleRootComponent` 在目标 CDO 指向同一 `SceneComp`。
- `UFunPark_Drop_DamageableButton_BP_Child_C` 有 `CurveFloat_0`（Timeline 曲线，含 `Time=0.35 / ArriveTangent=-90` 等键），属资产数据，不是实例属性。
- 五个类的 `RandomSeed` 与 `opp_seed` 的 `GetSeed` 体系关系本次未取证。
