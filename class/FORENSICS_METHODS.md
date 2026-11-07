# IDA MCP 静态取证方法与锚点

> 供后续类分析复用的方法、陷阱与校验锚点。类专属结论分别见 `FunParkCanal_Drop_DamageableButton_BP_RightCanal.md`、`RBOperatable.md`、`FunPark_DamageableButton_BP_chain.md`。
> 参照 `RBProjectionCodeCoordinator.md` 的取证链，并把本次踩过的坑记下来。

## 1. 环境

| 项 | 值 |
|---|---|
| IDA | `C:\Program Files\IDA Professional 9.3`（含 Hex-Rays 9.3.0.251224） |
| 数据库 | `d:\workspace\outlast\TOTClient-Win64-Shipping.exe.i64`，基址 `0x140000000` |
| IDAPython | 由 3.10 切到 **Python 3.13.12**（`HKCU\Software\Hex-Rays\IDA\Python3TargetDLL`），因插件要求 ≥3.11 |
| MCP 服务端 | `ida-pro-mcp 1.4.0` + `mcp 1.30.0`（**必须 `mcp<2`**，2.x 移除 `mcp.server.fastmcp`） |
| 客户端配置 | `C:\Users\ADMIN\.codebuddy\mcp.json` → `ida-pro-mcp`（stdio，Python 3.13 绝对路径） |
| IDA 插件 | `%APPDATA%\Hex-Rays\IDA Pro\plugins\mcp-plugin.py`（指向 site-packages 的符号链接） |
| RPC | `http://127.0.0.1:13337/mcp`，需 IDA 内 `Edit → Plugins → MCP`（`Ctrl+Alt+M`）启动 |
| 自检 | `python d:\workspace\outlast\ida_mcp_selftest.py`（48 个只读工具 + `check_connection`） |

默认只开放 48 个安全工具；12 个 unsafe（patch / 调试控制）需在配置 `args` 加 `--unsafe`。

## 2. 工具速查

| 工具 | 关键参数 | 用途 / 陷阱 |
|---|---|---|
| `list_strings_filter` | `offset,count,filter` | `filter` **只支持不区分大小写的子串**；源码 `pattern_filter` 的 `/regex/` 是 TODO，传 `/a\|b/` 会返回空 |
| `list_globals_filter` | `offset,count,filter` | 查 IDA 已命名符号（如 `aRboperatable_0`） |
| `get_xrefs_to` | `address` | 返回 `{address,type,function}`；FName 名字串常只有 1 个 data xref |
| `data_read_dword` | `address` | 读描述符 `+0x24` 的偏移值 |
| `read_memory_bytes` | `memory_address,size` | 返回**空格分隔的 hex 字符串**（如 `0xa0 0x1f …`），客户端解析成 bytes 再 `struct.unpack` |
| `decompile_function` | `address` | 首次调用会触发 Hex-Rays 初始化，可能 >60s；预热后正常 |
| `disassemble_function` | `start_address` | 返回 `{name,start_ea,stack_frame,lines}` |
| `get_function_by_address` / `get_function_by_name` | `address` / `name` | 先看 size，避免对超大函数直接反编译 |
| `get_callees` / `get_callers` | `function_address` | 追构造 / 注册链 |

## 3. 三条取证链模板

### 3.1 C++ 类链（拿类大小、构造、vfptr）

```text
ASCII 反射名（list_strings_filter 子串）
  → get_xrefs_to → 8 字节名字指针所在处（注册表项）
  → 同项 ±8 处的 .text 指针 = UClass 惰性构造函数
  → decompile_function 读 sub_14035AFB0 参数：
      宽类名 / 静态类缓存 / UFunction 注册回调 / 类大小 / ClassConstructor / 父类 UClass 构造
  → ClassConstructor（小 thunk）→ CDO 构造函数
  → 伪代码里的 `*a1 = &off_XXX` / `a1+560 = off_YYY` / `a1+1192 = off_ZZZ` = 三个 vfptr
  → 析构函数（同样写回三值）交叉验证；`a1[N]` 释放点可反推对象尾部字段
```

`.text` 范围 `0x140001000–0x145065E2D`；按该范围扫 `.rdata` 连续 qword 段可得每张 vtable 的边界与槽数。

### 3.2 属性链（拿偏移）

```text
属性名 ASCII → get_xrefs_to → 命中处即描述符
  → data_read_dword(描述符 + 0x24) = 属性偏移
  → 表项步长 0x38；一项常含「属性名 + RepNotify 名」两个指针
  → 用类大小与相邻属性挑表（同名属性会命中多张表）
```

bool 属性的 `+0x24` 是**位掩码**（常为 1），不是字节偏移。`FUNC_INDEX.md` §5.13 另记「结构体属性 `+0x28` = 类指针，按 0x38 步长走表」。

### 3.3 UFunction / 接口链

```text
sub_14048DA90(UClass, &off_XXX, N) → off_XXX 是 {名字指针, thunk VA} 数组，步长 0x10
  → read_memory_bytes(N*0x10) 解析 qword 对
  → 名字指针指向 FName 串，读 96 字节取 \x00 前 ASCII
  → thunk 簇（如 0x14390B/C）是 ProcessEvent 存根，不是 C++ vtable 槽
```

## 4. 校验锚点

| 地址 | 期望值 | 来源 |
|---|---:|---|
| `data_read_dword(0x145D3D22C)` | 69 | `RBProjectionCodeCoordinator.OnPanelActiveChangedEvent` |
| `data_read_dword(0x145D3D234)` | 3816 | `RBProjectionCodeCoordinator.WrongPasscodeDamage` |
| `data_read_dword(0x145C1FDDC)` | 1 | `bIsInteractible` 位掩码 |
| `data_read_dword(0x145C59464)` | 1104 | `InteractibleRootComponent` |
| `data_read_dword(0x145C58F54)` | 712 | `InteractionMesh` |
| `data_read_dword(0x145C58EC4)` | 688 | `InteractionZoneBox` |

每次换库 / 换版本先复跑前两行，确认 `+0x24` 规则仍成立。

## 5. 陷阱清单

1. **IDA 未勾选 Unicode**：宽类名（`L"RBOperatable"`、`L"ARBGameShowObjectiveCoordinator"`）不在字符串表里，但反编译 `UClass` 构造时能看到；ASCII 反射名池在 `0x1464xxxxx–0x1467xxxxx`。
2. **FName 池后缀名无 xrefs**：IDA 只为最长起始串建字符串项，`IsInteractible` / `RootComponent` / `RandomSeed` / `bStateOn` 常是别的长串后缀；直接拼后缀地址查 xrefs 可能为空，不要据此断言属性不存在。
3. **蓝图类在 exe 中无符号**：`DamageableButton` / `FunParkCanal` 子串命中 0；没有 UClass 构造、静态属性描述符、独立 vtable。属性在 pak 的 `BlueprintGeneratedClass.ChildProperties`，偏移运行时才算。
4. **同名属性多表**：`InteractibleRootComponent` 有 1104（本链）与 600（容器类表 `0x145B9E380`）；`InteractionMesh` 有 712 与 592；按类大小（1192 / 1608）与同表邻居挑。
5. **相邻类 vtable 混淆**：主表 `off_1459800B0` 之前/之后仍有函数指针；按「从 vfptr 起连续落在 .text、遇 0 停止」定边界。
6. **UFunction 簇 ≠ vtable 簇**：`0x14390B/C`（BlueprintEvent thunk）与 `0x1433A19xx` / `0x143618xxx`（C++ 虚表实现）要分开。
7. **`read_memory_bytes` 是 hex 文本**，不是原始 bytes；跨工具对齐时以 `data_read_dword` 为准。
8. **首次反编译慢**：Hex-Rays 初始化可能超过 60s，重试即可；客户端 `timeout` 设 1800。

## 6. 本次新增锚点汇总

| 类别 | VA | 说明 |
|---|---|---|
| 类名 | `0x14658BBD1` | ASCII `RBOperatable` |
| 类注册 | `0x145DE93C0` / `0x145DE93C8` | `sub_1409354A0` / 名字指针 |
| UClass 构造 | `sub_1409354A0`, `sub_140821820`, `sub_141231180`, `sub_14035B3C0` | `RBOperatable`(1608) / `RBInteractible`(1192) / `Actor`(560) / `Object`(40) |
| CDO | `sub_140668E20`, `sub_1433A13A0` | 构造 / 析构（写回 3 个 vfptr） |
| 主 vtable | `off_1459800B0` | 281 槽，`0x1459800B0–0x145980978` |
| 接口表 | `off_1459808E0`(19), `off_145980980`(245) | `a1+560` / `a1+1192` |
| 属性表 | `0x145C58E00` | `RBInteractible`，0x38 步长 |
| 排除表 | `0x145B9E300`, `0x145C1FD80` | 容器类 / 谜题面板类，非本链 |
| UFunction 表 | `off_145CCA080`(27), `off_145CC88E0`(2) | `RBOperatable` / `RBObjectiveRandomizable` |
| UFunction 注册 | `sub_142712310`, `sub_1426E6990` | 27 项 / 2 项 |
| 接口 thunk | `sub_14390B750`, `sub_14390B6A0` | `GetObjectiveTypeIndex` / `ShouldDiscard...` |
| 其它 | `sub_140668E10`, `sub_1429F35C0`, `sub_1400456C0`, `sub_142629270` | ClassConstructor / 父类 CDO / 共用回调 / 空函数 |

## 7. 复现

1. 打开 `TOTClient-Win64-Shipping.exe.i64`，`Ctrl+Alt+M` 启动 MCP 插件；确认 `127.0.0.1:13337` 处于 Listen。
2. `python d:\workspace\outlast\ida_mcp_selftest.py` 应输出 `Successfully connected to IDA Pro`。
3. 在 CodeBuddy 里直接调用 `disassemble_function` / `decompile_function` / `get_xrefs_to` 等 MCP 工具；批量取证可用一个最小 `mcp` 客户端（`StdioServerParameters` + `ClientSession.call_tool`）循环调用，用完即删。
4. 新类分析按 §3 三条链走，先用 §4 锚点校验，再写 `class/<类名>.md`。
