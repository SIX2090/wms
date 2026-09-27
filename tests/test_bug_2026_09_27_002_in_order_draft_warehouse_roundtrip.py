# -*- coding: utf-8 -*-
"""BUG-2026-09-27-002 回归：采购入库单自动草稿的仓库/备注字段存取闭环。

## 现场（与 BUG-2026-09-27-001 同批排查发现）

`in_order_add.html` 的自动草稿（localStorage，30 秒一次）用两个**在本模板中
不存在**的 id 取值：

    warehouse: document.querySelector('#warehouseSelect')?.value || '',   // 元素不存在
    remark:    document.querySelector('#remarkInput')?.value   || '',   // 元素不存在

- 仓库下拉的真实标识是 `<select name="warehouse_id">`（无 id）。
- 备注的真实标识是 `<textarea name="remark">`（无 id）。
- 本模板其他 4 处读备注一律用 `[name="remark"]`（1465/1633/2181/2427 行），
  只有草稿这两处用了不存在的 id。

后果：`querySelector('#...')` 返回 `null`，`?.value` 为 `undefined`，
`|| ''` 兜成空串 → **自动草稿里仓库与备注永远是空的**；恢复时
`if (data.warehouse)` / `if (data.remark)` 恒为假，**也永远回填不上**。
用户在录单中途关掉页面，30 秒前自动保存的草稿丢失仓库与备注，且无任何提示——
典型「静默失效」（不报错、不崩溃，功能就是不生效）。

## 本测试的防假绿设计（R8 第 3 条：回退后必须变红）

用 node **真实执行**模板里的「取数 → 存草稿 → 恢复」闭环，
**不依赖源码字符串断言**：

  T1. `collectFormData()` 存出的对象里，仓库字段名是 `warehouse_id` 且值非空
  T2. 存出的对象里不存在旧字段 `warehouse`（防复活）
  T3. 存出的对象里备注字段值为非空（防 `#remarkInput` 复活）
  T4. 恢复逻辑能从草稿数据回填到下拉（setter 被调用且值一致）
  T5. 恢复逻辑能从草稿数据回填到备注

T1/T3 用「值必须非空」而非「字段存在」——因为旧代码的字段**存在但恒为空**，
只断言存在会漏掉这个缺陷。
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


def _run_js(harness_body: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    harness = ROOT / ".t_bug_2026_09_27_002_harness.js"
    harness.write_text(harness_body, encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def _extract_collect_return(src: str) -> str:
    """抽出 collectFormData() 里 return {...} 的对象字面量源码。"""
    start = src.index("function collectFormData()")
    seg = src[start:]
    m = re.search(r"return \{", seg)
    assert m, "collectFormData 未找到 return {"
    i = seg.index("return {") + len("return {")
    depth = 1
    j = i
    while depth and j < len(seg):
        if seg[j] == "{":
            depth += 1
        elif seg[j] == "}":
            depth -= 1
        j += 1
    return seg[i:j - 1]


def _extract_restore_warehouse(src: str) -> str:
    """抽出 restoreDraft() 里仓库恢复片段。"""
    m = re.search(r"(// 恢复仓库.*?\n\s*\})", src, re.S)
    assert m, "未找到恢复仓库片段"
    return m.group(1)


def _extract_restore_remark(src: str) -> str:
    m = re.search(r"(// 恢复备注.*?\n\s*\})", src, re.S)
    assert m, "未找到恢复备注片段"
    return m.group(1)


def _harness() -> dict:
    src = _read_tpl()
    collect_body = _extract_collect_return(src)
    restore_wh = _extract_restore_warehouse(src)
    restore_rm = _extract_restore_remark(src)

    # 用列表 + append 拼装（避免长字面量列表的括号配对问题）
    parts = []
    parts.append("// ---- 假 DOM：仓库下拉 / 备注 / 供应商 都真实存在；不存在的 id 返回 null ----")
    parts.append("const SELECTED_WAREHOUSE_ID = '5';")
    parts.append("const TYPED_REMARK = '测试备注内容';")
    parts.append("const els = {};")
    parts.append("els['[name=\"warehouse_id\"]'] = { value: SELECTED_WAREHOUSE_ID };")
    parts.append("els['[name=\"remark\"]'] = { value: TYPED_REMARK };")
    parts.append("els['#supplierSearch'] = { value: '供应商甲' };")
    parts.append("const restored = {};")
    parts.append("function mkEl(key) {")
    parts.append("  return {")
    parts.append("    get value() { return els[key].value; },")
    parts.append("    set value(v) { restored[key] = v; }")
    parts.append("  };")
    parts.append("}")
    parts.append("const document = {")
    parts.append("  querySelectorAll: function () { return []; },")
    parts.append("  querySelector: function (sel) {")
    parts.append("    if (els.hasOwnProperty(sel)) return mkEl(sel);")
    parts.append("    return null;")
    parts.append("  }")
    parts.append("};")
    parts.append("")
    parts.append("// ---- ① 执行 collectFormData 的 return 对象字面量（原样抽取）----")
    parts.append("const rows = [];")  # collectFormData 内部变量，抽出的字面量里引用了它
    parts.append("const collected = {" + collect_body + "};")
    parts.append("")
    parts.append("// ---- ② 执行恢复片段（把 collected 当作草稿 data）----")
    parts.append("const data = collected;")
    parts.append(restore_wh)
    parts.append(restore_rm)
    parts.append("")
    parts.append("console.log(JSON.stringify({")
    parts.append("  collected_keys: Object.keys(collected),")
    parts.append("  collected: collected,")
    parts.append("  restored: restored,")
    parts.append("  expected_id: SELECTED_WAREHOUSE_ID,")
    parts.append("  expected_remark: TYPED_REMARK")
    parts.append("}));")
    return _run_js("\n".join(parts))


@pytest.fixture(scope="module")
def res() -> dict:
    return _harness()


class TestDraftWarehouseRoundTrip:
    """BUG-2026-09-27-002：草稿的仓库字段必须真实存下并能恢复。"""

    def test_t1_draft_stores_non_empty_warehouse_id(self, res):
        """T1：草稿对象里 warehouse_id 存在且值非空（旧代码是存在但恒为空）。"""
        c = res["collected"]
        assert "warehouse_id" in c, (
            f"草稿缺少 warehouse_id 字段，实际键：{res['collected_keys']}"
        )
        assert c["warehouse_id"] == res["expected_id"], (
            f"草稿里的 warehouse_id 为空或错值：{c['warehouse_id']!r}——"
            f"说明取值仍走不存在的 '#warehouseSelect'（静默失效）"
        )

    def test_t2_draft_has_no_legacy_warehouse_key(self, res):
        """T2：草稿对象不得存在旧键 warehouse（防复活）。"""
        assert "warehouse" not in res["collected"], (
            f"草稿仍写旧键 warehouse：{res['collected']}"
        )

    def test_t3_draft_stores_non_empty_remark(self, res):
        """T3：草稿对象里 remark 值非空（防 '#remarkInput' 复活）。"""
        assert res["collected"].get("remark") == res["expected_remark"], (
            f"草稿里的 remark 为空或错值：{res['collected'].get('remark')!r}——"
            f"说明取值仍走不存在的 '#remarkInput'（静默失效）"
        )

    def test_t4_restore_fills_warehouse_select(self, res):
        """T4：恢复逻辑能把草稿仓库回填到 [name=\"warehouse_id\"]。"""
        assert res["restored"].get('[name="warehouse_id"]') == res["expected_id"], (
            f"恢复后仓库下拉未被写入，restored={res['restored']}"
        )

    def test_t5_restore_fills_remark(self, res):
        """T5：恢复逻辑能把草稿备注回填到 [name=\"remark\"]。"""
        assert res["restored"].get('[name="remark"]') == res["expected_remark"], (
            f"恢复后备注未被写入，restored={res['restored']}"
        )


class TestNoDanglingIdSelectors:
    """静态兜底：JS 代码不得再引用模板中不存在的 id（注释中的说明文字除外）。"""

    @staticmethod
    def _js_code_lines() -> list[str]:
        """取模板内联 JS 的代码行，剔除 // 注释行与行尾注释。"""
        src = _read_tpl()
        out = []
        for ln in src.split("\n"):
            code = ln.split("//", 1)[0]
            if code.strip():
                out.append(code)
        return out

    def test_no_dangling_warehouse_select_id(self):
        src = _read_tpl()
        assert 'id="warehouseSelect"' not in src, "模板中出现了 id=\"warehouseSelect\" 元素"
        offenders = [c for c in self._js_code_lines() if "#warehouseSelect" in c]
        assert not offenders, (
            f"JS 代码仍引用不存在的选择器 '#warehouseSelect'（应为 [name=\"warehouse_id\"]）：{offenders}"
        )

    def test_no_dangling_remark_input_id(self):
        src = _read_tpl()
        assert 'id="remarkInput"' not in src, "模板中出现了 id=\"remarkInput\" 元素"
        offenders = [c for c in self._js_code_lines() if "#remarkInput" in c]
        assert not offenders, (
            f"JS 代码仍引用不存在的选择器 '#remarkInput'（应为 [name=\"remark\"]）：{offenders}"
        )
