# -*- coding: utf-8 -*-
"""BUG-2026-09-27-001（同类点）回归：库存调整单提交的仓库字段名必须与值口径一致。

## 背景

与 `test_bug_2026_09_27_001_in_order_warehouse_submit_field.py` 同根因
（P1-6 前端提交字段名改漏），本条覆盖**库存调整单** `adjustment_add.html`。

`submitForm()` 从 `[name="warehouse_id"]` 读到的是**仓库 ID**（下拉 value 是
`{{ warehouse.id }}`），却塞进 `warehouse` 字段。后端
`/adjustment/add` 虽同时接收 `warehouse` 与 `warehouse_id`，但 `warehouse_id`
收不到（前端没发），只拿到 `warehouse="1"`，于是**拿 "1" 当仓库名**匹配
`Warehouse.name`/`code` → 查不到 → 400「仓库不存在或已停用：1」。

## 本测试的防假绿设计（R8 第 3 条）

与 in_order 同款：用 node **真实执行**从模板抽取的取数与 payload 组装片段，
断言**执行结果**的字段名与取值，而非源码字符串。

  T1. payload 里存在 `warehouse_id`
  T2. payload 里不存在旧字段 `warehouse`
  T3. `warehouse_id` 的值 === 下拉 value（仓库 ID），而非显示文本
  T4. 取数来源是 `[name="warehouse_id"]`
  T5. 提交端点是 `/adjustment/add`
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app" / "templates" / "adjustment_add.html"


def _read_tpl() -> str:
    return TPL.read_text(encoding="utf-8")


def _run_js(harness_body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    harness = ROOT / ".t_bug_2026_09_27_001_adj_harness.js"
    harness.write_text(harness_body, encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _payload_harness() -> dict:
    src = _read_tpl()

    # ① 取数语句：调整单是 `const warehouseId = warehouseEl ? warehouseEl.value.trim() : '';`
    #    其中 warehouseEl = document.querySelector('[name="warehouse_id"]')
    m_sel = re.search(
        r"const\s+(\w+)\s*=\s*document\.querySelector\(\s*'(\[name=\"warehouse_id\"\])'\s*\);",
        src)
    assert m_sel, "未找到 [name=\"warehouse_id\"] 的 querySelector 语句"
    el_var, selector = m_sel.group(1), m_sel.group(2)

    m_read = re.search(
        r"const\s+(\w+)\s*=\s*" + re.escape(el_var) + r"\s*\?\s*" + re.escape(el_var) + r"\.value\.trim\(\)\s*:\s*''\s*;",
        src)
    assert m_read, "未找到从下拉读取仓库 ID 的语句"
    id_var = m_read.group(1)

    # ② payload 里的仓库字段行
    m_field = re.search(r"^\s*(warehouse_id|warehouse)\s*:\s*(\w+)\s*,\s*$", src, re.M)
    assert m_field, "未找到 payload 的仓库字段行"
    field_name, field_var = m_field.group(1), m_field.group(2)

    # ③ 提交端点
    m_url = re.search(r"fetch\(\s*'(/adjustment/add)'", src)
    url = m_url.group(1) if m_url else ""

    parts = [
        "const WAREHOUSE_ID_VALUE = '3';",
        "const WAREHOUSE_NAME_TEXT = '项目仓';",
        "const fakeEl = { value: ' ' + WAREHOUSE_ID_VALUE + ' ', textContent: WAREHOUSE_NAME_TEXT };",
        "const document = {",
        "  querySelector: function (sel) {",
        "    if (sel === " + json.dumps(selector) + ") return fakeEl;",
        "    return null;",
        "  }",
        "};",
        "",
        "const " + el_var + " = document.querySelector(" + json.dumps(selector) + ");",
        "const " + id_var + " = " + el_var + " ? " + el_var + ".value.trim() : '';",
        "",
        "const payload = { " + field_name + ": " + field_var + " };",
        "",
        "console.log(JSON.stringify({",
        "  payload: payload,",
        "  read_selector: " + json.dumps(selector) + ",",
        "  field_name: " + json.dumps(field_name) + ",",
        "  field_var: " + json.dumps(field_var) + ",",
        "  url: " + json.dumps(url) + ",",
        "  expected_id_value: WAREHOUSE_ID_VALUE,",
        "  display_name_text: WAREHOUSE_NAME_TEXT",
        "}));",
    ]
    return _run_js("\n".join(parts))


@pytest.fixture(scope="module")
def result() -> dict:
    return _payload_harness()


class TestAdjustmentWarehouseSubmitField:
    """BUG-2026-09-27-001 同类点：调整单提交字段名必须是 warehouse_id。"""

    def test_t1_payload_has_warehouse_id(self, result):
        assert "warehouse_id" in result["payload"], (
            f"payload 缺少 warehouse_id 字段，实际键：{list(result['payload'].keys())}"
        )

    def test_t2_payload_has_no_legacy_warehouse(self, result):
        assert "warehouse" not in result["payload"], (
            f"payload 仍使用旧字段名 warehouse（值为仓库 ID，后端当名称解析导致 400）："
            f"{result['payload']}"
        )

    def test_t3_value_is_warehouse_id_not_name(self, result):
        assert result["payload"].get("warehouse_id") == result["expected_id_value"], (
            f"warehouse_id 应为下拉 value（仓库 ID {result['expected_id_value']}），"
            f"实际 {result['payload'].get('warehouse_id')!r}"
        )
        assert result["payload"].get("warehouse_id") != result["display_name_text"], (
            "warehouse_id 取到了显示文本（仓库名称），值口径错误"
        )

    def test_t4_reads_from_warehouse_id_selector(self, result):
        assert result["read_selector"] == '[name="warehouse_id"]', (
            f"取值选择器为 {result['read_selector']!r}"
        )

    def test_t5_posts_to_adjustment_add(self, result):
        assert result["url"] == "/adjustment/add", f"提交端点为 {result['url']!r}"


class TestAdjustmentFormContract:
    """静态契约：下拉 name 与 option value 口径。"""

    def test_select_name_is_warehouse_id(self):
        src = _read_tpl()
        assert re.search(r'<select[^>]*name="warehouse_id"', src), "下拉 name 不是 warehouse_id"

    def test_option_value_is_id(self):
        src = _read_tpl()
        m = re.search(r'<select[^>]*name="warehouse_id"[^>]*>(.*?)</select>', src, re.S)
        assert m, "未找到仓库下拉"
        assert "warehouse.id" in m.group(1), "option value 不是仓库 ID"

    def test_field_name_is_warehouse_id(self, result):
        assert result["field_name"] == "warehouse_id"
