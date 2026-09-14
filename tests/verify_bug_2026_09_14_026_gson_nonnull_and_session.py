"""BUG-2026-09-14-026 回归测试：Gson 破坏非空契约 / 冷启动会话兜底。

背景
----
`BUG-2026-08-24-007` 确立了一类故障模式：Gson 走 `Unsafe.allocateInstance`，
绕过 Kotlin 构造器与 init，**不执行默认值、不做非空校验**。磁盘 JSON 里缺失的
非空字段会被静默置为 null 并装进"非空"属性，脏值随后在 UI 层被裸调 → 主线程
NPE → 整 App 崩溃（现场表现「屡次停止运行」）。

本次排查在该模式下又找到两个同源隐患：

① `WmsRepository.loadEditDraft()` —— 唯一一个**没有 try/catch** 的反序列化入口
   （同文件的 `loadStocktakeDraft()` 有）。且解出的 `ScanEditDraft.contractNo`
   为非空 `String`、`lines` 为非空 `List`，均可能被 Gson 置 null。

② `WmsRepository.getWarehouses()` —— 缺少 `ensureSession()`，而同类的
   `getDepartments()` / `getEmployees()` 都有。该方法在冷启动首页即可能被调用，
   早于 AuthViewModel 的异步会话还原。

本测试为**契约级断言**（源码结构），因为 Android 运行期无法在 CI 上复现
Keystore 损坏 / 磁盘半写等真机环境。
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID_SRC = REPO_ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

REPOSITORY = ANDROID_SRC / "data" / "repository" / "WmsRepository.kt"
EDIT_DRAFT_MODEL = ANDROID_SRC / "data" / "model" / "ScanEditDraft.kt"
SCAN_REQUESTS = ANDROID_SRC / "data" / "model" / "ScanRequests.kt"


def _extract_function(source: str, signature: str) -> str:
    """按大括号配对精确截取函数体。

    不能用 "找下一个 `    private fun `" 这种近似——若目标函数后面紧跟的是
    `suspend fun`（缩进不同）就会匹配失败，把整个文件余下部分都吞进来，
    导致断言在这段噪声里"碰巧"命中，测试变成假绿。
    """
    start = source.index(signature)
    brace_start = source.index("{", start)
    depth = 0
    for i in range(brace_start, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[start:i + 1]
    raise AssertionError(f"无法截取函数体: {signature}")


def _read(path: Path) -> str:
    assert path.exists(), f"缺少源文件: {path}"
    return path.read_text(encoding="utf-8")


def _strip_comments(source: str) -> str:
    """去掉行注释，避免注释里出现的字样造成假阳性/假阴性。"""
    return "\n".join(
        line for line in source.split("\n") if not line.strip().startswith("//")
    )


# ---------------------------------------------------------------------------
# ① loadEditDraft：必须 try/catch + 必须净化
# ---------------------------------------------------------------------------

def test_load_edit_draft_has_try_catch():
    """loadEditDraft 反序列化必须在 try/catch 内——JSON 损坏不得杀进程。"""
    src = _read(REPOSITORY)
    body = _extract_function(src, "suspend fun loadEditDraft(")

    assert "try {" in body, "loadEditDraft 缺少 try/catch，损坏草稿会抛异常到冷启动链路"
    assert "catch" in body, "loadEditDraft 的 try 没有对应 catch"
    assert "fromJson" in body, "loadEditDraft 未真正反序列化，断言对象可能有误"


def test_load_edit_draft_calls_sanitizer():
    """loadEditDraft 返回值必须经净化，剔除非法的扫码行。"""
    src = _read(REPOSITORY)
    assert "sanitizeEditDraft" in src, "缺少 sanitizeEditDraft 净化函数"

    body = _extract_function(src, "suspend fun loadEditDraft(")
    assert "sanitizeEditDraft" in body, "loadEditDraft 未调用净化函数，脏草稿会直达 UI"


def test_sanitizer_is_itself_guarded():
    """净化函数内部也必须兜底——脏数据可能在任何字段上抛 NPE。

    采用 runCatching，任一处失败整体退化为"无草稿"，绝不把异常抛给调用方。
    注意：本函数为表达式体（`= runCatching { ... }.getOrNull()`），
    `.getOrNull()` 落在闭合大括号**之外**，故需按"声明行到下一个成员"整体截取。
    """
    src = _read(REPOSITORY)
    start = src.index("private fun sanitizeEditDraft(")
    end = src.index("\n    suspend fun ", start)
    decl = src[start:end]
    assert "runCatching" in decl, "净化函数未用 runCatching 兜底，脏数据仍可能抛异常"
    assert "getOrNull" in decl, "净化函数未把失败退化为 null，异常会外泄"


def test_sanitizer_drops_blank_material_code_lines():
    """净化必须丢弃 material_code 为空的坏行，而不是把空串带进提交请求。"""
    src = _read(REPOSITORY)
    body = _extract_function(src, "private fun sanitizeEditDraft(")
    assert "isBlank" in body, "净化未剔除 material_code 为空的脏行"
    assert "mapNotNull" in body, "净化未采用 mapNotNull 丢弃坏行"


def test_edit_draft_model_nonnull_fields_are_known():
    """锁定 ScanEditDraft 的非空字段清单——新增非空字段必须同步进净化逻辑。"""
    src = _read(EDIT_DRAFT_MODEL)
    code = _strip_comments(src)

    # 这些字段声明为不可空（无 `?`），Gson 可能置 null
    assert "val contractNo: String" in code
    assert "val lines: List<DraftScanLine>" in code
    assert "val inboundBusinessType: String" in code


def test_scan_line_nonnull_fields_are_known():
    """ScanLine 的 material_code / quantity 为非空，净化需丢弃无法定位的坏行。"""
    src = _read(SCAN_REQUESTS)
    code = _strip_comments(src)
    assert "val material_code: String" in code
    assert "val quantity: Double" in code


# ---------------------------------------------------------------------------
# ② getWarehouses：必须补 ensureSession
# ---------------------------------------------------------------------------

def _method_body(src: str, signature: str) -> str:
    return _extract_function(src, signature)


def test_get_warehouses_calls_ensure_session():
    """getWarehouses 必须在使用前兜底还原会话，与下游下拉方法保持一致。"""
    src = _read(REPOSITORY)
    body = _method_body(src, "suspend fun getWarehouses(")
    code = _strip_comments(body)
    assert "ensureSession()" in code, (
        "getWarehouses 缺少 ensureSession()：冷启动首个请求可能不带 baseUrl/token"
    )


def test_downstream_list_methods_all_ensure_session():
    """同类下拉列表方法应全部有 ensureSession，防止再次漏掉某一个。"""
    src = _read(REPOSITORY)
    for sig in (
        "suspend fun getWarehouses(",
        "suspend fun getDepartments(",
        "suspend fun getEmployees(",
    ):
        body = _strip_comments(_method_body(src, sig))
        assert "ensureSession()" in body, f"{sig} 缺少 ensureSession()"


def test_ensure_session_defined_and_idempotent():
    """ensureSession 必须存在，且以内存态已就绪即返回（幂等、零开销）。"""
    src = _read(REPOSITORY)
    assert "suspend fun ensureSession()" in src
    body = _method_body(src, "suspend fun ensureSession(")
    assert "return" in body, "ensureSession 无提前返回，可能不幂等"


# ---------------------------------------------------------------------------
# ③ 离线队列：确认已有兜底，避免误报
# ---------------------------------------------------------------------------

def test_offline_replay_is_guarded():
    """离线补传的 replay 调用点必须有异常兜底（本项为已存在行为的回归保护）。"""
    src = _read(ANDROID_SRC / "data" / "repository" / "OfflineQueueManager.kt")
    assert "catch (e: Exception)" in src, "离线补传缺少通用异常兜底"
