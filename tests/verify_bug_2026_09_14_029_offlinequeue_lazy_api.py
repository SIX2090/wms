# -*- coding: utf-8 -*-
"""BUG-2026-09-14-029：离线队列 api 必须惰性解析 —— 静态契约测试。

这是「WMS扫码屡次停止运行」的**真实根因**（由 BUG-2026-09-14-028 的应用内崩溃
报告页在真机 3.8.2 上捕获，last_crash.txt 堆栈）：

    RuntimeException: Cannot create an instance of class ScanViewModel
      at NavGraphKt.AppNavGraph
    Caused by: IllegalStateException: 服务器地址未配置，请先登录并填写服务器地址
      at RetrofitClient.getApiService
      at ScanViewModel.<init>

链路：AppNavGraph 组合期创建 ScanViewModel → 其 init **同步**访问
`repository.offlineQueue`（不在 safeCall 内）→ offlineQueue 的 lazy 构造
OfflineQueueManager 时**急切**解析 `api`（WmsRepository.api 的 getter =
RetrofitClient.apiService）→ baseUrl 未配置（未登录 / 全新安装 / 清除数据）时
`check(baseUrl.isNotBlank())` 抛 IllegalStateException → 冷启动闪退。

注意：RetrofitClient.apiService 的 check 是**故意的安全守卫**（防止 token 发往未配置
服务器），不能删；真正错误是 OfflineQueueManager 在构造期就解析 api（它只在 replay
同步时才用 api）。修复：构造改收 `apiProvider: () -> WmsApiService`，内部
`by lazy { apiProvider() }` 延迟到 replay 首用时再解析；彼时已登录、baseUrl 已配置，
即便仍为空也由 doSync 的 try/catch 兜为失败。

本测试锁定的契约：
1. OfflineQueueManager 构造参数是 `apiProvider: () -> WmsApiService`（不再是 eager api）。
2. 内部用 `by lazy { apiProvider() }` 惰性解析 api（构造期不解析）。
3. getInstance 同样收 apiProvider。
4. WmsRepository.offlineQueue 传入 `{ api }` 惰性 lambda，而非裸 `api`。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (
    ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms"
)
OQM = BASE / "data" / "repository" / "OfflineQueueManager.kt"
REPO = BASE / "data" / "repository" / "WmsRepository.kt"


def _read(p: Path) -> str:
    assert p.exists(), f"未找到 {p}"
    return p.read_text(encoding="utf-8")


def _strip(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


# A9:no-test=reason=下面各 test_ 函数即本契约测试本体，被测对象为 Kotlin 源码文本


def test_constructor_takes_provider_not_eager_api():
    src = _strip(_read(OQM))
    assert re.search(r"constructor\([\s\S]*?apiProvider:\s*\(\)\s*->\s*WmsApiService", src), \
        "OfflineQueueManager 构造必须收 apiProvider: () -> WmsApiService"
    # 构造参数列表里不得再有 eager 的 private val api: WmsApiService
    ctor = src[src.find("private constructor"):src.find(") {", src.find("private constructor"))]
    assert "private val api:" not in ctor, "构造期不得持有 eager api: WmsApiService"


def test_api_resolved_lazily_inside():
    src = _strip(_read(OQM))
    assert re.search(r"val api:\s*WmsApiService\s+by lazy\s*\{\s*apiProvider\(\)\s*\}", src), \
        "必须用 by lazy { apiProvider() } 惰性解析 api，构造期不得解析"


def test_getinstance_takes_provider():
    src = _strip(_read(OQM))
    gi = src[src.find("fun getInstance"):]
    assert "apiProvider: () -> WmsApiService" in gi, "getInstance 必须收 apiProvider"
    assert "OfflineQueueManager(context, dao, apiProvider, networkMonitor)" in gi, \
        "getInstance 必须把 apiProvider 透传给构造器"


def test_repository_passes_lazy_lambda():
    src = _strip(_read(REPO))
    # offlineQueue 代码块内必须传 { api } 而非裸 api
    idx = src.find("val offlineQueue")
    assert idx >= 0, "WmsRepository 缺少 offlineQueue"
    block = src[idx:src.find(")", src.find("OfflineQueueManager.getInstance", idx)) + 1]
    assert "{ api }" in block, "offlineQueue 必须传惰性 { api }，而非裸 api（裸 api 会在构造期解析）"
    # 不得再出现 getInstance(...,\n  dao,\n  api,\n ...) 的裸 api 直传
    assert not re.search(r"getInstance\([\s\S]{0,120}?dao,\s*\n\s*api\s*,", block), \
        "不得再裸传 api（会在构造 OfflineQueueManager 时急切解析）"
