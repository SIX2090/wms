"""
回归验证：BUG-2026-08-24-007 手机端打开每日报表整 App 崩溃（渲染 NPE）

现象：
- 手机端进入「每日报表」页面即弹出「WMS扫码 屡次停止运行」（App 崩溃，非接口报错）。

根因：
- DailyReportItem.contractNo 原声明为非空 `String = ""`。但该类多数构造参数无默认值，
  Kotlin 不生成无参构造器，Gson 走 Unsafe.allocateInstance 实例化（绕过构造器，
  默认值 `= ""` 不生效）。服务端响应缺 contract_no 字段（旧版后端）时，
  contractNo 运行时为 null，破坏 Kotlin 非空契约；
- ReportScreens 渲染明细行时裸调 `item.contractNo.isNotBlank()` 抛 NPE，
  异常发生在 Compose 主线程渲染路径且未捕获 → 整 App 崩溃；
- 同链路存量隐患：Material.spec 列可空（nullable），后端原样输出 `"spec": null`
  时 `item.spec.isNotBlank()` 同样 NPE。

修复：
- ReportModels.DailyReportItem：spec / contractNo 改为可空 `String?`（对齐
  supplier / department 的既有可空模式）；
- ReportScreens：`isNotBlank()` → `isNullOrBlank()`；
- 后端 daily_detail：spec 输出统一 `or ''` 兜底，不再下发显式 null。

验收标准：
- T1: DailyReportItem.contractNo 声明为可空 String?
- T2: DailyReportItem.spec 声明为可空 String?
- T3: ReportScreens 不再裸调 item.contractNo.isNotBlank()（必须 isNullOrBlank）
- T4: ReportScreens 不再裸调 item.spec.isNotBlank()（必须 isNullOrBlank）
- T5: 后端 daily_detail 的 spec 输出带 or '' 兜底（禁止下发显式 null）
- T6: 出库页 ContractDto 用法保持 null 安全（orEmpty / isNullOrBlank），无同类 NPE
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
BACKEND = WORKSPACE / "app/routes/native_api.py"
MODELS = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ReportModels.kt"
SCREEN = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ReportScreens.kt"
SCAN_SCREEN = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt"
SCAN_VM = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/scan/ScanViewModel.kt"


def _daily_detail_body() -> str:
    src = BACKEND.read_text(encoding="utf-8")
    m = re.search(r"def\s+mobile_api_report_daily_detail\s*\(", src)
    assert m, "mobile_api_report_daily_detail 未找到"
    nxt = src.find("@app.route(", m.end())
    return src[m.start(): nxt if nxt > 0 else len(src)]


def _item_row_body() -> str:
    src = SCREEN.read_text(encoding="utf-8")
    m = re.search(r"fun\s+DailyReportItemRow\s*\(", src)
    assert m, "DailyReportItemRow 未找到"
    return src[m.start():]


def test_t1_contract_no_nullable():
    src = MODELS.read_text(encoding="utf-8")
    m = re.search(r'@SerializedName\("contract_no"\)\s+val\s+contractNo\s*:\s*([^,\n]+)', src)
    assert m, "DailyReportItem 缺少 contractNo 字段声明"
    assert "String?" in m.group(1), (
        f"contractNo 必须声明为可空 String?（Gson 绕过构造器默认值，"
        f"当前声明：{m.group(1).strip()}）"
    )


def test_t2_spec_nullable():
    src = MODELS.read_text(encoding="utf-8")
    m = re.search(r'@SerializedName\("spec"\)\s+val\s+spec\s*:\s*([^,\n]+)', src)
    assert m, "DailyReportItem 缺少 spec 字段声明"
    assert "String?" in m.group(1), (
        f"spec 必须声明为可空 String?（material.spec 列可空，后端可能下发 null，"
        f"当前声明：{m.group(1).strip()}）"
    )


def test_t3_contract_no_null_safe_usage():
    body = _item_row_body()
    assert "item.contractNo.isNotBlank()" not in body, (
        "明细行裸调 item.contractNo.isNotBlank()：contractNo 可空，"
        "Gson 缺字段/显式 null 时会抛 NPE 导致 App 崩溃"
    )
    assert re.search(r"!item\.contractNo\.isNullOrBlank\(\)", body), (
        "明细行必须使用 !item.contractNo.isNullOrBlank() 判空后展示合同编号"
    )


def test_t4_spec_null_safe_usage():
    body = _item_row_body()
    assert "item.spec.isNotBlank()" not in body, (
        "明细行裸调 item.spec.isNotBlank()：spec 可空，null 时抛 NPE"
    )
    assert re.search(r"!item\.spec\.isNullOrBlank\(\)", body), (
        "明细行必须使用 !item.spec.isNullOrBlank() 判空后展示规格"
    )


def test_t5_backend_spec_fallback_empty_string():
    body = _daily_detail_body()
    m = re.search(r"'spec':\s*(.+?),\n", body)
    assert m, "daily_detail 明细行缺少 spec 输出"
    expr = m.group(1).strip()
    assert "or ''" in expr or "or \"\"" in expr, (
        f"spec 输出必须 or '' 兜底（material.spec 列可空，显式 null 会破坏 "
        f"App 端非空契约），当前表达式：{expr}"
    )


def test_t6_outbound_contract_usage_null_safe():
    """出库页合同快速匹配的 ContractDto 用法必须保持 null 安全，无同类 NPE。"""
    screen = SCAN_SCREEN.read_text(encoding="utf-8")
    vm = SCAN_VM.read_text(encoding="utf-8")
    for label, src in (("ScanScreens", screen), ("ScanViewModel", vm)):
        assert "contract.contractNo.isNotBlank()" not in src, (
            f"{label} 裸调 contract.contractNo.isNotBlank()：ContractDto 字段可空，会 NPE"
        )
        assert "contract.projectName.isNotBlank()" not in src, (
            f"{label} 裸调 contract.projectName.isNotBlank()：ContractDto 字段可空，会 NPE"
        )
    # 渲染建议项与回填必须是 null 安全写法
    assert "contract.contractNo.orEmpty()" in screen, "建议项合同编号渲染必须 orEmpty()"
    assert "contract.projectName.isNullOrBlank()" in screen, "建议项项目名必须 isNullOrBlank 判空"
    assert "contract.contractNo.orEmpty()" in vm, "选中回填必须 orEmpty()"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        sys.exit(1)
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-24-007 NPE 崩溃回归验证通过")
