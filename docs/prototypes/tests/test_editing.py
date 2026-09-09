# -*- coding: utf-8 -*-
"""验证 Excel 式编辑交互：直接输入、双击续编、方向键、拖选、样式、清空、占位符"""
from playwright.sync_api import sync_playwright

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(os.environ.get("WBTPL_URL", "file://" + __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("print-template-editor-v2.html").as_posix()))

    # ① 单击选中 A1（标题合并格），直接打字 → 替换内容
    page.click("#sheetBody tr:nth-child(1) td")
    page.keyboard.type("采购入库单")
    page.click("#sheetBody tr:nth-child(8) th.rowh")  # 点别处提交编辑
    t = page.evaluate("() => S.rows[0].cells[0].t")
    assert t == "采购入库单", f"直接输入替换失败: {t}"
    print("① 单击后直接打字替换内容 ✓ ->", t)

    # ② 双击进入编辑，在原文末尾续写
    page.dblclick("#sheetBody tr:nth-child(2) td:nth-child(2)")
    page.keyboard.press("End")
    page.keyboard.type("（必填）")
    page.click("#sheetBody tr:nth-child(8) th.rowh")  # 点别处提交编辑
    t = page.evaluate("() => S.rows[1].cells[0].t")
    assert t == "物料编码（必填）", f"双击续编失败: {t}"
    print("② 双击进入编辑、光标处续写 ✓ ->", t)

    # ③ 方向键移动选区
    page.click("#sheetBody tr:nth-child(3) td:nth-child(2)")
    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")
    pos = page.evaluate("() => [selA.r, selA.c]")
    assert pos == [3, 1], f"方向键移动失败: {pos}"
    print("③ 方向键移动选区 ✓ -> 第4行 C列", pos)

    # ④ 按住拖动多选 B4:D5，验证 6 格高亮
    box1 = page.locator("#sheetBody tr:nth-child(4) td:nth-child(3)").bounding_box()
    box2 = page.locator("#sheetBody tr:nth-child(5) td:nth-child(5)").bounding_box()
    page.mouse.move(box1["x"] + 5, box1["y"] + 5)
    page.mouse.down()
    page.mouse.move(box2["x"] + 5, box2["y"] + 5, steps=6)
    page.mouse.up()
    n = page.evaluate("() => document.querySelectorAll('#sheetBody td.sel').length")
    assert n == 6, f"拖选高亮数不对: {n}"
    print("④ 按住拖动多选 B4:D5（6格高亮）✓")

    # ⑤ 对选区应用 加粗+填充色，验证写入了全部 6 格
    page.click("#btnBold")
    page.evaluate("() => { const el = document.getElementById('bgColor'); el.value='#fff3cd'; el.dispatchEvent(new Event('input')); }")
    styled = page.evaluate("""() => {
      let n = 0;
      for (let r = 3; r <= 4; r++) for (let c = 1; c <= 3; c++)
        if (S.rows[r].cells[c].s.bold && S.rows[r].cells[c].s.bg === '#fff3cd') n++;
      return n;
    }""")
    assert styled == 6, f"批量样式失败: {styled}"
    print("⑤ 选区批量应用 加粗+填充色（6/6格）✓")

    # ⑥ Delete 清空选区
    page.keyboard.press("Delete")
    # （上面选区本来就是空的，改为验证有内容的格子）
    page.click("#sheetBody tr:nth-child(2) td:nth-child(2)")
    page.keyboard.press("Delete")
    t = page.evaluate("() => S.rows[1].cells[0].t")
    assert t == "", f"Delete清空失败: {t}"
    print("⑥ Delete 键清空选中内容 ✓")

    # ⑦ 占位符 chip 插入当前单元格
    page.click("#sheetBody tr:nth-child(4) td:nth-child(3)")
    page.click(".chip:has-text('物料编码')")
    t = page.evaluate("() => S.rows[3].cells[1].t")
    assert t == "{{item.code}}", f"占位符插入失败: {t}"
    print("⑦ 点击占位符插入当前单元格 ✓ ->", t)

    # ⑧ Enter 进入编辑 / Escape 退出
    page.click("#sheetBody tr:nth-child(5) td:nth-child(3)")
    page.keyboard.press("Enter")
    editing = page.evaluate("() => !!editCtx")
    assert editing, "Enter 未进入编辑"
    page.keyboard.press("Escape")
    editing = page.evaluate("() => !!editCtx")
    assert not editing, "Escape 未退出编辑"
    print("⑧ Enter 进入编辑 / Escape 退出 ✓")

    # 截图：编辑后的完整界面
    page.click("#sheetBody tr:nth-child(1) td")
    page.screenshot(path="/workspace/editor-excel-demo.png", full_page=False)

    # 打印预览截图
    page.click("#btnPreview")
    page.wait_for_timeout(300)
    page.screenshot(path="/workspace/editor-print-preview.png", full_page=False)

    browser.close()

print("\n控制台错误:", errors if errors else "无")
print("=== 8 项 Excel 式编辑交互全部通过 ===")
