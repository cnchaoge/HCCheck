"""popup1: 车辆检测(不带挂/带挂流程的第一站)

操作:点提交 + 处理选下一处理人弹窗(默认配置)。
最简单的一个 popup,因为不涉及打印、年度审验等子操作。
"""
import config
from utils import safe, pa, step
from dialog import do_dialog


def handle(popup, plate):
    print("\n  ═══════════════════")
    print("  📋 popup1: 车辆检测")
    print("  ═══════════════════")

    # 调试: 打印 popup 信息
    print(f"  🔍 popup URL: {popup.url[:80]}")
    print(f"  🔍 popup frames: {[f.name for f in popup.frames if f.name]}")

    step("车辆检测: 准备提交")
    # 优先用 popup.frames 直接访问 _workflow_main
    wf = None
    for f in popup.frames:
        if f.name == "_workflow_main":
            wf = f
            break
    if wf is None:
        # fallback: 用 frame_locator
        wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
    try:
        btn = wf.get_by_role("button", name=config.BTN_SUBMIT)
        btn.wait_for(state="visible", timeout=10000)
        btn.click()
        print(f"  ✓ 点击提交")
    except Exception as e:
        print(f"  ⚠️ 提交按钮点不上 ({e}), 可能带挂流程需要手动选动作类型")
        print(f"  👆 请手动点提交后按回车")
        input(">>> 点完后按回车继续...")
    pa(2)
    do_dialog(popup, action_type=None, category=config.CATEGORY_ROLE)
    step("车辆检测: 完成 ✅")
