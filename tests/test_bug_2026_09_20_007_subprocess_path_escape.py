# -*- coding: utf-8 -*-
"""BUG-2026-09-20-007 回归锁：测试里经 `python -c` 起子进程时，路径不得拼进源码。

背景
----
`tests/test_opening_stock_migration.py::_run_migration` 原本这样写：

    os.environ['DATABASE_URL'] = 'sqlite:///{db_file}'   # ← 直接拼进 -c 源码

在 Windows 上 `db_file` 形如 `C:\\Users\\...\\legacy.db`，其中的 `\\U` 会被
Python 源码解析器当成 **unicode 转义**，子进程直接挂掉：

    SyntaxError: (unicode error) 'unicodeescape' codec can't decode bytes
    in position 12-13: truncated \\UXXXXXXXX escape

后果是 BUG-2026-09-15-007（期初库存分单）的**迁移回归锁 10/11 项恒失败**，
且失败信息是"迁移进程未正常完成"，与真实迁移缺陷无法区分 —— 回归锁失效。

契约（本文件锁定）
------------------
1. `_run_migration` 生成的子进程源码里**不得**出现 `DATABASE_URL` 的字面赋值
   （应改为经环境变量传递，源码只读不拼）；
2. 源码里**不得**出现未加 `!r` 的 f-string 路径插值（`'.../{db_file}'` 形态）；
3. `subprocess.run` 必须显式传 `env=`（否则环境变量传递形同虚设）；
4. 机制证明：同样的路径若直接拼进源码，Python 确实会抛 SyntaxError ——
   证明上述约束不是洁癖，而是真实故障路径。

注意：本文件只做**静态 + 机制**校验，不跑真实迁移（真实迁移由
`test_opening_stock_migration.py` 覆盖，已 11 passed）。
"""
from __future__ import annotations

import inspect
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "tests" / "test_opening_stock_migration.py"


def _source() -> str:
    return TARGET.read_text(encoding="utf-8")


def _run_migration_source() -> str:
    """取出 _run_migration 函数源码。"""
    src = _source()
    i = src.find("def _run_migration(")
    assert i >= 0, "未找到 _run_migration 定义"
    # 取到下一个顶层 def/class 之前
    rest = src[i:]
    m = re.search(r"\n(?:def |class |@)", rest[1:])
    return rest[: m.start() + 1] if m else rest


def test_t1_no_literal_database_url_assignment():
    """子进程源码里不得把 DATABASE_URL 写成字面赋值（路径会被 unicode 转义吞掉）。"""
    fn = _run_migration_source()
    assert "os.environ['DATABASE_URL'] =" not in fn, (
        "不得在 -c 源码里字面赋值 DATABASE_URL：Windows 路径的 \\U 会被解析成 "
        "unicode 转义（BUG-2026-09-20-007）。应改为经 env= 传入。"
    )


def test_t2_no_unrepr_path_interpolation():
    """源码里不得出现 '.../{db_file}' 这类未加 !r 的路径插值。"""
    fn = _run_migration_source()
    bad = re.findall(r"['\"]sqlite:///[^\"']*\{db_file\}['\"]", fn)
    assert not bad, f"存在未转义的路径插值（缺 !r）：{bad}"


def test_t3_subprocess_passes_env():
    """subprocess.run 必须显式传 env=，否则环境变量传递不生效。"""
    fn = _run_migration_source()
    assert "env=env" in fn or "env=" in fn, (
        "subprocess.run 未传 env=，DATABASE_URL 无法送达子进程"
    )


def test_t4_mechanism_windows_path_breaks_source():
    """机制证明：把本机路径直接拼进源码，Python 确实抛 SyntaxError。

    这是本 BUG 成立的实证——不是编码风格问题。只在 Windows 路径（含反斜杠）
    下复现；非 Windows 时跳过（正斜杠路径不会触发 unicode 转义）。
    """
    probe = Path(sys.executable).parent  # 形如 C:\...\Scripts
    win_path = str(probe).replace("/", "\\")
    if "\\" not in win_path:
        pytest.skip("非 Windows 路径，不触发 unicodeescape")

    script = f"x = '{win_path}'\nprint('OK')"
    r = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=60
    )
    # 路径里若含 \U / \u 等转义序列前缀则必炸；否则至少也要证明机制可探测
    if r.returncode != 0:
        assert "unicodeescape" in r.stderr or "SyntaxError" in r.stderr, (
            f"失败原因与预期不符：{r.stderr[:300]}"
        )
    else:
        # 路径不含转义前缀（如 C:\Python\...），用构造样本直接证明机制
        r2 = subprocess.run(
            [sys.executable, "-c", "x = 'C:\\Users\\x'\nprint('OK')"],
            capture_output=True, text=True, timeout=60,
        )
        assert r2.returncode != 0, "预期构造样本触发 SyntaxError，但通过了"
        assert "unicodeescape" in r2.stderr, r2.stderr[:300]


def test_t5_migration_test_file_importable():
    """被修文件本身语法正确、可导入（防止改坏）。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_osm_probe", TARGET)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # 不会真的跑迁移，只导入
    assert callable(mod._run_migration)
    assert "os" in dir(mod), "需 import os 以便读环境变量"
