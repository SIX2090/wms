# -*- coding: utf-8 -*-
"""P1-A 期初建账进度（未建账物料清单）回归。

用户诉求（原话）：「期初录到一半根本不知道漏了哪个物料，只能反复翻单据对账」。

新增 /opening_stock/progress 建账进度看板：行=物料、列=仓库，
格子显示该 (物料, 仓库) 的**累计**期初数量，空格子即"未建账"。

口径（INVENTORY_TRUTH.md §2.1.2）：
  - 某 (物料, 仓库) 期初 = 该组合下所有单据明细行 quantity 之和（多单据累加，
    绝不取单行当余额）；
  - quantity 合计为 0 视为未建账（录 0 与没录在库存上等价）；
  - warehouse_id 为 NULL 的历史行单列"未指定仓库"列，不猜归属。

覆盖：
  T1 页面渲染：进度统计 + 仓库列头 + 物料行
  T2 已建账格子显示数量、未建账格子显示"未建账"
  T3 多单据累加口径：同物料同仓两张单，进度页显示合计数（非单行）
  T4 只建了部分仓库时，该物料仍算已建账，未建的那个仓显示未建账
  T5 数量 0 的行按未建账处理
  T6 only_gap=1 只返回完全未建账的物料；only_gap=0 返回全部
  T7 停用仓库不出现在列头
  T8 历史 NULL 仓库行单列"未指定仓库"，且不污染真实仓库列
  T9 全库统计（stats）不受分页影响 —— 进度条分母是全库物料数（R1）
  T10 关键字筛选按编码/名称/规格
  T11 导出 CSV：未建账清单可直接下载，含表头；only_gap=0 时导全量
  T12 静态断言：列表页有「建账进度」入口
"""
from __future__ import annotations

import os
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

LIST_TEMPLATE = APP_DIR / "templates" / "opening_stock_list.html"
PROGRESS_TEMPLATE = APP_DIR / "templates" / "opening_stock_progress.html"


class TestOpeningStockProgress:
    """建账进度看板的页面与口径契约。"""

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
        self.wh3 = Warehouse(code="W3", name="停用仓", status="inactive")
        db.session.add_all([self.wh1, self.wh2, self.wh3])
        db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", spec="M6", unit_id=unit.id, stock=0)
        self.m2 = Material(code="M002", name="螺母", spec="M6", unit_id=unit.id, stock=0)
        self.m3 = Material(code="M003", name="垫片", unit_id=unit.id, stock=0)
        db.session.add_all([self.m1, self.m2, self.m3])
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

    def _save(self, payload):
        resp = self.client.post("/opening_stock/save", json=payload)
        return resp.status_code, resp.get_json()

    def _page(self, query=""):
        resp = self.client.get("/opening_stock/progress" + query)
        assert resp.status_code == 200, f"进度页应 200，实际 {resp.status_code}"
        return resp.get_data(as_text=True)

    def _seed(self, material, warehouse, quantity, price=1.0, date="2026-09-01"):
        status, body = self._save({
            "warehouse_id": warehouse.id, "date": date,
            "items": [{"material_id": material.id, "warehouse_id": warehouse.id,
                       "quantity": quantity, "price": price}],
        })
        assert status == 200, body
        return body["doc_id"]

    # ---- T1 页面渲染 ----

    def test_t1_progress_page_renders(self):
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0")
        assert "建账进度" in html
        assert "一号仓" in html and "二号仓" in html, "每个启用仓库应成一列"
        assert "M001" in html and "螺丝" in html, "应列出物料行"

    def test_t1b_default_shows_gap_materials(self):
        """默认（只看未建账）应列出完全未建账的物料，便于逐条补录。"""
        self._seed(self.m1, self.wh1, 100)
        html = self._page()
        assert "M002" in html, "未建账物料应出现在默认（只看未建账）视图"

    # ---- T2 已建账/未建账格子 ----

    def test_t2_cell_shows_qty_or_unbuilt(self):
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0")
        assert "100.00" in html, "已建账格子应显示数量"
        assert "未建账" in html, "未建账格子应有明确文案"

    # ---- T3 多单据累加 ----

    def test_t3_multi_doc_sums_not_single_row(self):
        """同物料同仓两张单（100 + 50），进度页必须显示 150 而非任意单行。"""
        self._seed(self.m1, self.wh1, 100)
        self._seed(self.m1, self.wh1, 50, date="2026-09-02")
        html = self._page("?only_gap=0")
        assert "150.00" in html, "必须按期初累计口径显示 150（多单据累加）"
        assert "100.00" not in html, "不得显示单张单据的数量"

    # ---- T4 部分建账 ----

    def test_t4_partial_built_counts_as_built(self):
        """m1 只在 wh1 建了账 → 该物料算已建账，wh2 格子显示未建账。"""
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=1")
        # 只看未建账时，m1 不该出现（它已在 wh1 建账）
        assert "M001" not in html, "只建了部分仓库的物料不应出现在「只看未建账」里"
        assert "M002" in html and "M003" in html, "完全没建账的物料应出现"

        html_all = self._page("?only_gap=0")
        assert "M001" in html_all
        assert "1/2" in html_all, "建账进度徽章应显示 1/2"

    # ---- T5 数量 0 视为未建账 ----

    def test_t5_zero_qty_treated_as_unbuilt(self):
        self._seed(self.m1, self.wh1, 0)
        html = self._page("?only_gap=1")
        assert "M001" in html, "期初数量为 0 应视为未建账（录 0 与没录等价）"

    # ---- T6 only_gap 开关 ----

    def test_t6_only_gap_toggle(self):
        self._seed(self.m1, self.wh1, 100)
        gap_html = self._page("?only_gap=1")
        all_html = self._page("?only_gap=0")
        assert "M001" not in gap_html
        assert "M001" in all_html
        # 全部视图应列出三个物料
        assert "M002" in all_html and "M003" in all_html

    # ---- T7 停用仓库 ----

    def test_t7_inactive_warehouse_excluded(self):
        """停用仓库不得作为列头出现（只比列头区间，避免撞口径说明文案）。"""
        html = self._page("?only_gap=0")
        head_start = html.find("<thead")
        head_end = html.find("</thead>")
        assert head_start != -1 and head_end != -1
        head = html[head_start:head_end]
        assert "一号仓" in head and "二号仓" in head
        assert "停用仓" not in head, "停用仓库不应作为建账目标出现在列头"

    # ---- T8 历史 NULL 仓库行 ----

    def test_t8_null_warehouse_row_separate_column(self):
        """历史直连台账（warehouse_id=NULL）不猜归属，单列一栏展示。"""
        db.session.add(OpeningStock(
            material_id=self.m1.id, warehouse_id=None, quantity=77.0,
            price=1.0, amount=77.0, date=None,
        ))
        db.session.commit()
        html = self._page("?only_gap=0")
        assert "未指定仓库" in html, "有 NULL 仓库历史行时应出现该列"
        assert "77.00" in html, "历史行的数量应可见"
        # 关键：不得把 77 摊到真实仓库列上
        idx_wh1 = html.find("一号仓")
        assert idx_wh1 != -1

    def test_t8b_null_warehouse_row_counts_as_built(self):
        """只有 NULL 仓库行的物料算已建账（库存上确实有数），不算完全未建账。"""
        db.session.add(OpeningStock(
            material_id=self.m1.id, warehouse_id=None, quantity=77.0,
            price=1.0, amount=77.0, date=None,
        ))
        db.session.commit()
        gap_html = self._page("?only_gap=1")
        assert "M001" not in gap_html, "有历史期初数量的物料不算完全未建账"

    # ---- T9 全库统计不受分页影响 ----

    def test_t9_stats_are_global_not_paged(self):
        """R1：进度条分母必须是全库物料数，不能拿当前页行数当总量。"""
        self._seed(self.m1, self.wh1, 100)
        # 每页 1 条，逼出分页
        html = self._page("?only_gap=0&per_page=20")
        # 物料总数 3、已建账 1、未建账 2（全库口径）
        assert "物料总数" in html and "未建账物料" in html
        # 默认只看未建账时当前页只有 2 行，但统计里总数仍是 3
        assert ">3<" in html.replace("\n", ""), "物料总数应为全库 3"

    # ---- T10 关键字筛选 ----

    def test_t10_search_filter(self):
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0&search=螺母")
        assert "M002" in html
        assert "M003" not in html, "关键字不匹配的物料应被过滤"

    def test_t10b_search_by_spec(self):
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0&search=M6")
        assert "M001" in html and "M002" in html, "规格应参与匹配"
        assert "垫片" not in html

    # ---- T11 导出 CSV ----

    def test_t11_export_csv(self):
        self._seed(self.m1, self.wh1, 100)
        resp = self.client.get("/opening_stock/progress/export?only_gap=1")
        assert resp.status_code == 200
        assert "csv" in (resp.headers.get("Content-Type") or "").lower()
        body = resp.get_data().decode("utf-8-sig")
        assert "物料编码" in body and "状态" in body
        assert "M002" in body, "未建账物料应出现在导出清单"
        assert "M001" not in body, "only_gap=1 时已建账物料不应导出"

    def test_t11b_export_all(self):
        self._seed(self.m1, self.wh1, 100)
        resp = self.client.get("/opening_stock/progress/export?only_gap=0")
        body = resp.get_data().decode("utf-8-sig")
        assert "M001" in body and "M002" in body

    # ---- T12 列表页入口 ----

    def test_t12_list_page_has_progress_entry(self):
        resp = self.client.get("/opening_stock")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "/opening_stock/progress" in html, "单据列表页应有建账进度入口"
        assert "建账进度" in html

    def test_t13_progress_requires_login(self):
        """未登录访问进度页应被重定向到登录页（不得泄露物料与库存）。

        夹具常驻 app_context 会泄漏登录态，须先显式 logout——与
        test_opening_stock_material_search / test_opening_stock_delete_all
        同一踩坑，生产真实 HTTP 无此问题。
        """
        anon = flask_app.test_client()
        anon.get("/logout")
        resp = anon.get("/opening_stock/progress")
        assert resp.status_code in (302, 401, 403), "未登录应拦截"

    def test_t13b_export_requires_login(self):
        """未登录不得下载建账进度清单。"""
        anon = flask_app.test_client()
        anon.get("/logout")
        resp = anon.get("/opening_stock/progress/export")
        assert resp.status_code in (302, 401, 403), "未登录应拦截导出"

    def test_t14_template_static_contract(self):
        """静态契约：模板存在且引用统计/导出/复制能力（防误删）。"""
        assert PROGRESS_TEMPLATE.exists(), "进度页模板必须存在"
        src = PROGRESS_TEMPLATE.read_text(encoding="utf-8")
        assert "建账进度" in src
        assert "/opening_stock/progress/export" in src, "应有导出入口"
        assert "copyUnbuiltRow" in src, "应有复制物料编码能力"
        assert "stats.percent" in src, "应有完成度进度条"

        list_src = LIST_TEMPLATE.read_text(encoding="utf-8")
        assert "/opening_stock/progress" in list_src

    def test_t15_tojson_inline_handler_uses_single_quote_attr(self):
        """回归：tojson 产出双引号 JSON，用双引号包属性会截断 onclick。

        实测踩坑——`onclick="copyUnbuiltRow({{ r.code|tojson }})"` 渲染成
        `onclick="copyUnbuiltRow("M-0001")"`，浏览器解析出的属性被提前截断，
        按钮点击无任何反应且不报错（静默失效，最坏的一类）。全站既有写法
        （opening_stock_list / print_routing）统一用单引号包属性。
        """
        src = PROGRESS_TEMPLATE.read_text(encoding="utf-8")
        for line in src.splitlines():
            if "tojson" in line and "onclick" in line:
                assert "onclick='" in line, (
                    f"tojson 内联处理器必须用单引号包属性，实际：{line.strip()}")
        assert "onclick='copyUnbuiltRow(" in src, "复制按钮的内联处理器丢失"

    def test_t16_rendered_onclick_is_well_formed(self):
        """渲染后 html 里复制按钮的 onclick 属性必须完整可用（端到端防截断）。"""
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0")
        import re
        m = re.search(r"onclick='([^']*copyUnbuiltRow[^']*)'", html)
        assert m, "渲染结果里找不到完整的 copyUnbuiltRow onclick 属性"
        handler = m.group(1)
        assert "M001" in handler, "处理器应带上物料编码"
        # 属性内部不应出现裸的双引号截断（已被 HTML 实体化才安全）
        assert 'onclick="copyUnbuiltRow(' not in html, "不得退化成双引号包属性"

    # ---- R2 多仓库边界三口径 ----

    def test_r2_1_multi_warehouse_isolation(self):
        """R2-1 多仓隔离：A 仓 60、B 仓 40，各自独立成列，绝不出现合计 100。"""
        self._seed(self.m1, self.wh1, 60)
        self._seed(self.m1, self.wh2, 40)
        html = self._page("?only_gap=0")
        body = html[html.find("<tbody>"):html.find("</tbody>")]
        assert "60.00" in body and "40.00" in body, "两仓数量应各自可见"
        assert "100.00" not in body, "不得把两仓合计摊到任一仓（串仓）"

    def test_r2_3_summary_equals_detail(self):
        """R2-3 汇总=明细：全库统计的物料数与实际物料行全集一致。"""
        self._seed(self.m1, self.wh1, 100)
        html = self._page("?only_gap=0")
        # 3 个物料（m1 已建账、m2/m3 未建账），全库统计总数必须是 3
        assert "物料总数" in html and "未建账物料" in html
        assert html.count("<code>M00") == 3, "明细行应为全部 3 个物料"
        assert ">3<" in html.replace("\n", "").replace(" ", ""), "全库汇总应为 3"

    def test_r2_2_single_warehouse_does_not_mark_all_built(self):
        """R2-2 单仓短路反例：仓库只有一个时也不得把全局库存当成该仓已建账。

        建账进度按 warehouse_id 精确聚合，刻意不走
        get_warehouse_stock_quantities 的单仓全量回落分支——否则单仓环境下
        凡是 Material.stock 非 0 的物料都会被误标成"已建账"，进度看板失去意义。
        """
        # 只留一个启用仓库
        self.wh2.status = "inactive"
        db.session.commit()
        # m1 有全局库存（模拟历史数据），但没有期初行
        self.m1.stock = 500
        db.session.commit()

        html = self._page("?only_gap=1")
        assert "M001" in html, "有全局库存但无期初行的物料仍必须算未建账"

    def test_r6_page_and_export_share_single_judgement(self):
        """R6：页面与导出必须共用同一份口径实现，不得各写一套 SUM/0 判定。

        两处各写一遍是本功能最易漂移的地方（改一处忘另一处 → 页面说已建账、
        导出说未建账）。口径唯一实现在 app.py 的
        `_opening_stock_progress_matrix` / `_opening_stock_progress_cells`。
        """
        route_src = (APP_DIR / "routes" / "opening_stock.py").read_text(encoding="utf-8")
        assert "_opening_stock_progress_matrix" in route_src
        assert "_opening_stock_progress_cells" in route_src
        # 路由内不得再自己写 SUM 聚合或 0 判定（各自一套 = 漂移温床）
        assert "func.sum(OpeningStock.quantity)" not in route_src, \
            "SUM 聚合只应存在于 app.py 的 _opening_stock_progress_matrix"
        assert "abs(qty) > 1e-9" not in route_src, \
            "0 判定只应存在于 app.py 的 _opening_stock_progress_cells"

        app_src = (APP_DIR / "app.py").read_text(encoding="utf-8")
        assert "def _opening_stock_progress_matrix(" in app_src
        assert "def _opening_stock_progress_cells(" in app_src

    def test_r6_page_and_export_agree_on_same_data(self):
        """端到端：同一份数据下，页面判定与导出判定必须一致（不漂移）。"""
        self._seed(self.m1, self.wh1, 100)   # 已建账
        # m2 只录 0 → 未建账
        self._save({
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m2.id, "warehouse_id": self.wh1.id,
                       "quantity": 0, "price": 0}],
        })
        csv_body = self.client.get(
            "/opening_stock/progress/export?only_gap=1").get_data().decode("utf-8-sig")
        gap_html = self._page("?only_gap=1")

        # 导出说 M001 已建账 → 页面「只看未建账」也不该有 M001
        assert "M001" not in csv_body.split("状态")[1]
        assert "M001" not in gap_html
        # 导出说 M002 未建账 → 页面也该有 M002（0 判定两侧一致）
        assert "M002" in csv_body and "M002" in gap_html
        # M003 完全没数据，两侧都算未建账
        assert "M003" in csv_body and "M003" in gap_html
