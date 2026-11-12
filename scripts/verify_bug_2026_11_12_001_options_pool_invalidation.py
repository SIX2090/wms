#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-11-12-001 离线静态验证器（不 import app，纯文本/AST 断言）。

验证「新建物料下拉不显示」修复的关键接线是否存在且位置正确：
  C1  options_api._get_pool 缓存命中路径包含表指纹探测（_entity_pool_signature）
  C2  _entity_pool_signature 的物料分支含 status 可入池行数（能感知停启用）
  C3  invalidate_options_pool 存在且被 material.py 编辑路由调用（在 commit 之后）
  C4  _py_keys 已记忆化（lru_cache）——签名触发重建时拼音零重算
  C5  探测异常 fail-open（返回 None 沿用缓存，不 500）
  C6  缓存条目为 (时间, 池, 签名) 三元组，签名随池一起写入
  C7  版本号已递增到本批序号
  C8  回归测试文件存在且含 6 条用例

本脚本遵守仓库安全守卫：不运行 pytest、不 import app、不连接任何数据库。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPT = ROOT / "app" / "routes" / "options_api.py"
MAT = ROOT / "app" / "routes" / "material.py"
VER = ROOT / "app" / "version.py"
TST = ROOT / "tests" / "test_bug_2026_11_12_001_options_pool_invalidation.py"

failures: list[str] = []


def check(cond: bool, label: str) -> None:
    print(("PASS  " if cond else "FAIL  ") + label)
    if not cond:
        failures.append(label)


opt = OPT.read_text(encoding="utf-8")
mat = MAT.read_text(encoding="utf-8")

# --- C1：缓存命中路径先探测签名 ---
check(
    "def _entity_pool_signature(key):" in opt,
    "C1a options_api 定义了 _entity_pool_signature",
)
get_pool_seg = re.search(
    r"def _get_pool\(key, kw\):.*?(?=\ndef )", opt, re.S)
check(get_pool_seg is not None, "C1b 找到 _get_pool 函数段")
if get_pool_seg:
    seg = get_pool_seg.group(0)
    idx_hit = seg.find("< _POOL_TTL")
    idx_probe = seg.find("current = _entity_pool_signature(key)")
    idx_return = seg.find("return pool, True")
    check(
        idx_hit != -1 and idx_probe != -1 and idx_return != -1
        and idx_hit < idx_probe < idx_return,
        "C1c TTL 命中后、return 前先做签名探测",
    )
    # 探测不匹配 → 从缓存清除该条目（用同一份缓存的身份判断防并发误清）
    check(
        "_POOL_CACHE.get(key) is cached" in seg and "_POOL_CACHE.pop(key, None)" in seg,
        "C1d 签名不一致时清除缓存条目（并发安全地清）",
    )

# --- C2：物料分支带 status 可入池行数 ---
check(
    "M.query.filter(_db.or_(M.status == 'active'" in opt
    and "M.status.is_(None)" in opt,
    "C2 物料签名含 active/NULL/'' 可入池行数（能感知停启用）",
)

# --- C3：material.py 编辑路由调用显式失效，且在主 commit 之后 ---
m = re.search(
    r"def edit_material\(id\):.*?(?=\n    @app\.route)", mat, re.S)
check(m is not None, "C3a 找到 edit_material 函数段")
if m:
    seg = m.group(0)
    idx_commit = seg.find("db.session.commit()")
    idx_inval = seg.find("invalidate_options_pool('material')")
    idx_msg = seg.find("msg = '物料更新成功'")
    check(
        idx_commit != -1 and idx_inval != -1 and idx_msg != -1
        and idx_commit < idx_inval < idx_msg,
        "C3b 失效调用在主事务 commit 之后、返回成功之前",
    )

# --- C4：拼音记忆化 ---
check(
    "@lru_cache(maxsize=" in opt and "def _py_keys(text):" in opt,
    "C4 _py_keys 已用 lru_cache 记忆化（重建时拼音零重算）",
)
check("from functools import lru_cache" in opt, "C4b lru_cache 已导入")

# --- C5：探测异常 fail-open ---
sig_seg = re.search(
    r"def _entity_pool_signature\(key\):.*?(?=\ndef )", opt, re.S)
check(sig_seg is not None, "C5a 找到 _entity_pool_signature 函数段")
if sig_seg:
    seg = sig_seg.group(0)
    check(
        "except Exception:" in seg and "return None" in seg,
        "C5b 探测异常返回 None（fail-open）",
    )
if get_pool_seg:
    seg2 = get_pool_seg.group(0)
    check(
        "current is None or current == sig" in seg2,
        "C5c 探测结果 None（失败）按「未变化」处理（fail-open 不重建）",
    )
    check(
        "try:\n            current = _entity_pool_signature(key)\n        except Exception:\n            current = None" in seg2,
        "C5d 探测调用自身异常也被兜住（下拉绝不 500）",
    )

# --- C6：缓存条目三元组 ---
if get_pool_seg:
    check(
        "_POOL_CACHE[key] = (now, pool, sig)" in get_pool_seg.group(0),
        "C6 缓存条目写入 (时间, 池, 签名) 三元组",
    )

# --- C7：版本号 ---
ver = VER.read_text(encoding="utf-8")
check("__version__ = '2026.11.19'" in ver, "C7 版本号已递增到 2026.11.19")

# --- C8：回归测试 ---
if TST.exists():
    t = TST.read_text(encoding="utf-8")
    names = re.findall(r"^def (test_\w+)\(", t, re.M)
    check(len(names) >= 6, "C8 回归测试存在且含 %d 条用例: %s" % (len(names), ", ".join(names)))
    check(
        'assert "211008" in _codes(' in t and "10平方" in t,
        "C8b 测试复刻了报障场景（211008 + 10平方）",
    )
else:
    check(False, "C8 回归测试文件存在")

print("-" * 60)
if failures:
    print("共 %d 项未通过：" % len(failures))
    for f in failures:
        print("  - " + f)
    sys.exit(1)
print("全部断言通过。")
