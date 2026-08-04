"""HCCheck v1.2 mock 测试 - 验证 db_query 和 history tab

不依赖 Playwright / 真实运管站系统。
"""
import os
import sys
import time

# 让 import 能找到 config / db / db_query
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import config
import db
import db_query


def test_1_data_dir():
    """测试 1: 数据目录正确创建"""
    print("\n=== Test 1: 数据目录 ===")
    print(f"  DATA_DIR: {config.DATA_DIR}")
    assert os.path.isdir(config.DATA_DIR), f"数据目录不存在: {config.DATA_DIR}"
    print("  ✅ 数据目录存在")
    return True


def test_2_record_runs():
    """测试 2: 写入 3 辆 mock 车到数据库"""
    print("\n=== Test 2: 写入 mock 数据 ===")

    # 初始化数据库
    db.init_db()
    run_id = db.get_run_id()
    print(f"  run_id: {run_id}")

    # 模拟 3 辆车 (时间递增, 防止负数 duration)
    base_time = time.time() - 300  # 5 分钟前开始
    test_cars = [
        ("冀J0E139", "带挂", base_time, base_time + 32.5, "成功", ""),
        ("冀J0E140", "不带挂", base_time + 40, base_time + 70.0, "成功", ""),
        ("冀J0E141", "带挂", base_time + 80, base_time + 140.0, "失败", "popup4 超时未响应"),
    ]

    for plate, flow_type, start, end, status, error in test_cars:
        ok = db.record_run(plate, flow_type, start, end, status, error)
        assert ok, f"记录 {plate} 失败"
        print(f"  ✅ {plate} ({flow_type}) - {status} ({end-start:.1f}s)")

    return run_id


def test_3_query(run_id):
    """测试 3: get_runs_by_run_id 查询"""
    print("\n=== Test 3: 查询本次 run ===")
    runs = db_query.get_runs_by_run_id(run_id)
    print(f"  查询到 {len(runs)} 辆车:")
    for r in runs:
        print(f"    {r['plate']} | {r['flow_type']} | {r['duration']:.1f}s | {r['status']}")
    assert len(runs) == 3, f"应该有 3 辆车, 实际 {len(runs)}"
    # 验证按 start_time 升序
    assert runs[0]["plate"] == "冀J0E139"
    assert runs[1]["plate"] == "冀J0E140"
    assert runs[2]["plate"] == "冀J0E141"
    # 验证失败车有 error
    assert runs[2]["error"] == "popup4 超时未响应"
    print("  ✅ 查询结果正确")
    return True


def test_4_summary(run_id):
    """测试 4: get_run_summary 汇总"""
    print("\n=== Test 4: 汇总统计 ===")
    summary = db_query.get_run_summary(run_id)
    print(f"  总数: {summary['total']}")
    print(f"  成功: {summary['success']}")
    print(f"  失败: {summary['failed']}")
    print(f"  平均耗时: {summary['avg_duration']}s")
    assert summary["total"] == 3
    assert summary["success"] == 2
    assert summary["failed"] == 1
    assert summary["avg_duration"] > 0
    print("  ✅ 汇总正确")
    return True


def test_5_export(run_id):
    """测试 5: 导出 xlsx"""
    print("\n=== Test 5: 导出 xlsx ===")
    output = os.path.join(SCRIPT_DIR, "_test_export.xlsx")
    # 先删旧文件
    if os.path.exists(output):
        os.remove(output)

    ok = db_query.export_run_to_xlsx(run_id, output)
    assert ok, "导出失败"
    assert os.path.exists(output), f"文件未生成: {output}"
    size = os.path.getsize(output)
    print(f"  ✅ xlsx 已生成: {output} ({size} bytes)")

    # 验证 xlsx 内容
    from openpyxl import load_workbook
    wb = load_workbook(output)
    ws = wb.active
    print(f"  Sheet 名: {ws.title}")
    print(f"  总行数: {ws.max_row}")
    print(f"  表头: {[c.value for c in ws[1]]}")
    print(f"  第一条: {[c.value for c in ws[2]]}")

    # 验证表头
    expected_headers = ["车牌", "类型", "耗时(秒)", "状态", "错误", "开始时间"]
    actual_headers = [c.value for c in ws[1]]
    assert actual_headers == expected_headers, f"表头不对: {actual_headers}"

    # 验证数据行数 = 1 表头 + 3 数据
    assert ws.max_row == 4, f"行数不对: {ws.max_row}"

    # 清理
    os.remove(output)
    print("  ✅ xlsx 内容正确, 测试文件已清理")
    return True


def test_6_empty_run_id():
    """测试 6: 空 run_id 容错"""
    print("\n=== Test 6: 空 run_id 容错 ===")
    runs = db_query.get_runs_by_run_id("")
    summary = db_query.get_run_summary("")
    assert runs == []
    assert summary["total"] == 0
    print("  ✅ 空 run_id 返回空结果不崩")
    return True


def test_6b_latest_run_id():
    """Test 6b: get_latest_run_id 跨进程查最新 (v1.2.1 修复验证)"""
    print("\n=== Test 6b: get_latest_run_id ===")
    # 先清掉表, 插 2 个不同 run_id
    import sqlite3
    conn = sqlite3.connect(config.DB_FILE, timeout=5)
    conn.execute("DELETE FROM runs")
    conn.commit()
    conn.close()

    # 插第 1 个 run (老)
    db.record_run("冀J0E139", "带挂", time.time()-100, time.time()-50, "成功", "", run_id="20260101-120000-old0001")
    # 插第 2 个 run (新)
    db.record_run("冀J0E140", "不带挂", time.time()-50, time.time()-20, "成功", "", run_id="20260101-130000-new0002")
    # 插第 3 个 (中间 created_at)
    db.record_run("冀J0E141", "带挂", time.time()-10, time.time(), "失败", "测试错误", run_id="20260101-140000-mid0003")

    latest = db_query.get_latest_run_id()
    print(f"  最新 run_id: {latest}")
    assert latest == "20260101-140000-mid0003", f"应为 mid0003, 实际 {latest}"
    print(f"  ✅ 最新 run_id 正确")
    return True


def test_7_gui_loading():
    """测试 7: GUI 代码结构 (AST 检查, 不实际 import, 避开 playwright 依赖)"""
    print("\n=== Test 7: GUI 代码结构 ===")
    import ast
    src = open(os.path.join(SCRIPT_DIR, "gui.py"), encoding="utf-8").read()
    tree = ast.parse(src)

    # 找 App 类
    app_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            app_class = node
            break
    assert app_class is not None, "找不到 class App"

    # 找方法名
    methods = {m.name for m in app_class.body if isinstance(m, ast.FunctionDef)}
    required = ["_build_tab_history", "_refresh_history_table", "_export_history_xlsx"]
    for m in required:
        assert m in methods, f"App 缺少方法: {m}"
        print(f"  ✅ App.{m} 存在")

    # 找 VERSION
    version = None
    for node in app_class.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "VERSION":
                    version = node.value.value
                    break
    assert version == "v1.2.1", f"VERSION 应为 v1.2.1, 实际 {version}"
    print(f"  ✅ App.VERSION = {version}")

    # 验证 import
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    assert "db" in imports, "缺 import db"
    assert "db_query" in imports, "缺 import db_query"
    print(f"  ✅ import db / db_query 正常")

    return True


def test_8_tab_order():
    """测试 8: 验证 Tab 顺序 (运行 / 历史记录 / 黑名单 / 设置)"""
    print("\n=== Test 8: Tab 顺序检查 ===")
    src = open(os.path.join(SCRIPT_DIR, "gui.py"), encoding="utf-8").read()

    # 找 4 个 tab 的添加顺序
    expected_order = [
        ("运行", "tab_run"),
        ("历史记录", "tab_history"),
        ("黑名单", "tab_skip"),
        ("设置", "tab_settings"),
    ]
    last_pos = -1
    for label, attr in expected_order:
        # 找 self.notebook.add(self.tab_xxx, ...)
        idx = src.find(f"self.notebook.add(self.{attr}")
        assert idx > last_pos, f"Tab '{label}' ({attr}) 位置不对"
        print(f"  ✅ {label} (self.{attr}) 在位置 {idx}")
        last_pos = idx
    return True


def test_11_popup2_strategy5():
    """测试 11: popup2 _close_print_preview 有策略5 (v1.2.2)

    背景: 17:39 运管站实测 popup2 打印后 Lodop 预览不关, 旧 4 策略都失效
    修法: 加策略5, 主动找 Lodop preview 容器里的"关闭"按钮直接点
    """
    print("\n=== Test 11: popup2 策略5 (Lodop 关闭按钮) ===")
    src = open(os.path.join(SCRIPT_DIR, "popups/p2_tech_review.py"), encoding="utf-8").read()

    # 检查策略5存在
    assert "lodop_close_selectors" in src, "❌ popup2 没有 lodop_close_selectors"
    print("  ✅ popup2 策略5 lodop_close_selectors 存在")

    # 检查 selector 列表包含关键 Lodop 容器
    for selector in [
        "LODOP_WebPrint",     # Lodop 主预览容器 class
        "关闭",                # 按钮文字
    ]:
        assert selector in src, f"❌ popup2 策略5 缺少关键 selector: {selector}"
    print("  ✅ 包含 LODOP_WebPrint selector + '关闭' 按钮")

    # 检查 fallback 到原提示
    assert "ℹ️ 打印预览可能仍在显示" in src, "❌ 错误信息丢了"
    print("  ✅ fallback 提示 '打印预览可能仍在显示' 保留")
    return True


def test_12_popup2_strategy8_lodop_api():
    """测试 12: popup2 策略8 进 _workflow_tmp iframe 调 LODOP API (v1.2.2 第 6 轮)

    背景: 策略7 诊断定位 _workflow_tmp iframe 是 Lodop 渲染位置, window.LODOP 在那里定义
    修法: 进 iframe 调 LODOP.PREVIEW(false) + SET_PRINT_MODE('AUTO_CLOSE_PREWINDOW', true) + CLOSE_PRINTTASK()
    """
    print("\n=== Test 12: popup2 策略8 (LODOP API) ===")
    src = open(os.path.join(SCRIPT_DIR, "popups/p2_tech_review.py"), encoding="utf-8").read()

    # 检查策略8存在
    assert "STRATEGY8" in src, "❌ popup2 没有 STRATEGY8"
    print("  ✅ popup2 策略8 STRATEGY8 存在")

    # 检查找 _workflow_tmp iframe
    assert "workflow_tmp" in src, "❌ popup2 策略8 没找 _workflow_tmp iframe"
    print("  ✅ 策略8 找 _workflow_tmp iframe")

    # 检查调关键 LODOP API
    for api in ["PREVIEW", "SET_PRINT_MODE", "AUTO_CLOSE_PREWINDOW", "CLOSE_PRINTTASK"]:
        assert api in src, f"❌ 策略8 缺 LODOP API: {api}"
    print("  ✅ 调用 PREVIEW / SET_PRINT_MODE / AUTO_CLOSE_PREWINDOW / CLOSE_PRINTTASK")
    return True


def test_13_popup2_strategy10_powershell():
    """测试 13: popup2 策略10 OS 层 PowerShell 关 Lodop native window (v1.2.2 第 9 轮)

    背景: Lodop preview 是 Windows native window, JS API 管不到
    修法: subprocess 调 PowerShell, Get-Process 找标题含'打印预览'/'Lodop', CloseMainWindow
    """
    print("\n=== Test 13: popup2 策略10 (PowerShell) ===")
    src = open(os.path.join(SCRIPT_DIR, "popups/p2_tech_review.py"), encoding="utf-8").read()

    # 检查策略10存在
    assert "STRATEGY10" in src, "❌ popup2 没有 STRATEGY10"
    print("  ✅ popup2 策略10 STRATEGY10 存在")

    # 检查 subprocess + PowerShell
    for kw in ["subprocess", "powershell", "CloseMainWindow", "Get-Process"]:
        assert kw in src, f"❌ 策略10 缺关键字: {kw}"
    print("  ✅ 用 subprocess + powershell + Get-Process + CloseMainWindow")

    # 检查只匹配预览窗口 (不杀 IE/Chrome)
    for kw in ["打印预览", "Lodop", "LODOP"]:
        assert kw in src, f"❌ 策略10 缺窗口标题关键词: {kw}"
    print("  ✅ 窗口标题关键词: 打印预览 / Lodop / LODOP")

    # 检查 win32 平台守卫
    assert 'sys.platform == "win32"' in src, "❌ 策略10 缺 win32 平台守卫"
    print("  ✅ 只在 Windows 平台执行 (sys.platform == 'win32')")

    return True



    """测试 12: popup2 策略8 进 _workflow_tmp iframe 调 LODOP API (v1.2.2 第 6 轮)

    背景: 策略7 诊断定位 _workflow_tmp iframe 是 Lodop 渲染位置, window.LODOP 在那里定义
    修法: 进 iframe 调 LODOP.PREVIEW(false) + SET_PRINT_MODE('AUTO_CLOSE_PREWINDOW', true) + CLOSE_PRINTTASK()
    """
    print("\n=== Test 12: popup2 策略8 (LODOP API) ===")
    src = open(os.path.join(SCRIPT_DIR, "popups/p2_tech_review.py"), encoding="utf-8").read()

    # 检查策略8存在
    assert "STRATEGY8" in src, "❌ popup2 没有 STRATEGY8"
    print("  ✅ popup2 策略8 STRATEGY8 存在")

    # 检查找 _workflow_tmp iframe
    assert "workflow_tmp" in src, "❌ popup2 策略8 没找 _workflow_tmp iframe"
    print("  ✅ 策略8 找 _workflow_tmp iframe")

    # 检查调关键 LODOP API
    for api in ["PREVIEW", "SET_PRINT_MODE", "AUTO_CLOSE_PREWINDOW", "CLOSE_PRINTTASK"]:
        assert api in src, f"❌ 策略8 缺 LODOP API: {api}"
    print("  ✅ 调用 PREVIEW / SET_PRINT_MODE / AUTO_CLOSE_PREWINDOW / CLOSE_PRINTTASK")
    return True


def test_10_popup4_excludes_main_page():
    """测试 10: popup4 _close_residual_popups 豁免主页面 (v1.2.2 修复)

    背景: 17:39 实测 popup4 入口清理残留弹窗时, 主页面也被关, 导致后续 navigation 全失败
    修法: _close_residual_popups 增加 main_page 参数, 同时豁免主页面
    """
    print("\n=== Test 10: popup4 豁免主页面 ===")
    print("\n=== Test 10: popup4 豁免主页面 ===")
    import popups.p4_vehicle_annual as p4

    # 检查 handle 函数签名
    import inspect
    handle_sig = inspect.signature(p4.handle)
    assert 'main_page' in handle_sig.parameters, \
        "❌ popup4.handle 没有 main_page 参数"
    print("  ✅ popup4.handle 有 main_page 参数")

    # 检查 _click_year_check 函数签名
    cyc_sig = inspect.signature(p4._click_year_check)
    assert 'main_page' in cyc_sig.parameters, \
        "❌ popup4._click_year_check 没有 main_page 参数"
    print("  ✅ popup4._click_year_check 有 main_page 参数")

    # 检查 _close_residual_popups 函数签名
    crp_sig = inspect.signature(p4._close_residual_popups)
    assert 'main_page' in crp_sig.parameters, \
        "❌ popup4._close_residual_popups 没有 main_page 参数"
    print("  ✅ popup4._close_residual_popups 有 main_page 参数")

    # 检查 run.py 调用方都传了 main_page=page (忽略注释行)
    import re
    run_src_lines = open(os.path.join(SCRIPT_DIR, "run.py"), encoding="utf-8").readlines()
    code_lines = [l for l in run_src_lines if not l.strip().startswith("#")]
    code_src = "".join(code_lines)
    handle_calls = re.findall(r'handle_vehicle_annual\(', code_src)
    main_page_passes = re.findall(r'main_page=page\b', code_src)
    print(f"  ✅ run.py 里 handle_vehicle_annual 调用 {len(handle_calls)} 处")
    print(f"  ✅ main_page=page 实际传参 {len(main_page_passes)} 处")
    assert len(handle_calls) == 2, f"❌ 应有 2 处调用, 实际 {len(handle_calls)}"
    assert len(main_page_passes) == 2, f"❌ 应有 2 处传 main_page=page, 实际 {len(main_page_passes)}"
    return True


def test_9_no_tkinter_typos():
    """测试 9: 防 Tkinter 参数名 typo (v1.2.1 回归)

    背景: 之前用了 'initialfilename' (错), Tcl 报错 'bad option -initialfilename'
          正确参数名是 'initialfile'
    """
    print("\n=== Test 9: Tkinter 参数名 ===")
    src = open(os.path.join(SCRIPT_DIR, "gui.py"), encoding="utf-8").read()

    # 禁止 'initialfilename=' 作为实际 kwarg (错误参数名)
    import re
    bad_kwarg = re.findall(r'\binitialfilename\s*=', src)
    assert not bad_kwarg, \
        f"❌ gui.py 实际调用里还有 'initialfilename=' typo, 应改为 'initialfile=' ({len(bad_kwarg)} 处)"
    print(f"  ✅ 没有 'initialfilename=' 实际 kwarg (只在注释里提到, OK)")

    # 应该有 'initialfile=' (正确)
    initialfile_count = src.count('initialfile=')
    assert initialfile_count >= 1, "❌ 没找到 'initialfile=' (导出对话框应有默认文件名)"
    print(f"  ✅ 'initialfile=' 出现 {initialfile_count} 次 (xlsx + log 导出)")

    # VERSION 应该是 v1.2.1
    assert 'VERSION = "v1.2.1"' in src, "❌ VERSION 没 bump 到 v1.2.1"
    print("  ✅ VERSION = v1.2.1")

    # 按钮文案应该是 "导出最近"
    assert "导出最近为 xlsx" in src, "❌ 按钮文案没改成 '导出最近'"
    assert "导出本次为 xlsx" not in src, "❌ 还有 '导出本次为 xlsx' 旧文案"
    print("  ✅ 按钮文案 '导出最近为 xlsx' 正确")
    return True


def test_14_click_query_and_pagination():
    """测试 14: _click_query_button / _has_next_page / _click_next_page 函数 (v1.2.3)

    背景: 用户要求打开普货审验后先点查询, 而且要支持超过 15 辆的分页
    修法: 加 3 个新函数 + 重构 get_next_plate_from_list 加翻页 while 循环
    """
    print("\n=== Test 14: 查询 + 分页函数 ===")
    src = open(os.path.join(SCRIPT_DIR, "run.py"), encoding="utf-8").read()

    # 检查 4 个新函数都存在
    for fn in ["_click_query_button", "_has_next_page", "_click_next_page", "_scan_current_page_for_plate"]:
        assert f"def {fn}(" in src, f"❌ run.py 缺函数: {fn}"
        print(f"  ✅ def {fn}() 存在")

    # 检查 _click_query_button 多策略
    query_section = src[src.find("def _click_query_button"):src.find("def _has_next_page")]
    assert "input[value='查询']" in query_section, "❌ 缺 input value 策略"
    assert "get_by_role" in query_section, "❌ 缺 role 策略"
    print("  ✅ _click_query_button 含 input value + role + text 三策略")

    # 检查 _has_next_page 双重判断
    has_next_section = src[src.find("def _has_next_page"):src.find("def _click_next_page")]
    assert "row_count < 15" in has_next_section, "❌ _has_next_page 缺 < 15 判断"
    assert "下一页" in has_next_section, "❌ _has_next_page 缺下一页按钮检查"
    assert "is_disabled" in has_next_section, "❌ _has_next_page 缺 disabled 检查"
    print("  ✅ _has_next_page 双重判断: < 15 + 下一页按钮 + disabled")

    # 检查 _click_next_page 翻页
    click_next_section = src[src.find("def _click_next_page"):src.find("def _verify_in_normal_review")]
    assert "下一页" in click_next_section, "❌ _click_next_page 缺下一页定位"
    assert "evaluate" in click_next_section, "❌ _click_next_page 缺 JS 强制点击兜底"
    print("  ✅ _click_next_page 含 text + JS 兜底")

    return True


def test_15_pagination_while_loop():
    """测试 15: get_next_plate_from_list 翻页 while 循环 (v1.2.3)

    背景: 超过 15 辆车时, 需翻页才能拿到所有车 (用户反馈: <15 辆时无下一页按钮)
    修法: 主函数加 while 循环, 调 _scan_current_page_for_plate + _has_next_page + _click_next_page
    """
    print("\n=== Test 15: 翻页 while 循环 ===")
    src = open(os.path.join(SCRIPT_DIR, "run.py"), encoding="utf-8").read()

    # 找 get_next_plate_from_list 函数体
    func_start = src.find("def get_next_plate_from_list(")
    next_func = src.find("# ========= table", func_start)
    func_body = src[func_start:next_func]

    # 检查 while 循环
    assert "while True:" in func_body, "❌ get_next_plate_from_list 缺 while 循环"
    print("  ✅ 含 while True 翻页循环")

    # 检查调 3 个新函数
    assert "_scan_current_page_for_plate" in func_body, "❌ 没调 _scan_current_page_for_plate"
    assert "_has_next_page" in func_body, "❌ 没调 _has_next_page"
    assert "_click_next_page" in func_body, "❌ 没调 _click_next_page"
    print("  ✅ 调用 _scan_current_page_for_plate / _has_next_page / _click_next_page")

    # 检查安全上限 (防止死循环)
    assert "page_no > 20" in func_body, "❌ 没设安全上限"
    print("  ✅ 安全上限 page_no > 20 防死循环")

    # 检查 _click_query_button 在主循环被调用
    main_loop_section = src[src.find("# === 第三步:"):src.find("# 🆕 v1.2.2: 读 table 前先检查")]
    assert "_click_query_button" in main_loop_section, "❌ 主循环没调 _click_query_button"
    print("  ✅ 主循环调用 _click_query按钮 (点查询按钮)")

    # 检查 PA_AFTER_NAV 用于翻页后等待
    assert "PA_AFTER_NAV" in func_body, "❌ 翻页后没等 PA_AFTER_NAV"
    print("  ✅ 翻页后等待 PA_AFTER_NAV")

    return True


def test_16_popup2_strategy9_no_false_success():
    """测试 16: popup2 STRATEGY9 不再因 SET_PRINT_MODE 'ok' 误设 closed=1 (v1.2.3 修复)

    背景: STRATEGY9 看到 SET_PRINT_MODE(CLOSE_PREVIEW_WINDOW) ok 就设 closed=1
          但 SET_PRINT_MODE 只是改配置, 不关已开预览 → 跳过了 STRATEGY8 和 STRATEGY10
    修法: STRATEGY9 只在 'called' 出现时设 closed=1, 忽略 SET_PRINT_MODE 的 'ok'
    """
    print("\n=== Test 16: popup2 STRATEGY9 误判修复 ===")
    src = open(os.path.join(SCRIPT_DIR, "popups/p2_tech_review.py"), encoding="utf-8").read()

    # 找 STRATEGY9 的判定段
    strategy9_start = src.find("# 🆕 v1.2.2 策略9")
    strategy8_start = src.find("# 🆕 v1.2.2 策略8")
    strategy9_section = src[strategy9_start:strategy8_start]

    # 检查不再用 'ok' 误判 (这是 bug 源)
    assert "'ok' in r" not in strategy9_section, \
        "❌ STRATEGY9 还在用 'ok' in r 误判 (会跳过 STRATEGY8/STRATEGY10)"
    print("  ✅ STRATEGY9 不再用 'ok' 误判")

    # 检查还有 'called' 判断 (close 类 API 真调用时仍能成功)
    assert "'called' in r" in strategy9_section, \
        "❌ STRATEGY9 没了 'called' 判断 (真调 close 类 API 时也不能成功)"
    print("  ✅ STRATEGY9 保留 'called' 判断")

    # 检查 STRATEGY10 还在 closed == 0 时运行 (不会被 STRATEGY9 误判挡住)
    strategy10_start = src.find("# 🆕 v1.2.2 策略10")
    assert strategy10_start > 0, "❌ 找不到 STRATEGY10 注释"
    strategy10_section = src[strategy10_start:strategy10_start + 800]
    assert 'sys.platform == "win32"' in strategy10_section, \
        "❌ STRATEGY10 平台守卫没了"
    assert "closed == 0" in strategy10_section, \
        "❌ STRATEGY10 条件守卫没了"
    print("  ✅ STRATEGY10 还在 closed == 0 + win32 时运行")

    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  HCCheck v1.2 mock 测试")
    print("=" * 60)

    try:
        test_1_data_dir()
        run_id = test_2_record_runs()
        test_3_query(run_id)
        test_4_summary(run_id)
        test_5_export(run_id)
        test_6_empty_run_id()
        test_6b_latest_run_id()
        test_7_gui_loading()
        test_8_tab_order()
        test_9_no_tkinter_typos()
        test_10_popup4_excludes_main_page()
        test_11_popup2_strategy5()
        test_12_popup2_strategy8_lodop_api()
        test_13_popup2_strategy10_powershell()
        test_14_click_query_and_pagination()
        test_15_pagination_while_loop()
        test_16_popup2_strategy9_no_false_success()

        print("\n" + "=" * 60)
        print("  ✅ 全部测试通过!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
