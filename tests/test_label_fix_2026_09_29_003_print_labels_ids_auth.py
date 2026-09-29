# -*- coding: utf-8 -*-
"""LABEL-FIX-2026-09-29-003：print_labels ids 转 int + 权限收紧。

生效确认：
① ids 按数字过滤（与 label.py print_batch_labels 口径一致），非数字不再进 in_()；
② 路由挂 require_role（与 label_template_detail 同口径），不留 @login_required 裸奔。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROUTE = ROOT / "app" / "routes" / "label_barcode.py"


def _route_segment(text):
    i = text.find("'/label_template/<int:id>/print'")
    assert i > 0, "未找到 print_labels 路由声明"
    # 取路由声明到下一个路由/文件尾之间的片段
    j = text.find("@app.route(", i + 10)
    return text[i:j if j > 0 else len(text)]


def test_ids_parsed_as_int():
    text = ROUTE.read_text(encoding="utf-8")
    seg = _route_segment(text)
    assert "int(i) for i in ids if i.strip().isdigit()" in seg, \
        "ids 未按数字过滤（与 label.py print_batch_labels 口径不一致）"
    # 旧写法：字符串列表直接进 in_() 必须消失
    assert "Material.id.in_(material_ids)" not in seg


def test_route_requires_role():
    text = ROUTE.read_text(encoding="utf-8")
    seg = _route_segment(text)
    assert "require_role" in seg, "print_labels 路由缺少 require_role（越权面）"
