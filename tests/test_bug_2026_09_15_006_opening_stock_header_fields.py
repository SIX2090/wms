# -*- coding: utf-8 -*-
"""BUG-2026-09-15-006 回归：期初库存单头部"摆设"字段清理 + 表头备注接通保存。

用户反馈"这个地方的功能有个屁用"（opening_stock.html 新增期初库存单头部）。

根因（静态核查证实）：表头三个字段是"摆设"——
- 备注（headerRemark）：有输入框，但 saveDocument() 从不读取，用户填了备注
  保存时被直接丢弃（最不友好的一类"没用"）；
- 单据编号（opening_doc_no）：OP+当天日期拼接的只读框，saveDocument() 不提交，
  这页是批量台账、单号不能用于查单据，纯装饰；
- 入库来源（期初建账）：只读固定文本，纯展示。
saveDocument() 实际只读取 日期 与 单据仓库 两个表头字段。

修复（用户选定"备注接通 + 删装饰"）：
- 表头备注接通保存：saveDocument() 读取 headerRemark，作为各行明细的默认备注
  （行内已单独填写备注的行不受影响），后端 batch_save 本就按 item.remark 落库；
- 删除装饰字段：单据编号、入库来源 两个只读框（模板 + 路由 opening_doc_no 死代码）。

验收点：
T1. 「单据编号」装饰字段已移除（模板无 单据编号 标签、无 opening_doc_no）。
T2. 「入库来源」装饰字段已移除（模板无 入库来源 标签）。
T3. 表头备注已接通：saveDocument() 读取 headerRemark 并回落到 item.remark。
T4. 路由不再传 opening_doc_no（死代码清理）。
T5. 不误删：日期、单据仓库、备注输入框、表头日期链路仍在。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "app" / "templates" / "opening_stock.html"
ROUTE = ROOT / "app" / "routes" / "opening_stock.py"


def _read(p: Path) -> str:
    assert p.exists(), f"文件缺失：{p}"
    return p.read_text(encoding="utf-8")


class TestDecorativeFieldsRemoved:
    def test_t1_doc_number_field_removed(self):
        html = _read(TEMPLATE)
        assert "单据编号" not in html, "装饰性的「单据编号」字段应移除"
        assert "opening_doc_no" not in html, "模板不应再引用 opening_doc_no"

    def test_t2_inbound_source_field_removed(self):
        html = _read(TEMPLATE)
        assert "入库来源" not in html, "只读固定的「入库来源」字段应移除"

    def test_t4_route_no_longer_passes_doc_number(self):
        src = _read(ROUTE)
        assert "opening_doc_no" not in src, "路由不应再计算/传递 opening_doc_no（死代码）"


class TestHeaderRemarkWired:
    def test_t3_header_remark_saved_as_default_row_remark(self):
        html = _read(TEMPLATE)
        assert "getElementById('headerRemark')" in html, (
            "saveDocument() 应读取表头备注 headerRemark"
        )
        assert "item.remark = headerRemark" in html, (
            "表头备注应回落为各行明细的默认备注（行内已填备注的行不受影响）"
        )


class TestKeptFieldsIntact:
    def test_t5_kept_fields_present(self):
        html = _read(TEMPLATE)
        # 日期与单据仓库是表头真正有用的两个字段，必须保留
        assert 'id="headerDocDate"' in html, "日期字段不应被误删"
        assert 'id="headerWarehouse"' in html, "单据仓库字段不应被误删"
        assert 'id="headerRemark"' in html, "备注输入框不应被误删（要接通保存）"
        # 表头日期链路（BUG-2026-09-15-004）不得被本改动破坏
        assert "getHeaderDocDate" in html, "表头日期读取函数应保留"
        assert "item.date = headerDate" in html, "表头日期落行逻辑应保留"
