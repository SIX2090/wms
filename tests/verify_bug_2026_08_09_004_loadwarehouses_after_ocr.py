# -*- coding: utf-8 -*-
"""
BUG-2026-08-09-004 回归测试：Android App "识别单据" 页打开即报"网络错误: Failed to connect to /127.0.0.1:5000"

根因：
  AiScreens.kt::DocumentOcrScreen 在挂载瞬间即
  `LaunchedEffect(Unit) { viewModel.loadWarehouses() }`，触发
  `WmsRepository.getWarehouses()` → `api.getWarehouses()` → Retrofit 在
  baseUrl 未配置时（默认 fallback `http://127.0.0.1:5000/`）立即
  `java.net.ConnectException: Failed to connect to /127.0.0.1:5000`，
  异常经 `WmsRepository.getWarehouses()` 包成
  `Result.failure(Exception("网络错误: Failed to connect to /127.0.0.1:5000"))`，
  再经 `AiViewModel.loadWarehouses onFailure` 写入
  `_uiState.error`，最后 `LaunchedEffect(uiState.error)` 在
  Snackbar 弹出。仓库下拉只对 OCR 识别成功、用户进入"确认生成入库草稿"
  阶段才展示，页面初始空态根本不需要仓库数据 → 提前请求就是噪声。

修复：
  把 `loadWarehouses()` 调用从 `LaunchedEffect(Unit)` 整体后移到
  `LaunchedEffect(uiState.ocrResult != null) { if (uiState.ocrResult != null) viewModel.loadWarehouses() }`。
  仅当 OCR 成功（即 `_uiState.ocrResult` 由 null 变为非空）时才请求仓库列表，
  初始空态不再发请求、不再展示误导性网络错误。`loadWarehouses()` 自身
  的 `if (_uiState.value.warehouses.isNotEmpty() || _uiState.value.isLoading) return`
  守卫保留，幂等性不变。

具体断言：
  T1. DocumentOcrScreen 函数体内不再存在
      `LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }` 这种
      页面挂载瞬间即调用的写法。
  T2. DocumentOcrScreen 函数体内必须存在
      `LaunchedEffect(uiState.ocrResult != null)` 块，且块内条件调用
      `viewModel.loadWarehouses()`（即 `if (uiState.ocrResult != null) viewModel.loadWarehouses()`）。
  T3. 旧触发路径上 `viewModel.loadWarehouses()` 不再被任何
      `LaunchedEffect(Unit)` 包裹（必须改用 `uiState.ocrResult != null` 守卫）。
  T4. ObjectRecognizeScreen / StocktakeRecognizeScreen 这两个 screen
      不应被本次修复波及——它们的 `LaunchedEffect(Unit)` 块不应出现
      `loadWarehouses()`（本来就没有，确认无回归）。

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_08_09_004_loadwarehouses_after_ocr.py -xvs
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID_DIR = ROOT / "app" / "android-native-wms" / "app" / "src" / "main"
AI_SCREENS_KT = ANDROID_DIR / "java" / "com" / "factory" / "wms" / "ui" / "screens" / "AiScreens.kt"


def _src() -> str:
    raw = AI_SCREENS_KT.read_text(encoding="utf-8")
    # 去掉 Kotlin 注释（// 单行、/* ... */ 块），避免历史 BUG 注释文本触发误报。
    no_block = re.sub(r"(?<!\S)/\*.*?\*/", "", raw, flags=re.DOTALL)
    no_line = re.sub(r"//[^\n]*", "", no_block)
    return no_line


def _extract_function_body(src: str, fun_name: str) -> str:
    """提取 `fun {name}(...)` 函数体（花括号匹配），用于在单 Screen 作用域内断言。
    允许函数前有 @Composable / @OptIn(...) 等注解。"""
    # 匹配 `fun {name}(`，前面允许任意非 { 的字符（注解、空白、换行）
    m = re.search(rf"fun\s+{fun_name}\s*\(", src)
    assert m is not None, f"找不到函数 {fun_name}"
    # 从 m.start() 开始向前找 { 的位置
    idx = src.find("{", m.end())
    assert idx != -1, f"函数 {fun_name} 找不到开始花括号"
    start = idx
    depth = 0
    for i in range(start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"函数 {fun_name} 的大括号不闭合")


# ---------------------------------------------------------------------------
# T1. DocumentOcrScreen 函数体内不再存在 LaunchedEffect(Unit){...loadWarehouses()...}
# ---------------------------------------------------------------------------
def test_t1_documentocrscreen_no_loadwarehouses_in_launchedeffect_unit():
    """DocumentOcrScreen 内必须不存在 `LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }`
    这种挂载瞬间即触发的写法——这是 BUG 根因。"""
    src = _src()
    body = _extract_function_body(src, "DocumentOcrScreen")
    # 在 DocumentOcrScreen 函数体内寻找：
    # LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }
    # 用非贪婪 + 嵌套花括号匹配
    pattern = (
        r"LaunchedEffect\s*\(\s*Unit\s*\)\s*\{"
        r"(?P<block>(?:[^{}]|\{[^{}]*\})*?)"
        r"\}"
    )
    for m in re.finditer(pattern, body):
        block = m.group("block")
        if "viewModel.loadWarehouses" in block:
            raise AssertionError(
                "DocumentOcrScreen 仍存在 `LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }`，"
                "挂载瞬间即触发网络请求，BUG-2026-08-09-004 未修复。"
                "必须改为 `LaunchedEffect(uiState.ocrResult != null) { if (uiState.ocrResult != null) viewModel.loadWarehouses() }`。"
            )


# ---------------------------------------------------------------------------
# T2. DocumentOcrScreen 函数体内必须存在 LaunchedEffect(uiState.ocrResult != null) { if (...) viewModel.loadWarehouses() }
# ---------------------------------------------------------------------------
def test_t2_documentocrscreen_loadwarehouses_guarded_by_ocrresult():
    """DocumentOcrScreen 内必须存在新的 `LaunchedEffect(uiState.ocrResult != null)`
    守卫块，且块内条件调用 `viewModel.loadWarehouses()`。"""
    src = _src()
    body = _extract_function_body(src, "DocumentOcrScreen")
    # 找 LaunchedEffect(uiState.ocrResult != null) { ... if (uiState.ocrResult != null) viewModel.loadWarehouses() }
    # 允许书写变体：LaunchedEffect(uiState.ocrResult != null) { if (uiState.ocrResult != null) viewModel.loadWarehouses() }
    pattern = (
        r"LaunchedEffect\s*\(\s*uiState\.ocrResult\s*!=\s*null\s*\)\s*\{"
        r"(?P<block>(?:[^{}]|\{[^{}]*\})*?)"
        r"\}"
    )
    matched = False
    for m in re.finditer(pattern, body):
        block = m.group("block")
        # 块内必须同时有条件判断与 loadWarehouses 调用
        if "viewModel.loadWarehouses" in block and "uiState.ocrResult" in block:
            matched = True
            break
    assert matched, (
        "DocumentOcrScreen 缺少 `LaunchedEffect(uiState.ocrResult != null) { if (uiState.ocrResult != null) viewModel.loadWarehouses() }`，"
        "BUG-2026-08-09-004 修复未生效。"
    )


# ---------------------------------------------------------------------------
# T3. 全文件层面：旧 `LaunchedEffect(Unit)` 包裹的 loadWarehouses 必须清零
# ---------------------------------------------------------------------------
def test_t3_no_launchedeffect_unit_contains_loadwarehouses_anywhere():
    """全文件层面（不只 DocumentOcrScreen）不应再出现
    `LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }` 这种裸调用，
    防止别处再引入同样的 BUG 模式。"""
    src = _src()
    # 跨函数查找 LaunchedEffect(Unit) { ... viewModel.loadWarehouses() ... }
    pattern = (
        r"LaunchedEffect\s*\(\s*Unit\s*\)\s*\{"
        r"(?P<block>(?:[^{}]|\{[^{}]*\})*?)"
        r"\}"
    )
    for m in re.finditer(pattern, src):
        block = m.group("block")
        if "viewModel.loadWarehouses" in block:
            raise AssertionError(
                f"全文件仍存在 `LaunchedEffect(Unit) {{ ... viewModel.loadWarehouses() }}`，"
                f"必须在 `LaunchedEffect(uiState.ocrResult != null)` 守卫下再调用。"
            )


# ---------------------------------------------------------------------------
# T4. ObjectRecognizeScreen / StocktakeRecognizeScreen 回归确认
# ---------------------------------------------------------------------------
def test_t4_other_ai_screens_unaffected():
    """ObjectRecognizeScreen / StocktakeRecognizeScreen 不应被本次修复波及——
    这两个 screen 本来就没有 `loadWarehouses()` 调用，回归确认无副作用。"""
    src = _src()
    for screen_name in ("ObjectRecognizeScreen", "StocktakeRecognizeScreen"):
        body = _extract_function_body(src, screen_name)
        assert "loadWarehouses" not in body, (
            f"{screen_name} 出现了 loadWarehouses() 调用，"
            f"BUG-2026-08-09-004 不应影响此 screen，存在回归风险。"
        )
