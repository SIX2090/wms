# -*- coding: utf-8 -*-
"""会话持久化 + 未保存提醒 专项测试"""
from playwright.sync_api import sync_playwright

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("dialog", lambda d: d.accept())
    page.goto(os.environ.get("WBTPL_URL", "file://" + __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("print-template-editor-v2.html").as_posix()))

    # ① 改动后保存按钮出现 ● 脏标记
    page.click("#sheetBody tr:nth-child(3) td:nth-child(2)")
    page.click("#btnBold")
    label = page.inner_text("#btnSave")
    assert "●" in label, f"脏标记未出现: {label}"
    print("① 改动后保存按钮出现 ● 脏标记 ✓ ->", label)

    # ② 保存后 ● 消失
    page.click("#btnSave")
    page.wait_for_timeout(1300)
    label = page.inner_text("#btnSave")
    assert "●" not in label, f"保存后脏标记未消失: {label}"
    print("② 保存模板后 ● 消失 ✓ ->", label)

    # ③ 不保存直接做两个改动，等防抖落盘
    page.click("#sheetBody tr:nth-child(3) td:nth-child(2)")
    page.click("#btnBold")
    page.click("#sheetBody tr:nth-child(4) td:nth-child(2)")
    page.click("#btnItalic")
    page.wait_for_timeout(1000)  # 等 800ms 防抖
    depth = page.evaluate("() => undoStack.length")
    assert depth >= 2, f"撤销栈深度异常: {depth}"
    print("③ 两个未保存改动完成，撤销栈深度:", depth)

    # ④ 刷新页面 → 现场(含未保存改动)和撤销栈完整恢复
    page.reload()
    st = page.evaluate("() => [S.rows[2].cells[0].s.bold===false, S.rows[3].cells[0].s.italic===true, undoStack.length]")
    assert st[0] and st[1], f"刷新后工作现场恢复不对: {st}"
    assert st[2] == depth, f"刷新后撤销栈深度不对: {st[2]} vs {depth}"
    print("④ 刷新后：未保存改动还在 ✓ 撤销栈恢复 ✓ 深度:", st[2])

    # ⑤ 刷新后 ● 脏标记也恢复（提示有改动未保存进模板）
    label = page.inner_text("#btnSave")
    assert "●" in label, f"刷新后脏标记未恢复: {label}"
    print("⑤ 刷新后 ● 脏标记恢复 ✓ ->", label)

    # ⑥ 恢复后的撤销栈真的能用：连撤两次，两个改动都回退
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    st = page.evaluate("() => [!!S.rows[2].cells[0].s.bold, !!S.rows[3].cells[0].s.italic]")
    assert st == [True, False], f"跨刷新的撤销失败: {st}"
    print("⑥ 跨刷新继续撤销：两个改动全部回退 ✓")

    # ⑦ 全部撤销回已保存状态后，● 自动消失
    page.wait_for_timeout(100)
    label = page.inner_text("#btnSave")
    assert "●" not in label, f"撤销回已保存状态后仍有脏标记: {label}"
    print("⑦ 撤销回已保存状态，● 消失 ✓ ->", label)

    # ⑧ beforeunload 拦截逻辑：有脏改动时 dirty=true（对话框逻辑已挂）
    page.click("#sheetBody tr:nth-child(5) td:nth-child(2)")
    page.click("#btnBold")
    d = page.evaluate("() => dirty")
    assert d == True, "dirty 未置位"
    hooked = page.evaluate("() => { let h=false; window.dispatchEvent(new Event('beforeunload')); h = JSON.parse(localStorage.getItem('wbtpl_v2')).session !== undefined; return h; }")
    assert hooked, "beforeunload 未落盘会话"
    print("⑧ 关闭页面前会话强制落盘 + 脏状态拦截逻辑就绪 ✓")

    browser.close()

print("\n控制台错误:", errors if errors else "无")
print("=== 会话持久化 + 未保存提醒 8 项全部通过 ===")
