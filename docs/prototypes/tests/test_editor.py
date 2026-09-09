# -*- coding: utf-8 -*-
"""打印模板编辑器功能冒烟测试：行列增删、合并、预览、页面设置"""
from playwright.sync_api import sync_playwright

import os
URL = os.environ.get("WBTPL_URL", "file://" + __import__("pathlib").Path(__file__).resolve().parent.parent.joinpath("print-template-editor-v2.html").as_posix())
errors = []

GRID_CHECK = """
() => {
  // 从 DOM 重建网格，验证每个视觉位置恰好被一个单元格覆盖（无空洞/重叠）
  const tb = document.querySelector('#sheetBody');
  const grid = [];
  const rows = [...tb.rows];
  let maxC = 0;
  rows.forEach((tr, r) => {
    grid[r] = grid[r] || [];
    let c = 0;
    for (const td of tr.cells) {
      while (grid[r][c]) c++;
      const rs = td.rowSpan || 1, cs = td.colSpan || 1;
      for (let i = 0; i < rs; i++) {
        grid[r+i] = grid[r+i] || [];
        for (let j = 0; j < cs; j++) grid[r+i][c+j] = 1;
      }
      c += cs;
    }
    maxC = Math.max(maxC, grid[r].length);
  });
  const R = grid.length;
  for (let r = 0; r < R; r++)
    for (let c = 0; c < maxC; c++)
      if (!grid[r] || !grid[r][c]) return 'HOLE at ' + r + ',' + c;
  return R + 'x' + maxC;
}
"""

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept("测试模板"))  # confirm接受/prompt填名称
    page.goto(URL)

    def state():
        return page.evaluate("() => ({R: S.rows.length, C: S.cols.length})")

    def grid_ok():
        return page.evaluate(GRID_CHECK)

    print("1. 初始网格:", state(), "DOM一致性:", grid_ok())

    # --- 删除行：点行号3选中整行，点"✕ 行" ---
    page.click("#sheetBody tr:nth-child(3) th.rowh")
    page.click("#btnDelRow")
    s = state()
    assert s["R"] == 7, f"删行失败 {s}"
    print("2. 删除第3行后:", s, "DOM一致性:", grid_ok())

    # --- 删除列：点列标B，点"✕ 列" ---
    page.click("#sheetHead th.colh:nth-child(3)")  # corner是第1个，B列是第3个
    page.click("#btnDelCol")
    s = state()
    assert s["C"] == 8, f"删列失败 {s}"
    print("3. 删除B列后:", s, "DOM一致性:", grid_ok())

    # --- 插入行/列 ---
    page.click("#sheetBody tr:nth-child(2) td:nth-child(2)")
    page.click("#btnInsRowD")
    page.click("#btnInsColR")
    s = state()
    assert s["R"] == 8 and s["C"] == 9, f"插入失败 {s}"
    print("4. 插入行+列后:", s, "DOM一致性:", grid_ok())

    # --- 合并 A4:B5 再取消 ---
    page.click("#sheetBody tr:nth-child(4) td:nth-child(2)")
    page.keyboard.down("Shift")
    page.click("#sheetBody tr:nth-child(5) td:nth-child(3)")
    page.keyboard.up("Shift")
    page.click("#btnMerge")
    merged = page.evaluate("() => S.rows[3].cells[0].rs === 2 && S.rows[3].cells[0].cs === 2")
    assert merged, "合并失败"
    print("5. 合并2x2:", grid_ok())
    page.click("#btnUnmerge")
    un = page.evaluate("() => S.rows[3].cells[0].rs === 1 && S.rows[3].cells[0].cs === 1 && !S.rows[4].cells[1].cov")
    assert un, "取消合并失败"
    print("6. 取消合并后:", grid_ok())

    # --- 跨行合并后删除中间行（最考验模型正确性的场景）---
    page.click("#sheetBody tr:nth-child(3) td:nth-child(2)")
    page.keyboard.down("Shift")
    page.click("#sheetBody tr:nth-child(5) td:nth-child(2)")
    page.keyboard.up("Shift")
    page.click("#btnMerge")  # 合并 B3:B5
    page.click("#sheetBody tr:nth-child(4) th.rowh")  # 选中第4行
    page.click("#btnDelRow")  # 删除合并区中间的行
    s = state()
    rs = page.evaluate("() => S.rows[2].cells[0].rs")
    assert s["R"] == 7 and rs == 2, f"跨合并删行失败 {s} rs={rs}"
    print("7. 跨合并区删中间行:", s, "剩余rowspan=2 ✓", "DOM一致性:", grid_ok())

    # --- 连续删到只剩1行1列也不能崩 ---
    for _ in range(6):
        page.click("#sheetBody tr:nth-child(1) th.rowh")
        page.click("#btnDelRow")
    for _ in range(8):
        page.click("#sheetHead th.colh:nth-child(2)")
        page.click("#btnDelCol")
    s = state()
    assert s["R"] == 1 and s["C"] == 1, f"极限删除失败 {s}"
    print("8. 删到只剩1行1列:", s, "DOM一致性:", grid_ok())

    # --- 恢复默认模板：清空存储后刷新（新版有会话恢复，清库才回到出厂模板） ---
    page.evaluate("() => { window.persistSession = () => {}; localStorage.removeItem('wbtpl_v2'); }")
    page.reload()
    print("9. 清库刷新后(出厂默认模板):", state(), grid_ok())

    # --- 打印预览：占位符替换 + 明细行展开 ---
    page.click("#btnPreview")
    preview = page.inner_text("#printSheet")
    assert "WL-0001" in preview and "WL-0003" in preview, "明细行未展开"
    assert "{{item.code}}" not in preview, "占位符未替换"
    assert "6901001000017" in preview, "条码未生成"
    item_rows = page.evaluate("() => document.querySelectorAll('#printSheet tr').length")
    assert item_rows == 10, f"预览行数应为 8-1+3=10，实际 {item_rows}"  # 1明细行→3行
    print("10. 打印预览: 明细1行展开为3行 ✓ 占位符已替换 ✓ 条码已生成 ✓")
    page.click("#btnPreviewClose")

    # --- 页面设置：A5 横向 自定义边距 ---
    page.click("#btnPage")
    page.select_option("#pgSize", "A5")
    page.select_option("#pgOrient", "landscape")
    page.fill("#pgMt", "20")
    page.fill("#pgScale", "80")
    page.click("#btnPageOk")
    page_css = page.evaluate("() => document.getElementById('pageStyle').textContent")
    assert "210mm 148mm" in page_css and "20mm" in page_css, f"@page 未生效: {page_css}"
    print("11. 页面设置 @page:", page_css.strip())
    page.click("#btnPreview")
    zoom = page.evaluate("() => document.querySelector('.paper').style.zoom")
    assert zoom == "0.8", f"缩放未生效 {zoom}"
    print("12. 预览纸张缩放 80% ✓")
    page.click("#btnPreviewClose")

    # --- 保存/多模板 ---
    page.click("#btnSave")
    assert "已保存" in page.inner_text("#btnSave") or page.inner_text("#btnSave") == "✓ 已保存"
    page.click("#btnNewTpl")  # prompt 自动 accept（默认名称）
    names = page.eval_on_selector("#tplSelect", "el => el.options.length")
    assert names == 2, "新建模板失败"
    print("13. 保存模板 ✓ 新建模板 ✓ 模板数:", names)

    browser.close()

if errors:
    print("\n!!! 控制台错误:")
    for e in errors: print("  -", e)
else:
    print("\n控制台无错误")
print("\n=== 全部测试通过 ===")
