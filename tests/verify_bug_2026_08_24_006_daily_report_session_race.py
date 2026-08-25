"""
回归测试：BUG-2026-08-24-006 - 手机端首次打开「每日报表」报
「网络错误: 服务器地址未配置，请先登录并填写服务器地址」

问题模式：
- AppNavGraph 组合阶段（App 启动时）即创建 ReportViewModel，其 init 立即调用
  load() 发起每日报表请求。
- AuthViewModel 还原 RetrofitClient 的 baseUrl/token 是异步的（DataStore +
  EncryptedSharedPreferences 首轮读取需数百毫秒），两者存在竞态：报表请求若先于
  会话还原完成，RetrofitClient.apiService 的 check(baseUrl.isNotBlank()) 抛
  IllegalStateException("服务器地址未配置...")，被 getDailyReport 外层 catch 包装成
  「网络错误: 服务器地址未配置，请先登录并填写服务器地址」（用户截图中的报错文本）。
- 该错误态滞留在 ReportViewModel.uiState.error 中，等用户首次进入报表页时
  LaunchedEffect(uiState.error) 弹出；且 init 加载失败后 report==null，
  页面停留在「当日暂无明细」空态，不会自动重试。

修复：
- WmsRepository 新增 ensureSession()：发起请求前若内存 baseUrl 为空，则从持久化
  存储同步还原 token（先于 baseUrl 注入，避免首个请求 401 误触发强制登出）与 baseUrl；
  已还原时为零开销 no-op。getDailyReport/getDashboard 请求前调用。
- ReportViewModel.init 不再自动加载（启动时可能尚未登录，提前加载只会留下过期错误态）；
  加载改由 DailyReportScreen 进入时 LaunchedEffect(Unit) 触发，每次进入按当前
  日期/类型刷新。

验收标准：
- T1: WmsRepository 必须存在 ensureSession()，且先注入 token 再注入 baseUrl
- T2: getDailyReport 必须在 api.dailyReportDetail 之前调用 ensureSession()
- T3: getDashboard 必须在 api.getDashboard 之前调用 ensureSession()（同一竞态）
- T4: ReportViewModel.init 不得再自动调用 load()（旧模式清零）
- T5: DailyReportScreen 必须在 LaunchedEffect(Unit) 中调用 viewModel.load()
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
REPO_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/data/repository/WmsRepository.kt"
VM_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/report/ReportViewModel.kt"
SCREEN_FILE = WORKSPACE / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ReportScreens.kt"


def _src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_function_body(src: str, signature: str) -> str:
    m = re.search(signature, src)
    if not m:
        return ""
    brace_start = src.find("{", m.end())
    if brace_start < 0:
        return ""
    depth = 0
    end = brace_start
    for i in range(brace_start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return src[brace_start: end + 1]


# ---------- T1: ensureSession 存在且先注入 token 再注入 baseUrl ----------
def test_t1_ensure_session_exists_and_token_before_baseurl():
    body = _extract_function_body(_src(REPO_FILE), r"suspend\s+fun\s+ensureSession\s*\(")
    assert body, "WmsRepository.ensureSession 函数未找到"
    assert "getSavedBaseUrl()" in body, "ensureSession 必须读取持久化的 baseUrl"
    assert "getSavedToken()" in body, "ensureSession 必须读取持久化的 token"
    assert "RetrofitClient.setToken" in body, "ensureSession 必须把 token 注入 RetrofitClient"
    assert "RetrofitClient.setBaseUrl" in body, "ensureSession 必须把 baseUrl 注入 RetrofitClient"
    # token 必须先于 baseUrl 注入：避免首个请求不带 Authorization → 401 → 误触发强制登出
    token_pos = body.find("RetrofitClient.setToken")
    baseurl_pos = body.find("RetrofitClient.setBaseUrl")
    assert token_pos < baseurl_pos, "ensureSession 必须先 setToken 再 setBaseUrl"
    # 已还原时必须是 no-op（guard 在最前面）
    assert "getBaseUrl().isNotBlank()" in body, "ensureSession 缺少「已还原则跳过」守卫"


# ---------- T2: getDailyReport 请求前必须调用 ensureSession ----------
def test_t2_daily_report_calls_ensure_session_first():
    body = _extract_function_body(_src(REPO_FILE), r"suspend\s+fun\s+getDailyReport\s*\(")
    assert body, "getDailyReport 函数未找到"
    assert "ensureSession()" in body, (
        "getDailyReport 必须在发起请求前调用 ensureSession()；"
        "BUG-2026-08-24-006：否则会与会话还原竞态抛「服务器地址未配置」"
    )
    ensure_pos = body.find("ensureSession()")
    api_pos = body.find("api.dailyReportDetail")
    assert api_pos >= 0, "getDailyReport 缺少 api.dailyReportDetail 调用"
    assert ensure_pos < api_pos, "ensureSession() 必须在 api.dailyReportDetail 之前调用"


# ---------- T3: getDashboard 请求前必须调用 ensureSession（同一竞态） ----------
def test_t3_dashboard_calls_ensure_session_first():
    body = _extract_function_body(_src(REPO_FILE), r"suspend\s+fun\s+getDashboard\s*\(")
    assert body, "getDashboard 函数未找到"
    assert "ensureSession()" in body, (
        "getDashboard 同样在 App 启动时由 HomeViewModel.init 触发，存在同一竞态，"
        "必须先调用 ensureSession()"
    )
    ensure_pos = body.find("ensureSession()")
    api_pos = body.find("api.getDashboard")
    assert api_pos >= 0, "getDashboard 缺少 api.getDashboard 调用"
    assert ensure_pos < api_pos, "ensureSession() 必须在 api.getDashboard 之前调用"


# ---------- T4: ReportViewModel.init 不得再自动调用 load() ----------
def test_t4_report_viewmodel_init_no_auto_load():
    body = _extract_function_body(_src(VM_FILE), r"init\s*")
    assert body, "ReportViewModel.init 块未找到"
    assert "load()" not in body, (
        "ReportViewModel.init 仍在自动调用 load()——App 启动时（可能尚未登录/会话未还原）"
        "提前加载会留下过期错误态，等用户首次进入报表页时弹出误导性报错"
    )


# ---------- T5: DailyReportScreen 进入时通过 LaunchedEffect 触发加载 ----------
def test_t5_screen_loads_on_entry():
    src = _src(SCREEN_FILE)
    m = re.search(r"LaunchedEffect\(Unit\)\s*\{[\s\S]*?viewModel\.load\(\)[\s\S]*?\}", src)
    assert m, (
        "DailyReportScreen 缺少 LaunchedEffect(Unit) { viewModel.load() }——"
        "init 不再自动加载后，必须在进入报表页时触发加载，否则页面永远空态"
    )


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
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-24-006 回归测试通过")
