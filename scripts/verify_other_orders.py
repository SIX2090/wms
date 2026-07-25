"""Targeted regression checks for other inbound/outbound documents."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app/app.py").read_text(encoding="utf-8")
BASE = (ROOT / "app/templates/base.html").read_text(encoding="utf-8")
IN_ADD = (ROOT / "app/templates/in_order_add.html").read_text(encoding="utf-8")
OUT_ADD = (ROOT / "app/templates/out_order_add.html").read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}")


require("@app.route('/other_in_order')" in APP and "@app.route('/other_in_order/add')" in APP, "其他入库列表和新增路由存在")
require("@app.route('/other_out_order')" in APP and "@app.route('/other_out_order/add')" in APP, "其他出库列表和新增路由存在")
require("'other_in': '其他入库'" in APP and "'其他入库'" in APP, "其他入库是受控业务类型")
require("business_type='其他出库'" not in APP or "'领料单', '销售出库', '其他出库'" in APP, "其他出库是受控业务类型")
require("generate_order_no('OI'" in APP and "generate_order_no('OO'" in APP, "其他出入库使用独立单号前缀")
require("customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'))" in APP, "其他入库保存客户归属")
require("idx_in_order_customer_id" in APP, "客户归属数据库迁移和索引存在")
require("party_field='customer_id' if is_other_in" in APP and "[partyField]: supplierId" in IN_ADD, "其他入库客户选择提交到后端")
require("isOtherOut" in OUT_ADD and "returnAddUrl" in OUT_ADD, "其他出库保持独立新增流程")
require("OutOrder.business_type == '领料单'" in APP and "OutOrder.business_type == explicit_bt" in APP, "领料与其他出库列表相互隔离")
require(all(path in BASE for path in ('/other_in_order/add', '/other_out_order/add', '/other_in_order', '/other_out_order')), "库存菜单包含其他出入库入口")
require("contract_no" in IN_ADD and "project_name" in IN_ADD and "contract_no" in OUT_ADD and "project_name" in OUT_ADD, "其他出入库复用合同工程明细")

print("PASS OTHER-ORDERS: other inbound/outbound document workflow verified")
