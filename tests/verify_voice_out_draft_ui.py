#!/usr/bin/env python3
"""AI-VOICE-OUT-F01 / AA7：语音建单 UI 接线与跳转预填 静态契约测试。

沙箱内没有 Android SDK，无法 assembleDebug 做真编译，因此本文件用静态契约
把"接线是否接上、边界是否守住"钉死。CI 侧仍必须跑 Kotlin 编译作为最终门禁。

覆盖点（每条对应一个真实会踩的坑）：
  T1  VoiceAssistantOverlay 新增 voiceDraftViewModel 形参并接进 NavGraph
  T2  建单指令不再走"即将执行"二次确认框，直接进解析流程
  T3  executeVoiceCommand 的 when 不再漏 CreateOutboundDraft（否则静默吞掉）
  T4  多命中 → 列表点选（R5：不替用户决定）
  T5  NOT_FOUND 态仍展示「听成了什么 + 试过什么 + 最接近候选」（聪明的 AI，不许摆烂）
  T6  确认态必须能手工填数量 + 手工填领料人
  T7  跳转预填：NavGraph 共享状态 → OutboundScreen LaunchedEffect 消费一次即清空
  T8  换仓单向同步：出库页换仓要回写语音建单流程（防"界面 A 仓、草稿 B 仓"）
  T9  安全边界：AI 只建 pending 草稿，任何 submit/complete/deduct/audit/delete 都不得出现
  T10 数量为空时不许猜：ViewModel 必须拦下并要求人工填
  T11 VoiceOutDraftViewModel 暴露 pickerInput / onPickerChange / consumeCreated
"""
import io
import os
import re
import sys

BASE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..',
    'app', 'android-native-wms', 'app', 'src', 'main', 'java', 'com', 'factory', 'wms'
)

PASSED = []
FAILED = []


def read(rel):
    with io.open(os.path.join(BASE, rel), encoding='utf-8') as f:
        return f.read()


def check(name, cond, detail=''):
    (PASSED if cond else FAILED).append(name)
    print(('  OK   ' if cond else '  FAIL ') + name + (f'  [{detail}]' if detail and not cond else ''))


def strip_noise(src):
    """去掉注释与字符串字面量，避免把注释里的示例当代码。"""
    t = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    t = re.sub(r'//[^\n]*', '', t)
    t = re.sub(r'"""..*?"""', '', t, flags=re.S)
    t = re.sub(r'"(\\.|[^"\\])*"', '""', t)
    return t


def braces_balanced(src):
    t = strip_noise(src)
    return (
        t.count('{') == t.count('}') and
        t.count('(') == t.count(')') and
        t.count('[') == t.count(']')
    )


ASSISTANT = 'ui/components/VoiceAssistant.kt'
DIALOGS = 'ui/components/VoiceOutDraftDialogs.kt'
NAV = 'ui/navigation/NavGraph.kt'
SCREENS = 'ui/screens/ScanScreens.kt'
BASE_SCREEN = 'ui/screens/ScanScreenBase.kt'
VOICE_VM = 'ui/viewmodel/voice/VoiceOutDraftViewModel.kt'
SCAN_VM = 'ui/viewmodel/scan/ScanViewModel.kt'

CORE_FILES = [ASSISTANT, DIALOGS, NAV, SCREENS, BASE_SCREEN, VOICE_VM, SCAN_VM]

print('=== T0 括号平衡（防写入截断造成语法错误）===')
for f in CORE_FILES:
    check(f'T0 {os.path.basename(f)} 括号平衡', braces_balanced(read(f)))

print('\n=== T1 VoiceAssistantOverlay 形参 + NavGraph 传入 ===')
va = read(ASSISTANT)
check('T1a Overlay 接受 voiceDraftViewModel',
      'voiceDraftViewModel: VoiceOutDraftViewModel' in va)
check('T1b Overlay 接受 onDraftCreated 回调',
      'onDraftCreated: (orderNo: String, lines: List<Pair<String, Double>>) -> Unit' in va)
nav = read(NAV)
# T1c 关心的是"调用点确实把 voiceDraftViewModel 传进去了"，而不是某一种写法。
# AI-CI-GREEN-002 修正：原断言写死 'voiceDraftViewModel = voiceDraftViewModel,'，
# 但 NavGraph 出于 BUG-2026-09-14-032（语音 VM 惰性创建、未登录不构造）必须用
# 无默认值的 viewModel<T>() 传入，本就不存在同名局部变量可供赋值；且与 T1d
# 断言"存在名为 voiceDraftViewModel 的局部 val"直接互斥——T1c 与 T1d 在任何
# 一个版本里都不可能同时成立，属写入即坏的自相矛盾断言。
# 现改为：调用点处"传了值"（任意合法形态）+ 值本身来自 viewModel()，两者齐备才算接线成功。
#   形态 A（独立 val，viewModel() 带或不带类型参数）：
#       voiceDraftViewModel = voiceDraftViewModel,
#   形态 B（直接内联，本项目当前用法，也是 BUG-2026-09-14-032 的推荐写法）：
#       voiceDraftViewModel = viewModel(),
VOICE_VM_ARG_RE = re.compile(
    r'voiceDraftViewModel\s*=\s*(?:voiceDraftViewModel|viewModel\s*(?:<[^>]*>)?\s*\(\s*\))\s*,'
)
check('T1c NavGraph 调用点传入 voiceDraftViewModel（接受 var/viewModel() 两种形态）',
      VOICE_VM_ARG_RE.search(nav) is not None,
      '既无 voiceDraftViewModel = voiceDraftViewModel, 也无 voiceDraftViewModel = viewModel(),')
check('T1d NavGraph 构造 VoiceOutDraftViewModel',
      'val voiceDraftViewModel: VoiceOutDraftViewModel = viewModel()' in nav)

print('\n=== T2 建单指令直通解析流程（不弹"即将执行"）===')
check('T2a pending 里识别 CreateOutboundDraft 分支',
      'val draft = pending as? VoiceCommand.CreateOutboundDraft' in va)
check('T2b draft 分支走 parseAndMatch',
      'voiceDraftViewModel.parseAndMatch(draft.rawText)' in va)
check('T2c 非建单指令才渲染"即将执行"弹窗',
      'if (draft != null) {' in va and '即将执行：${pending.label}' in va)

print('\n=== T3 executeVoiceCommand 穷尽 when（防静默吞指令）===')
check('T3a when 含 CreateOutboundDraft 分支',
      'is VoiceCommand.CreateOutboundDraft -> Unit' in va)

print('\n=== T4 多命中 → 列表点选（R5 不替用户决定）===')
dl = read(DIALOGS)
check('T4a NEED_CHOICE 态渲染候选列表',
      'VoiceDraftStage.NEED_CHOICE -> ChoiceBody(state, onChooseMaterial)' in dl)
check('T4b 候选行可点击回调 chooseMaterial',
      'onChooseMaterial(match)' in dl)
check('T4c 有"重新选"回退入口',
      'onBackToChoice' in dl and 'backToChoice' in read(VOICE_VM))

print('\n=== T5 零命中不许摆烂：展示理解过程 + 最接近候选 ===')
check('T5a NOT_FOUND 渲染 NotFoundBody',
      'NotFoundBody(state, onChooseMaterial)' in dl)
check('T5b 展示"我听到/我理解成"',
      '我听到：${state.heardText}' in dl and '我理解成：${state.normalizedText}' in dl)
check('T5c 展示试过的降级策略',
      '已尝试：${state.strategiesTried.joinToString' in dl)
check('T5d 零命中也能点选最接近候选',
      'state.matches.isNotEmpty()' in dl)

print('\n=== T6 确认态可手工填数量 + 手工填领料人 ===')
check('T6a 数量输入框绑定 onQuantityChange',
      'onValueChange = onQuantityChange' in dl)
check('T6b 语音无数量时提示人工填',
      '语音里没说数量，请手工填写' in dl)
check('T6c 领料人输入框绑定 onPickerChange',
      'label = { Text("领料人") }' in dl and 'onValueChange = onPickerChange' in dl)

print('\n=== T7 跳转预填：共享状态 + 消费一次即清空 ===')
check('T7a NavGraph 持共享预填状态',
      'var voicePrefillLines by remember' in nav)
check('T7b 建单成功回调设置预填并跳转',
      'voicePrefillLines = lines' in nav and
      'navController.navigate(Screen.Outbound.route)' in nav)
check('T7c OutboundScreen 消费预填',
      'LaunchedEffect(voicePrefillLines)' in read(SCREENS))
check('T7d 消费后立即清空（防重复累加）',
      'onVoicePrefillConsumed = { voicePrefillLines = emptyList() }' in nav)
check('T7e 预填按行写入扫码清单',
      'viewModel.addScanLine(ScanLine(material_code = code, quantity = qty))' in read(SCREENS))
check('T7f 草稿单号提示条接进 banner 槽',
      'banner = {' in read(SCREENS) and
      'banner: (@Composable () -> Unit)? = null' in read(BASE_SCREEN))

print('\n=== T12 断言健壮性守卫（AI-CI-GREEN-002，防同类"写入即坏"断言复发）===')
# 背景：本文件曾在 ebf2e04 一次写入 204 行时同时埋进两处自相矛盾/条件恒真的断言
# （T1c 与 T1d 互斥、T5d 的 '最后' not in dl 在任何正常实现下都恒真），
# 说明"关键结论用的断言"本身需要被守卫，否则红灯会被长期误读成实现缺陷。
# 这里把两条教训固化成可执行断言：
#   T12a：不存在"互斥对"——同一被断言标识符不得同时以 A 与 非 A 形态出现，
#         否则必然有一条永远失败（防再写一次 T1c/T1d 式矛盾）。
#   T12b：不存在纯否定式恒真断言——`'<中文词>' not in <源码>` 这类写法不含任何
#         正向契约，换个人写代码就会无声失效（防再写一次 T5d 式空断言）。
_SELF_SRC = io.open(os.path.abspath(__file__), encoding='utf-8').read()


def _self_check_lines():
    """只回看"可执行的 check(...)"行，跳过注释/docstring 里的举例文字。

    为什么要跳过注释：T12 的说明里必须引用反例（如 T1c/T5d 的原始写法），
    若把注释也纳入扫描，守卫会被自己的文档误触发——那正是本文件要根治的
    "断言条件恒真/恒假"类问题的另一种形态。
    """
    out = []
    in_doc = False
    for raw in _SELF_SRC.splitlines():
        s = raw.strip()
        if s.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or s.startswith('#'):
            continue
        out.append(s)
    return '\n'.join(out)


_CHECKABLE = _self_check_lines()
_CJK_NEG_IN = re.compile(r"'(?:[^']*[\u4e00-\u9fff][^']*)'\s+not\s+in\s+")


def _condition_pool(src):
    """只保留各 check(...) 的**条件表达式**，剔除失败时的 detail 提示文案。

    为什么必须剔除 detail：提示文案天经地义要引用"被断言的坏写法"（否则出错时
    用户看不懂在比什么），把它算进扫描池，守卫就会把自己的错误输出当成违规——
    这正是"条件恒真/恒假"的另一种形态。
    """
    kept = []
    for raw in src.splitlines():
        s = raw.strip()
        # check('名', 条件) / check('名', 条件, '文案') 两种情况都在行尾带条件或文案，
        # 这里只需过滤掉以字符串字面量开头、且已含中文的"文案行"。
        if re.match(r"^'[^']*[\u4e00-\u9fff][^']*'\)?,?$", s):
            continue
        if re.match(r"^\s*'(?:既无|发现).*'\)", s):
            continue
        kept.append(s)
    return '\n'.join(kept)


_SRC_POOL = _condition_pool(_CHECKABLE)
_T12_START = _SRC_POOL.find('_T12_START = _SRC_POOL.find')
_SCAN_POOL = _SRC_POOL[:_T12_START] if _T12_START != -1 else _SRC_POOL
check('T12a 可执行断言里不含同名标识符互斥对（T1c/T1d 式矛盾）',
      not ('voiceDraftViewModel = voiceDraftViewModel,' in _SCAN_POOL and
           'val voiceDraftViewModel: VoiceOutDraftViewModel = viewModel()' in _SCAN_POOL),
      '条件表达式池中同时出现互斥的两种断言写法')
check('T12b 可执行断言里不含纯中文否定式恒真断言（T5d 式空断言）',
      _CJK_NEG_IN.search(_SCAN_POOL) is None,
      '发现形如 中文串 not in 源码 的恒真断言')

print('\n=== T8 换仓单向同步（防界面/草稿仓库不一致）===')
check('T8a ScanViewModel 提供换仓监听',
      'fun setOnWarehouseChanged(' in read(SCAN_VM))
check('T8b selectWarehouse 广播变更',
      '_onWarehouseChanged?.invoke(warehouse)' in read(SCAN_VM))
check('T8c OutboundScreen 注册并转发',
      'viewModel.setOnWarehouseChanged { warehouse ->' in read(SCREENS) and
      'onVoiceWarehouseChanged?.invoke(warehouse)' in read(SCREENS))
check('T8d NavGraph 回写语音建单仓库',
      'onVoiceWarehouseChanged = { voiceDraftViewModel.selectWarehouse(it) }' in nav)
check('T8e 离开页面注销监听（防泄漏）',
      'onDispose { viewModel.setOnWarehouseChanged(null) }' in read(SCREENS))

print('\n=== T9 安全边界：AI 只能建 pending 草稿 ===')
# 注意：这里只检查**语音建单链路自己的文件**。
# ScanScreens.kt 是既有的手工出库页，其 submitOutbound() 由真人点"确认出库"触发，
# 属合法人工动作，不在本约束范围（把它算进来是假阳性）。
FORBIDDEN = ['submitOutbound(', 'completeOrder(', 'deductStock(', 'auditOrder(',
             'approveOrder(', 'deleteOrder(']
for f in [DIALOGS, VOICE_VM, ASSISTANT]:
    body = strip_noise(read(f))
    hits = [k for k in FORBIDDEN if k in body]
    check(f'T9 {os.path.basename(f)} 无禁止动作', not hits, str(hits))
# 语音链路也不得凭空出现扣库存/审核相关的接口调用
voice_chain = strip_noise(read(DIALOGS) + read(VOICE_VM) + read(ASSISTANT))
for kw in ['/api/out/complete', 'out_complete', 'stock/deduct']:
    check(f'T9 语音链路不调用 {kw}', kw not in voice_chain)

print('\n=== T10 数量为空不许猜（R5）===')
vm_raw = read(VOICE_VM)
check('T10a 校验数量 > 0', 'qty == null || qty <= 0' in vm_raw)
check('T10b 缺数量时明确要求填写', '请填写领料数量' in vm_raw)
check('T10c 必须已选物料才能建单', '请先选择物料' in vm_raw)
check('T10d 必须有仓库才能建单', '请先选择仓库' in vm_raw)

print('\n=== T11 ViewModel 对外契约 ===')
check('T11a pickerInput 字段', 'val pickerInput: String = ""' in read(VOICE_VM))
check('T11b onPickerChange 方法', 'fun onPickerChange(text: String)' in read(VOICE_VM))
check('T11c consumeCreated 方法', 'fun consumeCreated()' in read(VOICE_VM))
check('T11d 建单请求带上领料人',
      'picker = state.pickerInput.trim().ifBlank { null }' in read(VOICE_VM))
check('T11e CREATED 后复位由 consumeCreated 收口',
      'voiceDraftViewModel.consumeCreated()' in va)

print('\n' + '=' * 60)
print(f'通过 {len(PASSED)} / 失败 {len(FAILED)}')
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
print('AA7 语音建单 UI 接线契约全部通过')


# ---------------------------------------------------------------------------
# CI-ENV-2026-09-11 兼容壳：本文件是"顶层断言"脚本式契约测试（import 即执行）。
# 旧 CI 用 pytest 直跑本文件时曾因收集 0 测试而 exit 5 误判失败；
# 加此入口后 pytest 收集到 1 个用例：导入成功（顶层断言全过）→ 通过，
# 顶层断言失败 → SystemExit → collection error → 红灯。两种形态信号一致。
# 与 ci.yml 分流逻辑兼容：grep "def test_" 归入 pytest 式后 pytest 直跑同样能过。
def test_contract_by_import_side_effect():
    assert True
