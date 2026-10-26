#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 报表（report）域路由。
#
# 批量拆分模式：与销售（sales）域一致，采用「register_report_routes(app)」
# 直接在 app 上注册路由，endpoint 名保持不变（如 report、purchase_report、
# report_dashboard、report_dashboard_ai_insights、report_view、report_api_query、
# report_inout_print、report_inout_export、report_stock_print、
# report_print_not_implemented 等），
# 与 app.py 内原有 url_for 引用完全兼容。
#
# - 模块级只导入稳定依赖（flask / flask_login / db / utils），不导入 app，避免循环导入。
# - app.py 内部定义（REPORT_DEFINITIONS / REPORT_TYPE_ORDER /
#   build_report_dashboard_context / _get_report_definition / _build_report_filters /
#   _build_report_payload / _build_report_excel_download / _ai_llm_configured /
#   _ai_call_llm_chat / api_error / get_active_warehouses / get_default_warehouse /
#   inventory_alert_enabled / _material_alert_status_values / Supplier / Material /
#   InOrder / OutOrder 等）在各路由函数内延迟导入（请求期才执行），
#   避免 app.py 模块加载期触发循环导入。
# - 日志复用 register_report_routes(app) 传入的 app.logger（与 app.py 原实现一致）。
# 注意：本文件顶部不用多行 """docstring""" 作为模块说明，会触发 lint 脚本
# strip_py_comments 把多行字符串折叠成一行、导致行号偏移、豁免注释检测失效。
from __future__ import annotations

import io
import json
import os

from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import login_required

from db import db
from utils import require_role


def _auto_register_report_template(app, report_type, title, template_path):
    """首次模板打印时把报表动态内置模板登记进模板中心（幂等）。

    仅在 target_code=report_<type> 没有任何模板记录时插入一条默认记录；
    任何失败仅记日志，不影响本次下载。
    """
    try:
        from doc_print_excel import report_target_code
        from app import ExcelPrintTemplate
        target_code = report_target_code(report_type)
        if ExcelPrintTemplate.query.filter_by(
                target_type='report', target_code=target_code).first():
            return
        static_prefix = os.path.join(app.static_folder, '')
        if not template_path.startswith(static_prefix):
            return
        rel = template_path[len(static_prefix):].replace(os.sep, '/')
        db.session.add(ExcelPrintTemplate(
            name=f'系统默认{title}模板', target_type='report',
            target_code=target_code, template_type='excel',
            excel_template_path=f'/static/{rel}', is_default=True))
        db.session.commit()
    except Exception as e:  # noqa: BLE001 登记失败不影响下载
        db.session.rollback()
        app.logger.error(f'报表模板自动登记失败({report_type}): {e}')


# no-test:reason=路由注册辅助函数，能力由 report_* 各路由测试覆盖
def register_report_routes(app):
    @app.route('/report')
    @login_required
    def report():
        from app import REPORT_DEFINITIONS, REPORT_TYPE_ORDER, get_default_warehouse, _get_report_definition
        report_cards = [
            {'report_type': 'material_movement', **_get_report_definition('material_movement')}
            if report_type == 'summary' else
            {'report_type': report_type, **REPORT_DEFINITIONS[report_type]}
            for report_type in REPORT_TYPE_ORDER
        ]
        # BUG-2026-09-07-009：卡片「导出」需要默认仓库上下文——
        # 显式带 warehouse_id 导出（与报表仓库必填规则一致），
        # 无默认仓库时前端禁用导出并提示，避免下载到一个 JSON 错误页。
        return render_template(
            'report.html',
            report_cards=report_cards,
            default_warehouse=get_default_warehouse(),
        )

    @app.route('/purchase_report')
    @login_required
    def purchase_report():
        available_reports = [
            {
                'title': '采购订单执行统计表',
                'description': '按采购单和物料查看采购数量、已入库、未入库和逾期情况。',
                'url': url_for('report_view', report_type='purchase_order_execution'),
                'icon': 'bi-bag-check',
            },
            {
                'title': '供应商采购汇总表',
                'description': '按供应商汇总采购订单、金额、已入库和未入库。',
                'url': url_for('report_view', report_type='supplier_purchase_summary'),
                'icon': 'bi-building',
            },
            {
                'title': '物料采购汇总表',
                'description': '按物料编号、名称和规格汇总采购数量和金额。',
                'url': url_for('report_view', report_type='material_purchase_summary'),
                'icon': 'bi-box',
            },
            {
                'title': '采购价格分析表',
                'description': '对比物料、供应商、均价、最低价、最高价和最近采购价。',
                'url': url_for('report_view', report_type='purchase_price_analysis'),
                'icon': 'bi-currency-yen',
            },
            {
                'title': '全部入库明细报表',
                'description': '按入库单据查询全部入库类型流水（采购/产品/其他入库），适合核对到货、数量和金额。',
                'url': url_for('report_view', report_type='in_detail'),
                'icon': 'bi-box-arrow-in-down',
            },
            {
                'title': '采购单执行跟踪',
                'description': '查看采购单下推、待入库、已入库和执行状态。',
                'url': url_for('purchase_order_list'),
                'icon': 'bi-bag-check',
            },
            {
                'title': '采购申请执行跟踪',
                'description': '查看采购申请转采购单后的执行进度。',
                'url': url_for('purchase_request_list'),
                'icon': 'bi-list-check',
            },
            {
                'title': '供应商档案',
                'description': '维护供应商资料，供采购单和采购统计使用。',
                'url': url_for('supplier_list'),
                'icon': 'bi-building',
            },
        ]
        # BUG-2026-09-07-010：缺失报表差距清单不再展示给最终用户
        # （产品路线图归开发台账跟踪，业务页面只呈现可用能力）
        return render_template(
            'purchase_report.html',
            available_reports=available_reports,
        )

    @app.route('/report/dashboard')
    @login_required
    def report_dashboard():
        from app import (build_report_dashboard_context, get_active_warehouses,
                         get_default_warehouse, resolve_request_warehouse)
        warehouses = get_active_warehouses()
        warehouse, warehouse_error = resolve_request_warehouse(request.args)
        if warehouse is None:
            return render_template(
                'report_dashboard.html',
                stats=None,
                chart_data=None,
                warehouses=warehouses,
                selected_warehouse_id=None,
            )
        stats, chart_data = build_report_dashboard_context(warehouse)
        return render_template(
            'report_dashboard.html',
            stats=stats,
            chart_data=chart_data,
            warehouses=warehouses,
            selected_warehouse_id=warehouse.id,
        )

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/report/dashboard/ai_insights', methods=['POST'])
    @login_required
    def report_dashboard_ai_insights():
        from app import (_ai_call_llm_chat, _ai_llm_configured, api_error,
                         build_report_dashboard_context, resolve_request_warehouse)
        warehouse, warehouse_error = resolve_request_warehouse(request.args)
        if warehouse is None:
            return api_error(warehouse_error or '请选择仓库', 400)
        if not _ai_llm_configured():
            return api_error('请先在系统设置中配置大模型API')
        stats, chart_data = build_report_dashboard_context(warehouse)
        
        # 计算环比增长率
        in_amount_mom = ((stats['month_in_amount'] - stats['last_month_in_amount']) / stats['last_month_in_amount'] * 100) if stats['last_month_in_amount'] > 0 else 0
        out_amount_mom = ((stats['month_out_amount'] - stats['last_month_out_amount']) / stats['last_month_out_amount'] * 100) if stats['last_month_out_amount'] > 0 else 0
        
        prompt = f"""你是仓库管理系统的数据分析师，请基于以下仪表盘数据生成简洁的业务洞察：

【核心指标】
- 本月入库金额：{stats['month_in_amount']:.2f} 元，共 {stats['month_in_count']} 笔单据
- 本月领料金额：{stats['month_out_amount']:.2f} 元，共 {stats['month_out_count']} 笔单据
- 库存总量：{stats['total_stock']:.2f}，共 {stats['material_count']} 种物料
- 库存金额：{stats['stock_value']:.2f} 元

【环比分析】
- 入库金额环比：{in_amount_mom:+.1f}%（上月 {stats['last_month_in_amount']:.2f} 元）
- 领料金额环比：{out_amount_mom:+.1f}%（上月 {stats['last_month_out_amount']:.2f} 元）

【趋势数据】近10天出入库数量趋势：{json.dumps(chart_data.get('trend', {}), ensure_ascii=False)[:500]}

请生成4-6条有价值的业务洞察，包括：
1. 环比分析（本月vs上月，增长/下降原因分析）
2. 出入库趋势分析（近10天波动情况及可能原因）
3. 库存健康度评估（是否有积压或缺货风险）
4. 可执行的改进建议
要求语言简洁专业，每条不超过80字，用换行分隔。"""
        try:
            insights = _ai_call_llm_chat(prompt)
            if not insights:
                return api_error('AI生成失败，请稍后重试')
            return jsonify({'status': 'success', 'insights': insights})
        except Exception as e:
            app.logger.error(f'报表AI解读失败: {e}')
            return jsonify({'status': 'error', 'msg': '生成失败，请稍后重试'}), 500

    @app.route('/report/view/<report_type>')
    @login_required
    def report_view(report_type):
        from app import (Supplier, _get_report_definition, get_active_warehouses,
                         get_default_warehouse, price_dimension_enabled)
        if report_type == 'summary' and request.args.get('summary_view') != 'daily':
            report_type = 'material_movement'
        definition = _get_report_definition(report_type)
        if definition is None:
            abort(404)
        # BUG-2026-10-17-014-F04（审计 §3.6）：价格维度关闭时资金类报表下线。
        if report_type == 'purchase_price_analysis' and not price_dimension_enabled():
            flash('价格维度未启用，采购价格分析已下线；如需启用请把系统设置 price_dimension_enabled 设为 1。', 'warning')
            return redirect(url_for('report_dashboard'))
        suppliers = Supplier.query.all()
        # BUG-2026-08-02-014：报表筛选器加仓库下拉框，传 warehouses / default_warehouse 给模板
        return render_template(
            'report_view.html',
            report_type=report_type,
            title=definition['title'],
            suppliers=suppliers,
            warehouses=get_active_warehouses(),
            default_warehouse=get_default_warehouse(),
            summary_labels=definition['summary_labels'],
            summary_types=definition['summary_types'],
            filters_config=definition['filters'],
        )

    @app.route('/report/api/query')
    @app.route('/report/api/<report_type>')
    @login_required
    def report_api_query(report_type=None):
        from app import (_build_report_excel_download, _build_report_filters,
                         _build_report_payload, _get_report_definition, api_error)
        report_type = report_type or (request.args.get('report_type') or '').strip()
        definition = _get_report_definition(report_type)
        if definition is None:
            return jsonify({'status': 'error', 'msg': 'Unsupported report type'}), 400
        from app import price_dimension_enabled
        if report_type == 'purchase_price_analysis' and not price_dimension_enabled():
            return jsonify({'status': 'error', 'msg': '价格维度未启用，采购价格分析已下线'}), 400

        try:
            filters = _build_report_filters()
            # P1-BUGFIX：AGENTS.md 仓库必填规则——报表查询未指定仓库且无默认仓库时拒绝返回数据
            if not filters.get('warehouse_id'):
                return api_error('请选择仓库', 400)
            if filters['export'] == 'excel':
                # BUG-2026-09-07-020：导出走分批流式下载——SQL 分页报表循环取批
                # 全量导出（不再受 REPORT_ROW_LIMIT 单次截断），内存路径报表
                # 仍截断并在文件内提示（019 引入，随迁移保留）。
                return _build_report_excel_download(report_type, filters)
            payload = _build_report_payload(report_type, filters)
        except ValueError as exc:
            # BUG-2026-08-16-019：业务异常详细记录，不把内部细节返回客户端
            app.logger.error(f'report_api_query ValueError({report_type}): {exc}', exc_info=True)
            return jsonify({'status': 'error', 'msg': '报表数据生成失败，请检查查询条件'}), 400

        return jsonify({
            'status': 'success',
            'title': payload['title'],
            'columns': payload['columns'],
            'data': payload['rows'],
            'summary': payload['summary'],
            'summary_labels': payload['summary_labels'],
            'summary_types': payload['summary_types'],
            'total': payload['total'],
            'page': filters['page'],
            'page_size': filters['page_size'],
            # BUG-2026-09-07-003：截断标记与真实行数透传前端显式提示；
            # total_pages 补齐分页元数据（AGENTS.md R1）
            'truncated': payload.get('truncated', False),
            'raw_total': payload.get('raw_total', payload['total']),
            'total_pages': payload.get('total_pages', 1),
        })

    @app.route('/report/print')
    @login_required
    def report_print_not_implemented():
        from app import api_error
        return api_error('报表打印功能未实现', code=404)

    @app.route('/report/<report_type>/print_excel')
    @login_required
    def report_print_excel(report_type):
        """按所选（或默认）Excel 模板生成报表 .xlsx 下载（PRINT-TEMPLATE-F04 A4）。

        - 筛选/仓库必填规则与 /report/api/<type> 完全一致（复用同一过滤器构造）；
        - target_code=report_<报表类型>：首次打印自动把动态内置模板登记进
          excel_print_template（幂等），之后可在模板中心在线编辑/设默认；
        - 无用户模板时 render_report_excel_print 回退动态内置模板。
        """
        from app import (_build_report_filters, _collect_report_export_rows,
                         _get_report_definition, api_error)
        from doc_print_excel import render_report_excel_print, report_target_code
        definition = _get_report_definition(report_type)
        if definition is None:
            return api_error('Unsupported report type', 400)
        try:
            filters = _build_report_filters()
            # AGENTS.md 仓库必填规则：报表查询未指定仓库且无默认仓库时拒绝返回数据
            if not filters.get('warehouse_id'):
                return api_error('请选择仓库', 400)
            # BUG-2026-09-07-019/020：模板打印语义 = 当前筛选全量（打印请求不带
            # export 参数，前端显式 delete；019 曾强制置位走 payload，020 起直接
            # 用分批收集：SQL 分页报表循环取批全量、内存路径报表全量构建），
            # 与页面分页彻底无关。
            columns, all_rows, truncated, raw_total = \
                _collect_report_export_rows(report_type, filters)
        except ValueError as exc:
            app.logger.error(f'report_print_excel ValueError({report_type}): {exc}',
                             exc_info=True)
            return api_error('报表数据生成失败，请检查查询条件', 400)
        if truncated:
            app.logger.warning(
                '[REPORT] print_excel %s 筛选结果 %s 行超出单次处理上限，模板打印仅含前 %s 行',
                report_type, raw_total, len(all_rows))
        result = render_report_excel_print(
            report_type, definition['title'], columns,
            all_rows,
            template_id=request.args.get('template_id', type=int),
            static_folder=app.static_folder)
        if result is None:
            return api_error('报表模板生成失败', 500)
        output, filename, template_path = result
        _auto_register_report_template(app, report_type, definition['title'],
                                       template_path)
        return send_file(
            output, download_name=filename, as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.route('/report/<report_type>/print_preview')
    @login_required
    def report_print_preview(report_type):
        """Preview current full report data using the selected Excel template, without writes."""
        from pathlib import Path
        from app import (_build_report_filters, _collect_report_export_rows,
                         _get_report_definition, _serialize_excel_value, ExcelPrintTemplate, Warehouse,
                         price_dimension_enabled)
        from doc_print_excel import report_target_code
        from print_fill import template_file_abspath
        from services.report_print_preview import build_report_print_preview

        definition = _get_report_definition(report_type)
        title = definition['title'] if definition else '报表'
        context = dict(title=title, sheets=[], template_name='', total=0, error=None)
        try:
            if definition is None:
                raise ValueError('不支持的报表类型')
            include_prices = price_dimension_enabled()
            if report_type == 'purchase_price_analysis' and not include_prices:
                raise ValueError('价格维度未启用，采购价格分析已下线')
            filters = _build_report_filters()
            if not filters.get('warehouse_id'):
                raise ValueError('请选择仓库')
            if db.session.get(Warehouse, filters['warehouse_id']) is None:
                raise ValueError('所选仓库不存在，请重新选择')
            query = ExcelPrintTemplate.query.filter_by(
                target_type='report', target_code=report_target_code(report_type),
                template_type='excel')
            raw_id = (request.args.get('template_id') or '').strip()
            template = None
            template_path = None
            if raw_id:
                if not raw_id.isdecimal() or len(raw_id) > 18 or int(raw_id) <= 0:
                    raise ValueError('所选打印模板无效，请重新选择')
                template = query.filter_by(id=int(raw_id)).first()
                if template is None:
                    raise ValueError('所选模板不存在或不属于当前报表，请重新选择')
            else:
                # Do not let a stale default prevent the in-memory built-in template.
                template = query.filter_by(is_default=True).first()
            if template is not None:
                candidate = template_file_abspath(template.excel_template_path, app.static_folder)
                root = Path(app.static_folder).resolve()
                candidate = Path(candidate).resolve() if candidate else None
                if candidate and candidate.is_relative_to(root) and candidate.is_file():
                    template_path = candidate
                elif raw_id:
                    raise ValueError('所选打印模板文件不存在或不可用，请修复或重新选择模板')
                else:
                    template = None
            columns, rows, truncated, raw_total = _collect_report_export_rows(report_type, filters)
            if truncated:
                raise ValueError('当前结果超出完整打印范围，请缩小筛选范围后打印，避免遗漏数据')
            rows = [dict(row, **{column['field']: _serialize_excel_value(column, row)
                               for column in columns if column.get('type') == 'status'})
                    for row in rows]
            context.update(sheets=build_report_print_preview(title, columns, rows,
                template_path=template_path, include_prices=include_prices),
                total=len(rows), template_name=template.name if template else '系统内置模板')
        except ValueError as exc:
            context['error'] = str(exc)
            return render_template('report_print_preview.html', **context), 400
        except Exception:
            app.logger.exception('报表打印预览失败(%s)', report_type)
            context['error'] = '打印预览生成失败，请检查模板和筛选条件后重试'
            return render_template('report_print_preview.html', **context), 500
        response = app.make_response(render_template('report_print_preview.html', **context))
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.route('/report/inout/print')
    @login_required
    def report_inout_print():
        from openpyxl import Workbook
        from sqlalchemy.orm import joinedload
        from app import (InOrder, OutOrder, InOrderItem, OutOrderItem, api_error, db,
                         resolve_request_warehouse, parse_date_value,
                         _warehouse_document_match_clause, _apply_status_date_filters,
                         _apply_in_order_search, _apply_out_order_search,
                         _apply_order_partner_text_filter,
                         _apply_header_or_item_contract_filters)
        # BUG-2026-10-20-003：默认统计只计已完成；显式 document_type 是列表打印，
        # 允许按当前状态筛选（未筛状态则全状态），并逐行展示状态，避免把草稿当实绩。
        warehouse, wh_err = resolve_request_warehouse(request.args)
        if wh_err:
            return api_error(wh_err, 400)
        document_type = (request.args.get('document_type') or '').strip()
        if document_type not in ('', 'in_order', 'out_order'):
            return api_error('单据类型不正确', 400)
        status = (request.args.get('status') or '').strip()
        if status not in ('', 'pending', 'completed'):
            return api_error('单据状态不正确', 400)
        if not document_type and not status:
            status = 'completed'
        start_raw = request.args.get('start_date') or request.args.get('date_start')
        end_raw = request.args.get('end_date') or request.args.get('date_end')
        start_date, end_date = parse_date_value(start_raw), parse_date_value(end_raw)
        if (start_raw and not start_date) or (end_raw and not end_date):
            return api_error('日期格式不正确', 400)
        if start_date and end_date and start_date > end_date:
            return api_error('开始日期不能晚于结束日期', 400)
        search = (request.args.get('search') or '').strip()
        contract_no = (request.args.get('contract_no') or '').strip()
        project_name = (request.args.get('project_name') or '').strip()
        wb = Workbook()
        for kind, model, item_model, fk, title, partner_title in (
            ('in_order', InOrder, InOrderItem, 'in_order_id', '入库统计', '供应商'),
            ('out_order', OutOrder, OutOrderItem, 'out_order_id', '领料统计', '领料部门'),
        ):
            ws = wb.active if kind == 'in_order' else wb.create_sheet(title)
            ws.title = title
            # 既有九列与 sheet 名不变，状态追加末尾，避免旧消费方列号漂移。
            ws.append(['单据编号', '日期', partner_title, '合同编号', '工程名称',
                       '物料编码', '物料名称', '数量', '金额', '状态'])
            if document_type and document_type != kind:
                continue
            # 明细级查询必须直接输出筛中的行，不能整单筛选后再循环全部 items。
            query = db.session.query(model, item_model).outerjoin(
                item_model, getattr(item_model, fk) == model.id).options(
                    joinedload(item_model.material))
            query = query.filter(_warehouse_document_match_clause(model.warehouse, warehouse))
            query = _apply_status_date_filters(query, model, status, start_date, end_date)
            if kind == 'in_order':
                query = query.options(joinedload(InOrder.supplier))
                supplier_id = request.args.get('supplier_id', type=int) or 0
                if supplier_id:
                    query = query.filter(InOrder.supplier_id == supplier_id)
                else:
                    query = _apply_order_partner_text_filter(
                        query, InOrder, request.args.get('supplier_name') or '')
                query = _apply_in_order_search(query, search)
                aliases = {'purchase_in': '采购入库', 'product_in': '产品入库',
                           'other_in': '其他入库', 'sales_return': '销售退货入库'}
                allowed_types = ('采购入库', '产品入库', '其他入库', '销售退货入库')
                allowed_sorts = {'order_no', 'date', 'supplier_id', 'business_type',
                                 'purpose', 'status', 'created_at', 'total_amount'}
            else:
                query = query.options(joinedload(OutOrder.department))
                query = _apply_out_order_search(query, search)
                aliases = {'requisition': '领料单', 'other_out': '其他出库',
                           'sale': '销售出库', 'sales': '销售出库',
                           'purchase_return': '采购退货出库', 'return_out': '采购退货出库'}
                allowed_types = ('领料单', '其他出库', '销售出库', '采购退货出库')
                allowed_sorts = {'order_no', 'date', 'department_id', 'customer',
                                 'business_type', 'purpose', 'status', 'created_at', 'total_amount'}
            raw_type = (request.args.get('type') or '').strip()
            if kind == 'out_order':
                raw_type = raw_type.lower()
            business_type = aliases.get(raw_type, (request.args.get('business_type') or '').strip())
            if business_type in allowed_types:
                query = query.filter(model.business_type == business_type)
            elif document_type == 'out_order':
                # 与领料明细列表默认范围相同；裸统计仍包含各类已完成出库。
                query = query.filter(db.or_(OutOrder.business_type == '领料单',
                                            OutOrder.business_type.is_(None)))
            query = _apply_header_or_item_contract_filters(
                query, model, item_model, fk, contract_no_filter=contract_no,
                project_name_filter=project_name, item_level=True)
            default_sort = 'created_at' if document_type else 'date'
            sort_by = request.args.get('sort', default_sort)
            if sort_by not in allowed_sorts:
                sort_by = default_sort
            sort_col = (db.func.coalesce(item_model.amount, model.total_amount)
                        if sort_by == 'total_amount' else getattr(model, sort_by))
            ascending = request.args.get('order') == 'asc'
            query = query.order_by(sort_col.asc() if ascending else sort_col.desc())
            # 全集导出：不消费 page/per_page；关联一次预加载，保持查询数与行数解耦。
            for order, item in query.all():
                if item is None and not document_type:
                    continue
                if kind == 'in_order':
                    partner = order.supplier.name if order.supplier else ''
                else:
                    partner = order.department.name if order.department else (order.customer or '')
                ws.append([
                    order.order_no,
                    order.date.strftime('%Y-%m-%d') if order.date else '',
                    partner,
                    item.contract_no if item and item.contract_no is not None else (order.contract_no or ''),
                    item.project_name if item and item.project_name is not None else (order.project_name or ''),
                    item.material.code if item and item.material else '',
                    item.material.name if item and item.material else '',
                    (item.quantity or 0) if item else 0,
                    (item.amount or 0) if item else 0,
                    {'pending': '待完成', 'completed': '已完成'}.get(order.status, order.status or ''),
                ])
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(
            output, download_name='inout_report.xlsx', as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    @app.route('/report/inout/export')
    @login_required
    def report_inout_export():
        return report_inout_print()

    @app.route('/report/stock/print')
    @login_required
    def report_stock_print():
        from openpyxl import Workbook
        from app import api_error, inventory_alert_enabled, price_dimension_enabled
        from services.stock_print_preview import (collect_stock_print_data,
            resolve_stock_print_template, stock_print_rows, build_stock_excel_print)
        # BUG-2026-08-12-005：库存导出必须输出仓库级库存，不得输出 Material.stock 跨仓总数；
        # 仓库解析规则与新版报表一致（显式参数校验 + 默认仓库回退，无默认 400）
        try:
            warehouse, materials, quantities = collect_stock_print_data(request.args)
            template, template_path = resolve_stock_print_template(request.args, app.static_folder)
        except ValueError as exc:
            return api_error(str(exc), 400)
        # Printing consumes the same filtered candidates/order as the screen,
        # without its page/per_page limit. Both Excel paths use this one list.
        # PRINT-TEMPLATE-F04 A6：库存查询列表接入 Excel 模板打印——
        # 显式 template_id 或存在默认模板记录时按模板渲染；否则回退原硬编码版式
        if request.args.get('template_mode') == '1':
            try:
                include_prices = price_dimension_enabled()
                output = build_stock_excel_print('库存查询（%s）' % warehouse.name,
                    stock_print_rows(warehouse, materials, quantities, include_prices=include_prices),
                    include_prices=include_prices, template_path=template_path)
            except ValueError as exc:
                return api_error(str(exc), 400)
            except Exception:
                app.logger.exception('库存查询模板下载失败')
                return api_error('打印文件生成失败，请检查模板和筛选条件后重试', 500)
            return send_file(output, download_name='stock_query.xlsx', as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        from doc_print_excel import render_table_excel_print
        if template is not None:
            from types import SimpleNamespace
            rows = [SimpleNamespace(**row) for row in stock_print_rows(
                warehouse, materials, quantities, include_prices=price_dimension_enabled())]
            result = render_table_excel_print(
                'stock_query', rows, template_id=template.id,
                static_folder=app.static_folder,
                title_extra=warehouse.name or '')
            if result is not None:
                output, filename = result
                return send_file(
                    output, download_name=filename, as_attachment=True,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        wb = Workbook()
        ws = wb.active
        ws.title = '库存报表'
        headers = ['物料编码', '物料名称', '规格型号', '单位', '分类', '当前库存']
        if inventory_alert_enabled():
            headers.extend(['最低库存', '安全库存', '库存状态'])
        ws.append(headers)
        status_map = {
            'low': '低于最低库存',
            'danger': '低于安全库存',
            'normal': '正常',
            'disabled': '未启用预警',
        }
        for m in materials:
            stock = quantities.get(m.id, 0)
            row = [
                m.code or '',
                m.name or '',
                m.spec or '',
                m.unit.name if m.unit else '',
                m.category.name if m.category else '',
                stock,
            ]
            if inventory_alert_enabled():
                # 库存状态按仓库级数量判定，口径与 _material_alert_status_values 一致
                min_stock = m.min_stock or 0
                safety_stock = max(m.reorder_point or 0, min_stock)
                if min_stock <= 0 and safety_stock <= 0:
                    alert_status = 'disabled'
                elif stock <= min_stock:
                    alert_status = 'low'
                elif stock <= safety_stock:
                    alert_status = 'danger'
                else:
                    alert_status = 'normal'
                row.extend([min_stock, safety_stock, status_map.get(alert_status, '正常')])
            ws.append(row)
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return send_file(output, download_name='stock_report.xlsx', as_attachment=True)

    @app.route('/report/stock/print_preview')
    @login_required
    def report_stock_print_preview():
        """Render full filtered stock through the selected existing list template, read-only."""
        from app import price_dimension_enabled
        from services.report_print_preview import build_report_print_preview
        from services.stock_print_preview import (collect_stock_print_data,
            resolve_stock_print_template, stock_print_rows, stock_print_columns)
        context = dict(title='库存查询', sheets=[], template_name='', total=0, error=None)
        try:
            warehouse, materials, quantities = collect_stock_print_data(request.args)
            template, path = resolve_stock_print_template(request.args, app.static_folder)
            include_prices = price_dimension_enabled()
            rows = stock_print_rows(warehouse, materials, quantities, include_prices=include_prices)
            columns = stock_print_columns()
            context.update(sheets=build_report_print_preview(
                '库存查询（%s）' % warehouse.name, columns, rows,
                template_path=path, include_prices=include_prices),
                total=len(rows), template_name=template.name if template else '系统内置模板')
        except ValueError as exc:
            context['error'] = str(exc)
            return render_template('report_print_preview.html', **context), 400
        except Exception:
            app.logger.exception('库存查询打印预览失败')
            context['error'] = '打印预览生成失败，请检查模板和筛选条件后重试'
            return render_template('report_print_preview.html', **context), 500
        response = app.make_response(render_template('report_print_preview.html', **context))
        response.headers['Cache-Control'] = 'no-store'
        return response
