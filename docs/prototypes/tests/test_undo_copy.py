# -*- coding: utf-8 -*-
"""撤销/重做 + 复制/剪切/粘贴 专项测试"""
from playwright.sync_api import sync_playwright

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("dialog", lambda d: d.accept())
    page.goto(os.environ.get("WBTPL_URL", "file://" + __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("print-template-editor-v2.html").as_posix()))

    # ===== 撤销/重做 =====
    # ① 删行 → Ctrl+Z 撤销 → Ctrl+Y 重做
    page.click("#sheetBody tr:nth-child(3) th.rowh")
    page.click("#btnDelRow")
    assert page.evaluate("() => S.rows.length") == 7
    page.keyboard.press("Control+z")
    assert page.evaluate("() => S.rows.length") == 8, "撤销删行失败"
    page.keyboard.press("Control+y")
    assert page.evaluate("() => S.rows.length") == 7, "重做删行失败"
    print("① 删行 → Ctrl+Z撤销 → Ctrl+Y重做 ✓")
    page.keyboard.press("Control+z")  # 恢复到8行

    # ② 样式修改可撤销
    page.click("#sheetBody tr:nth-child(3) td:nth-child(2)")  # A3占位符格，默认无加粗
    page.click("#btnBold")
    assert page.evaluate("() => S.rows[2].cells[0].s.bold") == True
    page.click("#btnUndo")
    assert page.evaluate("() => !!S.rows[2].cells[0].s.bold") == False, "撤销加粗失败"
    page.click("#btnRedo")
    assert page.evaluate("() => S.rows[2].cells[0].s.bold") == True, "重做加粗失败"
    print("② 加粗 → 工具栏撤销/重做 ✓")

    # ③ 文本编辑可撤销（双击编辑→点别处提交→撤销）
    page.dblclick("#sheetBody tr:nth-child(4) td:nth-child(2)")
    page.keyboard.type("临时文字")
    page.click("#sheetBody tr:nth-child(6) th.rowh")  # 点别处触发提交
    assert page.evaluate("() => S.rows[3].cells[0].t") == "临时文字"
    page.click("#btnUndo")
    assert page.evaluate("() => S.rows[3].cells[0].t") == "", "撤销文本编辑失败"
    print("③ 文本编辑会话 → 撤销恢复原文 ✓")

    # ④ Esc 取消编辑（不产生历史、内容还原）
    page.dblclick("#sheetBody tr:nth-child(2) td:nth-child(2)")
    page.keyboard.type("不该保存")
    page.keyboard.press("Escape")
    t = page.evaluate("() => S.rows[1].cells[0].t")
    assert t == "物料编码", f"Esc取消失败: {t}"
    print("④ 编辑中按 Esc 取消、内容还原 ✓")

    # ===== 复制/粘贴 =====
    # ⑤ 复制带格式：B2(物料编码,粗体) → D5
    page.click("#sheetBody tr:nth-child(2) td:nth-child(2)")
    tsv = page.evaluate("""() => {
      const dt = new DataTransfer();
      document.dispatchEvent(new ClipboardEvent('copy', {clipboardData: dt, bubbles: true, cancelable: true}));
      return dt.getData('text/plain');
    }""")
    assert tsv == "物料编码", f"复制TSV不对: {tsv}"
    page.click("#sheetBody tr:nth-child(5) td:nth-child(5)")
    page.evaluate("""() => document.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true}))""")
    got = page.evaluate("() => [S.rows[4].cells[3].t, !!S.rows[4].cells[3].s.bold]")
    assert got == ["物料编码", True], f"带格式粘贴失败: {got}"
    print("⑤ 复制(带粗体格式) → 粘贴 ✓  TSV =", repr(tsv))

    # ⑥ 复制合并格：A1(标题,合并9列) → A7
    page.click("#sheetBody tr:nth-child(1) td")
    page.evaluate("""() => {
      const dt = new DataTransfer();
      document.dispatchEvent(new ClipboardEvent('copy', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""")
    page.click("#sheetBody tr:nth-child(7) td:nth-child(2)")
    page.evaluate("""() => document.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true}))""")
    cs = page.evaluate("() => S.rows[6].cells[0].cs")
    t = page.evaluate("() => S.rows[6].cells[0].t")
    assert cs == 9 and t == "物料标签", f"合并格粘贴失败 cs={cs} t={t}"
    print("⑥ 合并单元格(9列)整体复制粘贴 ✓")
    page.click("#btnUndo")  # 撤销⑥的粘贴

    # ⑦ 剪切：B2 → F6，源格清空
    page.click("#sheetBody tr:nth-child(2) td:nth-child(2)")
    page.evaluate("""() => {
      const dt = new DataTransfer();
      document.dispatchEvent(new ClipboardEvent('cut', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""")
    page.click("#sheetBody tr:nth-child(6) td:nth-child(7)")
    page.evaluate("""() => document.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true}))""")
    src = page.evaluate("() => S.rows[1].cells[0].t")
    dst = page.evaluate("() => S.rows[5].cells[5].t")
    assert src == "" and dst == "物料编码", f"剪切失败 src={src} dst={dst}"
    print("⑦ 剪切 → 粘贴后源格清空、目标格有内容 ✓")

    # ⑧ 外部 TSV 粘贴（模拟从真 Excel 复制）
    page.keyboard.press("Escape")  # 清内部剪贴板
    page.click("#sheetBody tr:nth-child(8) td:nth-child(2)")
    page.evaluate("""() => {
      const dt = new DataTransfer();
      dt.setData('text/plain', '甲\\t乙\\n丙\\t丁');
      document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true}));
    }""")
    vals = page.evaluate("() => [S.rows[7].cells[0].t, S.rows[7].cells[1].t, S.rows[8].cells[0].t, S.rows[8].cells[1].t]")
    assert vals == ["甲", "乙", "丙", "丁"], f"TSV粘贴失败: {vals}"
    print("⑧ 外部Excel文本(TSV)粘贴成2x2 ✓")
    rows = page.evaluate("() => S.rows.length")
    assert rows == 9, f"粘贴自动扩行失败: {rows}"
    print("⑨ 粘贴超出边界自动扩行 ✓ (8→9行)")

    # ⑩ 撤销粘贴
    page.click("#btnUndo")
    vals = page.evaluate("() => [S.rows[7].cells[0].t, S.rows.length]")
    assert vals == ["", 8], f"撤销粘贴失败: {vals}"
    print("⑩ 撤销整次粘贴(内容+扩行一起回退) ✓")

    browser.close()

print("\n控制台错误:", errors if errors else "无")
print("=== 撤销/重做 + 复制粘贴 10 项全部通过 ===")
