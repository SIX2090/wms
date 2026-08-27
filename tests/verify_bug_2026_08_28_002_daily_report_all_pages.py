"""
回归验证：BUG-2026-08-28-002 手机 APP「每日报表」明细只能看到 20 条

问题现象：手机 APP 每日报表（采购入库/领料单）明细列表只显示 20 条，
但汇总统计显示更多（如 58 明细）——因为汇总基于全集、明细列表被分页截断。

根因：WmsRepository.getDailyReport 调 /api/mobile/report/daily_detail 时
不传分页参数，后端默认只返回第 1 页 20 条明细，App 端不做翻页。

修复（Android 侧）：getDailyReport 先取第 1 页，按响应的 totalPages
逐页拉取 2..totalPages 并合并 items，返回全量明细。

验收标准：
- T1: getDailyReport 必须包含按 totalPages 的翻页循环（for page in 2..first.totalPages）
- T2: 翻页请求必须显式传 page/pageSize 参数
- T3: 必须合并各页 items（toMutableList + addAll）
- T4: 合并后通过 copy(items = allItems) 返回全量
- T5: 后端 daily_detail 必须返回 total_pages 分页元数据（契约不破坏）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
REPO_KT = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"
API_KT = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/api/WmsApiService.kt"
BACKEND = WORKSPACE / "app/routes/native_api.py"


def _repo_body() -> str:
    src = REPO_KT.read_text(encoding="utf-8")
    m = re.search(r"suspend\s+fun\s+getDailyReport\s*\(", src)
    assert m, "getDailyReport 未找到"
    # 截取到下一个 suspend fun 定义
    nxt = re.search(r"\n\s+suspend\s+fun\s+\w+\s*\(", src[m.end():])
    end = m.end() + nxt.start() if nxt else len(src)
    return src[m.start():end]


def _daily_detail_body() -> str:
    src = BACKEND.read_text(encoding="utf-8")
    m = re.search(r"def\s+mobile_api_report_daily_detail\s*\(", src)
    assert m, "mobile_api_report_daily_detail 未找到"
    nxt = src.find("@app.route(", m.end())
    return src[m.start(): nxt if nxt > 0 else len(src)]


def test_t1_repository_paginates_all_pages():
    body = _repo_body()
    assert "totalPages" in body, "getDailyReport 未消费 totalPages，无法翻页"
    assert re.search(r"for\s*\(\s*page\s+in\s+2\.\.\s*first\.totalPages\s*\)", body), (
        "缺少 for (page in 2..first.totalPages) 翻页循环"
    )


def test_t2_page_requests_pass_explicit_page_params():
    body = _repo_body()
    assert "page = 1" in body and "pageSize = 20" in body, (
        "第 1 页请求未显式传 page/pageSize"
    )
    assert re.search(r"page\s*=\s*page", body), "后续页请求未传递增的 page 参数"


def test_t3_items_merged_across_pages():
    body = _repo_body()
    assert "toMutableList()" in body, "未建立可变的合并列表"
    assert "addAll(data.items)" in body, "未合并后续页 items"


def test_t4_returns_merged_all_items():
    body = _repo_body()
    assert "copy(items = allItems" in body, (
        "未以 copy(items = allItems) 返回合并后的全量明细"
    )


def test_t5_backend_keeps_pagination_metadata():
    body = _daily_detail_body()
    assert "'total_pages'" in body, "后端响应缺少 total_pages 分页元数据"
    assert "'total'" in body and "'page_size'" in body, (
        "后端响应缺少 total / page_size 分页元数据"
    )


def test_t6_api_service_supports_page_params():
    src = API_KT.read_text(encoding="utf-8")
    m = re.search(r"suspend\s+fun\s+dailyReportDetail\s*\([\s\S]*?\)\s*:", src)
    assert m, "dailyReportDetail 接口未找到"
    sig = m.group(0)
    assert '@Query("page")' in sig and '@Query("page_size")' in sig, (
        "dailyReportDetail 缺少 page / page_size 查询参数"
    )


if __name__ == "__main__":
    tests = [
        test_t1_repository_paginates_all_pages,
        test_t2_page_requests_pass_explicit_page_params,
        test_t3_items_merged_across_pages,
        test_t4_returns_merged_all_items,
        test_t5_backend_keeps_pagination_metadata,
        test_t6_api_service_supports_page_params,
    ]
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-28-002 回归验证通过")
    sys.exit(0)
