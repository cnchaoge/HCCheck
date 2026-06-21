"""popup2: 技术岗位审核(不带挂流程)

操作:点车牌链接(让打印链接显示) → 4 种策略找"打印告知单" → 关打印预览 → 提交 → 选业务岗位审核

不带挂流程:popup2 = 技术岗位审核(带打印)
带挂流程:popup2 = 业务岗位审核(跳过打印,直接提交) — 用 p3 的 handler
"""
import config
from utils import safe, pa, step
from dialog import do_dialog

# 打印告知单的 4 种写法(业务术语同义变体,留使用方)
PRINT_LINK_TEXTS = [
    "打印综合性能检测告知单",
    "打印综合性能测试告知单",
    "综合性能检测告知单",
    "打印告知单",
]

# 打印链接所在 iframe 的不同写法(系统偶有变化)
PRINT_LINK_FRAME_SELECTORS = [
    "iframe[name='_Iframe_content']",
    "iframe[name='_IframeContent']",
    "iframe[id='_Iframe_content']",
    "frame[name='_Iframe_content']",
]

# 打印链接的 onclick JS 函数名
PRINT_ONCLICK_KEY = "doPrintDetect"


def _close_print_preview(context):
    """关闭 Lodop 打印预览
    Lodop 预览可能是:
    1. 独立的新窗口/标签页 - 遍历 context.pages 关闭
    2. 嵌入在业务弹窗里的 HTML 元素 - 用 JS 查找 LODOP 对象关闭
    3. 嵌入在业务弹窗里的隐藏 iframe - 遍历所有 frame 关闭
    """
    closed = 0

    # 策略1: 遍历 context.pages 找独立窗口
    for p in context.pages:
        try:
            url = (p.url or "").lower()
            title = ""
            try:
                title = p.title() or ""
            except:
                pass
            # Lodop 预览窗口特征
            is_preview = (
                "lodop" in url or
                "print_preview" in url or
                "printpreview" in url or
                "打印预览" in title or
                "lodop" in title.lower() or
                "caosoft" in url
            )
            if is_preview:
                try:
                    p.get_by_role("button", name="关闭").first.click()
                    print(f"  ✓ 关闭按钮: {title[:30]}")
                except:
                    pass
                try:
                    p.close()
                    closed += 1
                    print(f"  ✓ 关闭打印预览窗口")
                except:
                    pass
        except:
            continue

    # 策略2: 在每个业务页面里查找 LODOP 预览并关闭
    if closed == 0:
        for p in context.pages:
            try:
                # 尝试 JS 调用 LODOP 关闭预览, 并移除 lodop 预览遮罩
                result = p.evaluate("""() => {
                    let count = 0;
                    try {
                        // 查找并移除 lodop 预览容器
                        const selectors = [
                            '[id*="LODOP"]',
                            '[id*="lodop"]',
                            '[class*="LODOP"]',
                            '[class*="lodop"]',
                            '[id*="preview"]',
                            '[class*="preview"]',
                            '.ui-popup',
                            '.ui-popup-backdrop',
                        ];
                        for (const sel of selectors) {
                            const els = document.querySelectorAll(sel);
                            for (const e of els) {
                                try { e.remove(); count++; } catch(err) {}
                            }
                        }
                        // 移除所有 iframe (包括 lodop 预览的)
                        const iframes = document.querySelectorAll('iframe');
                        for (const f of iframes) {
                            const src = (f.src || '').toLowerCase();
                            if (src.includes('lodop') || src.includes('preview') || src.includes('print')) {
                                try { f.remove(); count++; } catch(err) {}
                            }
                        }
                        // 遍历所有 frame 移除 lodop 元素
                        const frames = document.querySelectorAll('iframe, frame');
                        for (const fr of frames) {
                            try {
                                const doc = fr.contentDocument || fr.contentWindow.document;
                                if (doc) {
                                    const subSelectors = ['[id*="LODOP"]', '[class*="LODOP"]', '.ui-popup', '.ui-popup-backdrop'];
                                    for (const sel of subSelectors) {
                                        const els = doc.querySelectorAll(sel);
                                        for (const e of els) {
                                            try { e.remove(); count++; } catch(err) {}
                                        }
                                    }
                                }
                            } catch(err) {}
                        }
                    } catch(e) {}
                    return count;
                }""")
                if result and result > 0:
                    print(f"  ✓ JS 移除 {result} 个 Lodop/遮罩元素")
                    closed = 1
                    break
            except:
                continue

    # 策略3: 按 Escape 键关闭可能还在的弹窗
    if closed == 0:
        for p in context.pages:
            try:
                p.keyboard.press("Escape")
            except:
                pass

    if closed == 0:
        print(f"  ⚠️ 未找到可关闭的打印预览")


def handle(popup, context, main_page, plate):
    print("\n  ═══════════════════")
    print("  📋 popup2: 技术岗位审核")
    print("  ═══════════════════")
    step("技术岗位审核: 准备打印告知单")
    wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)

    # 先点车牌链接(让打印链接显示)
    try:
        plate_link = wf.get_by_role("link", name=plate)
        safe(plate_link, timeout=3000).click()
        print("  ✓ 点击车牌链接")
        pa(1)
    except:
        # 没有车牌链接就跳过
        pass

    # 4 种策略找打印链接
    if not _click_print_link_v1(wf, popup):
        if not _click_print_link_v2(popup):
            if not _click_print_link_v3(popup):
                # 策略4: 人工兜底
                print("  ⚠️ 自动点击打印链接失败")
                print("  👆 请手动点击 [打印综合性能检测告知单] 后按回车")
                input(">>> 点完后按回车继续...")

    # 关闭 Lodop 打印预览 (可能是新窗口/标签页)
    pa(2)
    _close_print_preview(context)
    pa(2)
    step("技术岗位审核: 打印完成,准备提交")

    # 提交 + 选下一处理人
    try:
        safe(wf.get_by_role("button", name=config.BTN_SUBMIT), timeout=3000).click()
        pa(2)
        do_dialog(
            popup,
            action_type=config.ACTION_SUBMIT_TECH_REVIEW,
            category=config.CATEGORY_ROLE,
        )
    except:
        print("  ⚠️ 提交按钮找不到")
    step("技术岗位审核: 完成 ✅")


def _click_print_link_v1(wf, popup):
    """策略1: frame_locator 经典方式"""
    for fname in PRINT_LINK_FRAME_SELECTORS:
        try:
            cont = wf.frame_locator(fname)
            for txt in PRINT_LINK_TEXTS:
                try:
                    el = cont.locator(f'text="{txt}"').first
                    safe(el, timeout=3000)
                    el.dispatch_event("click")  # dispatch_event 绕过遮挡
                    print(f"  [V1] dispatch_event 点击 '{txt}' 成功")
                    return True
                except:
                    try:
                        el = cont.get_by_text(txt).first
                        safe(el, timeout=2000)
                        el.click(force=True)
                        print(f"  [V1] force-click '{txt}' 成功")
                        return True
                    except:
                        continue
            # 尝试 onclick 定位
            try:
                el = cont.locator(f"a[onclick*='{PRINT_ONCLICK_KEY}']").first
                safe(el, timeout=2000)
                el.dispatch_event("click")
                print(f"  [V1] onclick 定位 + dispatch 成功")
                return True
            except:
                pass
        except:
            continue
    print(f"  [V1] 失败")
    return False


def _click_print_link_v2(popup):
    """策略2: 遍历 popup 的所有 frame"""
    for f in popup.frames:
        try:
            el = f.locator(f"a[onclick*='{PRINT_ONCLICK_KEY}']").first
            if el.count() > 0:
                el.dispatch_event("click")
                print(f"  [V2] frame[{f.name}] onclick 定位 + dispatch")
                return True
        except:
            pass
    # 文本搜索
    for f in popup.frames:
        try:
            el = f.locator('a:has-text("打印综合性能检测告知单")').first
            if el.count() > 0:
                el.dispatch_event("click")
                print(f"  [V2] frame[{f.name}] 文本定位 + dispatch")
                return True
        except:
            pass
    print(f"  [V2] 失败")
    return False


def _click_print_link_v3(popup):
    """策略3: 在 popup 的每个 frame 里用 document.querySelector 找到链接后 click()"""
    for f in popup.frames:
        try:
            ok = f.evaluate(f'''() => {{
                const a = document.querySelector('a[onclick*="{PRINT_ONCLICK_KEY}"]');
                if (a) {{ a.click(); return true; }}
                return false;
            }}''')
            if ok:
                print(f"  [V3] frame[{f.name}] querySelector + click")
                return True
        except:
            continue
    # 全文字匹配
    for f in popup.frames:
        try:
            ok = f.evaluate('''() => {
                const links = document.querySelectorAll('a');
                for (const a of links) {
                    if (a.innerText.indexOf('打印') !== -1 && a.innerText.indexOf('告知') !== -1) {
                        a.click();
                        return true;
                    }
                }
                return false;
            }''')
            if ok:
                print(f"  [V3] 全文匹配 + click")
                return True
        except:
            continue
    print(f"  [V3] 失败")
    return False
