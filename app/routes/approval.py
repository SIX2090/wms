# 审批中心（approval）域路由：register-on-app 模式，endpoint 名与 app.py 原实现一致。
# 共享辅助函数（_get_order_list_filters / approve_purchase_request 等）仍留在 app.py，
# 各路由函数内部延迟导入，避免模块加载期循环导入。
from flask_login import login_required

from utils import require_role


# no-test:reason=路由注册辅助函数，能力由 approval_* 各路由测试覆盖
def register_approval_routes(app):
    @app.route('/approval')
    @login_required
    @require_role('admin', 'manager', 'purchase')
    def approval_list():
        from app import (
            PurchaseRequest,
            _apply_purchase_request_search,
            _apply_status_date_filters,
            _get_order_list_filters,
            render_template,
            request,
            url_for,
        )
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        # per_page 必须有下限保护，传入 0 或负数会让 paginate 抛 ValueError 导致接口 500
        per_page = max(1, per_page)
        if per_page not in [10, 20, 50, 100, 200]:
            per_page = 20
        status_filter, search, date_start, date_end, sort_by, sort_order = _get_order_list_filters(('pending', 'approved', 'rejected', 'completed'))
        allowed_sorts = {'request_no', 'date', 'applicant', 'department', 'status', 'created_at', 'total_amount'}
        if sort_by not in allowed_sorts:
            sort_by = 'created_at'

        query = PurchaseRequest.query
        query = _apply_status_date_filters(query, PurchaseRequest, status_filter, date_start, date_end)
        query = _apply_purchase_request_search(query, search)
        sort_col = getattr(PurchaseRequest, sort_by, PurchaseRequest.created_at)
        query = query.order_by(sort_col.asc() if sort_order == 'asc' else sort_col.desc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)

        approvals = []
        for item in pagination.items:
            approvals.append({
                'id': item.id,
                'type': '采购申请',
                'order_no': item.request_no,
                'applicant': item.applicant or (item.operator.username if item.operator else ''),
                'created_at': item.created_at,
                'date': item.date,
                'status': item.status,
                'detail_url': url_for('purchase_request_detail', id=item.id),
            })
        filters = {
            'status': status_filter,
            'search': search,
            'date_start': date_start.strftime('%Y-%m-%d') if date_start else '',
            'date_end': date_end.strftime('%Y-%m-%d') if date_end else '',
        }
        return render_template('approval.html',
                             approvals=approvals,
                             pagination=pagination,
                             per_page=per_page,
                             sort_by=sort_by,
                             sort_order=sort_order,
                             filters=filters,
                             pending_count=PurchaseRequest.query.filter_by(status='pending').count(),
                             approved_count=PurchaseRequest.query.filter_by(status='approved').count(),
                             rejected_count=PurchaseRequest.query.filter_by(status='rejected').count(),
                             total_count=PurchaseRequest.query.count())

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/approval/<int:id>/approve', methods=['POST'])
    @require_role('purchase')
    @login_required
    def approve_from_approval_center(id):
        from app import approve_purchase_request
        return approve_purchase_request(id)

    # pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务
    @app.route('/approval/<int:id>/reject', methods=['POST'])
    @require_role('purchase')
    @login_required
    def reject_from_approval_center(id):
        from app import reject_purchase_request
        return reject_purchase_request(id)