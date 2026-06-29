#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
包含：通用工具函数、序列化函数、库存操作函数、权限装饰器等
"""

import json
import os
import uuid
import html.parser
from datetime import datetime, date
from functools import wraps

from flask import request, jsonify, current_app, redirect, url_for, flash
from flask_login import current_user

from db import db


# ==================== 数值处理 ====================
def round_to_2_decimals(value):
    """将数值四舍五入到2位小数"""
    if value is None:
        return 0.0
    return round(float(value) * 100) / 100


STOCK_COMPARE_EPSILON = 1e-6


def normalize_stock_quantity(value):
    """Normalize stock quantities to the business precision used by the UI."""
    normalized = round_to_2_decimals(value)
    return 0.0 if abs(normalized) < STOCK_COMPARE_EPSILON else normalized


def is_stock_sufficient(current_stock, required_quantity):
    """Compare stock values at two-decimal business precision."""
    current = normalize_stock_quantity(current_stock)
    required = normalize_stock_quantity(required_quantity)
    return current + STOCK_COMPARE_EPSILON >= required


def parse_float_value(value, default=0):
    """安全地解析浮点数值"""
    try:
        if value is None or value == '':
            return float(default)
        result = float(value)
        if result < 0:
            return float(default)
        return result
    except (TypeError, ValueError):
        return float(default)


def parse_date_value(value, default=None):
    """安全地解析日期值"""
    if not value:
        return default
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return default


# ==================== 序列化函数 ====================
def serialize_unit(unit):
    if not unit:
        return None
    return {
        'id': unit.id,
        'code': unit.code or '',
        'name': unit.name,
    }


def serialize_supplier(supplier):
    if not supplier:
        return None
    return {
        'id': supplier.id,
        'code': supplier.code or '',
        'name': supplier.name,
        'contact': supplier.contact or '',
        'phone': supplier.phone or '',
        'address': supplier.address or '',
    }


def serialize_customer(customer):
    if not customer:
        return None
    return {
        'id': customer.id,
        'code': customer.code or '',
        'name': customer.name,
        'contact': customer.contact or '',
        'phone': customer.phone or '',
        'address': customer.address or '',
    }


def serialize_material(material):
    if not material:
        return None
    
    unit_obj = None
    try:
        unit_rel = getattr(material, 'unit', None)
        if unit_rel is not None:
            unit_obj = serialize_unit(unit_rel)
    except Exception:
        unit_obj = None
    
    return {
        'id': material.id or 0,
        'code': material.code or '',
        'name': material.name or '',
        'spec': material.spec or '',
        'purpose': material.purpose or '',
        'price': float(material.price or 0),
        'stock': float(material.stock or 0),
        'unit': unit_obj,
    }


def serialize_material_legacy(material):
    if not material:
        return None
    return {
        'id': material.id,
        'code': material.code,
        'name': material.name,
        'spec': material.spec or '',
        'purpose': material.purpose or '',
        'price': material.price or 0,
        'stock': material.stock or 0,
        'unit': material.unit.name if material.unit else '',
    }


def serialize_bom_item(item):
    return {
        'id': item.id,
        'material_id': item.material_id,
        'material_code': item.material.code if item.material else '',
        'material_name': item.material.name if item.material else '',
        'material_spec': item.material.spec if item.material else '',
        'quantity': item.quantity or 0,
        'unit_id': item.unit_id,
        'unit_cost': item.unit_cost or 0,
        'total_cost': item.total_cost or 0,
        'usage': item.usage or '',
        'remark': item.remark or '',
    }


def serialize_bom(bom):
    return {
        'id': bom.id,
        'bom_no': bom.bom_no,
        'product_code': bom.product_code,
        'product_name': bom.product_name,
        'version': bom.version,
        'status': bom.status,
        'level': bom.level or 1,
        'total_cost': bom.total_cost or 0,
        'created_at': bom.created_at.strftime('%Y-%m-%d %H:%M') if bom.created_at else '',
        'remark': bom.remark or '',
        'materials': [serialize_bom_item(item) for item in bom.items],
    }


# ==================== 库存操作 ====================
def check_stock_sufficient(material, required_quantity):
    """检查库存是否充足，返回(是否充足, 当前库存, 错误信息)"""
    if not material:
        return False, 0, '物料不存在'
    current_stock = normalize_stock_quantity(material.stock or 0)
    required_quantity = normalize_stock_quantity(required_quantity)
    if not is_stock_sufficient(current_stock, required_quantity):
        return False, current_stock, f'物料 {material.code} 库存不足，当前库存：{current_stock:.2f}，需要：{required_quantity:.2f}'
    return True, current_stock, ''


# ==================== 订单工具 ====================
def recalculate_order_total(order):
    if not order:
        return 0
    total = sum((item.amount or 0) for item in order.items)
    order.total_amount = total
    return total


# ==================== 打印模板工具 ====================
# Excel 导入允许的文件扩展名白名单
ALLOWED_EXCEL_EXTENSIONS = {'.xlsx', '.xls'}


def validate_excel_extension(filename):
    """校验上传文件扩展名是否为 Excel。

    返回 (is_valid, error_msg)。校验失败时 error_msg 为中文提示，
    成功时 error_msg 为空字符串。统一在所有 Excel 导入路由调用，
    避免恶意文件（如 .html/.svg）触发解析异常或被 openpyxl 误处理。
    """
    if not filename:
        return False, '请选择要导入的文件'
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXCEL_EXTENSIONS:
        return False, f'仅支持 Excel 文件（.xlsx 或 .xls），当前文件类型：{ext or "未知"}'
    return True, ''


# ==================== 打印 HTML 模板净化 ====================
# 用户自定义 HTML 打印模板经 SandboxedEnvironment 渲染后，仍可能包含 <script>、
# <iframe>、on* 事件属性等危险内容（管理员账号被攻破时会触发存储型 XSS）。
# 由于 wheelhouse 无 bleach/nh3，这里用标准库 html.parser 实现白名单净化器。

# 不需要闭合的标签（HTML void elements）
_VOID_TAGS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

# 必须连同内容一起丢弃的危险标签
_DANGEROUS_PRINT_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'applet', 'form',
                         'input', 'button', 'textarea', 'select', 'option', 'link', 'meta',
                         'base', 'svg', 'math', 'frame', 'frameset', 'noscript', 'template'}

# 允许的标签白名单（打印模板常用排版/表格/图片标签）
_ALLOWED_PRINT_TAGS = {
    'a', 'abbr', 'address', 'article', 'aside', 'b', 'blockquote', 'br', 'caption',
    'center', 'cite', 'code', 'col', 'colgroup', 'dd', 'del', 'details', 'dfn',
    'div', 'dl', 'dt', 'em', 'figcaption', 'figure', 'font', 'footer', 'h1', 'h2',
    'h3', 'h4', 'h5', 'h6', 'header', 'hr', 'i', 'img', 'ins', 'kbd', 'li', 'main',
    'mark', 'nav', 'ol', 'p', 'pre', 'q', 's', 'section', 'small', 'span', 'strong',
    'sub', 'summary', 'sup', 'table', 'tbody', 'td', 'tfoot', 'th', 'thead', 'time',
    'tr', 'u', 'ul', 'var', 'wbr',
}

# 允许的属性白名单（按标签不区分，统一过滤）
_ALLOWED_PRINT_ATTRS = {
    'align', 'alt', 'bgcolor', 'border', 'cellpadding', 'cellspacing', 'class',
    'color', 'colspan', 'datetime', 'face', 'height', 'href', 'id', 'lang', 'rel',
    'rowspan', 'size', 'span', 'src', 'style', 'target', 'title', 'valign', 'width',
    'nowrap', 'scope', 'headers',
}


def _has_dangerous_protocol(value: str) -> bool:
    """检查 URL 属性值是否包含 javascript:/vbscript:/data: 等危险协议。"""
    stripped = value.strip().lower()
    # 去掉前导空白和控制字符后再判断
    for proto in ('javascript:', 'vbscript:', 'data:', 'file:'):
        if stripped.startswith(proto):
            return True
    return False


def _escape_attr(value: str) -> str:
    """转义属性值中的双引号和 &，防止属性注入。"""
    return (value or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def _escape_text(text: str) -> str:
    """转义文本节点中的特殊字符。"""
    return (text or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class _PrintHtmlSanitizer(html.parser.HTMLParser):
    """白名单方式净化 HTML，移除 script/iframe 等危险标签及 on* 事件属性。"""

    def __init__(self):
        # Python 3.10- 兼容：convert_charrefs=True 默认即 True
        super().__init__(convert_charrefs=True)
        self._out: list[str] = []
        self._skip_depth = 0  # 正在被丢弃的标签嵌套层数

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if self._skip_depth > 0:
            # 已在丢弃栈中，自闭合标签不增加深度，普通标签才+1
            if tag not in _VOID_TAGS:
                self._skip_depth += 1
            return
        if tag in _DANGEROUS_PRINT_TAGS:
            if tag not in _VOID_TAGS:
                self._skip_depth = 1
            return
        if tag not in _ALLOWED_PRINT_TAGS:
            return  # 非白名单标签：丢弃标签本身但保留其内容
        safe_attrs = self._filter_attrs(tag, attrs)
        attr_str = ''.join(f' {k}="{_escape_attr(v)}"' for k, v in safe_attrs)
        if tag in _VOID_TAGS:
            self._out.append(f'<{tag}{attr_str} />' if tag == 'img' else f'<{tag}{attr_str}>')
        else:
            self._out.append(f'<{tag}{attr_str}>')

    def handle_startendtag(self, tag, attrs):
        # <img .../> 等自闭合形式
        tag = tag.lower()
        if self._skip_depth > 0 or tag in _DANGEROUS_PRINT_TAGS or tag not in _ALLOWED_PRINT_TAGS:
            return
        safe_attrs = self._filter_attrs(tag, attrs)
        attr_str = ''.join(f' {k}="{_escape_attr(v)}"' for k, v in safe_attrs)
        self._out.append(f'<{tag}{attr_str} />')

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._skip_depth > 0:
            if tag not in _VOID_TAGS:
                self._skip_depth -= 1
            return
        if tag in _ALLOWED_PRINT_TAGS and tag not in _VOID_TAGS:
            self._out.append(f'</{tag}>')

    def handle_data(self, data):
        if self._skip_depth > 0:
            return
        # 文本数据需要 HTML 转义，防止标签注入
        self._out.append(_escape_text(data))

    def handle_entityref(self, name):
        if self._skip_depth > 0:
            return
        self._out.append(f'&{name};')

    def handle_charref(self, name):
        if self._skip_depth > 0:
            return
        self._out.append(f'&#{name};')

    def _filter_attrs(self, tag, attrs):
        safe = []
        for k, v in attrs:
            k_lower = (k or '').lower()
            v_str = v or ''
            # 阻断 on* 事件属性
            if k_lower.startswith('on'):
                continue
            # 阻断 javascript:/vbscript:/data: 等危险协议
            if k_lower in ('href', 'src') and _has_dangerous_protocol(v_str):
                continue
            if k_lower not in _ALLOWED_PRINT_ATTRS:
                continue
            safe.append((k_lower, v_str))
        return safe

    def get_output(self) -> str:
        return ''.join(self._out)


def sanitize_print_html(html_content):
    """净化用户自定义 HTML 打印模板渲染后的内容。

    使用白名单方式过滤标签和属性：
    - 移除 script/style/iframe/form/svg 等危险标签及其内容
    - 移除 on* 事件属性
    - 移除 javascript:/vbscript:/data: 协议的 href/src
    - 非白名单标签丢弃标签本身但保留其内部文本

    用于在 |safe 输出前对 _render_html_print_content 的结果做防御性净化，
    防止管理员账号被攻破后通过打印模板注入存储型 XSS。
    """
    if not html_content:
        return ''
    try:
        parser = _PrintHtmlSanitizer()
        parser.feed(html_content)
        parser.close()
        return parser.get_output()
    except Exception as e:
        try:
            current_app.logger.error(f'打印模板HTML净化失败: {e}')
        except Exception:
            pass
        # 净化失败时只返回固定安全提示，不输出未净化的 HTML。
        return '<div style="color:#b91c1c;border:1px solid #fecaca;padding:12px;">打印模板内容净化失败，请检查模板后重试</div>'


def get_default_print_template(model):
    return model.query.filter_by(is_default=True).order_by(model.updated_at.desc()).first() or \
        model.query.order_by(model.updated_at.desc()).first()


def save_print_template_file(file_storage, prefix, static_folder):
    if not file_storage or not file_storage.filename:
        return ''

    # 严格限制打印模板文件扩展名为 Excel，避免上传 HTML 触发存储型 XSS
    ext = os.path.splitext(file_storage.filename)[1].lower()
    if ext not in ('.xlsx', '.xls'):
        ext = '.xlsx'
    filename = f'{prefix}_{uuid.uuid4().hex}{ext}'
    relative_dir = os.path.join('uploads', 'print_templates')
    absolute_dir = os.path.join(static_folder, relative_dir)
    os.makedirs(absolute_dir, exist_ok=True)

    absolute_path = os.path.join(absolute_dir, filename)
    file_storage.save(absolute_path)
    from flask import url_for
    return url_for('static', filename=f'uploads/print_templates/{filename}')


# ==================== 图片上传 ====================
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}


def save_upload_image(file_storage, subfolder='', upload_folder=None):
    """Validate and save an uploaded image under the configured upload folder."""
    if not file_storage or not file_storage.filename:
        return None, None

    ext = os.path.splitext(file_storage.filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return None, '仅支持 JPG、PNG、GIF、WEBP 格式图片'

    upload_root = upload_folder or current_app.config.get('UPLOAD_FOLDER', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads'))
    save_dir = os.path.join(upload_root, subfolder) if subfolder else upload_root
    os.makedirs(save_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}.{ext}"
    save_path = os.path.join(save_dir, filename)
    file_storage.save(save_path)

    relative_parts = ['uploads']
    if subfolder:
        relative_parts.append(subfolder.replace('\\', '/').strip('/'))
    relative_parts.append(filename)
    return '/'.join(relative_parts), None


# ==================== 权限装饰器 ====================
def require_role(*roles):
    """Require one of the allowed business roles on the server side."""
    allowed = set(roles or ())

    def wants_json_response():
        if request.path.startswith('/api/'):
            return True
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return True
        best = request.accept_mimetypes.best_match(['application/json', 'text/html'])
        return best == 'application/json' and request.accept_mimetypes[best] >= request.accept_mimetypes['text/html']

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                if wants_json_response():
                    return jsonify({'status': 'error', 'msg': '请先登录'}), 401
                return redirect(url_for('login', next=request.full_path if request.query_string else request.path))
            if current_user.role != 'admin' and current_user.role not in allowed:
                if wants_json_response():
                    return jsonify({'status': 'error', 'msg': '当前账号没有权限执行此操作'}), 403
                flash('当前账号没有权限访问该页面', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==================== Jinja2 过滤器 ====================
def currency_cn(value):
    """Format amounts for display without relying on corrupted legacy literals."""
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return '0.00'


def from_json_filter(value):
    """Deserialize a JSON string for templates."""
    if not value:
        return {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def to_json_filter(value):
    """Serialize a value to JSON for templates."""
    return json.dumps(value, ensure_ascii=False)


def range_filter(n):
    """Expose Python range behavior to templates."""
    return list(range(int(n)))


def add_filter(a, b):
    """Add two values for templates."""
    return int(a) + int(b)
