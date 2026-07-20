"""AI-BUG-F04: 基础设施修复验证
# AI_TASK: AI-BUG-F04

验证 E5/E6/E7/E8/E9 修复点：
- E5: restart.py WMS_ALLOW_AUTO_SECRET_KEY 不再无条件设置，仅在未显式配置时默认开启并打印警告
- E6: restart.py 端口与登录路径不再硬编码，提取为常量+环境变量 WMS_PORT / WMS_LOGIN_PATH
- E7: .githooks/pre-push 不再允许删除远程 main 分支，任何分支删除均被阻止
- E8: .github/workflows/verify.yml push 触发分支仅 main，移除 feature/* 和 ai/*
- E9: app.py backup_page 排序键支持 None 字段，避免 datetime/int/str 混合比较抛 TypeError

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def main() -> int:
    failures: list[str] = []

    # ── E5 + E6: restart.py ──
    restart = read(ROOT / 'app' / 'restart.py')

    # E5: 不再无条件 env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"
    # 旧形式（顶层无条件赋值，缩进 4 空格）：env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1"
    # 修复后必须包裹在条件块内（缩进 ≥8 空格）。
    if re.search(r'^    env\["WMS_ALLOW_AUTO_SECRET_KEY"\]\s*=\s*"1"\s*$', restart, re.MULTILINE):
        failures.append('E5: restart.py 仍存在无条件 env["WMS_ALLOW_AUTO_SECRET_KEY"] = "1" 赋值（顶层 4 空格缩进）')

    # E5: 必须仅在未显式配置时才默认开启（条件判断）
    if 'WMS_ALLOW_AUTO_SECRET_KEY' not in restart or 'not in env' not in restart:
        failures.append('E5: restart.py 缺少 WMS_ALLOW_AUTO_SECRET_KEY 未显式配置的条件判断')

    # E6: 端口必须可由环境变量覆盖，不得再硬编码 http://127.0.0.1:8080
    if 'WMS_PORT' not in restart:
        failures.append('E6: restart.py 缺少 WMS_PORT 环境变量配置')
    if 'WMS_LOGIN_PATH' not in restart:
        failures.append('E6: restart.py 缺少 WMS_LOGIN_PATH 环境变量配置')
    # 旧硬编码 URL 不应再出现（除常量默认值外）
    if re.search(r'"http://127\.0\.0\.1:8080', restart):
        failures.append('E6: restart.py 仍存在硬编码 http://127.0.0.1:8080 URL')

    # ── E7: .githooks/pre-push ──
    prepush = read(ROOT / '.githooks' / 'pre-push')

    # 不应再出现 "Allow deleting main" 注释或对应 continue 分支
    if 'Allow deleting main' in prepush:
        failures.append('E7: pre-push 仍存在 "Allow deleting main" 注释')
    # 必须包含禁止删除远程分支的逻辑
    if 'deleting remote branch' not in prepush:
        failures.append('E7: pre-push 缺少禁止删除远程分支的逻辑')
    # 必须检测 remote_sha 全 0 表示删除
    if '0000000000000000000000000000000000000000' not in prepush:
        failures.append('E7: pre-push 缺少 remote_sha 全 0 删除检测')

    # ── E8: .github/workflows/verify.yml ──
    yml = read(ROOT / '.github' / 'workflows' / 'verify.yml')
    # push 触发分支应仅 main
    push_match = re.search(r'push:\s*\n\s*branches:\s*\[([^\]]+)\]', yml)
    if not push_match:
        failures.append('E8: verify.yml 无法定位 push.branches 配置')
    else:
        branches = [b.strip().strip("'\"") for b in push_match.group(1).split(',')]
        if branches != ['main']:
            failures.append(f'E8: verify.yml push.branches 必须仅 [main]，实际为 {branches}')
    # 不应再触发 feature/* 或 ai/*
    if 'feature/*' in yml or "'ai/*'" in yml or '"ai/*"' in yml:
        failures.append('E8: verify.yml 仍包含 feature/* 或 ai/* 触发分支')

    # ── E9: app.py backup_page 排序键 ──
    app_py = read(ROOT / 'app' / 'app.py')
    # 必须包含 None 字段类型一致默认值
    if '_SORT_DEFAULTS' not in app_py or '_backup_sort_key' not in app_py:
        failures.append('E9: app.py backup_page 缺少 _SORT_DEFAULTS / _backup_sort_key 防御性排序键')
    # 旧形式 `item.get(sort_by) or ''` 不应再出现
    if re.search(r'backups\.sort\([^)]*item\.get\(sort_by\)\s*or\s*\'\'', app_py):
        failures.append('E9: app.py backup_page 仍使用 item.get(sort_by) or \'\' 排序键')

    if failures:
        print('FAIL INFRA-FIXES:')
        for f in failures:
            print('  - ' + f)
        return 1

    print(
        'PASS INFRA-FIXES: E5 restart.py SECRET_KEY 条件设置 + E6 端口/路径环境变量化 + '
        'E7 pre-push 禁止删除任何远程分支 + E8 verify.yml 仅 main 触发 + '
        'E9 backup_page 排序键 None 防御'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
