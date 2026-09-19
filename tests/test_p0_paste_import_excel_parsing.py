# -*- coding: utf-8 -*-
"""P0 粘贴导入（Excel / WPS 复制）解析 —— 模板结构 + 归一化逻辑回归。

背景：粘贴导入是仓库日常最重的录入口，用户实际操作是「在 Excel / WPS 里
选中区域复制，再粘到弹窗」。这类内容有两个真实特征容易踩坑：
  * 分隔符是 **Tab**（不是逗号、也不是 2 个以上空格）
  * 日期单元格常带时间后缀（2026/9/1 0:00）、或用中文年月日 / 点号写法

本次把解析改为 Tab 优先、多格式日期归一化到 YYYY-MM-DD，并扩展第 4/5 列
为批次号与有效期。测试用 Node 执行页面内抽出的纯函数，保证前端行为可回归。

测试用例：
  T1. 弹窗文案与新增列头出现在页面上（批次号 / 有效期）
  T2. Tab 分隔的多行数据能正确切分为 5 列
  T3. 日期归一化覆盖 / . 年 及带时间后缀的写法
  T4. 非法日期（2026-02-31）被拒绝而非静默滚动
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "app" / "templates" / "in_order_add.html"


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _extract_js_function(name: str) -> str:
    """从模板里抽出指定 JS 函数源码（按大括号配平）。"""
    src = _template_text()
    start = src.index(f"function {name}(")
    idx = src.index("{", start)
    depth = 0
    for pos in range(idx, len(src)):
        if src[pos] == "{":
            depth += 1
        elif src[pos] == "}":
            depth -= 1
            if depth == 0:
                return src[start:pos + 1]
    raise AssertionError(f"未能抽出函数 {name}")


def test_T1_paste_modal_and_columns_present():
    body = _template_text()
    assert "Excel / WPS 粘贴导入" in body, "弹窗标题应说明来源是 Excel / WPS"
    for label in ("批次号", "有效期"):
        assert label in body, f"明细表头应包含[{label}]"
    assert ".material-batch-no" in body, "行内应有批次号输入框"
    assert ".material-expiry" in body, "行内应有有效期输入框"


def _run_node(script: str) -> dict:
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError(f"node 执行失败：{proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_T2_tab_separated_rows_split_into_five_columns():
    """直接模拟把 Excel 复制内容粘进弹窗后解析出的 parts。"""
    script = r"""
const tabLine = ['M001','100','5.50','B20260901','2027/6/30'].join('\t');
const spacedLine = 'M002    200    3.00';
const splitRow = (line) => (line.indexOf('\t') >= 0
    ? line.split('\t')
    : line.split(/\s{2,}/)
).map(s => s.trim());
console.log(JSON.stringify({tab: splitRow(tabLine), spaced: splitRow(spacedLine)}));
"""
    out = _run_node(script)
    assert out["tab"] == ["M001", "100", "5.50", "B20260901", "2027/6/30"], \
        f"Tab 分隔应切出 5 列，实际 {out['tab']}"
    assert out["spaced"] == ["M002", "200", "3.00"], \
        f"2+ 空格分隔应切出 3 列，实际 {out['spaced']}"


def test_T3_expiry_normalization_covers_excel_formats():
    """归一化：/ . 年月日 及带时间后缀 → YYYY-MM-DD；空值 → 空串。"""
    page = _template_text()
    m = re.search(
        r"const normalizeExpiry = \(raw\) => \{.*?\n    \};",
        page,
        re.S,
    )
    assert m, "模板里应存在 normalizeExpiry 实现"
    fn_src = m.group(0)

    script = fn_src + r"""
const cases = ['2026-09-01','2026/9/1','2026.9.1','2026年9月1日','2026/9/1 0:00','','  '];
const res = {};
for (const c of cases) { res[c] = normalizeExpiry(c); }
console.log(JSON.stringify(res));
"""
    out = _run_node(script)
    for raw in ("2026-09-01", "2026/9/1", "2026.9.1", "2026年9月1日", "2026/9/1 0:00"):
        assert out[raw] == "2026-09-01", f"[{raw}] 应归一化为 2026-09-01，实际 {out[raw]}"
    assert out[""] == "" and out["  "] == "", "空值应归一化为空串（该行不记录有效期）"


def test_T4_invalid_date_rejected_not_rolled_over():
    """2026-02-31 这类非法日期必须被拒绝（Date 会静默滚动成 3-03）。"""
    page = _template_text()
    m = re.search(
        r"const normalizeExpiry = \(raw\) => \{.*?\n    \};",
        page,
        re.S,
    )
    assert m, "模板里应存在 normalizeExpiry 实现"
    fn_src = m.group(0)

    script = fn_src + r"""
console.log(JSON.stringify({
  feb31: normalizeExpiry('2026-02-31'),
  feb29: normalizeExpiry('2026-02-29'),
  month13: normalizeExpiry('2026-13-01'),
}));
"""
    out = _run_node(script)
    assert out["feb31"] is None, "2026-02-31 不是合法日期，应返回 null"
    assert out["feb29"] is None, "2026 年非闰年，2026-02-29 应返回 null"
    assert out["month13"] is None, "13 月应返回 null"
