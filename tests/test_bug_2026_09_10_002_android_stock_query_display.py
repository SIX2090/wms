# -*- coding: utf-8 -*-
"""BUG-2026-09-10-002 回归：Android 查库存候选展示契约（源码锚点）。

用户实测两点：①输「电线」点查询只弹「物料不存在」——要求精确未命中时
回退模糊列表；②候选只显示前 8 条且名称/规格/品牌挤一行省略号截断——
要求列出全部命中物料、名称/规格/品牌逐行完整显示。

沙箱无 Android SDK 无法编译 Kotlin，按仓库先例（verify_bug_2026_09_03_004）
用源码锚点锁定契约，APK 由 GitHub Actions 构建发布。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt"
VIEWMODEL = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/scan/ScanViewModel.kt"

screens_src = SCREENS.read_text(encoding="utf-8")
vm_src = VIEWMODEL.read_text(encoding="utf-8")


def _stock_query_block(src: str) -> str:
    start = src.index("fun StockQueryScreen(")
    return src[start:]


def test_search_button_and_ime_use_keyword_query_with_fuzzy_fallback():
    block = _stock_query_block(screens_src)
    # 放大镜按钮走 queryMaterialByKeyword（精确→模糊回退），不再直接精确查询
    assert "viewModel.queryMaterialByKeyword(manualCode.trim())" in block
    # 键盘搜索键（IME Search）同口径
    assert "KeyboardOptions(imeAction = ImeAction.Search)" in block
    assert "KeyboardActions(onSearch = {" in block
    # ViewModel 提供精确未命中回退模糊搜索的统一入口
    assert "fun queryMaterialByKeyword(keyword: String)" in vm_src
    fallback = vm_src.index("fun queryMaterialByKeyword(keyword: String)")
    tail = vm_src[fallback:]
    assert "repository.getMaterialInfo(normalized, whCode)" in tail
    assert "repository.searchMaterial(normalized, whCode)" in tail
    # 回退结果写入候选列表（交由页面展示全部命中物料）
    assert "materialSuggestions = materials" in tail


def test_suggestion_list_shows_all_matches_scrollable():
    block = _stock_query_block(screens_src)
    # 不再 take(N) 截断候选
    assert not re.search(r"materialSuggestions\.take\(\d+\)", block), \
        "候选列表仍存在 take(N) 截断"
    # 候选来自完整 materialSuggestions 且高度受限可滚动
    assert "val visibleSuggestions = uiState.materialSuggestions" in block
    assert ".heightIn(max = " in block
    assert ".verticalScroll(rememberScrollState())" in block


def test_suggestion_item_displays_name_spec_brand_fully():
    block = _stock_query_block(screens_src)
    # 候选项名称独立成行
    assert "material.name.orEmpty()" in block
    # 规格/品牌组合行保留（规格: x   品牌: y）
    assert '"规格: $it"' in block
    assert '"品牌: $it"' in block
    # 候选卡片区域不再有单行省略号截断（修复点所在的 StockQueryScreen 内）
    card_start = block.index("val visibleSuggestions = uiState.materialSuggestions")
    card_end = block.index("if (index < visibleSuggestions.size - 1)")
    card_block = block[card_start:card_end]
    assert "TextOverflow.Ellipsis" not in card_block, "候选项仍使用省略号截断"
    assert "maxLines = 1" not in card_block, "候选项仍限制单行显示"


def test_empty_state_message_for_no_match():
    block = _stock_query_block(screens_src)
    # 模糊也无命中时页面空态提示（替代「物料不存在」toast）
    assert "未找到包含「$manualCode」的物料" in block
