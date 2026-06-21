"""运管站货车审验 - 验收检查脚本

用法: python check.py
返回 0 = 全部通过,1 = 有失败
"""
import os
import sys
import re
import importlib


REQUIRED_FILES = [
    "config.py",
    "utils.py",
    "dialog.py",
    "run.py",
    "popups/__init__.py",
    "popups/p1_vehicle_check.py",
    "popups/p2_tech_review.py",
    "popups/p3_business_review.py",
    "popups/p4_vehicle_annual.py",
    "popups/p5_archive.py",
]

POPUP_HANDLERS = [
    "handle_vehicle_check",
    "handle_tech_review",
    "handle_business_review",
    "handle_vehicle_annual",
    "handle_archive",
]

CONFIG_KEYS_REQUIRED = [
    "DEBUG", "SLOW", "MAX_FAIL", "SINGLE_RUN", "HEADLESS", "URL",
    "PLATE_RE", "MENU_FOR_NORMAL", "MENU_FOR_TRAILER",
    "MENU_WORKBENCH", "MENU_NORMAL_REVIEW",
    "STEP_VEHICLE_CHECK", "STEP_TECH_REVIEW", "STEP_BUSINESS_REVIEW",
    "STEP_VEHICLE_ANNUAL", "STEP_ARCHIVE",
    "NODE_VEHICLE_CHECK", "NODE_TECH_REVIEW", "NODE_BUSINESS_REVIEW",
    "NODE_VEHICLE_ANNUAL", "NODE_ARCHIVE",
    "ACTION_SUBMIT_TECH_REVIEW", "ACTION_SUBMIT_VEHICLE_ANNUAL",
    "ACTION_SUBMIT_ARCHIVE", "ACTION_SUBMIT_YEAR_CHECK",
    "CATEGORY_ROLE", "CATEGORY_INITIATOR",
    "SELECTOR_FRAME_CONTENTS", "SELECTOR_FRAME_MAIN_KEF",
    "SELECTOR_FRAME_WORKFLOW_MAIN", "SELECTOR_IFRAME_SUBMIT_DIAG",
    "SELECTOR_IFRAME_IFRAME_CONTENT", "SELECTOR_IFRAME_SUBMIT_DIAGCL",
    "SELECTOR_FRAME_FIND_FRAME_KF", "SELECTOR_IFRAME_I_FRAME_USER",
    "SELECTOR_TREE_EXPAND",
    "BTN_SUBMIT", "BTN_COMPLETE", "BTN_START_TASK", "BTN_OK",
    "BTN_QUERY", "BTN_SELECT", "BTN_ADD", "BTN_SELECT_ALL", "BTN_CLOSE",
    "FLOW_TYPE_ID", "FLOW_TRAILER_MARKER", "FLOW_NORMAL_MARKER",
    "YEAR_CHECK_TEXTS", "DETECT_YEAR_CHECK", "DETECT_PRINT",
    "NAV_TREE_SELECTORS",
]

# popups/ 里"选择器位置"不应该出现的硬编码(都已抽到 config)
FORBIDDEN_IN_POPUPS = [
    "提交业务岗位审核", "提交归档", "提交车辆年审", "提交年审",
    "角色", "发起人",
    "车辆检测", "技术岗位审核", "业务岗位审核", "车辆年审", "归档",
    "frame[name=", "iframe[name=",
    "#contents", "#main_kef",
    "普货审验", "工作台",
    "年度审验", "年度審驗", "年度检验",
    "打印综合性能", "综合性能检测", "打印告知单",
]

# 选择器函数调用 — 只有这些位置的字符串字面量才算"硬编码"
# 匹配 frame_locator / .locator / get_by_role / select_option 等的字符串参数
SELECTOR_REGEX = re.compile(
    r"""(?:"""
    r"""frame_locator\(["']([^"']+)["']\)"""
    r"""|\.locator\(["']([^"']+)["']\)"""
    r"""|get_by_role\(["']([^"']+)["']"""
    r"""|get_by_role\([^,)]+,\s*name=["']([^"']+)["']"""
    r"""|select_option\(label=["']([^"']+)["']"""
    r"""|select_option\(["']([^"']+)["']"""
    r"""|\.press\(["']([^"']+)["']\)"""
    r"""|\.fill\(["']([^"']+)["']\)"""
    r""")""",
    re.VERBOSE,
)

DOCSTRING_RE = re.compile(r'(\"\"\".*?\"\"\"|\'\'\'.*?\'\'\')', re.DOTALL)


def check(label, ok, detail=""):
    mark = "✅" if ok else "❌"
    msg = f"  {mark} {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return ok


def strip_docstrings(path):
    with open(path) as fp:
        return DOCSTRING_RE.sub('""""""', fp.read())


def find_selector_hits(code, forbidden_strings):
    """扫一遍源码,返回所有命中 forbidden 的位置 [(file, line_no, content), ...]"""
    hits = []
    for i, line in enumerate(code.splitlines(), 1):
        # 跳过 print 语句(print 是给人看的日志,不算硬编码)
        if re.match(r'^\s*print\(', line):
            continue
        # 跳过注释行
        if line.strip().startswith("#"):
            continue
        for m in SELECTOR_REGEX.finditer(line):
            for grp in m.groups():
                if grp and any(f in grp for f in forbidden_strings):
                    hits.append((i, line.strip()))
                    break
    return hits


def main():
    all_ok = True
    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)

    print("=" * 50)
    print("  验收检查")
    print("=" * 50)

    # A. 文件结构
    print("\n[A] 文件结构")
    for f in REQUIRED_FILES:
        all_ok &= check(f"{f} 存在", os.path.isfile(f))

    # B. import 测试
    print("\n[B] import 测试(无循环引用)")
    for mod in ["config", "utils", "dialog"]:
        try:
            importlib.import_module(mod)
            all_ok &= check(f"import {mod}", True)
        except Exception as e:
            all_ok &= check(f"import {mod}", False, str(e))

    try:
        from popups import __all__ as popups_all
        ok = set(popups_all) == set(POPUP_HANDLERS)
        all_ok &= check("popups export 5 个 handler", ok, f"got {popups_all}")
    except Exception as e:
        all_ok &= check("popups export", False, str(e))

    # C. config 常量
    print("\n[C] config.py 常量")
    try:
        cfg = importlib.import_module("config")
        for name in CONFIG_KEYS_REQUIRED:
            all_ok &= check(f"config.{name}", hasattr(cfg, name))
    except Exception as e:
        all_ok &= check("config 加载", False, str(e))

    # D. 行数
    print("\n[D] 文件行数")
    if os.path.isfile("run.py"):
        with open("run.py") as fp:
            lines = len(fp.readlines())
        all_ok &= check("run.py ≤ 750 行", lines <= 750, f"实际 {lines} 行")

    # E. popups/ 抽硬编码审计 — 只查选择器位置,跳过 print 和注释
    print("\n[E] popups/ 中不应出现的硬编码(仅查选择器位置)")
    for forbidden in FORBIDDEN_IN_POPUPS:
        first_hit = ""
        for root, _, files in os.walk("popups"):
            for fn in files:
                if not fn.endswith(".py"):
                    continue
                full = os.path.join(root, fn)
                code = strip_docstrings(full)
                hits = find_selector_hits(code, [forbidden])
                if hits:
                    line_no, content = hits[0]
                    first_hit = f"{full}:{line_no}: {content[:80]}"
                    break
            if first_hit:
                break
        all_ok &= check(f"无 '{forbidden}'", not first_hit, first_hit)

    print("\n" + "=" * 50)
    print("  通过 ✅" if all_ok else "  失败 ❌")
    print("=" * 50)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
