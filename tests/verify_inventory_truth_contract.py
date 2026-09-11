#!/usr/bin/env python3
"""P1-a 库存读取收口：A11 lint 规则 + 收口文档契约测试。

背景（详见 INVENTORY_TRUTH.md）：
系统里"库存"有三个口径——总账 ``material.stock``（全局合计）、
库位账 ``location_inventory.quantity``（仓库 × 库位）、流水 ``stock_transaction``
（事实来源）。业务校验（够不够扣）必须用仓库级口径
``get_warehouse_stock_quantities()``，否则多仓库下会把"A仓+B仓合计"当成
"A仓可用"，导致 B 仓库存掩护 A 仓超发、盘点算出错误调整单。

同一根因已实测复发 4 次：BUG-2026-09-02-001（native_api 盘点）、
09-03-001（Excel 导入）、09-03-002（mobile 展示）、09-03-004（Android 展示）。
本测试把 A11 规则"能抓校验、放过展示"的行为钉死，防止规则被改钝。

覆盖点：
  T1  A11 已注册且默认启用、有中文描述
  T2  A11 判定口径包含比较运算符与 is_stock_sufficient 两种校验语境
  T3  A11 放过展示类用法（不入规则匹配的校验分支）
  T4  A11 豁免注释 stock-truth:reason= 存在且被检测
  T5  A11 仅对 git staged 新增行强制（不误报存量）
  T6  A11 对 app/utils.py（库存工具模块本身）整体豁免
  T7  INVENTORY_TRUTH.md 存在且覆盖三份数据 + 恒等式 + 派生方向 + 不猜铁律
  T8  INVENTORY_TRUTH.md 与 AGENTS.md / WMS_BUSINESS_SCOPE.md 交叉引用
  T9  收口函数 get_warehouse_stock_quantities 仍然"绝不回退全局"（防规则被架空）
  T10 A11 在真实存量仓库上跑一次必须 0 违规（防基线白名单腐化）
"""
import io
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
LINT = os.path.join(ROOT, 'scripts', 'lint_wms_rules.py')
TRUTH = os.path.join(ROOT, 'INVENTORY_TRUTH.md')
APP_PY = os.path.join(ROOT, 'app', 'app.py')

PASSED = []
FAILED = []


def read(p):
    with io.open(p, encoding='utf-8') as f:
        return f.read()


def check(name, cond, detail=''):
    (PASSED if cond else FAILED).append(name)
    print(('  OK   ' if cond else '  FAIL ') + name +
          (f'  [{detail}]' if detail and not cond else ''))


lint_src = read(LINT)
truth_src = read(TRUTH) if os.path.exists(TRUTH) else ''
app_src = read(APP_PY)

print('=== T1 A11 规则已注册 ===')
check('T1a 存在 RuleA11 类', 'class RuleA11NoRawGlobalStockCheck(Rule)' in lint_src)
check('T1b 规则名为 a11', "name = \"a11\"" in lint_src)
check('T1c 默认启用', 'enabled = True' in lint_src)
check('T1d 已注册进 RULES', '"a11": RuleA11NoRawGlobalStockCheck()' in lint_src)
check('T1e 在展示顺序中', '"a10", "a11"' in lint_src)
check('T1f 描述含中文', '（改用仓库级口径）' in lint_src)

print('\n=== T2 A11 能抓"校验语境" ===')
check('T2a 匹配比较运算符', r'[<>]=?|==|!=' in lint_src)
check('T2b 匹配 is_stock_sufficient 调用',
      'is|check)_stock_sufficient' in lint_src)
check('T2c 匹配 material/mat 等引用', r'material|mat|m|item\.material' in lint_src)
check('T2d 有 _is_check_context 判定函数',
      'def _is_check_context(self, stripped_text' in lint_src)
check('T2e 跨行回溯（往上 3 行）', 'pre.split("\\n")[-3:]' in lint_src)
# 间接场景：赋值给局部变量后在后续行比较——存量代码最常见形态
# （requisition.py:188 / transfer.py:186 / subcontract.py:320 均为此形态）。
# 若不做这层追踪，规则会漏掉绝大多数真实违规，形同虚设。
check('T2f 追踪"赋值后比较"间接场景',
      'assign_m = re.search(' in lint_src and '往下方看 6 行内' in lint_src)

print('\n=== T3 A11 放过"展示语境" ===')
# 展示用法不应触发：'stock': material.stock or 0 / f-string 插值 / 排序聚合
check('T3a 规则只抓校验，靠 _is_check_context 早退',
      'if not self._is_check_context(stripped, m.start(), line_start):' in lint_src)
# T3b 的真正验证在 T11（分类器实跑：展示用例判定为 False），
# 这里只确认规则文档写明了判定口径。
check('T3b 文档写明展示 vs 校验的判定口径',
      '校验语境' in lint_src and '展示用途' in lint_src)

print('\n=== T4 豁免注释 ===')
check('T4a 定义了 stock-truth 豁免注释正则',
      r'#\s*stock-truth\s*:' in lint_src)
check('T4b 检测本行与上一行',
      'for offset in (0, -1):' in lint_src)

print('\n=== T5 仅对 staged 新增行强制 ===')
check('T5a 调用 get_staged_added_lines',
      'added_lines = get_staged_added_lines(repo_root, f)' in lint_src)
check('T5b 存量行跳过', 'if ln not in added_lines:' in lint_src)
check('T5c 有基线白名单字典', '_BASELINE_ALLOW' in lint_src)
check('T5d 基线白名单命中即放过', 'if ln in baseline:' in lint_src)

print('\n=== T6 app/utils.py 整体豁免 ===')
check('T6a utils.py 被跳过', "if rel == \"app/utils.py\":" in lint_src)
check('T6b 跳过原因在扫描逻辑中说明',
      '是库存工具模块本身' in lint_src)
# 反向验证：utils.py 里的 check_stock_sufficient 确实裸用了 material.stock，
# 若不加豁免必然误报——这正是豁免存在的理由。
UTILS = os.path.join(ROOT, 'app', 'utils.py')
utils_src = read(UTILS) if os.path.exists(UTILS) else ''
check('T6c utils.py 确实含裸用（故豁免必要）',
      'normalize_stock_quantity(material.stock or 0)' in utils_src)

print('\n=== T7 INVENTORY_TRUTH.md 内容契约 ===')
check('T7a 文档存在', bool(truth_src))
check('T7b 覆盖三份数据', all(k in truth_src for k in [
    'material.stock', 'location_inventory.quantity', 'stock_transaction.quantity']))
check('T7c 写明恒等式', '① = Σ(② 按物料汇总) = Σ(③ 按物料汇总)' in truth_src)
check('T7d 写明派生方向', '③ → ② → ①' in truth_src)
check('T7e 写明禁止方向', '① → ②' in truth_src and '❌' in truth_src)
check('T7f 写明不猜铁律', '不猜' in truth_src and 'NULL' in truth_src)
check('T7g 写明 warehouse_id 是唯一判据', 'warehouse_id` 是唯一判据' in truth_src)
check('T7h 写明单仓短路是定时炸弹', '定时炸弹' in truth_src)
check('T7i 收录四个消费点复发编号',
      all(k in truth_src for k in ['09-02-001', '09-03-001', '09-03-002', '09-03-004']))
check('T7j 有写入入口清单', 'add_stock' in truth_src and 'deduct_stock_atomic' in truth_src)
check('T7k 提示 add_stock 不自动同步库位账',
      '不会自动同步库位账' in truth_src)
check('T7l 有改动自检清单', truth_src.count('- [ ]') >= 8)

print('\n=== T8 交叉引用 ===')
check('T8a 引用 AGENTS.md', 'AGENTS.md' in truth_src)
check('T8b 引用 WMS_BUSINESS_SCOPE.md', 'WMS_BUSINESS_SCOPE.md' in truth_src)
check('T8c 引用 WMS_BUG_BASELINE.md', 'WMS_BUG_BASELINE.md' in truth_src)

print('\n=== T9 收口函数未被架空 ===')
check('T9a 存在 get_warehouse_stock_quantities',
      'def get_warehouse_stock_quantities(warehouse):' in app_src)
check('T9b 文档写明"绝不回退全局"', '绝不回退全局' in app_src)
check('T9c 仍保留单仓兜底分支', 'if Warehouse.query.count() == 1:' in app_src)
check('T9d 仍保留 _material_stock_unattributed 兜底',
      'def _material_stock_unattributed(material_id):' in app_src)

print('\n=== T11 A11 分类器实跑行为（强于字符串匹配）===')
# 直接 import 规则类，用真实代码片段验证判定结果。
# 这是本测试最有价值的部分：证明规则不是"哑规则"。
import importlib.util

_spec = importlib.util.spec_from_file_location('_lint_rules', LINT)
_lint = importlib.util.module_from_spec(_spec)
try:
    _spec.loader.exec_module(_lint)
    _rule = _lint.RuleA11NoRawGlobalStockCheck()
    _loaded = True
except Exception as exc:  # noqa: BLE001
    _loaded = False
    _load_err = str(exc)

check('T11a 规则模块可导入', _loaded, '' if _loaded else str(_load_err) if not _loaded else '')

if _loaded:
    def _judge(code):
        st = _lint.strip_py_comments(code)
        m = _rule._STOCK_REF.search(st)
        if not m:
            return None
        ls = st.rfind('\n', 0, m.start()) + 1
        return _rule._is_check_context(st, m.start(), ls)

    positives = [
        ('直接小于比较', '            if material.stock < quantity:'),
        ('大于等于比较', '            if item.material.stock >= qty:'),
        ('is_stock_sufficient 传总账',
         '    if not is_stock_sufficient(material.stock or 0, quantity):'),
        ('间接：赋值后隔行比较',
         '            current = material.stock or 0\n            if current < quantity:\n                return x'),
        ('间接：存量真实写法',
         '            cs = normalize_stock_quantity(material.stock or 0)\n'
         '            if not is_stock_sufficient(cs, quantity):\n                pass'),
    ]
    negatives = [
        ('展示序列化', "                'stock': material.stock or 0,"),
        ('f-string 报表', "        f'- 库存 {m.stock:.0f}'"),
        ('纯赋值无后续比较',
         '            current = material.stock or 0\n            return current'),
    ]
    for desc, code in positives:
        check(f'T11 抓违规：{desc}', _judge(code) is True)
    for desc, code in negatives:
        check(f'T11 放展示：{desc}', _judge(code) is False)

print('\n=== T10 存量仓库实跑 A11 必须 0 违规 ===')
env = dict(os.environ)
env['PYENV_VERSION'] = '3.11.1'
try:
    proc = subprocess.run(
        [sys.executable, LINT, '--rule', 'a11'],
        cwd=ROOT, capture_output=True, text=True, env=env, timeout=180,
    )
    out = (proc.stdout or '') + (proc.stderr or '')
    check('T10a A11 退出码 0（存量不误报）', proc.returncode == 0,
          f'rc={proc.returncode} out={out[-300:]}')
    check('T10b 输出 0 处违规', '总计 0 处违规' in out, out[-200:])
except (OSError, subprocess.SubprocessError) as exc:
    check('T10a A11 退出码 0（存量不误报）', False, str(exc))
    check('T10b 输出 0 处违规', False, str(exc))

print('\n' + '=' * 60)
print(f'通过 {len(PASSED)} / 失败 {len(FAILED)}')
if FAILED:
    print('失败项：')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
print('P1-a 库存读取收口契约全部通过')
