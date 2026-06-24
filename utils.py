"""运管站货车审验 - 通用工具函数

所有 popup 共享的安全/便利函数,避免重复代码。
"""
import sys
import time

try:
    import pyperclip
except ImportError:
    pyperclip = None
    print("⚠️ pyperclip 未安装,用 Playwright fill 替代")

from playwright.sync_api import TimeoutError as PWTimeout

import config


def safe(loc, timeout=15000):
    """等待元素可见,超时抛 PWTimeout"""
    try:
        loc.wait_for(state="visible", timeout=timeout)
        return loc
    except PWTimeout:
        raise


def wait_until(condition, timeout=None, poll=None, description="", screenshot_page=None):
    """轮询 condition 直到返回真值或超时（智能等待，替代猜时间 pa()）

    Args:
        condition: callable（每次调用返回 truthy/falsy）
                   或 Playwright Locator（自动用 wait_for(state="visible")）
        timeout:   超时秒数，默认 config.WAIT_UNTIL_TIMEOUT
        poll:      轮询间隔秒数，默认 config.WAIT_UNTIL_POLL
        description: 失败时日志/错误信息用的描述
        screenshot_page: 失败时截图用的 page（可选）

    Returns:
        condition 的返回值（callable 时）/ Locator 本身（Locator 时）

    Raises:
        TimeoutError: 超时未满足

    Examples:
        # 等元素可见（Playwright Locator）
        wait_until(page.locator("a:has-text('年度审验')"), timeout=8, description="年度审验链接")

        # 等表格有行（callable）
        wait_until(lambda: table.locator("tbody tr").count() >= 1, description="工作台表格")

        # 等弹窗消失（callable + 失败截图）
        wait_until(lambda: popup.is_visible(), timeout=5, description="弹窗关闭",
                   screenshot_page=page)
    """
    if timeout is None:
        timeout = config.WAIT_UNTIL_TIMEOUT
    if poll is None:
        poll = config.WAIT_UNTIL_POLL

    desc = f" ({description})" if description else ""

    # 路径 A：Playwright Locator（用原生 wait_for，精度高）
    if hasattr(condition, 'wait_for') and callable(getattr(condition, 'wait_for', None)):
        try:
            condition.wait_for(state="visible", timeout=timeout * 1000)
            return condition
        except PWTimeout:
            if screenshot_page is not None:
                screenshot_on_error(screenshot_page, f"wait_{description}" if description else "wait")
            raise TimeoutError(f"等待元素超时{desc}（{timeout}s）")

    # 路径 B：callable（轮询）
    if not callable(condition):
        raise TypeError(
            f"wait_until: condition 必须是 callable 或 Playwright Locator,实际: {type(condition).__name__}"
        )

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = condition()
            if result:
                return result
        except Exception:
            # 单次轮询失败不算超时（元素可能还没渲染）
            pass
        time.sleep(poll)

    if screenshot_page is not None:
        screenshot_on_error(screenshot_page, f"wait_{description}" if description else "wait")
    raise TimeoutError(f"等待条件超时{desc}（{timeout}s）")


def wait_until_not(condition, timeout=None, poll=None, description="", screenshot_page=None):
    """轮询 condition 直到返回 falsy 或超时（智能等待"消失"）

    用法同 wait_until，区别：等待 condition 变为 falsy。
    Locator 时内部用 wait_for(state="hidden")；callable 时轮询 falsy 或抛异常。

    Examples:
        # 等弹窗消失（Playwright Locator）
        wait_until_not(page.locator(".popup"), timeout=5, description="弹窗关闭")

        # 等列表为空（callable）
        wait_until_not(lambda: table.locator("tr").count() > 0, description="列表清空")
    """
    if timeout is None:
        timeout = config.WAIT_UNTIL_TIMEOUT
    if poll is None:
        poll = config.WAIT_UNTIL_POLL

    desc = f" ({description})" if description else ""

    # 路径 A：Playwright Locator（用原生 wait_for hidden）
    if hasattr(condition, 'wait_for') and callable(getattr(condition, 'wait_for', None)):
        try:
            condition.wait_for(state="hidden", timeout=timeout * 1000)
            return True
        except PWTimeout:
            if screenshot_page is not None:
                screenshot_on_error(screenshot_page, f"waitnot_{description}" if description else "waitnot")
            raise TimeoutError(f"等待元素消失超时{desc}（{timeout}s）")

    # 路径 B：callable（轮询）
    if not callable(condition):
        raise TypeError(
            f"wait_until_not: condition 必须是 callable 或 Playwright Locator,实际: {type(condition).__name__}"
        )

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            result = condition()
            if not result:
                return True
        except Exception:
            # 抛异常也算"消失"（元素已从 DOM 移除，is_visible 抛错）
            return True
        time.sleep(poll)

    if screenshot_page is not None:
        screenshot_on_error(screenshot_page, f"waitnot_{description}" if description else "waitnot")
    raise TimeoutError(f"等待条件消失超时{desc}（{timeout}s）")


def pa(t=config.SLOW):
    """sleep 一会儿,t 不传则走 config.SLOW"""
    time.sleep(t)


def step(msg):
    """Debug 模式:每个关键节点提示,按 y 才继续
    非 DEBUG 模式下直接返回,不阻塞流程
    """
    if not config.DEBUG:
        return
    print(f"\n── [{msg}] ──")
    while True:
        inp = input("  按 [y]继续  [n]跳过  [q]退出: ").strip().lower()
        if inp == "y":
            break
        elif inp == "n":
            print("    跳过")
            break
        elif inp == "q":
            print("    退出")
            sys.exit(0)


def paste_into(locator, text):
    """优先用剪贴板粘贴(绕过 input 事件),pyperclip 不可用时 fallback fill"""
    if pyperclip:
        pyperclip.copy(text)
        pa(0.15)
        locator.click()
        pa(0.1)
        locator.press("ControlOrMeta+a")
        pa(0.1)
        locator.press("ControlOrMeta+v")
    else:
        locator.fill(text)
    pa(0.4)


def screenshot_on_error(page, label):
    """出错时截图到当前目录,失败也不影响流程"""
    try:
        ts = time.strftime("%H%M%S")
        path = f"err_{label}_{ts}.png"
        page.screenshot(path=path)
        print(f"  📸 {path}")
    except Exception as sce:
        print(f"  ⚠️ 截图失败: {sce}")
