# -*- coding: utf-8 -*-
"""LABEL-FIX-2026-09-29-001：print_label.html 必须支持设计器全部字段（含别名）。

生效确认：设计器左栏全部 data-field 每个都在 print_label.html 有对应分支，
不再静默打印成空白（A12）；date 字段所需 now 由后端 print_labels 传入。
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
DESIGNER = ROOT / "app" / "templates" / "material.html"
PRINT_PAGE = ROOT / "app" / "templates" / "print_label.html"
ROUTE = ROOT / "app" / "routes" / "label_barcode.py"


def _designer_fields():
    text = DESIGNER.read_text(encoding="utf-8")
    return set(re.findall(r'data-field="([^"]+)"\s+data-label="', text))


def _print_page_branches():
    text = PRINT_PAGE.read_text(encoding="utf-8")
    return set(re.findall(r"cell_data\.field == '(\w+)'", text))


def test_designer_fields_nonempty_baseline():
    fields = _designer_fields()
    # 基线锁：设计器 11 个字段，若左栏被改动此测试迫使人工复核本契约
    assert len(fields) == 11, f"设计器字段数变化（{len(fields)}），需复核打印页覆盖契约"


def test_print_label_covers_all_designer_fields():
    designer = _designer_fields()
    branches = _print_page_branches()
    missing = designer - branches
    assert not missing, (
        f"print_label.html 缺失设计器字段分支（会静默打印成空白）: {sorted(missing)}"
    )


def test_print_labels_passes_now_for_date_field():
    """date 分支用 now.strftime，后端必须传 now，否则静默空白（A12）。"""
    text = ROUTE.read_text(encoding="utf-8")
    i = text.find("'/label_template/<int:id>/print'")
    assert i > 0
    j = text.find("@app.route(", i + 10)
    seg = text[i:j if j > 0 else len(text)]
    assert "now=datetime.now()" in seg, "print_labels 未向模板传 now，date 字段将静默空白"
