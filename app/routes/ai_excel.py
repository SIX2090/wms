#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单据 OCR 导出 Excel（ai_excel）域路由。

FEATURE-2026-10-08-EXCEL：送货单等单据图片拍照/上传 → OCR 提取 → 生成 Excel 下载。
复用 app.py 的识别链路（图片预处理→视觉模型→JSON 提取），但跳过物料匹配/
草稿创建/确认台，直接把单据头 + 明细行写成 xlsx 返回。

- A10 架构约束：新路由放 app/routes/ 模块，不进 app.py。
- A8 说明：本接口输入是 multipart 图片文件（与 api_document_ocr 一致），
  图片字段无法用 pydantic JSON 模型表达，沿用 request.files 校验模式。
"""
from __future__ import annotations

import base64
import io

from functools import wraps

from flask import Blueprint, jsonify, request, send_file

ai_excel_bp = Blueprint('ai_excel', __name__)


def _web_or_api_role_required(*roles):
    """与 app.py web_or_api_role_required 等价的本地实现（避免循环导入）。

    Web session 或 Bearer Token 用户均可；角色不在白名单则 403。
    """
    allowed = set(roles or ())

    def decorator(f):
        # no-test:reason=装饰器内部包装，由 api_document_ocr_excel 的契约测试覆盖
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask_login import current_user
            user = current_user if current_user.is_authenticated else None
            if user is None:
                from app import get_bearer_user
                user = get_bearer_user()
            if user is None:
                return jsonify({'status': 'error', 'success': False, 'msg': '未登录或 Bearer Token 无效'}), 401
            if user.role != 'admin' and user.role not in allowed:
                return jsonify({'status': 'error', 'success': False, 'msg': '当前账号没有权限执行该操作'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
MAX_IMAGE_BYTES = 10 * 1024 * 1024

DOC_TYPE_LABELS = {
    'in_order': '入库/送货单',
    'out_order': '出库/领料单',
    'transfer': '调拨单',
    'check': '盘点单',
    'wechat': '微信通知',
    'other': '单据',
}

OCR_EXTRACT_PROMPT = '''请仔细识别这张单据图片的内容。这可能是一张送货单、入库单、出库单、领料单、微信聊天截图或手写单据。

请提取以下信息：
1. 单据类型（入库/出库/调拨/盘点/微信通知）
2. 供应商/客户名称（如有）
3. 单据编号（如有）
4. 物料明细：编码、名称、规格、数量、单价、金额
5. 日期（如有）
6. 备注信息

请在回答末尾追加一个JSON代码块，格式如下：
```json
{
  "document_type": "in_order",
  "supplier": "供应商名称",
  "order_no": "单据编号",
  "date": "2024-01-15",
  "items": [
    {"code": "A001", "name": "物料名称", "spec": "规格", "quantity": 100, "price": 10.5}
  ],
  "remarks": "备注"
}
```
document_type可选：in_order（入库/送货）、out_order（出库/领料）、transfer（调拨）、check（盘点）、wechat（微信通知）。
无法识别的字段留空或省略。'''

DOC_TYPE_HINT_LABELS = {
    'in_order': '这是一张入库单/送货单',
    'out_order': '这是一张出库单/领料单',
    'wechat': '这是微信聊天截图，可能包含送货通知',
}


def _to_float_or_none(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


@ai_excel_bp.route('/api/ai/document_ocr_excel', methods=['POST'])
@_web_or_api_role_required('warehouse', 'purchase')
def api_document_ocr_excel():
    """单据图片 OCR 提取 → Excel 下载。App「识别单据」页提供导出按钮。"""
    # 延迟导入：识别链路辅助函数在 app.py（避免启动期循环导入）
    from app import (
        _ai_call_llm_vision,
        _ai_llm_configured,
        _ai_llm_vision_enabled,
    )

    if not _ai_llm_configured() or not _ai_llm_vision_enabled():
        return jsonify({'status': 'error', 'msg': '请先在系统设置中启用大模型和图片识别'}), 400
    if 'image' not in request.files:
        return jsonify({'status': 'error', 'msg': '请上传图片'}), 400
    file = request.files['image']
    if not file.filename:
        return jsonify({'status': 'error', 'msg': '请选择图片文件'}), 400
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_IMAGE_EXT:
        return jsonify({'status': 'error', 'msg': '不支持的图片格式'}), 400
    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > MAX_IMAGE_BYTES:
        return jsonify({'status': 'error', 'msg': '图片大小不能超过10MB'}), 400

    try:
        original_bytes = file.read()
        try:
            from ai.documents.image_preprocessing import preprocess_image
            preprocess_result = preprocess_image(original_bytes, filename=file.filename)
        except Exception as preprocess_exc:  # noqa: BLE001
            preprocess_result = None
        if preprocess_result is not None and not preprocess_result.is_usable:
            return jsonify({
                'status': 'error',
                'msg': preprocess_result.blocked_reason or '图片质量不满足识别要求',
            }), 400
        if preprocess_result is not None and preprocess_result.is_usable and preprocess_result.processed_bytes:
            img_data = base64.b64encode(preprocess_result.processed_bytes).decode('ascii')
            data_url = f'data:{preprocess_result.processed_mime};base64,{img_data}'
        else:
            img_data = base64.b64encode(original_bytes).decode('ascii')
            data_url = f'data:image/{ext};base64,{img_data}'

        doc_type_hint = request.form.get('document_type', 'auto')
        prompt = OCR_EXTRACT_PROMPT
        if doc_type_hint != 'auto':
            prompt = f'提示：{DOC_TYPE_HINT_LABELS.get(doc_type_hint, "")}\n\n' + prompt

        reply, extracted, error = _ai_call_llm_vision(prompt, [{'data_url': data_url}])
        if error:
            return jsonify({'status': 'error', 'msg': f'视觉模型调用失败：{error}'}), 500
        if not extracted or not isinstance(extracted, dict):
            if reply and reply.strip():
                return jsonify({'status': 'error', 'msg': '未识别到单据明细，无法导出 Excel。' + reply[:200]}), 422
            return jsonify({'status': 'error', 'msg': '未识别到单据内容，无法导出 Excel'}), 422

        doc_type_label = DOC_TYPE_LABELS.get(
            str(extracted.get('document_type') or '').strip().lower(), '单据')

        rows = []
        for item in extracted.get('items') or []:
            if not isinstance(item, dict):
                continue
            rows.append([
                str(item.get('code') or '').strip(),
                str(item.get('name') or '').strip(),
                str(item.get('spec') or '').strip(),
                _to_float_or_none(item.get('quantity')),
                _to_float_or_none(item.get('price')),
                _to_float_or_none(item.get('amount')),
                str(item.get('unit') or '').strip(),
            ])

        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = '单据明细'
        ws.append(['单据类型', doc_type_label])
        ws.append(['供应商/客户', str(extracted.get('supplier') or '').strip()])
        ws.append(['单据编号', str(extracted.get('order_no') or '').strip()])
        ws.append(['日期', str(extracted.get('date') or '').strip()])
        ws.append(['备注', str(extracted.get('remarks') or '').strip()])
        ws.append([])
        ws.append(['物料编码', '物料名称', '规格型号', '数量', '单价', '金额', '单位'])
        for row in rows:
            ws.append(row)
        if not rows:
            ws.append(['（未识别到明细行）', '', '', None, None, None, ''])
        for col, width in zip('ABCDEFG', (16, 28, 18, 10, 10, 12, 8)):
            ws.column_dimensions[col].width = width

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        from datetime import datetime as _dt
        stamp = _dt.now().strftime('%Y%m%d_%H%M%S')
        supplier_part = (str(extracted.get('supplier') or '').strip()[:20] or '单据')
        download_name = f'单据_{supplier_part}_{stamp}.xlsx'
        from urllib.parse import quote as _quote
        return send_file(
            output,
            download_name=_quote(download_name),
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
    except Exception as e:  # noqa: BLE001
        from flask import current_app
        current_app.logger.error(f'OCR导出Excel失败: {e}')
        return jsonify({'status': 'error', 'msg': f'导出失败：{str(e)}'}), 500
