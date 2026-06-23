"""运管站货车审验 - 选下一处理人弹窗处理

所有 popup 处理完自己那一步后,都通过 do_dialog 调起"选择下一处理人"弹窗。

修复历史:
- 2026-06-23: 强化等待逻辑
  - 选完动作类型后,显式等"全选"和"确定"按钮可见再点
  - 提高确定按钮超时 (5s → 8s)
  - 全选链接等待延长 (3s → 5s)
"""
import config
from utils import safe, pa


def do_dialog(popup, action_type=None, category=config.CATEGORY_ROLE, do_full_select=True):
    """
    处理"选下一处理人"弹窗
    经验:默认选项即可,通常只需要 全选 + 确定

    Args:
        popup: workflow 弹窗 page
        action_type: 弹窗里"动作类型"下拉要选的关键词(None 表示不改默认值)
        category: 弹窗里"用户分类"下拉要选的值(默认"角色")
        do_full_select: 是否点"全选"(默认 True)
    """
    wf  = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)
    sub = wf.frame_locator(config.SELECTOR_IFRAME_SUBMIT_DIAG)

    # 选动作类型(部分 popup 需要改默认值)
    if action_type:
        try:
            sel = sub.locator("select").first
            sel.wait_for(state="visible", timeout=5000)
            opts = sel.locator("option")
            match = False
            for o in range(opts.count()):
                if action_type in opts.nth(o).text_content():
                    sel.select_option(index=o)
                    print(f"  弹窗: 动作类型→{action_type}")
                    match = True
                    break
            if not match:
                print(f"  弹窗: 动作类型默认已是正确值")
            # 选完动作类型后,等弹窗刷新(用户列表重新加载)
            pa(1.5)
        except Exception as e:
            print(f"  弹窗: 动作类型跳过({e})")

    # 选处理人类别
    try:
        sel = sub.locator("select").nth(1)
        if sel.count() > 0:
            sel.wait_for(state="visible", timeout=5000)
            sel.select_option(label=category)
            print(f"  弹窗: 处理人类别→{category}")
            pa(1)
    except:
        pass
    pa(0.5)

    # 全选 — 显式等可见
    if do_full_select:
        try:
            uf = sub.frame_locator(config.SELECTOR_IFRAME_I_FRAME_USER)
            sel_all = uf.get_by_role("link", name=config.BTN_SELECT_ALL)
            sel_all.wait_for(state="visible", timeout=5000)
            sel_all.click()
            print("  弹窗: 全选")
            pa(0.5)
        except Exception as e:
            print(f"  弹窗: 全选跳过(可能已默认全选) ({e})")

    # 确定 — 显式等可见
    try:
        ok_btn = sub.get_by_role("button", name=config.BTN_OK)
        ok_btn.wait_for(state="visible", timeout=8000)
        ok_btn.click()
        print("  弹窗: 确定")
        pa(1.5)
    except Exception as e:
        print(f"  弹窗: 确定按钮找不到({e})")
        raise
