# -*- coding: utf-8 -*-
"""
BUG-2026-08-23-001 回归：手机 APP 扫码/手工出入库卡片须显示
物料编码、物料名称、品牌、规格、数量五个字段。

背景：用户截图中扫码入库卡片只显示编码+数量。卡片 UI 与 addScanLine 的
物料详情补全能力在 commit 17df8a1c（2026-08-20）才合入 main，而现场 APK
是 3.1.0 (versionCode 4，2026-08-16 构建)，不含该能力；且能力合入后未递增
版本号，部署包永远不会更新到手机（BUG-2026-08-16-022 已立过同类规矩）。

修复：
1. ScanScreenBase / OpeningStockScreen 详情行字段顺序统一为 名称/品牌/规格，
   配合标题行编码 + 数量行，构成 编码/名称/品牌/规格/数量 五要素。
2. versionCode 4→5、versionName 3.1.0→3.2.0，确保新 APK 能作为更新安装。

验收点（Kotlin 源码级，Android 编译由 CI android-build.yml 兜底）：
T1. ScanScreenBase 卡片渲染 material_code/material_name/material_brand/material_spec/quantity 五字段。
T2. 详情行顺序为 名称 → 品牌 → 规格（listOfNotNull 内顺序断言）。
T3. ScanViewModel.addScanLine 含物料详情补全（getMaterialInfo + searchMaterial 兜底，
    回填 name/spec/brand），扫码与手工添加入库/出库均走该入口。
T4. InboundScreen/OutboundScreen/StocktakeScreen 的扫码与手动添加都调用 addScanLine
    （四入口共用同一渲染与补全链路，不存在"只有入库修了"的分叉）。
T5. versionCode 已递增（>=5）且 versionName 为 3.2.0。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

SCAN_SCREEN_BASE = (ANDROID / "ui" / "screens" / "ScanScreenBase.kt").read_text(encoding="utf-8")
SCAN_SCREENS = (ANDROID / "ui" / "screens" / "ScanScreens.kt").read_text(encoding="utf-8")
SCAN_VM = (ANDROID / "ui" / "viewmodel" / "scan" / "ScanViewModel.kt").read_text(encoding="utf-8")
OPENING_STOCK = (ANDROID / "ui" / "screens" / "OpeningStockScreen.kt").read_text(encoding="utf-8")
BUILD_GRADLE = (ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts").read_text(encoding="utf-8")


def test_scan_card_renders_five_material_fields():
    """T1：卡片展示 编码/名称/品牌/规格/数量。"""
    for field in ("material_code", "material_name", "material_brand", "material_spec"):
        assert f"line.{field}" in SCAN_SCREEN_BASE, f"ScanScreenBase 未渲染 {field}"
    assert "formatQuantity(line.quantity)" in SCAN_SCREEN_BASE


def test_detail_line_order_is_name_brand_spec():
    # 2026-11-15 名称、编码、品牌规格分层，四个身份字段仍按同一语义传给公共视图。
    assert "WmsMaterialIdentity(line.material_code, line.material_name, line.material_brand, line.material_spec)" in SCAN_SCREEN_BASE
    assert "WmsMaterialIdentity(line.materialCode, line.materialName, line.materialBrand, line.materialSpec)" in OPENING_STOCK
    component = (ANDROID / "ui/components/WmsRecordContent.kt").read_text(encoding="utf-8")
    assert 'name?.takeIf' in component and '"编码 $code"' in component
    assert component.index('brand?.takeIf') < component.index('spec?.takeIf')
    assert "softWrap = true" in component and "TextOverflow.Ellipsis" not in component


def test_add_scan_line_enriches_material_details():
    """T3：addScanLine 对缺名称/规格的行经 enrichScanLineMaterial 调用物料接口补全并回填。

    2026-09-03 重构（BUG-2026-09-03-003）：addScanLine 的异步补全抽为
    enrichScanLineMaterial(code) 私有函数供 add/replace 复用，锚点随之更新。
    """
    assert "fun addScanLine(incoming: ScanLine)" in SCAN_VM
    assert "private fun enrichScanLineMaterial(" in SCAN_VM
    assert "enrichScanLineMaterial(line.material_code)" in SCAN_VM
    assert "repository.getMaterialInfo(" in SCAN_VM
    assert "repository.searchMaterialMatches(" in SCAN_VM
    assert "material_name = it.name" in SCAN_VM
    assert "material_spec = it.spec" in SCAN_VM
    assert "material_brand = it.brand" in SCAN_VM


def test_all_four_entry_points_share_add_scan_line():
    """T4：扫码入库/出库 + 手动添加入库/出库（含盘点）全部经 addScanLine，
    共用同一卡片渲染与补全逻辑。"""
    for screen in ("fun InboundScreen(", "fun OutboundScreen(", "fun StocktakeScreen("):
        assert screen in SCAN_SCREENS, f"缺少 {screen}"
    # 手动和扫码都保留补全链；扫码入口固定加 1，不复用手动数量。
    assert SCAN_SCREENS.count("onScanBarcode = { barcode ->") >= 3
    assert SCAN_SCREENS.count("onManualAdd = {") >= 3
    assert SCAN_SCREENS.count("viewModel.addCameraScanLine(barcode,") == 2
    camera = SCAN_VM.split("fun addCameraScanLine(", 1)[1].split("private fun quantityDraftKey", 1)[0]
    assert "return addScanLine(ScanLine(" in camera and "quantity = 1.0" in camera
    assert SCAN_SCREENS.count("viewModel.addScanLine(") >= 3
    stocktake = SCAN_SCREENS.split("fun StocktakeScreen(", 1)[1]
    assert "addOrConfirmStocktakeLine(" in stocktake and "viewModel.addScanLine(line)" in stocktake


def test_apk_version_bumped_for_release():
    """T5：版本号递增，新能力才能随 APK 更新到手机。"""
    code = int(re.search(r"versionCode\s*=\s*(\d+)", BUILD_GRADLE).group(1))
    name = re.search(r'versionName\s*=\s*"([^"]+)"', BUILD_GRADLE).group(1)
    assert code >= 5, f"versionCode 未递增: {code}"
    # AI-MOB-APK-001 起 versionName 随发版递增（3.5.0），硬编码 == 每次升版必挂 CI；
    # 改为逐段数值比较，不得低于既有发版基线 3.3.0。
    got = tuple(int(p) for p in name.split("."))
    assert got >= (3, 3, 0), f"versionName {name} 低于发版基线 3.3.0"
