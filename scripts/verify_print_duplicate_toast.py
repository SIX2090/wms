# -*- coding: utf-8 -*-
"""静态形态锁：2026-11-13「重复点击」提示由绿色改为黄色（BUG-2026-11-13-002）。

三处提交入口（物料列表 / 入库单详情 / 出库单详情）在收到
``res.duplicate === true`` 时必须用 warning 色提示，正常提交仍保持 success 色。
纯文本读取，不导入 WMS 应用模块、不连接数据库、不访问现役服务。
--root 可指向导出旧版本文件的临时目录，用于 R8 回退等价验证。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

APP_JS = 'app/static/js/app.js'
MATERIAL_JS = 'app/static/js/pages/material-list.js'
IN_DETAIL = 'app/templates/in_order_detail.html'
OUT_DETAIL = 'app/templates/out_order_detail.html'
MOBILE_SCAN = 'app/templates/mobile_scan.html'

CALL_SITES = {
    MATERIAL_JS: '已发送标签到打印工作站',
    IN_DETAIL: '已发送到打印工作站',
    OUT_DETAIL: '已发送到打印工作站',
}
NEW_BRANCH = "(res && res.duplicate) ? 'warning' : 'success'"


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding='utf-8') if path.is_file() else ''


def collect_checks(root: Path) -> list[tuple[str, bool, str]]:
    """Return (name, passed, detail) triples; every check is a regression lock."""
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, passed: bool, detail: str = '') -> None:
        checks.append((name, bool(passed), detail))

    sources = {path: _read(root, path) for path in CALL_SITES}
    app = _read(root, APP_JS)
    mobile = _read(root, MOBILE_SCAN)

    # --- 三处入口：duplicate 提示改黄色，正常提交保持绿色 ---
    add('C01 all three call sites present',
        all(text for text in sources.values()),
        '物料列表 / 入库单详情 / 出库单详情三份源码均可读')
    add('C02 submit path unchanged',
        all("WMS.api.post('/print_queue/jobs'" in text for text in sources.values()),
        '仍走统一包装的 WMS.api.post，未改原生 fetch')

    for path, fallback in CALL_SITES.items():
        text = sources[path]
        tag = path.rsplit('/', 1)[-1]
        pattern = re.compile(
            r"showToast\(res\.msg \|\| '" + re.escape(fallback) + r"',\s*"
            + re.escape(NEW_BRANCH) + r"\);")
        add('C03 ' + tag + ' warning on duplicate',
            pattern.search(text) is not None,
            'duplicate 时用 warning 色；正常提交仍是 success 色')
        add('C04 ' + tag + ' exactly one guarded toast',
            text.count(NEW_BRANCH) == 1,
            '恰好一处，未误改其它成功提示')
        add('C05 ' + tag + ' old green toast removed',
            re.search(r"showToast\(res\.msg \|\| '" + re.escape(fallback)
                      + r"',\s*'success'\);", text) is None,
            '不存在旧的恒定绿色写法')
        add('C06 ' + tag + ' no blanket warning',
            re.search(r"showToast\(res\.msg[^\n]*,\s*'warning'\);", text) is None,
            '没有把「所有成功」一律改成黄色')
        add('C07 ' + tag + ' failure still danger',
            re.search(r"\.catch\(function\(err\) \{\s*showToast\('发送打印任务失败[^\n]*'danger'\)",
                      text) is not None,
            '请求失败仍为 danger，不受本次改动影响')

    # --- 去重逻辑本体未被触碰（本批只改展示层）---
    add('C08 duplicate response contract unchanged',
        re.search(r"return Promise\.resolve\(\{\s*status: 'success',\s*duplicate: true,",
                  app) is not None
        and '已发送，请勿重复点击' in app,
        'app.js 仍返回 status=success / duplicate=true 与原文案')
    add('C09 five second window unchanged',
        'PRINT_JOB_DUPLICATE_WINDOW_MS = 5000;' in app,
        '5 秒窗口常量未变')
    add('C10 guard still installed once',
        'api.post.__wmsPrintJobDuplicateGuard' in app,
        '统一包装层仍在，三处入口共享同一把锁')
    add('C11 mobile_scan postRaw untouched',
        "WMS.api.postRaw('/print_queue/jobs'" in mobile
        and NEW_BRANCH not in mobile,
        '第 4 处提交点自带 disabled 防护，不属本批范围')
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]),
                        help='仓库根目录（R8 回退验证时指向导出旧版本的临时目录）')
    parser.add_argument('--json', action='store_true', help='仅输出 JSON')
    args = parser.parse_args()

    checks = collect_checks(Path(args.root))
    passed = sum(1 for _, ok, _ in checks if ok)
    payload = {
        'root': str(Path(args.root)),
        'passed': passed,
        'total': len(checks),
        'success': passed == len(checks),
        'failed': [{'check': name, 'detail': detail} for name, ok, detail in checks if not ok],
    }
    if not args.json:
        for name, ok, detail in checks:
            sys.stdout.write(('  OK  ' if ok else ' FAIL ') + name
                             + (' - ' + detail if detail else '') + '\n')
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return 0 if payload['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
