# -*- coding: utf-8 -*-
"""模块4b：合同 + 委外链路深度检查。

结构注意：全程不得维持外层 app_context（g 泄漏坑，见 deep_audit_mod6）。
"""
import re
import sys
sys.path.insert(0, "/Coze/Drive/扣子/wms/scripts")
from deep_audit_lib import app_module, fresh_env, check, csrf_from, make_client
from app import db


def get_json(c, path):
    r = c.get(path)
    try:
        import json as _j
        return r.status_code, _j.loads(r.get_data(as_text=True))
    except Exception:
        return r.status_code, None


def mod4b_contract():
    # ---- seed ----
    with app_module.app.app_context():
        fresh_env()
        from app import Supplier
        db.session.add(Supplier(name="华中铜业", code="SUP-HZ"))
        db.session.commit()

    c = make_client()

    # ---- 合同 ----
    # C1. 合同列表页
    r = c.get("/contract")
    check("合同列表页 200", r.status_code == 200, f"st={r.status_code}")

    # C2. 新增合同（实际字段：contract_no + project_name，无 title/amount）
    tok = csrf_from(c, "/contract")
    r = c.post("/contract/add", data={
        "csrf_token": tok,
        "contract_no": "CT-2026-001",
        "project_name": "铜排采购年度框架",
        "remark": "深度检测用",
    }, follow_redirects=False)
    check("合同新增", r.status_code == 200, f"st={r.status_code}")

    # C3. 合同 API 列表（键名是 contracts）
    st, data = get_json(c, "/contract/api/list")
    ok = st == 200 and data and isinstance(data.get("contracts"), list) \
        and len(data["contracts"]) >= 1
    check("合同 api/list", ok, f"st={st} n={len((data or {}).get('contracts', []))}")

    # C4. 合同详情/编辑（详情是 JSON；编辑须带 contract_no + project_name）
    st, data = get_json(c, "/contract/1")
    ok = (st == 200 and data and data.get("status") == "success"
          and data.get("contract", {}).get("contract_no") == "CT-2026-001")
    check("合同详情 JSON", ok, f"st={st}")
    r = c.post("/contract/1/edit", data={
        "csrf_token": tok, "contract_no": "CT-2026-001",
        "project_name": "铜排采购年度框架v2",
        "remark": "编辑后"}, follow_redirects=False)
    check("合同编辑", r.status_code == 200, f"st={r.status_code}")

    # C5. 模板下载/导出
    r = c.get("/contract/download_template")
    check("合同模板下载", r.status_code == 200, f"st={r.status_code}")
    r = c.get("/contract/export")
    check("合同导出", r.status_code == 200, f"st={r.status_code}")


def mod4b_subcontract():
    # ---- seed：物料 + 供应商 + 仓库（委外发料需要库存）----
    with app_module.app.app_context():
        fresh_env()
        from app import Supplier
        from werkzeug.security import generate_password_hash
        db.session.add(Supplier(name="华中铜业", code="SUP-HZ"))
        db.session.commit()

    c = make_client()

    # S0. 委外列表/进度页
    for ep in ["/subcontract", "/subcontract/progress"]:
        r = c.get(ep)
        check(f"{ep} 200", r.status_code == 200, f"st={r.status_code}")

    # S1. 新增委外单
    tok = csrf_from(c, "/subcontract")
    r = c.post("/subcontract/add", data={
        "csrf_token": tok,
        "supplier_name": "华中铜业",
        "warehouse": "A仓",
        "remark": "委外镀锡",
    }, follow_redirects=False)
    check("委外单新增", r.status_code in (200, 302), f"st={r.status_code}")
    # 拿到单据 id
    with app_module.app.app_context():
        from app import SubcontractOrder
        so = SubcontractOrder.query.order_by(SubcontractOrder.id.desc()).first()
        sc_id = so.id if so else None
        sc_no = so.order_no if so else None
    check("委外单已入库", sc_id is not None, f"sc_id={sc_id}")

    if not sc_id:
        print("[abort] 无委外单可继续")
        return

    # S2. 详情页
    r = c.get(f"/subcontract/{sc_id}")
    check("委外详情 200", r.status_code == 200, f"st={r.status_code}")

    # S3. 添加委外明细（需先备料：给 M001 入库 100）
    with app_module.app.app_context():
        from app import User, Material
        from flask_login import login_user
        admin = User.query.filter_by(username="admin").first()
        mat = Material.query.filter_by(code="M001").first()
        with app_module.app.test_request_context("/"):
            login_user(admin)  # login_user 需请求 ctx；g 随该 ctx 销毁
            ok, err = app_module.add_stock(mat, 100, transaction_type="in",
                                            warehouse="A仓")
            db.session.commit()
    tok = csrf_from(c, f"/subcontract/{sc_id}")
    r = c.post(f"/subcontract/{sc_id}/item/add", data={
        "csrf_token": tok,
        "material_code": "M001",
        "quantity": "20",
    }, follow_redirects=False)
    check("委外明细添加", r.status_code in (200, 302), f"st={r.status_code}")

    # S4. 发料（issue）：直接在委外单上发料（material_code + quantity，仓库继承父单）
    r = c.post(f"/subcontract/{sc_id}/issue", data={
        "csrf_token": tok,
        "material_code": "M001",
        "quantity": "20"}, follow_redirects=False)
    check("委外发料", r.status_code in (200, 302), f"st={r.status_code}")
    with app_module.app.app_context():
        from app import Material
        mat = Material.query.filter_by(code="M001").first()
        stock_after_issue = mat.stock
    check("发料后库存 100-20=80", stock_after_issue == 80,
          f"stock={stock_after_issue}")

    # S5. 完工接收（receive）：material_code + quantity + price，仓库继承父单
    r = c.post(f"/subcontract/{sc_id}/receive", data={
        "csrf_token": tok,
        "material_code": "M001",
        "quantity": "20",
        "price": "12"}, follow_redirects=False)
    check("委外接收", r.status_code in (200, 302), f"st={r.status_code}")
    with app_module.app.app_context():
        from app import Material
        mat = Material.query.filter_by(code="M001").first()
        stock_after_receive = mat.stock
    check("接收后库存回补 80+20=100", stock_after_receive == 100,
          f"stock={stock_after_receive}")

    # S6. 提交审核 + 完成
    # 收货数量(20) ≥ 明细数量(20) 时 receive 已自动把单据推到 completed——
    # complete 接口此时正确返回 400「该委外单已完结」，属正常幂等拒绝。
    r = c.post(f"/subcontract/{sc_id}/submit", data={"csrf_token": tok},
               follow_redirects=False)
    check("委外提交审核（已完结单正确拒绝）",
          r.status_code in (200, 400), f"st={r.status_code}")
    r = c.post(f"/subcontract/{sc_id}/complete", data={"csrf_token": tok},
               follow_redirects=False)
    body = None
    try:
        body = r.get_json()
    except Exception:
        pass
    check("委外完成（幂等拒绝即正确）",
          r.status_code in (200, 302)
          or (r.status_code == 400 and "已完结" in str((body or {}).get("msg", ""))),
          f"st={r.status_code} msg={(body or {}).get('msg', '')}")
    with app_module.app.app_context():
        from app import SubcontractOrder
        so = db.session.get(SubcontractOrder, sc_id)
        final_status = so.status
    check("委外单终态 completed", final_status == "completed",
          f"status={final_status}")

    # S7. 导出
    r = c.get("/subcontract/export")
    check("委外导出", r.status_code == 200, f"st={r.status_code}")


if __name__ == "__main__":
    mod4b_contract()
    mod4b_subcontract()
