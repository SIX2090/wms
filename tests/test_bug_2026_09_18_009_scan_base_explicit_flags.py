# -*- coding: utf-8 -*-
"""
BUG-2026-09-18-009 回归：扫码页基类不得用「按钮文案」驱动功能开关。

现象（潜在，未爆发但已具备爆发条件）
------------------------------------
`ScanScreenBase` 里渲染「库位选择器」+「拍照取证」两块功能的条件是：

    if (submitLabel == "提交入库" || submitLabel == "提交出库") { ... }

`submitLabel` 是**按钮显示文案**。全仓库检索，它是该变量唯一的逻辑用途
（其余两处都是直接显示）。也就是说：

  * 谁把按钮文案从「提交入库」润色成「确认入库」（纯 UI 改动），
    **库位选择器和拍照取证会一起静默消失** —— 无编译错误、无测试报警，
    只有"启用库位管理后入库必须填写库位"这条后端校验才会在提交时报错；
  * 更隐蔽的是盘点页：它的行为仰赖"自己的文案不等于提交入库/出库"这个
    **否定式巧合**，即把别人的文案当成了自己的开关。

这是典型的「隐式耦合」缺陷：两个独立功能（库位 / 取证）挂在一个显示字符串上，
改文案 = 改功能，而改文案的人完全不会去读基类实现。

修复
----
把隐式反推改为调用方**显式声明**：

  * `showLocationSelector: Boolean = false`  —— 是否渲染库位选择器
  * `showEvidenceCapture: Boolean = false`   —— 是否渲染拍照取证入口

`submitLabel` 降级为**纯显示**，不再参与任何逻辑判断。
三个调用点各自声明真实意图（入库/出库 = true，盘点 = false），
新增页面必须主动决策而不是继承巧合。
"""
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreenBase.kt')
SCREENS = os.path.join(
    REPO, 'app', 'android-native-wms', 'app', 'src', 'main', 'java',
    'com', 'factory', 'wms', 'ui', 'screens', 'ScanScreens.kt')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


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


def _strip_comments(text):
    """去掉行注释与块注释，只留可执行代码 —— 否则"引用旧代码的说明注释"
    会被误判成"旧代码还在"。"""
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return '\n'.join(re.sub(r'//.*$', '', ln) for ln in text.splitlines())


# ------------------------------------------------------- T1 字符串开关已删除
def test_t1_submit_label_string_gate_removed():
    """原来的文案比对必须彻底消失，不能只是加个旁路。

    注意：只在**代码**上判断，注释里允许引用旧写法作为说明。
    """
    src = _strip_comments(_read(BASE))
    assert 'submitLabel == "提交入库"' not in src, \
        'submitLabel 仍参与「提交入库」文案比对（BUG-2026-09-18-009 根因未除）'
    assert 'submitLabel == "提交出库"' not in src, \
        'submitLabel 仍参与「提交出库」文案比对'
    # 任何把 submitLabel 参与比较/条件判断的写法都要拒绝
    assert not re.search(r'submitLabel\s*[=!]=\s*"', src), \
        'submitLabel 仍被用作条件判断（应降级为纯显示）'


# --------------------------------------------------------- T2 新参数已声明
def test_t2_explicit_boolean_params_declared():
    """基类必须新增两个显式布尔参数，且默认关闭（新增页面强制主动决策）。"""
    src = _read(BASE)
    assert re.search(r'showLocationSelector:\s*Boolean\s*=\s*false', src), \
        '缺少 showLocationSelector: Boolean = false 参数'
    assert re.search(r'showEvidenceCapture:\s*Boolean\s*=\s*false', src), \
        '缺少 showEvidenceCapture: Boolean = false 参数'


# --------------------------------------------------- T3 渲染条件改用新参数
def test_t3_render_conditions_use_new_params():
    """两块功能的渲染条件必须挂在新参数上。"""
    src = _read(BASE)
    assert re.search(r'if\s*\(\s*showLocationSelector\s*\)', src), \
        '库位选择器的渲染条件未改用 showLocationSelector'
    assert re.search(r'if\s*\(\s*showEvidenceCapture\s*\)', src), \
        '拍照取证的渲染条件未改用 showEvidenceCapture'
    # 库位选择器组件本身要还在（别把功能删了）
    assert 'ScanLocationSelector(viewModel)' in src, '库位选择器组件被误删'
    assert '拍照取证（' in src, '拍照取证按钮被误删'


# ------------------------------------------------ T4 入库/出库点声明为 true
def test_t4_inbound_outbound_opt_in():
    """入库/出库产生单据，必须显式开启两块功能。"""
    src = _read(SCREENS)
    m = re.search(r'fun InboundScreen\(.*?\n\}\n', src, re.S)
    assert m, '找不到 InboundScreen'
    inbound = m.group(0)
    assert 'showLocationSelector = true' in inbound, '入库页未开启库位选择器'
    assert 'showEvidenceCapture = true' in inbound, '入库页未开启拍照取证'

    m2 = re.search(r'fun OutboundScreen\(.*?\n\}\n', src, re.S)
    assert m2, '找不到 OutboundScreen'
    outbound = m2.group(0)
    assert 'showLocationSelector = true' in outbound, '出库页未开启库位选择器'
    assert 'showEvidenceCapture = true' in outbound, '出库页未开启拍照取证'


# ------------------------------------------------- T5 盘点页显式声明为关闭
def test_t5_stocktake_opts_out_explicitly():
    """盘点不产生单据，必须**显式**写 false，而不是靠文案否定式巧合。"""
    src = _read(SCREENS)
    m = re.search(r'fun StocktakeScreen\(.*?\n    ScanScreenBase\(', src, re.S)
    assert m, '找不到 StocktakeScreen 的 ScanScreenBase 调用'
    seg_start = m.end()
    seg = src[seg_start:seg_start + 4000]
    assert 'showLocationSelector = false' in seg, \
        '盘点页未显式声明 showLocationSelector = false'
    assert 'showEvidenceCapture = false' in seg, \
        '盘点页未显式声明 showEvidenceCapture = false'


# ------------------------------------------- T6 三个调用点都必须显式传参
def test_t6_all_call_sites_pass_params_explicitly():
    """三处调用都要显式传参 —— 漏传会静默回落到默认值，等于又埋一次隐式耦合。"""
    src = _read(SCREENS)
    calls = [m.start() for m in re.finditer(r'ScanScreenBase\(', src)]
    assert len(calls) == 3, f'预期 3 个 ScanScreenBase 调用点，实际 {len(calls)}'
    # 每个调用点从其起始位置到下一个调用点（或文件尾）之间的内容归它所有，
    # 避免固定窗口截断（入库页 header 块较长，固定 2600 字会切不到参数）。
    bounds = calls + [len(src)]
    for idx in range(len(calls)):
        seg = src[bounds[idx]:bounds[idx + 1]]
        assert 'showLocationSelector =' in seg, \
            f'第 {idx + 1} 个调用点未显式传 showLocationSelector'
        assert 'showEvidenceCapture =' in seg, \
            f'第 {idx + 1} 个调用点未显式传 showEvidenceCapture'


# ------------------------------------------------- T7 文案仍作为显示值保留
def test_t7_submit_label_still_used_for_display():
    """submitLabel 不能一起删掉 —— 它仍要作为按钮文案显示。"""
    src = _read(BASE)
    # 按钮上仍引用 submitLabel（显示用途）
    assert re.search(r'submitLabel\s*,', src), \
        'submitLabel 未再用于按钮文案显示（应降级为纯显示而非删除）'
    assert re.search(r'submitLabel:\s*String', src), 'submitLabel 参数声明丢失'
    screens = _read(SCREENS)
    for label in ('"提交入库"', '"提交出库"', '"提交盘点"'):
        assert f'submitLabel = {label}' in screens, f'缺少按钮文案 {label}'


# ------------------------------------------------------------ T8 括号平衡兜底
def test_t8_brace_balance():
    for path in (BASE, SCREENS):
        assert _brace_balance(_read(path)) == 0, \
            f'{os.path.basename(path)} 括号不平衡'
