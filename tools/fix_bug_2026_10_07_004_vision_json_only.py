#!/usr/bin/env python3
"""BUG-2026-10-07-004 修复：视觉模型只返回纯 JSON（无文字说明）时提取结果被丢弃。

场景：用户在 AI 助手上传票据图 + 「提取产品名称 产品型号」。
模型遵守 doc vision system prompt 返回纯 JSON（无 ```json 包裹的纯文本 JSON 也常见），
_ai_extract_json_object 能解析出 extracted，但：
  1. _ai_call_llm_document_vision_extract 的 normalize 因 document_type=other
     或 items 规格字段不完整等原因返回 None → extracted_doc=None；
  2. 回落到 _ai_call_llm_vision，_ai_vision_parse_extracted 返回 reply='' extracted=None
     （纯 JSON 无 ``` 包裹时 match 失败 → 返回整个 JSON 文本作为 reply？不——
     纯 JSON 无代码块时 match=None → reply=content 即 JSON 文本，extracted=None）。
     实际丢数据的路径：reply 为空字符串时主链路直接当失败处理。

修复（主链路 _ai_handle_warehouse_assistant_request 内）：
  vision_reply 为空但 extracted 非空时，继续走 _ai_create_draft_from_extracted；
  连 structured_response 都没有时，把 extracted 渲染成可读明细兜底回复，
  而不是落到「没有返回具体错误」的误导报错。

本脚本做三处修改（幂等，重复运行安全）：
  A. _ai_call_llm_vision：reply 为空但 content 有值时，从 content 直接解析 JSON
     （补 ```json 剥离之外的裸 JSON 场景），并把空 reply 兜底成 ''。
  B. 主链路：`if vision_reply:` 改为 `if vision_reply or extracted:`
     并在纯 extracted 分支构造兜底 reply 文本。
  C. 错误文案分支：vision_error 为空且 extracted 也为空时不再断言「模型没有返回」，
     保持原文案（该分支只在真正无结果时到达）。
"""
from __future__ import annotations

import re
import sys

APP_PY = '/Coze/Drive/扣子/wms/app/app.py'


def read_src() -> str:
    with open(APP_PY, 'rb') as f:
        return f.read().decode('utf-8')


def write_src(src: str) -> None:
    with open(APP_PY, 'wb') as f:
        f.write(src.encode('utf-8'))


def main() -> int:
    src = read_src()
    changed = []

    # ── A. _ai_call_llm_vision：裸 JSON 兜底解析 + 空 reply 兜底 ──
    old_a = """        reply, extracted = _ai_vision_parse_extracted(content)
        return reply[:1400], extracted, ''
"""
    new_a = """        reply, extracted = _ai_vision_parse_extracted(content)
        if not extracted:
            bare = _ai_extract_json_object(content)
            if isinstance(bare, dict):
                extracted = bare
                if not reply or not reply.strip():
                    reply = ''
        if not reply.strip() and not extracted:
            return None, None, '供应商接口返回成功，但没有可用的文本或结构化内容'
        return reply[:1400], extracted, ''
"""
    if old_a in src:
        src = src.replace(old_a, new_a, 1)
        changed.append('A: _ai_call_llm_vision bare-JSON fallback')
    elif new_a[:80] in src:
        changed.append('A: already applied')
    else:
        print('A: target block not found', file=sys.stderr)
        return 1

    # ── B. 主链路：vision_reply 空但 extracted 有值时继续处理 ──
    old_b = """            vision_reply, extracted, vision_error = _ai_call_llm_vision(message, images, context)
            if vision_reply:
"""
    new_b = """            vision_reply, extracted, vision_error = _ai_call_llm_vision(message, images, context)
            if not vision_reply and extracted:
                vision_reply = _ai_vision_extracted_fallback_reply(extracted)
            if vision_reply:
"""
    if old_b in src:
        src = src.replace(old_b, new_b, 1)
        changed.append('B: main chain extracted-only fallback wiring')
    elif new_b[:120] in src:
        changed.append('B: already applied')
    else:
        print('B: target block not found', file=sys.stderr)
        return 1

    # ── C. 新增兜底 reply 生成函数（放在 _ai_vision_parse_extracted 之后） ──
    helper = '''

def _ai_vision_extracted_fallback_reply(extracted):
    """BUG-2026-10-07-004：视觉模型只返回结构化提取（无文字说明）时的兜底回复。

    模型按 doc prompt 输出纯 JSON 时，主链路不应把提取结果当成「模型没有返回」。
    这里把 items 渲染成用户可读的明细列表，供后续建单/确认流程继续走。
    """
    if not isinstance(extracted, dict):
        return ''
    items = extracted.get('items') or []
    lines = ['图片已识别，提取到以下内容：']
    doc_type = str(extracted.get('document_type') or '').strip()
    if doc_type:
        label = AI_DOC_TYPE_LABELS.get(doc_type) or doc_type
        lines.append(f'单据类型：{label}')
    for field in ('order_no', 'delivery_no', 'supplier', 'customer'):
        value = str(extracted.get(field) or '').strip()
        if value:
            lines.append(f'{field}：{value}')
    for item in items[:20]:
        if not isinstance(item, dict):
            continue
        bits = []
        for key, label in (('code', '编码'), ('name', '名称'), ('spec', '规格'), ('quantity', '数量'), ('unit', '单位')):
            value = str(item.get(key) or '').strip()
            if value and value not in ('0', '0.0'):
                bits.append(f'{label} {value}')
        if bits:
            lines.append('・' + '，'.join(bits))
    if len(items) > 20:
        lines.append(f'……共 {len(items)} 条明细')
    if not extracted.get('order_no') and not items:
        return ''
    return '\\n'.join(lines)
'''
    anchor_c = "    return content.strip(), None\n\ndef _ai_vision_try_create_draft"
    if anchor_c in src:
        src = src.replace(anchor_c, "    return content.strip(), None\n" + helper + "\ndef _ai_vision_try_create_draft", 1)
        changed.append('C: fallback reply helper added')
    elif '_ai_vision_extracted_fallback_reply' in src:
        changed.append('C: already applied')
    else:
        print('C: anchor not found', file=sys.stderr)
        return 1

    write_src(src)
    for c in changed:
        print('OK', c)
    return 0


if __name__ == '__main__':
    sys.exit(main())
