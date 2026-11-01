# -*- coding: utf-8 -*-
"""UE 关卡 JSON 解析内核（解析 / 翻译 / 几何 / 门分类）。

出处：原 `release/map2/mapcore.py` 的前半部分（解析内核），**已内联进本项目**，
不再从旧 map 工具导入；渲染/出图/wik i 那一半没有搬过来。

对外提供的都是纯函数 + `MapExtractor`，路径由调用方传入，本模块不假设仓库结构。
仅 `i18n_names.json`（房间译名覆盖表）需要放在 `<ui>/data/` 下。
"""
from __future__ import annotations

import collections
import io
import json
import math
import os
import re
import statistics
import sys

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
I18N_FILE = os.path.join(DATA_DIR, 'i18n_names.json')
OVERRIDE_FILE = I18N_FILE          # 兼容原文件里的命名

# 单个顶层对象的大小上限（字节）。超过就跳过不解析，见 iter_objects。
MAX_OBJ_BYTES = 24 * 1024 * 1024


import argparse
import collections
import contextlib
import glob
import io
import json
import math
import os
import re
import subprocess
import sys


# ================================ 翻译(i18n) ====

"""房间/门/物品名称的英文 -> 中文对照。

- 先查整串复合词 (crawlspace / generatorroom / chdoor ...), 再逐词根替换;
- CamelCase 与下划线都会被拆开, 数字、楼层序号(2nd/3rd)、未知缩写原样保留;
- 同目录 i18n_names.json 的人工校对结果优先 (可自行修改后重跑)。
"""


HERE = os.path.dirname(os.path.abspath(__file__))
OVERRIDE_FILE = I18N_FILE

MAP_ZH = {
    'AmeliaEscape02': '阿米莉亚逃脱 02',
    'AmeliaEscapeTrial': '阿米莉亚逃脱（试炼）',
    'Courthouse': '法院',
    'CourthouseArchive': '法院 · 档案区',
    'CourthouseJudicial': '法院 · 审判区',
    'DowntownRiot': '市中心暴乱',
    'DowntownRiotSewers': '市中心暴乱 · 下水道',
    'FunPark': '欢乐公园',
    'FunParkBarn': '欢乐公园 · 谷仓',
    'FunParkCanal': '欢乐公园 · 运河',
    'FunParkIllusion': '欢乐公园 · 幻境',
    'Global': '全局（逻辑层）',
    'Lobby': '试炼前厅',
    'Mansion': '宅邸',
    'MansionEscape': '宅邸逃脱',
    'MansionEscape_2': '宅邸逃脱 2',
    'MobsterHideout': '黑帮藏身处',
    'MobsterHideoutSyndicate': '黑帮藏身处 · 辛迪加',
    'Orphanage': '孤儿院',
    'OrphanageInstitution': '孤儿院 · 收容所',
    'OrphanageServices': '孤儿院 · 后勤区',
    'PoliceStation': '警察局',
    'PoliceStationAttic': '警察局 · 阁楼',
    'PoliceStationBasement': '警察局 · 地下',
    'PoliceStationOffices': '警察局 · 办公区',
    'PrisonFarm': '监狱农场',
    'ReleaseDestinations': '释放目的地（逻辑层）',
    'Resort': '度假村',
    'ResortSpa': '度假村 · 水疗区',
    'ShoppingMall': '购物中心',
    'ShoppingMallCarrefour': '购物中心 · 超市区',
    'SuburbRiot': '郊区暴乱',
    'SuburbRiotResidential': '郊区暴乱 · 住宅区',
    'TelevisionStudio': '电视演播室',
    'TelevisionStudioRooftop': '电视演播室 · 屋顶',
    'ToyFactory': '玩具工厂',
    'ToyFactoryShipping': '玩具工厂 · 运输区',
    'ToyFactoryWarehouse': '玩具工厂 · 仓库',
}

# 词根表 (键为小写紧凑写法, 复合词优先匹配)
WORDS = {
    # 方位 / 楼层
    'west': '西', 'east': '东', 'north': '北', 'south': '南', 'central': '中央',
    'center': '中央', 'middle': '中部', 'northwest': '西北', 'northeast': '东北',
    'southwest': '西南', 'southeast': '东南', 'left': '左', 'right': '右',
    'side': '侧', 'front': '正面', 'back': '后', 'rear': '后', 'top': '顶部',
    'upper': '上层', 'lower': '下层', 'under': '下方', 'down': '下层', 'up': '上层',
    'outside': '外部', 'inner': '内侧', 'outer': '外侧', 'corner': '转角',
    'gf': '一层', 'groundfloor': '一层', 'ground': '地面层', 'basement': '地下室',
    'b1': '地下一层', 'b2': '地下二层', 'attic': '阁楼', 'roof': '屋顶',
    'rooftop': '屋顶', 'underground': '地下', 'floor': '层', 'hall2nd': '二层厅',
    '1f': '一层', '2f': '二层', '3f': '三层', '4f': '四层',
    'mansion1st': '宅邸一层', 'mansion2nd': '宅邸二层',
    # 房间类型
    'room': '房', 'rooms': '房区', 'corridor': '走廊', 'cooridor': '走廊',
    'corridors': '走廊', 'hall': '厅', 'halls': '厅区', 'hallway': '走廊',
    'main': '主', 'mainhall': '主厅', 'lobby': '大堂', 'lobbyhall': '大堂厅',
    'entrance': '入口', 'entrancehall': '入口大厅', 'exit': '出口',
    'stair': '楼梯', 'stairs': '楼梯', 'staircase': '楼梯', 'stairwell': '楼梯井',
    'stairhall': '楼梯厅', 'landing': '平台',
    'office': '办公室', 'offices': '办公区', 'study': '书房', 'library': '图书室',
    'laboratory': '实验室', 'lab': '实验室', 'bathroom': '洗手间', 'toilet': '厕所',
    'shower': '淋浴间', 'dressing': '更衣室', 'cloakroom': '衣帽间',
    'kitchen': '厨房', 'dining': '餐厅', 'cafeteria': '食堂', 'restaurant': '餐厅',
    'bar': '酒吧', 'pub': '酒吧', 'casino': '赌场', 'gambling': '赌博区',
    'storage': '储藏室', 'store': '商店', 'warehouse': '仓库', 'depot': '库房',
    'closet': '储物间', 'locker': '储物柜', 'lockers': '储物柜区',
    'maintenance': '维修间', 'workshop': '车间', 'worshop': '车间',
    'generator': '发电机', 'generatorroom': '发电机房', 'boiler': '锅炉房',
    'incinerator': '焚化炉', 'control': '控制', 'controlroom': '控制室',
    'security': '安保区', 'monitoring': '监控室', 'surveillance': '监控区',
    'observation': '观察室', 'reception': '接待处', 'waiting': '等候区',
    'queue': '排队区', 'conference': '会议室', 'meeting': '会议室',
    'administration': '行政区', 'admin': '行政', 'records': '档案室',
    'archives': '档案库', 'archive': '档案库', 'evidence': '证物',
    'evidenceoffice': '证物室', 'evidencehall': '证物厅', 'courtroom': '法庭',
    'judge': '法官', 'judges': '法官', 'judgesoffice': '法官办公室',
    'clerks': '书记员室', 'clerksoffice': '书记员办公室', 'detective': '警探',
    'interrogation': '审讯室', 'holding': '拘留', 'holdingcells': '拘留牢房',
    'cell': '牢房', 'cells': '牢房', 'jail': '监狱', 'prison': '监狱',
    'warden': '典狱长', 'patrol': '巡逻区', 'armory': '军械库', 'morgue': '停尸房',
    'infirmary': '医务室', 'medical': '医务', 'pharmacy': '药房',
    'pharmcoldstorage': '药品冷藏室', 'drug': '毒品', 'research': '研究区',
    'testing': '试验区', 'conditioning': '调教区', 'torture': '刑讯室',
    'execution': '行刑区', 'kill': '处决', 'trap': '陷阱区',
    'dorm': '宿舍', 'dorms': '宿舍区', 'bedroom': '卧室', 'house': '房屋',
    'school': '学校', 'classroom': '教室', 'playground': '操场', 'gym': '体育馆',
    'church': '教堂', 'chapel': '礼拜堂', 'crypt': '地窖', 'cemetary': '墓地',
    'cemetery': '墓地', 'museum': '博物馆', 'theater': '剧院', 'theatre': '剧院',
    'cinema': '影院', 'studio': '演播室', 'studio1': '1号演播室',
    'studio2': '2号演播室', 'studio3': '3号演播室', 'studio4': '4号演播室',
    'studio5': '5号演播室', 'backstage': '后台', 'broadcast': '广播',
    'broadcasting': '广播室', 'audio': '音频区', 'visual': '视频区',
    'antenna': '天线区', 'factory': '工厂', 'prod': '生产', 'line': '线',
    'prodline': '生产线', 'conveyor': '传送带', 'materials': '物料区',
    'shipping': '运输区', 'receiving': '收货区', 'loading': '装卸区',
    'loadingarea': '装卸区', 'loadingentrance': '装卸入口', 'docks': '码头区',
    'receivingdocks': '收货码头', 'dock': '码头', 'hangar': '机库',
    'shipyard': '船厂', 'garage': '车库', 'parking': '停车场', 'car': '车辆',
    'vehicle': '车辆', 'metro': '地铁', 'subway': '地铁', 'train': '列车',
    'trainyard': '列车编组场', 'station': '车站', 'bunker': '地堡',
    'caves': '洞穴', 'cave': '洞穴', 'sewer': '下水道', 'sewers': '下水道',
    'sewertunnel': '下水道隧道', 'uppersewer': '上层下水道',
    'lowersewer': '下层下水道', 'tunnel': '隧道', 'pipes': '管道区',
    'hydro': '水电站', 'canal': '运河', 'bridge': '桥', 'ramp': '坡道',
    'basementramp': '地下坡道', 'catwalk': '天桥', 'shuttle': '接驳车',
    'shuttlequeue': '接驳排队区', 'bus': '巴士', 'boat': '船', 'truck': '卡车',
    'donut': '甜甜圈', 'donuttruck': '甜甜圈车', 'diner': '餐馆',
    'grocery': '杂货店', 'shop': '商店', 'fashion': '时装店',
    'department': '百货', 'departmentstore': '百货商店', 'salon': '沙龙',
    'hair': '理发店', 'spa': '水疗区', 'pool': '泳池', 'garden': '花园',
    'park': '公园', 'barn': '谷仓', 'farm': '农场', 'yard': '场地',
    'courtyard': '庭院', 'backyard': '后院', 'alley': '小巷',
    'backalley': '后巷', 'street': '街道', 'streets': '街区', 'town': '镇区',
    'villa': '别墅', 'mansion': '宅邸', 'shack': '棚屋', 'building': '建筑',
    'facade': '外立面', 'tower': '塔楼', 'block': '街区', 'hub': '枢纽区',
    'area': '区域', 'space': '空间', 'path': '通道', 'access': '通道',
    'connection': '连接处', 'wall': '墙', 'window': '窗', 'door': '门',
    'gate': '大门', 'carrefour': '超市', 'commercial': '商业区',
    'dealership': '车行', 'bank': '银行', 'post': '邮政', 'postoffice': '邮局',
    'sorting': '分拣区', 'printing': '印刷室', 'clothing': '服装店',
    'laundry': '洗衣房', 'restroom': '洗手间', 'water': '水池', 'fire': '消防',
    'chemical': '化学品', 'explosive': '爆炸物', 'machinery': '机械区',
    'harvester': '收割者', 'panopticon': '全景监狱', 'facility': '设施',
    'infants': '婴儿区', 'girls': '女生区', 'boys': '男生区', 'women': '女区',
    'men': '男区', 'orph': '孤儿', 'orphroom': '孤儿房', 'wine': '酒窖',
    'cellar': '地窖', 'vault': '金库', 'auction': '拍卖场', 'loge': '包厢',
    'circus': '马戏团', 'illusion': '幻境', 'puppet': '木偶', 'rabbit': '兔子',
    'easter': '复活节', 'egg': '彩蛋', 'eastereggsroom': '彩蛋房',
    'dark': '黑暗区', 'lights': '灯光区', 'silent': '静默区',
    'broken': '破损区', 'old': '旧', 'new': '新', 'big': '大', 'small': '小',
    'long': '长', 'open': '开放', 'closed': '封闭', 'secret': '密道',
    'hidden': '隐藏', 'escape': '逃生', 'intro': '序章', 'ending': '结局',
    'final': '最终', 'reward': '奖励', 'prime': '精华', 'asset': '资产',
    'regroup': '集合点', 'infiltration': '潜入', 'escort': '护送',
    'first': '第一', 'second': '第二', 'cold': '冷藏', 'warm': '常温',
    # 地图专有缩写 / 人名
    'ps': '警局', 'ex': '外部', 'ext': '外部', 'exterior': '室外',
    'expop': '实验区', 'pop': '城区', 'rdc': 'RDC', 'rc': 'RC', 'sas': 'SAS',
    'mc': 'MC', 'presbyter': '长老区', 'dallers': '达勒斯', 'rich': '富人区',
    'poor': '贫民区', 'gore': '血腥区', 'foreman': '工头', 'chief': '警长',
    'scientist': '科学家', 'worker': '工人', 'guard': '守卫',
    'criminal': '罪犯', 'human': '人体', 'aster': '紫菀', 'design': '设计区',
    'upside': '倒置区', 'hole': '深坑', 'jump': '跳跃区', 'cons': '建设',
    'constrcution': '施工', 'contruction': '施工', 'construction': '施工',
    'constrution': '施工', 'scrapyard': '废料场', 'judicial': '审判',
    'court': '法院', 'courthouse': '法院', 'master': '主区', 'slave': '副区',
    'controls': '控制区', 'witness': '证人区', 'cellblock': '牢房区',
    'valve': '阀门', 'filming': '拍摄区', 'balcony': '露台', 'nook': '凹间',
    'crawl': '爬行', 'crawlspace': '夹层', 'lounge': '休息室',
    'breakroom': '休息室', 'break': '休息', 'mall': '商场', 'shooting': '射击',
    'range': '靶场', 'shootingrange': '靶场', 'janitor': '清洁工',
    'janitorcloset': '清洁间', 'ward': '病区', 'chambre': '房间',
    'bench': '长椅', 'walkway': '步道', 'service': '服务',
    'servicecorridor': '服务走廊', 'servicehall': '服务厅',
    'services': '后勤区', 'service1': '后勤区1', 'service2': '后勤区2',
    'tortureroom': '刑讯室', 'eastside': '东侧', 'wastside': '西侧',
    'ch': '法院', 'chj': '法院', 'cardbord': '纸板',
    'cardbordbarrel': '纸板桶', 'controlroom': '控制室',
    'backroom': '后室', 'toys': '玩具', 'toy': '玩具', 'doll': '玩偶',
    'employee': '员工', 'staff': '员工', 'lockerroom': '更衣室',
    'manager': '经理室', 'managerroom': '经理室', 'guest': '客房',
    'guestroom': '客房', 'beach': '海滩', 'housekeeping': '客房服务',
    'laundry': '洗衣房', 'boilerroom': '锅炉房', 'frontdesk': '前台',
    'backyard': '后院', 'garage': '车库', 'hangar': '机库',
    'basement': '地下室', 'mechanic': '机修间', 'crypt': '地窖',
    'lobby': '大堂', 'suites': '套房', 'suite': '套房', 'vip': '贵宾区',
    'unnamed': '未命名', 'resort': '度假村', 'studio': '演播室', 'soundstage': '摄影棚',
    'controlroom': '控制室', 'editing': '剪辑室', 'props': '道具区',
    'gameroom': '游戏室', 'finearts': '美术室', 'telephone': '电话间',
    'changeroom': '更衣室', 'rewardroom': '奖励房', 'janitor': '清洁间',
    'chargehand': '工头室', 'beautysalon': '美容院', 'massage': '按摩室',
    'elevator': '电梯', 'lift': '电梯', 'harbor': '港口', 'guardpost': '守卫岗',
    'blueprints': '蓝图', 'blueprint': '蓝图', 'bureau': '局', 'statue': '雕像',
    'crew': '船员', 'officeblock': '办公区', 'newsroom': '新闻室',
    'chineserestaurant': '中餐厅', 'chinese': '中式', 'small': '小',
    'corridorsmall': '小走廊', 'exitsign': '出口标志',
    '1stfloor': '一层', '2ndfloor': '二层', '3rdfloor': '三层',
    '4thfloor': '四层', '1st': '一层', '2nd': '二层', '3rd': '三层', '4th': '四层',
    'coordination': '协调区', 'cooridor': '走廊', 'blockout': '灰模区',
    'temp': '临时区', 'shared': '共用区', 'reverse': '反向', 'stages': '舞台区',
    'stage': '舞台', 'sound': '音响', 'film': '拍摄', 'talent': '演员',
    'actors': '演员', 'actorsdepartment': '演员部', 'department': '部门',
    'wardrobe': '服装间', 'makeup': '化妆间', 'prop': '道具',
    'props': '道具区', 'lighting': '灯光', 'set': '布景', 'sets': '布景区',
    # 物品 / 门
    'health': '医疗', 'antidote': '解毒剂', 'medkit': '医疗包',
    'medicine': '药品', 'adrenaline': '肾上腺素', 'bandage': '绷带',
    'document': '文件', 'objective': '目标', 'evidencebox': '证物箱',
    'head': '头颅', 'headevidence': '头颅证据', 'utility': '工具',
    'lockpick': '撬锁器', 'pile': '堆', 'toolbox': '工具箱',
    'toolcabinet': '工具柜', 'hidespot': '藏身点', 'phonebooth': '电话亭',
    'barrel': '桶', 'cardboard': '纸板', 'cardboardbarrel': '纸板桶',
    'garbagebin': '垃圾桶', 'thrashcan': '垃圾桶', 'trashcan': '垃圾桶',
    'cornerdesk': '角桌', 'deskwood': '木桌', 'workshopbasket': '工篮',
    'woodbox': '木箱', 'boxopen': '敞口箱', 'surface': '台面',
    'exitstage': '撤离点', 'largepuzzle': '大型解谜', 'largepuzzleroom': '大型解谜房',
    'gatheranddeliver': '收集运送', 'objcoord': '目标坐标',
    'gascan': '汽油桶', 'battery': '电池', 'key': '钥匙', 'keys': '钥匙',
    'coin': '硬币', 'money': '钱', 'letter': '信件', 'note': '便条',
    'poster': '海报', 'picture': '照片', 'tape': '磁带', 'radio': '收音机',
    'battery': '电池', 'bottle': '瓶子', 'crate': '板条箱', 'crates': '板条箱',
    'box': '箱子', 'boxes': '箱子', 'bag': '袋子', 'basket': '篮子',
    'shelf': '货架', 'shelves': '货架', 'cabinet': '柜子', 'drawer': '抽屉',
    'table': '桌子', 'desk': '桌子', 'chair': '椅子', 'bed': '床',
    'couch': '沙发', 'sofa': '沙发', 'trash': '垃圾', 'dumpster': '垃圾箱',
}

CAT_ZH = {
    'objective': '目标点',
    'evidence': '证据 / 头颅',
    'document': '文档',
    'health': '药品 / 血包',
    'tool': '工具 / 撬锁',
    'hide': '藏身点',
    'container': '容器',
}

DOOR_WORDS = {
    'chdoor': '法院门', 'doorwood': '木门', 'rollingdoor': '卷帘门',
    'doubledoor': '双开门', 'monsterclosetdoor': '怪物柜门',
    'staticslidingdoor': '固定滑门', 'backgrounddoor': '背景门',
    'sasdoor': 'SAS 门', 'lobbymurkoffemployeedoor': '大堂员工门',
    'employeedoor': '员工门', 'slidingdoor': '滑门', 'door': '门',
    'rolleddoor': '卷帘门', 'metal': '金属', 'wood': '木质',
}

_PREFIX_RE = re.compile(r'^(SP-|CHJ_|Cont-|Hidespot_|Cont-?DirectSurface-|'
                        r'RBRoom_?|RBRoom)', re.I)
_SUFFIX_RE = re.compile(r'(_BP\d?_C|_BP_C|_BP\d?|_C)$', re.I)
_TOKEN_RE = re.compile(r'\d+(?:st|nd|rd|th)|[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+|[\u4e00-\u9fff]+')
_DROP_SEG = re.compile(r'^(sp|cont|chj|bp\d?|c|surface|directsurface|objcoord|pile)$', re.I)

_overrides = None


def load_overrides():
    global _overrides
    if _overrides is None:
        try:
            with io.open(OVERRIDE_FILE, encoding='utf-8') as f:
                _overrides = json.load(f)
        except Exception:
            _overrides = {}
    return _overrides


def _clean(text):
    return _SUFFIX_RE.sub('', _PREFIX_RE.sub('', text or '')).replace('_', ' ')


def _compact(s):
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _tokens(text):
    raw = []
    for chunk in _clean(text).split():
        raw.extend(_TOKEN_RE.findall(chunk))
    # 2 / F 这类楼层标记合并成 2F
    out, i = [], 0
    while i < len(raw):
        if re.fullmatch(r'\d+', raw[i]) and i + 1 < len(raw) and raw[i + 1] in ('F', 'B', 'D'):
            out.append(raw[i] + raw[i + 1])
            i += 2
        else:
            out.append(raw[i])
            i += 1
    return out


def _lookup(key):
    key = key.lower()
    return WORDS.get(key) or DOOR_WORDS.get(key)


def _translate_token(tok):
    low = tok.lower()
    if low in WORDS:
        return WORDS[low]
    m = re.fullmatch(r'(\d+)(st|nd|rd|th)', low)
    if m:
        return m.group(1) + 'F'
    m = re.fullmatch(r'([a-z]+?)(\d{1,2})(st|nd|rd|th)?', low)
    if m:
        base, num, suf = m.group(1), m.group(2), m.group(3)
        if suf:
            return WORDS.get(base, base) + num + 'F'
        if base in WORDS:
            return WORDS[base] + num
        return tok
    return tok


GENERIC_SUFFIX = ('房', '厅', '室', '区', '区域', '空间', '间')


def _join(parts):
    out = ''
    for p in parts:
        if not p:
            continue
        if out and out.endswith(p):          # 发电机房 + 房
            continue
        if out and p in GENERIC_SUFFIX and out[-1] in '室间厅区房层街楼园场':
            continue                          # 装卸区 + 区域
        if out and _is_latin(out[-1]) and _is_latin(p[0]):
            out += ' '
        out += p
    return out


def _is_latin(ch):
    return ch.isascii() and ch.isalnum()


def translate(text, overrides=True):
    """英文名 -> 中文名, 未识别的词保留原文。"""
    if not text:
        return ''
    if overrides:
        ov = load_overrides()
        if text in ov:
            return ov[text]
    key = _compact(_clean(text))
    if key in WORDS:
        return WORDS[key]
    toks = [t for t in _tokens(text) if t]
    if not toks:
        return text

    # 贪心最长匹配: 优先把相邻词合成复合词 (department store / loading area ...)
    parts = []
    i = 0
    while i < len(toks):
        hit = None
        for span in (3, 2):
            if i + span <= len(toks):
                key = _compact(''.join(toks[i:i + span]))
                if key in WORDS or key in DOOR_WORDS:
                    hit = (span, _lookup(key))
                    break
        if hit:
            parts.append(hit[1])
            i += hit[0]
        else:
            parts.append(_translate_token(toks[i]))
            i += 1
    return _join(parts).strip()


def coverage(text):
    toks = [t for t in _tokens(text) if t.isalpha()]
    if not toks:
        return 0.0
    return sum(1 for t in toks if _translate_token(t) != t) / len(toks)


GENERIC_ITEM = {'health', 'utility', 'document', 'objective', 'evidence'}


def _segments(text, extra_drop=()):
    base = _SUFFIX_RE.sub('', _PREFIX_RE.sub('', text or ''))
    segs = [s for s in re.split(r'[-_]+', base) if s]
    out = []
    for s in segs:
        if _DROP_SEG.match(s) or _compact(s) in extra_drop:
            continue
        out.append(s)
    return out


def translate_door(t):
    """RollingDoor-DoubleDoor_BP_C -> 卷帘门·双开门"""
    res = []
    for s in _segments(t):
        key = _compact(s)
        if key in DOOR_WORDS:
            res.append(DOOR_WORDS[key])
        elif re.fullmatch(r'\d+[a-z]?', s, re.I):
            res.append(s.lower())
        else:
            res.append(translate(s, overrides=False))
    res = [r for r in dict.fromkeys(res) if r]
    return '·'.join(res) or t


def translate_item(t):
    """SP-Health-Antidote-Surface_BP_C -> 医疗·解毒剂"""
    segs = [s for s in _segments(t) if not re.fullmatch(r'[A-Za-z]{1,2}\d{0,2}', s)]
    if len(segs) > 1:
        segs = [s for s in segs if _compact(s) not in GENERIC_ITEM] or segs
    res = []
    for s in segs:
        zh = translate(s, overrides=False)
        if not zh or zh.lower() in ('c', 'bp'):
            continue
        if any(zh in r or r in zh for r in res):   # 桶 / 纸板桶
            longer = max([zh] + [r for r in res if zh in r or r in zh], key=len)
            res = [r for r in res if r not in longer]
            zh = longer
        res.append(zh)
    return '·'.join(dict.fromkeys(res)) or t


def write_overrides(names, path=OVERRIDE_FILE):
    """导出「可能译得不完整」的条目供人工校对(已存在则不覆盖)。

    只导出含残留英文或词根覆盖率低的名称, 其余走词表自动翻译 ——
    这样以后补充词表仍然对大部分房间生效。
    """
    if os.path.exists(path):
        return path
    data = {}
    for n in sorted(set(names)):
        zh = translate(n, overrides=False)
        if not zh or zh == n:
            continue
        if re.search(r'[A-Za-z]{2,}', zh) or coverage(n) < 0.75:
            data[n] = zh
    with io.open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    global _overrides
    _overrides = data
    return path

# ================================ 解析(mapdata) ====

"""从 UE4 导出的 MAP JSON 中提取房间/门/物品等平面图信息。

用法:
    python MAP/tools/map.py parse <map文件夹> -o plan.json [--mode local|raw]
"""


# ---------------------------------------------------------------- 基础工具


def iter_objects(path, max_obj=MAX_OBJ_BYTES):
    """按行流式切分顶层对象并逐个 json.loads，避免整个大文件进内存。

    导出格式为 2 空格缩进的 pretty json，顶层数组元素以 '  {' 开头、
    以 '  }' / '  },' 结尾，内部缩进更深，因此按行切分是安全的。

    超过 max_obj 字节的单个对象只跳过、不解析：PoliceStationOffices 的
    `PSO_Admin-01_ART.json` 里有个几百万行的 Brush/Spline 对象，整段读进
    内存会直接 MemoryError（早期整文件扫描时就是这么挂的）。
    这类超大对象里只有几何网格数据，不会有房间 / 门 / 物品 actor。
    """
    buf = []
    size = 0
    idx = -1
    skipping = False
    with io.open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            s = line.rstrip('\r\n')
            if skipping:
                if s == '  }' or s == '  },':
                    idx += 1
                    skipping = False
                continue
            if not buf:
                if s.startswith('  {'):
                    buf.append(s)
                    size = len(s)
                continue
            buf.append(s)
            size += len(s) + 1
            if size > max_obj:
                skipping = True
                buf = []
                size = 0
                continue
            if s == '  }' or s == '  },':
                idx += 1
                text = '\n'.join(buf)
                if text.endswith(','):
                    text = text[:-1]
                try:
                    yield idx, json.loads(text)
                except ValueError as e:
                    sys.stderr.write('skip obj %d in %s: %s\n' % (idx, path, e))
                buf = []
                size = 0


def ref_index(ref):
    """{'ObjectPath': 'OPP/.../CHJ.123'} -> 123"""
    if not ref:
        return None
    try:
        return int(ref['ObjectPath'].rsplit('.', 1)[1])
    except (KeyError, ValueError, AttributeError):
        return None


def yaw_rotate(x, y, yaw_deg):
    if not yaw_deg:
        return x, y
    r = math.radians(yaw_deg)
    c, s = math.cos(r), math.sin(r)
    return x * c - y * s, x * s + y * c


def vec(d, default=0.0):
    if not d:
        return default, default, default
    return d.get('X', default), d.get('Y', default), d.get('Z', default)


# ---------------------------------------------------------------- 几何


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def poly_area(poly):
    if len(poly) < 3:
        return 0.0
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(a) * 0.5


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xx = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xx > x:
                inside = not inside
    return inside


def _seg_t(p1, p2, q1, q2):
    """p 线段与 q 线段的交点参数 t(0..1), 无交点返回 None。"""
    d1x, d1y = p2[0] - p1[0], p2[1] - p1[1]
    d2x, d2y = q2[0] - q1[0], q2[1] - q1[1]
    den = d1x * d2y - d1y * d2x
    if abs(den) < 1e-9:
        return None
    t = ((q1[0] - p1[0]) * d2y - (q1[1] - p1[1]) * d2x) / den
    u = ((q1[0] - p1[0]) * d1y - (q1[1] - p1[1]) * d1x) / den
    if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
        return min(1.0, max(0.0, t))
    return None


def _dedupe_ring(h):
    out = []
    for p in h:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-6:
            out.append(p)
    if len(out) > 1 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-6:
        out.pop()
    return out


def merge_hulls(hulls, inset=3.0):
    """把同一房间的多个碰撞块(3D 凸包在 2D 投影下会重叠)合并成一条外轮廓。

    做法: 先去重/去掉被完全包含的小块, 再把边按交点切分, 去掉落在别的块内部的
    子段和正反重合的共享边, 最后首尾相接成环。失败时退回原始 hull 列表。
    """
    hulls = [_dedupe_ring(h) for h in hulls if len(h) >= 3]
    hulls = [h for h in hulls if len(h) >= 3]
    if len(hulls) <= 1:
        return hulls

    # 被别的块完全包住的块直接丢掉(同一房间的碰撞块常有多层重叠)
    kept_hulls = []
    for i, h in enumerate(hulls):
        cx = sum(p[0] for p in h) / len(h)
        cy = sum(p[1] for p in h) / len(h)
        inside_other = any(
            j != i and poly_area(g) > poly_area(h) and point_in_poly(cx, cy, g)
            for j, g in enumerate(hulls))
        if not inside_other:
            kept_hulls.append(h)
    hulls = kept_hulls or hulls

    parts = []
    for hi, h in enumerate(hulls):
        n = len(h)
        cx = sum(p[0] for p in h) / n
        cy = sum(p[1] for p in h) / n
        for i in range(n):
            a, b = h[i], h[(i + 1) % n]
            if math.hypot(b[0] - a[0], b[1] - a[1]) < 1e-6:
                continue
            ts = {0.0, 1.0}
            for hj, g in enumerate(hulls):
                if hj == hi:
                    continue
                m = len(g)
                for j in range(m):
                    t = _seg_t(a, b, g[j], g[(j + 1) % m])
                    if t is not None:
                        ts.add(round(t, 6))
            ts = sorted(ts)
            for t0, t1 in zip(ts, ts[1:]):
                if t1 - t0 < 1e-6:
                    continue
                p0 = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
                p1 = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
                mx, my = (p0[0] + p1[0]) / 2.0, (p0[1] + p1[1]) / 2.0
                vx, vy = cx - mx, cy - my
                L = math.hypot(vx, vy) or 1.0
                qx, qy = mx + vx / L * inset, my + vy / L * inset
                hidden = False
                for hj, g in enumerate(hulls):
                    if hj == hi:
                        continue
                    if point_in_poly(qx, qy, g):
                        hidden = True
                        break
                if not hidden:
                    parts.append((p0, p1))

    def key(p):
        return (round(p[0], 1), round(p[1], 1))

    # 去掉正反重合的共享边
    seen = {}
    for p0, p1 in parts:
        seen.setdefault((key(p0), key(p1)), []).append((p0, p1))
    kept = []
    for (k0, k1), segs in seen.items():
        if (k1, k0) in seen:
            continue
        kept.extend(segs)
    if not kept:
        return hulls

    # 首尾相接成环
    nxt = {}
    for p0, p1 in kept:
        nxt.setdefault(key(p0), []).append((p0, p1))
    rings, used = [], set()
    for p0, p1 in kept:
        if (key(p0), key(p1)) in used:
            continue
        ring, cur, ok = [p0], p1, True
        used.add((key(p0), key(p1)))
        while True:
            if key(cur) == key(ring[0]):
                break
            cand = [s for s in nxt.get(key(cur), []) if (key(s[0]), key(s[1])) not in used]
            if not cand:
                ok = False
                break
            s = cand[0]
            used.add((key(s[0]), key(s[1])))
            ring.append(s[0])
            cur = s[1]
            if len(ring) > 400:
                ok = False
                break
        if ok and len(ring) >= 3:
            rings.append(ring)

    if not rings:
        return hulls
    rings.sort(key=poly_area, reverse=True)
    if sum(poly_area(r) for r in rings) < 0.6 * sum(poly_area(h) for h in hulls):
        return hulls
    # 只保留外轮廓(内环是碰撞块之间的缝隙, 当成洞画会多出一圈线)
    return rings[:1]


# ---------------------------------------------------------------- 类型规则

# Shutter(卷帘/闸门) 也是门; DoorWindow 这类"带窗的门"是门不是窗, 所以不再按 Window 排除
DOOR_RE = re.compile(r'Door|Gate|Shutter', re.I)
DOOR_SKIP = re.compile(r'Component|Light|Plane|Sign|Destroyed|Broken', re.I)

# 关键物品分类: (key, 正则, 显示名)
ITEM_RULES = [
    ('clue_keypad', re.compile(r'ClueGame_Symbol_Keypad', re.I), '推理输入'),
    ('clue_confirm', re.compile(r'SingleCodeActivator_Button', re.I), '答案确认'),
    ('clue_killer', re.compile(r'ClueMannequin|ClueMissingBodyPart', re.I), '凶手线索'),
    ('clue_weapon', re.compile(r'ClueWeapon_BP', re.I), '凶器线索'),
    ('clue_room', re.compile(r'ClueRoom_BP', re.I), '犯罪现场候选'),
    ('detector', re.compile(r'BlacklightDetectorWide_QuestItemSpawn', re.I), '黑光探测器'),
    ('gas_valve', re.compile(r'TF_Gas_ValvePanel|TF_ValvePanel', re.I), '燃气阀门'),
    ('pump_display', re.compile(r'Pump_Display_BP', re.I), '分区泵表'),
    ('gas_window', re.compile(r'TFS_GasWindow', re.I), '气体观察窗'),
    ('projection_symbol', re.compile(r'ProjectionSymbol_BP', re.I), '投影符号'),
    ('clue_screen', re.compile(r'ProjectionClue_NarrativeScreen', re.I), '符号屏幕（线索）'),
    ('code_tv', re.compile(r'Projection_TvChannel_BP', re.I), '符号电视'),
    ('letter_tv', re.compile(r'^tvChannel_BP', re.I), '字母屏'),
    ('passcode_pad', re.compile(r'PasscodeTriggerable_Base', re.I), '密码键盘'),
    ('decoder', re.compile(r'Decoder_DeviceItem_Spawner', re.I), '解码器生成点'),
    ('loot', re.compile(r'ValuablesBox|ValuablesSafeDrop', re.I), '赃物/交付点'),
    ('objective', re.compile(r'ObjectiveCoord|ObjCoord|Timed_Generator|Decoder_Device|MannequinVan', re.I), '目标点'),
    ('frequency', re.compile(r'FrequencyMatchPanel', re.I), '调频面板'),
    ('switchboard', re.compile(r'SwitchesBoard_Base', re.I), '配电盘（目标）'),
    ('clue_code', re.compile(r'Clue_BlackLightable', re.I), '黑光码候选'),
    ('clue_tv', re.compile(r'Clue(Room|Weapon)\w*_TvChannel|^tvChannel_BP', re.I), '线索电视'),
    ('mannequin', re.compile(r'ManneqinSetup', re.I), '人体模型候选'),
    ('button', re.compile(r'Orp_Movable_Button|Regroup_Button|StageEnd_Button', re.I), '机关按钮'),
    ('evidence', re.compile(r'Evidence|HeadEvidence', re.I), '证据/头颅'),
    ('document', re.compile(r'Document', re.I), '文档'),
    ('health', re.compile(r'Medkit|Pharmacy|Antidote|SP-Health', re.I), '药品/血包'),
    ('tool', re.compile(r'Lockpick|ToolBox|ToolCabinet|Workshop|Battery', re.I), '工具/钥匙'),
    ('hide', re.compile(r'Hidespot|PhoneBooth|Locker', re.I), '藏身点'),
    ('container', re.compile(r'^Cont-|Cabinet|Basket|EvidenceBox', re.I), '容器'),
]
ITEM_SKIP = re.compile(
    r'Thrown|-Throw-|Component|Previs|Decal|Light|Sound|Instanced|InteractionPanel|'
    r'Manager|Spawner|SpawnLocation|Volume|Trap|Marker|NavLink|Sign', re.I
)
# 名字里带 Light/Spawn 等跳过词但确实是任务点的类型, 先于 ITEM_SKIP 判定
ITEM_ALLOW = re.compile(
    r'BlacklightDetectorWide_QuestItemSpawn|Clue_BlackLightable|SwitchesBoard_Base|'
    r'Orp_Movable_Button|^tvChannel_BP|Decoder_DeviceItem_Spawner', re.I
)

KEEP_COMPONENT_TYPES = {
    'SceneComponent', 'StaticMeshComponent', 'BoxComponent', 'CapsuleComponent',
    'ArrowComponent', 'BrushComponent', 'ChildActorComponent', 'BillboardComponent',
    # PrefabActor 的根组件；ORI 等地图把人偶/道具挂在 Prefab 上，
    # 不收这个类型的话这些 actor 的坐标会全算成 (0,0,0)
    'PrefabComponent',
}
COMP_TRIM_KEYS = ('RelativeLocation', 'RelativeRotation', 'AttachParent')
# 楼梯标记只留定位/宽度/链指针; Prev/Next 用来把一串标记接成一道楼梯
STAIR_TRIM_KEYS = ('RootComponent', 'StairsWidth', 'Prev', 'Next')


def classify_item(tname):
    for key, rx, label in ITEM_RULES:
        if rx.search(tname):
            return key, label
    return None


def is_door_type(tname):
    return bool(DOOR_RE.search(tname)) and tname.endswith('_C') and not DOOR_SKIP.search(tname)


def is_item_type(tname):
    if not tname.endswith('_C'):
        return False
    if ITEM_ALLOW.search(tname):
        return True
    if ITEM_SKIP.search(tname):
        return False
    return classify_item(tname) is not None


# ---------------------------------------------------------------- 提取


class MapExtractor:
    def __init__(self, folder, mode='local', verbose=False, only=None):
        self.folder = folder
        self.mode = mode
        self.verbose = verbose
        self.only = re.compile(only, re.I) if only else None
        self.per_file = {}     # fn -> {idx: obj}
        self.room_objs = []
        self.door_objs = []
        self.item_objs = []
        self.spawn_objs = []
        self.stair_objs = []
        self.scanned = []

    def log(self, *a):
        if self.verbose:
            print(*a)

    # -- 读取
    def scan(self):
        for fn in sorted(os.listdir(self.folder)):
            if not fn.endswith('.json') or 'BuiltData' in fn or 'VisibilityData' in fn:
                continue
            if self.only and not self.only.search(fn):
                continue
            path = os.path.join(self.folder, fn)
            keep = {}
            n = 0
            for idx, obj in iter_objects(path):
                t = obj.get('Type') or ''
                if t == 'RBRoom':
                    self.room_objs.append((fn, idx, obj))
                elif is_door_type(t):
                    self.door_objs.append((fn, idx, obj))
                elif is_item_type(t):
                    self.item_objs.append((fn, idx, obj))
                elif t == 'PlayerStart':
                    self.spawn_objs.append((fn, idx, obj))
                elif t == 'RBStairsMarker':
                    self.stair_objs.append((fn, idx, obj))
                    p = obj.get('Properties') or {}
                    obj = {
                        'Type': t,
                        'Name': obj.get('Name'),
                        'Outer': obj.get('Outer'),
                        'Properties': {k: p[k] for k in STAIR_TRIM_KEYS if k in p},
                    }
                elif t in ('BodySetup', 'Model', 'BrushComponent'):
                    pass
                elif t in KEEP_COMPONENT_TYPES:
                    p = obj.get('Properties') or {}
                    obj = {
                        'Type': t,
                        'Outer': obj.get('Outer'),
                        'Properties': {k: p[k] for k in COMP_TRIM_KEYS if k in p},
                    }
                else:
                    continue
                keep[idx] = obj
                n += 1
            self.per_file[fn] = keep
            self.scanned.append(fn)
            self.log('  %-45s keep %d' % (fn, n))

    def get(self, fn, ref):
        i = ref_index(ref)
        if i is None:
            return None
        return self.per_file.get(fn, {}).get(i)

    # -- 变换
    def comp_transform(self, fn, ref, depth=0):
        comp = self.get(fn, ref)
        if comp is None or comp.get('Type') not in KEEP_COMPONENT_TYPES:
            return (0.0, 0.0, 0.0), 0.0
        p = comp.get('Properties') or {}
        loc = vec(p.get('RelativeLocation'))
        yaw = (p.get('RelativeRotation') or {}).get('Yaw', 0.0) or 0.0
        parent = p.get('AttachParent')
        if parent and depth < 6:
            ploc, pyaw = self.comp_transform(fn, parent, depth + 1)
            dx, dy = yaw_rotate(loc[0], loc[1], pyaw)
            loc = (ploc[0] + dx, ploc[1] + dy, ploc[2] + loc[2])
            yaw += pyaw
        return loc, yaw

    def to_world(self, loc, yaw, x, y, z):
        if self.mode == 'raw':
            return x, y, z
        dx, dy = yaw_rotate(x, y, yaw)
        return loc[0] + dx, loc[1] + dy, loc[2] + z

    # -- 房间
    def extract_rooms(self):
        rooms = []
        for fn, idx, obj in self.room_objs:
            p = obj.get('Properties') or {}
            loc, yaw = self.comp_transform(fn, p.get('RootComponent'))
            hulls, zs = [], []
            bc = self.get(fn, p.get('BrushComponent'))
            bs = self.get(fn, (bc or {}).get('Properties', {}).get('BrushBodySetup'))
            elems = ((bs or {}).get('Properties') or {}).get('AggGeom') or {}
            for ce in elems.get('ConvexElems') or []:
                pts = []
                for v in ce.get('VertexData') or []:
                    x, y, z = vec(v)
                    wx, wy, wz = self.to_world(loc, yaw, x, y, z)
                    pts.append((wx, wy, wz))
                zs.extend(q[2] for q in pts)
                hull = convex_hull([(round(q[0], 2), round(q[1], 2)) for q in pts])
                if len(hull) >= 3 and poly_area(hull) > 2000:
                    hulls.append(hull)
            if not hulls:
                mo = self.get(fn, p.get('Brush'))
                if mo:
                    pts = []
                    for v in (mo.get('Points') or [])[:-1]:
                        x, y, z = vec(v)
                        wx, wy, wz = self.to_world(loc, yaw, x, y, z)
                        pts.append((wx, wy, wz))
                    zs.extend(q[2] for q in pts)
                    hull = convex_hull([(round(q[0], 2), round(q[1], 2)) for q in pts])
                    if len(hull) >= 3:
                        hulls.append(hull)
            if not hulls:
                self.log('  ! no geometry for %s' % obj.get('Name'))
                continue
            if len(hulls) > 1:
                hulls = merge_hulls(hulls)
            name = re.sub(r'^RBRoom_?', '', obj.get('Name') or '').replace('_', ' ').strip()
            if re.fullmatch(r'[\d\s]+', name or ''):
                name = 'Room ' + (name or '?').replace(' ', '-')
            allpts = [q for h in hulls for q in h]
            rooms.append({
                'name': name,
                'raw_name': obj.get('Name'),
                'file': fn,
                'hulls': hulls,
                'zmin': round(min(zs), 1),
                'zmax': round(max(zs), 1),
                'cx': round(sum(q[0] for q in allpts) / len(allpts), 1),
                'cy': round(sum(q[1] for q in allpts) / len(allpts), 1),
                'area': round(sum(poly_area(h) for h in hulls), 1),
                'room_size': p.get('RoomSize'),
            })
        return rooms

    # -- 门 / 物品
    def actor_point(self, fn, obj):
        p = obj.get('Properties') or {}
        loc, yaw = self.comp_transform(fn, p.get('RootComponent'))
        return loc, yaw

    def extract_doors(self):
        doors = []
        for fn, idx, obj in self.door_objs:
            loc, yaw = self.actor_point(fn, obj)
            doors.append({
                'name': obj.get('Name'), 'type': obj.get('Type'), 'file': fn,
                'x': round(loc[0], 1), 'y': round(loc[1], 1), 'z': round(loc[2], 1),
                'yaw': round(yaw, 2),
            })
        return doors

    def extract_spawns(self):
        """玩家出生点(PlayerStart): 位置 + 朝向, 用于定视图朝向。"""
        out = []
        for fn, idx, obj in self.spawn_objs:
            loc, yaw = self.actor_point(fn, obj)
            out.append({
                'name': obj.get('Name'), 'file': fn,
                'x': round(loc[0], 1), 'y': round(loc[1], 1), 'z': round(loc[2], 1),
                'yaw': round(yaw, 2),
            })
        return out

    # -- 楼梯
    def extract_stairs(self):
        """RBStairsMarker -> 一道楼梯(run): 低端、高端、踏步宽。

        导出里一个标记对就是一级踏步(高差 16.7 / 33.3 ...), 一道楼梯是几十个
        这样的踏步沿同一方向接力; 按端点邻近把它们串成 run, 取最低点与最高点
        作为楼梯的两端, 宽度取整体最大值(扶手到扶手)。
        """
        steps = []
        seen_files = set()
        for fn, _idx, _obj in self.stair_objs:
            if fn in seen_files:                # 每个文件只处理一次
                continue
            seen_files.add(fn)
            info = {}
            for idx, node in self.per_file.get(fn, {}).items():
                if node.get('Type') != 'RBStairsMarker':
                    continue
                p = node.get('Properties') or {}
                loc, _yaw = self.comp_transform(fn, p.get('RootComponent'))
                info[idx] = {
                    'name': node.get('Name') or '',
                    'p': loc,
                    'w': float(p.get('StairsWidth') or 0.0),
                    'prev': ref_index(p.get('Prev')),
                    'next': ref_index(p.get('Next')),
                }
            for head, node in info.items():
                if node['prev'] in info:
                    continue                    # 不是链头
                chain, cur, seen = [], head, set()
                while cur in info and cur not in seen:
                    seen.add(cur)
                    chain.append(cur)
                    cur = info[cur]['next']
                if len(chain) < 2:
                    continue
                pts = [info[i]['p'] for i in chain]
                lo = min(pts, key=lambda q: q[2])
                hi = max(pts, key=lambda q: q[2])
                if hi[2] - lo[2] < 1.0:
                    continue
                widths = [info[i]['w'] for i in chain if info[i]['w'] > 0]
                steps.append({
                    'name': info[head]['name'], 'file': fn,
                    'w': statistics.median(widths) if widths else 0.0,
                    'a': [lo[0], lo[1], lo[2]],
                    'b': [hi[0], hi[1], hi[2]],
                })
        return group_stair_runs(steps)

    def extract_items(self):
        items = []
        for fn, idx, obj in self.item_objs:
            cat = classify_item(obj.get('Type') or '')
            loc, yaw = self.actor_point(fn, obj)
            items.append({
                'name': obj.get('Name'), 'type': obj.get('Type'), 'file': fn,
                'cat': cat[0], 'cat_label': cat[1],
                'x': round(loc[0], 1), 'y': round(loc[1], 1), 'z': round(loc[2], 1),
                'yaw': round(yaw, 2),
            })
        return items


TRIAL_TAGS = [('MT01', 'MT01'), ('MT02', 'MT02'), ('MT03', 'MT03')]


def trial_of_file(fn):
    """按文件名判断点位/房间属于哪个关卡变体。

    法院: CHJ_LD_MT01_B00 -> MT01 ; 度假村: RE_LD_T10_B01 -> T10_B01 ;
    演播室: TelevisionStudio_LD_B03 -> B03 ; 其它 -> 通用
    """
    b = os.path.basename(fn or '')
    m = re.search(r'MT(\d+)', b)
    if m:
        return ['MT%02d' % int(m.group(1))]
    m = re.search(r'(T\d+_B\d{2})', b)
    if m:
        return [m.group(1)]
    m = re.search(r'_B(\d{2})', b)
    if m:
        return ['B' + m.group(1)]
    return ['通用']


ROOM_REF_RE = re.compile(r'RBRoom_?[A-Za-z0-9_]+')


def room_trial_tags(folder, raw_names):
    """房间被哪些关卡变体引用(引用=该关卡会用到这个房间)。"""
    import glob as _glob
    names = set(n for n in raw_names if n)
    res = {n: [] for n in raw_names}
    for path in _glob.glob(os.path.join(folder, '*.json')):
        base = os.path.basename(path)
        if '_BuiltData' in base:
            continue
        if not re.search(r'(_B\d{2}|T\d+_B|Shared)', base):
            continue
        tags = trial_of_file(base)
        txt = io.open(path, encoding='utf-8', errors='ignore').read()
        refs = set(ROOM_REF_RE.findall(txt)) & names
        if not refs:
            continue
        for n in refs:
            res[n].extend(tags)
    for n in res:
        res[n] = sorted(set(res[n]))
    return res


def main_parse(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('folder')
    ap.add_argument('-o', '--out', default=None)
    ap.add_argument('--mode', default='local', choices=['local', 'raw'])
    ap.add_argument('--only', default=None, help='只扫描文件名匹配该正则的 json')
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args(argv)

    ex = MapExtractor(args.folder, mode=args.mode, verbose=args.verbose, only=args.only)
    ex.scan()
    rooms = ex.extract_rooms()
    doors = ex.extract_doors()
    items = ex.extract_items()
    spawns = ex.extract_spawns()

    # 标上"属于哪个试炼": 房间看 B00 引用, 点位看所在文件
    rtags = room_trial_tags(args.folder, [r['raw_name'] for r in rooms])
    for r in rooms:
        r['trials'] = rtags.get(r['raw_name']) or []
    for it in items:
        it['trials'] = trial_of_file(it['file'])
    for d in doors:
        d['trials'] = trial_of_file(d['file'])

    data = {'folder': args.folder, 'mode': args.mode,
            'rooms': rooms, 'doors': doors, 'items': items, 'spawns': spawns}
    out = args.out or os.path.join(args.folder, 'plan.json')
    parent = os.path.dirname(out)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with io.open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print('rooms=%d doors=%d items=%d spawns=%d -> %s'
          % (len(rooms), len(doors), len(items), len(spawns), out))

# ---------------------------------------------------------------------------
# 门 / 走廊 分类（原渲染段里的通用工具，提取时也要用）
# ---------------------------------------------------------------------------
# 走廊/通道统一底色, 普通房间用色相均匀分布的浅色
CORRIDOR_FILL = '#dfe6ee'
CORRIDOR_RE = re.compile(r'corridor|hallway|passage|access|path\b|walkway|catwalk|'
                         r'stair|ramp|bridge|tunnel|cooridor', re.I)

CONNECTOR_COLOR = '#0f766e'
SPAWN_COLOR = '#059669'
EXIT_COLOR = '#0d9488'

CONNECTOR_RE = re.compile(r'stair|lift|elevator|ramp|escalator', re.I)

# 门类型: (中文名, 描边色, 填充色, 门洞宽度uu) —— 图例里名字尽量短, 省横向空间
DOOR_CATS = collections.OrderedDict([
    ('normal', ('普通门', '#b45309', '#fbbf24', 230)),
    ('rolling', ('卷帘/闸门', '#1d4ed8', '#93c5fd', 320)),
    ('sliding', ('滑动门', '#0e7490', '#67e8f9', 260)),
    ('closet', ('柜门', '#6d28d9', '#d8b4fe', 170)),
    ('access', ('权限门', '#15803d', '#86efac', 230)),
    ('backdrop', ('装饰门', '#475569', '#cbd5e1', 210)),
    ('other', ('其他门', '#374151', '#9ca3af', 220)),
])

DOOR_RULES = [
    (re.compile(r'monstercloset', re.I), 'closet'),
    (re.compile(r'rolling ?door|rollingdoor|shutter', re.I), 'rolling'),
    (re.compile(r'sliding', re.I), 'sliding'),
    (re.compile(r'employeedoor|sasdoor', re.I), 'access'),
    (re.compile(r'backgrounddoor', re.I), 'backdrop'),
    (re.compile(r'\bdoor|doorwood|ch_?door', re.I), 'normal'),
]


def door_cat(dtype):
    for rx, key in DOOR_RULES:
        if rx.search(dtype or ''):
            return key
    return 'other'


def door_width(dtype, base):
    """卷帘门按 2M/3M 调整门洞宽度。"""
    m = re.search(r'(\d)M\b', dtype or '', re.I)
    if m:
        return float(m.group(1)) * 100.0
    return base

def is_corridor(name):
    return bool(CORRIDOR_RE.search(name or ''))


def is_connector(name):
    return bool(CONNECTOR_RE.search(name))


# 楼梯段接力的判定: 上一段顶端与下一段底端在 XY 上够近、z 上连续
STAIR_LINK_XY = 260.0
STAIR_LINK_Z = 120.0


def group_stair_runs(steps):
    """把首尾相接的踏步并成一道楼梯(run)。

    导出里一个标记对只覆盖一级台阶, 一道楼梯是几十级沿同一方向接力:
    两级的端点 XY 够近、z 上连续, 就算同一道楼梯。
    返回 [{id, a: 低端, b: 高端, w, zmin, zmax, steps}]。
    """
    n = len(steps)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    ends = [((s['a'][0], s['a'][1], s['a'][2]), (s['b'][0], s['b'][1], s['b'][2]))
            for s in steps]
    for i in range(n):
        for j in range(i + 1, n):
            linked = False
            for pi in ends[i]:
                for pj in ends[j]:
                    if abs(pi[2] - pj[2]) > STAIR_LINK_Z:
                        continue
                    if math.hypot(pi[0] - pj[0], pi[1] - pj[1]) > STAIR_LINK_XY:
                        continue
                    linked = True
                    break
                if linked:
                    break
            if linked:
                union(i, j)

    buckets = collections.OrderedDict()
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)

    runs = []
    for k, members in enumerate(buckets.values()):
        pts = [p for i in members for p in (steps[i]['a'], steps[i]['b'])]
        lo = min(pts, key=lambda q: q[2])
        hi = max(pts, key=lambda q: q[2])
        widths = [steps[i]['w'] for i in members if steps[i]['w'] > 0]
        runs.append({
            'id': k,
            'file': steps[members[0]]['file'],
            'name': steps[members[0]]['name'],
            'a': [round(lo[0], 1), round(lo[1], 1), round(lo[2], 1)],
            'b': [round(hi[0], 1), round(hi[1], 1), round(hi[2], 1)],
            'w': round(max(widths), 1) if widths else 200.0,
            'zmin': round(lo[2], 1),
            'zmax': round(hi[2], 1),
            'steps': len(members),
        })
    return runs


def hull_dist(x, y, h):
    """点到多边形轮廓的最短距离（点位归属房间时的兜底判定）。"""
    best = 1e18
    n = len(h)
    for i in range(n):
        x1, y1 = h[i]
        x2, y2 = h[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / L2))
        d = math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
        if d < best:
            best = d
    return best
