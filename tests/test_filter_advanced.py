# -*- coding: utf-8 -*-
"""AI-WMS-FILTER-003：库存查询分页 + 主数据查询索引 + 供应商/客户筛选维度。

背景（承接 AI-WMS-FILTER-002 的全系统筛选评估）：
1. 库存查询一次渲染 951 条（约 735 KB），列表页不分页。
2. 供应商/客户只有 1 个关键词框，筛选维度单薄。
3. 主数据表缺 JOIN / 排序会走的索引。

验收点：
- `_apply_master_advanced_filters` 三个维度（定向搜索 / 日期区间 / 业务往来）
  均生效，且脏参数不报错。
- 库存查询分页：每页条数正确、总数正确、越界安全。
- `stock_filter`(low/normal) 与全量互补，且过滤后总数是过滤后的条数，
  不是全量分页（这是分页改造最容易算错的地方）。
- 供应商/客户列表与导出共用同一筛选入口，且不得再叠加
  `_apply_simple_search`（会导致条件重复）。
- 索引在「模型 __table_args__」与「自动迁移 DDL」两处各声明一次，名字一致
  （新库靠 create_all，老库靠 auto_migrate，两边缺一都会在对应场景失效）。

注意事项：`LIKE '%kw%'` 的前置通配符用不上 B-tree 索引，本次补的索引
服务的是 JOIN / 排序 / 区间过滤，模糊搜索本身不在优化范围内。
"""
from __future__ import annotations

import os
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import Material, Supplier, SystemSetting, User, Warehouse, db  # noqa: E402

import pytest  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

FIELDS = ["code", "name", "contact", "phone", "address"]
ROW_RE = re.compile(r'<tr class="[^"]*">\s*<td>\s*\d+\s*</td>')


@pytest.fixture(autouse=True)
def _app_ctx():
    with app_module.app.app_context():
        yield


def _uid():
    return uuid.uuid4().hex[:8]


def _make_client():
    db.drop_all()
    db.create_all()
    u = User(username="qa-" + _uid(), password_hash="x")
    db.session.add(u)
    db.session.flush()
    db.session.add(Warehouse(code="WH01", name="成品仓"))
    db.session.commit()
    client = app_module.app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(u.id)
        sess["user_id"] = str(u.id)
        sess["_fresh"] = True
    return client


def _seed_materials(n):
    """造 n 个物料，返回仓库 id。"""
    wh = Warehouse.query.first()
    for i in range(n):
        db.session.add(Material(code="T-%04d" % i, name="测试物料%d" % i,
                                stock=0, min_stock=0))
    db.session.commit()
    return wh.id


def _enable_alert():
    s = SystemSetting.query.filter_by(key="inventory_alert_enabled").first()
    if s is None:
        db.session.add(SystemSetting(key="inventory_alert_enabled", value="1"))
    else:
        s.value = "1"
    db.session.commit()


def _total(client, url):
    r = client.get(url)
    assert r.status_code == 200, "HTTP %s" % r.status_code
    html = r.get_data(as_text=True)
    m = re.search(r"共\s*(\d+)\s*条记录", html)
    return int(m.group(1)) if m else -1


# ---------------- 通用筛选 helper（A9 门禁要求同名用例） ----------------

def test__apply_master_advanced_filters():
    fn = app_module._apply_master_advanced_filters
    today = datetime.now().strftime("%Y-%m-%d")

    with app_module.app.test_request_context("/supplier?search=ABC&search_field=code"):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        sql = str(q).replace('"', "")
        assert "supplier.code LIKE" in sql, "定向搜索未生效"
        assert "address LIKE" not in sql, "定向搜索不应再叠加其他字段"
        assert f["search_field"] == "code"

    with app_module.app.test_request_context("/supplier?search=ABC"):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        assert "address LIKE" in str(q).replace('"', ""), "未指定范围应退回全字段"
        assert f["search_field"] == ""

    with app_module.app.test_request_context("/supplier?search=ABC&search_field=bogus"):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        assert "address LIKE" in str(q).replace('"', ""), "非法字段名应安全退回全字段"

    def _where(q):
        """只看 WHERE 子句：SELECT 列里也会有 created_at，不能用整条 SQL 判断。"""
        sql = str(q)
        return sql.split("WHERE")[-1] if "WHERE" in sql else ""

    with app_module.app.test_request_context(
            "/supplier?date_from=%s&date_to=%s" % (today, today)):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        where = _where(q)
        assert "created_at >=" in where and "created_at <" in where, "日期区间未生效"
        assert f["date_from"] == today and f["date_to"] == today

    with app_module.app.test_request_context("/supplier?date_from=not-a-date"):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        where = _where(q)
        assert "created_at >=" not in where and "created_at <" not in where, (
            "脏日期参数应被忽略，不能报错或误筛")

    rel = getattr(Supplier, "in_orders", None)
    if rel is None:
        pytest.skip("Supplier.in_orders 关系不存在，跳过业务往来维度")
    with app_module.app.test_request_context("/supplier?has_business=yes"):
        q, f = fn(Supplier.query, Supplier, FIELDS,
                  business_expr=db.or_(rel.any()))
        assert "EXISTS" in str(q).upper(), "has_business=yes 未加 EXISTS"
        assert f["has_business"] == "yes"
    with app_module.app.test_request_context("/supplier?has_business=no"):
        q, f = fn(Supplier.query, Supplier, FIELDS,
                  business_expr=db.or_(rel.any()))
        assert "NOT" in str(q).upper(), "has_business=no 未取反"
    # 未传 business_expr 时不应崩，也不应凭空加条件
    with app_module.app.test_request_context("/supplier?has_business=yes"):
        q, f = fn(Supplier.query, Supplier, FIELDS)
        assert "EXISTS" not in str(q).upper()


# ---------------- 库存查询分页 ----------------

def test_stock_query_paginates():
    client = _make_client()
    wid = _seed_materials(25)
    # per_page 走白名单 (20/50/100/200)，用 20 验证分页边界
    r = client.get("/stock_query?warehouse_id=%d&per_page=20" % wid)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "共 25 条记录" in html, "总数应为过滤后的 25，而不是每页条数"
    assert len(ROW_RE.findall(html)) == 20, "每页 20 条"
    r2 = client.get("/stock_query?warehouse_id=%d&per_page=20&page=2" % wid)
    html2 = r2.get_data(as_text=True)
    assert len(ROW_RE.findall(html2)) == 5, "第二页应剩 5 条"
    assert "<td>21</td>" in html2, "第二页序号应从 21 开始（全局序号，不是页内序号）"


def test_stock_query_page_out_of_range_is_safe():
    client = _make_client()
    wid = _seed_materials(12)
    r = client.get("/stock_query?warehouse_id=%d&page=999" % wid)
    assert r.status_code == 200, "越界页不应 404（error_out=False）"
    html = r.get_data(as_text=True)
    assert "共 12 条记录" in html
    assert "暂无匹配物料" in html


def test_stock_filter_low_normal_complementary():
    """low + normal 必须等于全部——分页最容易在这里算错。"""
    client = _make_client()
    wid = _seed_materials(12)
    _enable_alert()
    # 挑 3 个物料设成必然预警（库存 0 < 最低库存）
    picks = Material.query.filter(Material.code.like("T-%")).order_by(
        Material.code).limit(3).all()
    for m in picks:
        m.min_stock = 100000
    db.session.commit()

    base = "/stock_query?warehouse_id=%d" % wid
    allc = _total(client, base)
    low = _total(client, base + "&stock_filter=low")
    normal = _total(client, base + "&stock_filter=normal")
    assert low == 3, "应有 3 条预警物料，实际 %d" % low
    assert low + normal == allc, "low(%d) + normal(%d) 应等于全量(%d)" % (low, normal, allc)


# ---------------- 列表与导出同口径（防回退） ----------------

def test_supplier_list_and_export_share_one_filter_entry():
    src = (APP_DIR / "routes" / "supplier.py").read_text(encoding="utf-8")
    exp = (APP_DIR / "routes" / "unit_supplier_import.py").read_text(encoding="utf-8")
    for name, text in (("supplier.py", src), ("unit_supplier_import.py", exp)):
        assert "_apply_master_advanced_filters" in text, (
            "%s 未接入统一筛选入口，页面与导出口径会分叉" % name)
        # 只约束 Supplier：同文件里 Unit 等实体仍可正常使用 _apply_simple_search
        assert "_apply_simple_search(Supplier.query" not in text, (
            "%s 仍在对 Supplier 叠加 _apply_simple_search，会导致条件重复"
            "（helper 内部已处理 search）" % name)


def test_customer_list_and_export_share_one_filter_entry():
    src = (APP_DIR / "routes" / "customer.py").read_text(encoding="utf-8")
    assert src.count("_apply_master_advanced_filters") >= 2, (
        "customer.py 的列表与导出都要接入统一筛选入口")
    assert "_apply_simple_search(Customer.query" not in src, (
        "customer.py 仍在对 Customer 叠加 _apply_simple_search，会导致条件重复")


# ---------------- 索引声明（新库 + 老库两处） ----------------

# 注意：location_inventory.material_id 单列索引早已存在
# （idx_location_inventory_material_id），本次不再重复建。
@pytest.mark.parametrize("index_name", [
    "idx_location_inventory_wh_material",
    "idx_material_supplier",
    "idx_material_unit",
    "idx_material_created",
    "idx_supplier_created",
    "idx_customer_created",
])
def test_performance_index_declared_in_model_and_migration(index_name):
    """索引名必须在模型与自动迁移中各出现一次。

    新库由 db.create_all() 依 __table_args__ 建；老库由 auto_migrate_database()
    的 DDL 补。任一处缺失，对应场景就会静默缺索引。
    """
    src = (APP_DIR / "app.py").read_text(encoding="utf-8")
    cnt = src.count(index_name)
    assert cnt == 2, (
        "%s 应在模型 __table_args__ 与自动迁移 DDL 中各出现一次，实际 %d 次"
        % (index_name, cnt))


def test_stock_query_pager_keeps_all_filters():
    """分页宏的 base_kwargs 必须带全筛选字段，否则翻页丢条件。"""
    src = (APP_DIR / "templates" / "stock_query.html").read_text(encoding="utf-8")
    m = re.search(r"base_kwargs\s*=\s*\{(.*?)\}", src, re.S)
    assert m, "stock_query.html 未用 pager 宏的 base_kwargs 透传筛选参数"
    keys = set(re.findall(r"'(\w+)'\s*:", m.group(1)))
    missing = [f for f in ("search", "category_id", "stock_filter", "warehouse_id")
               if f not in keys]
    assert not missing, "分页 base_kwargs 漏了 %s（翻页会丢条件）" % ", ".join(missing)
