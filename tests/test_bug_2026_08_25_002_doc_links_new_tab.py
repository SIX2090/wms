# -*- coding: utf-8 -*-
"""BUG-2026-08-25-002 回归测试：单据/报表/列表点击记录项必须新开浏览器标签页。

需求（2026-08-25）：所有单据、报表、列表，"点击进入某一项"必须新开页签。
例：库存台账点领料单、入库明细点单据编号、采购订单列表点单号，
原列表页保持打开不关闭，便于对照查询。（report_view.html 已由 f28b921 先行修复，
本轮把同一规则推广到全部列表/报表/单据交叉引用链接。）

范围判定：
- 命中：href 含 url_for('..._detail') / detail_url / _edit_page / safeJumpUrl 的 <a>
  （即"进入某一项"的记录级链接，含行内 查看/编辑 按钮与详情页的 来源单 交叉引用）
- 排除：菜单、分页、新增/导出/打印、返回/取消等页面内导航，以及详情页内
  同记录"编辑"模式切换按钮（EXCLUSIONS 显式登记理由）

测试用例：
  T1. 全模板扫描：所有记录级链接必须含 target="_blank" 且 rel="noopener"（排除项除外）
  T2. 关键列表页（入库/出库/采购/销售/盘点/调拨/调整/领料申请）单号链接逐一点名验证
  T3. 排除项仍然保持原样（防误改返回/编辑切换等页面内导航）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

TPL_DIR = Path(__file__).resolve().parent.parent / "app" / "templates"

ANCHOR = re.compile(r"<a\b[^>]*>")
RECORD_HREF = re.compile(
    r"url_for\('[a-z_]*_detail'|detail_url|_edit_page|safeJumpUrl\("
)

# 显式排除登记：(文件名, 理由) —— 均为"页面内导航/同记录模式切换"，不属于"列表进入某一项"
EXCLUSIONS = {
    "base.html": "菜单/导航链接",
    "in_order_push.html": "下推页「返回单据」回退导航",
    "sales_order_edit.html": "编辑页「取消」返回详情，页面内回退导航",
    "label_preview.html": "预览页「返回模板」回退导航",
    "purchase_order_detail.html": "详情页「编辑」为同记录模式切换",
    "sales_order_detail.html": "详情页「编辑」为同记录模式切换",
    "purchase_request_detail.html": "详情页「编辑」为同记录模式切换",
    "after_sale_out_detail.html": "详情页「编辑」为同记录模式切换",
}

# T2 点名验证的关键列表页单号链接（文件 -> 必须出现的记录级端点特征）
KEY_LIST_PAGES = {
    "in_order.html": "in_order_detail",
    "out_order.html": "out_order_detail",
    "purchase_order.html": "purchase_order_detail",
    "purchase_request.html": "purchase_request_detail",
    "sales_order.html": "sales_order_detail",
    "check.html": "check_detail",
    "transfer.html": "transfer_detail",
    "adjustment.html": "adjustment_detail",
    "requisition.html": "requisition_detail",
    "after_sale_out.html": "after_sale_out_detail",
    "bom.html": "bom_detail",
    "subcontract_progress.html": "subcontract_detail",
    "pending_documents.html": "detail_url",
    "approval.html": "detail_url",
    "sales_report.html": "sales_order_detail",
    "sales_outflow_report.html": "out_order_detail",
    "sales_reconciliation_report.html": "sales_order_detail",
}


def _iter_record_anchors():
    """产出 (文件, 锚点标签) 列表：所有记录级链接。"""
    for tpl in sorted(TPL_DIR.glob("*.html")):
        src = tpl.read_text(encoding="utf-8")
        for m in ANCHOR.finditer(src):
            tag = m.group(0)
            if "href" in tag and RECORD_HREF.search(tag):
                yield tpl.name, tag


def test_t1_all_record_links_open_new_tab():
    """全模板扫描：记录级链接必须 target=_blank + rel=noopener（排除项除外）。"""
    violations = []
    for fname, tag in _iter_record_anchors():
        if fname in EXCLUSIONS:
            continue
        if 'target="_blank"' not in tag or 'rel="noopener"' not in tag:
            violations.append(f"{fname}: {tag.strip()[:120]}")
    assert not violations, (
        "以下记录级链接未新开标签页：\n" + "\n".join(violations)
    )


def test_t2_key_list_pages_order_no_links():
    """关键列表/报表页的单号链接逐一点名验证已新开标签页。"""
    for fname, endpoint_hint in KEY_LIST_PAGES.items():
        src = (TPL_DIR / fname).read_text(encoding="utf-8")
        hits = [
            m.group(0) for m in ANCHOR.finditer(src)
            if endpoint_hint in m.group(0)
        ]
        assert hits, f"{fname} 未找到指向 {endpoint_hint} 的链接"
        for tag in hits:
            assert 'target="_blank"' in tag, f"{fname} 链接缺 target=_blank：{tag.strip()[:100]}"
            assert 'rel="noopener"' in tag, f"{fname} 链接缺 rel=noopener：{tag.strip()[:100]}"


def test_t3_exclusions_remain_same_tab():
    """排除项（返回/同记录编辑切换）不得被误加 target=_blank。"""
    checks = {
        "in_order_push.html": "in_order_detail",
        "sales_order_edit.html": "sales_order_detail",
        "label_preview.html": "label_template_detail",
    }
    for fname, hint in checks.items():
        src = (TPL_DIR / fname).read_text(encoding="utf-8")
        for m in ANCHOR.finditer(src):
            tag = m.group(0)
            if hint in tag:
                assert 'target="_blank"' not in tag, (
                    f"{fname} 的回退导航被误加 target=_blank：{tag.strip()[:100]}"
                )
