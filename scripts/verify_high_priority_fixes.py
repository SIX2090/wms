#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI-BUG-F05: 剩余高优 bug 修复验证脚本。

覆盖 7 个修复点：
- F1: app/ai/v2_routes.py _get_llm_config 与 query 参数 int() 未防御非数字字符串
- F2: app/ai/tools/inventory.py ilike 未转义 LIKE 通配符
- F3: app/ai/agents/draft_check.py 使用 datetime 但未 import
- F4: app/notifications.py SMTP 无超时
- F5: app/wechat_helper.py /send 端点无认证
- F6: app/utils.py save_upload_image 仅校验扩展名
- F7: app/static/js/excel-table.js destroy() 未移除事件监听器
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel: Path) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')


def main() -> int:
    failures: list[str] = []

    # ── F1: v2_routes.py ──
    v2 = read(Path('app/ai/v2_routes.py'))
    if 'def _safe_int(' not in v2:
        failures.append('F1: v2_routes.py 缺少 _safe_int 辅助函数定义')
    # _get_llm_config 必须走 _safe_int，不再有裸 int(_get(...))
    if re.search(r"timeout_seconds=int\(_get\(['\"]ai_llm_timeout", v2):
        failures.append('F1: v2_routes.py _get_llm_config 仍存在裸 int(_get("ai_llm_timeout"...)) 调用')
    if re.search(r"max_tokens=int\(_get\(['\"]ai_llm_max_tokens", v2):
        failures.append('F1: v2_routes.py _get_llm_config 仍存在裸 int(_get("ai_llm_max_tokens"...)) 调用')
    if 'timeout_seconds=_safe_int(' not in v2:
        failures.append('F1: v2_routes.py timeout_seconds 未走 _safe_int')
    if 'max_tokens=_safe_int(' not in v2:
        failures.append('F1: v2_routes.py max_tokens 未走 _safe_int')
    # query 参数 limit/days 必须走 _safe_int，不再有 min(int(request.args.get(...)))
    if re.search(r"min\(int\(request\.args\.get\(", v2):
        failures.append('F1: v2_routes.py 仍存在 min(int(request.args.get(...))) 形式的 query 参数解析')
    if 'limit = _safe_int(request.args.get' not in v2:
        failures.append('F1: v2_routes.py query 参数 limit 未走 _safe_int')
    if 'days = _safe_int(request.args.get' not in v2:
        failures.append('F1: v2_routes.py query 参数 days 未走 _safe_int')

    # ── F2: tools/inventory.py ──
    inv = read(Path('app/ai/tools/inventory.py'))
    if 'def _escape_like_pattern(' not in inv:
        failures.append('F2: tools/inventory.py 缺少 _escape_like_pattern 函数定义')
    # material_query 必须使用 escape='\\' 且不再有裸 ilike(f'%{keyword}%')
    if re.search(r"Material\.code\.ilike\(f['\"]%\{keyword\}%['\"]\)", inv):
        failures.append('F2: tools/inventory.py 仍存在 Material.code.ilike(f\'%{keyword}%\') 裸拼接')
    if re.search(r"Material\.name\.ilike\(f['\"]%\{keyword\}%['\"]\)", inv):
        failures.append('F2: tools/inventory.py 仍存在 Material.name.ilike(f\'%{keyword}%\') 裸拼接')
    if "Material.code.ilike(f'%{escaped}%', escape='\\\\')" not in inv:
        failures.append('F2: tools/inventory.py material_query 未使用 escape=\\\\ 转义 LIKE')
    if "Material.name.ilike(f'%{escaped}%', escape='\\\\')" not in inv:
        failures.append('F2: tools/inventory.py material_query 未使用 escape=\\\\ 转义 LIKE（name 字段）')

    # ── F3: agents/draft_check.py ──
    dc = read(Path('app/ai/agents/draft_check.py'))
    if 'from datetime import datetime' not in dc and 'from datetime import' not in dc:
        failures.append('F3: agents/draft_check.py 缺少 datetime 导入')
    if 'datetime.now().strftime' not in dc:
        # format_draft_check_report 用到 datetime.now().strftime，如果缺失说明被误改
        failures.append('F3: agents/draft_check.py 缺少 datetime.now().strftime 调用（修复点应保留）')

    # ── F4: notifications.py ──
    noti = read(Path('app/notifications.py'))
    if 'smtp_timeout' not in noti:
        failures.append('F4: notifications.py 缺少 smtp_timeout 配置')
    if 'SMTP_TIMEOUT' not in noti:
        failures.append('F4: notifications.py 缺少 SMTP_TIMEOUT 环境变量读取')
    # smtplib.SMTP 必须传入 timeout=，不再有裸 smtplib.SMTP(self.smtp_host, self.smtp_port)
    if re.search(r"smtplib\.SMTP\(self\.smtp_host,\s*self\.smtp_port\)\s*(?:as|:)", noti) and \
       'smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=' not in noti:
        failures.append('F4: notifications.py 仍存在无 timeout 参数的 smtplib.SMTP 调用')
    if 'smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=' not in noti:
        failures.append('F4: notifications.py 未在 smtplib.SMTP 调用中传入 timeout=')

    # ── F5: wechat_helper.py ──
    wechat = read(Path('app/wechat_helper.py'))
    if 'def _check_auth' not in wechat:
        failures.append('F5: wechat_helper.py 缺少 _check_auth 方法')
    if 'hmac.compare_digest' not in wechat:
        failures.append('F5: wechat_helper.py _check_auth 未使用 hmac.compare_digest 防时序攻击')
    # do_POST /send 必须在 parse_multipart 之前校验 _check_auth
    post_match = re.search(r'def do_POST\(self\).*?(?=\n    def )', wechat, re.DOTALL)
    if not post_match:
        failures.append('F5: wechat_helper.py 无法定位 do_POST 方法')
    else:
        post_body = post_match.group(0)
        auth_pos = post_body.find('self._check_auth()')
        parse_pos = post_body.find('parse_multipart(self)')
        if auth_pos == -1:
            failures.append('F5: wechat_helper.py do_POST 未调用 _check_auth')
        elif parse_pos != -1 and auth_pos > parse_pos:
            failures.append('F5: wechat_helper.py do_POST 的 _check_auth 调用位于 parse_multipart 之后，存在时序窗口')
    if 'forbidden: missing or invalid X-Wechat-Helper-Token' not in wechat:
        failures.append('F5: wechat_helper.py 缺少 403 forbidden 响应体')

    # ── F6: utils.py save_upload_image ──
    utils = read(Path('app/utils.py'))
    if '_looks_like_image' not in utils:
        failures.append('F6: utils.py 缺少 _looks_like_image magic bytes 校验函数')
    if '_IMAGE_MAGIC_PREFIXES' not in utils:
        failures.append('F6: utils.py 缺少 _IMAGE_MAGIC_PREFIXES 常量')
    if 'image.verify()' not in utils:
        failures.append('F6: utils.py save_upload_image 未调用 Pillow image.verify()')
    if "from PIL import Image as _PILImage" not in utils:
        failures.append('F6: utils.py save_upload_image 未尝试导入 Pillow')
    # 旧实现直接 file_storage.save(save_path)，新实现必须先 read() 再写回
    if 'file_storage.save(save_path)' in utils:
        failures.append('F6: utils.py save_upload_image 仍直接调用 file_storage.save(save_path) 而未先读出内容做校验')

    # ── F7: excel-table.js destroy() ──
    js = read(Path('app/static/js/excel-table.js'))
    if '_boundListeners' not in js:
        failures.append('F7: excel-table.js 缺少 _boundListeners 收集机制')
    if '_on(target, event, handler, options)' not in js and '_on(target, event, handler' not in js:
        failures.append('F7: excel-table.js 缺少 _on 事件注册辅助方法')
    if 'target.removeEventListener(event, handler, options)' not in js:
        failures.append('F7: excel-table.js destroy() 未调用 removeEventListener')
    # setupCellSelection 必须走 _on，不再直接 document.addEventListener('click', ...)
    if re.search(r"document\.addEventListener\(['\"]click['\"],\s*\(", js):
        failures.append('F7: excel-table.js setupCellSelection 仍直接 document.addEventListener 而非走 _on')
    # setupKeyboardNavigation / setupCopyPaste 必须走 _on，不再直接 this.table.addEventListener
    if re.search(r"this\.table\.addEventListener\(['\"]keydown['\"],\s*\(", js):
        failures.append('F7: excel-table.js setupKeyboardNavigation/setupCopyPaste 仍直接 this.table.addEventListener 而非走 _on')

    if failures:
        print('FAIL HIGH-PRIORITY-FIXES:')
        for f in failures:
            print(' -', f)
        return 1
    print('PASS HIGH-PRIORITY-FIXES: F1-F7 全部修复点检测到加固')
    return 0


if __name__ == '__main__':
    sys.exit(main())
