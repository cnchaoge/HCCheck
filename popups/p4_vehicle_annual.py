"""popup4: 车辆年审(不带挂/带挂流程都用到)

操作:点"年度审验"链接 → 等子页面加载 → 提交 → 选下一处理人
带挂流程的 popup4(年审2)category 是"发起人"而不是"角色"。
"""
import config
from utils import safe, pa, step
from dialog import do_dialog


def handle(popup, context, plate,
           action_type=config.ACTION_SUBMIT_ARCHIVE,
           category=config.CATEGORY_ROLE):
    print("\n  ═══════════════════")
    print("  📋 popup4: 车辆年审")
    print("  ═══════════════════")
    step("车辆年审: 准备点击年度审验")

    # 优先用 popup.frames 遍历找年度审验
    clicked = _click_year_check_via_frames(popup)
    if not clicked:
        clicked = _click_year_check_via_text_in_frames(popup)
    if not clicked:
        # fallback: 用 frame_locator 链
        clicked = _click_year_check_via_frame_locator(popup)

    if not clicked:
        print("  ⚠️ 找不到年度审验链接,手动点击后按回车")
        input("  >>> 点完按回车继续...")
    # 等子页面加载 (年度审验子页面加载后,会显示“检测结果”或其他新内容)
    pa(3)
    print(f"  调试 - 等子页面加载...")
    _wait_for_year_check_subpage(popup)
    pa(2)

    # 提交
    try:
        # 优先 popup.frames 找提交
        submit_clicked = False
        for f in popup.frames:
            try:
                btn = f.get_by_role("button", name=config.BTN_SUBMIT)
                if btn.count() > 0:
                    btn.first.click(force=True)
                    submit_clicked = True
                    print(f"  ✓ frame[{f.name}] 点击提交")
                    break
            except:
                continue
        if not submit_clicked:
            wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
            safe(wf.get_by_role("button", name=config.BTN_SUBMIT), timeout=3000).click()
            print("  ✓ 点击提交")
    except:
        print("  ⚠️ 提交按钮找不到")
    pa(2)
    do_dialog(popup, action_type=action_type, category=category)
    step("车辆年审: 完成 ✅")


def _wait_for_year_check_subpage(popup):
    """等待年度审验子页面加载
    策略: 轮询 _workflow_main frame, 看是否出现“检测”或类似新内容 (区别于初始页)
    """
    try:
        wf_frames = [f for f in popup.frames if f.name == "_workflow_main"]
        if not wf_frames:
            print(f"  调试 - 未找到 _workflow_main frame")
            return False
        wf = wf_frames[0]
        # 轮询 5 次,每次 1 秒
        for i in range(5):
            try:
                text = wf.locator("body").text_content(timeout=2000)
                # 子页面特征: 出现 "检测结果" / "检测项目" / "结论" 等关键词
                if any(kw in text for kw in ["检测结果", "检测项目", "检测结论", "不合格项", "综检结果"]):
                    print(f"  ✓ 年度审验子页面已加载 (attempt={i})")
                    return True
            except:
                pass
            pa(1)
        print(f"  ⚠️ 年度审验子页面加载超时,可能未跳转")
    except Exception as e:
        print(f"  调试 - wait_for_year_check_subpage 异常: {e}")
    return False


def _click_year_check_via_frames(popup):
    """策略1: 遍历 popup.frames 找 link 角色 + JS click"""
    for f in popup.frames:
        for txt in config.YEAR_CHECK_TEXTS:
            try:
                link = f.get_by_role("link", name=txt)
                if link.count() > 0:
                    # 优先用 JS click (触发浏览器真实跳转)
                    link.first.evaluate("el => el.click()")
                    print(f"  ✓ frame[{f.name}] JS-click link'{txt}'")
                    return True
            except:
                continue
            try:
                link = f.locator(f'a:has-text("{txt}")')
                if link.count() > 0:
                    link.first.evaluate("el => el.click()")
                    print(f"  ✓ frame[{f.name}] JS-click a:has-text'{txt}'")
                    return True
            except:
                continue
    return False


def _click_year_check_via_text_in_frames(popup):
    """策略2: 遍历 popup.frames 找文字 + JS click"""
    for f in popup.frames:
        for txt in config.YEAR_CHECK_TEXTS:
            try:
                el = f.locator(f'text="{txt}"')
                if el.count() > 0:
                    el.first.evaluate("el => el.click()")
                    print(f"  ✓ frame[{f.name}] JS-click text'{txt}'")
                    return True
            except:
                continue
    return False


def _click_year_check_via_frame_locator(popup):
    """策略3: fallback 到 frame_locator 链 + JS click"""
    wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
    conn = wf.frame_locator(config.SELECTOR_IFRAME_IFRAME_CONTENT)
    for sel_text in config.YEAR_CHECK_TEXTS:
        try:
            el = conn.locator(f'a:has-text("{sel_text}")')
            if el.count() > 0:
                el.first.evaluate("el => el.click()")
                print(f"  ✓ frame_locator JS-click a:has-text'{sel_text}'")
                return True
        except:
            continue
        try:
            el = conn.get_by_role("link", name=sel_text)
            if el.count() > 0:
                el.first.evaluate("el => el.click()")
                print(f"  ✓ frame_locator JS-click link'{sel_text}'")
                return True
        except:
            continue
    return False
