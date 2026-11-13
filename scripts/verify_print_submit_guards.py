# -*- coding: utf-8 -*-
"""静态形态锁：2026-11-13「发送打印」防误操作 / 防重复出纸三处修复。

纯文本读取，不导入 WMS 应用模块、不连接数据库、不访问现役服务。
供本地离线验证与 tests/test_print_submit_guards_20261113.py 共用；
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
STATION_HTML = 'app/templates/print_station.html'


def _read(root: Path, relative: str) -> str:
    path = root / relative
    return path.read_text(encoding='utf-8') if path.is_file() else ''


def collect_checks(root: Path) -> list[tuple[str, bool, str]]:
    """Return (name, passed, detail) triples; every check is a regression lock."""
    checks: list[tuple[str, bool, str]] = []

    def add(name: str, passed: bool, detail: str = '') -> None:
        checks.append((name, bool(passed), detail))

    app = _read(root, APP_JS)
    material = _read(root, MATERIAL_JS)
    station = _read(root, STATION_HTML)

    # --- 统一客户端层的重复提交锁 ---
    add('C01 guard installed once',
        'api.post.__wmsPrintJobDuplicateGuard' in app
        and 'postWithPrintJobGuard.__wmsPrintJobDuplicateGuard = true' in app,
        '防重复安装标记 + 安装标记')
    add('C02 api.post wrapped',
        'var originalPost = api.post;' in app and 'api.post = postWithPrintJobGuard;' in app,
        '保留原函数并替换 WMS.api.post')
    add('C03 only print job submit path',
        "PRINT_JOB_SUBMIT_PATH = '/print_queue/jobs'" in app
        and 'isPrintJobSubmitPath(url)' in app
        and "trimText(url).split('?')[0] === PRINT_JOB_SUBMIT_PATH" in app,
        '精确路径匹配且剥离查询串')
    add('C04 5 second window',
        'PRINT_JOB_DUPLICATE_WINDOW_MS = 5000;' in app,
        '5 秒窗口常量')
    add('C05 original post preserved for other paths',
        app.count('originalPost.call(api, url, data, options)') >= 3,
        '非目标路径 / 无指纹 / 正常提交均透传')
    add('C06 fingerprint job_type + target_id + target_ids',
        'function buildPrintJobSubmitKey(data)' in app
        and 'trimText(data.job_type)' in app
        and "'id=' + trimText(data.target_id)" in app
        and "normalizePrintJobTargetIds(data.target_ids)" in app
        and "return jobType + '|' + targets.join('&');" in app,
        '两种载荷形态都覆盖')
    add('C07 target_ids normalized',
        'function normalizePrintJobTargetIds(value)' in app
        and "seen['#' + text]" in app
        and 'ids.sort(' in app
        and "return ids.join(',');" in app,
        '去空 / 去重 / 排序后拼接')
    add('C08 lock acquired with timer',
        'function acquirePrintJobKey(key)' in app
        and 'setTimeout(' in app
        and '}, PRINT_JOB_DUPLICATE_WINDOW_MS);' in app,
        '窗口到期自动释放')
    add('C09 lock released explicitly',
        'function releasePrintJobKey(key)' in app
        and 'clearTimeout(timerId)' in app
        and 'delete lockedPrintJobKeys[key]' in app,
        '显式解锁')
    add('C10 duplicate short-circuits request',
        re.search(r"return Promise\.resolve\(\{\s*status: 'success',\s*duplicate: true,",
                  app) is not None
        and '已发送，请勿重复点击' in app
        and 'if (!acquirePrintJobKey(key))' in app,
        '重复点击不再发第二次请求')
    add('C11 sync throw releases lock',
        re.search(r'catch \(error\) \{\s*releasePrintJobKey\(key\);\s*throw error;', app) is not None,
        '同步异常立即解锁')
    add('C12 rejection releases lock',
        re.search(r'\}\s*, function\(error\) \{\s*releasePrintJobKey\(key\);\s*throw error;',
                  app) is not None,
        '请求失败立即解锁，允许重试')
    add('C13 success keeps window lock',
        re.search(r'return request\.then\(function\(result\) \{\s*return result;\s*\}, function\(error\)',
                  app) is not None,
        '成功不提前解锁，窗口内仍防双击')
    add('C14 non-promise response releases lock',
        re.search(r"typeof request\.then !== 'function'\) \{\s*releasePrintJobKey\(key\);",
                  app) is not None,
        '非 Promise 返回不残留锁')

    # --- 空选反馈 ---
    send = re.search(r'function sendLabelsToPrintStation\(\) \{(.*?)\n\}', material, re.S)
    body = send.group(1) if send else ''
    add('C15 empty selection warns',
        "showToast('请先勾选要打印的物料', 'warning');" in body,
        '空选给中文 warning 提示')
    add('C16 empty selection returns',
        re.search(r"if \(!ids\.length\) \{\s*//[^\n]*\n\s*showToast\([^\n]+\);\s*return;\s*\}",
                  body) is not None,
        '仍立即 return，不发请求')
    add('C17 submit still uses WMS.api.post',
        "WMS.api.post('/print_queue/jobs'" in body,
        '未改走原生 fetch')

    # --- 打印工作站待确认提醒 ---
    add('C18 hint element hidden by default',
        'id="printConfirmHint" hidden' in station,
        '默认不显示')
    add('C19 hint text explains re-print risk',
        '5 分钟后会被系统重新认领并再次打印' in station,
        '说明不确认的后果')
    add('C20 hint element resolved',
        "var confirmHint = document.getElementById('printConfirmHint');" in station,
        '拿到 DOM 引用')
    add('C21 hint shown on job claim',
        re.search(r'function handleJob\(job\) \{[^}]*?confirmHint\.hidden = false;', station, re.S)
        is not None,
        '认领任务后显示')
    add('C22 hint hidden after settle',
        'confirmHint.hidden = true;' in station,
        '结果保存后撤销提醒')
    add('C23 independent template does not load app.js',
        'app.js' not in station,
        '避免 complete/fail 上报被同一守卫误拦')
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
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    if not args.json:
        for name, ok, detail in checks:
            sys.stdout.write(('  OK  ' if ok else ' FAIL ') + name + (' - ' + detail if detail else '') + '\n')
    return 0 if payload['success'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
