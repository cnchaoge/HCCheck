"""popup5: 归档(流程最后一步,两流程都用)

操作:点"完成"按钮 → 等弹窗 → 点"确定" → 完成
"""
import config
from utils import safe, pa, step


def handle(popup, main_page, plate):
    print("\n  ═══════════════════")
    print("  📋 popup5: 归档")
    print("  ═══════════════════")
    step("归档: 准备点击完成")
    wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
    safe(wf.get_by_role("button", name=config.BTN_COMPLETE)).click()

    # 点"确定"弹窗(可能多个,由 dialog 监听器和元素点击双重保障)
    pa(2)
    for i in range(3):
        try:
            btn = wf.get_by_role("button", name=config.BTN_OK)
            safe(btn, timeout=2000).click()
            print(f"  归档弹窗: 确定({i+1})")
            pa(1)
        except:
            break

    pa(2)
    print(f"  ✓ 归档完成 🎉")
    step("归档: 完成 ✅")
