# -*- coding: utf-8 -*-
"""期初库存「导出」回归（用户反馈：「期初单据导出功能也有问题」）。

用户只说了"导出有问题"，未给现象，实测复现出三处叠加缺陷，
任何一处都足以让导出的文件不可用：

  ① 换行符写错 → 整个文件塌成一行
     `new Blob([...lines.join('\\n')])` 写在**单引号字符串**里，
     `'\\n'` 是「反斜杠 + n」两个字面字符，不是换行符。导出结果：
     `"仓库","物料编码",…"备注"\n"WH001",…`（其中的 \n 是可见文本），
     Excel/WPS 打开只有第 1 行有内容，其余全挤在一个单元格里。
     同仓库的 in_order_add.html / out_order_add.html 用的都是正确的 '\n'，
     只有本模板写错——属 R6 意义上的"同能力他处正确、此处漂移"。

  ② 导出列序与导入列序不一致 → 导出的文件无法回导
     导出原为 9 列：仓库,物料编码,物料名称,规格,单位,数量,单价,期初余额,备注
     而粘贴导入 parsePasteLines 按 6 列取值：仓库,编码,数量,单价,备注,日期
     即"导出的第 3 列是名称，导入却当成数量"。用户「导出 → 改价格 → 导回」
     的常规闭环必然失败（物料编码还会因带引号而匹配不到）。
     现统一到后端 /opening_stock/import/template 的官方列序：
     仓库编码,物料编码,物料名称,规格,单位,数量,单价,备注,日期。

  ③ 导入解析不认引号 → 带引号的 CSV 每列都解错
     parsePasteLines 原用 line.split(/\\t|,/) 裸切，不剥引号也不识别引号内逗号：
     `"M001"` 解析出的是带引号的 `"M001"`（物料匹配失败），
     `"含逗号,的备注"` 还会被从中间切开导致整体错列。
     现新增 splitCsvLine（支持双引号包裹、"" 转义、引号内逗号）。

另修两处体验缺陷：
  · 空单据点导出原本静默下载一个只有表头的文件，现提示「没有可导出的明细行」；
  · 导出文件名带单据号（opening_stock_QS26090001.csv），不再是同名覆盖。

覆盖：
  T1 换行符：导出内容必须含真实 \n，不得含字面量反斜杠 n
  T2 列序：表头与后端官方导入模板一致（9 列，含「日期」末列）
  T3 闭环：导出 → parsePasteLines 回导，字段逐项一致（含带逗号的备注不裂列）
  T4 splitCsvLine 引号/转义/引号内逗号/裸 Tab 兼容
  T5 表头行自动跳过（导出的文件直接整段粘贴回来不能把表头当数据行）
  T6 空单据导出给出提示且不下载
  T7 兼容性：原有宽松粘贴格式（Tab / 裸逗号 / 缺列）行为不变
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"

TEMPLATE = APP_DIR / "templates" / "opening_stock.html"
NODE = shutil.which("node")


def _template_src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _extract_function(src: str, name: str) -> str:
    """从模板里抽出 `function name(...) {...}` 的完整源码（顶层 } 收尾）。"""
    m = re.search(r"^function %s\b[\s\S]*?^}" % re.escape(name), src, re.M)
    assert m, f"模板中未找到函数 {name}（改名或删除需同步更新本测试）"
    return m.group(0)


@pytest.fixture(scope="module")
def js_runtime(tmp_path_factory):
    """把模板里的真实导出/解析函数抽出来，在 node 里跑真实逻辑。

    不重写一份 JS 逻辑来"模拟"——直接执行模板中的同一份源码，
    否则测试与实现会各写一套、改了实现测试仍绿（假绿灯）。
    `exportRows()` 会真实执行：桩掉 Blob/URL/createElement 只为截获它生成的字节。
    """
    if not NODE:
        pytest.skip("未安装 node，跳过导出逻辑动态验证")

    src = _template_src()
    funcs = "\n\n".join(
        _extract_function(src, n)
        for n in ("csvCell", "splitCsvLine", "parsePasteLines", "exportRows",
                  # BUG-2026-09-16-012：parsePasteLines 的物料解析改走缓存，
                  # 这两个缓存函数同样是模板真实实现，一并抽取执行
                  "cacheMaterial", "findMaterialByCode")
    )

    harness = tmp_path_factory.mktemp("os_export") / "harness.js"
    harness.write_text(
        funcs
        + """

// ---- 模板数据源的等价替身（仅数据，不含逻辑）----
let rows = [];
// BUG-2026-09-16-012：整库内嵌 materialData 已移除，改为缓存 Map +
// 模板真实的 cacheMaterial/findMaterialByCode（上方已抽取）——数据形状与
// 服务端 api_material_payload 一致，测试数据经真实 cacheMaterial 灌入。
const materialCache = new Map();
const materialCodeIndex = new Map();
[
    { id: 1, code: 'M001', name: '轴承6204', spec: '内径20mm', unit: '套', price: 25.5 },
    { id: 2, code: 'M002', name: '电机', spec: '1.5kW', unit: '台', price: 800 },
].forEach(cacheMaterial);
const warehouseOptions = [
    { id: 7, name: 'WH001 - 主仓库' },
    { id: 8, name: 'WH002 - 备件仓' },
];
const warehouseCodeById = { 7: 'WH001', 8: 'WH002' };
let OPENING_DOC = null;
let capturedBlob = null;
let capturedDownload = null;
const toasts = [];

// ---- 浏览器 API 桩：只为截获 exportRows 真正产出的内容 ----
class Blob {
    constructor(parts) { this.parts = parts; capturedBlob = parts.join(''); }
}
const URL = { createObjectURL: () => 'blob:stub', revokeObjectURL: () => {} };
function showToast(msg) { toasts.push(msg); }
// addRow 等未被本测试覆盖，此处仅提供 exportRows 需要的 showToast / getElementById
const document = {
    body: { appendChild() {}, removeChild() {} },
    getElementById: () => null,
    createElement: () => ({ click() { capturedDownload = this.download; }, set download(v) { this._d = v; }, get download() { return this._d; } }),
};

// ---- 驱动：灌入 rows 后真实调用模板的 exportRows() ----
function drive(rowsData, docDate, docNo) {
    capturedBlob = null; capturedDownload = null; toasts.length = 0;
    rows = rowsData.slice();
    OPENING_DOC = docNo ? { id: 1, doc_no: docNo, date: docDate } : null;
    exportRows();
    return { csv: capturedBlob, filename: capturedDownload, toasts: toasts.slice() };
}

module.exports = { drive, parsePasteLines, splitCsvLine, csvCell };
""",
        encoding="utf-8",
    )
    return harness


def _run_node(harness: Path, script: str) -> str:
    r = subprocess.run(
        [NODE, "-e", f"const h = require({str(harness)!r});\n" + script],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, f"node 执行失败：{r.stderr[:500]}"
    return r.stdout


class TestOpeningStockExportCsv:
    """导出 CSV 的内容正确性与「导出→回导」闭环。"""

    def test_t1_newlines_are_real_not_literal_backslash_n(self, js_runtime):
        """换行必须是真实 \\n；不得出现字面量「反斜杠+n」（本次 BUG 的核心）。"""
        out = _run_node(js_runtime, """
const r = h.drive([
  { material_id: 1, warehouse_id: 7, material_code: 'M001', material_name: '轴承', spec: 's', unit: '套', quantity: 100, price: 25.5, remark: 'r1' },
  { material_id: 2, warehouse_id: 8, material_code: 'M002', material_name: '电机', spec: 's', unit: '台', quantity: 5, price: 800, remark: 'r2' },
], '2026-09-16', 'QS26090001');
console.log(JSON.stringify({
  newlines: (r.csv.match(/\\n/g) || []).length,
  literal: r.csv.includes('\\\\n'),
  lines: r.csv.split('\\n').length,
}));
""")
        import json
        data = json.loads(out)
        assert data["newlines"] == 2, "表头+2 数据行应含 2 个真实换行"
        assert data["lines"] == 3
        assert data["literal"] is False, (
            "导出内容出现了字面量「反斜杠+n」——join('\\\\n') 写法回归，"
            "会导致整个 CSV 塌成一行"
        )

    def test_t1b_source_has_no_escaped_newline_join(self):
        """静态兜底：模板代码中不得再出现 join('\\\\n') 这种写错的换行。

        只扫非注释行——注释里会引用这个错误写法做说明，不能误判。
        """
        code_lines = [
            ln for ln in _template_src().splitlines()
            if not ln.lstrip().startswith(("//", "<!--"))
        ]
        code = "\n".join(code_lines)
        assert "join('\\\\n')" not in code, (
            "模板代码中仍有 join('\\\\n')"
            "（单引号内的 \\\\n 是字面反斜杠+n 而非换行，会让整个 CSV 塌成一行）"
        )
        assert "join('\\n')" in code, "导出应以真实换行符 \\n 拼接"

    def test_t2_header_matches_official_import_template(self):
        """导出表头必须与后端官方导入模板列序一致，否则无法回导。"""
        src = _template_src()
        m = re.search(r"const headers = \[([^\]]+)\]", src)
        assert m, "未找到导出表头定义"
        headers = [h.strip().strip("'\"") for h in m.group(1).split(",")]
        assert headers == [
            "仓库编码", "物料编码", "物料名称", "规格", "单位",
            "数量", "单价", "备注", "日期",
        ], f"导出列序与官方模板不一致：{headers}"

        # 与后端模板下载路由的列序对齐（单一事实来源）
        backend = (APP_DIR / "routes" / "opening_stock.py").read_text(encoding="utf-8")
        bm = re.search(r"headers = \[([^\]]+)\]", backend)
        assert bm, "未找到后端导入模板表头"
        backend_headers = [h.strip().strip("'\"") for h in bm.group(1).split(",")]
        assert headers == backend_headers, (
            f"导出列序 {headers} 与后端导入模板 {backend_headers} 不一致"
        )

    def test_t3_export_then_reimport_roundtrip(self, js_runtime):
        """导出 → 回导闭环：字段逐项一致，带逗号的备注不得裂列。"""
        out = _run_node(js_runtime, """
const r = h.drive([
  { material_id: 1, warehouse_id: 7, material_code: 'M001', material_name: '轴承6204', spec: '内径20mm', unit: '套', quantity: 100, price: 25.5, remark: '首期' },
  { material_id: 2, warehouse_id: 8, material_code: 'M002', material_name: '电机', spec: '1.5kW', unit: '台', quantity: 5, price: 800, remark: '含逗号,的备注' },
], '2026-09-16', 'QS26090001');
const parsed = h.parsePasteLines(r.csv, '');
console.log(JSON.stringify(parsed));
""")
        import json
        data = json.loads(out)
        assert data["errors"] == [], f"回导不应报错：{data['errors']}"
        assert len(data["items"]) == 2, (
            f"回导应得 2 行（表头需自动跳过），实际 {len(data['items'])}"
        )

        first, second = data["items"]
        assert first["material_id"] == 1 and first["warehouse_id"] == 7
        assert first["quantity"] == 100 and first["price"] == 25.5
        assert first["remark"] == "首期" and first["date"] == "2026-09-16"

        assert second["material_id"] == 2 and second["warehouse_id"] == 8
        assert second["quantity"] == 5 and second["price"] == 800
        assert second["remark"] == "含逗号,的备注", (
            "引号内的逗号被当成列分隔符，导出文件回导后备注裂成多列"
        )

    def test_t4_split_csv_line_handles_quotes_and_separators(self, js_runtime):
        """splitCsvLine：双引号包裹 / 引号转义 / 引号内逗号 / 裸 Tab 均正确。"""
        # 用 \\x22 表示双引号，避免与 Python 三引号字符串冲突
        out = _run_node(js_runtime, """
const q = '\\x22';
const cases = [
  'a,b,c',
  q + 'a' + q + ',' + q + 'b,c' + q + ',' + q + 'd' + q,
  q + 'he said ' + q + q + 'hi' + q + q + q + ',x',
  'a\\tb\\tc',
];
console.log(JSON.stringify(cases.map(c => h.splitCsvLine(c))));
""")
        import json
        got = json.loads(out)
        assert got[0] == ["a", "b", "c"]
        assert got[1] == ["a", "b,c", "d"], "引号内的逗号不应作为分隔符"
        assert got[2] == ['he said "hi"', "x"], '引号转义应还原为一个双引号'
        assert got[3] == ["a", "b", "c"], "原有 Tab 分隔必须继续可用"

    def test_t5_header_row_is_skipped(self, js_runtime):
        """导出的文件整段粘回时，表头行不得被当成数据行。"""
        out = _run_node(js_runtime, """
const withHeader = h.parsePasteLines(
  '"仓库编码","物料编码","物料名称","规格","单位","数量","单价","备注","日期"\\n' +
  '"WH001","M001","轴承","s","套","100","25.5","r","2026-09-16"', '');
const noHeader = h.parsePasteLines(
  '"WH001","M001","轴承","s","套","100","25.5","r","2026-09-16"', '');
console.log(JSON.stringify({
  withHeader: withHeader.items.length,
  withHeaderErrors: withHeader.errors.length,
  noHeader: noHeader.items.length,
}));
""")
        import json
        data = json.loads(out)
        assert data["withHeader"] == 1, "表头行未被跳过，被当成了数据行"
        assert data["withHeaderErrors"] == 0
        assert data["noHeader"] == 1, "不带表头时也应正常解析"

    def test_t6_empty_document_warns_instead_of_silent_download(self, js_runtime):
        """空单据点导出：应提示且不产生下载（原来会静默下载只有表头的文件）。"""
        out = _run_node(js_runtime, """
const r = h.drive([], '2026-09-16', 'QS26090001');
console.log(JSON.stringify({
  csv: r.csv,
  filename: r.filename,
  toasts: r.toasts,
}));
""")
        import json
        data = json.loads(out)
        assert data["csv"] is None, (
            "空单据不应生成 Blob（原来会下载一个只有表头的文件）"
        )
        assert data["filename"] is None, "空单据不应触发下载"
        assert data["toasts"], "空单据导出应给出中文提示"
        assert any("没有可导出" in t for t in data["toasts"]), (
            f"提示语不含可识别信息：{data['toasts']}"
        )

    def test_t6b_nonempty_document_downloads_with_doc_no(self, js_runtime):
        """有明细时应正常下载，且文件名带单据号（避免多单互相覆盖）。"""
        out = _run_node(js_runtime, """
const r = h.drive([
  { material_id: 1, warehouse_id: 7, material_code: 'M001', material_name: '轴承', spec: 's', unit: '套', quantity: 1, price: 1, remark: '' },
], '2026-09-16', 'QS26090001');
console.log(JSON.stringify({ filename: r.filename, hasCsv: !!r.csv, toasts: r.toasts }));
""")
        import json
        data = json.loads(out)
        assert data["hasCsv"] is True, "有明细时必须产出内容"
        assert data["filename"] == "opening_stock_QS26090001.csv", (
            f"导出文件名应带单据号，实际 {data['filename']!r}"
        )

    def test_t7_legacy_paste_formats_still_work(self, js_runtime):
        """兼容性：原有宽松粘贴格式（Tab / 裸逗号 / 缺日期列）行为不变。"""
        out = _run_node(js_runtime, """
const cases = {
  tab: 'WH001\\tM001\\t100\\t25.5\\t备注1\\t2026-09-16',
  bareComma: 'WH001,M001,100,25.5,备注1,2026-09-16',
  noDate: 'WH001,M001,100,25.5,备注1',
};
const res = {};
for (const k in cases) {
  const r = h.parsePasteLines(cases[k], '2026-01-01');
  res[k] = { items: r.items.length, errors: r.errors,
             qty: r.items[0] && r.items[0].quantity,
             price: r.items[0] && r.items[0].price,
             wh: r.items[0] && r.items[0].warehouse_id,
             remark: r.items[0] && r.items[0].remark,
             date: r.items[0] && r.items[0].date };
}
console.log(JSON.stringify(res));
""")
        import json
        data = json.loads(out)
        for key in ("tab", "bareComma", "noDate"):
            assert data[key]["items"] == 1, f"{key} 格式解析失败：{data[key]['errors']}"
            assert data[key]["qty"] == 100
            assert data[key]["price"] == 25.5
            assert data[key]["wh"] == 7
            assert data[key]["remark"] == "备注1"
        # 无日期列时回落默认日期，不报错
        assert data["noDate"]["errors"] == []
        assert data["noDate"]["date"] == "2026-01-01"


class TestOpeningStockExportStatic:
    """导出相关的静态契约（不依赖 node）。"""

    def test_warehouse_code_map_declared(self):
        """导出需要仓库编码，模板必须声明 id→code 映射。"""
        src = _template_src()
        assert "const warehouseCodeById" in src, (
            "缺少 warehouseCodeById 映射，导出第 1 列「仓库编码」取值会落空"
        )
        assert re.search(r"warehouseCodeById\s*=\s*\{", src)
        # 取值时优先编码、回退名称
        assert "warehouseCodeById[row.warehouse_id]" in src

    def test_export_filename_includes_doc_no(self):
        """导出文件名带单据号，避免多张单据导出互相覆盖。"""
        src = _template_src()
        assert "opening_stock_' +" in src or "opening_stock_\" +" in src, (
            "导出文件名未带单据号"
        )
        assert "OPENING_DOC.doc_no" in src.split("link.download")[1][:200]

    def test_export_uses_real_date_input_id(self):
        """日期取真实存在的表头日期输入框 id（headerDocDate）。"""
        src = _template_src()
        body = src.split("function exportRows()")[1].split("\nfunction ")[0]
        assert "headerDocDate" in body, (
            "导出的日期列应取 headerDocDate（模板中真实存在的表头日期输入框）"
        )
        assert "getElementById('docDate')" not in body, (
            "docDate 元素在模板中不存在，取值为空会导致日期列空掉"
        )
