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
