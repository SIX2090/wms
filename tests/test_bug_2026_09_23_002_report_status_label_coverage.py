# -*- coding: utf-8 -*-
"""BUG-2026-09-23-002：报表状态列翻译残缺，采购单 partial/closed 原样显示英文。

现场（真实浏览器模拟，采购订单执行统计表）：一张 partial（部分入库）的
采购订单在报表「状态」列显示为英文 "partial"，而同页 completed 单显示
「已完成」——用户看到的报表中英文混杂。

根因：report_view.html 的状态翻译是**手写的二值映射**（completed→已完成 /
pending→待处理，其余原样透传），且同型代码散落在两条渲染路径
（屏幕徽章 ~L509 / 打印 ~L405）。后端 `purchase_order_status_label` 有完整
四值映射（pending/partial/completed/closed），前端没有对齐——R6 同型：
翻译逻辑多消费点各自内联、覆盖不全。同时该报表的状态**筛选下拉**也只有
待处理/已完成两项，无法按「部分入库/已关闭」过滤（后端本就支持）。

修复：模板内引入共享 STATUS_LABELS/STATUS_BADGES 映射（四值，与后端同口径），
屏幕徽章与打印渲染统一走 statusLabel()；筛选下拉仅对
purchase_order_execution 追加 partial/closed 两项（避免污染入出库/盘点报表）。

断言：
  T1 STATUS_LABELS 必须覆盖 pending/partial/completed/closed 四值
  T2 屏幕渲染不得再出现只认 completed/pending 的硬编码徽章分支
  T3 打印渲染不得再出现二值三元翻译
  T4 筛选下拉对 purchase_order_execution 提供 partial/closed 选项
"""
import re
from pathlib import Path

TPL = Path(__file__).resolve().parents[1] / "app" / "templates" / "report_view.html"


def _src() -> str:
    return TPL.read_text(encoding="utf-8")


def test_t1_status_labels_cover_all_purchase_order_statuses():
    src = _src()
    m = re.search(r"STATUS_LABELS\s*=\s*\{(.*?)\}", src, re.S)
    assert m, "report_view.html 缺少共享 STATUS_LABELS 映射"
    body = m.group(1)
    for status, label in (("pending", "待处理"), ("partial", "部分入库"),
                          ("completed", "已完成"), ("closed", "已关闭")):
        assert re.search(rf"{status}\s*:\s*'{label}'", body), (
            f"STATUS_LABELS 缺少 {status} → {label} 映射，"
            f"该状态单据将在报表状态列原样显示英文"
        )


def test_t2_screen_badge_render_uses_shared_map():
    src = _src()
    # 旧形态：只认 completed/pending 两个硬编码 if 分支
    assert "badge bg-success\">已完成" not in src, (
        "屏幕渲染仍硬编码 completed→已完成 徽章分支，partial 会漏翻译"
    )
    assert "badge bg-warning text-dark\">待处理" not in src, (
        "屏幕渲染仍硬编码 pending→待处理 徽章分支"
    )
    assert "STATUS_BADGES[value]" in src and "STATUS_LABELS[value]" in src, (
        "屏幕渲染未统一走 STATUS_LABELS/STATUS_BADGES 共享映射"
    )


def test_t3_print_render_uses_shared_label_fn():
    src = _src()
    assert "'已完成' : (value === 'pending' ? '待处理' : value)" not in src, (
        "打印渲染仍是二值三元翻译，partial/closed 会原样显示英文"
    )
    assert re.search(r"column\.type === 'status'\)\s*value\s*=\s*statusLabel\(value\)", src), (
        "打印渲染未统一走 statusLabel()"
    )


def test_t4_purchase_execution_filter_offers_partial_and_closed():
    src = _src()
    # 限定只在 purchase_order_execution 下追加，防止污染其他报表
    m = re.search(
        r"if\s+report_type\s*==\s*'purchase_order_execution'\s*%\}(.*?)endif",
        src, re.S)
    assert m, "筛选下拉未对 purchase_order_execution 追加状态选项"
    block = m.group(1)
    assert 'value="partial"' in block and "部分入库" in block, "缺少 partial→部分入库 选项"
    assert 'value="closed"' in block and "已关闭" in block, "缺少 closed→已关闭 选项"
