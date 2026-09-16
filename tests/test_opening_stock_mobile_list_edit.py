# -*- coding: utf-8 -*-
"""P1-C 手机端「已建账列表 + 编辑」回归。

用户诉求：手机端只能"建账"，建完之后看不到自己建了什么、建错了也没法改，
必须回 PC 端翻单据列表。本项给手机端补上：

  1. GET  /api/opening_stock            —— 已建账明细列表，**标准分页**
  2. POST /api/opening_stock/<line_id>  —— 按差额编辑数量/单价

重点回归（R1 分页口径）：
  此前该接口写死 `.limit(200)`，把**分页上限当成了业务上限**——
  第 201 条之后的建账记录手机端永远看不到，且响应不带 total，
  用户无法知道"本仓到底建了多少条"。修复后必须：
  - page / page_size 生效，响应带 total / page / page_size / total_pages；
  - total 基于**过滤后全集**，与分页彻底解耦；
  - built_total / built_quantity 基于**仓库全集**（不受 keyword / 分页影响）；
  - 建账条数超过 200 时必须能翻到第 201 条（本文件的核心断言）。

编辑口径（与 PC 端 POST /opening_stock/edit/<id> 一致）：
  - 按差额调整，Material.stock 只增减 delta（绝不覆盖式写总账）；
  - 不允许换物料 / 换仓库；
  - warehouse_id 为 NULL 的历史行拒改（归属未知时不动总账）。
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
from app import (  # noqa: E402
    Material,
    OpeningStock,
    OpeningStockDoc,
    StockTransaction,
    Unit,
    User,
    Warehouse,
    db,
)

flask_app.config["TESTING"] = True
flask_app.config["WTF_CSRF_ENABLED"] = False


class TestMobileOpeningStockList:
    """GET /api/opening_stock 分页与汇总口径。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        self._wipe()

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()
        self.unit = unit
        self.wh1 = Warehouse(code="W1", name="一号仓", status="active")
        self.wh2 = Warehouse(code="W2", name="二号仓", status="active")
        db.session.add_all([self.wh1, self.wh2])
        db.session.flush()
        self.mats = []
        for i in range(1, 6):
            m = Material(code="M%03d" % i, name="物料%d" % i, unit_id=unit.id, stock=0)
            db.session.add(m)
            self.mats.append(m)
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        self._wipe()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _wipe(self):
        for model in (OpeningStock, OpeningStockDoc, StockTransaction,
                      Material, Warehouse, Unit, User):
            db.session.query(model).delete()
        db.session.commit()

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

    def _seed(self, material, warehouse, quantity, price=1.0, date="2026-09-01"):
        """走 PC 端 /opening_stock/save 建账（与真实链路同口径）。"""
        resp = self.client.post("/opening_stock/save", json={
            "warehouse_id": warehouse.id, "date": date,
            "items": [{"material_id": material.id, "warehouse_id": warehouse.id,
                       "quantity": quantity, "price": price}],
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()["doc_id"]

    def _list(self, query):
        resp = self.client.get("/api/opening_stock" + query)
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body.get("status") in ("success", "ok"), body
        return body["data"]

    # ---- T1 基本返回结构 ----

    def test_t1_list_returns_pagination_metadata(self):
        self._seed(self.mats[0], self.wh1, 100)
        data = self._list("?warehouse_id=%d" % self.wh1.id)
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["material_code"] == "M001"
        assert item["quantity"] == 100
        assert item["warehouse_id"] == self.wh1.id
        # R1：必须返回完整分页元数据（此前一个都没有）
        for key in ("total", "page", "page_size", "total_pages",
                    "built_total", "built_quantity"):
            assert key in data, f"响应缺少分页/汇总字段 {key}"

    # ---- T2 仓库隔离 ----

    def test_t2_warehouse_isolation(self):
        self._seed(self.mats[0], self.wh1, 100)
        self._seed(self.mats[1], self.wh2, 40)
        d1 = self._list("?warehouse_id=%d" % self.wh1.id)
        d2 = self._list("?warehouse_id=%d" % self.wh2.id)
        assert [i["material_code"] for i in d1["items"]] == ["M001"]
        assert [i["material_code"] for i in d2["items"]] == ["M002"]
        assert d1["built_quantity"] == 100
        assert d2["built_quantity"] == 40

    # ---- T3 核心：不再有 200 条天花板 ----

    def test_t3_no_200_row_ceiling(self):
        """建 205 条（>200）后必须能翻到第 201 条 —— 这是本项的核心回归。

        修复前 `.limit(200)` 会让第 201 条之后永久不可见。
        """
        for i in range(205):
            material = Material(code="BULK%03d" % i, name="批量%d" % i,
                                unit_id=self.unit.id, stock=0)
            db.session.add(material)
            db.session.flush()
            self._seed(material, self.wh1, 1)

        first = self._list("?warehouse_id=%d&page=1&page_size=100" % self.wh1.id)
        assert first["total"] == 205, "total 必须是全集 205，不能被 limit 截断"
        assert first["total_pages"] == 3, "205 条 / 每页 100 → 3 页"
        assert first["built_total"] == 205, "汇总必须是全仓 205，与分页无关"
        assert len(first["items"]) == 100

        last = self._list("?warehouse_id=%d&page=3&page_size=100" % self.wh1.id)
        assert len(last["items"]) == 5, "第 3 页应剩 5 条（201~205）"
        assert last["page"] == 3

        # 第 201 条确实拿得到（把所有页的 id 收齐，断言覆盖全集）
        seen = set()
        for p in (1, 2, 3):
            page = self._list("?warehouse_id=%d&page=%d&page_size=100"
                              % (self.wh1.id, p))
            seen.update(i["id"] for i in page["items"])
        assert len(seen) == 205, "翻页必须能覆盖全部 205 条，不得有不可见记录"

    # ---- T4 汇总与分页解耦（R1） ----

    def test_t4_summary_decoupled_from_paging(self):
        for i in range(30):
            material = Material(code="SUM%03d" % i, name="汇总%d" % i,
                                unit_id=self.unit.id, stock=0)
            db.session.add(material)
            db.session.flush()
            self._seed(material, self.wh1, 2)
        page1 = self._list("?warehouse_id=%d&page=1&page_size=10" % self.wh1.id)
        assert len(page1["items"]) == 10, "明细应按 page_size 截断"
        assert page1["total"] == 30
        assert page1["built_total"] == 30, "汇总不得随分页缩小"
        assert page1["built_quantity"] == 60, "期初数量合计 = 30 × 2"

    def test_t4b_summary_unaffected_by_keyword(self):
        """keyword 只筛明细；built_total/built_quantity 仍是整仓口径。"""
        self._seed(self.mats[0], self.wh1, 100)
        self._seed(self.mats[1], self.wh1, 40)
        data = self._list("?warehouse_id=%d&keyword=M001" % self.wh1.id)
        assert [i["material_code"] for i in data["items"]] == ["M001"]
        assert data["total"] == 1, "total 基于过滤后全集"
        assert data["built_total"] == 2, "built_total 是整仓口径，不受 keyword 影响"
        assert data["built_quantity"] == 140

    # ---- T5 关键字搜索 ----

    def test_t5_keyword_matches_name_and_spec(self):
        self._seed(self.mats[0], self.wh1, 100)
        data = self._list("?warehouse_id=%d&keyword=物料1" % self.wh1.id)
        assert len(data["items"]) == 1
        assert data["items"][0]["material_code"] == "M001"

    # ---- T6 多单据累加在列表中表现为多行（口径不丢失） ----

    def test_t6_multi_doc_listed_as_separate_rows(self):
        """列表是**明细行**视角：同物料同仓两张单 = 两行，合计 150。

        与建账进度看板（矩阵视角，合并为 150）互补，不冲突。
        """
        self._seed(self.mats[0], self.wh1, 100)
        self._seed(self.mats[0], self.wh1, 50, date="2026-09-02")
        data = self._list("?warehouse_id=%d" % self.wh1.id)
        assert data["total"] == 2, "两张单应有两行明细"
        assert sum(i["quantity"] for i in data["items"]) == 150
        assert data["built_quantity"] == 150, "合计口径 = 跨单据累加"

    # ---- T7 登录要求 ----

    def test_t7_requires_login(self):
        anon = flask_app.test_client()
        anon.get("/logout")
        resp = anon.get("/api/opening_stock?warehouse_id=%d" % self.wh1.id)
        assert resp.status_code in (401, 302), resp.status_code


class TestMobileOpeningStockEdit:
    """POST /api/opening_stock/<line_id> 按差额编辑。"""

    def setup_method(self):
        self.ctx = flask_app.app_context()
        self.ctx.push()
        db.create_all()
        self._wipe()

        unit = Unit(code="PCS", name="个")
        db.session.add(unit)
        db.session.flush()
        self.unit = unit
        self.wh1 = Warehouse(code="W1", name="一号仓", status="active")
        self.wh2 = Warehouse(code="W2", name="二号仓", status="active")
        db.session.add_all([self.wh1, self.wh2])
        db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0)
        self.m2 = Material(code="M002", name="螺母", unit_id=unit.id, stock=0)
        db.session.add_all([self.m1, self.m2])
        db.session.commit()

        self.client = flask_app.test_client()
        self._login()

    def teardown_method(self):
        self._wipe()
        db.session.commit()
        db.session.remove()
        self.ctx.pop()

    def _wipe(self):
        for model in (OpeningStock, OpeningStockDoc, StockTransaction,
                      Material, Warehouse, Unit, User):
            db.session.query(model).delete()
        db.session.commit()

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

    def _seed(self, material, warehouse, quantity, price=1.0, date="2026-09-01"):
        resp = self.client.post("/opening_stock/save", json={
            "warehouse_id": warehouse.id, "date": date,
            "items": [{"material_id": material.id, "warehouse_id": warehouse.id,
                       "quantity": quantity, "price": price}],
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        return resp.get_json()["doc_id"]

    def _bearer_headers(self):
        """编辑接口走 @api_role_required，只认 Bearer Token（与 PC 会话不通用）。"""
        resp = self.client.post("/api/login",
                                json={"username": "admin", "password": "admin"})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        token = resp.get_json()["data"]["token"]
        return {"Authorization": "Bearer %s" % token}

    def _line_id(self, material, warehouse):
        row = OpeningStock.query.filter_by(
            material_id=material.id, warehouse_id=warehouse.id
        ).first()
        assert row is not None, "期初明细行应存在"
        return row.id

    def _edit(self, line_id, payload):
        return self.client.post("/api/opening_stock/%d" % line_id, json=payload,
                                headers=self._bearer_headers())

    def _stock(self, material):
        db.session.expire_all()
        return Material.query.get(material.id).stock

    # ---- T1 改数量：按差额调整总账 ----

    def test_t1_edit_quantity_adjusts_stock_by_delta(self):
        self._seed(self.m1, self.wh1, 100)
        assert self._stock(self.m1) == 100
        line_id = self._line_id(self.m1, self.wh1)

        resp = self._edit(line_id, {"quantity": 60})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        body = resp.get_json()
        assert body["status"] in ("success", "ok"), body
        assert body["data"]["quantity"] == 60
        assert body["data"]["delta"] == -40, "delta 必须是 60 - 100 = -40"

        assert self._stock(self.m1) == 60, "总账必须是差额调整后的 60，不是 160"

    def test_t1b_edit_upward(self):
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        resp = self._edit(line_id, {"quantity": 150})
        assert resp.status_code == 200
        assert resp.get_json()["data"]["delta"] == 50
        assert self._stock(self.m1) == 150

    # ---- T2 部分字段更新：PATCH 语义 ----

    def test_t2_only_price_updates_keeps_quantity(self):
        self._seed(self.m1, self.wh1, 100, price=1.0)
        line_id = self._line_id(self.m1, self.wh1)
        resp = self._edit(line_id, {"price": 3.5})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        data = resp.get_json()["data"]
        assert data["quantity"] == 100, "未提交数量时必须保留原数量"
        assert data["price"] == 3.5
        assert data["amount"] == 350.0, "金额 = 数量 × 新单价"
        assert self._stock(self.m1) == 100, "只改单价不动库存"

    def test_t2b_empty_payload_rejected(self):
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        resp = self._edit(line_id, {})
        assert resp.status_code == 400, "什么都不提交应 400，而不是静默成功"

    # ---- T3 参数校验 ----

    def test_t3_invalid_quantity_rejected(self):
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        for bad in ("abc", -5, ""):
            resp = self._edit(line_id, {"quantity": bad})
            assert resp.status_code == 400, f"数量 {bad!r} 应 400，实际 {resp.status_code}"
            body = resp.get_json()
            assert body["status"] == "error"
        assert self._stock(self.m1) == 100, "非法输入不得改动库存"

    def test_t3b_not_found(self):
        resp = self._edit(999999, {"quantity": 1})
        assert resp.status_code == 404

    # ---- T4 不允许换物料/换仓库 ----

    def test_t4_cannot_change_material_or_warehouse(self):
        """提交里带 material_code / warehouse_id 必须被忽略（不允许换）。"""
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        resp = self._edit(line_id, {
            "quantity": 80,
            "material_code": "M002",
            "warehouse_id": self.wh2.id,
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        row = OpeningStock.query.get(line_id)
        assert row.material_id == self.m1.id, "物料不得被换掉"
        assert row.warehouse_id == self.wh1.id, "仓库不得被换掉"
        assert self._stock(self.m2) == 0, "另一物料库存不得被牵连"

    # ---- T5 NULL 仓库历史行拒改 ----

    def test_t5_null_warehouse_row_rejected(self):
        """warehouse_id 为 NULL 的历史行归属未知，手机端不得改（不动总账）。"""
        doc = OpeningStockDoc.query.first()
        row = OpeningStock(
            doc_id=None, material_id=self.m1.id, warehouse_id=None,
            date=None, quantity=50, price=1.0, amount=50.0,
        )
        db.session.add(row)
        db.session.commit()
        material_stock_before = self._stock(self.m1)

        resp = self._edit(row.id, {"quantity": 10})
        assert resp.status_code == 400, "无仓库归属的行应拒改"
        assert "仓库" in resp.get_json()["msg"]
        assert self._stock(self.m1) == material_stock_before, "不得改动总账"

    # ---- T6 流水正确性 ----

    def test_t6_writes_opening_transaction_with_delta(self):
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        db.session.query(StockTransaction).delete()
        db.session.commit()

        self._edit(line_id, {"quantity": 70})
        txns = StockTransaction.query.filter_by(
            material_id=self.m1.id, transaction_type="opening"
        ).all()
        assert len(txns) == 1, "调整应写一条 opening 流水"
        assert txns[0].quantity == -30, "流水数量必须是差额 -30，不是新值 70"
        assert txns[0].warehouse_id == self.wh1.id, "流水必须落 warehouse_id"

    # ---- T7 仓库隔离：改 A 仓不影响 B 仓 ----

    def test_t7_edit_isolated_between_warehouses(self):
        self._seed(self.m1, self.wh1, 100)
        self._seed(self.m1, self.wh2, 40)
        assert self._stock(self.m1) == 140

        line_a = self._line_id(self.m1, self.wh1)
        self._edit(line_a, {"quantity": 10})
        assert self._stock(self.m1) == 50, "总账 = 改后的 10 + B 仓 40"

        row_b = OpeningStock.query.filter_by(
            material_id=self.m1.id, warehouse_id=self.wh2.id
        ).first()
        assert row_b.quantity == 40, "B 仓期初不得被牵连"

    # ---- T8 登录要求 ----

    def test_t8_requires_login(self):
        self._seed(self.m1, self.wh1, 100)
        line_id = self._line_id(self.m1, self.wh1)
        anon = flask_app.test_client()
        anon.get("/logout")
        resp = anon.post("/api/opening_stock/%d" % line_id, json={"quantity": 1})
        assert resp.status_code in (401, 302), resp.status_code

class TestMobileOpeningStockStaticContract:
    """静态契约：Android 侧确实接上了新接口（防止后端改了 App 没跟上）。"""

    SRC = (ROOT / "app" / "android-native-wms" / "app" / "src" / "main"
           / "java" / "com" / "factory" / "wms")
    KOTLIN_API = SRC / "data" / "api" / "WmsApiService.kt"
    KOTLIN_MODELS = SRC / "data" / "model" / "OpeningStockModels.kt"
    KOTLIN_REPO = SRC / "data" / "repository" / "WmsRepository.kt"
    KOTLIN_VM = SRC / "ui" / "viewmodel" / "opening" / "OpeningStockViewModel.kt"
    KOTLIN_SCREEN = SRC / "ui" / "screens" / "OpeningStockScreen.kt"
    ROUTE_SRC = ROOT / "app" / "routes" / "native_api.py"

    def test_t9_route_has_no_hardcoded_200_limit(self):
        """R1：列表接口不得再出现 `.limit(200)` 这种把分页上限当业务上限的写法。

        注释与 docstring 里为了说明历史问题会提到这个字符串，先剥掉再断言。
        """
        src = self.ROUTE_SRC.read_text(encoding="utf-8")
        start = src.index("def native_api_opening_stock_list")
        end = src.index("def native_api_opening_stock_update")
        segment = src[start:end]
        # 剥掉三引号 docstring 与 # 行注释（只留真正的代码）
        segment = re.sub(r'""".*?"""', "", segment, flags=re.S)
        segment = re.sub(r"#[^\n]*", "", segment)
        assert "limit(200)" not in segment, "已建账列表不得写死 200 条上限"
        assert "_mobile_paginate" in segment, "必须走统一分页助手"
        assert "'total'" in segment or '"total"' in segment, "必须返回 total"

    def test_t10_list_data_has_pagination_fields(self):
        src = self.KOTLIN_MODELS.read_text(encoding="utf-8")
        start = src.index("data class OpeningStockListData")
        segment = src[start:start + 900]
        assert "totalPages" in segment, "Kotlin 模型必须解析 total_pages"
        assert "builtTotal" in segment, "Kotlin 模型必须解析 built_total"
        assert "builtQuantity" in segment, "Kotlin 模型必须解析 built_quantity"
        assert '"total_pages"' in segment, "需用 SerializedName 映射 snake_case"

    def test_t11_api_service_has_paging_and_edit(self):
        src = self.KOTLIN_API.read_text(encoding="utf-8")
        assert '@Query("page")' in src, "列表接口必须支持 page 参数"
        assert '@Query("page_size")' in src, "列表接口必须支持 page_size 参数"
        assert "api/opening_stock/{lineId}" in src, "必须有编辑明细接口"

    def test_t11b_repository_exposes_page_and_update(self):
        src = self.KOTLIN_REPO.read_text(encoding="utf-8")
        assert "suspend fun getOpeningStockPage(" in src, "仓储层需暴露分页列表方法"
        assert "suspend fun updateOpeningStock(" in src, "仓储层需暴露编辑方法"
        assert "api.updateOpeningStock(" in src, "编辑方法必须真正调用接口"

    def test_t12_viewmodel_declares_built_list_api(self):
        """VM↔Screen 配对（同类事故历史：BUG-2026-09-12-001）。

        Screen 调用的每个 VM 方法都必须真实存在，否则 Kotlin 编译失败、
        APK 构建挂掉（CI Android APK Build）。
        """
        vm_src = self.KOTLIN_VM.read_text(encoding="utf-8")
        for method in ("loadBuiltItems", "loadMoreBuiltItems", "searchBuiltItems",
                       "startEditing", "cancelEditing", "submitEdit"):
            assert re.search(r"fun\s+%s\s*\(" % method, vm_src), (
                "OpeningStockViewModel 缺少 %s 声明 —— Screen 调用会导致 Kotlin 编译失败"
                % method
            )
        # 状态字段也要在
        for field in ("builtItems", "builtTotal", "builtQuantity", "editingItem"):
            assert field in vm_src, "UiState 缺少字段 %s" % field

    def test_t13_screen_uses_declared_methods_only(self):
        """反向检查：Screen 里 `viewModel.X(` 的每个 X 都能在 VM 里找到声明。"""
        screen_src = self.KOTLIN_SCREEN.read_text(encoding="utf-8")
        vm_src = self.KOTLIN_VM.read_text(encoding="utf-8")
        # 先算 Screen 里出现的所有调用名（仅限 opening 页自己新增的那批）
        calls = set(re.findall(r"viewModel\.(\w+)\s*\(", screen_src))
        missing = sorted(
            name for name in calls
            if not re.search(r"fun\s+%s\s*\(" % re.escape(name), vm_src)
        )
        assert not missing, ("Screen 调用了 ViewModel 上不存在的方法（Kotlin 必编译失败）："
                             + ", ".join(missing))

    def test_t14_screen_has_edit_dialog_and_list_section(self):
        src = self.KOTLIN_SCREEN.read_text(encoding="utf-8")
        assert "editBuiltQuantity" in src or "builtEdit" in src or "editingItem" in src, (
            "Screen 必须接入编辑弹窗状态"
        )
        assert "建账明细" in src or "已建账" in src, "Screen 必须有已建账列表区块"
