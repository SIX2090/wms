# -*- coding: utf-8 -*-
"""物料合并回归：一个物料只允许一个物料编号（2026-09-25）。

业务口径（用户明确纠正过一轮）：
    停用 ≠ 解决重复。停用后档案与编号仍在库里，仍是一物两码；
    重复的两个物料编码必须**合并成一个** —— 单据、流水、库位账、期初、图片
    全部改指到保留的物料，库存累加，被并掉的档案删除，旧编码转存为别名。

为什么必须转别名：现场常有人拿旧编码去扫码/搜索，删了就彻底找不到，
纸质单据上的旧编号也对不上。别名表 ai_material_alias 就是干这个的。

实测背景（生产库副本，1261 条物料）：
    - 名称+规格+品牌（去空格 + 不分大小写）相同的重复 5 组 10 条
    - 全库 **22 张表**引用 material_id。只按「记得住的几张表」改指必漏，
      漏一张就留下指向已删除物料的孤儿行。故合并清单由
      test_material_merge_covers_all_ref_tables 用 metadata 反射兜底。
    - 最典型一条：入库单 IN26090112 里 115021 入 28、115022 入 2 —— 同一个
      物料在同一张单上被拆成两行，按物料统计用量永远加不到一起。
"""
from __future__ import annotations

import os
import sys
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
from app import db, Material, User  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

AJAX_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _reset(login=True):
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(username="admin",
                            password_hash=generate_password_hash("admin"),
                            role="admin", must_change_password=False))
        db.session.commit()
    client = app_module.app.test_client()
    if login:
        client.post("/login", data={"username": "admin", "password": "admin"},
                    content_type="application/x-www-form-urlencoded")
    return client


def _seed(code, name="模块前连接器40针", spec="6ES75921BM000XB0", brand=None, stock=0):
    with app_module.app.app_context():
        m = Material(code=code, name=name, spec=spec, brand=brand, stock=stock,
                     status="active")
        db.session.add(m)
        db.session.commit()
        return m.id


def _preview(target_id, source_id):
    with app_module.app.app_context():
        from app import material_merge_preview
        return material_merge_preview(target_id, source_id)


def _merge(target_id, source_id, keep_alias=True):
    with app_module.app.app_context():
        from app import merge_material_duplicates
        stats = merge_material_duplicates(target_id, source_id, keep_alias=keep_alias)
        db.session.commit()
        return stats


# ------------------------------------------------------------ 清单完整性

def test_material_merge_covers_all_ref_tables():
    """防腐：任何含 material_id 的表都必须在合并清单里，否则留下孤儿行。

    生产库实测 22 张表引用 material_id，凭记忆列清单必漏。这里用 SQLAlchemy
    metadata 反射出全部表，倒逼清单保持完整 —— 新增引用表忘了同步就红。
    """
    from app import MATERIAL_MERGE_QUANTITY_TABLES, MATERIAL_MERGE_REF_TABLES

    covered = set(MATERIAL_MERGE_REF_TABLES) | set(MATERIAL_MERGE_QUANTITY_TABLES)
    covered |= {'ai_material_alias'}  # 单独处理：改指 + 旧编码转别名
    covered |= {'material'}           # 物料主表本身

    missing = []
    with app_module.app.app_context():
        for name, table in db.metadata.tables.items():
            if 'material_id' in table.c and name not in covered:
                missing.append(name)

    assert not missing, (
        '这些表引用了 material_id 但不在合并清单 MATERIAL_MERGE_REF_TABLES 里，'
        '合并后会留下指向已删除物料的孤儿行：' + ', '.join(sorted(missing)))


# ------------------------------------------------------------ 合并前置校验

def test_material_merge_preview():
    """预览是只读的：给出保留方、被并方、库存变化与受影响行数。"""
    _reset()
    target = _seed("115021", stock=28)
    source = _seed("115022", stock=2)
    with app_module.app.app_context():
        from app import InOrder, InOrderItem, OutOrder, OutOrderItem

        io = InOrder(order_no="IN-1")
        db.session.add(io)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=io.id, material_id=source,
                                   quantity=2, price=0, amount=0))
        db.session.commit()

    data = _preview(target, source)
    assert data["target"]["code"] == "115021" and data["source"]["code"] == "115022"
    assert data["stock_after"] == 30, "库存必须累加"
    assert data["tables"].get("in_order_item") == 1
    assert data["total_rows"] >= 1
    # 只读：预览之后数据不能变
    with app_module.app.app_context():
        assert Material.query.filter_by(code="115022").first() is not None


def test_merge_rejects_different_dedupe_key():
    """判重键不一致绝不允许合并 —— 防止把两个不同物料并成一个。"""
    _reset()
    a = _seed("A-1", name="按钮", spec="LA38-11")
    b = _seed("B-1", name="接触器", spec="CJX2-12")
    try:
        _preview(a, b)
        assert False, "名称+规格不同必须拒绝合并"
    except ValueError as exc:
        assert "不一致" in str(exc)


def test_merge_rejects_self():
    _reset()
    a = _seed("A-1")
    try:
        _preview(a, a)
        assert False, "不能合并到自己"
    except ValueError as exc:
        assert "自己" in str(exc)


def test_merge_accepts_space_and_case_variant():
    """空格/大小写变体属于同一个物料 —— 这正是生产库那 3 组漏网的情形。"""
    _reset()
    a = _seed("A-1", name="浪涌后备保护", spec="JKDB-25I/4P 25KA")
    b = _seed("B-1", name="浪涌后备保护", spec="JKDB-25I/4P 25kA")
    data = _preview(a, b)
    assert data["target"]["code"] == "A-1"


# ------------------------------------------------------------ 合并本体

def test_merge_material_duplicates():
    """合并后：单据改指、库存累加、被并档案删除、三账恒等式仍成立。"""
    _reset()
    with app_module.app.app_context():
        from app import InOrder, InOrderItem, OutOrder, OutOrderItem, StockTransaction

        target = _seed("115021", stock=28)
        source = _seed("115022", stock=2)
        io = InOrder(order_no="IN-1")
        oo = OutOrder(order_no="OU-1")
        db.session.add_all([io, oo])
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=io.id, material_id=source,
                                   quantity=2, price=0, amount=0))
        db.session.add(OutOrderItem(out_order_id=oo.id, material_id=source,
                                    quantity=2, price=0, amount=0))
        # 三账要成立：①总账 必须等于 ③流水Σ
        db.session.add(StockTransaction(material_id=target, transaction_type="in",
                                        quantity=28))
        db.session.add(StockTransaction(material_id=source, transaction_type="in",
                                        quantity=2))
        db.session.commit()

    stats = _merge(target, source)
    assert stats["stock_after"] == 30
    assert stats["source_code"] == "115022"
    assert stats["ledger_ok"], f"三账恒等式不成立：{stats['ledger_detail']}"

    with app_module.app.app_context():
        assert Material.query.filter_by(code="115022").first() is None, "被并档案必须删掉"
        assert Material.query.filter_by(code="115021").first().stock == 30
        assert Material.query.count() == 1, "一个物料只允许剩一个编号"
        from app import InOrderItem, OutOrderItem, StockTransaction
        assert InOrderItem.query.filter_by(material_id=target).count() == 1, "入库明细已改指"
        assert OutOrderItem.query.filter_by(material_id=target).count() == 1, "出库明细已改指"
        assert StockTransaction.query.filter_by(material_id=target).count() == 2


def test_merge_keeps_old_code_as_alias():
    """旧编码必须转存为别名 —— 现场拿旧编码扫码/搜索还要能命中。"""
    _reset()
    target = _seed("115021")
    source = _seed("115022")
    stats = _merge(target, source, keep_alias=True)
    assert stats["alias"] == "115022"
    with app_module.app.app_context():
        from app import AIMaterialAlias, _ai_material_alias_key
        row = AIMaterialAlias.query.filter_by(
            alias_key=_ai_material_alias_key("115022")).first()
        assert row is not None and row.material_id == target
        assert row.source == "material_merge"


def test_merge_without_alias():
    """keep_alias=False：旧编码彻底不留。"""
    _reset()
    target = _seed("115021")
    source = _seed("115022")
    stats = _merge(target, source, keep_alias=False)
    assert stats["alias"] is None
    with app_module.app.app_context():
        from app import AIMaterialAlias
        assert AIMaterialAlias.query.count() == 0


def test_merge_location_inventory_merges_quantity():
    """库位账按（仓库 + 库位）合并数量，不能留下同键两行。"""
    _reset()
    with app_module.app.app_context():
        from app import LocationInventory

        target = _seed("115021", stock=3)
        source = _seed("115022", stock=5)
        db.session.add(LocationInventory(material_id=target, warehouse_id=1,
                                         location="A-01", quantity=3))
        db.session.add(LocationInventory(material_id=source, warehouse_id=1,
                                         location="A-01", quantity=5))
        db.session.commit()

    _merge(target, source)
    with app_module.app.app_context():
        from app import LocationInventory
        rows = LocationInventory.query.filter_by(material_id=target).all()
        assert len(rows) == 1, "同（仓库+库位）必须合成一条"
        assert rows[0].quantity == 8


def test_merge_leaves_no_orphan_rows():
    """合并完不能有任何行指向已删除的物料。"""
    _reset()
    with app_module.app.app_context():
        from app import InOrder, InOrderItem, StockTransaction

        target = _seed("115021")
        source = _seed("115022")
        io = InOrder(order_no="IN-1")
        db.session.add(io)
        db.session.flush()
        db.session.add(InOrderItem(in_order_id=io.id, material_id=source,
                                   quantity=1, price=0, amount=0))
        db.session.add(StockTransaction(material_id=source, transaction_type="in",
                                        quantity=1))
        db.session.commit()

    _merge(target, source)
    with app_module.app.app_context():
        for name, table in db.metadata.tables.items():
            if 'material_id' not in table.c or name == 'material':
                continue
            from sqlalchemy import select
            n = db.session.execute(
                select(table.c.id).where(table.c.material_id == source)).fetchall()
            assert not n, f"{name} 留下了指向已删除物料的孤儿行：{len(n)} 行"


# ------------------------------------------------------------ 路由（两步确认）

def test_merge_route_requires_preview_before_execute():
    """不带 confirm 只返回预览，绝不许一键合并。"""
    client = _reset()
    target = _seed("115021", stock=28)
    source = _seed("115022", stock=2)
    r = client.post(f"/material/{source}/merge",
                    json={"target_code": "115021"}, headers=AJAX_HEADERS)
    data = r.get_json()
    assert data["status"] == "preview", data
    assert data["data"]["stock_after"] == 30
    with app_module.app.app_context():
        assert Material.query.filter_by(code="115022").first() is not None, "预览不能改数据"


def test_merge_route_executes_with_confirm():
    client = _reset()
    target = _seed("115021", stock=28)
    source = _seed("115022", stock=2)
    # 三账要成立：①总账 必须等于 ③流水Σ，否则合并会被守卫拦下
    with app_module.app.app_context():
        from app import StockTransaction
        db.session.add(StockTransaction(material_id=target, transaction_type="in",
                                        quantity=28))
        db.session.add(StockTransaction(material_id=source, transaction_type="in",
                                        quantity=2))
        db.session.commit()
    r = client.post(f"/material/{source}/merge",
                    json={"target_code": "115021", "confirm": True, "keep_alias": True},
                    headers=AJAX_HEADERS)
    data = r.get_json()
    assert data["status"] == "success", data
    with app_module.app.app_context():
        assert Material.query.filter_by(code="115022").first() is None
        assert Material.query.filter_by(code="115021").first().stock == 30


def test_merge_route_rejects_unknown_target():
    client = _reset()
    source = _seed("115022")
    r = client.post(f"/material/{source}/merge",
                    json={"target_code": "NOT-EXIST", "confirm": True},
                    headers=AJAX_HEADERS)
    assert r.get_json()["status"] == "error"


def test_merge_preview_route_rejects_mismatch():
    client = _reset()
    a = _seed("A-1", name="按钮", spec="LA38-11")
    b = _seed("B-1", name="接触器", spec="CJX2-12")
    r = client.post("/material/merge_preview",
                    json={"source_code": "B-1", "target_code": "A-1"},
                    headers=AJAX_HEADERS)
    assert r.get_json()["status"] == "error"


# ------------------------------------------------- 数据库级「一物一码」唯一约束

def test_find_material_dedupe_conflicts():
    """冲突查询：找出仍然一物多码的分组（空格/大小写变体也要算同一组）。"""
    _reset()
    _seed("105020", name="浪涌后备保护", spec="JKDB-25I/4P 25KA")
    _seed("105021", name="浪涌后备保护", spec="JKDB-25I/4P 25kA")
    _seed("108032", name="按钮", spec="LA38-11 绿色")
    _seed("108034", name="按钮", spec="LA38-11绿色")
    _seed("900001", name="唯一物料", spec="NO-DUP")
    with app_module.app.app_context():
        from app import find_material_dedupe_conflicts
        conflicts = find_material_dedupe_conflicts()
    assert len(conflicts) == 2, conflicts
    codes = {c for grp in conflicts for c in grp["codes"]}
    assert codes == {"105020", "105021", "108032", "108034"}


def test_ensure_material_dedupe_unique_index(tmp_path):
    """存量无重复 → 建上唯一索引；建上后数据库层拒绝插入重复。

    这是「一个物料只允许一个物料编号」的物理保证：应用层判重可能被绕过
    （新入口、直连数据库、老版本代码），唯一索引绕不过去。
    """
    import sqlite3

    from app import (MATERIAL_DEDUPE_UNIQUE_INDEX_DDL,
                     ensure_material_dedupe_unique_index)

    db_file = tmp_path / "inventory.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, "
                "name TEXT, spec TEXT, brand TEXT)")
    con.execute("INSERT INTO material VALUES (1,'A','按钮','LA38-11',NULL)")
    con.commit()
    con.close()

    ok, conflicts = ensure_material_dedupe_unique_index(str(db_file))
    assert ok and not conflicts

    # 索引建上后：空格/大小写变体也插不进去
    con = sqlite3.connect(str(db_file))
    for bad in [("B", "按钮", "LA38-11 ", None), ("C", "按钮", "la38-11", None)]:
        try:
            con.execute("INSERT INTO material (code,name,spec,brand) VALUES (?,?,?,?)", bad)
            con.commit()
            assert False, f"数据库层必须拒绝重复物料：{bad}"
        except sqlite3.IntegrityError:
            con.rollback()
    # 同名称不同规格 / 同规格不同品牌 —— 合法，必须放行
    con.execute("INSERT INTO material (code,name,spec,brand) VALUES ('D','按钮','LA38-22',NULL)")
    con.execute("INSERT INTO material (code,name,spec,brand) VALUES ('E','按钮','LA38-11','欧姆龙')")
    con.commit()
    con.close()


def test_ensure_material_dedupe_unique_index_blocked_by_conflicts(tmp_path):
    """存量还有一物两码 → 索引建不上，但**不能抛异常**（启动期会被调用）。"""
    import sqlite3

    from app import ensure_material_dedupe_unique_index

    db_file = tmp_path / "inventory.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, "
                "name TEXT, spec TEXT, brand TEXT)")
    con.execute("INSERT INTO material VALUES (1,'A','按钮','LA38-11 绿色',NULL)")
    con.execute("INSERT INTO material VALUES (2,'B','按钮','LA38-11绿色',NULL)")
    con.commit()
    con.close()

    ok, conflicts = ensure_material_dedupe_unique_index(str(db_file))
    assert not ok, "有重复时必须拒绝建索引"
    assert len(conflicts) == 1
    # 没建上索引 → 数据库仍可写入（不能因为索引建不上就让业务写不了）
    con = sqlite3.connect(str(db_file))
    con.execute("INSERT INTO material (code,name,spec,brand) VALUES ('C','按钮','LA38-11绿色',NULL)")
    con.commit()
    con.close()

    # 合并掉重复之后（只留一条）→ 这次能建上了
    con = sqlite3.connect(str(db_file))
    con.execute("DELETE FROM material WHERE code IN ('A', 'B')")
    con.commit()
    con.close()
    ok2, _ = ensure_material_dedupe_unique_index(str(db_file))
    assert ok2, "重复清掉后必须能补建索引"


def test_merge_then_unique_index_becomes_possible(tmp_path):
    """端到端：合并掉一组重复 → 唯一索引从「建不上」变成「建得上」。"""
    import sqlite3

    from app import ensure_material_dedupe_unique_index

    db_file = tmp_path / "inventory.db"
    con = sqlite3.connect(str(db_file))
    con.execute("CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, "
                "name TEXT, spec TEXT, brand TEXT)")
    con.execute("INSERT INTO material VALUES (1,'115021','模块前连接器40针','6ES75921BM000XB0','西门子')")
    con.execute("INSERT INTO material VALUES (2,'115022','模块前连接器40针','6ES75921BM000XB0','西门子')")
    con.commit()
    con.close()

    assert not ensure_material_dedupe_unique_index(str(db_file))[0]
    _merge(1, 2)
    with app_module.app.app_context():
        con = sqlite3.connect(str(db_file))
        con.execute("DELETE FROM material WHERE code='115022'")
        con.commit()
        con.close()
    assert ensure_material_dedupe_unique_index(str(db_file))[0]
