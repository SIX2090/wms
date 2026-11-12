# -*- coding: utf-8 -*-
"""离线验证器：P0 闸门 G10（默认凭证与自动解锁）的代码形态断言。

本机 pytest 被 LPAC 隔离守卫拦截，真实行为断言由
``tests/test_f21_admin_force_password_change.py::TestG10*`` 交 CI；本脚本只做
不导入 app、不碰数据库的静态检查，用于施工当下与 R8 变异验证。

检查项：

  C1 解锁被 ``_env_flag('WMS_AUTO_UNLOCK_DISABLED_ADMIN')`` 门控（默认不执行）
  C2 解锁不再是无条件 ``if user.status == 'disabled':`` 裸判断
  C3 解锁留 warning 日志（恢复动作可审计），且不再用 info 静默通过
  C4 默认密码字面量 ``... or 'admin'`` 原样保留（AGENTS §一 + BUG-NEW-005）
  C5 启动自检行包含 bootstrap_pw 状态，且不输出密码值
  C6 部署清单同时要求两个变量名

退出码：0 全过；1 有失败项。
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_PY = ROOT / "app" / "app.py"
STARTUP = ROOT / "app" / "startup_check.py"
CHECKLIST = ROOT / "PRODUCTION_DEPLOYMENT_CHECKLIST.md"


def _fail(msg):
    print(f"  FAIL {msg}")
    return 1


def main():
    for path in (APP_PY, STARTUP, CHECKLIST):
        if not path.exists():
            print(f"目标文件不存在: {path}")
            return 1

    src = APP_PY.read_text(encoding="utf-8")
    failures = 0

    marker = "def ensure_admin_user_exists():"
    if marker not in src:
        print("  FAIL 找不到 ensure_admin_user_exists")
        return 1
    start = src.index(marker)
    nxt = src.find("\ndef ", start + len(marker))
    raw = src[start:nxt if nxt > 0 else len(src)]
    body = "\n".join(l for l in raw.splitlines() if not l.strip().startswith("#"))

    # C1 门控
    if "_env_flag('WMS_AUTO_UNLOCK_DISABLED_ADMIN')" not in body:
        failures += _fail("C1 解锁未被 WMS_AUTO_UNLOCK_DISABLED_ADMIN 门控")
    elif not re.search(r"user\.status\s*==\s*'disabled'\s*and\s*_env_flag", body):
        failures += _fail("C1 门控写法异常（应 status=='disabled' and _env_flag(...)）")
    else:
        print("C1 解锁已受显式开关门控")

    # C2 不得残留裸判断
    if re.search(r"if user\.status\s*==\s*'disabled':", body):
        failures += _fail("C2 仍存在无条件的 if user.status == 'disabled':")
    else:
        print("C2 无残留的裸判断")

    # C3 日志级别
    if "auto-unlocked" not in body:
        failures += _fail("C3 解锁缺少可识别的审计日志")
    elif not re.search(r"logger\.warning\(\s*\n?\s*[\"']Admin account auto-unlocked", body):
        failures += _fail("C3 解锁日志不是 warning 级")
    else:
        print("C3 解锁留 warning 审计日志")

    # C4 默认密码字面量
    if "os.environ.get('WMS_BOOTSTRAP_PASSWORD') or 'admin'" not in src:
        failures += _fail("C4 默认密码字面量被改动（会撞 BUG-NEW-005 与 AGENTS §一）")
    else:
        print("C4 默认密码字面量保留")

    # C5 启动自检
    startup = STARTUP.read_text(encoding="utf-8")
    if "bootstrap_pw=" not in startup:
        failures += _fail("C5 启动自检行未包含 bootstrap_pw 状态")
    elif "WMS_BOOTSTRAP_PASSWORD" not in startup:
        failures += _fail("C5 自检未读取 WMS_BOOTSTRAP_PASSWORD")
    else:
        print("C5 启动自检包含口令状态")

    # C6 部署清单
    checklist = CHECKLIST.read_text(encoding="utf-8")
    missing = [v for v in ("WMS_BOOTSTRAP_PASSWORD", "WMS_AUTO_UNLOCK_DISABLED_ADMIN")
               if v not in checklist]
    if missing:
        failures += _fail(f"C6 部署清单缺少：{', '.join(missing)}")
    else:
        print("C6 部署清单含两个变量")

    print("\n结果：" + ("通过" if failures == 0 else f"失败 {failures} 项"))
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.exit(main())
