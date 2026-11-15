# -*- coding: utf-8 -*-
"""INV-BATCH-001-E / BUG-2026-09-04-005 Android 锚点：盘点先选盘点单（AA③）。

断言 Android 五层（model/api/repository/viewmodel/screen）都接入 checkId 盘点单选单：
- StocktakeRequest / StocktakeDraft 带 check_id；CheckOrderDto/CheckOrdersListData 存在
- Retrofit @GET api/stocktake/check_orders listPendingCheckOrders
- Repository loadPendingCheckOrders
- ViewModel selectedCheckOrder / loadPendingCheckOrders / submit 携带 checkId 且未选单拦截
- UI CheckOrderSelectorCard + CheckOrderPickerDialog + 确认弹窗 enabled 依赖盘点单
- 版本递增 versionCode ≥ 12 / versionName ≥ 3.7.1（AI-MOB 发版递增；3.6.0 为领料部门/领料人下拉前的版本，3.7.0 为关键词联想前的版本，3.7.2 为首页概览下钻）
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"
GRADLE = ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts"


def _p(rel: str) -> str:
    return (BASE / rel).read_text(encoding="utf-8")


def _version_code(gradle: str) -> int:
    """versionCode 取整数，便于断言 >= 而非锁死某个具体值。"""
    import re
    m = re.search(r"versionCode\s*=\s*(\d+)", gradle)
    assert m, "build.gradle.kts 未找到 versionCode"
    return int(m.group(1))


def _version_tuple(gradle: str) -> tuple:
    import re
    m = re.search(r'versionName\s*=\s*"([\d.]+)"', gradle)
    assert m, "build.gradle.kts 未找到 versionName"
    return tuple(int(x) for x in m.group(1).split("."))


def _kotlin_function_body(source: str, name: str) -> str:
    """Locate a Kotlin function body without depending on its default arguments or line count."""
    # Mask comments and literals so parentheses/braces in them cannot end the declaration.
    masked = re.sub(r'//[^\n]*|/\*[\s\S]*?\*/|"""[\s\S]*?"""|"(?:\\.|[^"\\])*"',
                    lambda match: ' ' * len(match.group()), source)
    declaration = re.search(r'\bfun\s+(?:<[^>]+>\s*)?' + re.escape(name) + r'\s*\(', masked)
    assert declaration, f"未找到 Kotlin 函数 {name}"
    depth = 1
    cursor = declaration.end()
    while cursor < len(masked) and depth:
        depth += (masked[cursor] == '(') - (masked[cursor] == ')')
        cursor += 1
    assert depth == 0, f"{name} 参数括号未闭合"
    opening = masked.find('{', cursor)
    assert opening != -1, f"{name} 缺少函数体"
    depth = 1
    cursor = opening + 1
    while cursor < len(masked) and depth:
        depth += (masked[cursor] == '{') - (masked[cursor] == '}')
        cursor += 1
    assert depth == 0, f"{name} 函数体未闭合"
    return source[opening:cursor]



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
    persist = _kotlin_function_body(src, "persistStocktakeDraftNow")
    assert "checkId = state.selectedCheckOrder?.id ?: stocktakeSourceCheckId" in persist
    restore = _kotlin_function_body(src, "maybeRestoreStocktakeDraft")
    assert "stocktakeSourceCheckId = draft.checkId" in restore
    assert "orders.singleOrNull { it.id == draft.checkId }" in restore
    assert "selectedCheckOrder = check ?: CheckOrderDto(draft.checkId" in restore
    assert "if (check == null && draft.requestId == null)" in restore
    submit = _kotlin_function_body(src, "submitStocktake")
    guard = submit.index("if (checkOrder == null)")
    payload = submit.index("val request = StocktakeRequest(")
    assert "val checkOrder = state.selectedCheckOrder" in submit
    assert "return@launch" in submit[guard:payload], "未选盘点单必须在构造请求前终止"
    assert "checkId = checkOrder.id" in submit[payload:]
    selector = _kotlin_function_body(src, "selectCheckOrder")
    assert "stocktakeSourceCheckId != order.id" in selector
    assert "scanLines.isNotEmpty()" in selector, "恢复有内容的草稿不能静默改挂别的盘点单"


def test_screen_ui_and_confirm_gate():
    src = _p("ui/screens/ScanScreens.kt")
    assert "CheckOrderSelectorCard(" in src
    assert "CheckOrderPickerDialog(" in src
    assert "showCheckOrderDialog" in src
    assert "import com.factory.wms.data.model.CheckOrderDto" in src
    # 确认弹窗的提交按钮依赖"已选盘点单"。
    # BUG-2026-09-12-010：该 enabled 表达式改为跨行（追加了 !uiState.isLoading
    # 防重复提交守卫），故按语义断言"两个前置条件都在提交按钮的 enabled 块内"，
    # 不再依赖单行字面量。原始意图（未选盘点单不得提交）保持不变。
    # AI-APP-FIX-406：弹窗骨架收敛为 WmsSubmitConfirmDialog，enabled 表达式改经
    # confirmEnabled 参数传入（组件内 Button(enabled = confirmEnabled)），断言相应
    # 兼容两种写法。
    # 定位方式：从调用 viewModel.submitStocktake() 的按钮块内取 enabled 表达式，
    # 避免误命中页面上其他组件的 enabled（如仓库选择卡）。
    btn = src.index("viewModel.submitStocktake()")
    block = src[btn:btn + 900]
    assert "confirmEnabled" in block or "enabled" in block, (
        "未找到盘点提交按钮的 enabled 前置校验"
    )
    assert "uiState.selectedCheckOrder != null" in block, (
        "盘点确认按钮必须依赖已选盘点单（未选不得提交）"
    )
    assert "!uiState.isLoading" in block, (
        "BUG-2026-09-12-010：盘点确认按钮还须带防重复提交守卫"
    )


def test_version_bump():
    gradle = GRADLE.read_text(encoding="utf-8")
    assert _version_code(gradle) >= 12
    assert _version_tuple(gradle) >= (3, 7, 1)
