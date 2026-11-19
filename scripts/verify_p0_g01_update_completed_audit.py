# -*- coding: utf-8 -*-
"""离线验证器：P0 闸门 G-01（已完成入库单改数留痕）的代码形态断言。

为什么不用 pytest：本机普通 shell 跑 pytest 会被
``tests/conftest.py`` → ``scripts/verify_db_guard.require_isolated_test_runtime()``
在导入 app 之前终止（预期安全行为，不得绕过）。真实行为断言由
``tests/test_p0_g01_update_completed_audit.py`` 交 CI 执行；本脚本只做
**不导入 app、不碰数据库**的静态检查，用于施工当下与 R8 变异验证。

检查项（每条都对应一个具体的错法）：

  C1 路由函数存在且区间可定位（防止改名后断言静默失效）
  C2 使用随业务事务登记的审计写法，同时保留操作日志
  C3 审计操作名和目标单据正确
  C4 成功路径只能提交一次，关键审计先于提交，普通日志随后写入
  C5 old 快照必须早于删除循环
  C6 审计登记函数只加入会话；提交异常回滚并返回错误
  C7 数量增删改必须提供原因，落库前截断至 200 字
  C8 函数体内仍有 ``db.session.commit()``（防止断言区间错位后误判通过）

退出码：0 全过；1 有失败项。
"""
from __future__ import annotations

import ast
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

    if "from services.document_stock_audit import stage_order_audit" not in body or "log_operation" not in body:
        failures += _failure("C2 缺少事务审计或操作日志")
    audit_call = re.search(r"stage_order_audit\(\s*'%s',\s*order," % AUDIT_OP, body)
    if not audit_call:
        failures += _failure("C3 未对目标单据登记改数审计")

    # C8 先确认区间内有 commit，否则下面的位置比较没有意义
    commits = [m.start() for m in re.finditer(r"db\.session\.commit\(\)", body)]
    if not commits:
        failures += _failure("C8 区间内找不到 db.session.commit()，断言区间可能错位")
        print("\n结果：失败")
        return 1
    print(f"C8 区间内 commit 数：{len(commits)}")

    audit_pos = audit_call.start() if audit_call else -1
    if len(commits) != 1 or not (0 <= audit_pos < commits[0] < body.find("log_operation(")):
        failures += _failure("C4 关键审计、唯一业务提交和普通日志顺序不正确")

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

    source = (ROOT / 'app/services/document_stock_audit.py').read_text(encoding='utf-8')
    stage = next(node for node in ast.parse(source).body
                 if isinstance(node, ast.FunctionDef) and node.name == 'stage_order_audit')
    calls = {ast.unparse(node.func) for node in ast.walk(stage) if isinstance(node, ast.Call)}
    if ('db.session.add' not in calls or 'db.session.commit' in calls or
            any(isinstance(node, ast.Try) for node in ast.walk(stage))):
        failures += _failure("C6 审计登记须加入外层会话，写入异常须向外传播")
    tail = body[commits[0]:]
    if not re.search(r"except Exception:\s+db.session.rollback\(\).*?return .*?, 500", tail, re.S):
        failures += _failure("C6 提交失败必须回滚并返回错误")
    if "[:200]" not in body or "if quantity_changed and not audit_reason:" not in body:
        failures += _failure("C7 数量变更缺少原因门禁或长度上限")

    print("\n结果：" + ("通过" if failures == 0 else f"失败 {failures} 项"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
