# -*- coding: utf-8 -*-
"""BUG-2026-09-10-011 回归（Android 静态契约）：错误文案不再吞掉服务端 msg。

背景：WmsRepository 有 20 处 `catch (e: Exception) { Result.failure(Exception(
"网络错误: ${e.message}")) }`，会把 handleResponse 已正确透传的服务端业务提示
（如「请选择进行中的盘点单」「请选择仓库」）覆盖成"网络错误"，现场以为网络故障
而反复重试。实测 handleResponse 本身是正确的，问题只在这些外层 catch。

修复：
- 新增 `WmsRepository.BusinessException`：标记"服务端已给出明确原因"的失败
- 新增私有 `safeCall { }`：业务错误原样放行，仅真网络异常才加"网络错误"前缀
- 20 处调用点全部收口到 safeCall（含 3 个 submit 的级联 catch）

验收：
- T1 BusinessException 存在且挂在 companion object 上
- T2 safeCall 先捕获 BusinessException 再兜底捕获 Exception
- T3 handleResponse 的失败路径统一产出 BusinessException（而非裸 Exception）
- T4 不得再有"裸 try/catch 直包 网络错误"的存量写法（收口完成）
- T5 getDashboard / getDailyReport 等关键接口走 safeCall
- T6 级联 catch（submit 类）必须放行 BusinessException
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"


def _src() -> str:
    return REPO.read_text(encoding="utf-8")


def test_t1_business_exception_in_companion():
    src = _src()
    assert "class BusinessException(message: String) : Exception(message)" in src
    # 必须定义在 companion object 内（供 UI 层按类型判断）
    comp = src.index("companion object {")
    comp_end = src.index("\n    }", comp)
    assert "class BusinessException" in src[comp:comp_end], \
        "BusinessException 应定义在 companion object 内"


def test_t2_safe_call_catches_business_first():
    src = _src()
    # T 必须 reified：内部要调用同为 reified 的 handleResponse。
    # 若非 reified，Release 编译直接失败
    # （"Cannot use 'T' as reified type parameter"，CI job 103063453342）。
    assert "private suspend inline fun <reified T> safeCall(" in src
    body = src[src.index("private suspend inline fun <reified T> safeCall("):]
    body = body[:body.index("private inline fun <reified T> handleResponse")]
    # BusinessException 分支必须在 Exception 分支之前
    assert body.index("catch (e: BusinessException)") < body.index("catch (e: Exception)")
    assert "网络错误" in body.split("catch (e: Exception)")[1], \
        "只有兜底 catch 才应标注网络错误"


def test_t3_handle_response_yields_business_exception():
    src = _src()
    body = src[src.index("private inline fun <reified T> handleResponse"):]
    assert "Result.failure(BusinessException(envelope.displayMessage()))" in body
    assert "Result.failure(BusinessException(envelope?.displayMessage()" in body
    assert 'Result.failure(BusinessException(errorMsg ?: "请求失败' in body
    # 不应再有裸 Exception 承载业务 msg
    assert "Result.failure(Exception(envelope" not in body


def test_t4_no_legacy_wrapping_left():
    src = _src()
    # 存量写法：try 块内直接跟 "网络错误" 兜底 —— 应已全部收口到 safeCall
    legacy = re.findall(
        r'handleResponse<[^>]+>\(response\)\n\s*\} catch \(e: Exception\) \{\n'
        r'\s*Result\.failure\(Exception\("网络错误',
        src,
    )
    assert legacy == [], f"仍有 {len(legacy)} 处未收口的写法"


def test_t5_key_apis_use_safe_call():
    src = _src()
    for fn in ("getDashboard", "getDailyReport", "searchMaterial",
               "getOpeningStock", "createPrintJob"):
        body = src[src.index(f"suspend fun {fn}("):]
        body = body[:body.index("suspend fun", 10)] if "suspend fun" in body[10:] else body
        assert "safeCall" in body, f"{fn} 应走 safeCall 以保留服务端 msg"


def test_t6_cascade_catch_passes_business_exception():
    src = _src()
    # submit 类接口（含额外处理）的外层 catch 必须先放行 BusinessException
    cascade = src.count("} catch (e: BusinessException) {\n            Result.failure(e)")
    assert cascade >= 5, f"级联 catch 放行 BusinessException 的数量不足：{cascade}"
