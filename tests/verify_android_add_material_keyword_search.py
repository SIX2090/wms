# -*- coding: utf-8 -*-
"""「添加物料」弹窗关键词模糊联想 —— 静态契约测试（AI-MOB-ADD-KEYWORD-01）。

需求：扫码入库 / 扫码出库 / 扫码盘点 / 期初库存四个页面的「添加物料」
弹窗，输入框与「查库存」同口径——支持名称/规格/品牌关键词模糊联想，
不再只认物料编码。选中候选后自动回填物料编码。

实现要点（本测试锁定的契约）：
1. 后端 /api/material/search 按 code|name|spec|brand 四字段 LIKE 匹配
   （app/app.py material_search_api）——后端本来就支持，缺的是 UI。
2. ScanScreenBase 弹窗：输入框 label/placeholder 说明可搜名称规格品牌，
   渲染 materialSuggestions 候选列表，点选回调 onMaterialSuggestionSelected，
   加载中显示 LinearProgressIndicator，候选区限高内部滚动不撑破弹窗。
3. 四个调用点都要接线：入库 / 出库 / 盘点（ScanScreens.kt 三处 ScanScreenBase
   调用）与期初库存（OpeningStockScreen.kt）。
4. OpeningStockViewModel 需具备 materialSuggestions / 
   materialSuggestionsLoading 状态与 searchMaterialSuggestions / 
   clearMaterialSuggestions 方法（防抖 + 序号防竞态）。
5. 版本递增 versionCode 12 / versionName 3.7.1。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "app" / "android-native-wms"
SRC = ANDROID / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# A9:no-test=reason=下面各 test_ 函数即本契约测试本体，被测对象为 Android 源码文本


def test_backend_search_matches_name_spec_brand():
    """后端 /api/material/search 必须按 code/name/spec/brand 四字段模糊匹配。

    这是本次功能的前提：后端早已支持，前端只是没把候选用起来。
    若哪天有人把 brand 从匹配字段里去掉，这里立刻红。
    """
    src = _read(ROOT / "app" / "app.py")
    m = re.search(
        r"@app\.route\('/api/material/search'.*?\n(.*?)\n\n@app\.route",
        src, re.S,
    )
    assert m, "未找到 /api/material/search 端点"
    body = m.group(1)
    for field in ("Material.code", "Material.name", "Material.spec", "Material.brand"):
        assert field in body, f"搜索端点未按 {field} 匹配"


def test_scan_screen_base_dialog_supports_keyword():
    """ScanScreenBase 的「添加物料」弹窗必须渲染关键词候选。"""
    src = _read(SRC / "ui" / "screens" / "ScanScreenBase.kt")

    # 输入框提示已改为可搜名称/规格/品牌
    assert "物料编码 / 名称 / 规格 / 品牌" in src, "输入框 label 未更新为多字段提示"
    assert "输入或扫描物料编码，也可搜名称/规格/品牌" in src, "输入框 placeholder 未更新"

    # 候选列表渲染 + 点选回填
    assert "materialSuggestions.forEachIndexed" in src, "弹窗未渲染候选列表"
    assert "onMaterialSuggestionSelected(material)" in src, "候选点选未回调"

    # 加载态与限高滚动（弹窗空间有限，候选多不能撑破）
    assert "materialSuggestionsLoading" in src, "弹窗缺少候选加载态"
    assert "heightIn(max = 220.dp)" in src, "候选区未限高"
    assert "verticalScroll(rememberScrollState())" in src, "候选区未做内部滚动"

    # 候选行展示规格/品牌，便于用户区分同名前缀物料
    assert '"规格: $it"' in src and '"品牌: $it"' in src, "候选行未展示规格/品牌"


def test_all_four_callers_wire_keyword_search():
    """入库/出库/盘点三处 ScanScreenBase 调用 + 期初库存都要接线。"""
    scan = _read(SRC / "ui" / "screens" / "ScanScreens.kt")
    opening = _read(SRC / "ui" / "screens" / "OpeningStockScreen.kt")

    # ScanScreens.kt：三处 ScanScreenBase 调用（入库/出库/盘点），每处都要有联想接线。
    # 注意本文件还有第 4 处 searchMaterialSuggestions 调用属于「查库存」页自己的
    # 搜索框（该页是联想功能的对标基线，非本次改造对象），故用调用点而非全文计数。
    base_calls = scan.count("ScanScreenBase(")
    assert base_calls == 3, f"ScanScreenBase 调用点应为 3 处，实测 {base_calls}"
    assert scan.count("materialSuggestions = uiState.materialSuggestions") == base_calls, (
        f"三处调用点都要把候选列表传给 ScanScreenBase，"
        f"实测 {scan.count('materialSuggestions = uiState.materialSuggestions')} 处"
    )
    assert scan.count("onMaterialSuggestionSelected") == base_calls, (
        "三处调用点都要传候选点选回调"
    )
    # 弹窗关闭时清空候选，避免下次打开残留（三处 onDismissScanner 都要有）
    assert scan.count("viewModel.clearMaterialSuggestions()") >= base_calls, (
        "三处调用点都要在关闭弹窗时清空候选"
    )
    # 查库存页 + 入库/出库/盘点共 4 处输入联想入口
    assert scan.count("viewModel.searchMaterialSuggestions(it)") == 4, (
        "输入联想入口应为 4 处（查库存页 + 入库/出库/盘点弹窗）"
    )

    # 期初库存：输入变化触发联想 + 候选渲染 + 点选回填 + 关闭清空
    assert "viewModel.searchMaterialSuggestions(it)" in opening, "期初库存未接线联想"
    assert "uiState.materialSuggestions.forEachIndexed" in opening, "期初弹窗未渲染候选"
    assert "uiState.materialSuggestionsLoading" in opening, "期初弹窗缺少加载态"
    assert "heightIn(max = 220.dp)" in opening, "期初候选区未限高"
    assert "viewModel.clearMaterialSuggestions()" in opening, "期初未在关闭时清空候选"
    assert "物料编码 / 名称 / 规格 / 品牌" in opening, "期初输入框 label 未更新"


def test_opening_viewmodel_has_suggestion_state_and_debounce():
    """OpeningStockViewModel 需具备联想状态与防抖搜索（与查库存同实现）。"""
    src = _read(SRC / "ui" / "viewmodel" / "opening" / "OpeningStockViewModel.kt")

    assert "val materialSuggestions: List<MaterialDto> = emptyList()" in src
    assert "val materialSuggestionsLoading: Boolean = false" in src
    assert "fun searchMaterialSuggestions(keyword: String)" in src
    assert "fun clearMaterialSuggestions()" in src
    # 防抖 180ms + 序号防竞态（后发请求先到时丢弃旧结果）
    assert "delay(180)" in src, "缺少防抖"
    assert "materialSearchSequence" in src, "缺少竞态序号"
    assert "materialSearchJob?.cancel()" in src, "缺少旧请求取消"
    # 复用查库存同一个 repository 方法，口径一致
    assert "repository.searchMaterial(normalizedKeyword)" in src


def test_version_bumped():
    """版本递增：versionCode 12 / versionName 3.7.1。"""
    gradle = _read(ANDROID / "app" / "build.gradle.kts")
    assert "versionCode = 12" in gradle
    assert 'versionName = "3.7.1"' in gradle
