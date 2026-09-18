#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 批量导入（batch_import）域路由。
#
# 批量拆分模式：为避免 endpoint 前缀化导致大量 url_for 引用改动，
# 采用「register_batch_import_routes(app)」直接在 app 上注册路由，endpoint 名保持不变
# （如 batch_import_page、import_out_order、import_in_order），与 app.py 内原有
# url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（InOrder、Material、Supplier、api_error 等）在各路由函数内
#   延迟导入（请求期才执行），避免 app.py 模块加载期触发循环导入。
# - 日志统一使用 current_app.logger 替代 app.logger。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

from datetime import datetime

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from db import db
from utils import require_role, validate_excel_extension, validate_excel_size, round_to_2_decimals


def _opening_stock_existing_summary(OpeningStock, OpeningStockDoc, material_id, warehouse_id):
    """该 (物料, 仓库) 当前已有期初合计与涉及单据数（P1-B 预检用，只读）。

    口径与 INVENTORY_TRUTH.md §2.1.2 一致：跨**全部单据**累加 quantity，
    不取单行。预检要如实告诉用户"这行会并入已有账（当前合计 X，涉及 N 张单）"，
    而不是等正式导入后才让人发现期初被叠加了。

    注意：跨单据累加是刻意的——同物料同仓可以有多张单，此处只做只读汇总，
    不修改任何数据。
    """
    rows = db.session.query(
        OpeningStockDoc.doc_no,
        OpeningStock.quantity,
    ).join(
        OpeningStock, OpeningStock.doc_id == OpeningStockDoc.id
    ).filter(
        OpeningStock.material_id == material_id,
        OpeningStock.warehouse_id == warehouse_id,
    ).all()
    total = sum(float(qty or 0) for _, qty in rows)
    doc_nos = {doc_no for doc_no, _ in rows}
    # 兼容历史直连台账行（doc_id 为 NULL，不参与上面的 JOIN）
    orphan_total = db.session.query(
        db.func.coalesce(db.func.sum(OpeningStock.quantity), 0)
    ).filter(
        OpeningStock.material_id == material_id,
        OpeningStock.warehouse_id == warehouse_id,
        OpeningStock.doc_id.is_(None),
    ).scalar()
    total += float(orphan_total or 0)
    return total, len(doc_nos)


# no-test:reason=路由注册辅助函数，能力由 batch_import 各路由测试覆盖
def register_batch_import_routes(app):
    @app.route('/import/out_order', methods=['POST'])
    @require_role('warehouse', 'purchase')
    @login_required
    def import_out_order():
        from app import (
            Department,
            Material,
            OutOrder,
            OutOrderItem,
            Unit,
            api_error,
            current_user,
        )
        file = request.files.get('file')
        if not file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error('请选择要导入的领料单文件')
            flash('请选择要导入的领料单文件', 'danger')
            return redirect(url_for('batch_import_page'))
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(_ext_msg)
            flash(_ext_msg, 'danger')
            return redirect(url_for('batch_import_page'))
        # m-03：限制 Excel 上传 ≤ 5MB
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(_size_msg)
            flash(_size_msg, 'danger')
            return redirect(url_for('batch_import_page'))
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file)
            ws = wb.active
            header_row = [str(cell).strip() if cell else '' for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
            col_map = {}
            for idx, h in enumerate(header_row):
                if not h:
                    continue
                if '单据编号' in h or '领料单号' in h or '出库单号' in h or '订单编号' in h:
                    col_map['order_no'] = idx
                elif h == '日期' or '日期' in h:
                    col_map['date'] = idx
                elif h == '用途' or '用途' in h:
                    col_map['purpose'] = idx
                elif '部门' in h or '领料' in h:
                    col_map['department'] = idx
                elif h == '领料人' or '领料人' in h:
                    col_map['picker'] = idx
                elif '物料编码' in h or '编码' in h:
                    col_map['material_code'] = idx
                elif '物料名称' in h or '名称' in h:
                    col_map['material_name'] = idx
                elif h == '规格' or '规格' in h:
                    col_map['spec'] = idx
                elif h == '单位' or '单位' in h:
                    col_map['unit'] = idx
                elif '数量' in h:
                    col_map['quantity'] = idx
                elif '单价' in h or '价格' in h:
                    col_map['price'] = idx
                elif '金额' in h or '总额' in h:
                    col_map['amount'] = idx
                elif '客供' in h:
                    col_map['customer_supplied'] = idx
                elif '合同编号' in h or '合同单号' in h:
                    col_map['contract_no'] = idx
                elif '备注' in h:
                    col_map['remark'] = idx
            if 'order_no' not in col_map:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return api_error(f'Excel表头缺少"单据编号"列。检测到的表头：{", ".join(header_row)}')
                flash(f'Excel表头缺少"单据编号"列', 'danger')
                return redirect(url_for('batch_import_page'))
            count = 0
            skip = 0
            skip_details = []
            warnings = []
            current_order = None
            current_items = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                def get_val(key):
                    if key not in col_map:
                        return ''
                    idx = col_map[key]
                    if idx >= len(row):
                        return ''
                    return str(row[idx]).strip() if row[idx] is not None else ''
                def get_num(key):
                    if key not in col_map:
                        return 0
                    idx = col_map[key]
                    if idx >= len(row) or row[idx] is None:
                        return 0
                    try:
                        return round_to_2_decimals(row[idx])
                    except (ValueError, TypeError):
                        return 0
                order_no = get_val('order_no')
                if not order_no:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：单据编号为空')
                    continue
                if current_order and order_no != current_order.order_no:
                    for item in current_items:
                        db.session.add(item)
                    count += 1
                    current_order = None
                    current_items = []
                if not current_order:
                    dept_name = get_val('department')
                    department = Department.query.filter_by(name=dept_name).first() if dept_name else None
                    if not department and dept_name:
                        department = Department.query.filter_by(code=dept_name).first()
                    date_str = get_val('date')
                    date_val = None
                    if date_str:
                        try:
                            date_val = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                date_val = datetime.strptime(date_str, '%Y/%m/%d').date()
                            except ValueError:
                                try:
                                    date_val = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
                                except ValueError:
                                    pass
                    if date_val is None and 'date' in col_map:
                        raw_date = row[col_map['date']] if col_map['date'] < len(row) else None
                        if raw_date is not None:
                            if hasattr(raw_date, 'date'):
                                date_val = raw_date.date()
                            elif hasattr(raw_date, 'year'):
                                date_val = raw_date
                    current_order = OutOrder(
                        order_no=order_no,
                        date=date_val,
                        purpose='领料单' if get_val('purpose') == '生产出库' else get_val('purpose'),
                        business_type='领料单',
                        department_id=department.id if department else None,
                        picker=get_val('picker') or None,
                        remark=get_val('remark'),
                        operator_id=current_user.id
                    )
                    if OutOrder.query.filter_by(order_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：单据编号{order_no}已存在')
                        current_order = None
                        continue
                    db.session.add(current_order)
                    db.session.flush()
                material_code = get_val('material_code')
                if material_code:
                    material = Material.query.filter_by(code=material_code).first()
                    if not material:
                        material = Material(
                            code=material_code,
                            name=get_val('material_name'),
                            spec=get_val('spec')
                        )
                        db.session.add(material)
                        db.session.flush()
                        warnings.append(f'自动创建物料：{material_code}')
                    unit_name = get_val('unit')
                    unit = Unit.query.filter_by(name=unit_name).first() if unit_name else None
                    if not unit and unit_name:
                        unit = Unit.query.filter_by(code=unit_name).first()
                    if not unit and unit_name:
                        unit = Unit(code=unit_name, name=unit_name)
                        db.session.add(unit)
                        db.session.flush()
                        warnings.append(f'自动创建单位：{unit_name}')
                    if material and unit and not material.unit_id:
                        material.unit_id = unit.id
                    qty = get_num('quantity')
                    prc = get_num('price')
                    amt = get_num('amount')
                    # BUG-2026-08-30-007：负数数量/单价直接拒绝（与 Web 端校验对齐），
                    # 此前 -5 可原样写入导致库存被反扣/金额倒挂
                    if qty <= 0:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：数量必须大于 0')
                        continue
                    prc = max(0, prc)
                    amt = max(0, amt)
                    if amt == 0:
                        amt = round_to_2_decimals(qty * prc)
                    item = OutOrderItem(
                        out_order_id=current_order.id,
                        material_id=material.id if material else None,
                        quantity=qty,
                        price=prc,
                        amount=amt,
                        remark=(get_val('remark') or '').strip() or None
                    )
                    current_items.append(item)
            if current_order and current_items:
                for item in current_items:
                    db.session.add(item)
                count += 1
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return api_error(f'导入失败：{str(e)}')
                flash(f'导入失败：{str(e)}', 'danger')
                return redirect(url_for('batch_import_page'))
            msg = f'领料单导入成功，共导入 {count} 张单据'
            if skip:
                msg += f'，跳过 {skip} 条'
            if skip_details:
                warnings.append(f'跳过详情：{"; ".join(skip_details[:20])}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                resp = {'status': 'success', 'msg': msg, 'count': count}
                if warnings:
                    resp['warnings'] = '；'.join(warnings)
                return jsonify(resp)
            flash(msg, 'success')
            for w in warnings:
                flash(w, 'warning')
        except Exception as e:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(f'领料单导入失败：{str(e)}')
            flash(f'领料单导入失败：{str(e)}', 'danger')
        return redirect(url_for('batch_import_page'))

    @app.route('/import/in_order', methods=['POST'])
    @require_role('warehouse', 'purchase')
    @login_required
    def import_in_order():
        from app import (
            InOrder,
            InOrderItem,
            Customer,
            Material,
            Supplier,
            Unit,
            Warehouse,
            api_error,
            assert_warehouse_active,
            current_user,
            get_default_warehouse,
            location_management_enabled,
            resolve_item_contract,
        )
        file = request.files.get('file')
        if not file:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error('请选择要导入的入库单文件')
            flash('请选择要导入的入库单文件', 'danger')
            return redirect(url_for('batch_import_page'))
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(_ext_msg)
            flash(_ext_msg, 'danger')
            return redirect(url_for('batch_import_page'))
        # m-03：限制 Excel 上传 ≤ 5MB
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(_size_msg)
            flash(_size_msg, 'danger')
            return redirect(url_for('batch_import_page'))
        try:
            from openpyxl import load_workbook
            wb = load_workbook(file)
            ws = wb.active
            header_row = [str(cell).strip() if cell else '' for cell in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
            col_map = {}
            for idx, h in enumerate(header_row):
                if not h:
                    continue
                if '单据编号' in h or '入库单号' in h or '订单编号' in h:
                    col_map['order_no'] = idx
                elif h == '日期' or '日期' in h:
                    col_map['date'] = idx
                elif '业务类型' in h or '入库类型' in h or '入库来源' in h:
                    col_map['business_type'] = idx
                elif h == '用途' or '用途' in h:
                    col_map['purpose'] = idx
                elif h == '仓库' or '仓库' in h:
                    col_map['warehouse'] = idx
                elif h == '库位' or '库位' in h:
                    col_map['location'] = idx
                elif '供应商' in h:
                    col_map['supplier'] = idx
                elif h == '客户' or '客户' in h or '客供方' in h:
                    col_map['customer'] = idx
                elif '工程名称' in h:
                    col_map['project_name'] = idx
                elif '物料编码' in h or '编码' in h:
                    col_map['material_code'] = idx
                elif '物料名称' in h or '名称' in h:
                    col_map['material_name'] = idx
                elif h == '规格' or '规格' in h:
                    col_map['spec'] = idx
                elif h == '单位' or '单位' in h:
                    col_map['unit'] = idx
                elif '数量' in h:
                    col_map['quantity'] = idx
                elif '单价' in h or '价格' in h:
                    col_map['price'] = idx
                elif '金额' in h or '总额' in h:
                    col_map['amount'] = idx
                elif '客供' in h:
                    col_map['customer_supplied'] = idx
                elif '合同编号' in h or '合同单号' in h:
                    col_map['contract_no'] = idx
                elif '工程名称' in h:
                    col_map['project_name'] = idx
                elif '备注' in h:
                    col_map['remark'] = idx
            if 'order_no' not in col_map:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return api_error(f'Excel表头缺少"单据编号"列。检测到的表头：{", ".join(header_row)}')
                flash(f'Excel表头缺少"单据编号"列', 'danger')
                return redirect(url_for('batch_import_page'))
            count = 0
            skip = 0
            skip_details = []
            warnings = []
            current_order = None
            current_items = []
            for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
                def get_val(key):
                    if key not in col_map:
                        return ''
                    idx = col_map[key]
                    if idx >= len(row):
                        return ''
                    return str(row[idx]).strip() if row[idx] is not None else ''
                def get_num(key):
                    if key not in col_map:
                        return 0
                    idx = col_map[key]
                    if idx >= len(row) or row[idx] is None:
                        return 0
                    try:
                        return round_to_2_decimals(row[idx])
                    except (ValueError, TypeError):
                        return 0
                order_no = get_val('order_no')
                if not order_no:
                    skip += 1
                    skip_details.append(f'第{row_idx}行：单据编号为空')
                    continue
                if current_order and order_no != current_order.order_no:
                    for item in current_items:
                        db.session.add(item)
                    count += 1
                    current_order = None
                    current_items = []
                if not current_order:
                    business_type = get_val('business_type') or '采购入库'
                    if business_type not in ('采购入库', '产品入库', '其他入库'):
                        skip += 1
                        skip_details.append(f'第{row_idx}行：业务类型无效')
                        continue
                    warehouse = get_val('warehouse') or (get_default_warehouse().name if get_default_warehouse() else '')
                    if not warehouse:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：仓库为空且未配置默认仓库')
                        continue
                    warehouse_ok, warehouse_msg = assert_warehouse_active(warehouse, allow_empty=False)
                    if not warehouse_ok:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：{warehouse_msg}')
                        continue
                    location = get_val('location')
                    if location_management_enabled() and not location:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：库位为空')
                        continue
                    supplier_name = get_val('supplier')
                    customer_name = get_val('customer')
                    supplier = Supplier.query.filter_by(name=supplier_name).first() if supplier_name else None
                    if not supplier and supplier_name:
                        supplier = Supplier.query.filter_by(code=supplier_name).first()
                    if not supplier and supplier_name:
                        supplier = Supplier(code=supplier_name, name=supplier_name)
                        db.session.add(supplier)
                        db.session.flush()
                        warnings.append(f'自动创建供应商：{supplier_name}')
                    customer = Customer.query.filter_by(name=customer_name).first() if customer_name else None
                    if not customer and customer_name:
                        customer = Customer.query.filter_by(code=customer_name).first()
                    if not customer and customer_name:
                        customer = Customer(code=customer_name, name=customer_name)
                        db.session.add(customer)
                        db.session.flush()
                        warnings.append(f'自动创建客户：{customer_name}')
                    if business_type == '采购入库' and not supplier:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：采购入库缺少供应商')
                        continue
                    if business_type == '其他入库' and not customer:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：其他入库缺少客户')
                        continue
                    date_str = get_val('date')
                    date_val = None
                    if date_str:
                        try:
                            date_val = datetime.strptime(date_str, '%Y-%m-%d').date()
                        except ValueError:
                            try:
                                date_val = datetime.strptime(date_str, '%Y/%m/%d').date()
                            except ValueError:
                                try:
                                    date_val = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
                                except ValueError:
                                    pass
                    if date_val is None and 'date' in col_map:
                        raw_date = row[col_map['date']] if col_map['date'] < len(row) else None
                        if raw_date is not None:
                            if hasattr(raw_date, 'date'):
                                date_val = raw_date.date()
                            elif hasattr(raw_date, 'year'):
                                date_val = raw_date
                    current_order = InOrder(
                        order_no=order_no,
                        date=date_val,
                        business_type=business_type,
                        purpose=get_val('purpose'),
                        warehouse=warehouse,
                        location=location,
                        supplier_id=supplier.id if supplier else None,
                        customer_id=customer.id if customer else None,
                        contract_no=get_val('contract_no') or None,
                        project_name=get_val('project_name') or None,
                        remark=get_val('remark'),
                        operator_id=current_user.id
                    )
                    if InOrder.query.filter_by(order_no=order_no).first():
                        skip += 1
                        skip_details.append(f'第{row_idx}行：单据编号{order_no}已存在')
                        current_order = None
                        continue
                    db.session.add(current_order)
                    db.session.flush()
                material_code = get_val('material_code')
                if material_code:
                    material = Material.query.filter_by(code=material_code).first()
                    if not material:
                        material = Material(
                            code=material_code,
                            name=get_val('material_name'),
                            spec=get_val('spec')
                        )
                        db.session.add(material)
                        db.session.flush()
                        warnings.append(f'自动创建物料：{material_code}')
                    unit_name = get_val('unit')
                    unit = Unit.query.filter_by(name=unit_name).first() if unit_name else None
                    if not unit and unit_name:
                        unit = Unit.query.filter_by(code=unit_name).first()
                    if not unit and unit_name:
                        unit = Unit(code=unit_name, name=unit_name)
                        db.session.add(unit)
                        db.session.flush()
                        warnings.append(f'自动创建单位：{unit_name}')
                    if material and unit and not material.unit_id:
                        material.unit_id = unit.id
                    qty = get_num('quantity')
                    prc = get_num('price')
                    amt = get_num('amount')
                    # BUG-2026-08-30-007：负数数量/单价直接拒绝（与 Web 端校验对齐）
                    if qty <= 0:
                        skip += 1
                        skip_details.append(f'第{row_idx}行：数量必须大于 0')
                        continue
                    prc = max(0, prc)
                    amt = max(0, amt)
                    if amt == 0:
                        amt = round_to_2_decimals(qty * prc)
                    customer_supplied = get_val('customer_supplied').strip().lower() in ('是', 'yes', 'y', 'true', '1')
                    if customer_supplied and current_order.business_type != '其他入库':
                        skip += 1
                        skip_details.append(f'第{row_idx}行：客供料只能用于其他入库')
                        continue
                    # BUG-2026-09-18-013：Excel 明细无逐行合同列，走表头兜底；
                    # 与逐行新增（add_in_order_item）同一收口函数，避免口径分叉。
                    _c_id, _c_no, _p_name = resolve_item_contract(current_order)
                    item = InOrderItem(
                        in_order_id=current_order.id,
                        material_id=material.id if material else None,
                        quantity=qty,
                        price=prc,
                        amount=amt,
                        is_customer_supplied=customer_supplied,
                        contract_id=_c_id,
                        contract_no=_c_no,
                        project_name=_p_name,
                    )
                    current_items.append(item)
            if current_order and current_items:
                for item in current_items:
                    db.session.add(item)
                count += 1
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return api_error(f'导入失败：{str(e)}')
                flash(f'导入失败：{str(e)}', 'danger')
                return redirect(url_for('batch_import_page'))
            msg = f'入库单导入成功，共导入 {count} 张单据'
            if skip:
                msg += f'，跳过 {skip} 条'
            if skip_details:
                warnings.append(f'跳过详情：{"; ".join(skip_details[:20])}')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                resp = {'status': 'success', 'msg': msg, 'count': count}
                if warnings:
                    resp['warnings'] = '；'.join(warnings)
                return jsonify(resp)
            flash(msg, 'success')
            for w in warnings:
                flash(w, 'warning')
        except Exception as e:
            db.session.rollback()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return api_error(f'入库单导入失败：{str(e)}')
            flash(f'入库单导入失败：{str(e)}', 'danger')
        return redirect(url_for('batch_import_page'))

    @app.route('/batch_import')
    @login_required
    def batch_import_page():
        _module_type = request.args.get('type', '').strip().lower() or None
        return render_template('batch_import.html', module_type=_module_type)

    # P1-类别 B：基础资料 /import 与 /export 便捷入口（统一跳转集中式 /batch_import）
    @app.route('/user/import', methods=['POST'])
    @login_required
    @require_role('admin')
    def user_import_stub():
        return redirect(url_for('batch_import_page', type='user'))

    @app.route('/user/export')
    @login_required
    @require_role('admin')
    def user_export_stub():
        return redirect(url_for('batch_import_page', type='user'))

    @app.route('/label_template/import', methods=['POST'])
    @login_required
    @require_role('admin')
    def label_template_import_stub():
        return redirect(url_for('batch_import_page', type='label_template'))

    @app.route('/label_template/export')
    @login_required
    @require_role('admin')
    def label_template_export_stub():
        return redirect(url_for('batch_import_page', type='label_template'))

    # ARCH-OS-IMPORT：期初库存 Excel 批量导入（替代原"仅重定向到批量导入页"的空 stub）。
    # 解析 xlsx → 复用 batch_save 的同一校验/入账路径（_apply_opening_stock_balance），
    # 仓库/物料/数量/单价/唯一键/停用仓库校验与手工保存完全一致。
    @app.route('/opening_stock/import', methods=['POST'])
    @require_role('warehouse')
    @login_required
    def opening_stock_import():
        """期初库存 Excel 导入（P1-B 两段式：预检 → 确认）。

        两段式原因：导入是**批量写库存**的高风险动作，原来"选文件 → 直接入账"
        一步到位，用户看不到会导入什么、会跳过哪些行、会不会覆盖已有单据，
        出错只能事后删单回冲。现在：
          - 第一段 `dry_run=true`：走完全相同的解析+校验，**不写任何数据**，
            返回逐行结果（将导入/将跳过 + 原因 + 与既有单据的关系），
            让用户先看清再决定；
          - 第二段不带 dry_run：真正落库。

        关键设计：两段**共用同一条代码路径**，dry_run 只控制"写不写"。
        绝不为了预检另写一套校验——两套校验必然漂移，出现"预检说没问题、
        正式导入却跳过"（或反之）是最坏结果，比没有预检更伤信任（R6）。
        """
        from app import (
            Material,
            OpeningStock,
            OpeningStockDoc,
            STOCK_COMPARE_EPSILON,
            Warehouse,
            _apply_opening_stock_balance,
            _parse_opening_stock_date,
            api_error,
            current_app,
            current_user,
            db,
            generate_order_no,
            jsonify,
            log_operation,
            normalize_stock_quantity,
            parse_float_value,
            round_to_2_decimals,
        )

        # 预检开关：只接受 true/false/1/0 等常见真值写法，其余按正式导入处理
        _dry_raw = (request.form.get('dry_run') or '').strip().lower()
        dry_run = _dry_raw in ('1', 'true', 'yes', 'on')

        file = request.files.get('file')
        if not file:
            return api_error('请选择要导入的期初库存文件')
        _ext_ok, _ext_msg = validate_excel_extension(file.filename)
        if not _ext_ok:
            return api_error(_ext_msg)
        _size_ok, _size_msg = validate_excel_size(file)
        if not _size_ok:
            return api_error(_size_msg)

        try:
            from openpyxl import load_workbook
            wb = load_workbook(file, read_only=True)
            ws = wb.active
            rows_iter = ws.iter_rows(values_only=True)
            header_row = [str(c).strip() if c is not None else '' for c in next(rows_iter, [])]
            col_map = {}
            for idx, h in enumerate(header_row):
                if not h:
                    continue
                if '仓库编码' in h or h == '仓库' or '仓库' in h:
                    col_map.setdefault('warehouse', idx)
                if '物料编码' in h or ('编码' in h and '物料' in h):
                    col_map['material_code'] = idx
                elif '物料名称' in h or ('名称' in h and '物料' in h):
                    col_map['material_name'] = idx
                elif '数量' in h:
                    col_map['quantity'] = idx
                elif '单价' in h or '价格' in h:
                    col_map['price'] = idx
                elif '日期' in h:
                    col_map['date'] = idx
                elif '备注' in h:
                    col_map['remark'] = idx
            if 'material_code' not in col_map or 'quantity' not in col_map:
                return api_error(f'Excel 表头缺少"物料编码"或"数量"列。检测到的表头：{", ".join(header_row)}')

            def _v(row, key, default=''):
                i = col_map.get(key)
                if i is None or i >= len(row):
                    return default
                v = row[i]
                return '' if v is None else str(v).strip()

            def _raw(row, key):
                # FIX-OS-DATE-001: 取原始单元格值（日期列可能是 datetime/date 对象，str() 会带时间部分）
                i = col_map.get(key)
                if i is None or i >= len(row):
                    return None
                return row[i]

            def _row_date(row):
                # 解析行日期：支持 datetime/date 对象与 YYYY-MM-DD 字符串；非法或空返回 None（回落当天）
                import datetime as _dt
                v = _raw(row, 'date')
                if v is None or (isinstance(v, str) and not v.strip()):
                    return None
                if isinstance(v, _dt.datetime):
                    return v.date().isoformat()
                if isinstance(v, _dt.date):
                    return v.isoformat()
                s = str(v).strip()
                for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y%m%d'):
                    try:
                        return _dt.datetime.strptime(s[:10] if fmt == '%Y-%m-%d' else s, fmt).date().isoformat()
                    except (ValueError, TypeError):
                        continue
                return None

            def _is_example_row(row):
                # 模板示例行：物料名称含"示例"则跳过
                name = _v(row, 'material_name')
                return '示例' in name

            imported = 0
            skipped = 0
            errors = []
            seen_keys = set()
            # P1-B：预检逐行结果（dry_run 时返回给前端，正式导入时为空）
            preview_rows = []
            # ARCH-OS-DOC-01：整批导入归入一张新单据，用户导入完就能在期初库存
            # 列表里按单查看/改日期/走 首上下末 导航。单头日期取导入当天并允许
            # 导入后修改（用户诉求"导入的期初库存单据怎么修改日期"）。
            batch_doc = None
            batch_lines = []

            def _ensure_batch_doc():
                """懒建单据头：整表全是错误行时不产生空单据污染列表。"""
                nonlocal batch_doc
                if batch_doc is None:
                    batch_doc = OpeningStockDoc(
                        doc_no=generate_order_no('QS'),
                        date=_parse_opening_stock_date(None),
                        warehouse_id=None,  # 一单可含多仓库，仓库在明细行上
                        status='active',
                        remark=f'Excel 导入（{file.filename or "未命名文件"}）',
                        operator_id=current_user.id if current_user.is_authenticated else None,
                    )
                    db.session.add(batch_doc)
                    db.session.flush()
                return batch_doc

            for row_no, row in enumerate(rows_iter, start=2):
                if _is_example_row(row):
                    continue
                code = _v(row, 'material_code')
                qty_raw = _v(row, 'quantity')
                if not code and not qty_raw:
                    continue  # 空行
                # P1-B：本行处理结果，统一在循环末尾落到 preview_rows
                # （只加一个记录点，避免在 6 个跳过分支各写一遍导致漏记）
                outcome = {'row_no': row_no, 'material_code': code, 'action': 'import',
                           'reason': '', 'material_name': '', 'warehouse': '',
                           'quantity': None, 'price': None, 'date': '',
                           'existing_quantity': None, 'existing_docs': 0}
                material = Material.query.filter_by(code=code).first()
                if not material:
                    errors.append(f'第 {row_no} 行：物料编码 [{code}] 不存在')
                    skipped += 1
                    outcome.update(action='skip', reason=f'物料编码 [{code}] 不存在')
                    preview_rows.append(outcome)
                    continue
                wh_code = _v(row, 'warehouse')
                warehouse = None
                if wh_code:
                    warehouse = Warehouse.query.filter(
                        (Warehouse.code == wh_code) | (Warehouse.name == wh_code)
                    ).first()
                    if not warehouse:
                        errors.append(f'第 {row_no} 行：仓库 [{wh_code}] 不存在')
                        skipped += 1
                        outcome.update(action='skip', reason=f'仓库 [{wh_code}] 不存在')
                        preview_rows.append(outcome)
                        continue
                else:
                    # AGENTS.md 仓库必填：期初建账未指定仓库属数据错误，报错引导用户补列，
                    # 不做静默默认仓回落（避免账实错仓）。
                    errors.append(f'第 {row_no} 行：未指定仓库编码（期初建账仓库必填）')
                    skipped += 1
                    outcome.update(action='skip', reason='未指定仓库编码（期初建账仓库必填）')
                    preview_rows.append(outcome)
                    continue
                if (warehouse.status or 'active') != 'active':
                    errors.append(f'第 {row_no} 行：仓库 [{warehouse.name}] 已停用')
                    skipped += 1
                    outcome.update(action='skip', reason=f'仓库 [{warehouse.name}] 已停用')
                    preview_rows.append(outcome)
                    continue
                dedup_key = (material.id, warehouse.id)
                if dedup_key in seen_keys:
                    errors.append(f'第 {row_no} 行：物料+仓库重复，请合并后导入')
                    skipped += 1
                    outcome.update(action='skip', reason='物料+仓库在文件内重复')
                    preview_rows.append(outcome)
                    continue
                # 注意：dedup_key 在**本行校验全部通过后**才登记（见下方
                # seen_keys.add）。若在此处提前登记，一行"数量非法/负数"被跳过
                # 之后，同 (物料,仓库) 的后续合法行会被误判成"文件内重复"一并
                # 跳过——用户改了错误行重传仍然导入不进来，且提示驴唇不对马嘴。

                quantity = parse_float_value(qty_raw, None)
                price = parse_float_value(_v(row, 'price'), 0)
                if quantity is None:
                    # BUG-2026-09-16-015：负数/非数字/空值统一落到这里，
                    # 提示要能区分，否则用户看到"无效"不知道该改什么
                    if not str(qty_raw or '').strip():
                        reason = '数量为空'
                    elif str(qty_raw).strip().startswith('-'):
                        reason = f'数量 [{qty_raw}] 不能小于 0'
                    else:
                        reason = f'数量 [{qty_raw}] 无效，必须是大于等于 0 的数字'
                    errors.append(f'第 {row_no} 行：{reason}')
                    skipped += 1
                    outcome.update(action='skip', reason=reason)
                    preview_rows.append(outcome)
                    continue
                if price < 0:
                    errors.append(f'第 {row_no} 行：单价不能小于 0')
                    skipped += 1
                    outcome.update(action='skip', reason='单价不能小于 0')
                    preview_rows.append(outcome)
                    continue
                # 本行已通过全部文件级校验，登记去重键（后续同键行才算真重复）
                seen_keys.add(dedup_key)

                try:
                    quantity = normalize_stock_quantity(quantity)
                    price = round_to_2_decimals(price)
                    amount = round_to_2_decimals(quantity * price)
                    row_date = _row_date(row)

                    # 预检：查该 (物料,仓库) 是否已有期初（跨全部单据），
                    # 告诉用户这行是"新增"还是"并入已有账"。只读查询，无副作用。
                    existing_qty, existing_docs = _opening_stock_existing_summary(
                        OpeningStock, OpeningStockDoc, material.id, warehouse.id)
                    outcome.update(
                        material_name=material.name, warehouse=warehouse.name,
                        quantity=quantity, price=price, date=row_date or '',
                        existing_quantity=existing_qty, existing_docs=existing_docs)

                    if dry_run:
                        # 预检阶段绝不写库：不建单据、不动库存、不落明细
                        imported += 1
                        preview_rows.append(outcome)
                        continue

                    doc = _ensure_batch_doc()
                    # 只在本批单据内查找同 (物料,仓库) 行：跨单据允许重复，
                    # 若不带 doc_id 过滤会命中别的单据的行，导致改错单/库存错算。
                    opening = OpeningStock.query.filter_by(
                        doc_id=doc.id, material_id=material.id, warehouse_id=warehouse.id
                    ).with_for_update().first()
                    _, delta = _apply_opening_stock_balance(
                        opening, material, quantity, price, amount,
                        _v(row, 'remark') or None, warehouse,
                        _parse_opening_stock_date(row_date),
                        '',
                        doc_id=doc.id,
                    )
                    batch_lines.append((doc, material, warehouse, row_date))
                    if opening is None or abs(delta) > STOCK_COMPARE_EPSILON:
                        imported += 1
                    preview_rows.append(outcome)
                except ValueError as ve:
                    errors.append(f'第 {row_no} 行：{ve}')
                    skipped += 1
                    outcome.update(action='skip', reason=str(ve))
                    preview_rows.append(outcome)

            # ===== 预检分支：任何写操作到此为止，回滚只读事务后返回逐行结果 =====
            if dry_run:
                # 预检路径上没有写操作，但查询可能开了只读事务；
                # 显式 rollback 确保即使将来有人在预检路径里误加写入也不会落库。
                db.session.rollback()
                importable = [r for r in preview_rows if r['action'] == 'import']
                overwrite = [r for r in importable if r.get('existing_docs')]
                fresh = [r for r in importable if not r.get('existing_docs')]
                return jsonify({
                    'status': 'success',
                    'dry_run': True,
                    'msg': (f'预检完成：{len(importable)} 行可导入'
                            f'（其中 {len(fresh)} 行新增、{len(overwrite)} 行并入已有期初），'
                            f'{skipped} 行有问题'),
                    'imported': len(importable),
                    'skipped': skipped,
                    'errors': errors[:20],
                    'rows': preview_rows[:500],
                    'total_rows': len(preview_rows),
                    'truncated': len(preview_rows) > 500,
                    'fresh_count': len(fresh),
                    'overwrite_count': len(overwrite),
                })

            # 明细行日期为空时跟随单头（导入行自带日期则保留，尊重 Excel 里的建账日）
            db.session.flush()
            for doc, material, warehouse, row_date in batch_lines:
                if not row_date:
                    line = OpeningStock.query.filter_by(
                        doc_id=doc.id, material_id=material.id,
                        warehouse_id=warehouse.id,
                    ).first()
                    if line is not None:
                        line.date = doc.date

            # 一行都没导入成功则不留空单据
            if batch_doc is not None and not batch_lines:
                db.session.delete(batch_doc)
                batch_doc = None

            db.session.commit()
            doc_no = batch_doc.doc_no if batch_doc is not None else None
            log_operation(
                '批量导入期初库存',
                f'导入 {imported} 行，跳过 {skipped} 行，单据 {doc_no or "-"}',
                'opening_stock', batch_doc.id if batch_doc is not None else None,
            )
            msg = f'期初库存导入完成，共导入 {imported} 行'
            if doc_no:
                msg += f'，已生成单据 {doc_no}'
            if skipped:
                msg += f'，跳过 {skipped} 行'
            return jsonify({
                'status': 'success',
                'msg': msg,
                'imported': imported,
                'skipped': skipped,
                'errors': errors[:20],
                # 与预检同一份逐行结果契约：调用方（前端/AI/脚本）不必为两段写
                # 两套解析，也让"预检结果 vs 实际结果"可直接逐行比对（P1-B）。
                'rows': preview_rows[:500],
                'total_rows': len(preview_rows),
                'truncated': len(preview_rows) > 500,
                'doc_id': batch_doc.id if batch_doc is not None else None,
                'doc_no': doc_no,
                'detail_url': f'/opening_stock/{batch_doc.id}' if batch_doc is not None else None,
            })
        except Exception as e:  # noqa: BLE001
            db.session.rollback()
            current_app.logger.error(f'期初库存批量导入失败: {e}')
            return api_error('期初库存导入失败，请检查文件格式后重试')

    @app.route('/opening_stock/export')
    @login_required
    def opening_stock_export_stub():
        return redirect(url_for('batch_import_page', type='opening_stock'))