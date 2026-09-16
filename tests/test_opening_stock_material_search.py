# -*- coding: utf-8 -*-
"""BUG-2026-09-16-012 回归：期初编辑页物料改服务端搜索（去掉整库内嵌）。

问题：`/opening_stock/add` 与 `/opening_stock/<id>` 把 `Material.query.all()`
全部物料序列化进页面（materialData），物料上千时首屏 HTML 数 MB、前端再
全量 filter，又卡又违反 R1（把"全量"当默认）。

改造：
  - 两个编辑页路由不再查询/内嵌物料清单；
  - 联想：/api/material/search?keyword=（既有接口，web 会话可用），
    防抖 200ms + 序号防竞态，命中进本地缓存（materialCache/materialCodeIndex）；
  - 粘贴导入：新增 POST /opening_stock/materials/lookup 按编码批量预热
    （A8 pydantic 校验），payload 与移动端同一构造器 api_material_payload（R6）；
  - selectMaterial / parsePasteLines 一律查缓存，不再引用 materialData。

覆盖：
  T1 编辑/新建页不再整库内嵌物料（页面无 materialData，路由无 material_options）
  T2 lookup 接口：命中返回完整 payload 字段 + missing 清单
  T3 lookup 接口：入参校验（空列表/超 500/非列表/未登录）
  T4 lookup 与 /api/material/search 同一 payload 构造器（R6 静态防漂移）
  T5 模板静态契约：联想走服务端搜索、选中查缓存、粘贴导入先预热
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from app import app as flask_app  # noqa: E402
from app import Material, Unit, User, Warehouse, db  # noqa: E402

flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False

TEMPLATE = APP_DIR / "templates" / "opening_stock.html"
ROUTE_SRC = APP_DIR / "routes" / "opening_stock.py"


class TestOpeningStockMaterialSearch:
    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        # drop_all+create_all 全量重建（test_material_delete_missing_ai_table 模式）：
        # 全量 pytest 共享内存库下逐表 wipe 会撞 foreign_keys=ON 的残留行，
        # 大选择集运行时 setup 必挂；重建免疫未知残留。
        db.drop_all()
        db.create_all()

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()
        self.m1 = Material(code="M001", name="轴承6204", spec="内径20mm",
                           unit_id=unit.id, stock=10, price=25.5)
        self.m2 = Material(code="M002", name="电机", spec="1.5kW",
                           unit_id=unit.id, stock=3, price=800)
        db.session.add_all([self.m1, self.m2])
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def _login(self):
        from werkzeug.security import generate_password_hash
        if not User.query.filter_by(username="admin").first():
            db.session.add(User(
                username="admin",
                password_hash=generate_password_hash("admin"),
                role="admin",
                must_change_password=False,
            ))
            db.session.commit()
        self.client.post("/login",
                         data={"username": "admin", "password": "admin"},
                         content_type="application/x-www-form-urlencoded")

    # ---- T1 页面不再整库内嵌 ----

    def test_t1_pages_no_longer_embed_full_catalog(self):
        for url in ("/opening_stock/add",):
            resp = self.client.get(url)
            assert resp.status_code == 200
            html = resp.get_data(as_text=True)
            assert "const materialData" not in html, f"{url} 仍内嵌 materialData 整库物料"
            assert "materialCache" in html, f"{url} 缺少物料缓存结构"
        # 路由源码不再为渲染查询全部物料（剥掉注释再断言，避免注释里的说明文字误判）
        src = ROUTE_SRC.read_text(encoding="utf-8")
        code_only = "\n".join(
            line for line in src.splitlines() if not line.lstrip().startswith("#"))
        assert "material_options" not in code_only, "路由仍在构造 material_options 整库清单"
        assert "Material.query.all()" not in code_only, "路由仍存在 Material.query.all() 整库查询"

    # ---- T2 lookup 命中与 payload ----

    def test_t2_lookup_returns_payload_and_missing(self):
        resp = self.client.post("/opening_stock/materials/lookup",
                                json={"codes": ["M001", " m002 ", "NOPE"]})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] == "success"
        items = body["data"]["items"]
        by_code = {m["code"]: m for m in items}
        assert set(by_code) == {"M001", "M002"}
        m1 = by_code["M001"]
        # 网格需要的字段一个不能少（与 api_material_payload 同形状）
        for field in ("id", "code", "name", "spec", "unit", "price", "stock"):
            assert field in m1, f"payload 缺字段 {field}"
        assert m1["name"] == "轴承6204" and m1["unit"] == "个"
        assert m1["price"] == 25.5 and m1["stock"] == 10
        assert body["data"]["missing"] == ["NOPE"]

    # ---- T3 lookup 入参校验 ----

    def test_t3_lookup_validation(self):
        # 空列表
        r = self.client.post("/opening_stock/materials/lookup", json={"codes": []})
        assert r.status_code == 400
        # 全部空白编码
        r = self.client.post("/opening_stock/materials/lookup", json={"codes": [" ", ""]})
        assert r.status_code == 400
        # 超 500
        r = self.client.post("/opening_stock/materials/lookup",
                             json={"codes": [f"C{i}" for i in range(501)]})
        assert r.status_code == 400
        # 非列表
        r = self.client.post("/opening_stock/materials/lookup", json={"codes": "M001"})
        assert r.status_code == 400
        # 未登录（夹具常驻 app_context 会泄漏登录态，须先显式 logout——
        # 与 test_opening_stock_delete_all 同一踩坑，生产真实 HTTP 无此问题）
        anon = flask_app.test_client()
        anon.get("/logout")
        r = anon.post("/opening_stock/materials/lookup", json={"codes": ["M001"]})
        assert r.status_code in (302, 401)

    # ---- T4 payload 同一构造器（R6）----

    def test_t4_lookup_uses_shared_payload_builder(self):
        src = ROUTE_SRC.read_text(encoding="utf-8")
        m = re.search(r"def opening_stock_materials_lookup\(\):.*?(?=\n    # |\n    @app\.route|\Z)",
                      src, flags=re.DOTALL)
        assert m, "opening_stock_materials_lookup 定义丢失"
        body = m.group(0)
        assert "api_material_payload(" in body, (
            "lookup 未复用 api_material_payload——与 /api/material/search 字段会各自漂移"
        )

    # ---- T5 模板静态契约 ----

    def test_t5_template_static_contract(self):
        src = TEMPLATE.read_text(encoding="utf-8")
        # 联想走服务端搜索，不再前端全量 filter（注释里提到 materialData 字样不算，
        # 断言实际代码用法：声明与属性访问都不存在）
        assert "/api/material/search?keyword=" in src, "联想未接服务端搜索"
        assert "const materialData" not in src, "模板仍声明 materialData 整库数据"
        assert "materialData." not in src, "模板仍在使用 materialData 整库数据"
        # 选中查缓存
        select = re.search(r"function selectMaterial\(.*?\n}", src, flags=re.DOTALL)
        assert select and "materialCache.get" in select.group(0), "selectMaterial 未查缓存"
        # 粘贴导入先批量预热再解析
        confirm = re.search(r"function confirmPasteImport\(\).*?\n}", src, flags=re.DOTALL)
        assert confirm and "/opening_stock/materials/lookup" in confirm.group(0), (
            "confirmPasteImport 未批量预热物料缓存"
        )
        assert "extractPasteCodes" in src, "缺少 extractPasteCodes 预热辅助"
        # 防抖与竞态守卫
        assert "materialSearchSeq" in src and "clearTimeout" in src, "联想缺少防抖/竞态守卫"
