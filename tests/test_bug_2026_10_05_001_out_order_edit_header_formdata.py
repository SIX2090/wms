# -*- coding: utf-8 -*-
"""BUG-2026-10-05-001 回归锁：出库单「编辑单据」保存恒失败（FormData 迭代器误用）。

症状
----
领料单（及其他出库单）反提交后，在「编辑单据」弹窗修改仓库/日期等任意字段，
点「保存」恒弹「请选择出库日期」，弹窗不关闭，**不发任何 POST 请求**。
用户误以为是日期问题，实际是**编辑单据保存功能整体不可用**。

根因
----
`out_order_detail.html` 的 `saveHeader()` 用

    Array.prototype.forEach.call(new FormData(form).entries(), function (entry) { ... })

遍历表单。`FormData.prototype.entries()` 返回的是 **Iterator**，不是 Array，
也不是 Array-like（**没有 `length` 属性**）。
`Array.prototype.forEach` 对非数组对象按 `length` 索引遍历 —— `length` 为
`undefined`（`length >>> 0 === 0`），于是**循环 0 次**，`data` 恒为 `{}`，
`data.date` 恒 `undefined`，必然命中 `if (!data.date)` 分支。

**解析陷阱**：该 bug 只在浏览器里 click 触发时暴露；用
`Array.from(...)` / `for...of` / `Object.fromEntries(...)`（迭代器协议）
做验证会永远"通过"，因为那些 API 都支持迭代器。这正是它躲过此前测试的原因。

为什么出库单中招而入库单没有
--------------------------
`in_order_detail.html` 的 `saveHeader()` 从一开始就写的是
`Object.fromEntries(formData.entries())`（正确），两个页面是同功能复制而来，
出库单那份被改成了错误写法。

本测试锁什么
------------
pytest 没有 JS 引擎，锁的是**写法契约**而非运行时：
  1. `saveHeader()` 内**不得**出现对 `FormData.entries()` 结果的
     `Array.prototype.*.call()` 直接调用（必须显式物化）。
  2. `saveHeader()` 必须使用可迭代协议安全的方式取值
     （`Object.fromEntries` / `Array.from` / `for...of` / `fd.forEach`）。
  3. 全仓扫一遍：任何 `Array.prototype.forEach.call(<...>.entries(), ...)`
     形态都必须报警（R6 同根因防复发）。
  4. 台账必须有 BUG-2026-10-05-001 条目（A13 生效确认字段存在）。
"""

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TPL_DIR = os.path.join(ROOT, "app", "templates")
BASELINE = os.path.join(ROOT, "WMS_BUG_BASELINE.md")

OUT_DETAIL = os.path.join(TPL_DIR, "out_order_detail.html")
IN_DETAIL = os.path.join(TPL_DIR, "in_order_detail.html")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_save_header(src, path_label):
    """截出 saveHeader() 的函数体（大括号配平）。"""
    m = re.search(r"function\s+saveHeader\s*\(\s*\)\s*\{", src)
    assert m, f"{path_label} 找不到 saveHeader() 函数"
    i = m.end()
    depth = 1
    start = i
    while i < len(src) and depth:
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        i += 1
    assert depth == 0, f"{path_label} saveHeader() 大括号不配平"
    return src[start:i]


# ===================== 1. 出库单：不得再有 iterator + Array.prototype.call =====================

# 伪代码特征：Array.prototype.<meth>.call( <某个 .entries()> ...
# 注意：中间参数可能含括号（如 new FormData(form).entries()），
# 所以必须用非贪婪 .*? 而不是 [^)]* —— 后者会在 FormData(form) 的 ')' 处提前截断，
# 导致原 BUG 代码漏检（A14 反向验证曾因此失败）。
_BAD_ITER_CALL = re.compile(
    r"Array\.prototype\.\w+\.call\s*\(\s*.*?\.entries\s*\(", re.S
)


def test_out_order_save_header_has_no_iterator_misuse():
    """out_order_detail.html 的 saveHeader 不得对 .entries() 迭代器用 Array.prototype.call。"""
    body = _extract_save_header(_read(OUT_DETAIL), "out_order_detail.html")
    bad = _BAD_ITER_CALL.search(body)
    assert bad is None, (
        "out_order_detail.html saveHeader() 仍在对 FormData.entries() 迭代器调用 "
        f"Array.prototype.*.call —— 会 0 次循环导致保存恒失败：\n{bad.group(0) if bad else ''}"
    )


# ===================== 2. 出库单：必须用可迭代安全的取值方式 =====================

_SAFE_PATTERNS = (
    "Object.fromEntries(",   # 首选（与 in_order_detail 一致）
    "Array.from(",           # 显式物化
    "fd.forEach(",           # FormData 自带 forEach
    "for (const [",          # for...of 解构
    "for (let [",
)
# for...of 的宽松匹配（变量名任取）
_FOR_OF = re.compile(r"for\s*\(\s*(?:const|let|var)\s*\[")


def test_out_order_save_header_uses_iterable_safe_collection():
    """out_order_detail.html 的 saveHeader 必须用迭代器安全方式收集表单数据。"""
    body = _extract_save_header(_read(OUT_DETAIL), "out_order_detail.html")
    ok = any(p in body for p in _SAFE_PATTERNS) or _FOR_OF.search(body)
    assert ok, (
        "out_order_detail.html saveHeader() 未使用迭代器安全方式"
        f"（应含 {' / '.join(_SAFE_PATTERNS)} 或 for...of 解构）：\n{body[:600]}"
    )


def test_out_order_save_header_uses_object_from_entries():
    """与入库单保持同一写法，避免再次分叉。"""
    body = _extract_save_header(_read(OUT_DETAIL), "out_order_detail.html")
    assert "Object.fromEntries(new FormData(form).entries())" in body or \
           "Object.fromEntries(formData.entries())" in body, (
        "out_order_detail.html saveHeader() 建议与 in_order_detail.html 统一为 "
        "Object.fromEntries(...entries())，防止同功能两份实现再次分叉"
    )


# ===================== 3. 入库单对照组：仍必须是正确写法 =====================

def test_in_order_save_header_still_correct():
    """入库单是照妖镜：它一直是对的，不能被"顺手改坏"。"""
    body = _extract_save_header(_read(IN_DETAIL), "in_order_detail.html")
    assert _BAD_ITER_CALL.search(body) is None, (
        "in_order_detail.html saveHeader() 被改出了 iterator 误用（回归）"
    )
    assert "Object.fromEntries(" in body, (
        "in_order_detail.html saveHeader() 应保持 Object.fromEntries 写法"
    )


# ===================== 4. R6 全仓同根因扫描 =====================

def test_no_iterator_misuse_anywhere_in_templates():
    """全仓模板：任何 '<xxx>.entries()' 直接喂给 Array.prototype.*.call 都要报警。"""
    offenders = []
    for name in sorted(os.listdir(TPL_DIR)):
        if not name.endswith((".html", ".htm")):
            continue
        src = _read(os.path.join(TPL_DIR, name))
        for m in _BAD_ITER_CALL.finditer(src):
            line = src[: m.start()].count("\n") + 1
            offenders.append(f"{name}:{line}: {m.group(0)[:80]}")
    assert not offenders, (
        "检测到 FormData/Map 等迭代器被 Array.prototype.*.call 直接遍历"
        f"（会 0 次循环）：\n  " + "\n  ".join(offenders)
    )


def test_no_iterator_misuse_in_static_js():
    """静态 JS 目录同样扫描。"""
    js_dir = os.path.join(ROOT, "app", "static", "js")
    offenders = []
    if os.path.isdir(js_dir):
        for name in sorted(os.listdir(js_dir)):
            if not name.endswith(".js"):
                continue
            src = _read(os.path.join(js_dir, name))
            for m in _BAD_ITER_CALL.finditer(src):
                line = src[: m.start()].count("\n") + 1
                offenders.append(f"{name}:{line}: {m.group(0)[:80]}")
    assert not offenders, (
        "app/static/js 下检测到迭代器被 Array.prototype.*.call 直接遍历：\n  "
        + "\n  ".join(offenders)
    )


# ===================== 5. 台账登记（A13：生效确认字段必须存在） =====================

BUG_ID = "BUG-2026-10-05-001"


def test_baseline_registered_with_effective_confirmation():
    assert os.path.isfile(BASELINE), "WMS_BUG_BASELINE.md 不存在"
    src = _read(BASELINE)
    assert BUG_ID in src, f"台账缺少 {BUG_ID} 条目"
    idx = src.find(BUG_ID)
    entry = src[idx: idx + 3000]
    assert "根因" in entry, f"{BUG_ID} 条目缺少「根因」字段"
    assert "修复" in entry, f"{BUG_ID} 条目缺少「修复」字段"
    assert "R6" in entry, f"{BUG_ID} 条目缺少「R6 同类点排查」字段"
    assert "回归锁" in entry, f"{BUG_ID} 条目缺少「回归锁」字段"
    assert "生效确认" in entry, f"{BUG_ID} 条目缺少 A13「生效确认」字段"
    assert "out_order_detail.html" in entry, f"{BUG_ID} 条目应点名文件"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
