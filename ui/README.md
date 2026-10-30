# ui — 交互式地图（数据提取 + 实时渲染）

把 `paks/MAP/Maps/<地图>` 里的关卡 JSON 提取成**每关一份**的地图数据，再用 Tkinter 实时渲染。
改分区、加点位、写备注都只改 JSON，不需要重新出图。

## 两个前端：Web 版（默认）与 Tk 版（`--tk`）

| 入口 | 说明 |
|---|---|
| `启动地图工具.bat` | 默认起 **Web 版**（`python mapweb.py`），双击即可 |
| `启动地图工具.bat --tk` | 起旧的 Tk 版（等价于 `python mapview.py`） |
| `python mapweb.py` | Web 版：本机 HTTP 服务 + Edge/Chrome 应用窗口，复用 `mapview` 的渲染与 `seedinfo` 的种子推理 |
| `python mapview.py` | Tk 版：原窗口程序，功能不变 |

Web 版把页面放在 `web/`（`index.html` / `style.css` / `app.js`），后端接口：
`/api/state`、`/api/levels`、`/api/map?level=<关卡>`、`/api/note`、`/api/config`、
`/api/window/hide`、`/api/window/quit`。常用参数：

```powershell
python mapweb.py --port 18765      # 固定端口（默认自动挑空闲端口）
python mapweb.py --browser         # 用普通浏览器标签页打开，而不是应用窗口
python mapweb.py PSA_MT01          # 指定初始关卡
```

- 默认模式下进程生命周期跟着浏览器窗口：**关掉窗口服务就退出**；`--browser` 时服务不随浏览器退出。
- 运行会在 `data/cache/web_profile/` 生成 Edge 配置目录（已 gitignore，可随时删）。
- Web 版只是新增入口，`mapdb.py` / `maplib/` / `data/` 与 Tk 版完全共用，`ui/` 仍然自包含。

```
ui/
  mapdb.py                 提取器（paks → data/maps/<关卡>.json）
  mapweb.py                Web 版入口（本地 HTTP 服务 + 浏览器窗口，默认）
  web/                     前端（index.html / style.css / app.js，Canvas 渲染）
  mapview.py               渲染器（窗口 / --png 导出 / 右侧答案面板 / 全局快捷键）
  gamelog.py               读 OPP.log 里本局的关卡 + 种子（GameStageInfo / StageReady 都认）
  seedinfo.py              调 seed.py 推理（关卡 + 种子 → 答案文本，带缓存）
  seedpanel.py             右侧「本局答案」面板
  hotkey.py                全局快捷键（低级键盘钩子，只观察不吞键，支持 Ctrl+A）
  uifont.py                统一字体（整数像素字号，保证字清晰）
  启动地图工具.bat         一键启动（双击默认起 Web 版，加 --tk 用 Tk 版，其余参数透传）
  config.json              日志路径 / 快捷键 / 面板宽度 / 字号等
  README.md                本文（工具说明 + 给 AI 的工作流）
  ZONES.md                 分区清单与判定逻辑（每关几区、为什么，人工维护）
  maplib/                  自带解析内核（extract.py 解析+翻译+门分类，names.py 房间命名+点位归属）
  data/extract.json        提取配置（要哪些图层，默认只要门 + 任务点位）
  data/levels.json         关卡 → 地图名（--sync-levels 从 seed.py 同步）
  data/zones/<关卡>.json   分区/点位默认配置（历史配置已迁到这里）
  data/i18n_names.json     房间译名覆盖表（maplib/extract 用）
  data/room_names.json     全局房间备注名（maplib/names 用）
  data/points/<关卡>.json  本关点位规则 + 可选 zones（人工/AI 手写）
  data/maps/<关卡>.json    交付数据（机器生成，含 notes）
  data/orientation.json    每张图的镜像方式（没写的按 x=左右镜像，与旧交付版一致）
  data/cache/              几何、点位、类分布、门类缓存
  data/preview/*.png       预览图
```

`release/map/`、`release/map2/` 是历史工具，**本工具不再依赖它们**：解析内核已经内联进
`maplib/`（见下），旧目录可以完全不动。

---

## 0. 依赖与独立交付

`ui/` 是**自包含**的：拷走整个目录就能跑，不需要 `release/map2`，也不需要 `seed.py`。

| 文件 | 依赖 |
|---|---|
| `mapview.py`（窗口 / `--png`） | 标准库 `tkinter`；`--png` 另需 Pillow |
| `mapdb.py`（提取数据） | 同目录 `maplib/`（自带）+ 游戏 `paks/MAP/Maps` |
| `maplib/extract.py` | 只依赖 `data/i18n_names.json`（房间译名覆盖表） |
| `maplib/names.py` | 只依赖 `data/room_names.json`（全局房间备注名） |
| `gamelog.py` / `seedpanel.py` / `uifont.py` | 只读游戏日志，无第三方依赖 |
| `seedinfo.py` | **软依赖** 上级目录的 `seed.py`（找不到就只在面板提示，地图照常用） |
| `hotkey.py` | `ctypes`（仅 Windows；其它平台自动跳过） |
| `启动地图工具.bat` | 找 `pythonw`（找不到退到 `python`），双击启动；日志写到 `mapview_out.log` |

`maplib/` 的来历：原先这两块代码在 `release/map2/mapcore.py` / `zonemap.py` 里，现在把
「解析 / 翻译 / 几何 / 门分类 / 房间命名」这一半**内联**到本项目，渲染出图那一半没有搬。
**以后只维护这里的版本**，和旧工具不再同步。

### 需要外部提供的东西

| 东西 | 怎么给 | 说明 |
|---|---|---|
| 游戏地图数据 | `--paks "D:/.../paks/MAP/Maps"` 或环境变量 `OUTLAST_MAPS_DIR` | 只有提取时需要；只看地图不用 |
| 关卡 → 地图名 | `data/levels.json`（已内置 10 个） | 新增关卡时在仓库里跑 `python mapdb.py --sync-levels` 从 `seed.py` 同步 |

### 交付形态

| 场景 | 带什么 | 命令 |
|---|---|---|
| 只给人看地图 | `ui/`（+ Pillow） | 双击 `启动地图工具.bat`，或 `python mapview.py` |
| 要能自己提取新关卡 | `ui/` + 游戏 `paks/MAP/Maps` | `python mapdb.py SMC_MT02 --paks "D:/.../paks/MAP/Maps"` |

体积参考：代码 + 数据约 **1.7 MB**（`mapdb.py` 36 + `mapview.py` 74 + `maplib/` 55 +
30 份地图数据 1731 + 点位/分区/译名表 152 + README+ZONES 45）。`data/cache/`（约 2 MB）和
`data/preview/`（约 1 MB）是可再生的，交付时可以删掉，首次提取会自动重建。

---

## 1. 最常用

```powershell
cd <本仓库目录>\ui
python mapview.py                 # 打开窗口，等日志：读到关卡+种子就自动加载地图
python mapview.py PSA_MT01        # 锁定看某一关（不跟日志自动切换）
python mapdb.py SMC_MT02          # 生成/更新 data/maps/SMC_MT02.json
python mapdb.py --all             # data/levels.json 里的所有关卡（TSR_MT02 这类未收录的要单独指定）
```

或者干脆双击 **`启动地图工具.bat`**，不用开命令行。

窗口标题栏末尾带版本号（如 `[2026-10-29.6]`），排查问题先看它——不是最新版说明还在跑旧进程。

窗口里：点击房间/点位 → 显示信息并**自动复制原始名**（房间是 `RBRoom_...`，不是备注名）；**按住左键拖动（或中键/右键拖动）= 平移地图**；
滚轮缩放（以光标为心，且不会被拖/缩到看不见地图）；`F` 适应窗口；**`T` 顺时针转 90°（文字不跟着转）**、`X` 左右镜像；
`1/2/3` 切层、`O` 叠加、`Esc` 取消选中；双击（或 `N`）编辑备注 →
直接写回该关卡 JSON；工具栏 `all names` 显示全部房间名。
左上角图例**默认不显示**（免得挡地图），要按区筛选时勾工具栏 `legend (H)` 调出来：
单击分区切换显示、双击改分区名。

**右侧「本局答案」面板**：自动读游戏日志里本局的关卡与种子，调 `seed.py` 推理后显示。
**日志里一出现 `Trial ID` + `Seed` 就刷新，不用等 `StageReady`**；`poll_log` 默认开，每 0.9 秒
stat 一次日志，变了才解析。工具栏 `R` 或面板「刷新」可以手动重读。
**全局快捷键 `Ctrl+A`**（默认）弹出/收起整个窗口并刷新答案，详见 §7。

导出静态图（自检/给人看）：

```powershell
python mapview.py SMC_MT02 --png data/preview/smc.png --mode floor --floor 0 --all-names
```

---

## 2. 给 AI 的工作流（从一句描述到出图）

输入是用户口头描述的关卡机制，输出是「点位规则 + 分区 + 重新生成的地图 JSON + 自检通过」。
**按顺序执行，不要跳步**。

> 这个工具**只做「把配置翻译成地图数据」**：它不知道哪个蓝图是任务点，也不会替你猜。
> 「提哪些点」由你读原始关卡 JSON 得出，「本局刷几个 / 怎么随机」由任务协调器的属性决定。
> 以前脚本里有一套自动推荐（`--suggest`），因为漏掉过真实任务点已经删掉了，别再依赖它。

### 步骤 0：确认关卡和地图

```powershell
python mapdb.py <LEVEL>          # 先跑一次（还没配点位时也能出图，只出房间/门）
```

成功时会打印 `几何缓存 <地图目录名>`（首次是 `扫描 <地图目录名>`）。报「找不到对应地图」
说明该关卡的关卡文件不在 `paks/MAP/Maps` 里，用 `--map <目录名>` 指定；
关卡 → 地图的对照写在 `data/levels.json`。

### 步骤 1：读原始关卡 JSON，找出点位类

UE 导出的 JSON 是逐行缩进的，直接搜就行（`Type` 就是蓝图类名）：

```powershell
cd paks\MAP\Maps\PoliceStationBasement
Select-String -Path PSB_MT03_B01.json -Pattern '"Type": ".*Box.*' |
  Select-Object -ExpandProperty Line | Sort-Object -Unique
```

看三样东西：

| 看什么 | 怎么用 |
|---|---|
| `Type` | 蓝图类名，直接当 `point_types.pattern`（写成 `^类名$`，`match=type`） |
| `Name` | 实例名（`match=name` 时才用）；名字里的编号/区域能反推它属于哪儿 |
| `Properties` | 挂的组件指针：任务点一般有 `RootComponent`，再带 `RBObjectiveActorComponent` / `RBInteractionZoneComponent` / `RBRandomizableHelperComponent` 之类 |

判据（可信度从高到低）：

1. 被某个 `*ObjCoord*` / `GatherAndDeliver*` 协调器的 `ObjectiveActors` / `LargePickupActors`
   点名引用 → 就是任务点本体；
2. 挂着 `RBObjectiveActorComponent` + 交互/随机化组件 → 大概率是任务点；
3. 只在本关文件（文件名带 `_MTxx_`）里出现，通用文件（`*_ART.json`、`*_LD_*.json`、
   `*_Background.json` 等）里没有 → 本关专属，值得看；
4. 只在通用文件里出现、数量巨大（灰盒、灯、线、地板）→ 一般不要。

**搜索关键词表**（用户描述 → 先搜这些，搜不到就换词）：

| 用户描述里的词 | 先搜这些 |
|---|---|
| 黑光 / 紫外灯照图案 | `BlackLightable`、`BlacklightDetector` |
| 投影符号 / 图案 / 密码盘 | `ProjectionSymbol`、`Passcode`、`SwitchBoard_PanelComponent` |
| 显示器 / 屏幕 / 显示区域 | `tvChannel`、`NarrativeScreen`、`Screen` |
| 密码面板 / 接线 / 电闸 | `SwitchesBoard`、`SwitchBoard`、`Keypad`、`Console` |
| 拍照 / 摄像机 | `PhotoDispenser`、`Camera`（`Camera` 多是装饰） |
| 人偶上下半身 | `Mannequin`；`MannequinBP_SinglePose` 是通用模特 |
| 放映机 / 录像盘 | `DiaporamaProjector`、`Cassette` |
| 阀门 / 气泵 | `Valve`、`FirePump`、`Gas` |
| 箱子 / 搬东西 / 投箱 | `Box`、`Crate`、`Container`、`Pickup`、`GatherAndDeliver`、`Grinder` |
| 交付 / 赃物 / 保险箱 | `GatherAndDeliver`、`Valuables`、`SafeDrop`、`Orp_Movable` |
| 撤离 / 出口 | `ExitStage`、`SAS`（房间名） |
| 结束键 / 阶段结束 | `StageEnd` |
| 目标点 / 到达某处 | `ObjCoord`、`Goto`、`Delay` |
| 敌人 / 刷怪 | `NPC_Spawn`、`Spawner` —— 一般**不要**，除非用户明确要刷怪位置 |
| 电池 / 充能站 | `PlaceableRechargeableStation` —— 通用设施，用户要求才加 |

### 步骤 2：确认「刷几个 / 怎么随机」（看协调器属性）

任务协调器（`*ObjCoord*`、`GatherAndDeliver*` 这类）的属性里写着随机化规则。
先 `cd paks/MAP/Maps/<地图目录>`，再把它的 `Properties` dump 出来看：

```powershell
cd paks\MAP\Maps\PoliceStationBasement
python -c "import json;d=json.load(open('PSB_MT03_B00.json',encoding='utf-8'));p=[o for o in d if o.get('Name')=='PSB_MT03_GatherAndDeliver_ObjCoord_BP'][0]['Properties'];[print(k,'=',json.dumps(p.get(k),ensure_ascii=False)) for k in ('LargePickupActors','LargePickupActorsRandomizationSetup','FixedMaxCount','ObjectiveActors','NextObjectiveCoordinator')]"
```

| 字段 | 含义 | 对出图的影响 |
|---|---|---|
| `ObjectiveActors` / `LargePickupActors` | 真正要交付/搬运的**类** | 这就是点位该用的 `pattern`（按 `match=type`） |
| `PrimaryActorsRandomizationSetup` / `…Secondary…`.DesiredCount | 每局随机挑几个 | `10 选 60` → **60 个候选全标**，不要只标 10 个 |
| `FixedMaxCount`（`Values1P/2P/3P`） | 按人数固定的数量上限 | 人数不同数量不同时写进 `subtitle` |
| `DistanceBetweenSameObjectives` | 同局同类点最小间距（uu） | 玩家能据此判断「附近只会有一个」，值得写进备注 |
| `Next/PreviousObjectiveCoordinator` | 任务链的上一/下一环 | 决定字幕里的先后顺序 |

PSB_MT03 的结论：`LargePickupActors=PrivateFilesBox-01_BP_C`、`DesiredCount=10`、
`FixedMaxCount 1P/2P/3P 都是 10`、同局箱子间距 ≥1000uu —— 所以 60 个候选全部上图。

### 步骤 3：写点位规则

直接编辑 `data/points/<LEVEL>.json` 的 `point_types`：

```jsonc
{ "key": "box",
  "pattern": "^PrivateFilesBox-01_BP_C$",   // 类名照抄，^…$ 全匹配最稳
  "match": "type",                          // type=按蓝图类名；name=按实例名
  "label": "箱子",                           // 中文标签（信息栏 label_zh）
  "short": "Box",                           // 图上短名，ASCII
  "style": "" }                             // clue=空心（线索）；省略/空=实心（目标）
```

一个点位类型一个条目，多个类型就多个条目；字段含义见 §4，`data/points/` 下已有几份
现成配置可以照抄格式。`sources` 写错了就扫不到东西：默认只猜 `<前缀>_LD_<MTxx>_B00.json`，
点位在 `_B01.json` 这类文件里时必须显式列出来。

### 步骤 4：写分区（可选，但强烈建议）

**默认逻辑：分区 = 任务区域（task area），不是点位分类，也不是楼层。**

- 玩家按区推进：做完一个区的任务 → 去下一个区；同类任务会重复出现在不同区；
- 分区数由**任务物/任务轮次**决定（2 台推车 = 2 区、4 个人偶 = 4 区、4 把图案钥匙 = 4 区、4 轮钱箱 = 1 固定 + 3 随机）；
- **分区标记 = 该区任务物的位置**（钱箱/推车/钥匙/人偶…），因为玩家要做的就是这个任务物；
- 一个区可以有多个候选点位（随机取一个），所以「1 区 1 点」不是硬要求。

**特殊逻辑要显式声明**：不按任务区域划分时（例如 `DRS_MT01` 按房间：一房一区，因为线索只给房间、玩家先到房间再找对应武器的模型），必须在 `data/points/<LEVEL>.json` 的 `_说明` 里写清「本关不按任务区域分，原因是……」，并在 `zones[].note` 里说明该区含义。

现状盘点（每关分区数 + 划分逻辑 + 待办）见 [`ZONES.md`](ZONES.md)，改分区前后都去看一眼。

分区写在同一个 `data/points/<LEVEL>.json` 里：

```jsonc
"zones": [
  { "id": "A", "name": "Studio 3", "color": "#7c3aed",
    "rooms": ["RBRoom_Studio3*"] },
  { "id": "B", "name": "Studio 4", "color": "#b45309",
    "rooms": ["RBRoom_Studio4*"], "note": "4 号棚，密码盘在南侧" }
]
```

规则：

1. `rooms` / `actors` 支持 `*` 通配，`!` 前缀是**排除**（`"!RBRoom_Casino_1F_BackDock*"`）。
2. **先写的区先占用房间**（后写的不会抢）。所以窄的通配写前面，宽的后写。
3. 点位所在房间会自动并入该点位所属的区（可以用 `"merge_room": false` 关掉）。
4. `actors` 只对点位生效（按实例名通配），`rooms` 对房间生效。
5. 颜色不写会自动取调色板；建议保持 `A→#7c3aed, B→#b45309, C→#0f766e, D→#1d4ed8, E→#be123c`
   的既有约定，跨关卡看起来一致。
6. 划法优先级：**按任务区域**（默认，见本节开头）> 按房间/房间前缀（线索只给房间时，如 DRS_MT01）> **按楼层**（楼层模式本来就能切，不必拆区）。
   按任务链（谜题/交付/撤离）拆出来的"区"只是流程节点，**不算任务区域**，别和上面的几区混用。
7. 一个关卡可以只有 1 个区，也可以没有；没有时图例显示 `no zone config`，房间用中性灰。
8. 固定点/教学点/交付终点这类"每局都在同一处"的点位，最好单独一个区并在 `note` 里写明「固定」，不要和随机任务区混在一起。

### 步骤 5：生成

```powershell
python mapdb.py <LEVEL>
```

### 步骤 6：自检（必做）

```powershell
python mapdb.py <LEVEL> --check
```

```
TSR_MT01  数据自检  ui/data/maps/TSR_MT01.json  (46 KB)
  生成 2026-10-29 17:45:26   来源 paks/MAP/Maps/TelevisionStudioRooftop
  房间 71   门 86   点位 8   物品 0   楼层 4   分区 0
  门类型  access=2 normal=21 other=3 rolling=36 sliding=4 spawn=20   trial_only=1
  点位类型  delay_obj_coord=1 exit_stage_obj_coord=1 ...
  ! 该关卡没有分区（zones 为空）：图例无法按区筛选，房间用中性色
  结论  1 条提示
```

问题 → 处理：

| 提示 | 原因 | 处理 |
|---|---|---|
| 该关卡没有分区 | 没写 `zones` | 按 §4 加；不打算分区可以忽略 |
| N 个房间没有分区归属 | 通配没覆盖 | 补 `rooms` 通配，或用 `--all-names` 出图看是哪些房间 |
| 分区 X 没有任何房间 | 通配写错 | 检查前缀大小写/下划线；`RBRoom_Studio5` 和 `RBRoom_Services2ndStudio5` 是两个房间 |
| N 个点位没匹配到房间 | 点位落在房间体积外 >400uu | 通常是占位/调试点，确认后可不管 |
| 坐标是 (0,0,0) | 读取失败或占位 | 加 `--refresh` 重扫；仍为 0 说明它在关卡文件里就是 0 |
| 同区同短名 | 同类型多个点位 | 正常（信息栏仍能区分），或改成 `match=name` 精确定位 |

### 步骤 7：出图给人看

```powershell
python mapview.py <LEVEL> --png data/preview/<LEVEL>.overlay.png
python mapview.py <LEVEL> --png data/preview/<LEVEL>.1F.png --mode floor --floor 0 --all-names
```

---

## 3. 示例：TSR_MT01（油漆工 + 黑光图案）

> 用户描述：「这一关分布了 5 个油漆工，玩家要找到这些油漆工，用黑光照出图案，然后回去输入密码，
> 旁边有显示器显示油漆工所在的区域，例如 Studio5」

### 3.1 读原文对应到的类

```
Clue_BlackLightable_SwitchBoard_BP_C         n=80  → 黑光图案点（就是油漆工身上/旁边的图案）
tvChannel_BP_C                               n=8   → 显示器频道
BlacklightDetectorWide_QuestItemSpawn_BP_C   n=4   → 黑光道具补给点
Orp_Movable_Button_BP_C                      n=1   → 剧情节点的按钮
SwitchesBoard_Base_BP_C                      n=1   → 输入密码的接线面板（实例名 MT01_SwitchesBoard_Base_BP_Studio5）
NarrativeScreenOnly_BP_C                     n=8   → "只显示叙事的屏幕"，显示器本体
（另有 7 条 obj coord 已经在 data/points/TSR_MT01.json 里）
```

### 3.2 命令

```powershell
# 先按上面的类名补好 data/points/TSR_MT01.json 的 point_types，再生成
python mapdb.py TSR_MT01
python mapdb.py TSR_MT01 --check
```

### 3.3 分区（已按 71 个房间验证，全覆盖）

TSR 的房间名按部门划分（`RBRoom_Studio3*`、`RBRoom_Offices3rd*`、`RBRoom_Services2nd*`…）：

```jsonc
"zones": [
  { "id": "A", "name": "Studio 3",   "color": "#7c3aed", "rooms": ["RBRoom_Studio3*"] },
  { "id": "B", "name": "Studio 4",   "color": "#b45309", "rooms": ["RBRoom_Studio4*"] },
  { "id": "C", "name": "Studio 5",   "color": "#0f766e", "rooms": ["RBRoom_*Studio5*"] },
  { "id": "D", "name": "Studio 1-2", "color": "#1d4ed8", "rooms": ["RBRoom_Studio1*", "RBRoom_Studio2*"] },
  { "id": "E", "name": "Offices 2F/3F", "color": "#be123c", "rooms": ["RBRoom_Offices*"] },
  { "id": "F", "name": "Services & backstage", "color": "#4d7c0f",
    "rooms": ["RBRoom_Services*", "RBRoom_*Actors*", "RBRoom_ActorDepartment*"] },
  { "id": "G", "name": "Roof & audiovisual", "color": "#0891b2",
    "rooms": ["RBRoom_Roof*", "RBRoom_Rooftop*", "RBRoom_AudioVisual*", "RBRoom_Bridge*"] }
]
```

注意 `C` 必须写在 `F` 前面：`RBRoom_Services2ndStudio5` 两个模式都能匹配，先写的先占用。
实测房间数 `E=25 F=16 C=8 G=7 B=6 A=5 D=4`，共 71，无遗漏。

### 3.4 收尾

```powershell
python mapdb.py TSR_MT01
python mapdb.py TSR_MT01 --check
python mapview.py TSR_MT01 --png data/preview/TSR_MT01.overlay.png
```

实测（在临时副本上跑完再还原）：13 条点位规则 → **110 个点位 / 7 个分区 / 71 个房间全覆盖**，
`--check` 通过。效果图：`data/preview/TSR_MT01.demo.overlay.png`、`TSR_MT01.demo.3F.png`。

> 80 个 `Clue_BlackLightable_SwitchBoard` 是黑光图案点，3F 图上会密集叠在一起；
> 点位超过 12 个时图上只显示编号，点开信息栏看类型和坐标。

### 3.5 例：PSB_MT03（限时投箱，60 选 10）

> 用户描述：「任务点位就是箱子，会在 3 个区域随机分布一些箱子」

1. 在 `PSB_MT03_B01.json` 里搜 `Box`：60 个 `PrivateFilesBox-01_BP_C`，每个都带
   `RBObjectiveActorComponent` + `RBInteractionZoneComponent` + `RBRandomizableHelperComponent`
   —— 这就是箱子本体。
2. 顺带确认它不是通用道具：只在 `_MT03_` 文件里出现，`PSB_LD_Items.json` 等通用文件里没有。
3. 看 `PSB_MT03_GatherAndDeliver_ObjCoord_BP` 的属性：`LargePickupActors=PrivateFilesBox-01_BP_C`、
   `DesiredCount=10`、`FixedMaxCount`（1P/2P/3P）=10、`DistanceBetweenSameObjectives=1000`
   → 「**10 选 60**」，同局箱子互相至少隔 1000uu，**60 个候选全部上图**。
4. 60 个点落在 27 个房间，按设施聚成 3 片：射击场/军械库/档案室（22）、
   停尸房/体育馆/维修间（21）、车库/轮胎库/后巷（17）。
5. 结果：53 房间 / 79 门 / 60 点位 / 3 分区，`--check` 通过；配置在
   `data/points/PSB_MT03.json`，预览 `data/preview/PSB_MT03.overlay.png`。

> 这个关卡的箱子名字里没有 `ObjCoord`/`Objective` 之类的任务词。**只按类名关键词猜类别一定会漏**
> —— 这就是脚本里那套自动推荐被删掉的原因。

---

## 4. 数据格式参考

### `data/points/<关卡>.json`（人工/AI 维护）

```jsonc
{
  "level": "TSR_MT02",
  "map": "TelevisionStudioRooftop",
  "sources": ["TSR_LD_MT02_B00.json"],   // 扫哪些关卡文件；不写会自动猜 <前缀>_LD_<MTxx>_B00.json
  "point_types": [
    { "key": "photo", "pattern": "^SMC_MT02_TriggerablePhotoDispenser", "match": "name",
      "label": "Photo", "style": "clue", "props": ["ObjectiveIndex"], "merge_room": true }
  ],
  "zones": [ /* 见 §2 步骤 4 */ ],
  "room_names": { "RBRoom_X": "备注名" }  // 优先级最高的房间显示名
}
```

| 字段 | 说明 |
|---|---|
| `pattern` | 正则；`match=type` 时匹配蓝图类名（如 `^Clue_BlackLightable_SwitchBoard_BP_C$`），`match=name` 时匹配实例名（如 `^MT01_ProjectionSymbol_BP_`） |
| `match` | `type`（推荐，稳定）/ `name`（按实例名，历史配置的写法） |
| `style` | `clue` = 空心圆（线索/可交互）；不写 = 实心（目标） |
| `short` | 图上标记的短名（ASCII，如 `Judge`）；不写就按实例名推，推不出来时退回类型名 |
| `props` | 额外读取的 actor 属性，`ObjectiveIndex` 可用来按组自动分区 |
| `merge_room` | 默认 `true`：点位所在房间并入该点位所属分区 |

### `data/maps/<关卡>.json`（机器生成）

| 字段 | 内容 |
|---|---|
| `rooms[]` | `raw`（原始名，主键）、`name`（英文）、`name_zh`、`hulls`（世界坐标多边形）、`z`、`c`、`area`、`kind`（room/corridor/connector）、`floors`、`zone` |
| `doors[]` | `name`、`type`、`kind`（spawn/normal/rolling/sliding/access/backdrop/other）、`trial_only`、`w`、`p`、`yaw`、`rooms`、`floor` |
| `points[]` | `actor`（实例名，主键）、`key`、`label`、`style`、`short`、`num`（区内编号）、`p`、`room`、`zone`、`floor` |
| `floors[]` | `index`、`level`（z 均值）、`label`（`B1/1F/2F…`）、`band` |
| `zones[]` | `id`、`name`（英文）、`name_zh`、`color` |
| `notes` | `{rooms:{raw:文本}, zones:{id:文本}, points:{actor:文本}}` —— **重新提取时会保留** |

### `data/extract.json`

```jsonc
{ "layers": { "doors": true, "points": true, "items": false },
  "item_cats": [],                                    // items=true 时的类别白名单
  "floors": { "min_sep": 250, "min_rooms": 3, "span": 400 } }
```

命令行可临时覆盖：`--with-items`、`--item-cats hide,health`、`--no-doors`、`--no-points`。

---

## 5. 命令行参考

```powershell
python mapdb.py <LEVEL> [选项]

  --check                   自检已生成 JSON，有问题返回退出码 1
  --all                     所有关卡
  --map <目录名>             手动指定 paks/MAP/Maps 下的目录
  --paks <目录>              paks/MAP/Maps 位置（独立交付时用）
  --sync-levels             从上级目录的 seed.py 同步关卡表到 data/levels.json
  --out-dir <目录>           输出目录（默认 data/maps）
  --refresh                 强制重扫几何/点位/类分布
  --with-items / --item-cats / --no-doors / --no-points
  -q                        安静模式
```

```powershell
python mapview.py [LEVEL|文件] [选项]      # 不给 LEVEL = 跟着日志走

  --png <文件>              无窗口导出（不给 LEVEL 时用日志里那一关）
  --mode overlay|floor      默认 overlay
  --floor <N>               N 从 0 开始
  --all-names               标注全部房间名
  --size 2200x1500
  --list                    已生成的关卡数据
  --log <文件>              OPP.log 路径（默认自动找）
  --seed-lib <文件>         seed.py 路径（默认上级目录的 seed.py）
  --hotkey <键>             全局快捷键（默认 ctrl+a，写 none 关闭）
  --no-hotkey               本次不注册快捷键
  --no-seed                 不显示右侧答案面板
  --seed-marks              --png 时把本局答案里的坐标也画上
  --follow                  给了 LEVEL 也仍然跟随日志自动切图
  --font-scale <1.0>        界面字号缩放（嫌字小就 1.15）
  --flip none|x|y|xy        镜像方式（默认按 data/orientation.json，缺省 x=左右镜像）
  --rot 0|90|180|270        --png 时顺便旋转
```

**给了 LEVEL 就锁定那一关**（`follow` 复选框不勾）：以前 `python mapview.py PSA_MT01` 会被日志里
上一局的 `MHS_MT01` 顶掉，现在不会；想跟着日志切就加 `--follow` 或勾上工具栏 `follow log`。

---

## 6. 已知坑

1. **脚本不替你判断哪个蓝图是任务点**：以前有个 `--suggest` 按类名关键词打分推荐，实测会漏
   （PSB_MT03 的箱子 `PrivateFilesBox-01_BP_C` 名字里没有任务词，60 个实例一个都没被推荐），
   已经删掉了。点位类型只能读原始 JSON 得出，见 §2 步骤 1。
2. **类名不是判据，组件和引用关系才是**：`Clue_BlackLightable_*` 名字带 `Light`、
   `PrivateFilesBox-01_BP_C` 名字带 `Box`，按名字猜都会错。认 `RBObjectiveActorComponent` /
   `RBInteractionZoneComponent` / `RBRandomizableHelperComponent`，以及协调器属性里的
   `ObjectiveActors` / `LargePickupActors`。
3. **`pattern` 写错是静默失败**：不报错，只是点位 0 个。生成后看 `--check` 输出的 `点位 N`
   或 `data/maps/<关卡>.json` 的 `points` 长度；八成是 `^类名$` 漏了 `_C` 后缀，或者
   `match` 写成 `name` 却给了类名。
4. **CDO 不是场景实例**：`Default__*`、`*GEN_VARIABLE*` 会被过滤，别手工加回来。
5. **通用物 vs 关卡专属**：文件名带 `_MTxx_` 的是本关专属文件，`*_ART.json`、`*_LD_*.json`、
   `*_Background.json` 是全图通用文件。点位只出现在通用文件里通常是藏身点/灯/线/地板。
6. **短名重复**：同区同类型点位短名会一样（如 19 台 `Cassette Converter`），
   图上点位多时只显示编号，点开看信息栏。
7. **门的两层分类**：`kind`（类型）+ `trial_only`（本关专属门，别的图没有同类）。
   刷怪门 = `MonsterClosetDoor` 一类；`trial_only` 只代表"本关独有门资产"，不代表一定上锁。
8. **备注别写在 `data/maps` 之外的地方**：UI 里加的备注直接进 `data/maps/<关卡>.json` 的 `notes`，
   重新提取会保留；改通配/颜色请改 `data/points`。
9. **缓存**：`data/cache/` 里是几何、点位、门类索引。游戏更新后 `--refresh`，
   或直接删掉对应缓存文件。
10. **名字语言**：`name` 一律英文（`name_zh` 备查）。中文只会出现在备注里。
    分区要同时写 `name`（中文）和 `name_en`（英文），只写一个会被另一侧顶掉。
11. **快捷键“没反应”/“旧键还有效”先分四种情况**：
    a) 钩子没装上 → 底部会写「快捷键不可用（错误码 N）」；
    b) 装上了但收不到键 → 游戏是管理员权限而本工具不是（UIPI 拦截），用管理员启动本工具；
    c) 收到了但窗口看不见 → 游戏在独占全屏，换成无边框/窗口化全屏；
    d) **有旧实例还在跑** → 它仍然响应旧快捷键（改了 Ctrl+A，按 M 还会弹）。新版本加了
    单实例锁，启动第二个会弹提示；先把 `pythonw.exe` 结束掉。
    `python hotkey.py -k ctrl+a` 可以单独验证钩子。
12. **`ctypes.wintypes` 里没有 `KBDLLHOOKSTRUCT`**：必须自己声明结构体（`hotkey.py` 里已经写了）。
    以前直接 `cast(l_param, POINTER(wt.KBDLLHOOKSTRUCT))` 每次都抛 `AttributeError`，被
    `except: pass` 吞掉 —— 钩子装好了、日志也不报错，但按什么键都没反应，极难查。
13. **`set.issubset(dict)` 比的是键，不是值**：判断修饰键时如果写成
    `{'ctrl'}.issubset({'ctrl': False, 'shift': False, ...})`，结果**永远是 True**，
    于是配了 `ctrl+a` 光按 `a` 也会触发。`hotkey._mods_down()` 现在返回**按下的键名集合**
    （`{'ctrl'}` / `set()`），别再改回字典。
14. **旋转后的平移/缩放要换算**：屏幕位移 `(dx, dy)` 在 90°/270° 时对应的 `ox/oy` 增量是
    `(dy, -dx)`，所以拖动统一走 `View.pan_by()`，别再直接 `ox += dx`。另外 Tk Canvas 自带
    `<MouseWheel>` 绑定会 `yview` 滚动视口（只挪视口、不改坐标，看着就像"位置莫名跳一下"），
    `_on_wheel` 末尾 `return 'break'` 把它挡掉。
15. **图别被拖丢**：`View.clamp()` 保证地图至少有 60px 留在窗口里，拖动结束时按视图重整一次画布
    （`canvas.move` 只是拖动过程里的快速反馈）。

---

## 7. 快捷键与「本局答案」（seed 集成）

### 用法

```powershell
cd <本仓库目录>\ui
python mapview.py                      # 打开窗口，等日志自动加载（右侧自带答案面板）
python mapview.py --hotkey ctrl+a      # 指定全局快捷键（默认就是 ctrl+a）
python mapview.py PSA_MT01             # 锁定看某一关，不跟日志自动切
python mapview.py --no-seed            # 只要地图，不要答案面板
```

开机挂着它、进游戏后：

1. 日志里出现 `GameStageInfo changed. ... Trial ID: PSA_MT01, ..., Seed: 123456, ...` 就**立刻**
   算答案 + 切到这一关的地图（不用等几十秒后的 `StageReady`）
2. 答案里带坐标的条目会**自动标在地图上**（圆圈数字 ①②③ + 标签）
3. 工具栏 `seed (N)` 勾选框或按 `S` 可整体显隐；分层模式下只显示本层的标记
4. 点标记 → 信息栏显示 section/房间/坐标，并**复制坐标**；对应的房间会高亮
5. 按 `R` 强制重算；`H` 调出/收起左上角图例；再按 `Ctrl+A` 把窗口收回

游戏里按 **Ctrl+A** 就是开关：窗口收着（或最小化）就弹出 + 置顶 + 抢焦点 + 刷新答案，
已经显示着就收回。**点窗口右上角 X 也只是收起**（进程留着，Ctrl+A 再叫出来），
要真正退出程序点工具栏右侧的 **Quit**（或把 `close_action` 设成 `quit`）。

- 快捷键用低级键盘钩子（`hotkey.py`），**只观察不吞键**——游戏照常收到键，不注入进程、不读内存
- 组合键写法：`ctrl+a` / `ctrl+shift+m` / `alt+F9` / `F8` / `M`，改 `config.json` 的 `hotkey`，
  写 `none` 关闭。**默认用 Ctrl+A 就是为了打字输入 M 时不误触发**（单键只在「没有按 Ctrl/Alt/Win」
  时才响应；而单键若被游戏占用，会两边一起响应）
- 置顶靠 `always_topmost`（默认 true）。游戏是**独占全屏**时 Windows 不允许别的窗口压上去，
  换成「无边框窗口 / 窗口化全屏」就能看到（游戏侧限制，工具绕不过）
- **权限要对齐**：如果 OPP 是「以管理员身份运行」，本工具也必须以管理员身份启动，否则
  Windows 的 UIPI 会让钩子收不到按键；启动脚本右键 →「以管理员身份运行」
- 排查快捷键：`python hotkey.py -k ctrl+a`，按一下看有没有打印（启动时也会把实际生效的键
  写进 `mapview_out.log`）
- **只允许一个实例**：已经开着一个再启动会弹「已经有一个地图工具在运行」。改了 `hotkey`
  之后必须先关掉旧进程——否则老进程还在用老键响应（比如改了 Ctrl+A，按 M 照样弹出），
  任务管理器里结束 `pythonw.exe` / `python.exe` 即可
- **弹出时自动抢焦点**：除置顶外还会 `AttachThreadInput` 抢前台、`ClipCursor(None)`
  解除游戏对鼠标的锁定，并把指针挪到窗口中心。否则鼠标一动就被游戏吃去转视角，工具栏勾不到
- 点房间/点位自动复制的是**原始名**（`RBRoom_...` / `MT01_Clue_...`），界面上显示的
  中英文名只是给人看的；要再复制一次用 `Copy raw`

**地图会自动跟着本局走**（不给 LEVEL 时）：读到的 `Trial ID` 和当前窗口关卡不同时，直接切到
那一关的地图（图层开关、备注等都保留）。给了 LEVEL 就锁定，想跟随就加 `--follow` 或勾
工具栏 `follow log`。这关还没生成过地图数据时，底部会提示 `python mapdb.py <关卡>`。

### 数据流

```
OPP.log ──(gamelog.py：整份读，>16MB 才只读末尾 8MB)──> {trial, seed, players, difficulty, status, time}
                                            │
                                            ▼
                             seedinfo.py（进程内调 seed.py 的 predict / render）
                                            │
                        ┌───────────────────┴────────────────────┐
                        ▼                                        ▼
        seedpanel.py（右侧文本）                   markers.py（从结果里挖坐标）
        '!' 提示橙色，答案行加粗                     → 地图上的 ①②③ 标记
```

### 坐标标记怎么来的

不针对某一关卡写死，按字段名递归找（`markers.py`）：

| seed.py 输出 | 标记标签 |
|---|---|
| `patterns[].coordinates`（MHS 投影符号） | `骷髅 854`（图案名 + 密码） |
| `mannequins[].coordinates`（SMC 人偶） | `红 / 绿 / 蓝 / 教学` |
| `rooms[].coordinates`（CHJ 房间 + 密码） | 密码 `2671` |
| `connections[].letter_coordinates / number_coordinates`（TSR） | `Letter J` / `Number 21` |
| `clue.crime_scene_coordinates`（RES） | `Break Room` |

- `coordinate_type = room_center` 的用**空心虚线圆**，表示只到房间级别，不是道具精确位置
- 世界坐标和地图是同一套，直接 `Layout` 换算，不偏移
- PNG 导出想带标记：`--png a.png --seed-marks`（只在日志里的关卡与所画关卡一致时才加）

日志里认这两种行：

```
[..]RB:  StageReady. Trial ID: MHS_MT01, Stage: ..., Mission: MHS_MT01, Seed: 759759, ENbPlayer: 1
[..]RB:  GameStageInfo changed. ... Trial ID: MHS_MT01, Program difficulty: Easy, ..., Seed: 759759, ...
```

**「最后一局」怎么算**：`GameStageInfo` 和 `StageReady` 一起按行号排序，取最后一条。所以

- 新一局刚开始，只有 `GameStageInfo`（带 Trial ID / Seed / 难度 / 人数）→ 状态 `loading`（面板显示
  「加载中」），**答案已经算好、地图已经切过去了**
- 几十秒后 `StageReady` 出现 → 状态变 `准备中`；`StageStarted / StageEnding / StageSuccess /
  ReturnToLobby` 依次变「进行中 / 已结束」
- `StageReady` 行里没有难度，用同一 seed 的 `GameStageInfo` 补；补不到按 Easy

**刷新时机**：主窗口每 `poll_interval_ms`（默认 900ms）stat 一次日志，**文件大小/mtime 变了才
解析**；解析出来的 (关卡, 种子, 人数, 难度, 状态) 和上次不同才重算答案。按 `R`/「刷新」是强制重算。

### 日志路径

依次找：`config.json` 的 `log_path` → 环境变量 `OPP_LOG` →
`%LOCALAPPDATA%\OPP\Saved\Logs\OPP.log` → `%LOCALAPPDATA%\*\Saved\Logs\OPP.log` →
本目录的 `OPP.log`（调试副本）。

```powershell
python gamelog.py            # 当前读到哪一局
python gamelog.py --all      # 日志里所有对局
python gamelog.py --json
python seedinfo.py --log     # 直接算日志里最新一局
```

### 配置 `config.json`

```jsonc
{
  "log_path": null,            // 留空=自动找
  "hotkey": "ctrl+a",          // ctrl+a / M / F1~F12 / none
  "seed_lib": null,            // 留空=上级目录的 seed.py
  "panel_width": 440,
  "window": "1440x960",        // 关窗口时会记住实际大小
  "activate_on_hotkey": true,  // 弹出时抢焦点（要操作地图就需要）
  "always_topmost": true,      // 弹出后压在最上面（游戏全屏必须）
  "follow_game": true,         // 按日志里的关卡自动切地图
  "poll_log": true,            // 自动轮询日志（关了就只按 R 才刷新）
  "poll_interval_ms": 900,
  "font_scale": 1.0,           // 字太小就 1.15；也可以用 --font-scale
  "show_legend": false,        // 左上角图例默认关；工具栏 legend / H 切换
  "flip": null,                // 镜像：null=按 data/orientation.json（缺省 x）
  "close_action": "hide"       // 点 X 只收起（Ctrl+A 叫回来）；quit=直接退出
}
```

`seed.py` 默认取上级目录的 `seed.py`；单独交付时用 `--seed-lib` 或环境变量 `OPP_SEED_LIB` 指定。
找不到时面板会直接说明原因，不影响看地图。

---

## 8. 朝向：镜像与旋转

**结论：以前这版渲染和旧交付图是左右反的。** 依据有两条：

1. 旧工具 `release/map/map.py` 默认 `--flip x`，注释写着「交付版默认左右镜像」；
2. `release/map/orientation.json` 里唯一核对过的图：
   > CourthouseJudicial 与玩家手绘图 ref.jpg 核对：右上角斜向突出的庭院/天桥块在镜像后吻合，故取 x。

`mapview.py` 原来只做 `screen_y = oy - y*scale`（Y 向上），没有 X 轴镜像，所以它画出来是
旧交付图的镜像版。现在**默认左右镜像（x）**，与旧图一致。

四个层级都能改，优先级从高到低：

| 方式 | 写法 | 生效范围 |
|---|---|---|
| `config.json` | `"flip": "none"` / `"x"` / `"y"` / `"xy"` | 每次启动（最高优先级，`null` = 用下面两项） |
| 命令行 | `--flip none` / `--flip x` | 本次运行 |
| 界面 | 工具栏 `Mirror X`、快捷键 `X` | 立刻生效（只影响本次运行，不改配置） |
| 每张图 | `data/orientation.json` | 被上面几项覆盖之前，按图取；没写的按 `x` |

`data/orientation.json`：

```jsonc
{ "CourthouseJudicial": "x",             // 键名可以是地图名…
  "CHJ_MT01": "x",                       // …也可以是关卡号
  "MobsterHideoutSyndicate": "none" }
```

右下角一直显示当前状态（`Overlay · all floors (3) · mirror X · rot 90°`），搞不清朝向看那里。

### 旋转

`T` 或工具栏 `Rotate`，每次顺时针 90°，转完自动重新适应窗口。旋转在**屏幕空间**绕视图中心
做，所以：

- 房间、门、点位、坐标标记一起转；
- **文字（房间名、点位短名、图例、右下角状态）始终水平**，不会被倒过来；
- 滚轮缩放锚点、拖拽平移、点击命中都不受影响；
- `--png` 同样支持：`python mapview.py MHS_MT01 --png a.png --rot 90 --flip x`。

图层/分区/备注都在世界坐标层面算完再投影，所以朝向怎么变都不影响数据和交互。
