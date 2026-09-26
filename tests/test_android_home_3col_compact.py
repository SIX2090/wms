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

本测试为结构断言（沙箱无 Kotlin SDK，无法真编译），与
verify_android_startup_crash_safety.py 同一模式。
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

def test_grid_is_three_columns():
    src = _read()
    assert "row * 3 + col" in src, "网格未改为 3 列（row * 3 + col）"
    assert "row * 2 + col" not in src, "仍残留 2 列索引（row * 2 + col）"
    assert "(cards.size + 2) / 3" in src, "rowCount 未按 3 列计算"


def test_grid_last_row_has_placeholder():
    """末行补 Spacer 占位——13 张卡 3 列末行只 1 张，不补会被拉变形。"""
    src = _read()
    assert "Spacer(modifier = Modifier.width(cardWidth))" in src, (
        "缺少末行占位 Spacer，末行单卡会被 spacedBy 拉变形"
    )


# ---------------------------------------------------------------------------
# ② FunctionCardItem 压缩
# ---------------------------------------------------------------------------

def test_card_height_reduced():
    src = _read()
    assert "height(104.dp)" in src, "卡片高度未压缩到 104.dp"
    assert "height(168.dp)" not in src, "仍残留 168.dp 高度"


def test_card_subtitle_single_line():
    src = _read()
    body = _extract_function(src, "fun FunctionCardItem(")
    # 副标题块：找到 card.subtitle 所在的 Text，其后应有 maxLines = 1
    assert "maxLines = 1" in body, "卡片副标题未限制单行"


# ---------------------------------------------------------------------------
# ③ 今日概览条：四格对齐
# ---------------------------------------------------------------------------

def test_overview_items_single_line():
    src = _read()
    body = _extract_function(src, "private fun OverviewItemCell(")
    # label 和 sub 两个 Text 都应有 maxLines = 1
    count = body.count("maxLines = 1")
    assert count >= 2, f"OverviewItemCell 内 maxLines=1 只出现 {count} 次，label 或 sub 未限制单行"


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

def test_hero_bottom_padding_increased():
    src = _read()
    assert "padding(top = 16.dp, bottom = 48.dp)" in src, (
        "Hero 底部 padding 未加大到 48.dp，无法承接半悬浮概览条"
    )


def test_overview_section_offset():
    src = _read()
    # 标题 + 概览条整体 Column offset，骨架同形
    count = src.count("Column(modifier = Modifier.offset(y = (-28).dp))")
    assert count >= 2, f"半悬浮 offset 只出现 {count} 次，真实布局或骨架至少一处缺失"


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
    """13 张卡全部保留（用户决策：只缩小不减少）。"""
    src = _read()
    count = src.count("FunctionCard(")
    # FunctionCard 定义 1 次 + 13 张卡实例 = 14
    assert count == 14, f"卡片数量变动：FunctionCard( 出现 {count} 次（应为 14）"
