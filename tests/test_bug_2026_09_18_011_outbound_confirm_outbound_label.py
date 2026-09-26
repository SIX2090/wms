# -*- coding: utf-8 -*-
"""
BUG-2026-09-18-011 回归：手机端出库提交按钮文案统一为「确认出库」。

需求
----
把出库页底部提交按钮的文案由「提交出库」改为「确认出库」。

改动范围（R6：一次改干净同根因消费点）
--------------------------------------
出库链路原本「提交出库」与「确认出库」两套说法混用，同一屏里：
  * 底部按钮          → 「提交出库」
  * 确认弹窗标题      → 「确认出库」
  * 确认弹窗正文      → 「…确认提交出库？」
  * 确认弹窗主按钮    → 「确认出库」
本改动把这四处统一到「确认出库」口径。

为什么是纯文案改动（重要）
--------------------------
自 BUG-2026-09-18-009 起，`submitLabel` 已**降级为纯显示值**：
库位选择器与拍照取证改由 `showLocationSelector` / `showEvidenceCapture`
两个显式布尔参数控制，不再比对按钮文案。因此在本次改动前，把文案从
「提交出库」改成任何别的词都**不会**影响功能开关；在本次改动后同样如此。
本测试同时锁住这一点（T4），防止有人日后把逻辑又挂回文案上。

附带修正：`-009` 的 T7 曾把三个文案字面量硬编码进断言，导致这次合法润色
会让测试变红 —— 测试在**阻止**改动。已改为结构性断言（见 T5）。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENS = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreens.kt')
BASE = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreenBase.kt')
TEST_009 = os.path.join(
    REPO, 'tests', 'test_bug_2026_09_18_009_scan_base_explicit_flags.py')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _code_only(text):
    """去注释，避免把"引用旧文案的说明注释"误判成"旧文案还在"。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', ln) for ln in text.splitlines())


def _outbound_screen(src):
    start = src.index('fun OutboundScreen(')
    end = src.index('fun StocktakeScreen(', start)
    return src[start:end]


def _brace_balance(text):
    depth = 0
    cleaned = re.sub(r'""".*?"""', '', text, flags=re.S)
    cleaned = re.sub(r"'''.*?'''", '', cleaned, flags=re.S)
    for line in cleaned.splitlines():
        line = re.sub(r'//.*$', '', line)
        line = re.sub(r'"(?:[^"\\]|\\.)*"', '""', line)
        line = re.sub(r"'(?:[^'\\]|\\.)*'", "''", line)
        depth += line.count('(') - line.count(')')
    return depth


# ------------------------------------------------- T1 按钮文案已改为确认出库
def test_t1_submit_button_label_is_confirm_outbound():
    """出库页 submitLabel 必须为「确认出库」。"""
    body = _outbound_screen(_read(SCREENS))
    m = re.search(r'submitLabel\s*=\s*"([^"]*)"', body)
    assert m, '出库页未传 submitLabel'
    assert m.group(1) == '确认出库', \
        f'出库页按钮文案应为「确认出库」，实际「{m.group(1)}」'


# ------------------------------------------------- T2 旧文案已彻底移除
def test_t2_old_label_removed_from_code():
    """代码里不得再出现「提交出库」—— 不能只改一处。"""
    code = _code_only(_read(SCREENS))
    assert '提交出库' not in code, \
        'ScanScreens.kt 代码中仍存在「提交出库」（注释中引用历史属允许）'


# ------------------------------------------------- T3 弹窗内文案同口径
def test_t3_dialog_copy_aligned():
    """弹窗标题/正文/主按钮也应为「确认出库」口径，不留旧说法。

    只在**代码**上断言：`ScanScreens.kt` 里有一条说明注释引用了旧句
    「…确认提交出库？」用于解释改了什么，注释里保留历史是合理的。

    AI-APP-FIX-406：弹窗骨架收敛为 WmsSubmitConfirmDialog——标题与主按钮
    文案改经 title/confirmLabel 参数传入（组件内渲染为 Text(title)/
    Text(confirmLabel)），口径约束不变。
    """
    body = _code_only(_outbound_screen(_read(SCREENS)))
    # 弹窗标题
    assert re.search(r'title\s*=\s*"确认出库"', body), \
        '弹窗标题不是「确认出库」'
    # 弹窗正文：应为「…，确认出库？」
    assert re.search(r'Text\("共 \$\{uiState\.scanLines\.size\} 种物料[^"]*确认出库？"\)', body), \
        '弹窗正文未统一为「确认出库？」'
    assert '确认提交出库' not in body, '弹窗正文仍是「确认提交出库」'
    # 主按钮
    assert re.search(r'confirmLabel\s*=\s*"确认出库"', body), \
        '弹窗主按钮不是「确认出库」'


# --------------------------------- T4 纯文案改动：逻辑不得挂回文案上
def test_t4_copy_change_does_not_affect_logic():
    """submitLabel 必须仍是纯显示值（-009 的约束不能被本次改动破坏）。"""
    code = _code_only(_read(BASE))
    assert not re.search(r'submitLabel\s*[=!]=\s*"', code), \
        'submitLabel 又被用作条件判断（-009 的根因复发）'
    # 两个显式开关仍在，且出库页仍开启
    assert re.search(r'showLocationSelector:\s*Boolean', _read(BASE)), \
        'showLocationSelector 参数丢失'
    assert re.search(r'showEvidenceCapture:\s*Boolean', _read(BASE)), \
        'showEvidenceCapture 参数丢失'
    body = _outbound_screen(_read(SCREENS))
    assert 'showLocationSelector = true' in body, '出库页库位选择器被误关'
    assert 'showEvidenceCapture = true' in body, '出库页拍照取证被误关'


# ------------------------- T5 防止测试再次把显示文案硬编码成断言（-009 修订）
def test_t5_009_test_no_longer_hardcodes_copy():
    """-009 的 T7 不得再硬编码具体按钮文案，否则合法润色会把测试弄红。

    只看**可执行代码**：`-009` 的模块/函数 docstring 里引用
    `submitLabel == "提交出库"` 是在解释它当初修的是什么问题，
    属于合理的历史记录，不算"硬编码断言"。
    """
    src = _read(TEST_009)
    # 剥掉所有字符串字面量之外的 docstring 太复杂；改用精确断言：
    # 断言里不能再出现 `submitLabel = "某具体文案"` 这种把文案写死的检查。
    code = _code_only(src)
    # 去掉 docstring（三引号块）后再看
    code = re.sub(r'""".*?"""', '', code, flags=re.S)
    for stale in ('"提交出库"', '"提交入库"', '"提交盘点"'):
        assert f"submitLabel = {stale}" not in code, \
            f'-009 测试仍硬编码断言 submitLabel = {stale}（应改结构性断言）'
    # 结构性断言的标志：提取 submitLabel 值并校验非空 / 互异
    assert 'submitLabel' in code and 'labels' in code, \
        '-009 测试缺少"提取 submitLabel 值并校验"的结构性断言'
    assert re.search(r'len\(set\(labels\)\)\s*==\s*3', code), \
        '-009 测试未校验三个页面文案互异（结构性断言缺失）'


# ------------------------------------------------- T6 入库/盘点文案未被波及
def test_t6_other_pages_unaffected():
    """本次只改出库，入库/盘点文案必须保持原样（防误伤）。"""
    src = _read(SCREENS)
    assert 'submitLabel = "提交入库"' in src, '入库页文案被误改'
    assert 'submitLabel = "提交盘点"' in src, '盘点页文案被误改'


# ------------------------------------------------------------ T7 括号平衡兜底
def test_t7_brace_balance():
    assert _brace_balance(_read(SCREENS)) == 0, 'ScanScreens.kt 括号不平衡'
    assert _brace_balance(_read(BASE)) == 0, 'ScanScreenBase.kt 括号不平衡'
