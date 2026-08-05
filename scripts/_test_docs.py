"""单据模块按钮/状态流转全量测试。"""
import sys, time
sys.path.insert(0, '/workspace/scripts')
from _btn_harness import H, BASE

h = H()
if not h.login():
    print('LOGIN FAILED'); sys.exit(1)

# ---------- 列表页 + 导出 + 下载模板 + 新增页 ----------
docs = {
    '/purchase_request': ('采购申请', '/purchase_request/add'),
    '/purchase_order': ('采购订单', '/purchase_order/add'),
    '/in_order': ('采购入库', '/in_order/add'),
    '/in_order?type=product': ('产品入库', '/in_order/add?type=product'),
    '/out_order': ('领料出库', '/out_order/add'),
    '/other_in_order': ('其他入库', '/other_in_order/add'),
    '/other_out_order': ('其他出库', '/other_out_order/add'),
    '/transfer': ('库存调拨', '/transfer/add'),
    '/check': ('库存盘点', '/check/add'),
    '/adjustment': ('库存调整', '/adjustment/add'),
    '/after_sale_out': ('售后出库', '/after_sale_out/add'),
    '/sales': ('销售订单', '/sales/add'),
    '/sales/outbound': ('销售出库', '/sales/outbound'),
    '/subcontract': ('委外管理', '/subcontract'),
    '/requisition': ('工单领料', '/requisition/add'),
}
for path, (label, addp) in docs.items():
    h.page(path, f'列表[{label}] {path}')
    # 导出
    basepath = path.split('?')[0]
    h.export(f'{basepath}/export', f'导出[{label}]')
    # 下载模板（部分单据有）
    h.export(f'/export/template/{basepath.strip("/").split("/")[-1]}', f'模板[{label}]')
    # 新增页（GET 页面类）
    if addp and '?' not in addp:
        h.page(addp, f'新增页[{label}] {addp}')

# 特殊模板端点
h.export('/export/template/in_order', '采购入库模板')

h.report('单据模块-页面/导出')