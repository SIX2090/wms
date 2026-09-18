# -*- coding: utf-8 -*-
"""BUG-2026-09-18-006 回归：扫码出入库页「提交」按钮被顶部内容顶出屏幕且滚不回来。

现场现象（用户 2026-09-18 截图 + 口述）：
    手机端 → 出库 → 手工添加，**看不到提交按钮**，单据提交不了。

根因（代码实证）：
    ScanScreenBase 的外层 Column 是**不可滚动**的。它的子项依次是
    header（出库页含 仓库卡 + 领料部门 + 领料人 + 合同编号卡）/ 库位选择器 /
    拍照取证 / 草稿错误 / 扫码反馈 / 离线横幅 / 打印横幅 / 汇总卡，
    只有扫码清单带 weight(1f)。Compose 的 Column 在高度不足时会把**超出的部分
    直接裁掉**（不是压缩，也不是滚动），而后几个子项被裁掉的正是——
    排在最后的底部提交区。因为整体不可滚，用户往回滚也找不回来。

两个放大器（本次一并修）：
    ① ContractInputCard 的合同建议是**无约束 forEach 全量展开**（对比弹窗内
       物料候选早已 heightIn(max=220) + verticalScroll）。出库页输入 1 个字符
       常命中十几条合同，单卡可高达七八百 dp，足以吃光整屏；
    ② 底部提交区里，手工添加的物料联想也是无约束 take(5) 平铺（与 ① 同类形状）。

修复契约（本测试锁定）：
    T1 顶部固定区必须 weight(1f) + verticalScroll —— 内容再高也只滚动，不挤按钮；
    T2 底部提交区必须在可滚区**之外**（非 weight 子项），保证恒被测量与展示；
    T3 合同建议限高 + 内部滚动；
    T4 底部区的手工添加候选同样限高 + 内部滚动，且底部区整体有高度上限；
    T5 入库/出库/盘点三页共用基类，一处修复三页同时生效（R6）；
    T6 Kotlin 括号平衡（无 SDK 时的最低限度编译替代检查）。

沙箱无 Android SDK，按仓库先例（test_bug_2026_09_10_003 / 2026_09_18_003）用
源码锚点锁定，并以 ktlint 做「改动前后语法错误数不增加」的对照。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCREENS_DIR = (
    ROOT
    / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens"
)
BASE = SCREENS_DIR / "ScanScreenBase.kt"
SCAN_SCREENS = SCREENS_DIR / "ScanScreens.kt"

base_src = BASE.read_text(encoding="utf-8")
scan_src = SCAN_SCREENS.read_text(encoding="utf-8")


def test_top_area_is_scrollable():
    """T1：顶部固定区加 weight(1f) + verticalScroll，内容再高也只滚动不挤按钮。"""
    assert ".weight(1f)" in base_src
    assert ".verticalScroll(rememberScrollState())" in base_src
    # 关键：weight 与 verticalScroll 必须落在同一个 modifier 链上（即顶部区那个 Column）
    assert (
        "modifier = Modifier\n"
        "                    .weight(1f)\n"
        "                    .fillMaxWidth()\n"
        "                    .verticalScroll(rememberScrollState())"
    ) in base_src, "顶部区应同时带 weight(1f) 与 verticalScroll"


def test_bottom_action_bar_outside_scroll_area():
    """T2：底部提交区必须留在可滚区之外，保证提交按钮恒可见。

    判定方式：底部 Surface 的注释块与 `Surface(` 之间不得出现 `}` 关闭可滚 Column
    之后又重新打开——这里用更稳的形状断言：底部 Surface 之前紧邻的是可滚 Column
    的闭合，而 Surface 自身不带 weight/verticalScroll。
    """
    marker = "// Bottom actions（顶部圆角浮层，与列表区自然过渡）"
    idx = base_src.index(marker)
    seg = base_src[idx : idx + 1400]
    # 底部区是普通 Surface（不参与 weight 分配、不滚动）
    assert "Surface(" in seg
    assert "weight(1f)" not in seg.split("Column(")[0]
    # 可滚区在底部区之前已闭合（闭合大括号紧邻注释行）
    before = base_src[:idx].rstrip()
    assert before.endswith("}"), "可滚 Column 应在底部操作区之前闭合"


def test_contract_suggestions_height_capped():
    """T3：ContractInputCard 的合同建议限高 + 内部滚动（原为无约束 forEach）。"""
    start = scan_src.index("private fun ContractInputCard(")
    seg = scan_src[start : start + 3200]
    assert "suggestions.isNotEmpty()" in seg
    assert ".heightIn(max = 200.dp)" in seg, "合同建议必须限高"
    assert ".verticalScroll(rememberScrollState())" in seg, "合同建议必须内部滚动"


def test_manual_suggestions_height_capped_and_bar_capped():
    """T4：底部区的手工添加候选限高；底部区整体也有高度上限。"""
    assert "materialSuggestions.take(5)" in base_src
    # 候选包在限高滚动容器内
    idx = base_src.index("materialSuggestions.take(5)")
    seg = base_src[max(0, idx - 900) : idx]
    assert ".heightIn(max = 200.dp)" in seg, "手工添加候选必须限高"
    assert ".verticalScroll(rememberScrollState())" in seg, "手工添加候选必须内部滚动"
    # 底部操作区整体限高，防止内部内容反向撑破
    assert ".heightIn(max = 420.dp)" in base_src


def test_all_three_scan_pages_share_the_base():
    """T5：入库/出库/盘点三页都走 ScanScreenBase，一处修复三页生效（R6）。"""
    assert scan_src.count("ScanScreenBase(") >= 3
    # 三页均应存在，且都不再自己搭不可滚的骨架
    for title in ['title = "入库"', 'title = "出库"', 'title = "盘点"']:
        assert title in scan_src, f"未找到扫描页：{title}"


def test_kotlin_brace_balance():
    """T6：改动后两个 Kotlin 文件括号仍平衡。"""
    for name, src in (("ScanScreenBase.kt", base_src), ("ScanScreens.kt", scan_src)):
        for open_ch, close_ch in [("{", "}"), ("(", ")"), ("[", "]")]:
            assert src.count(open_ch) == src.count(close_ch), (
                f"{name} 的 {open_ch}{close_ch} 不平衡："
                f"{src.count(open_ch)} vs {src.count(close_ch)}"
            )
