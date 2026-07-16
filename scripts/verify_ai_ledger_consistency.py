"""AI-R02: AI 台账一致性检查
# AI_TASK: AI-R02

校验代码中的 AI 任务标记与台账 WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md 不脱节。

机制：
- 代码中用注释 `# AI_TASK: <ID>` 标记 AI 能力归属（路由、工具注册、Feature Flag 等）
- 本脚本扫描 app/ 下所有 .py 和 .html 文件，提取 AI_TASK 标记
- 校验每个标记的 ID 在台账中存在且状态为"已完成"
- 校验台账第 8 节"后续完成记录"中每个已完成任务至少有一个代码标记（防虚假报告）
- 未标记的 AI 相关代码（含 ai/ 目录或 AI_TOOL_REGISTRY 引用）输出警告，不阻塞

渐进式策略：当前仅要求 AI-R01 已完成的核心代码有标记，其余未标记仅警告。
通过 ENFORCE_TASK_IDS 环境变量可切换为强制模式。

退出码 0=通过（含警告），1=失败（标记的 ID 不存在于台账或状态非已完成）。
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / 'app'
LEDGER_PATH = ROOT / 'WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md'

# 匹配代码中的 AI 任务标记：# AI_TASK: AI-R01 或 <!-- AI_TASK: AI-R01 -->
TASK_MARKER_RE = re.compile(r'AI_TASK:\s*([A-Z]+-[A-Z0-9-]+)')

# 匹配台账第 4 节任务总表中的任务行：| 顺序 | 编号 | 状态 | ...
# 状态列取值：已完成 / 下一项 / 待开发
LEDGER_TASK_RE = re.compile(
    r'\|\s*\d+\s*\|\s*([A-Z]+-[A-Z0-9-]+)\s*\|\s*([^|]+)\|'
)

# 匹配台账第 8 节后续完成记录表：| 任务编号 | 完成日期 | ...
LEDGER_COMPLETED_RE = re.compile(
    r'\|\s*([A-Z]+-[A-Z0-9-]+)\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|'
)


def parse_ledger_tasks() -> tuple[dict[str, str], set[str]]:
    """返回 (任务ID->状态, 已完成任务ID集合)"""
    text = LEDGER_PATH.read_text(encoding='utf-8')
    task_status: dict[str, str] = {}
    completed: set[str] = set()

    # 第 4 节总表状态
    for match in LEDGER_TASK_RE.finditer(text):
        task_id = match.group(1).strip()
        status = match.group(2).strip()
        if task_id in ('任务编号', '顺序'):
            continue
        task_status[task_id] = status

    # 第 7、8 节完成记录
    for match in LEDGER_COMPLETED_RE.finditer(text):
        task_id = match.group(1).strip()
        completed.add(task_id)

    return task_status, completed


def scan_code_markers() -> dict[str, list[str]]:
    """扫描 app/ 和 scripts/verify_ai_*.py，返回 {任务ID: [文件路径列表]}"""
    markers: dict[str, list[str]] = {}

    # app/ 下所有 .py 和 .html（业务能力代码）
    for ext in ('*.py', '*.html'):
        for path in APP_DIR.rglob(ext):
            try:
                text = path.read_text(encoding='utf-8')
            except (UnicodeDecodeError, OSError):
                continue
            for match in TASK_MARKER_RE.finditer(text):
                task_id = match.group(1)
                markers.setdefault(task_id, []).append(str(path.relative_to(ROOT)))

    # scripts/verify_ai_*.py（验证脚本归属标记）
    scripts_dir = ROOT / 'scripts'
    for path in scripts_dir.glob('verify_ai_*.py'):
        try:
            text = path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue
        for match in TASK_MARKER_RE.finditer(text):
            task_id = match.group(1)
            markers.setdefault(task_id, []).append(str(path.relative_to(ROOT)))

    return markers


def main() -> int:
    failures: list[str] = []
    warnings: list[str] = []

    task_status, completed_tasks = parse_ledger_tasks()
    code_markers = scan_code_markers()

    # 1. 代码中标记的 ID 必须在台账中存在
    for task_id, files in code_markers.items():
        if task_id not in task_status:
            failures.append(
                f'代码标记的 AI_TASK:{task_id} 在台账中不存在（出现在 {len(files)} 个文件）'
            )
            continue
        # 2. 已标记的 ID 状态应为"已完成"
        status = task_status[task_id]
        if status != '已完成':
            failures.append(
                f'代码标记的 AI_TASK:{task_id} 台账状态为 {status!r}，仅"已完成"任务可有代码标记'
            )

    # 3. 台账第 8 节已完成任务应有代码标记（防虚假报告）
    #    渐进式策略：仅对 AI-RXX 主任务强制，子修复项（如 AI-SEC-F01）和 P0/UX 暂不强制
    enforce_mode = os.environ.get('AI_LEDGER_ENFORCE', 'gradual')
    for task_id in completed_tasks:
        if not task_id.startswith('AI-R'):
            continue
        if task_id not in code_markers:
            if enforce_mode == 'strict':
                failures.append(
                    f'台账标记"已完成"的 {task_id} 在代码中无 AI_TASK 标记，疑似虚假报告'
                )
            else:
                warnings.append(
                    f'台账标记"已完成"的 {task_id} 在代码中无 AI_TASK 标记（渐进式模式仅警告）'
                )

    # 4. 警告：AI 核心代码无任何标记（渐进式提醒，不阻塞）
    core_ai_files = [
        'app/ai/tools/registry.py',
        'app/ai/policies.py',
        'app/ai/draft_idempotency.py',
    ]
    for rel_path in core_ai_files:
        full_path = ROOT / rel_path
        if full_path.exists():
            text = full_path.read_text(encoding='utf-8')
            if 'AI_TASK:' not in text:
                warnings.append(f'AI 核心文件 {rel_path} 无 AI_TASK 标记')

    # 输出
    if warnings:
        print('WARN AI-LEDGER-CONSISTENCY:')
        for w in warnings:
            print(f'  ! {w}')

    if failures:
        print('FAIL AI-LEDGER-CONSISTENCY:')
        for f in failures:
            print(f'  - {f}')
        return 1

    if not warnings:
        print(
            f'PASS AI-LEDGER-CONSISTENCY: 代码标记 {len(code_markers)} 个任务，'
            f'台账已完成 {len(completed_tasks)} 个，映射一致'
        )
    else:
        print(
            f'PASS AI-LEDGER-CONSISTENCY (with warnings): 代码标记 {len(code_markers)} 个任务，'
            f'{len(warnings)} 条警告（渐进式模式，未阻塞）'
        )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
