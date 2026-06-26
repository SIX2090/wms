#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块
包含：通用工具函数、序列化函数、库存操作函数、权限装饰器等
"""

import json
import os
import uuid
from datetime import datetime, date
from functools import wraps

from flask import request, jsonify, current_app
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
    """检查用户角色，如果不符合则返回错误"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'status': 'error', 'msg': '请先登录'})
            if current_user.role not in roles and current_user.role != 'admin':
                return jsonify({'status': 'error', 'msg': '您没有权限执行此操作'})
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
