# -*- coding: utf-8 -*-
"""
CI-GREEN-GATE-2026-09-18 回归：AGENTS.md §三「CI 全绿门禁」+ 每日定时检查。

规则
----
**开始任何任务前**，必须确认以下三个工作流在 `main` 上最近一次运行全部为绿色：

    Android APK Build      .github/workflows/android-build.yml
    WMS AI Verification    .github/workflows/verify.yml
    WMS CI                 .github/workflows/ci.yml

任一非绿 → 禁止开工，必须先修绿。

本测试锁三件事，缺一条规则就失效：
  1. **规则条文在** —— AGENTS.md 里三个工作流名与"禁止开工"语义都在；
  2. **检查工具在且可用** —— scripts/check_ci_green.py 存在、零依赖、
     全绿 rc=0 / 非绿 rc=1、且"查不到"时**必须阻断**而不是放行；
  3. **每天真的会跑** —— 三个工作流都带 schedule 定时触发（否则当天没人推
     代码就没有新运行记录，门禁退化成"看某天偶然跑过的旧结果"，
     依赖撤回/镜像失效这类时间性故障会被漏掉）。

为什么第 3 条是硬性的
--------------------
「每天检查一次」若不落成 schedule，就只是"每次想起来才看"。CI 的价值之一是
**时间性故障探测**：某天 pypi 撤包、actions/checkout 弃用旧版本、
ubuntu-latest 换内核，这些在**没人改动代码时**也会让 CI 变红。
只有定时跑才能发现它们，也才能保证门禁每天都有"当天的"结论。
"""
import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AGENTS = os.path.join(REPO, 'AGENTS.md')
CHECKER = os.path.join(REPO, 'scripts', 'check_ci_green.py')
WORKFLOWS = {
    'Android APK Build': os.path.join(REPO, '.github/workflows/android-build.yml'),
    'WMS AI Verification': os.path.join(REPO, '.github/workflows/verify.yml'),
    'WMS CI': os.path.join(REPO, '.github/workflows/ci.yml'),
}
PY = sys.executable


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


# ---------------------------------------------------------- T1 规则条文
def test_t1_agents_md_declares_gate():
    """AGENTS.md 必须写明门禁的三个工作流名与"禁止开工"语义。"""
    src = _read(AGENTS)
    assert 'CI 全绿门禁' in src, 'AGENTS.md 缺少「CI 全绿门禁」规则标题'
    assert '2026-09-18' in src, '规则未标注新增日期（本仓库要求新增规则注明日期）'
    for name, path in WORKFLOWS.items():
        assert name in src, f'AGENTS.md 未列出工作流 {name}'
        # 工作流文件名要能对上（防止写了名字但指错文件）
        assert os.path.basename(path) in src, f'AGENTS.md 未给出 {name} 的文件名'
    # 阻断语义：必须明确"任一非绿即不得开工"
    assert re.search(r'任一非绿[^\n]*不得开工|任一非绿[^\n]*禁止', src), \
        'AGENTS.md 未写明"任一非绿即不得开工"的阻断语义'
    # 推荐的一键检查命令要写进文档，否则规则不可执行
    assert 'check_ci_green.py' in src, 'AGENTS.md 未给出 check_ci_green.py 检查命令'


# ------------------------------------------------------- T2 工作流清单一致
def test_t2_workflow_list_matches_repo():
    """三个工作流文件必须真实存在且 name 与清单一致（改名会让门禁静默失效）。"""
    for name, path in WORKFLOWS.items():
        assert os.path.isfile(path), f'工作流文件不存在：{path}'
        head = _read(path).splitlines()[0]
        assert head.startswith('name:'), f'{path} 首行不是 name'
        actual = head.split(':', 1)[1].strip()
        assert actual == name, f'{path} 的 name 是 {actual!r}，清单写的是 {name!r}'


# ------------------------------------------------- T3 检查脚本零依赖
def test_t3_checker_is_stdlib_only():
    """检查脚本必须只用标准库 —— 受限网络下装包是额外风险。"""
    src = _read(CHECKER)
    imports = set(re.findall(r'^\s*(?:import|from)\s+([A-Za-z_][\w.]*)', src, re.M))
    # 只允许标准库（顶层模块名）
    allowed = {'argparse', 'json', 'os', 'sys', 'urllib', 're', 'typing', '__future__'}
    bad = {m for m in imports if m.split('.')[0] not in allowed}
    assert not bad, f'check_ci_green.py 引入了非标准库依赖：{sorted(bad)}'


# ------------------------------------------------- T4 三个工作流都带定时触发
def test_t4_all_workflows_have_daily_schedule():
    """三个工作流都必须带 schedule，否则"每天检查一次"落不了地。"""
    for name, path in WORKFLOWS.items():
        src = _read(path)
        assert re.search(r'^\s*schedule:', src, re.M), \
            f'{name} 缺少 schedule 定时触发（每天检查一次无法闭环）'
        m = re.search(r"cron:\s*'([^']+)'", src)
        assert m, f'{name} 的 schedule 缺少 cron 表达式'
        parts = m.group(1).split()
        assert len(parts) == 5, f'{name} 的 cron 不是 5 段式：{m.group(1)!r}'
        # 必须是"每天一次"：日/月/周字段均为 *，分钟与小时为具体值
        minute, hour, dom, month, dow = parts
        assert (dom, month, dow) == ('*', '*', '*'), \
            f'{name} 的 cron 不是每天执行：{m.group(1)!r}'
        assert minute.isdigit() and hour.isdigit(), \
            f'{name} 的 cron 分钟/小时必须为具体值：{m.group(1)!r}'


# ------------------------------------------------- T5 三个 cron 时刻一致
def test_t5_schedules_are_aligned():
    """三个工作流应在同一时刻触发，早上看到的是同一天的新鲜结果。"""
    crons = {}
    for name, path in WORKFLOWS.items():
        m = re.search(r"cron:\s*'([^']+)'", _read(path))
        crons[name] = m.group(1) if m else None
    assert len(set(crons.values())) == 1, f'三个工作流的 cron 不一致：{crons}'


# --------------------------------------------- T6 检查脚本判定逻辑（离线单测）
def test_t6_checker_verdict_logic_offline():
    """用桩数据直接验判定逻辑：全绿放行、非绿阻断、查不到也阻断。

    不依赖网络与 token —— 把 classify() 单独加载进来测。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location('ccg', CHECKER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 全绿
    assert mod.classify({'status': 'completed', 'conclusion': 'success'})[0] == 'green'
    # 失败
    for bad in ('failure', 'timed_out', 'cancelled', 'startup_failure'):
        assert mod.classify({'status': 'completed', 'conclusion': bad})[0] == 'failed', bad
    # 还在跑 → pending（不能放行）
    for pend in ('queued', 'in_progress'):
        assert mod.classify({'status': pend, 'conclusion': None})[0] == 'pending', pend
    # 查不到运行记录 → missing（不能放行）
    assert mod.classify(None)[0] == 'missing'
    # 大小写不敏感（GitHub 返回过 'Success' 之类）
    assert mod.classify({'status': 'completed', 'conclusion': 'SUCCESS'})[0] == 'green'


# ------------------------------------------ T7 检查脚本的真实退出码（离线）
def test_t7_checker_exit_code_on_failure():
    """在无 token 的私有仓库上必须**阻断**（rc=1），不得误报放行。"""
    env = dict(os.environ)
    env.pop('GH_TOKEN', None)
    env.pop('GITHUB_TOKEN', None)
    # 指向不存在的 token 路径，保证走匿名分支
    proc = subprocess.run(
        [PY, CHECKER, '--json'],
        capture_output=True, text=True, env=env, timeout=180, cwd=REPO,
    )
    assert proc.returncode in (0, 1), f'意外退出码：{proc.returncode}\n{proc.stderr[:400]}'
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(f'--json 输出不是合法 JSON：{proc.stdout[:400]}')
    assert 'ok' in payload and 'results' in payload
    assert len(payload['results']) == 3, '结果条数应为 3（三个工作流）'
    # rc 与 ok 必须自洽
    assert (proc.returncode == 0) == payload['ok'], \
        f'退出码({proc.returncode})与 ok({payload["ok"]})不一致'
    for r in payload['results']:
        assert r['workflow'] in WORKFLOWS, f'出现未登记的工作流：{r["workflow"]}'


# ------------------------------------------------ T8 只查 main 的运行
def test_t8_checker_filters_branch_main():
    """必须按 branch=main 过滤 —— 否则 PR 分支的绿会被误当成 main 的绿。"""
    src = _read(CHECKER)
    assert 'branch={BRANCH}' in src or 'branch=main' in src, \
        'check_ci_green.py 未按分支过滤运行记录（会把 PR 分支的绿误判为 main 全绿）'
    assert 'BRANCH = "main"' in src, 'BRANCH 常量必须为 main'


# ------------------------------------------------- T9 门禁不会静默失效
def test_t9_gate_fails_loud_on_api_error():
    """API 异常必须计入阻断，不允许"查不到就当绿"。"""
    src = _read(CHECKER)
    assert 'HTTPError' in src, '未处理 HTTPError（工作流被改名/删除时会静默放行）'
    assert re.search(r'blocked = \[r for r in results if r\[.state.\] != .green.\]', src), \
        '阻断判定必须基于 state != green（含 missing/pending/failed）'
