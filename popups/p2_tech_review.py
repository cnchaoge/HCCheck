"""popup2: 技术岗位审核(不带挂流程)

操作:点车牌链接(让打印链接显示) → 4 种策略找"打印告知单" → 关打印预览 → 提交 → 选业务岗位审核

不带挂流程:popup2 = 技术岗位审核(带打印)
带挂流程:popup2 = 业务岗位审核(跳过打印,直接提交) — 用 p3 的 handler

修复历史:
- 2026-06-23: 强化打印预览关闭
  - 追踪 pages_before 找出新开的 page 关闭
  - 加 CLodop / C-Lodop / caosoft 关键词
  - JS 调用 LODOP.PREVIEW() 取消 + SetPrintMode 关闭
  - 按 Escape 多次 + Ctrl+W
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

# Lodop 预览特征关键词 (URL 或 title)
LODOP_KEYWORDS = [
    "lodop",
    "clodop",
    "c-lodop",
    "caosoft",
    "print_preview",
    "printpreview",
    "print-preview",
    "preview",
]


def _close_print_preview(context, pages_before):
    """关闭 Lodop 打印预览 - 强化版

    Args:
        context: Playwright BrowserContext
        pages_before: 点击打印前的 page 列表(用于检测新开的 tab)

    Lodop 预览可能是 4 种形式:
    1. 独立的新窗口/标签页 (window.open) - 找新 page 关闭
    2. 嵌入在业务弹窗里的 HTML 元素 - 用 JS 查找 LODOP 对象关闭
    3. 嵌入在业务弹窗里的隐藏 iframe - 遍历所有 frame 关闭
    4. Chrome 原生 print dialog (window.print) - 按 Escape
    """
    closed = 0

    # 策略1: 检测点击后新开的 page (最可靠)
    new_pages = [p for p in context.pages if p not in pages_before]
    for p in new_pages:
        try:
            print(f"  🔍 检测到新 page: url={p.url[:50]}, title={p.title()[:30] if p.title() else ''}")
            # 先点关闭按钮(如果有)
            try:
                p.get_by_role("button", name="关闭").first.click(timeout=2000)
                print(f"  ✓ 点击新 page 关闭按钮")
            except:
                pass
            # 直接关 tab
            try:
                p.close()
                closed += 1
                print(f"  ✓ 关闭新 page")
            except Exception as e:
                print(f"  关闭新 page 失败: {e}")
        except:
            continue

    # 策略2: 遍历所有 pages 找 Lodop 特征
    if closed == 0:
        for p in context.pages:
            try:
                url = (p.url or "").lower()
                title = ""
                try:
                    title = (p.title() or "").lower()
                except:
                    pass

                is_preview = any(kw in url or kw in title for kw in LODOP_KEYWORDS)
                # 特殊情况: about:blank + 标题含 lodop/打印
                if not is_preview and url == "about:blank":
                    is_preview = any(kw in title for kw in ["lodop", "打印", "preview"])

                if is_preview:
                    try:
                        p.get_by_role("button", name="关闭").first.click(timeout=2000)
                    except:
                        pass
                    try:
                        p.close()
                        closed += 1
                        print(f"  ✓ 关闭 Lodop 预览 (按特征匹配)")
                    except:
                        pass
            except:
                continue

    # 策略3: JS 移除 Lodop 元素 (iframe / 遮罩)
    if closed == 0:
        for p in context.pages:
            try:
                result = p.evaluate("""() => {
                    let count = 0;
                    try {
                        // 1. 移除 Lodop 相关 iframe
                        const iframes = document.querySelectorAll('iframe');
                        for (const f of iframes) {
                            const src = (f.src || '').toLowerCase();
                            const id = (f.id || '').toLowerCase();
                            if (src.includes('lodop') || src.includes('clodop') || src.includes('caosoft') ||
                                src.includes('preview') || id.includes('lodop') || id.includes('preview')) {
                                try { f.remove(); count++; } catch(err) {}
                            }
                        }
                        // 2. 移除 Lodop 弹窗 div / 遮罩
                        const selectors = [
                            '[id*="LODOP"]', '[id*="lodop"]', '[id*="Lodop"]',
                            '[class*="LODOP"]', '[class*="lodop"]', '[class*="Lodop"]',
                            '[id*="preview"]', '[class*="preview"]',
                            '.ui-popup', '.ui-popup-backdrop',
                            'div[style*="position: absolute"][style*="z-index"]',
                        ];
                        for (const sel of selectors) {
                            const els = document.querySelectorAll(sel);
                            for (const e of els) {
                                try { e.remove(); count++; } catch(err) {}
                            }
                        }
                        // 3. 遍历所有 frame 移除 lodop 元素
                        const frames = document.querySelectorAll('iframe, frame');
                        for (const fr of frames) {
                            try {
                                const doc = fr.contentDocument || fr.contentWindow.document;
                                if (doc) {
                                    for (const sel of selectors) {
                                        const els = doc.querySelectorAll(sel);
                                        for (const e of els) {
                                            try { e.remove(); count++; } catch(err) {}
                                        }
                                    }
                                }
                            } catch(err) {}
                        }
                        // 4. 调用 LODOP API 关闭预览
                        if (window.LODOP) {
                            try {
                                if (typeof window.LODOP.PREVIEW === 'function') {
                                    window.LODOP.PREVIEW(false);
                                    count++;
                                }
                                if (typeof window.LODOP.SetPrintMode === 'function') {
                                    try { window.LODOP.SetPrintMode('PREVIEW_IN_BROWSER', false); } catch(e) {}
                                }
                                if (typeof window.LODOP.On_Return !== 'undefined') {
                                    window.LODOP.On_Return = null;
                                }
                            } catch(e) {}
                        }
                        if (window.getLodop) {
                            try {
                                const lodop = window.getLodop();
                                if (lodop && typeof lodop.PREVIEW === 'function') {
                                    lodop.PREVIEW(false);
                                    count++;
                                }
                            } catch(e) {}
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

    # 策略4: 键盘快捷键 (Escape / Ctrl+W)
    if closed == 0:
        for p in context.pages:
            try:
                p.keyboard.press("Escape")
                pa(0.3)
                p.keyboard.press("Escape")
                pa(0.3)
                # Ctrl+W 关 tab
                p.keyboard.press("Control+w")
                pa(0.3)
            except:
                pass
        # 再 check 一遍 pages 数量
        new_after_kb = [p for p in context.pages if p not in pages_before]
        for p in new_after_kb:
            try:
                p.close()
                closed += 1
            except:
                pass

    if closed == 0:
        print(f"  ⚠️ 未找到可关闭的打印预览")
    return closed


def handle(popup, context, main_page, plate):
    print("\n  ═══════════════════")
    print("  📋 popup2: 技术岗位审核")
    print("  ═══════════════════")
    step("技术岗位审核: 准备打印告知单")
    wf = popup.frame_locator(config.SELECTOR_FRAME_WORKFLOW_MAIN)

    # 先点车牌链接(让打印链接显示)
    try:
        plate_link = wf.get_by_role("link", name=plate)
        if plate_link.count() > 0:
            plate_link.first.click()
            print("  ✓ 点击车牌链接")
            pa(1)
    except:
        # 没有车牌链接就跳过
        pass

    # 记录点击打印前的 pages (用于检测新开 tab)
    pages_before = list(context.pages)

    # 🆕 用 CDP 抑制 Chrome 原生打印 dialog (Lodop.PREVIEW 会触发 window.print())
    # 设在 main_page 上,这样 iframe (_Iframe_content 里的打印链接) 也能继承
    cdp_session = None
    try:
        cdp_session = context.new_cdp_session(main_page)
        cdp_session.send("Page.setPrintDialogBehavior", {"behavior": "suppress"})
    except Exception as e:
        if config.DEBUG:
            print(f"  调试 - CDP 抑制打印 dialog 失败: {e}")

    # 4 种策略找打印链接
    if not _click_print_link_v1(wf, popup):
        if not _click_print_link_v2(popup):
            if not _click_print_link_v3(popup):
                # 策略4: 人工兜底
                print("  ⚠️ 自动点击打印链接失败")
                print("  👆 请手动点击 [打印综合性能检测告知单] 后按回车")
                try:
                    input(">>> 点完后按回车继续...")
                except (ValueError, EOFError, OSError):
                    print("  ⚠️ stdin 不可用,跳过")

    # 关闭 Lodop 打印预览 (可能是新窗口/标签页)
    pa(2)
    _close_print_preview(context, pages_before)
    pa(1)

    # 🆕 恢复默认打印 dialog 行为
    if cdp_session:
        try:
            cdp_session.send("Page.setPrintDialogBehavior", {"behavior": "default"})
            cdp_session.detach()
        except:
            pass
    step("技术岗位审核: 打印完成,准备提交")

    # 提交 + 选下一处理人
    try:
        safe(wf.get_by_role("button", name=config.BTN_SUBMIT), timeout=5000).click()
        pa(2)
        do_dialog(
            popup,
            action_type=config.ACTION_SUBMIT_TECH_REVIEW,
            category=config.CATEGORY_ROLE,
        )
    except Exception as e:
        print(f"  ⚠️ 提交按钮找不到 ({e})")
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
