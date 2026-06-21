"""popup3: 业务岗位审核(不带挂流程) / 业务岗位审核(带挂流程)

不带挂流程:popup3 = 业务岗位审核 → 提交 → 选"提交车辆年审"
带挂流程:popup2 = 业务岗位审核 → 提交 → 选"提交归档"

两流程差异仅在 action_type,其它逻辑一致。
"""
import config
from utils import safe, pa, step
from dialog import do_dialog


def handle(popup, context, plate, action_type=config.ACTION_SUBMIT_VEHICLE_ANNUAL):
    print("\n  ═══════════════════")
    print("  📋 popup3: 业务岗位审核")
    print("  ═══════════════════")
    step("业务岗位审核: 准备提交")
    wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
    try:
        safe(wf.get_by_role("button", name=config.BTN_SUBMIT), timeout=3000).click()
        print("  ✓ 点击提交")
    except:
        print("  ⚠️ 提交按钮找不到,尝试在流程页面中点车牌")
        _click_plate_link_in_wf(context, wf, plate)
    pa(2)
    do_dialog(popup, action_type=action_type, category=config.CATEGORY_ROLE)
    step("业务岗位审核: 完成 ✅")


def _click_plate_link_in_wf(context, wf, plate):
    """在 workflow 页面里点车牌号链接(仅限弹窗内,不搜主页面)"""
    print(f"  找车牌 {plate} 链接")
    try:
        link = wf.get_by_role("link", name=plate)
        safe(link, timeout=3000).click()
        print(f"  wf frame 中找到并点击")
        return True
    except:
        pass
    # 只搜弹窗(popup)内的 frame,不搜主页面
    for f in context.pages[-1].frames:
        try:
            link = f.locator(f'a:has-text("{plate}")')
            if link.count() > 0:
                link.first.click()
                print(f"  popup frame[{f.name}] 找到并点击")
                return True
        except:
            pass
    print("  找不到车牌链接")
    return False
