# -*- coding: utf-8 -*-
"""P1-7 收敛「防回退」静态门禁。

行为由 tests/test_p1_7_three_ledgers_business_paths.py（判据）与
tests/test_p1_7_transfer_converged.py（调拨入口）覆盖；本文件管的是另一件事：

    **已经收敛的路径，不许再有人手写绕过。**

库存三账写入只允许经 services/warehouse_stock_service.py 的两个入口：
  - apply_stock_delta      入/出库语义（改 ① 总账 + ③ 流水 + ② 库位账）
  - apply_transfer_pair    调拨语义（只写双流水 + ② 库位账，① 不动）

路由文件里一旦重新出现 add_stock / deduct_stock / add_stock_transaction /
update_location_inventory / deduct_location_inventory_atomic 的**实际调用**，
说明又有人在手工双写三账——那是 BUG-2026-09-20-008 型静默账实分裂的温床。

判定方式：先剥掉 Python 行注释再匹配调用形态（名字后紧跟 `(`），
避免把说明性注释里的函数名误判为违规。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"

# 只允许经入口写的库存原语
FORBIDDEN = (
    "add_stock",
    "deduct_stock",
    "deduct_stock_atomic",
    "add_stock_transaction",
    "update_location_inventory",
    "deduct_location_inventory_atomic",
)


def _strip_comments(src: str) -> str:
    """去掉行注释（本文件用途下足够：原语名不会出现在字符串字面量里）。"""
    return re.sub(r"#[^\n]*", "", src)


def _calls(src: str, name: str) -> list[str]:
    return re.findall(rf"(?<![\w.]){name}\s*\(", src)


# (文件, 必须使用的入口)
CONVERGED = [
    ("app/routes/transfer.py", "apply_transfer_pair"),
    ("app/routes/requisition.py", "apply_stock_delta"),
]


@pytest.mark.parametrize("rel,entry", CONVERGED)
def test_route_uses_single_entry(rel, entry):
    """已收敛的路由必须引用对应入口。"""
    src = (ROOT / rel).read_text(encoding="utf-8")
    assert entry in src, f"{rel} 未使用入口 {entry}"


@pytest.mark.parametrize("rel,entry", CONVERGED)
@pytest.mark.parametrize("primitive", FORBIDDEN)
def test_route_no_manual_primitive_calls(rel, entry, primitive):
    """已收敛的路由不得再手工调用底层库存原语（注释不算）。"""
    src = _strip_comments((ROOT / rel).read_text(encoding="utf-8"))
    hits = _calls(src, primitive)
    assert not hits, (
        f"{rel} 仍在手工调用 {primitive}()（{len(hits)} 处）——"
        f"必须改经入口 {entry}，否则三账双写会再次分叉。"
    )


def test_services_module_exposes_both_entries():
    """入口函数必须存在于服务模块，且签名是关键字-only 的仓库/库位参数。"""
    src = (APP_DIR / "services/warehouse_stock_service.py").read_text(encoding="utf-8")
    for fn in ("apply_stock_delta", "apply_transfer_pair"):
        m = re.search(rf"^def {fn}\(", src, re.MULTILINE)
        assert m, f"{fn} 不存在"
    # 两个入口都必须有 * 分隔的关键字参数，防止调用方按位置误传仓库
    assert "*, transaction_type," in src.replace("'", "").replace('"', "")
