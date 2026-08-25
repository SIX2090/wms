"""
回归验证：手机端每日报表 UI 字段调整（2026-08-24 用户需求）

需求：
- 每日报表（采购入库/领料单）不显示：金额（汇总总金额 + 明细金额）、用户名（操作人）、
  单据编号
- 需要显示：合同编号

配套改动：
- 后端 /api/mobile/report/daily_detail 明细行新增 contract_no（明细级优先，回退单据头）
- Android ReportModels.DailyReportItem 新增 contractNo 字段
- Android ReportScreens 移除总金额/明细金额/单据编号/操作人，底部行展示合同编号 + 往来单位

验收标准：
- T1: 后端 daily_detail 明细行必须返回 contract_no（明细级优先 item.contract_no）
- T2: Android DailyReportItem 必须有 contractNo（contract_no）字段
- T3: ReportScreens 汇总卡不得再有「总金额」单元格
- T4: ReportScreens 明细行不得再展示 item.amount / item.orderNo / item.operator
- T5: ReportScreens 必须展示合同编号（item.contractNo）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
BACKEND = WORKSPACE / "app/routes/native_api.py"
MODELS = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ReportModels.kt"
SCREEN = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ReportScreens.kt"


def _daily_detail_body() -> str:
    src = BACKEND.read_text(encoding="utf-8")
    m = re.search(r"def\s+mobile_api_report_daily_detail\s*\(", src)
    assert m, "mobile_api_report_daily_detail 未找到"
    # 截取到下一个路由定义
    nxt = src.find("@app.route(", m.end())
    return src[m.start(): nxt if nxt > 0 else len(src)]


def test_t1_backend_row_has_contract_no():
    body = _daily_detail_body()
    assert "'contract_no'" in body, "daily_detail 明细行缺少 contract_no 字段"
    assert re.search(r"item\.contract_no\s+or\s+order\.contract_no", body), (
        "contract_no 必须明细级优先（item.contract_no or order.contract_no）"
    )


def test_t2_android_model_has_contract_no():
    src = MODELS.read_text(encoding="utf-8")
    assert '@SerializedName("contract_no")' in src and "contractNo" in src, (
        "DailyReportItem 缺少 contractNo（contract_no）字段"
    )


def test_t3_summary_no_amount_cell():
    src = SCREEN.read_text(encoding="utf-8")
    assert 'SummaryCell("总金额"' not in src, "汇总卡仍展示「总金额」，需求要求隐藏金额"


def test_t4_item_row_hides_amount_orderno_operator():
    src = SCREEN.read_text(encoding="utf-8")
    m = re.search(r"fun\s+DailyReportItemRow\s*\(", src)
    assert m, "DailyReportItemRow 未找到"
    body = src[m.start():]
    assert "item.amount" not in body, "明细行仍展示金额 item.amount"
    assert "item.orderNo" not in body, "明细行仍展示单据编号 item.orderNo"
    assert "item.operator" not in body, "明细行仍展示操作人 item.operator"


def test_t5_item_row_shows_contract_no():
    src = SCREEN.read_text(encoding="utf-8")
    m = re.search(r"fun\s+DailyReportItemRow\s*\(", src)
    body = src[m.start():]
    assert "item.contractNo" in body, "明细行未展示合同编号 item.contractNo"


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
    print(f"\n所有 {len(tests)} 个每日报表 UI 回归验证通过")
