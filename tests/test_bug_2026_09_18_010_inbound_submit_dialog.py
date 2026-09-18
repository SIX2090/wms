# -*- coding: utf-8 -*-
"""
BUG-2026-09-18-010 回归：手机端入库确认弹窗缺仓库信息与前置校验。

现象
----
四个扫码页的"提交前确认"弹窗里，**入库页是信息最少的一个**：

  * 出库页显示 共 N 种物料 + 领料部门 + 领料人；
  * 盘点页显示 盘点仓库 + 盘点单，且未选时明确提示
    「尚未选择盘点仓库，请先选择仓库」；
  * 出库/盘点页的确认按钮都带前置校验（盘点：仓库与盘点单都选了才可点）；
  * **入库页只有一句「共 N 种物料，数量 X，确认提交入库？」**，
    仓库、供应商、合同、备注一概不显示，按钮也只看 isLoading，
    未选仓库时照样可点。

为什么这不是"美观问题"
----------------------
入库单的仓库是决定**库存记到哪个仓**的唯一依据。多仓场景下用户点提交前
看不到自己选的是哪个仓，选错仓提交是一次真实账目错误（库存进错仓），
而单据提交后 status 落 completed、无补录入口 —— 错账不可自愈。
盘点页早已用弹窗解决同一类问题，入库页属漏改（同根因不同消费点，R6）。

修复
----
1. 弹窗正文补齐单头信息：收货仓库（未选时改为明确的"请先选择仓库"警告）、
   供应商、合同编号、备注（后三者仅在有值时显示，避免空行噪音）。
2. 确认按钮追加「已选仓库」前置校验：
   `enabled = uiState.selectedWarehouse != null && !uiState.isLoading`
   —— 与盘点页同一写法：前置条件用 && 追加，**不能被 isLoading 覆盖**。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENS = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreens.kt')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _inbound_screen(src):
    """截取 InboundScreen 函数体（到 OutboundScreen 定义为止）。"""
    start = src.index('fun InboundScreen(')
    end = src.index('fun OutboundScreen(', start)
    return src[start:end]


def _inbound_submit_dialog(src):
    """截取 InboundScreen 里的 showSubmitDialog 块。

    用 AlertDialog( 起点 + 大括号配平找终点，避免被内层 lambda 的 `}` 截断。
    """
    seg = _inbound_screen(src)
    pos = seg.index('if (showSubmitDialog) {')
    i = seg.index('{', pos)
    depth = 0
    for j in range(i, len(seg)):
        if seg[j] == '{':
            depth += 1
        elif seg[j] == '}':
            depth -= 1
            if depth == 0:
                return seg[pos:j + 1]
    raise AssertionError('未能配平 InboundScreen 的 showSubmitDialog 块')


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


# ------------------------------------------------------- T1 弹窗展示仓库
def test_t1_dialog_shows_warehouse():
    """入库确认弹窗必须展示收货仓库（改为未选时的警告文案亦可通过）。"""
    body = _inbound_submit_dialog(_read(SCREENS))
    assert 'uiState.selectedWarehouse' in body, \
        '入库确认弹窗未读取 selectedWarehouse（BUG-2026-09-18-010 根因）'
    assert '收货仓库：' in body, '弹窗未展示收货仓库代号/名称'
    assert '尚未选择收货仓库' in body, \
        '未选仓库时缺少明确的前置提示文案'


# ------------------------------------------------- T2 未选仓库时按钮禁用
def test_t2_confirm_button_requires_warehouse():
    """确认按钮必须有"已选仓库"前置校验，且不被 isLoading 覆盖。"""
    body = _inbound_submit_dialog(_read(SCREENS))
    m = re.search(r'enabled\s*=\s*(.+?),\s*\n', body, re.S)
    assert m, '找不到确认按钮的 enabled 表达式'
    cond = m.group(1)
    assert 'selectedWarehouse != null' in cond, \
        f'确认按钮未校验仓库已选：{cond!r}'
    assert '!uiState.isLoading' in cond, \
        f'确认按钮丢失提交中禁用：{cond!r}'
    # 必须是 && 串联前置条件，而不是三选一（用 || 会让未选仓库也能点）
    assert '&&' in cond, f'前置条件未用 && 串联（被覆盖风险）：{cond!r}'
    assert '||' not in cond, f'前置条件用了 ||，未选仓库时按钮会变可点：{cond!r}'


# ------------------------------------------- T3 单头信息一并展示（有值时）
def test_t3_dialog_shows_header_fields_when_present():
    """供应商/合同/备注应在有值时展示，方便提交前最后核对。"""
    body = _inbound_submit_dialog(_read(SCREENS))
    assert 'uiState.selectedSupplier' in body, '弹窗未展示供应商'
    assert 'uiState.contractNo' in body, '弹窗未展示合同编号'
    assert 'uiState.inboundRemark' in body, '弹窗未展示备注'
    # 空值不应产生空行噪音：必须有 isNotBlank / let 之类的存在性判断
    assert re.search(r'inboundRemark\.isNotBlank\(\)|inboundRemark\s*\.takeIf', body), \
        '备注未做非空判断，空备注会产生空行'
    assert re.search(r'contractNo\.isNotBlank\(\)|contractNo\s*\.takeIf', body), \
        '合同号未做非空判断'


# ------------------------------------------------- T4 物料汇总信息未丢失
def test_t4_dialog_keeps_material_summary():
    """改造后原有汇总信息必须保留（防"补了新信息删了旧信息"）。"""
    body = _inbound_submit_dialog(_read(SCREENS))
    assert re.search(r'scanLines\.size', body), '弹窗丢失物料种数'
    assert re.search(r'totalQuantity', body), '弹窗丢失总数量'


# --------------------------------------------- T5 与盘点弹窗口径一致
def test_t5_consistent_with_stocktake_dialog():
    """盘点弹窗是本仓库既有的正确范式，入库页应与它同口径。"""
    src = _read(SCREENS)
    # 盘点弹窗：前置校验用 && 串联
    m = re.search(r'enabled = uiState\.selectedWarehouse != null &&\s*\n\s*uiState\.selectedCheckOrder != null &&\s*\n\s*!uiState\.isLoading', src)
    assert m, '盘点弹窗的既有 && 前置校验写法发生了变化（本修复以它为范式）'
    # 两者都必须展示仓库
    assert '盘点仓库：' in src, '盘点弹窗未展示仓库'
    assert '收货仓库：' in src, '入库弹窗未展示仓库'


# ------------------------------------------------- T6 提交守卫未被削弱
def test_t6_submit_guard_intact():
    """弹窗仍须调用 submitInbound，且 ViewModel 层守卫不能被动到。"""
    body = _inbound_submit_dialog(_read(SCREENS))
    assert 'viewModel.submitInbound()' in body, '弹窗未调用 submitInbound()'
    assert 'showSubmitDialog = false' in body, '弹窗未在提交后关闭'


# ------------------------------------------------------------ T7 括号平衡兜底
def test_t7_brace_balance():
    assert _brace_balance(_read(SCREENS)) == 0, 'ScanScreens.kt 括号不平衡'
