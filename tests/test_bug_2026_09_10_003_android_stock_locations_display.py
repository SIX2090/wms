# -*- coding: utf-8 -*-
"""BUG-2026-09-10-003 回归：Android 查库存结果卡展示契约（源码锚点）。

P1-①徽标「库存充足/不足」依赖 min_stock 真值——结果卡必须有最低库存
InfoChip 且徽标按 minStock 比较；P1-②结果卡必须有「库位分布」区块，
逐行展示各库位数量。沙箱无 Android SDK，按仓库先例用源码锚点锁定。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DTO = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/MaterialDto.kt"
SCREENS = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt"

dto_src = DTO.read_text(encoding="utf-8")
screens_src = SCREENS.read_text(encoding="utf-8")


def test_material_dto_has_locations_field_with_compat_default():
    # DTO 增加 locations（snake_case 序列化名），带默认值保持存量构造兼容
    assert '@SerializedName("locations") val locations: List<MaterialLocationDto>? = null' in dto_src
    assert "data class MaterialLocationDto(" in dto_src
    assert '@SerializedName("location") val location: String?' in dto_src
    assert '@SerializedName("quantity") val quantity: Double?' in dto_src
    # min_stock/reorder_point 字段契约保留（后端本次起真实下发）
    assert '@SerializedName("min_stock") val minStock: Double?' in dto_src
    assert '@SerializedName("reorder_point") val reorderPoint: Double?' in dto_src


def test_result_card_badge_compares_against_min_stock():
    # 徽标必须按 stock 与 minStock 比较（不是恒与 0 比）
    assert "(material.stock ?: 0.0) > (material.minStock ?: 0.0)" in screens_src
    # 结果卡展示最低库存/再订货点（后端本次起下发真值）
    assert 'InfoChip("最低库存", formatQuantity((material.minStock ?: 0).toDouble()))' in screens_src
    assert 'InfoChip("再订货点", formatQuantity((material.reorderPoint ?: 0).toDouble()))' in screens_src


def test_result_card_has_locations_distribution_block():
    # 「库位分布」区块：非空才显示，逐行展示库位与数量
    assert "if (!material.locations.isNullOrEmpty()) {" in screens_src
    assert '"库位分布"' in screens_src
    assert "material.locations.orEmpty().forEach { loc ->" in screens_src
    assert "loc.location.orEmpty()" in screens_src
    assert "formatQuantity(loc.quantity ?: 0.0)" in screens_src
