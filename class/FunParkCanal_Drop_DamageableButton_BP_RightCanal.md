# FunParkCanal_Drop_DamageableButton_BP_RightCanal_C

> 类专属锚点速查。C++ 基类侧的属性偏移 / vtable 见 `RBOperatable.md`；蓝图链的属性、CDO、UFunction 见 `FunPark_DamageableButton_BP_chain.md`；取证方法与锚点校验见 `FORENSICS_METHODS.md`。
> 路径相对工作区根 `outlast/`；VA 均为 `TOTClient-Win64-Shipping.exe` 基址 `0x140000000` 下的静态地址。

## 文档集

| 文档（均在 `opp_seed/class/`） | 内容 |
|---|---|
| `FunParkCanal_Drop_DamageableButton_BP_RightCanal.md`（本文） | 目标类标识、属性、组件拓扑、接口与函数 |
| `RBOperatable.md` | C++ 基类链：对象布局、属性描述符偏移、三张 vtable、27 项 UFunction |
| `FunPark_DamageableButton_BP_chain.md` | 三层蓝图类的属性 / CDO / UFunction / 接口对照 |
| `FORENSICS_METHODS.md` | IDA MCP 取证方法、陷阱、校验锚点、新增 VA 汇总 |
| `RBProjectionCodeCoordinator.md` | 既有格式基准（协调器类） |

## 速查表

| 项 | 值 |
|---|---|
| 类标识 | `BlueprintGeneratedClass'OPP/Content/LD/Operatable/ThrowableTargets/FunParkCanal_Drop_DamageableButton_BP_RightCanal_C'` |
| 资产 | `pak/LD/Operatable/ThrowableTargets/FunParkCanal_Drop_DamageableButton_BP_RightCanal.cpp` / `.json` |
| 直接父类 | `UFunPark_Drop_DamageableButton_BP_Child_C` |
| C++ 终端基类 | `/Script/OPP.RBOperatable`（反射名 `0x14658BBD1`） |
| ClassFlags | `CLASS_Config \| CLASS_Optional \| CLASS_ReplicationDataIsSetUp \| CLASS_CompiledFromBlueprint \| CLASS_HasInstancedReference` |
| ClassConfigName / ClassWithin | `Engine` / `Class'Object'`（`/Script/CoreUObject`） |
| 接口 | `Class'RBObjectiveRandomizable'`（`/Script/OPP`），`PointerOffset=0`，`bImplementedByK2=true` |
| UFunction | 2 个：`GetObjectiveTypeIndex`、`ShouldDiscardOtherObjectiveActorForRandomization` |
| CDO | `Default__FunParkCanal_Drop_DamageableButton_BP_RightCanal_C`，`RandomSeed=1543793506` |
| 新增实例属性 | **0**（`BlueprintGeneratedClass` 条目无 `ChildProperties`） |
| C++ vtable | **无独立表**，实例沿用 `&off_1459800B0` / `+560` / `+1192` 三个 vfptr |

## 1. 取证链

```text
蓝图 cpp/json → Super/SuperStruct → FunPark_Drop_..._Child_C → Simple_DamageableButton_BP_C
  → SuperStruct = Class'RBOperatable' (/Script/OPP)              ← 蓝图层止于此
ASCII "RBOperatable" 0x14658BBD1 → xref 0x145DE93C8（UClass 注册表项）
  → 同项 0x145DE93C0 = sub_1409354A0（UClass 惰性构造，类大小 1608）
  → ClassConstructor sub_140668E10 → sub_140668E20（CDO 构造，写 3 个 vfptr）
  → 父类链 sub_140821820 (RBInteractible,1192) → sub_141231180 (Actor,560) → sub_14035B3C0 (Object,40)
属性名 ASCII → xrefs → 描述符 +0x24 = 偏移       ← 详见 RBOperatable.md §3
```

exe 字符串表中 `FunParkCanal` / `DamageableButton` **0 命中**：蓝图类名只在 pak 资产里，运行时从序列化数据创建 `BlueprintGeneratedClass`，因此 exe 中没有它的 UClass 构造、属性描述符或 C++ vtable。

## 2. 类定义与属性

```1:15:pak/LD/Operatable/ThrowableTargets/FunParkCanal_Drop_DamageableButton_BP_RightCanal.cpp
class UFunParkCanal_Drop_DamageableButton_BP_RightCanal_C : public UFunPark_Drop_DamageableButton_BP_Child_C
{
public:
    class USimpleConstructionScript* SimpleConstructionScript = "...";
    ...
    int32 RandomSeed = 1543793506;
    class USceneComponent* RootComponent = "...:SceneComp'";
};
```

| 属性 | 类型 | CDO 值 / 指向 | 层次 | 静态偏移 |
|---|---|---|---|---|
| `SimpleConstructionScript` | `USimpleConstructionScript*` | `..._RightCanal_C:SimpleConstructionScript_0` | UClass 元数据 | — |
| `InheritableComponentHandler` | `UInheritableComponentHandler*` | `..._RightCanal_C:InheritableComponentHandler` | UClass 元数据 | — |
| `IsInteractible` | `FScheduledBool` | `ApplyDesiredStateCallback → IsInteractiveChangedCallback` | C++ `RBInteractible` | **+568** |
| `InteractionZoneBox` | `URBInteractionZoneComponent*` | `Default__..._RightCanal_C:InteractionZone` | C++ `RBInteractible` | **+688** |
| `InteractionMesh` | `UStaticMeshComponent*` | `Default__..._RightCanal_C:InteractMesh` | C++ `RBInteractible` | **+712** |
| `InteractibleRootComponent` | `USceneComponent*` | `Default__..._RightCanal_C:SceneComp` | C++ `RBInteractible` | **+1104** |
| `RandomSeed` | `int32` | `1543793506` | 蓝图 CDO 覆盖 | 运行时 `FProperty` |
| `RootComponent` | `USceneComponent*` | 与 `SceneComp` 同一对象 | `AActor` | 运行时 `FProperty` |

`RootComponent` 与 `InteractibleRootComponent` 在 CDO 里指向同一个 `SceneComp`。cpp 把继承属性一并展开列出；JSON 中本类 `BlueprintGeneratedClass` 没有 `ChildProperties`，说明它只做 CDO 覆盖、未新增实例字段。

## 3. 组件拓扑（CDO / SCS）

```text
Default__..._RightCanal_C
  ├─ RootComponent ─────────────┐
  ├─ InteractibleRootComponent ─┴→ SceneComp (Template: Default__..._Child_C:SceneComp)
  ├─ InteractionMesh = InteractMesh (AttachParent: SceneComp)
  ├─ InteractionZoneBox = InteractionZone (AttachParent: InteractMesh)
  └─ SimpleConstructionScript_0
        └─ DefaultSceneRootNode → SCS_Node_0 → DefaultSceneRoot_GEN_VARIABLE (Mobility: Static)
```

- `SceneComp`、`InteractMesh`、`InteractionZone` 的 `Template` 全部指向 `Default__FunPark_Drop_DamageableButton_BP_Child_C` 的同名模板。
- `InheritableComponentHandler.Records[0]`：`ComponentClass=Class'NiagaraComponent'`，模板 `..._RightCanal_C:Ngr_Temp_Sys_14_Obj_CrankSparkBurst_GEN_VARIABLE`（`OverrideParameters={}`），`ComponentKey.OwnerClass=Simple_DamageableButton_BP_C`，`SCSVariableName=Ngr_Temp_Sys_14_Obj_CrankSparkBurst`，`AssociatedGuid=A2E2F67E-4B95DA73-28C84D9D-E0A9FB2D`。
- 该 Niagara 模板的 `Template` 指向 `..._Child_C:Ngr_Temp_Sys_14_Obj_CrankSparkBurst_GEN_VARIABLE`，即继承链上的组件覆写。

## 4. 接口与 UFunction

| 函数 | 签名（JSON `ChildProperties`） | FunctionFlags | 接口 thunk |
|---|---|---|---|
| `GetObjectiveTypeIndex` | `ReturnValue: IntProperty (4B, Parm\|OutParm\|ReturnParm)` | `FUNC_Event \| FUNC_Public \| FUNC_HasOutParms \| FUNC_BlueprintCallable \| FUNC_BlueprintEvent \| FUNC_BlueprintPure \| FUNC_Const` | `sub_14390B750` |
| `ShouldDiscardOtherObjectiveActorForRandomization` | `actor: ObjectProperty Class'Actor' (8B, BlueprintVisible\|BlueprintReadOnly\|Parm)`、`ReturnValue: BoolProperty (1B, ByteMask=1)` | 同上 | `sub_14390B6A0` |

- 两者属 `/Script/OPP.RBObjectiveRandomizable` 接口，接口 UFunction 表 `off_145CC88E0`（2 项，由 `sub_1426E6990` 注册）。
- 反编译 `sub_14390B750` / `sub_14390B6A0` 可见只是 `ProcessEvent` 存根（间接虚调用 + 参数打包 / 栈 cookie），**蓝图函数体不在 exe 中**。
- `Children` / `FuncMap` 各只有这两个函数；`bImplementedByK2=true`、`PointerOffset=0` 说明接口由 K2 实现，不占 `+560/+1192` 的 C++ 接口 vfptr。

## 5. 旁支与 CDO 对照

`FunParkCanal_Drop_DamageableButton_BP_LeftCanal_C` 与本类**同构**（同一父类、同样 2 个 UFunction、同一接口、同样 8 项属性），仅 `RandomSeed` 不同：

| 类 | 父类 | `RandomSeed` |
|---|---|---:|
| `UDamageableButton-01_BP_C` | `URBOperatable` | 758509635 |
| `USimple_DamageableButton_BP_C` | `URBOperatable` | 97264942 |
| `UFunPark_Drop_DamageableButton_BP_Child_C` | `USimple_DamageableButton_BP_C` | 1516456114 |
| `UFunParkCanal_Drop_DamageableButton_BP_LeftCanal_C` | `..._Child_C` | 2083139261 |
| **`UFunParkCanal_Drop_DamageableButton_BP_RightCanal_C`** | `..._Child_C` | **1543793506** |

`RandomSeed` 与 `opp_seed` 里 `GetSeed` / `RandSeeded` 种子体系的关系本次未取证，勿直接套用。

## 6. 备注

- 目标类没有独立 C++ vtable；实例主 vfptr 是 `&off_1459800B0`（`RBOperatable` CDO 构造 `sub_140668E20` 写入），完整槽位见 `RBOperatable.md` §4。
- `IsInteractible` / `InteractionZoneBox` / `InteractionMesh` / `InteractibleRootComponent` 的偏移来自 C++ 属性描述符表 `0x145C58E00`，不是蓝图反射数据。
- `RandomSeed` / `RootComponent` 无静态描述符：前者是蓝图 CDO 覆盖值，后者属引擎 `AActor`；要在运行时取偏移需遍历 `BlueprintGeneratedClass.ChildProperties` 按 `ElementSize` 累加对齐。
- 校验锚点：`0x145D3D22C=69`、`0x145D3D234=3816`（参考文档已知属性）、`0x145C59464=1104`（`InteractibleRootComponent`）；详见 `FORENSICS_METHODS.md`。
