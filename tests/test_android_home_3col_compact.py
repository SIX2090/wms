"""WMS 手机端首页优化（2026-09-26）结构断言。

背景
----
用户截图暴露三个问题：① 13 张功能卡 2 列 168dp 高，首屏只能看 4 张，要滚两屏；
② 卡片副标题（如"手工/扫码 · 多物料入库"）在窄卡内被截断；③ 今日概览条四格
副标题（"入0 出0"、"低于安全库存"）未设 maxLines，换行导致四格基线错位。

本次优化（仅 HomeScreen.kt，零外溢）：
- 卡片网格 2 列 → 3 列，高度 168dp → 104dp
- 副标题 2 行 → 1 行 + Ellipsis，5 条超长文案精简
- 概览条四格 label/sub 加 maxLines=1 + 顶对齐
- Hero 区与概览条半悬浮衔接

2026-10-30 用户要求简化布局：三列及全部入口保留；固定高度、半悬浮断言
按新规格替换为内容自适应和正常文档流断言，并新增 Compose 真实测量回归。

2026-11-15 用户授权改为分组工作台；旧几何约束按新规格更新。
本测试只验证消费者接线，实际编译、点击与字体测量见 NativeWorkbenchTest / CompactLayoutTest。
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HOME_SCREEN = (
    REPO_ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms" / "ui" / "screens" / "HomeScreen.kt"
)


def _read() -> str:
    assert HOME_SCREEN.exists(), f"缺少源文件: {HOME_SCREEN}"
    return HOME_SCREEN.read_text(encoding="utf-8")


def _extract_function(source: str, signature: str) -> str:
    """大括号配对精确截取函数体（表达式体函数取到下一个成员声明）。"""
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


# ---------------------------------------------------------------------------
# ① 卡片网格：3 列
# ---------------------------------------------------------------------------

def test_home_groups_prioritize_primary_tasks():
    # 2026-11-15 用户授权改为分组工作台；十四个入口的真实点击由 NativeWorkbenchTest 验证。
    src = _read()
    for group in ("开始作业", "查询与报表", "资料与工具"):
        assert f'HomeSectionTitle("{group}")' in src
    assert 'HomePrimaryTask(cards[0]' in src and 'HomePrimaryTask(cards[1]' in src
    assert 'HomeEntryRow(cards[2]' in src


def test_secondary_inventory_actions_share_available_width():
    # 新版不用三列末行占位；两张次级作业卡按相同权重布局，内容决定高度。
    src = _read()
    assert 'listOf(cards[3], cards[4]).forEach' in src
    assert 'FunctionCardItem(card, Modifier.weight(1f)' in src
    assert 'HomeEntryRow(card)' in src


# ---------------------------------------------------------------------------
# ② FunctionCardItem 压缩
# ---------------------------------------------------------------------------

def test_card_height_reduced():
    src = _read()
    assert "heightIn(min = 96.dp)" in src
    assert "height(104.dp)" not in src, "固定高度会裁切放大字体"
    assert "height(168.dp)" not in src, "仍残留 168.dp 高度"


def test_card_title_wraps_without_redundant_subtitle():
    src = _read()
    body = _extract_function(src, "fun FunctionCardItem(")
    # 2026-10-30 用户要求减少信息：完整标题可换行，冗余副标题不再渲染。
    assert "card.title" in body
    assert "card.subtitle" not in body
    assert "maxLines" not in body
    assert "TextOverflow.Ellipsis" not in body


# ---------------------------------------------------------------------------
# ③ 今日概览条：四格对齐
# ---------------------------------------------------------------------------

def test_overview_values_adapt_without_truncation():
    src = _read()
    body = _extract_function(src, "private fun TodayMovementCell(")
    assert "WmsAdaptiveRecord(value" in body
    assert "WmsQuantityText(value, Modifier.fillMaxWidth())" in body
    assert "maxLines" not in body and "TextOverflow.Ellipsis" not in body
    assert 'Text(label' in body and 'Text(sub' in body


def test_overview_row_top_aligned():
    src = _read()
    body = _extract_function(src, "fun TodayOverviewBar(")
    assert "verticalAlignment = Alignment.Top" in body, (
        "概览条 Row 未顶对齐，四格 sub 行数不一致时会错位"
    )


def test_overview_alert_text_shortened():
    src = _read()
    assert '"低库存"' in src, "库存告警副标题未精简为「低库存」"
    assert '"低于安全库存"' not in src, "仍残留「低于安全库存」长文案"


# ---------------------------------------------------------------------------
# ④ Hero 半悬浮
# ---------------------------------------------------------------------------

def test_workbench_uses_shared_spacing_and_scroll():
    src = _read()
    assert '.padding(WmsDimens.PagePaddingHorizontal)' in src
    assert '.verticalScroll(rememberScrollState())' in src
    assert 'Brush.verticalGradient' not in src
    assert 'padding(top = 16.dp, bottom = 48.dp)' not in src


def test_overview_states_remain_in_normal_flow():
    src = _read()
    assert "Modifier.offset" not in src
    for state in ('dashboard != null -> TodayOverviewBar', 'isLoading -> DashboardOverviewSkeleton', 'else -> DashboardOverviewError'):
        assert state in src


# ---------------------------------------------------------------------------
# ⑤ 副标题文案精简
# ---------------------------------------------------------------------------

def test_long_subtitles_shortened():
    src = _read()
    for old, new in [
        ("搜索物料 · 拍照上传档案照片", "搜索 · 拍照建档"),
        ("按仓展示 · 各物料每日结存", "按仓每日结存"),
        ("单物料 · 期初出入结存流水", "期初出入结存"),
        ("本人盘点 · 回查差异与采纳状态", "回查差异采纳"),
        ("日期范围 · 按仓查看流水", "按仓查流水"),
    ]:
        assert new in src, f"缺少精简副标题「{new}」"
        assert old not in src, f"仍残留长副标题「{old}」"


def test_cards_count_unchanged():
    """13 张卡全部保留（用户决策：只缩小不减少）+ AI 助手卡（AI-ASSISTANT-MOBILE-001）。"""
    src = _read()
    count = src.count("FunctionCard(")
    # FunctionCard 定义 1 次 + 13 张卡实例 + AI 助手卡 = 15
    assert count == 15, f"卡片数量变动：FunctionCard( 出现 {count} 次（应为 15）"
