"""BUG-2026-08-03-001：表头向下填充按钮（WmsFillDown.fillDown）跳过空行

回归测试：
昨天 BUG-2026-08-02-021 修复了 Ctrl+D（setupColumnFillDown）跳过空行，
但表头列上的向下填充按钮（WmsFillDown.fillDown，app.js）是另一套独立机制，
仍然把合同编号/工程名称填到所有 15 行（含空行）。

本测试做静态 JS 内容断言（项目无 JSDOM/Selenium），防止代码回退：
- T1: fillDown 函数检查 material_code 列
- T2: fillDown 统计 skipped 空行计数
- T3: fillDown 提示文案含"跳过 ... 个空行"
- T4: 跳过逻辑仅在 material_code 列存在时生效（不影响其他表格）
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_JS = ROOT / "app" / "static" / "js" / "app.js"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_fill_down(js: str) -> str:
    """提取 fillDown 函数体（从 function fillDown 到下一个 function）。"""
    start = js.index("function fillDown(")
    # 找到下一个顶层 function 定义作为结束
    end = js.index("\n    function ", start + 1)
    return js[start:end]


def test_T1_fillDown_checks_material_code():
    """修复：fillDown 遍历时检查 material_code 列是否为空。"""
    js = _read(APP_JS)
    block = _extract_fill_down(js)
    assert "material_code" in block, "fillDown 未检查 material_code 列"
    assert "cellFor(row, 'material_code')" in block, \
        "fillDown 未用 cellFor(row, 'material_code') 定位物料编码单元格"


def test_T2_fillDown_counts_skipped():
    """修复：fillDown 统计跳过的空行数。"""
    js = _read(APP_JS)
    block = _extract_fill_down(js)
    assert "skipped" in block, "fillDown 未统计 skipped 空行计数"
    assert "skipped += 1" in block or "skipped++" in block, \
        "fillDown 未递增 skipped"


def test_T3_fillDown_skip_message():
    """修复：fillDown 提示文案包含跳过空行说明。"""
    js = _read(APP_JS)
    block = _extract_fill_down(js)
    assert "跳过" in block, "fillDown 提示文案未含'跳过'"
    assert "空行" in block, "fillDown 提示文案未含'空行'"


def test_T4_fillDown_guard_only_when_material_column_exists():
    """修复：跳过逻辑仅在 material_code 列存在时生效（有 materialCell 守卫）。"""
    js = _read(APP_JS)
    block = _extract_fill_down(js)
    # 必须先判断 materialCell 存在，再判断值为空
    assert "var materialCell = cellFor(row, 'material_code')" in block, \
        "fillDown 未先获取 materialCell"
    assert "if (materialCell)" in block, \
        "fillDown 未用 if (materialCell) 守卫——无 material_code 列的表格不应跳过"
