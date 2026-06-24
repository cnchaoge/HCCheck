import os

"""运管站货车审验 - 配置常量集中地

所有可能因为站点改版而变化的硬编码都集中在这里,改一处生效全局。
业务术语的同义变体(打印告知单的多种写法等)放在使用方局部列表里更直观,不在此处。
"""
import re

# ========= 运行控制 =========
DEBUG = False            # True: 每步按 y 才走
SINGLE_RUN = False       # True: 跑完一辆就停
MAX_CARS = 2             # 最多跑几辆车 (0=无限)
MAX_FAIL = 3             # 同一辆车失败 N 次进黑名单
HEADLESS = False         # True: 无头模式(不推荐,看不到弹窗)
SLOW = 0.5               # pa() 默认 sleep 秒

# ========= 操作间隔常量（pa() 参数统一名，集中可调） =========
PA_AFTER_CLICK = 2       # 点击菜单/按钮后等待（最常用）
PA_AFTER_MENU = 1        # 菜单点击后等待
PA_AFTER_QUERY = 1.5     # 查询后等待
PA_AFTER_SUBMIT = 2      # 提交后等待
PA_AFTER_POPUP = 3       # 弹窗打开后等待
PA_AFTER_NAV = 3         # 页面导航后等待
PA_SHORT = 0.5           # 短间隔
PA_VERY_SHORT = 0.15     # 输入框内操作
PA_LONG = 5              # 长间隔

# ========= 智能等待常量（wait_until / wait_until_not 默认值） =========
WAIT_UNTIL_TIMEOUT = 10.0   # 默认超时秒数
WAIT_UNTIL_POLL = 0.3       # 轮询间隔秒数

# ========= 停止控制（GUI ↔ 主循环通信） =========
# GUI 按"停止"时：
#   CURRENT_PLATE 非空 → 设 SINGLE_RUN=True → 当前车跑完后温和退出
#   CURRENT_PLATE 空   → 设 FORCE_STOP=True   → 主循环下一圈立即 break
CURRENT_PLATE = ""       # 当前正在处理的车牌（空 = 空闲）
FORCE_STOP = False       # 强制停止标志（True 时主循环下一圈立即 break）

# ========= 状态栏同步（GUI 启动时赋值） =========
# run.py 调 push_status() 推状态消息到这个 queue
# GUI 主线程消费后更新 plate_var / step_var / done_var
# 传 None 表示该项不更新
STATUS_QUEUE = None

# ========= 站点 =========
URL = "https://221.195.18.1:8181/yg/loginAction.do"

# ========= 登录配置 =========
LOGIN_USERNAME = ""   # 留空则手动输入
LOGIN_PASSWORD = ""   # 留空则手动输入
LOGIN_AUTO_SUBMIT = True  # True: 填完自动点登录; False: 等人工确认
SCHEDULE = ""  # Cron 表达式, 如 "0 8 * * *" = 每天8点; 留空=不启用定时

# ========= 系统设置（可在 GUI 调整） =========
_gui_cfg_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".user_config.json")
if os.path.exists(_gui_cfg_file):
    import json
    try:
        _gui_cfg = json.load(open(_gui_cfg_file, "r", encoding="utf-8"))
        LOGIN_USERNAME = _gui_cfg.get("username", LOGIN_USERNAME)
        LOGIN_PASSWORD = _gui_cfg.get("password", LOGIN_PASSWORD)
        LOGIN_AUTO_SUBMIT = _gui_cfg.get("auto_login", LOGIN_AUTO_SUBMIT)
        HEADLESS = _gui_cfg.get("headless", HEADLESS)
        SLOW = _gui_cfg.get("slow", SLOW)
        MAX_FAIL = _gui_cfg.get("max_fail", MAX_FAIL)
        MAX_CARS = _gui_cfg.get("max_cars", MAX_CARS)
        SCHEDULE = _gui_cfg.get("schedule", SCHEDULE)
    except:
        pass


# ========= 车牌识别(31 省简称) =========
PLATE_RE = re.compile(
    r'^[\u4eac\u6daf\u6caa\u6e1d\u5180\u8c6b\u4e91\u8fdb\u9ed1\u6e58'
    r'\u7696\u9c81\u65b0\u82cf\u6d59\u8d63\u9102\u6842\u7518\u664b'
    r'\u8499\u9655\u5409\u95fd\u8d35\u7ca4\u9752\u85cf\u5ddd\u5b81\u743c]'
    r'[A-Z][A-Z0-9]{4,6}(挂)?$'
)

# ========= 步骤常量(内部状态机用,英文 token) =========
STEP_VEHICLE_CHECK = "vehicle_check"          # 车辆检测
STEP_TECH_REVIEW = "tech_review"              # 技术岗位审核
STEP_BUSINESS_REVIEW = "business_review"      # 业务岗位审核
STEP_VEHICLE_ANNUAL = "vehicle_annual"        # 车辆年审
STEP_ARCHIVE = "archive"                      # 归档

# ========= 节点显示名(UI 文字,用于识别当前步骤) =========
NODE_VEHICLE_CHECK = "车辆检测"
NODE_TECH_REVIEW = "技术岗位审核"
NODE_BUSINESS_REVIEW = "业务岗位审核"
NODE_VEHICLE_ANNUAL = "车辆年审"
NODE_ARCHIVE = "归档"

# 快速检测关键字(用于 _detect_popup_step 特征元素识别)
DETECT_YEAR_CHECK = "年度审验"   # 出现即视为"车辆年审"步骤
DETECT_PRINT = "打印"            # 出现即视为"技术岗位审核"步骤

# 年度审验的 3 种写法(带挂流程的"车辆年审1"和 p4 都要用,放 config 共享)
YEAR_CHECK_TEXTS = ["年度审验", "年度審驗", "年度检验"]

# ========= 菜单名(导航) =========
MENU_WORKBENCH = "工作台"
MENU_NORMAL_REVIEW = "普货审验"
MENU_FOR_NORMAL = "道路货物运输车辆审验"
MENU_FOR_TRAILER = "挂车及其他车辆审验(普货)"
MENU_FREIGHT_MANAGE = "货运管理"  # 导航树的父节点，需要先点击展开

# 流程标识(工作台行内文字)
FLOW_TRAILER_MARKER = "挂车"  # 带挂流程的识别字
FLOW_NORMAL_MARKER = "普货"   # 不带挂流程的识别字

# ========= 弹窗动作类型(选下一处理人时选) =========
ACTION_SUBMIT_TECH_REVIEW = "提交业务岗位审核"
ACTION_SUBMIT_VEHICLE_ANNUAL = "提交车辆年审"
ACTION_SUBMIT_ARCHIVE = "提交归档"
ACTION_SUBMIT_YEAR_CHECK = "提交年审"  # 带挂流程专用(车辆年审1)

# ========= 弹窗分类(选处理人时选) =========
CATEGORY_ROLE = "角色"
CATEGORY_INITIATOR = "发起人"

# ========= Frame / iframe 选择器 =========
SELECTOR_FRAME_CONTENTS = "#contents"
SELECTOR_FRAME_MAIN_KEF = "#main_kef"
SELECTOR_FRAME_WORKFLOW_MAIN = "frame[name='_workflow_main']"
SELECTOR_IFRAME_SUBMIT_DIAG = "iframe[name='submitDiag']"
SELECTOR_IFRAME_IFRAME_CONTENT = "iframe[name='_Iframe_content']"
SELECTOR_IFRAME_SUBMIT_DIAGCL = "iframe[name='submitDiagcl']"
SELECTOR_FRAME_FIND_FRAME_KF = "frame[name='FindFrame_kf']"
SELECTOR_IFRAME_I_FRAME_USER = "iframe[name='iFrame_user']"
SELECTOR_TREE_EXPAND = "#webfx-tree-object-apollo-4-plus"

# 表格选择器（工作台 / 年审列表共用）
SELECTOR_TABLE = "table"
SELECTOR_TABLE_ROW = "table tbody tr"

# 年度审验链接选择器模板（填入变体文字）
# 示例: f"a:has-text('{config.YEAR_CHECK_TEXTS[0]}')"
SELECTOR_A_YEAR_CHECK = "a:has-text('{text}')"

# 导航树展开备选(系统偶尔换 ID)
NAV_TREE_SELECTORS = [
    "#webfx-tree-object-apollo-4-plus",
    "[id*='tree-object']",
    "[id*='apollo']",
    "a:has-text('货运管理')",
]

# ========= 按钮名 =========
BTN_SUBMIT = "提交"
BTN_COMPLETE = "完成"
BTN_START_TASK = "创建任务(R)"  # 启动任务按钮(带 R accesskey)
BTN_OK = "确定"
BTN_QUERY = "查询"
BTN_SELECT = "选择"
BTN_ADD = "+"
BTN_SELECT_ALL = "全选"
BTN_CLOSE = "关闭"

# ========= 表单/流程字段 =========
INPUT_LICENSE_PLATE = "input[name='licensePlateNO']"
SELECTOR_FLOW_ID = "#flowid"
FLOW_TYPE_ID = "b04917f4-037c-4665-9421-3d62e2d78122"  # 业务类型 ID(普货审验)
