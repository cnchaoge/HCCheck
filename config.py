import os

"""运管站货车审验 - 配置常量集中地

所有可能因为站点改版而变化的硬编码都集中在这里,改一处生效全局。
业务术语的同义变体(打印告知单的多种写法等)放在使用方局部列表里更直观,不在此处。

v1.2 数据目录变更:
- 新优先: HCCheck.exe 同目录的 data/ 子目录 (E:\\HCCheck\\data)
- 兜底:   %APPDATA%\\HCCheck (兼容旧版)
- 老数据自动迁移 + 备份到 .legacy_backup/<时间戳>/
"""
import re
import sys
import shutil
import time as _time


# 脚本所在目录 (开发模式 / 打包模式都准确)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_frozen() -> bool:
    """是否 PyInstaller 打包后运行"""
    return getattr(sys, "frozen", False)


def get_user_data_dir():
    """获取传统 APPDATA 目录路径（v1.2 兼容用，迁移老数据时定位来源）

    - Windows: %APPDATA%\\HCCheck
    - macOS:   ~/Library/Application Support/HCCheck
    - Linux:   $XDG_DATA_HOME/HCCheck 或 ~/.local/share/HCCheck

    注意: 不在这里 makedirs, 由 get_data_dir() 统一管理
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    return os.path.join(base, "HCCheck")


def _can_write_dir(path: str) -> bool:
    """检查目录是否可写（写测试文件验证真实权限）"""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except (OSError, PermissionError):
        return False


def get_data_dir() -> str:
    """获取数据目录（v1.2 新设计）

    优先级:
      1. PyInstaller 打包后: HCCheck.exe 所在目录 + /data (推荐,E:\\HCCheck\\data)
      2. Python 开发模式:    脚本所在目录 + /data
      3. 上面都失败 → 回退到 %APPDATA%/HCCheck (兼容旧版)

    Returns:
        数据目录绝对路径 (保证存在 + 可写)
    """
    if _is_frozen():
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = SCRIPT_DIR

    primary = os.path.join(base, "data")
    if _can_write_dir(primary):
        return primary

    fallback = get_user_data_dir()
    if _can_write_dir(fallback):
        return fallback

    # 实在不行就用 primary (makedirs 可能失败但不影响主流程)
    os.makedirs(primary, exist_ok=True)
    return primary


def migrate_legacy_data() -> dict:
    """从 %APPDATA%/HCCheck 迁移老数据到新 data 目录

    规则:
      - 旧文件存在 + 新文件不存在 → 复制过去 + 在新目录建 .legacy_backup/<时间戳>/ 留底
      - 新文件已存在 → 不动 (新数据是事实)
      - 旧文件保留不动 (用户可手动清理)

    Returns:
        {"migrated": [filenames], "backup_dir": path or None, "old_dir": path or None}
    """
    old_dir = get_user_data_dir()
    new_dir = get_data_dir()

    if not os.path.isdir(old_dir):
        return {"migrated": [], "backup_dir": None, "old_dir": None}

    old_files = ["user_config.json", "skip_plates.json", "hccheck.db"]
    backup_root = os.path.join(new_dir, ".legacy_backup")
    timestamp = _time.strftime("%Y%m%d_%H%M%S")
    backup_dir = os.path.join(backup_root, timestamp)

    # 先确认真的有可迁移的文件再创建 backup 目录
    has_old = any(os.path.exists(os.path.join(old_dir, f)) for f in old_files)
    if not has_old:
        return {"migrated": [], "backup_dir": None, "old_dir": old_dir}

    migrated = []
    try:
        os.makedirs(backup_dir, exist_ok=True)
    except Exception:
        return {"migrated": [], "backup_dir": None, "old_dir": old_dir}

    for fname in old_files:
        old_path = os.path.join(old_dir, fname)
        new_path = os.path.join(new_dir, fname)
        backup_path = os.path.join(backup_dir, fname)

        if not os.path.exists(old_path):
            continue
        if os.path.exists(new_path):
            # 新文件已存在, 不动 (新数据是事实)
            continue

        try:
            # 先备份, 再复制
            shutil.copy2(old_path, backup_path)
            shutil.copy2(old_path, new_path)
            migrated.append(fname)
        except Exception as e:
            if DEBUG:
                print(f"  ⚠️ 迁移 {fname} 失败: {e}")

    return {"migrated": migrated, "backup_dir": backup_dir, "old_dir": old_dir}


def _initialize_data_dir() -> dict:
    """启动时初始化 (创建目录 + 迁移老数据)

    在 import 时自动调用一次 (GUI 模式 / 无头模式 / 直接 import 都生效)
    """
    data_dir = get_data_dir()
    mig = migrate_legacy_data()

    # 打印迁移结果 (只打印真的有迁移的, 没迁移不刷屏)
    if mig["migrated"]:
        print(f"  📦 数据目录已就绪: {data_dir}")
        print(f"  📂 从旧目录迁移 {len(mig['migrated'])} 个文件: {', '.join(mig['migrated'])}")
        if mig["backup_dir"]:
            print(f"  💾 备份位置: {mig['backup_dir']}")
        if mig["old_dir"]:
            print(f"  ℹ️  旧目录未删除: {mig['old_dir']} (可手动清理)")
    else:
        print(f"  📁 数据目录: {data_dir}")

    return {"data_dir": data_dir, **mig}


# ========= 自动初始化 (import 时执行) =========
_init_result = _initialize_data_dir()
DATA_DIR = _init_result["data_dir"]
LEGACY_BACKUP_DIR = _init_result["backup_dir"]

# ========= 数据文件路径 (v1.2 起统一在 DATA_DIR) =========
# 用户配置文件路径
USER_CONFIG_FILE = os.path.join(DATA_DIR, "user_config.json")

# 黑名单车牌文件路径
SKIP_PLATES_FILE = os.path.join(DATA_DIR, "skip_plates.json")

# SQLite 处理结果数据库 (替代旧的 xlsx 累积)
DB_FILE = os.path.join(DATA_DIR, "hccheck.db")

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

# ========= GUI 配置类型校验 helper =========
def _load_bool(value, default):
    """JSON 加载后强转 bool。容错: 任何异常 fallback 默认值。
    接受: True/False, 0/1, "true"/"false"/"yes"/"no"/"on"/"off" 等"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off", ""):
            return False
    return default


def _load_int(value, default):
    """JSON 加载后强转 int。容错"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _load_float(value, default):
    """JSON 加载后强转 float。容错"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ========= 系统设置（可在 GUI 调整） =========
_gui_cfg_file = USER_CONFIG_FILE
if os.path.exists(_gui_cfg_file):
    import json
    try:
        _gui_cfg = json.load(open(_gui_cfg_file, "r", encoding="utf-8"))
        LOGIN_USERNAME = str(_gui_cfg.get("username", LOGIN_USERNAME) or "")
        LOGIN_PASSWORD = str(_gui_cfg.get("password", LOGIN_PASSWORD) or "")
        LOGIN_AUTO_SUBMIT = _load_bool(_gui_cfg.get("auto_login"), LOGIN_AUTO_SUBMIT)
        HEADLESS = _load_bool(_gui_cfg.get("headless"), HEADLESS)
        SLOW = _load_float(_gui_cfg.get("slow"), SLOW)
        MAX_FAIL = _load_int(_gui_cfg.get("max_fail"), MAX_FAIL)
        MAX_CARS = _load_int(_gui_cfg.get("max_cars"), MAX_CARS)
        SCHEDULE = str(_gui_cfg.get("schedule", SCHEDULE) or "")
    except Exception as e:
        if DEBUG:
            print(f"  ⚠️ 加载 user_config.json 失败, 使用默认值: {e}")


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
