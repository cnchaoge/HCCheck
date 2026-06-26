"""HCCheck - 运管站货车审验自动化 GUI 入口

用法: python gui.py
打包: python build.py → dist/HCCheck.exe
"""
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import sys
import os
import time
import queue
import json
import subprocess

# Windows 高分屏 DPI 适配（必须在创建窗口前设置）
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

# 确保能导入同目录模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import config
from run import main as run_main
import run as _run  # 用于访问 SKIP_PLATES / _load_skip_plates() / _save_skip_plates() / _add_to_skip_plates() / _remove_from_skip_plates()

# 用户配置文件路径（从 config 模块导入，位于用户数据目录，打包后保留）
CONFIG_FILE = config.USER_CONFIG_FILE


# ============================================================
# 工具函数
# ============================================================
def load_user_config():
    """加载本地保存的用户配置"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}


def save_user_config(cfg: dict):
    """保存用户配置到本地"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ 保存配置失败: {e}")


# ============================================================
# 日志重定向
# ============================================================
class TextRedirector:
    """将 stdout/stderr 重定向到 Tkinter 的 queue，由 GUI 线程安全消费"""

    def __init__(self, queue: queue.Queue, orig):
        self.queue = queue
        self.orig = orig

    def write(self, text):
        if text:
            self.queue.put(text)
        if self.orig:
            self.orig.write(text)

    def flush(self):
        if self.orig:
            self.orig.flush()


# ============================================================
# 主窗口
# ============================================================
class App(tk.Tk):
    VERSION = "v1.1.0"
    APP_NAME = "HCCheck"

    def __init__(self):
        super().__init__()
        self.title(f"HCCheck {self.VERSION} — 运管站货车审验自动化工具")
        self.geometry("580x600")
        self.minsize(500, 520)

        # 自动居中
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        # 加载保存的配置
        self._saved_cfg = load_user_config()

        # 状态变量
        self.running = False
        self.worker_thread: threading.Thread | None = None
        self.log_queue: queue.Queue = queue.Queue()
        # 状态栏同步队列（run.py push_status() 推消息，_consume_queues 消费）
        self.status_queue: queue.Queue = queue.Queue()
        config.STATUS_QUEUE = self.status_queue
        # 停止信号阶段：0=未触发, 1=温和停已发, 2=强制停已发
        # 5 秒内连点 2 次 = 温和停升级为强制停
        self._stop_phase = 0
        self._stop_phase_time = 0.0

        # 构建界面
        self._build_ui()

        # 启动日志消费循环
        self._consume_queues()

        # 窗口关闭处理
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # --------------------------------------------------------
    # UI 构建 — Notebook 标签页
    # --------------------------------------------------------
    def _build_ui(self):
        # ── 顶部: 标题 + 版本 ──
        header = ttk.Frame(self)
        header.pack(fill=tk.X, padx=12, pady=(10, 4))
        ttk.Label(header, text="🚛 HCCheck",
                  font=("Microsoft YaHei", 16, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text=self.VERSION,
                  font=("Microsoft YaHei", 9), foreground="gray").pack(side=tk.RIGHT)

        # ── Notebook 标签页 ──
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # 标签页1: 运行
        self.tab_run = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_run, text="  🚀 运行  ")
        self._build_tab_run(self.tab_run)

        # 标签页2: 黑名单
        self.tab_skip = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_skip, text="  🚫 黑名单  ")
        self._build_tab_skip(self.tab_skip)

        # 标签页3: 设置
        self.tab_settings = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(self.tab_settings, text="  ⚙ 设置  ")
        self._build_tab_settings(self.tab_settings)

        # ── 底部控制按钮（移到运行 tab） ──
        # self.btn_start / self.btn_stop 在 _build_tab_run 末尾创建

    # --------------------------------------------------------
    # 标签页: 运行
    # --------------------------------------------------------
    def _build_tab_run(self, parent):
        # ── 顶部工具栏 ──
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(toolbar, text="📊 运行状态",
                  font=("Microsoft YaHei", 12, "bold")).pack(side=tk.LEFT)

        # ── 状态区 ──
        status_frame = ttk.LabelFrame(parent, text="", padding=8)
        status_frame.pack(fill=tk.X, pady=(0, 6))

        row_status = ttk.Frame(status_frame)
        row_status.pack(fill=tk.X, pady=2)
        ttk.Label(row_status, text="当前车牌:").pack(side=tk.LEFT)
        self.plate_var = tk.StringVar(value="—")
        ttk.Label(row_status, textvariable=self.plate_var,
                  font=("Microsoft YaHei", 11, "bold"), foreground="#1a73e8").pack(side=tk.LEFT, padx=(4, 20))

        ttk.Label(row_status, text="当前步骤:").pack(side=tk.LEFT)
        self.step_var = tk.StringVar(value="—")
        ttk.Label(row_status, textvariable=self.step_var,
                  font=("Microsoft YaHei", 11, "bold"), foreground="#34a853").pack(side=tk.LEFT, padx=(4, 20))

        ttk.Label(row_status, text="已完成:").pack(side=tk.LEFT)
        self.done_var = tk.StringVar(value="0")
        ttk.Label(row_status, textvariable=self.done_var,
                  font=("Microsoft YaHei", 11, "bold")).pack(side=tk.LEFT, padx=(4, 4))
        ttk.Label(row_status, text="辆").pack(side=tk.LEFT)

        # ── 日志区 ──
        log_frame = ttk.LabelFrame(parent, text="📋 运行日志", padding=4)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("Consolas", 10),
            state=tk.DISABLED, height=18
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # 日志区按钮行
        log_btns = ttk.Frame(log_frame)
        log_btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(log_btns, text="🗑 清空日志", command=self._clear_log).pack(side=tk.LEFT)
        ttk.Button(log_btns, text="💾 导出日志", command=self._export_log).pack(side=tk.LEFT, padx=(4, 0))

        # ── 底部控制按钮（启动/停止/关于/设置） ──
        ctrl = ttk.Frame(parent)
        ctrl.pack(fill=tk.X, pady=(6, 0))

        self.btn_start = ttk.Button(ctrl, text="▶ 启动", command=self._start, width=14)
        self.btn_start.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_stop = ttk.Button(ctrl, text="⏹ 停止", command=self._stop, width=14, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 8))

        ttk.Button(ctrl, text="❓ 关于", command=self._about).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(ctrl, text="⚙ 设置",
                   command=lambda: self.notebook.select(self.tab_settings)).pack(side=tk.RIGHT)

    # --------------------------------------------------------
    # 标签页: 设置
    # --------------------------------------------------------
    def _build_tab_settings(self, parent):
        # 使设置页内容居中且宽度可控
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True)

        # ── 登录设置 ──
        login_frame = ttk.LabelFrame(container, text="🔑 登录设置", padding=12)
        login_frame.pack(fill=tk.X, pady=(0, 8))

        # 用户名
        row1 = ttk.Frame(login_frame)
        row1.pack(fill=tk.X, pady=3)
        ttk.Label(row1, text="登录账号:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.username_var = tk.StringVar(value=self._saved_cfg.get("username", config.LOGIN_USERNAME))
        ttk.Entry(row1, textvariable=self.username_var, width=28).pack(side=tk.LEFT, padx=(8, 0))

        # 密码
        row2 = ttk.Frame(login_frame)
        row2.pack(fill=tk.X, pady=3)
        ttk.Label(row2, text="登录密码:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.password_var = tk.StringVar(value=self._saved_cfg.get("password", config.LOGIN_PASSWORD))
        ttk.Entry(row2, textvariable=self.password_var, width=28, show="●").pack(side=tk.LEFT, padx=(8, 0))

        # 自动登录
        row3 = ttk.Frame(login_frame)
        row3.pack(fill=tk.X, pady=3)
        ttk.Label(row3, text="", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.auto_login_var = tk.BooleanVar(value=self._saved_cfg.get("auto_login", config.LOGIN_AUTO_SUBMIT))
        ttk.Checkbutton(row3, text="填完账号密码后自动点击登录按钮", variable=self.auto_login_var).pack(side=tk.LEFT, padx=(8, 0))

        # ── 运行设置 ──
        run_frame = ttk.LabelFrame(container, text="⚙ 运行设置", padding=12)
        run_frame.pack(fill=tk.X, pady=(0, 8))

        # 最大车辆数
        row4 = ttk.Frame(run_frame)
        row4.pack(fill=tk.X, pady=3)
        ttk.Label(row4, text="最多跑几辆:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.max_cars_var = tk.StringVar(value=str(self._saved_cfg.get("max_cars", config.MAX_CARS)))
        ttk.Entry(row4, textvariable=self.max_cars_var, width=6).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(row4, text="辆  （0 = 无限，直到列表为空）", foreground="gray").pack(side=tk.LEFT, padx=(4, 0))

        # 定时任务
        row6b = ttk.Frame(run_frame)
        row6b.pack(fill=tk.X, pady=3)
        ttk.Label(row6b, text="定时任务:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.schedule_enabled_var = tk.BooleanVar(value=self._saved_cfg.get("schedule_enabled", False))
        ttk.Checkbutton(row6b, text="启用定时", variable=self.schedule_enabled_var,
                        command=self._toggle_schedule).pack(side=tk.LEFT, padx=(8, 0))

        # 定时详情（可折叠）
        self.schedule_detail_frame = ttk.Frame(run_frame)
        self.schedule_detail_frame.pack(fill=tk.X, pady=3)
        # 占位标签
        ttk.Label(self.schedule_detail_frame, text="", width=12).pack(side=tk.LEFT)
        # 时间
        time_frame = ttk.Frame(self.schedule_detail_frame)
        time_frame.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(time_frame, text="执行时间:").pack(side=tk.LEFT)
        self.schedule_hour_var = tk.StringVar(value=self._saved_cfg.get("schedule_hour", "08"))
        ttk.Entry(time_frame, textvariable=self.schedule_hour_var, width=3).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT)
        self.schedule_minute_var = tk.StringVar(value=self._saved_cfg.get("schedule_minute", "00"))
        ttk.Entry(time_frame, textvariable=self.schedule_minute_var, width=3).pack(side=tk.LEFT, padx=(4, 0))
        # 周期
        cycle_frame = ttk.Frame(self.schedule_detail_frame)
        cycle_frame.pack(side=tk.LEFT, padx=(16, 0))
        ttk.Label(cycle_frame, text="周期:").pack(side=tk.LEFT)
        self.schedule_cycle_var = tk.StringVar(value=self._saved_cfg.get("schedule_cycle", "daily"))
        ttk.Radiobutton(cycle_frame, text="每天", variable=self.schedule_cycle_var,
                        value="daily").pack(side=tk.LEFT, padx=(4, 8))
        ttk.Radiobutton(cycle_frame, text="工作日", variable=self.schedule_cycle_var,
                        value="weekday").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(cycle_frame, text="自定义", variable=self.schedule_cycle_var,
                        value="custom").pack(side=tk.LEFT)
        # 自定义星期
        self.custom_days_frame = ttk.Frame(run_frame)
        self.custom_days_frame.pack(fill=tk.X, pady=3)
        ttk.Label(self.custom_days_frame, text="", width=12).pack(side=tk.LEFT)
        days_inner = ttk.Frame(self.custom_days_frame)
        days_inner.pack(side=tk.LEFT, padx=(8, 0))
        self.day_vars = {}
        day_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        saved_days = self._saved_cfg.get("schedule_days", [])
        for name, key in zip(day_names, day_keys):
            var = tk.BooleanVar(value=key in saved_days)
            self.day_vars[key] = var
            ttk.Checkbutton(days_inner, text=name, variable=var).pack(side=tk.LEFT, padx=(0, 4))
        # 初始状态
        self._toggle_schedule()

        # ── 系统设置 ──
        sys_frame = ttk.LabelFrame(container, text="🖥 系统设置", padding=12)
        sys_frame.pack(fill=tk.X, pady=(0, 8))

        # 无头模式
        row7 = ttk.Frame(sys_frame)
        row7.pack(fill=tk.X, pady=3)
        ttk.Label(row7, text="无头模式:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.headless_var = tk.BooleanVar(value=self._saved_cfg.get("headless", config.HEADLESS))
        ttk.Checkbutton(row7, text="不显示浏览器窗口（后台运行，看不到操作过程）",
                        variable=self.headless_var).pack(side=tk.LEFT, padx=(8, 0))

        # 操作间隔
        row8 = ttk.Frame(sys_frame)
        row8.pack(fill=tk.X, pady=3)
        ttk.Label(row8, text="操作间隔:", width=12, anchor=tk.E).pack(side=tk.LEFT)
        self.slow_var = tk.StringVar(value=str(self._saved_cfg.get("slow", config.SLOW)))
        ttk.Entry(row8, textvariable=self.slow_var, width=6).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(row8, text="秒  （每步操作之间的等待时间）", foreground="gray").pack(side=tk.LEFT, padx=(4, 0))

        # ── 保存按钮 ──
        btn_row = ttk.Frame(container)
        btn_row.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(btn_row, text="💾 保存所有设置", command=self._save_all_settings).pack(side=tk.RIGHT)
        self.settings_status_var = tk.StringVar(value="")
        ttk.Label(btn_row, textvariable=self.settings_status_var,
                  foreground="green").pack(side=tk.RIGHT, padx=(0, 12))

    # --------------------------------------------------------
    # 定时任务 UI 控制
    # --------------------------------------------------------
    def _build_cron_expression(self):
        """把 GUI 配置转成 Cron 表达式"""
        if not self.schedule_enabled_var.get():
            return ""
        minute = self.schedule_minute_var.get().zfill(2)
        hour = self.schedule_hour_var.get().zfill(2)
        cycle = self.schedule_cycle_var.get()
        if cycle == "daily":
            return f"{minute} {hour} * * *"
        elif cycle == "weekday":
            return f"{minute} {hour} * * 1-5"
        elif cycle == "custom":
            day_keys = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            day_nums = ["1", "2", "3", "4", "5", "6", "0"]
            selected = []
            for key, num in zip(day_keys, day_nums):
                if self.day_vars[key].get():
                    selected.append(num)
            if not selected:
                return ""
            days_str = ",".join(selected)
            return f"{minute} {hour} * * {days_str}"
        return ""

    # --------------------------------------------------------
    # 标签页3: 黑名单 🆕
    # --------------------------------------------------------
    def _build_tab_skip(self, parent):
        # 顶部说明
        info = ttk.Frame(parent)
        info.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(info, text="跳过这些车（不会再跑）。服务器提示'不能创建流程'时自动加。",
                  foreground="gray", wraplength=600).pack(side=tk.LEFT)
        self.skip_count_var = tk.StringVar(value="共 0 辆")
        ttk.Label(info, textvariable=self.skip_count_var,
                  font=("Microsoft YaHei", 11, "bold"), foreground="#1a73e8").pack(side=tk.RIGHT)

        # 列表区（占中间大部）
        list_frame = ttk.LabelFrame(parent, text="黑名单", padding=4)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 6))

        self.skip_listbox = tk.Listbox(
            list_frame, font=("Consolas", 11),
            selectmode=tk.EXTENDED,  # 允许多选
        )
        skip_scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.skip_listbox.yview)
        self.skip_listbox.config(yscrollcommand=skip_scroll.set)
        self.skip_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        skip_scroll.pack(side=tk.LEFT, fill=tk.Y)

        # 按钮区
        skip_btns = ttk.Frame(parent)
        skip_btns.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(skip_btns, text="🗑 移除选中",
                   command=self._remove_selected_skip_plates).pack(side=tk.LEFT)
        ttk.Button(skip_btns, text="🔄 刷新",
                   command=self._refresh_skip_listbox).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Button(skip_btns, text="🧹 清空全部",
                   command=self._clear_all_skip_plates).pack(side=tk.LEFT, padx=(4, 0))

        # 初始化列表
        self._refresh_skip_listbox()

    def _toggle_schedule(self):
        """根据是否启用定时，显示/隐藏定时详情"""
        if self.schedule_enabled_var.get():
            self.schedule_detail_frame.pack(fill=tk.X, pady=3)
            self.custom_days_frame.pack(fill=tk.X, pady=3)
        else:
            self.schedule_detail_frame.pack_forget()
            self.custom_days_frame.pack_forget()

    # --------------------------------------------------------
    # 🆕 黑名单管理
    # --------------------------------------------------------
    def _refresh_skip_listbox(self):
        """从磁盘重新加载黑名单,刷新 listbox"""
        # 从磁盘重新读
        disk_plates = _run._load_skip_plates()
        # 合并到内存里的 (以防运行中刚加的)
        _run.SKIP_PLATES.update(disk_plates)
        # 清空 listbox
        self.skip_listbox.delete(0, tk.END)
        # 按字母顺序填充
        for plate in sorted(_run.SKIP_PLATES):
            self.skip_listbox.insert(tk.END, plate)
        # 更新计数
        count = len(_run.SKIP_PLATES)
        self.skip_count_var.set(f"共 {count} 辆")

    def _remove_selected_skip_plates(self):
        """移除 listbox 里选中的车牌"""
        selected = self.skip_listbox.curselection()
        if not selected:
            self.settings_status_var.set("⚠️ 请先选中要移除的车牌")
            return
        removed = []
        for idx in selected:
            plate = self.skip_listbox.get(idx)
            _run._remove_from_skip_plates(plate)  # 从内存 + 磁盘移除
            removed.append(plate)
        # 刷新 listbox
        self._refresh_skip_listbox()
        # 提示
        self.settings_status_var.set(f"✅ 已移除 {len(removed)} 辆: {', '.join(removed)}")

    def _clear_all_skip_plates(self):
        """清空全部黑名单"""
        if not _run.SKIP_PLATES:
            return
        # 确认
        from tkinter import messagebox
        if not messagebox.askyesno("确认", f"确定要清空全部 {len(_run.SKIP_PLATES)} 辆黑名单吗？\n（清空后这些车会被重新尝试）"):
            return
        count = len(_run.SKIP_PLATES)
        _run.SKIP_PLATES.clear()
        _run._save_skip_plates()
        self._refresh_skip_listbox()
        self.settings_status_var.set(f"✅ 已清空 {count} 辆黑名单")

    # --------------------------------------------------------
    # 保存设置
    # --------------------------------------------------------
    def _save_all_settings(self):
        """保存所有设置到本地文件"""
        cfg = {
            "username": self.username_var.get().strip(),
            "password": self.password_var.get(),
            "auto_login": self.auto_login_var.get(),
            "max_cars": self.max_cars_var.get(),
            "headless": self.headless_var.get(),
            "slow": self.slow_var.get(),
            "schedule_enabled": self.schedule_enabled_var.get(),
            "schedule_hour": self.schedule_hour_var.get(),
            "schedule_minute": self.schedule_minute_var.get(),
            "schedule_cycle": self.schedule_cycle_var.get(),
            "schedule_days": [k for k, v in self.day_vars.items() if v.get()],
            "schedule": self._build_cron_expression(),
        }
        save_user_config(cfg)
        self.settings_status_var.set("✓ 已保存")
        self.after(3000, lambda: self.settings_status_var.set(""))

        # 如果启用了定时任务，同步到 Windows 任务计划
        if cfg.get("schedule_enabled"):
            cron = cfg.get("schedule", "")
            if cron:
                ok, msg = register_schtask(cron)
                if ok:
                    messagebox.showinfo("定时任务", f"{msg}\n\n点击确定后可以在后台运行，无需保持 GUI 打开")
                else:
                    messagebox.showwarning("定时任务", msg)
        else:
            # 取消定时任务
            unregister_schtask()

    # --------------------------------------------------------
    # 启动前登录对话框
    # --------------------------------------------------------
    def _show_login_dialog(self):
        """弹出登录输入框, 返回 (username, password, ok)"""
        dialog = tk.Toplevel(self)
        dialog.title("登录运管站")
        dialog.geometry("380x200")
        dialog.transient(self)
        dialog.grab_set()
        dialog.resizable(False, False)

        result = {"username": "", "password": "", "ok": False}

        # 标题
        ttk.Label(dialog, text="🚛 请输入运管站登录账号",
                  font=("Microsoft YaHei", 12, "bold")).pack(pady=(16, 8))

        # 账号
        row1 = ttk.Frame(dialog)
        row1.pack(fill=tk.X, padx=24, pady=4)
        ttk.Label(row1, text="账号:", width=6, anchor=tk.E).pack(side=tk.LEFT)
        username_var = tk.StringVar(value=self.username_var.get())
        ttk.Entry(row1, textvariable=username_var, width=24).pack(side=tk.LEFT, padx=(4, 0))

        # 密码
        row2 = ttk.Frame(dialog)
        row2.pack(fill=tk.X, padx=24, pady=4)
        ttk.Label(row2, text="密码:", width=6, anchor=tk.E).pack(side=tk.LEFT)
        password_var = tk.StringVar(value=self.password_var.get())
        ttk.Entry(row2, textvariable=password_var, width=24, show="●").pack(side=tk.LEFT, padx=(4, 0))

        # 记住密码
        remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="记住密码(保存到本地)", variable=remember_var).pack(pady=(4, 0))

        # 按钮
        def on_login():
            result["username"] = username_var.get().strip()
            result["password"] = password_var.get()
            result["ok"] = True
            # 如果勾了记住密码，存到主设置里
            if remember_var.get():
                self.username_var.set(result["username"])
                self.password_var.set(result["password"])
                self._save_all_settings()
            dialog.destroy()

        def on_cancel():
            result["ok"] = False
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="🔑 登录", command=on_login, width=12).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_frame, text="取消", command=on_cancel, width=12).pack(side=tk.LEFT, padx=4)

        # 回车键快捷登录
        dialog.bind("<Return>", lambda e: on_login())
        dialog.bind("<Escape>", lambda e: on_cancel())

        # 模态等待
        dialog.wait_window()
        return result["username"], result["password"], result["ok"]

    # --------------------------------------------------------
    # 日志操作
    # --------------------------------------------------------
    def _append_log(self, text: str):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _export_log(self):
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            initialfilename=f"HCCheck_日志_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        )
        if path:
            self.log_text.config(state=tk.NORMAL)
            content = self.log_text.get("1.0", tk.END)
            self.log_text.config(state=tk.DISABLED)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("导出成功", f"日志已保存到:\n{path}")

    def _consume_queues(self):
        """从两个队列中取出消息：log_queue（日志）和 status_queue（状态栏）
        - log_queue: 接收 worker 的 print 输出，特殊信号 __WORKER_DONE__
        - status_queue: 接收 run.py push_status() 推的状态更新
        """
        # 日志队列
        try:
            while True:
                text = self.log_queue.get_nowait()
                if text == "__WORKER_DONE__":
                    self._on_worker_done()
                    continue
                self._append_log(text)
        except queue.Empty:
            pass
        # 状态队列
        try:
            while True:
                status = self.status_queue.get_nowait()
                self._apply_status(status)
        except queue.Empty:
            pass
        self.after(100, self._consume_queues)

    def _apply_status(self, status: dict):
        """根据 push_status() 推送的消息更新状态栏
        任一字段为 None 表示不更新该项
        """
        plate = status.get("plate")
        if plate is not None:
            self.plate_var.set(plate or "—")
        step = status.get("step")
        if step is not None:
            self.step_var.set(step or "—")
        done = status.get("done")
        if done is not None:
            self.done_var.set(str(done))

    # --------------------------------------------------------
    # 启动 / 停止
    # --------------------------------------------------------
    def _apply_config(self):
        """把 GUI 上的配置写回 config 模块"""
        config.LOGIN_USERNAME = self.username_var.get().strip()
        config.LOGIN_PASSWORD = self.password_var.get()
        config.LOGIN_AUTO_SUBMIT = self.auto_login_var.get()
        config.HEADLESS = self.headless_var.get()
        config.SINGLE_RUN = False  # 默认批量模式
        config.DEBUG = False       # 默认关闭调试
        try:
            config.MAX_CARS = int(self.max_cars_var.get())
        except ValueError:
            config.MAX_CARS = 0
        try:
            config.SLOW = float(self.slow_var.get())
        except ValueError:
            config.SLOW = 0.5
        config.SCHEDULE = self._build_cron_expression()

    def _start(self):
        if self.running:
            return

        # 先把设置页的值应用到 config
        self._apply_config()

        # 如果设置页没填账号密码，才弹登录框让用户填（备用）
        if not config.LOGIN_USERNAME or not config.LOGIN_PASSWORD:
            username, password, ok = self._show_login_dialog()
            if not ok:
                return
            # 登录框填了，同步回设置页 + config
            config.LOGIN_USERNAME = username
            config.LOGIN_PASSWORD = password
            config.LOGIN_AUTO_SUBMIT = True
            self.username_var.set(username)
            self.password_var.set(password)

        # 重置停止控制状态（防止上一次未清理的信号影响本次启动）
        config.CURRENT_PLATE = ""
        config.FORCE_STOP = False
        config.SINGLE_RUN = False
        self.running = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.done_var.set("0")
        self.plate_var.set("启动中...")
        self.step_var.set("—")

        # 重定向 stdout/stderr 到队列
        sys.stdout = TextRedirector(self.log_queue, sys.__stdout__)
        sys.stderr = TextRedirector(self.log_queue, sys.__stderr__)

        # 启动后台线程
        self.worker_thread = threading.Thread(target=self._run_worker, daemon=True)
        self.worker_thread.start()

    def _run_worker(self):
        """后台线程运行主流程
        退出时往 log_queue 推一个 __WORKER_DONE__ 特殊信号，
        主线程的 _consume_log_queue 会消费后触发 _on_worker_done()
        比之前用 self.after() 在子线程调主线程更可靠，不会丢
        """
        try:
            run_main()
        except SystemExit:
            pass
        except Exception as e:
            self.log_queue.put(f"\n💥 异常退出: {e}\n")
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            self.log_queue.put("__WORKER_DONE__")

    def _on_worker_done(self):
        self.running = False
        config.CURRENT_PLATE = ""
        config.FORCE_STOP = False
        self._stop_phase = 0
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.plate_var.set("已停止")
        self.step_var.set("—")

    def _stop(self):
        """智能停止：
        - 有车在跑且首次按 → 温和停（按钮保持可用）
        - 有车在跑且 5 秒内再按 → 升级为强制停（关闭 stdin + FORCE_STOP）
        - 没车在跑 → 直接强制停
        """
        import time as _t
        if not self.running:
            return
        now = _t.time()
        current = config.CURRENT_PLATE

        # 已发过温和停且 5 秒内 → 升级为强制停
        if self._stop_phase == 1 and (now - self._stop_phase_time) < 5.0 and current:
            self._stop_phase = 2
            config.FORCE_STOP = True
            config.SINGLE_RUN = False
            self._close_stdin_to_break_input()
            self.log_queue.put("\n⛔ 升级为强制停止：主循环下一圈立即退出，卡住的 input() 也会被唤醒\n")
            self.plate_var.set("强制停止中...")
            self.btn_stop.config(state=tk.DISABLED)
            return

        if current:
            # 有车在跑 + 首次按 → 温和停，按钮保持可用，提示可升级
            config.SINGLE_RUN = True
            self._stop_phase = 1
            self._stop_phase_time = now
            self.log_queue.put(f"\n⏹ 温和停止：当前车 [{current}] 跑完后退出")
            self.log_queue.put("   ⚡ 5 秒内再按一次停止按钮可强制中断（用于车卡死场景）\n")
            self.plate_var.set(f"停止中({current})...")
            # 按钮保持 NORMAL，让用户可以再按一次升级为强制停
        else:
            # 没车在跑 → 直接强制停
            self._stop_phase = 2
            config.FORCE_STOP = True
            self._close_stdin_to_break_input()
            self.log_queue.put("\n⛔ 强制停止：主循环下一圈立即退出\n")
            self.plate_var.set("强制停止中...")
            self.btn_stop.config(state=tk.DISABLED)

    def _close_stdin_to_break_input(self):
        """关闭 stdin 让卡在 input() 的 worker 唤醒抛 EOFError"""
        try:
            sys.stdin.close()
        except Exception:
            pass

    # --------------------------------------------------------
    # 关于 / 关闭
    # --------------------------------------------------------
    def _about(self):
        messagebox.showinfo(
            "关于 HCCheck",
            f"HCCheck {self.VERSION}\n"
            f"\u8fd0\u7ba1\u7ad9\u8d27\u8f66\u5ba1\u9a8c\u81ea\u52a8\u5316\u5de5\u5177\n"
            "\n"
            "\u6587\u4ef6\u7248\u672c:        1.1.0.0\n"
            "\u5f00\u6e90\u9879\u76ee:        http://github.com/cnchaoge/hccheck\n"
            "\n"
            "\u6280\u672f\u6808: Python + Playwright + Tkinter\n"
            "\u6d41\u7a0b: \u8f66\u8f86\u68c0\u6d4b \u2192 \u6280\u672f\u5ba1\u6838 \u2192 \u4e1a\u52a1\u5ba1\u6838 \u2192 \u8f66\u8f86\u5e74\u5ba1 \u2192 \u5f52\u6863\n"
            "\n"
            "\u00a9 2026 \u8d85\u54e5 18531729777\uff08\u5fae\u4fe1\uff09"
        )

    def _on_close(self):
        if self.running:
            if not messagebox.askyesno("确认", "程序正在运行中，确定要退出吗？"):
                return
            config.SINGLE_RUN = True
        self.destroy()


# ============================================================
# Windows 任务计划集成（定时任务调度）
# ============================================================
def register_schtask(cron_expr, exe_path=None):
    """把 cron 表达式注册到 Windows 任务计划
    Args:
        cron_expr: Cron 表达式，如 '0 8 * * *' (每天8点)
        exe_path: HCCheck.exe 路径, 默认为当前 Python
    Returns:
        (success: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "非 Windows 系统不支持此功能"

    if not cron_expr:
        return False, "请先配置定时规则"

    parts = cron_expr.split()
    if len(parts) != 5:
        return False, f"Cron 表达式格式错误: {cron_expr}"

    minute, hour, day, month, weekday = parts

    if exe_path is None:
        exe_path = sys.executable

    # 只处理"每天/工作日/自定义星期" 三种场景
    if day != "*" or month != "*":
        return False, "暂不支持指定日期/月份，仅支持每天/工作日/周几"

    # 转换星期 (cron: 0=周日, 1-5=周一-周五; schtasks: MON,TUE,WED,THU,FRI,SAT,SUN)
    weekday_map = {
        "1-5": "MON,TUE,WED,THU,FRI",
        "0": "SUN",
        "1": "MON",
        "2": "TUE",
        "3": "WED",
        "4": "THU",
        "5": "FRI",
        "6": "SAT",
    }

    if weekday == "*":
        # 每天
        sc_type = "DAILY"
        sc_value = None
    elif weekday == "1-5":
        # 工作日
        sc_type = "WEEKLY"
        sc_value = "MON,TUE,WED,THU,FRI"
    elif "," in weekday:
        # 自定义多天
        days = []
        for d in weekday.split(","):
            d = d.strip()
            if d in weekday_map:
                days.append(weekday_map[d])
        sc_type = "WEEKLY"
        sc_value = ",".join(days)
    else:
        # 单天
        sc_type = "WEEKLY"
        sc_value = weekday_map.get(weekday, "MON")

    # 先删除旧任务
    delete_cmd = ["schtasks", "/delete", "/tn", "HCCheck_Auto", "/f"]
    subprocess.run(delete_cmd, capture_output=True, shell=False)

    # 构建创建命令
    start_time = f"{hour.zfill(2)}:{minute.zfill(2)}"
    cmd = [
        "schtasks", "/create",
        "/tn", "HCCheck_Auto",
        "/tr", f'"{exe_path}" --headless',
        "/sc", sc_type,
        "/st", start_time,
    ]
    if sc_value:
        cmd.extend(["/d", sc_value])
    cmd.append("/f")  # 强制覆盖

    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode == 0:
        cycle_desc = {
            "DAILY": "每天",
            "WEEKLY": f"每周{sc_value}",
        }.get(sc_type, sc_type)
        return True, f"已注册定时任务：{cycle_desc} {start_time} 自动运行"
    else:
        return False, f"注册失败: {result.stderr or result.stdout}"


def unregister_schtask():
    """从 Windows 任务计划删除"""
    if sys.platform != "win32":
        return False, "非 Windows 系统不支持此功能"
    cmd = ["schtasks", "/delete", "/tn", "HCCheck_Auto", "/f"]
    result = subprocess.run(cmd, capture_output=True, text=True, shell=False)
    if result.returncode == 0:
        return True, "已取消定时任务"
    else:
        return False, f"取消失败: {result.stderr or '任务不存在'}"


# ============================================================
# 入口
# ============================================================
def _run_headless():
    """无头模式入口：供 Windows 任务计划调用"""
    from run import main as run_main
    print("=" * 60)
    print("  HCCheck 无头模式（定时任务触发）")
    print("=" * 60)
    run_main()


if __name__ == "__main__":
    if "--headless" in sys.argv:
        # 无头模式：不开 GUI，直接跑主流程
        _run_headless()
    else:
        # 正常 GUI 模式
        app = App()
        app.mainloop()
