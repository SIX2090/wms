# -*- coding: utf-8 -*-
"""离线验证器：P0 闸门 G-01（已完成入库单改数留痕）的代码形态断言。

为什么不用 pytest：本机普通 shell 跑 pytest 会被
``tests/conftest.py`` → ``scripts/verify_db_guard.require_isolated_test_runtime()``
在导入 app 之前终止（预期安全行为，不得绕过）。真实行为断言由
``tests/test_p0_g01_update_completed_audit.py`` 交 CI 执行；本脚本只做
**不导入 app、不碰数据库**的静态检查，用于施工当下与 R8 变异验证。

检查项（每条都对应一个具体的错法）：

  C1 路由函数存在且区间可定位（防止改名后断言静默失效）
  C2 ``log_audit`` / ``log_operation`` 在该函数的 from app import 列表里
  C3 函数体内出现 ``log_audit('update_completed_in_order', 'in_order', ...)``
  C4 log_audit 位置在**主 commit 之后**（前移会把半成品业务写提前落库）
  C5 old 快照 ``before_items`` 出现在删除循环之前（事后取只能拿到新值）
  C6 审计块被 try/except 包住，且异常分支只记日志不 return 失败
     （业务已提交，回传失败会造成"说没存、实际已改"）
  C7 reason 有 200 长度截断（String(200)，换库会 DataError 被吞 → 静默丢审计）
  C8 函数体内仍有 ``db.session.commit()``（防止断言区间错位后误判通过）

退出码：0 全过；1 有失败项。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "app" / "routes" / "in_order.py"
AUDIT_OP = "update_completed_in_order"


def _failure(msg):
    print(f"  FAIL {msg}")
    return 1


def main():
    if not TARGET.exists():
        print(f"目标文件不存在: {TARGET}")
        return 1
    src = TARGET.read_text(encoding="utf-8")

    failures = 0

    # C1 定位函数体（到下一个顶层 def 结束）
    marker = "def update_completed_in_order(id):"
    if marker not in src:
        print(f"  FAIL C1 找不到 {marker}")
        return 1
    start = src.index(marker)
    nxt = src.find("\n    @app.route(", start + len(marker))
    raw_body = src[start:nxt if nxt > 0 else len(src)]
    # 去掉纯注释行：本函数注释里会引用 `db.session.commit()` 等符号（说明"为什么
    # 不能放前面"），不过滤会让 C8 把注释当成真实调用、位置断言随之失真。
    body = "\n".join(
        line for line in raw_body.splitlines()
        if not line.strip().startswith("#")
    )
    print(f"C1 函数体定位：{len(body)} 字符（已剔除注释行）")

    # C2 导入
    if not re.search(r"log_audit,\s*log_operation|log_operation,\s*log_audit", body):
        failures += _failure("C2 函数内未从 app 导入 log_audit / log_operation")
    else:
        print("C2 审计函数已导入")

    # C3 审计调用（要求 op 字符串紧跟在调用上，避免注释/参数表残留造成假通过）
    audit_call = re.search(
        r"log_audit\(\s*\n?\s*'%s',\s*'in_order'" % AUDIT_OP, body)
    if not audit_call:
        failures += _failure(f"C3 未调用 log_audit('{AUDIT_OP}', 'in_order', ...)")
    else:
        print("C3 审计调用存在")

    # C8 先确认区间内有 commit，否则下面的位置比较没有意义
    commits = [m.start() for m in re.finditer(r"db\.session\.commit\(\)", body)]
    if not commits:
        failures += _failure("C8 区间内找不到 db.session.commit()，断言区间可能错位")
        print("\n结果：失败")
        return 1
    print(f"C8 区间内 commit 数：{len(commits)}")

    # C4 顺序
    audit_pos = audit_call.start() if audit_call else -1
    if audit_pos < 0 or audit_pos < commits[0]:
        failures += _failure("C4 log_audit 位于首个 commit 之前（会提前落库/谎报成功）")
    else:
        print("C4 log_audit 在 commit 之后")

    # C5 快照位置
    snap_pos = body.find("before_items")
    delete_pos = body.find("for item_id in deleted_items:")
    if snap_pos < 0:
        failures += _failure("C5 找不到 before_items 快照")
    elif delete_pos < 0:
        failures += _failure("C5 找不到删除明细循环（区间可能错位）")
    elif snap_pos > delete_pos:
        failures += _failure("C5 before_items 快照在删除循环之后（old 值已被改写）")
    else:
        print("C5 old 快照在写入之前")

    # C6 审计块容错
    tail = body[commits[0]:]
    if "except Exception as e:" not in tail:
        failures += _failure("C6 审计块缺少 except 兜底")
    elif "审计写入失败" not in tail:
        failures += _failure("C6 审计失败分支未按“只记日志”处理")
    elif re.search(r"except Exception as e:\s*\n\s*[^\n]*\n\s*[^\n]*return ", tail):
        failures += _failure("C6 审计块异常分支出现 return（会把已提交的业务报成失败）")
    else:
        print("C6 审计失败不回传为保存失败")

    # C7 截断
    if "[:200]" not in body:
        failures += _failure("C7 reason 未做 200 长度截断")
    else:
        print("C7 reason 已截断到 200")

    print("\n结果：" + ("通过" if failures == 0 else f"失败 {failures} 项"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
