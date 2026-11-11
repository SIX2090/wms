# -*- coding: utf-8 -*-
"""离线验证器：P0 闸门 G-16（期初一键全删加保护）的代码形态断言。

本机 pytest 被 LPAC 隔离守卫拦截（预期行为，不得绕过），真实行为断言由
``tests/test_opening_stock_delete_all.py::TestPurgeGuard`` 交 CI；本脚本只做
不导入 app、不碰数据库的静态检查，用于施工当下与 R8 变异验证。

检查项：

  C1 ``OPENING_STOCK_PURGE_PHRASE`` 常量存在且取值正确
  C2 路由内做 confirm_phrase 比对，且失败分支返回 400（不是"警告后继续"）
  C3 短语校验发生在**任何删除/回冲之前**（顺序错=校验形同虚设）
  C4 ``log_audit('purge_opening_stock', ...)`` 在 commit 之后
  C5 单据快照在 commit 之前（commit 后 ORM 对象过期，取不到被删对象）
  C6 前端内置短语、提交 confirm_phrase、按钮可置灰

退出码：0 全过；1 有失败项。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "app" / "routes" / "opening_stock.py"
FRONTEND = ROOT / "app" / "templates" / "opening_stock_list.html"
PHRASE = "清空全部期初库存"
OP = "purge_opening_stock"


def _fail(msg):
    print(f"  FAIL {msg}")
    return 1


def main():
    for path in (BACKEND, FRONTEND):
        if not path.exists():
            print(f"目标文件不存在: {path}")
            return 1

    src = BACKEND.read_text(encoding="utf-8")
    failures = 0

    # C1 常量
    m = re.search(r"OPENING_STOCK_PURGE_PHRASE\s*=\s*'([^']+)'", src)
    if not m:
        failures += _fail("C1 缺少 OPENING_STOCK_PURGE_PHRASE 常量")
        phrase = None
    else:
        phrase = m.group(1)
        if phrase != PHRASE:
            failures += _fail(f"C1 短语取值异常：{phrase!r}")
        else:
            print(f"C1 常量正确：{phrase}")

    # 定位路由函数体
    marker = "def delete_all_opening_stock():"
    if marker not in src:
        print("  FAIL 找不到 delete_all_opening_stock")
        return 1
    start = src.index(marker)
    nxt = src.find("\n    @app.route(", start + len(marker))
    raw = src[start:nxt if nxt > 0 else len(src)]
    body = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("#"))

    # C2 短语校验（含 400 返回）
    if "confirm_phrase" not in body:
        failures += _fail("C2 路由未校验 confirm_phrase")
    elif not re.search(r"confirm_phrase[^\n]*!=?\s*OPENING_STOCK_PURGE_PHRASE"
                       r"|OPENING_STOCK_PURGE_PHRASE\s*\n?[^)]*!=\s*\(payload\.confirm_phrase", body):
        failures += _fail("C2 confirm_phrase 未与常量比对")
    elif "确认短语" not in body:
        failures += _fail("C2 拒绝时未给出「确认短语」提示")
    else:
        print("C2 短语校验与 400 提示就位")

    # C3 校验早于任何删除/回冲。
    # 定位依据必须是**比对语句本身**而不是裸 "confirm_phrase"——后者在 pydantic
    # 模型定义里也出现，删掉校验行后仍能匹配到，会让本条断言恒真（实测踩过）。
    check_pos = body.find("!= OPENING_STOCK_PURGE_PHRASE")
    risky = [p for p in (
        body.find("_reverse_opening_stock_line(line"),
        body.find("db.session.delete(line)"),
        body.find("db.session.delete(doc)"),
    ) if p >= 0]
    if check_pos < 0:
        failures += _fail("C3 找不到短语比对语句（校验缺失或写法变更）")
    elif not risky:
        failures += _fail("C3 找不到回冲/删除调用，断言区间可能错位")
    elif check_pos > min(risky):
        failures += _fail("C3 短语校验发生在回冲/删除之后（拦截无效）")
    else:
        print("C3 校验在任何写入之前")

    # C4/C5 顺序
    commits = [m.start() for m in re.finditer(r"db\.session\.commit\(\)", body)]
    if not commits:
        failures += _fail("C4 区间内找不到 db.session.commit()")
        print("\n结果：失败")
        return 1
    audit_pos = body.find(f"'{OP}'")
    if audit_pos < 0:
        failures += _fail(f"C4 未调用 log_audit('{OP}', ...)")
    elif audit_pos < commits[0]:
        failures += _fail("C4 审计写在 commit 之前（业务回滚时会谎报成功）")
    else:
        print("C4 审计在 commit 之后")

    snap_pos = body.find("audit_docs")
    if snap_pos < 0:
        failures += _fail("C5 找不到 audit_docs 快照")
    elif snap_pos > commits[0]:
        failures += _fail("C5 快照在 commit 之后（被删对象属性已过期）")
    else:
        print("C5 单据快照在 commit 之前")

    # C6 前端
    html = FRONTEND.read_text(encoding="utf-8")
    if PHRASE not in html:
        failures += _fail("C6 前端未内置确认短语")
    elif "confirm_phrase" not in html:
        failures += _fail("C6 前端未提交 confirm_phrase")
    elif "btnPurgeOpeningStock" not in html:
        failures += _fail("C6 按钮缺少可置灰 id（防连点）")
    else:
        print("C6 前端接线完整")

    print("\n结果：" + ("通过" if failures == 0 else f"失败 {failures} 项"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
