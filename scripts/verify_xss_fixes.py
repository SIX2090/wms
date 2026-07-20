"""AI-BUG-F03: 前端 XSS 修复验证
# AI_TASK: AI-BUG-F03

验证 D1/D2/D9/D10 修复点：
- D1: document_ocr.html renderResult 内 res.reply / res.msg / item.code / item.name / item.spec /
      item.quantity / res.draft.order_no / res.draft.url 等 XSS 拼接已加 escapeHtml / safeUrl
- D2: out_order_detail.html showAnomalyWarning 中 a.msg / a.ai_suggestion 已加 escapeHtml
- D9: app.js toast() message 已改用 textContent，避免 innerHTML 注入
- D10: app.js initMobileListCards 中 status.innerHTML = statusCell.innerHTML 改为 cloneNode；
       cloneCellControlsForMobile 中 rowNo 已加 escapeHtml

退出码 0=通过，1=失败。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'app' / 'templates'
STATIC_JS = ROOT / 'app' / 'static' / 'js'


def read(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def check_no_raw_innerhtml_with(text: str, *markers: str) -> list[str]:
    """检查 text 中不包含 ' + marker + ' 形式的 raw innerHTML 拼接（marker 未包 escapeHtml）。"""
    failures: list[str] = []
    for marker in markers:
        # 形如 innerHTML = '...' + res.draft.url + '...'
        # 允许 escapeHtml(marker) / safeUrl(marker)，禁止裸拼接
        pattern = re.compile(r"innerHTML\s*=\s*[^;]*\+\s*" + re.escape(marker) + r"\s*\+")
        for m in pattern.finditer(text):
            # 取该行前后窗口确认未走 escapeHtml/safeUrl
            start = max(0, m.start() - 200)
            window = text[start:m.end() + 80]
            if 'escapeHtml(' + marker in window or 'safeUrl(' + marker in window:
                continue
            failures.append(f'发现裸 innerHTML 拼接 {marker}（未走 escapeHtml/safeUrl）: {m.group(0)[:120]}')
    return failures


def main() -> int:
    failures: list[str] = []

    # ── D1: document_ocr.html ──
    d1 = read(TEMPLATES / 'document_ocr.html')

    # 必须定义 escapeHtml 和 safeUrl
    if 'function escapeHtml' not in d1:
        failures.append('D1: document_ocr.html 缺少 escapeHtml 函数定义')
    if 'function safeUrl' not in d1:
        failures.append('D1: document_ocr.html 缺少 safeUrl 函数定义')

    # res.reply / res.msg / res.draft.order_no / res.draft.url / item.code 等需走 escapeHtml/safeUrl
    # 检查 res.reply 不再裸拼接
    if re.search(r"innerHTML\s*=\s*[^;]*\+\s*res\.reply\s*\+", d1) and 'escapeHtml(res.reply)' not in d1:
        failures.append('D1: document_ocr.html res.reply 未走 escapeHtml')

    # res.msg 不再裸拼接（与 err.message 区分）
    if re.search(r"innerHTML\s*=\s*[^;]*\+\s*\(res\.msg\s*\|\|", d1) and 'escapeHtml(res.msg' not in d1:
        failures.append('D1: document_ocr.html res.msg 未走 escapeHtml')

    # err.message 不再裸拼接
    if re.search(r"innerHTML\s*=\s*[^;]*\+\s*err\.message\s*\+", d1) and 'escapeHtml(err' not in d1:
        failures.append('D1: document_ocr.html err.message 未走 escapeHtml')

    # item.code/name/spec/quantity 必须走 escapeHtml
    for field in ['item.code', 'item.name', 'item.spec', 'item.quantity']:
        if re.search(r"innerHTML\s*=\s*[^;]*\+\s*\(" + re.escape(field) + r"\s*\|\|", d1):
            if ('escapeHtml(' + field) not in d1:
                failures.append(f'D1: document_ocr.html {field} 未走 escapeHtml')

    # res.draft.order_no 必须走 escapeHtml
    if 'escapeHtml(res.draft.order_no)' not in d1:
        failures.append('D1: document_ocr.html res.draft.order_no 未走 escapeHtml')

    # res.draft.url 必须走 safeUrl 校验
    if 'safeUrl(res.draft.url)' not in d1:
        failures.append('D1: document_ocr.html res.draft.url 未走 safeUrl')

    # ── D2: out_order_detail.html ──
    d2 = read(TEMPLATES / 'out_order_detail.html')

    # showAnomalyWarning 内 a.msg 和 a.ai_suggestion 必须走 escapeHtml
    if 'escapeHtml(a.msg)' not in d2:
        failures.append('D2: out_order_detail.html showAnomalyWarning a.msg 未走 escapeHtml')
    if 'escapeHtml(a.ai_suggestion)' not in d2:
        failures.append('D2: out_order_detail.html showAnomalyWarning a.ai_suggestion 未走 escapeHtml')

    # ── D9: app.js toast() ──
    js = read(STATIC_JS / 'app.js')

    # toast() 必须使用 textContent 写入 message，而不是 innerHTML + message 拼接
    # 取 function toast 起到下一个 function 之间的内容作为函数体
    toast_start = js.find('function toast(')
    if toast_start == -1:
        failures.append('D9: app.js 缺少 toast 函数定义')
    else:
        # 截取到下一个 "function " 出现位置（粗暴但足够验证修复）
        next_fn = js.find('function ', toast_start + 10)
        body = js[toast_start:next_fn if next_fn != -1 else toast_start + 800]
        if 'cb-toast-body' not in body:
            failures.append('D9: app.js toast 函数缺少 cb-toast-body 节点选择')
        if 'textContent' not in body:
            failures.append('D9: app.js toast 函数未使用 textContent 写入消息')
        # 旧形式：'<div class="cb-toast-body">' + message + '</div>' 不应再出现
        if re.search(r"cb-toast-body['\"]\s*>\s*'\s*\+\s*message\s*\+", body):
            failures.append('D9: app.js toast 仍存在 message 裸 innerHTML 拼接')

    # ── D10: app.js initMobileListCards / cloneCellControlsForMobile ──
    # status.innerHTML = statusCell.innerHTML 必须改为 cloneNode 方式
    if re.search(r"status\.innerHTML\s*=\s*statusCell\.innerHTML", js):
        failures.append('D10: app.js initMobileListCards 仍存在 status.innerHTML = statusCell.innerHTML')

    # cloneCellControlsForMobile 中 rowNo 必须走 escapeHtml
    if 'escapeHtml(rowNo)' not in js:
        failures.append('D10: app.js cloneCellControlsForMobile rowNo 未走 escapeHtml')

    if failures:
        print('FAIL XSS-FIXES:')
        for f in failures:
            print('  - ' + f)
        return 1

    print(
        'PASS XSS-FIXES: D1 document_ocr.html / D2 out_order_detail.html / '
        'D9 app.js toast / D10 app.js initMobileListCards 均已加固'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
