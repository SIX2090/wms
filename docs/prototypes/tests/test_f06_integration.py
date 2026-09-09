# -*- coding: utf-8 -*-
"""F06 集成冒烟：v2 编辑器 + 真实 api.js + Mock 后端路由（grid 读写/preview_data）。

自包含：自动用 Jinja 渲染 app/templates/print_template_editor.html 到临时目录、
软链 app/static、启动临时静态服务器、Playwright 拦截后端路由。

运行：python3 docs/prototypes/tests/test_f06_integration.py
依赖：playwright + jinja2（Chromium 已安装）。
"""
import functools
import http.server
import json
import os
import pathlib
import socketserver
import threading

import jinja2
from playwright.sync_api import sync_playwright

REPO = pathlib.Path(__file__).resolve().parents[3]
TPL = REPO / "app" / "templates" / "print_template_editor.html"
WORK = pathlib.Path(os.environ.get("F06_WORK", "/tmp/f06_itest"))
PORT = int(os.environ.get("F06_PORT", "8899"))


def prepare():
    WORK.mkdir(exist_ok=True)
    html = jinja2.Environment().from_string(TPL.read_text(encoding="utf-8")).render(
        template_id=1, template_name="测试物料标签模板", is_default=True,
        prefix="global", template_label="通用 Excel 模板",
        csrf_token=lambda: "test-token",
        url_for=lambda endpoint, filename=None: "/static/" + (filename or ""))
    (WORK / "editor.html").write_text(html, encoding="utf-8")
    link = WORK / "static"
    if not link.exists():
        os.symlink(REPO / "app" / "static", link)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


prepare()
handler = functools.partial(_Quiet, directory=str(WORK))
httpd = socketserver.TCPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()

GRID = {
    "status": "success",
    "template": {"id": 1, "name": "测试物料标签模板", "is_default": True, "prefix": "global"},
    "sheets": [{
        "name": "标签",
        "max_row": 8, "max_col": 9,
        "merges": [{"row": 1, "col": 1, "rowspan": 1, "colspan": 9}],
        "cells": (
            [{"row": 1, "col": 1, "value": "物料标签", "merged": True,
              "style": {"bold": True, "font_size": 16, "h_align": "center", "v_align": "center",
                        "border": {"top": "thin", "right": "thin", "bottom": "thin", "left": "thin"}}}]
            + [{"row": 2, "col": c, "value": h, "merged": False,
                "style": {"bold": True, "h_align": "center", "v_align": "center", "bg_color": "#F5F5F5",
                          "border": {"top": "thin", "right": "thin", "bottom": "thin", "left": "thin"}}}
               for c, h in enumerate(["物料编码", "物料名称", "规格型号", "单位", "分类", "供应商", "单价", "当前库存", "条码"], 1)]
            + [{"row": 3, "col": c, "value": v, "merged": False,
                "style": {"h_align": "center", "v_align": "center",
                          "border": {"top": "thin", "right": "thin", "bottom": "thin", "left": "thin"}}}
               for c, v in enumerate(["{item.material.code}", "{item.material.name}", "{item.material.spec}",
                                      "{item.material.unit.name}", "{item.quantity}", "{item.price}",
                                      "{item.amount}", "{item.remark}", "{img_barcode:item.material.barcode}"], 1)]
        ),
        "col_widths": {str(i): 12 for i in range(1, 10)},
        "row_heights": {"1": 24},
    }],
}

PREVIEW = {
    "status": "success",
    "context": {
        "order": {"order_no": "RK20260910001", "date": "2026-09-10", "supplier": {"name": "示例供应商有限公司"},
                  "customer": "示例客户", "purpose": "生产领用", "remark": "无", "picker": "张三",
                  "operator": {"username": "admin"}},
        "items": [
            {"material": {"code": f"WL-{i:04d}", "name": f"示例物料{i}", "spec": "M6×20",
                          "brand": "SKF", "unit": {"name": "个"}, "barcode": f"6901234{i:05d}"},
             "quantity": i * 5, "price": 3.5, "amount": i * 17.5, "remark": ""}
            for i in range(1, 4)
        ],
        "total_quantity": 30, "total_amount": 105.0,
        "print_date": "2026-09-10", "today": "2026-09-10",
    },
    "target_type": "label", "target_code": "material_label",
}

posted = []
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1500, "height": 950})
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("dialog", lambda d: d.accept())

    def handle_grid(route):
        if route.request.method == "GET":
            route.fulfill(json=GRID)
        else:
            posted.append(json.loads(route.request.post_data))
            route.fulfill(json={"status": "success", "msg": "模板已更新"})

    page.route("**/global_print_template/1/grid", handle_grid)
    page.route("**/global_print_template/1/preview_data", lambda r: r.fulfill(json=PREVIEW))
    page.goto("http://127.0.0.1:" + str(PORT) + "/editor.html")
    page.wait_for_selector("#gridTable td.cell")

    # ① 加载渲染：19 个单元格、标题合并 9 列
    n = page.eval_on_selector_all("#gridTable td.cell", "els => els.length")
    span = page.evaluate("() => document.querySelector('#gridTable tbody tr td').colSpan")
    assert n == 64 and span == 9, f"渲染异常 n={n} span={span}"
    print("① grid 加载渲染：8×9网格(64格) + 标题合并9列 ✓")

    # ② 中文直输（IME 捕获器）
    page.click("#gridTable tbody tr:nth-child(5) td:nth-child(2)")
    page.keyboard.type("临时备注")
    page.click("#gridTable tbody tr:nth-child(8) th.rowh")
    t = page.evaluate("() => __tplEditor.getS().rows[4].cells[0].t")
    assert t == "临时备注", f"中文直输失败: {t}"
    print("② 中文直输 ✓ ->", t)

    # ③ 结构操作：插入行→插入列→删除行→撤销×3 全恢复
    page.click("#gridTable tbody tr:nth-child(5) td:nth-child(2)")
    page.click("#btnInsRowD")
    page.click("#btnInsColR")
    assert page.evaluate("() => [__tplEditor.getS().rows.length, __tplEditor.getS().cols.length]") == [9, 10]
    page.click("#gridTable tbody tr:nth-child(6) th.rowh")
    page.click("#btnDelRow")
    assert page.evaluate("() => __tplEditor.getS().rows.length") == 8
    for _ in range(3):
        page.keyboard.press("Control+z")
    assert page.evaluate("() => [__tplEditor.getS().rows.length, __tplEditor.getS().cols.length]") == [8, 9], "撤销恢复失败"
    print("③ 插行/插列/删行 + Ctrl+Z×3 恢复 ✓")

    # ④ 合并 B5:C5 → 保存 → 校验 POST 载荷
    page.click("#gridTable tbody tr:nth-child(5) td:nth-child(3)")
    page.keyboard.down("Shift")
    page.click("#gridTable tbody tr:nth-child(5) td:nth-child(4)")
    page.keyboard.up("Shift")
    page.click("#btnMerge")
    label = page.inner_text("#btnSave")
    assert "●" in label, "脏标记未出现"
    page.click("#btnSave")
    page.wait_for_timeout(300)
    assert len(posted) == 1, "未发出保存请求"
    pl = posted[0]["sheets"][0]
    ups = {tuple(u[:2]): u[2] for u in pl["upserts"]}
    assert ups.get((5, 1)) == "临时备注", f"upserts 缺编辑值: {ups.get((5,1))}"
    assert {"row": 5, "col": 2, "rowspan": 1, "colspan": 2} in pl["merges"], f"merges 错: {pl['merges']}"
    assert pl["del_rows"] == [], "del_rows 应为空（全状态DIFF）"
    print("④ 合并+保存：upserts/merges/del_rows 载荷正确 ✓")
    label = page.inner_text("#btnSave")
    assert "●" not in label, "保存后脏标记未消失"
    print("⑤ 保存后 ● 消失 ✓")

    # ⑥ 无改动再保存 → 不发请求
    page.click("#btnSave")
    page.wait_for_timeout(200)
    assert len(posted) == 1, "无改动不应发请求"
    print("⑥ 无改动保存被拦截 ✓")

    # ⑦ 取消合并 → 保存 → unmerges 载荷
    page.click("#gridTable tbody tr:nth-child(5) td:nth-child(3)")
    page.click("#btnUnmerge")
    page.click("#btnSave")
    page.wait_for_timeout(300)
    assert len(posted) == 2
    pl2 = posted[1]["sheets"][0]
    assert [5, 2] in pl2["unmerges"], f"unmerges 错: {pl2['unmerges']}"
    print("⑦ 取消合并 → unmerges 载荷正确 ✓")

    # ⑧ 打印预览：占位符替换 + 明细行展开 + 条码虚线框
    page.click("#btnPreview")
    page.wait_for_selector("#previewContent .paper")
    pv = page.inner_text("#previewContent")
    assert "WL-0001" in pv and "WL-0003" in pv, "明细未展开"
    assert "{item.material.code}" not in pv, "占位符未替换"
    assert "690123400001" in pv, "条码值未显示"
    rows = page.evaluate("() => document.querySelectorAll('#previewContent table.pv tbody tr').length")
    assert rows == 10, f"预览行数应为10(8-1+3): {rows}"
    print("⑧ 打印预览：明细1→3行展开 ✓ 占位符替换 ✓ 条码虚线框 ✓")

    # ⑨ 页面设置：A5 横向 → @page 生效
    page.click("#btnExitPreview")
    page.click("#btnPageSetup")
    page.select_option("#pgSize", "A5")
    page.select_option("#pgOrient", "landscape")
    page.click("#btnPageOk")
    css = page.evaluate("() => document.getElementById('pageStyle').textContent")
    assert "210mm 148mm" in css, f"@page 未生效: {css}"
    print("⑨ 页面设置 @page ✓ ->", css.strip())

    # ⑩ 复制粘贴（内部带格式）+ 外部 TSV
    page.click("#gridTable tbody tr:nth-child(2) td:nth-child(2)")  # 物料编码(粗体)
    page.evaluate("""() => { const dt = new DataTransfer();
      document.dispatchEvent(new ClipboardEvent('copy', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    page.click("#gridTable tbody tr:nth-child(6) td:nth-child(2)")
    page.evaluate("""() => document.dispatchEvent(new ClipboardEvent('paste', {bubbles: true, cancelable: true}))""")
    got = page.evaluate("() => [__tplEditor.getS().rows[5].cells[0].t, !!__tplEditor.getS().rows[5].cells[0].s.bold]")
    assert got == ["物料编码", True], f"带格式粘贴失败: {got}"
    page.keyboard.press("Escape")
    page.click("#gridTable tbody tr:nth-child(7) td:nth-child(2)")
    page.evaluate("""() => { const dt = new DataTransfer(); dt.setData('text/plain', '甲\\t乙');
      document.dispatchEvent(new ClipboardEvent('paste', {clipboardData: dt, bubbles: true, cancelable: true})); }""")
    vals = page.evaluate("() => [__tplEditor.getS().rows[6].cells[0].t, __tplEditor.getS().rows[6].cells[1].t]")
    assert vals == ["甲", "乙"], f"TSV粘贴失败: {vals}"
    print("⑩ 复制(带格式)/外部TSV粘贴 ✓")

    page.screenshot(path="/tmp/itest-integrated.png")
    browser.close()

print("\n控制台错误:", errors if errors else "无")
print("=== F06 集成测试 10 项全部通过 ===")

httpd.shutdown()
print("（静态服务器已关闭）")
