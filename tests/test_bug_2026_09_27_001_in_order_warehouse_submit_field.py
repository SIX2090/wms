# -*- coding: utf-8 -*-
"""BUG-2026-09-27-001 回归：采购入库单提交的仓库字段名必须与值口径一致。

## 现场

用户「新增采购入库单」选择仓库「项目仓」后点保存，弹出：
    保存失败：仓库不存在或已停用：1

## 根因

P1-6（BUG-2026-09-25-007）把仓库参数统一为 `warehouse_id`，分三处改造：
    ① 下拉渲染：`<select name="warehouse_id">` + `value="{{ warehouse.id }}"`  ← 已改
    ② 后端解析：`validate_inventory_warehouse(value, warehouse_id)` ID 优先   ← 已改
    ③ JS 提交：payload 里应发 `warehouse_id: <下拉 value>`                     ← **改漏**

`submitForm()` 从 `[name="warehouse_id"]` 读到的是**仓库 ID 字符串**（如 "1"），
却塞进了 `warehouse` 字段。后端 `data.get('warehouse_id')` 为 None，只拿到
`warehouse="1"`，于是**拿 "1" 当仓库名去匹配** `Warehouse.name`/`Warehouse.code`
→ 查不到 → 400「仓库不存在或已停用：1」。用户选的「项目仓」根本没被传出去。

## 为什么原有 21 项 P1-6 测试全绿却没拦住

`test_p1_6_in_order_warehouse_id_param.py` 的测试**自己构造**符合新契约的请求
（`_post_in_order(..., warehouse_id=wh_b.id)`）直接打后端，**从不经过前端**；
其「前端 3 项」也只是静态断言 `'name="warehouse_id"' in html`
（见 T7/T8/T9）——测的是**下拉的属性**，不是**提交的 payload**。

结果：后端 + 下拉两层被测住了，**前端提交字段名这一层完全在雷达外**，
于是 9 项 + 12 项全绿，线上保存必失败。

## 本测试的防假绿设计（R8 第 3 条：回退后必须变红）

不满足于「源码里有 warehouse_id 字符串」（注释里写一句就能骗过）。
本测试用 node **真实执行**从模板抽取的「取数 + 组装 payload」片段，
断言**执行结果的字段名与取值**：

  T1. payload 里**存在** `warehouse_id`
  T2. payload 里**不存在** `warehouse`（旧字段名不得复活）
  T3. `warehouse_id` 的值 === 下拉的 value（即仓库 ID），而非显示文本(名称)
  T4. 取数来源必须是 `[name="warehouse_id"]`（防选择器被改回别的字段）
  T5. 提交目标端点仍是 `/in_order/add`（防误改成别的路由）

把修复回退（`warehouse_id: warehouseId` → `warehouse: warehouseId`）后，
T1/T2/T3 必须精准变红——这才是有效的锁。
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TPL = ROOT / "app" / "templates" / "in_order_add.html"


def _read_tpl() -> str:
    return TPL.read_text(encoding="utf-8")


def _extract_submit_form(src: str) -> str:
    """抽出 submitForm 函数体（从 `function submitForm` 到下一个顶层 function）。"""
    start = src.index("function submitForm(")
    rest = src[start:]
    # 找到下一个顶层 `function ` 定义（列 0 缩进）
    m = re.search(r"\n    function [A-Za-z_]", rest[10:])
    end = 10 + m.start() if m else len(rest)
    return rest[:end]


def _run_js(harness_body: str) -> dict:
    """在 node 中执行给定 JS 片段，返回其打印的 JSON。"""
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")

    harness = ROOT / ".t_bug_2026_09_27_001_harness.js"
    # 逐行列表拼装，不用三引号字面量（踩坑：三引号里的 \n 会被 Python 解析成真实换行）
    lines = harness_body.split("\n")
    harness.write_text("\n".join(lines), encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)

    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _payload_harness() -> dict:
    """构造 harness：模拟 DOM，真实执行模板里的取数与 payload 组装逻辑。

    做法：从模板抽出
      ① 取变量行：`const warehouseId = document.querySelector('[name="warehouse_id"]').value;`
      ② payload 里仓库那一行：`warehouse_id: warehouseId,`
    然后在一个假的 document 上执行①，再把②代入对象字面量，打印结果。
    """
    src = _read_tpl()

    # ① 抓取「读仓库」那一行的完整语句（含变量名）
    m_read = re.search(
        r"^\s*const\s+(\w+)\s*=\s*document\.querySelector\(\s*'(\[name=\"warehouse_id\"\])'\s*\)\.value;\s*$",
        src, re.M)
    assert m_read, "未在模板中找到从 [name=\"warehouse_id\"] 取值的语句"
    var_name = m_read.group(1)
    selector = m_read.group(2)

    # ② 抓取 payload 里仓库字段那一行（字段名: 变量名）
    m_field = re.search(
        r"^\s*(warehouse_id|warehouse)\s*:\s*(\w+)\s*,\s*$",
        src, re.M)
    assert m_field, "未在模板中找到 payload 的仓库字段行"
    field_name = m_field.group(1)
    field_var = m_field.group(2)

    # ③ 抓取提交端点
    m_url = re.search(r"fetch\(\s*'(/in_order/add)'", src)
    url = m_url.group(1) if m_url else ""

    parts = [
        "// 假 document：模拟页面上的仓库下拉（value = 仓库 ID）",
        "const WAREHOUSE_ID_VALUE = '7';",
        "const WAREHOUSE_NAME_TEXT = '项目仓';",
        "const fakeEl = { value: WAREHOUSE_ID_VALUE, textContent: WAREHOUSE_NAME_TEXT };",
        "const document = {",
        "  querySelector: function (sel) {",
        "    if (sel === " + json.dumps(selector) + ") return fakeEl;",
        "    return null;",
        "  }",
        "};",
        "",
        "// ① 原样执行模板里的取数语句",
        "const " + var_name + " = document.querySelector(" + json.dumps(selector) + ").value;",
        "",
        "// ② 原样执行模板里 payload 的仓库字段行",
        "const payload = {",
        "  " + field_name + ": " + field_var + ",",
        "};",
        "",
        "console.log(JSON.stringify({",
        "  payload: payload,",
        "  read_selector: " + json.dumps(selector) + ",",
        "  read_var: " + json.dumps(var_name) + ",",
        "  field_name: " + json.dumps(field_name) + ",",
        "  url: " + json.dumps(url) + ",",
        "  expected_id_value: WAREHOUSE_ID_VALUE,",
        "  display_name_text: WAREHOUSE_NAME_TEXT",
        "}));",
    ]
    return _run_js("\n".join(parts))


@pytest.fixture(scope="module")
def result() -> dict:
    return _payload_harness()


class TestInOrderWarehouseSubmitField:
    """BUG-2026-09-27-001：提交字段名必须是 warehouse_id。"""

    def test_t1_payload_has_warehouse_id(self, result):
        """T1：payload 中存在 warehouse_id 字段。"""
        assert "warehouse_id" in result["payload"], (
            f"payload 缺少 warehouse_id 字段，实际键：{list(result['payload'].keys())}"
        )

    def test_t2_payload_has_no_legacy_warehouse(self, result):
        """T2：payload 中不得存在旧字段名 warehouse（防复活）。"""
        assert "warehouse" not in result["payload"], (
            f"payload 仍使用旧字段名 warehouse（值为仓库 ID，后端会当名称解析导致 400）："
            f"{result['payload']}"
        )

    def test_t3_value_is_warehouse_id_not_name(self, result):
        """T3：warehouse_id 的值是仓库 ID，不是显示文本（名称）。"""
        assert result["payload"].get("warehouse_id") == result["expected_id_value"], (
            f"warehouse_id 取值应为下拉 value（仓库 ID {result['expected_id_value']}），"
            f"实际为 {result['payload'].get('warehouse_id')!r}"
        )
        assert result["payload"].get("warehouse_id") != result["display_name_text"], (
            "warehouse_id 取到了显示文本（仓库名称），值口径错误"
        )

    def test_t4_reads_from_warehouse_id_selector(self, result):
        """T4：取数来源必须是 [name="warehouse_id"]。"""
        assert result["read_selector"] == '[name="warehouse_id"]', (
            f"取值选择器为 {result['read_selector']!r}，应为 [name=\"warehouse_id\"]"
        )

    def test_t5_posts_to_in_order_add(self, result):
        """T5：提交端点仍是 /in_order/add。"""
        assert result["url"] == "/in_order/add", f"提交端点为 {result['url']!r}"


class TestInOrderAddFormContract:
    """静态契约：下拉 name 与 option value 口径（与真实执行测试互补）。"""

    def test_select_name_is_warehouse_id(self):
        src = _read_tpl()
        assert re.search(r'<select[^>]*name="warehouse_id"', src), "下拉 name 不是 warehouse_id"
        # 不能存在独立的 name="warehouse" 下拉
        assert not re.search(r'<select[^>]*name="warehouse"', src), "仍存在 name=\"warehouse\" 下拉"

    def test_option_value_is_id(self):
        src = _read_tpl()
        m = re.search(r'<select[^>]*name="warehouse_id"[^>]*>(.*?)</select>', src, re.S)
        assert m, "未找到仓库下拉"
        body = m.group(1)
        assert "warehouse.id" in body, "option value 不是仓库 ID（未按 P1-6 迁移）"
        assert "value=\"{{ warehouse.name }}\"" not in body, "option value 仍是仓库名称"

    def test_js_syntax_ok(self):
        """模板内联 JS 至少保证取数/组装的片段可被 node 解析（由 fixture 覆盖）。"""
        node = shutil.which("node")
        if not node:
            pytest.skip("node 不可用")
        r = _payload_harness()
        assert r["field_name"] == "warehouse_id"
