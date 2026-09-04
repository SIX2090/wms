# -*- coding: utf-8 -*-
"""INV-BATCH-001-E / BUG-2026-09-04-005 Android 锚点：盘点先选盘点单（AA③）。

断言 Android 五层（model/api/repository/viewmodel/screen）都接入 checkId 盘点单选单：
- StocktakeRequest / StocktakeDraft 带 check_id；CheckOrderDto/CheckOrdersListData 存在
- Retrofit @GET api/stocktake/check_orders listPendingCheckOrders
- Repository loadPendingCheckOrders
- ViewModel selectedCheckOrder / loadPendingCheckOrders / submit 携带 checkId 且未选单拦截
- UI CheckOrderSelectorCard + CheckOrderPickerDialog + 确认弹窗 enabled 依赖盘点单
- 版本递增 versionCode 10 / versionName 3.6.0（AI-MOB 发版递增）
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
GRADLE = ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts"


def _p(rel: str) -> str:
    return (BASE / rel).read_text(encoding="utf-8")


def test_model_check_id_fields():
    src = _p("data/model/ScanRequests.kt")
    assert '@SerializedName("check_id") val checkId: Long? = null' in src, "StocktakeRequest 必须携带 check_id"
    assert "data class CheckOrderDto" in src and "checkNo" in src
    assert "data class CheckOrdersListData" in src
    assert "@SerializedName(\"check_id\") val checkId: Long? = null,\n    val lines" in src, \
        "StocktakeDraft 断点续盘草稿必须持久化 checkId"


def test_api_endpoint():
    src = _p("data/api/WmsApiService.kt")
    assert '@GET("api/stocktake/check_orders")' in src
    assert "suspend fun listPendingCheckOrders" in src
    assert "CheckOrdersListData" in src


def test_repository_loader():
    src = _p("data/repository/WmsRepository.kt")
    assert "suspend fun loadPendingCheckOrders(warehouseCode: String): Result<List<CheckOrderDto>>" in src


def test_viewmodel_selection_and_submit_guard():
    src = _p("ui/viewmodel/scan/ScanViewModel.kt")
    assert "val checkOrders: List<CheckOrderDto> = emptyList()" in src
    assert "val selectedCheckOrder: CheckOrderDto? = null" in src
    assert "fun loadPendingCheckOrders()" in src
    assert "fun selectCheckOrder(order: CheckOrderDto)" in src
    assert "checkId = checkOrder.id" in src, "submitStocktake 必须携带所选盘点单 id"
    assert "请选择盘点单（在电脑端创建盘点单后选择" in src
    # 换仓必须重置所选盘点单
    assert "if (changed) null else _uiState.value.selectedCheckOrder" in src
    # 断点续盘草稿带 check_id 并自动回选
    assert "checkId = s.selectedCheckOrder?.id" in src
    assert "private fun restoreStocktakeCheckOrder(checkId: Long)" in src


def test_screen_ui_and_confirm_gate():
    src = _p("ui/screens/ScanScreens.kt")
    assert "CheckOrderSelectorCard(" in src
    assert "CheckOrderPickerDialog(" in src
    assert "showCheckOrderDialog" in src
    assert "import com.factory.wms.data.model.CheckOrderDto" in src
    # 确认弹窗的提交按钮依赖"已选盘点单"
    assert "uiState.selectedWarehouse != null && uiState.selectedCheckOrder != null" in src


def test_version_bump():
    gradle = GRADLE.read_text(encoding="utf-8")
    assert "versionCode = 10" in gradle
    assert 'versionName = "3.6.0"' in gradle
