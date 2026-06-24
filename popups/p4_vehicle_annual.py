"""popup4: 车辆年审(不带挂/带挂流程都用到)

操作:点车牌链接(让年度审验链接显示) → 3 种策略找"年度审验" → 等子页面加载 → 提交 → 选下一处理人
带挂流程的 popup4(年审2)category 是"发起人"而不是"角色"。

修复历史:
- 2026-06-23: 加 wait_for + retry + 异常处理 input
  - 仿 popup2 先点车牌链接(让年度审验链接显示)
  - 每个策略等元素 visible 后再点
  - 子页面加载等待加长到 10s
  - input() 包 try/except 防止 stdin 关闭崩
"""
import config
from utils import safe, pa, step, wait_until
from dialog import do_dialog


def handle(popup, context, plate,
           action_type=config.ACTION_SUBMIT_ARCHIVE,
           category=config.CATEGORY_ROLE):
    print("\n  ═══════════════════")
    print("  📋 popup4: 车辆年审")
    print("  ═══════════════════")
    step("车辆年审: 准备点击年度审验")

    # 🆕 先点车牌链接(让"年度审验"链接显示 — 跟 popup2 一样的 UI 模式)
    _click_plate_link(popup, plate)

    # 用 3 个策略找"年度审验"链接
    clicked = _click_year_check(popup, max_retry=2)

    if not clicked:
        print("  ⚠️ 找不到年度审验链接,手动点击后按回车")
        try:
            input("  >>> 点完按回车继续...")
        except (ValueError, EOFError, OSError):
            print("  ⚠️ stdin 不可用 (I/O closed),跳过本步骤")
            # 仍然尝试提交,让流程尽量往下走
            pass

    # 点完链接后短间隔,让页面就位
    pa(2)

    # 提交
    try:
        submit_clicked = False
        for f in popup.frames:
            try:
                btn = f.get_by_role("button", name=config.BTN_SUBMIT)
                if btn.count() > 0:
                    btn.first.wait_for(state="visible", timeout=5000)
                    btn.first.click(force=True)
                    submit_clicked = True
                    print(f"  ✓ frame[{f.name}] 点击提交")
                    break
            except:
                continue
        if not submit_clicked:
            wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
            safe(wf.get_by_role("button", name=config.BTN_SUBMIT), timeout=5000).click()
            print("  ✓ 点击提交")
    except Exception as e:
        print(f"  ⚠️ 提交按钮找不到 ({e})")
    pa(2)
    do_dialog(popup, action_type=action_type, category=category)
    step("车辆年审: 完成 ✅")


def _click_plate_link(popup, plate):
    """点车牌链接(让"年度审验"链接显示,跟 popup2 一样)"""
    try:
        wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
        plate_link = wf.get_by_role("link", name=plate)
        if plate_link.count() > 0:
            plate_link.first.click()
            print("  ✓ 点击车牌链接")
            pa(1.5)
    except:
        # 没有车牌链接就跳过(不影响主流程)
        pass


def _any_year_check_visible(popup):
    """检查 popup 任何 frame 里是否有"年度审验"链接可见（轮询条件用）

    复用 3 个策略的 selector，每个 get_by_role / locator 都包 try/except
    元素不存在 / 不可见时返回 False，让 wait_until 继续轮询。
    """
    try:
        for f in popup.frames:
            for txt in config.YEAR_CHECK_TEXTS:
                try:
                    if f.get_by_role("link", name=txt).first.is_visible():
                        return True
                except Exception:
                    pass
                try:
                    if f.locator(f'a:has-text("{txt}")').first.is_visible():
                        return True
                except Exception:
                    pass
                try:
                    if f.locator(f'text="{txt}"').first.is_visible():
                        return True
                except Exception:
                    pass
    except Exception:
        pass
    return False


def _click_year_check(popup, max_retry=2):
    """点"年度审验"链接,带重试和智能等待（替代 pa(3)）"""
    for attempt in range(max_retry):
        # 3 个策略依次尝试
        clicked = _click_year_check_via_frames(popup)
        if not clicked:
            clicked = _click_year_check_via_text_in_frames(popup)
        if not clicked:
            clicked = _click_year_check_via_frame_locator(popup)

        if clicked:
            return True

        # 没点到,用 wait_until 智能等待（轮询到链接可见或超时），替代原来猜时间的 pa(3)
        if attempt < max_retry - 1:
            print(f"  调试 - 第 {attempt + 1} 次未找到,智能等待链接...")
            try:
                wait_until(
                    lambda: _any_year_check_visible(popup),
                    timeout=3,
                    poll=0.5,
                    description="年度审验链接可见",
                )
            except TimeoutError:
                # 超时仍不可见，下一轮重试接管
                pass

    return False


def _click_year_check_via_frames(popup):
    """策略1: 遍历 popup.frames 找 link 角色,等可见再点"""
    for f in popup.frames:
        for txt in config.YEAR_CHECK_TEXTS:
            try:
                link = f.get_by_role("link", name=txt)
                if link.count() > 0:
                    link.first.wait_for(state="visible", timeout=5000)
                    link.first.evaluate("el => el.click()")
                    print(f"  ✓ frame[{f.name}] JS-click link'{txt}'")
                    return True
            except:
                continue
            try:
                link = f.locator(f'a:has-text("{txt}")')
                if link.count() > 0:
                    link.first.wait_for(state="visible", timeout=5000)
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
                    el.first.wait_for(state="visible", timeout=5000)
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
                el.first.wait_for(state="visible", timeout=5000)
                el.first.evaluate("el => el.click()")
                print(f"  ✓ frame_locator JS-click a:has-text'{sel_text}'")
                return True
        except:
            continue
        try:
            el = conn.get_by_role("link", name=sel_text)
            if el.count() > 0:
                el.first.wait_for(state="visible", timeout=5000)
                el.first.evaluate("el => el.click()")
                print(f"  ✓ frame_locator JS-click link'{sel_text}'")
                return True
        except:
            continue
    return False
