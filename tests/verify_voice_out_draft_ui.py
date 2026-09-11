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
check('T1c NavGraph 注入 voiceDraftViewModel',
      'voiceDraftViewModel = voiceDraftViewModel,' in nav)
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
      '最后' not in dl and 'state.matches.isNotEmpty()' in dl)

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
