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
