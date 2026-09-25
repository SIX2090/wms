# -*- coding: utf-8 -*-
"""物料停用功能回归（2026-09-25）。

业务诉求：库里出现了 3 组重复物料（名称+规格撞车，靠空格/大小写差异溜过判重），
需要能把重复的那一档**停用**，而不是删掉——删了会带走历史单据与流水。

设计边界（本测试重点钉死这一条）：
    停用 = 「新建单据时不再出现在可选列表里」
    停用 ≠ 删除，也 ≠ 从历史数据里消失。
    历史单据、库存数量、库存台账、报表一律照常显示停用物料，
    否则停用一个物料就等于让它的历史账凭空蒸发，账实核对直接对不上。

口径沿用仓库/部门/合同的既有约定（master_data.py:95/107/129）：
status 字段取值 active/inactive，不另造 is_active / enabled。
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


def _client():
    with app_module.app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(User(username="admin",
                            password_hash=generate_password_hash("admin"),
                            role="admin", must_change_password=False))
        db.session.commit()
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _seed(code, name="物料", spec="SPEC", brand=None, status='active', stock=0):
    with app_module.app.app_context():
        m = Material(code=code, name=name, spec=spec, brand=brand,
                     stock=stock, status=status)
        db.session.add(m)
        db.session.commit()
        return m.id


# ------------------------------------------------------- 迁移补列（生产坑位）

def test_ensure_material_status_column(tmp_path):
    """补列必须能自愈存量库：加列 + 回填 active + 幂等。

    为什么必须有这个测试：start_wms_*.bat 默认 WMS_NO_DB_TOUCH=1 会跳过
    auto_migrate_database()，只写在迁移里的列在存量生产库重启后补不上，
    物料列表一查 status 就 500。这个根因在仓里已复发 5 次。
    """
    import sqlite3

    db_file = tmp_path / "inventory.db"
    conn = sqlite3.connect(str(db_file))
    conn.execute("CREATE TABLE material (id INTEGER PRIMARY KEY, code TEXT, name TEXT)")
    conn.execute("INSERT INTO material (code, name) VALUES ('OLD-1', '老物料')")
    conn.commit()
    conn.close()

    from app import ensure_material_status_column

    ensure_material_status_column(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(material)")]
    assert "status" in cols, "存量库必须补出 status 列"
    rows = conn.execute("SELECT status FROM material").fetchall()
    conn.close()
    assert rows and all(r[0] == "active" for r in rows), "历史行必须回填为启用"

    # 幂等：再跑一次不得报错、不得重复加列
    ensure_material_status_column(str(db_file))
    conn = sqlite3.connect(str(db_file))
    cols2 = [r[1] for r in conn.execute("PRAGMA table_info(material)")]
    conn.close()
    assert cols2.count("status") == 1


def test_ensure_material_status_column_missing_db_noop(tmp_path):
    """库文件不存在（全新部署）时直接返回，交给 create_all 建表。"""
    from app import ensure_material_status_column

    ensure_material_status_column(str(tmp_path / "not_exists.db"))


# ------------------------------------------------------------ 过滤条件本身

def test_material_selectable_filter():
    """include_inactive=True 返回 None（不加过滤）；否则排除停用。"""
    from app import material_selectable_filter

    assert material_selectable_filter(True) is None
    cond = material_selectable_filter(False)
    assert cond is not None

    _client()
    active_id = _seed("F-1", status='active')
    inactive_id = _seed("F-2", status='inactive')

    with app_module.app.app_context():
        ids = {m.id for m in Material.query.filter(cond).all()}
        assert active_id in ids
        assert inactive_id not in ids, "停用物料必须被过滤掉"
        # NULL / 空串按启用处理（存量库补列回填完成前的老行不能被整体过滤掉）
        m = Material(code="F-3", name="老行", spec="", stock=0)
        m.status = None
        db.session.add(m)
        db.session.commit()
        assert m.id in {x.id for x in Material.query.filter(cond).all()}


# ---------------------------------------------------------------- 停用/启用

def test_set_material_status():
    """停用 → 启用 → 非法值，三条路径。"""
    client = _client()
    mid = _seed("S-1")

    resp = client.post(f"/material/{mid}/set_status",
                       data={"status": "inactive"}, headers=AJAX_HEADERS)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["new_status"] == "inactive"
    with app_module.app.app_context():
        assert Material.query.get(mid).status == "inactive"

    resp = client.post(f"/material/{mid}/set_status",
                       data={"status": "active"}, headers=AJAX_HEADERS)
    assert resp.get_json()["new_status"] == "active"
    with app_module.app.app_context():
        assert Material.query.get(mid).status == "active"

    resp = client.post(f"/material/{mid}/set_status",
                       data={"status": "deleted"}, headers=AJAX_HEADERS)
    assert resp.status_code == 400, "非法状态必须拒绝"

    resp = client.post("/material/999999/set_status",
                       data={"status": "inactive"}, headers=AJAX_HEADERS)
    assert resp.status_code == 404


def test_stopped_material_data_not_deleted():
    """停用一个物料，它的数据必须原样还在（停用 ≠ 删除）。"""
    client = _client()
    mid = _seed("K-1", name="铜排", spec="TMY-100x10", stock=7)
    client.post(f"/material/{mid}/set_status", data={"status": "inactive"},
                headers=AJAX_HEADERS)
    with app_module.app.app_context():
        m = Material.query.get(mid)
        assert m is not None, "停用不得删行"
        assert m.stock == 7, "停用不得动库存"
        assert m.code == "K-1" and m.name == "铜排"


# ------------------------------------------------------------ 列表与下拉

def test_material_list_default_hides_inactive():
    """列表默认只看启用；切到「停用」「全部」能找回。"""
    client = _client()
    _seed("L-1", status='active')
    _seed("L-2", status='inactive')

    html = client.get("/material").get_data(as_text=True)
    assert "L-1" in html
    assert "L-2" not in html, "默认列表不应出现停用物料"

    html = client.get("/material?status=inactive").get_data(as_text=True)
    assert "L-2" in html, "切到「停用」必须能找回，否则没法重新启用"
    assert "L-1" not in html

    html = client.get("/material?status=all").get_data(as_text=True)
    assert "L-1" in html and "L-2" in html


def test_material_api_all_excludes_inactive():
    """下拉数据源 /material/api/all 排除停用；显式 include_inactive=1 可取全量。"""
    client = _client()
    _seed("A-1", status='active')
    _seed("A-2", status='inactive')

    codes = [m["code"] for m in
             client.get("/material/api/all").get_json()["materials"]]
    assert "A-1" in codes and "A-2" not in codes

    codes = [m["code"] for m in
             client.get("/material/api/all?include_inactive=1").get_json()["materials"]]
    assert "A-1" in codes and "A-2" in codes, \
        "历史单据需要连停用物料一起显示时必须能取到（否则下拉会显示空白）"


def test_material_api_list_excludes_inactive():
    """/material/api/list 同样排除停用。"""
    client = _client()
    _seed("B-1", status='active')
    _seed("B-2", status='inactive')
    codes = [m["code"] for m in
             client.get("/material/api/list").get_json()["materials"]]
    assert "B-1" in codes and "B-2" not in codes


def test_material_search_api_excludes_inactive():
    """/api/material/search（主联想口）排除停用。"""
    client = _client()
    _seed("C-1", name="断路器", status='active')
    _seed("C-2", name="断路器", status='inactive')

    data = client.get("/api/material/search?kw=断路器").get_json()
    codes = [m["code"] for m in data.get("data", [])]
    assert "C-1" in codes and "C-2" not in codes

    data = client.get("/api/material/search?kw=断路器&include_inactive=1").get_json()
    codes = [m["code"] for m in data.get("data", [])]
    assert "C-1" in codes and "C-2" in codes


def test_material_all_api_excludes_inactive():
    """/api/material/all 排除停用。"""
    client = _client()
    _seed("D-1", status='active')
    _seed("D-2", status='inactive')
    data = client.get("/api/material/all").get_json()
    codes = [m["code"] for m in data.get("data", [])]
    assert "D-1" in codes and "D-2" not in codes


# ------------------------------------------------------------ 编辑表单联动

def test_edit_material_can_set_status():
    """编辑弹窗保存 status 生效；非法值 400。"""
    client = _client()
    mid = _seed("E-1", name="继电器", spec="PF113A", brand="欧姆龙")

    resp = client.post(f"/material/edit/{mid}", data={
        "code": "E-1", "name": "继电器", "spec": "PF113A",
        "brand": "欧姆龙", "status": "inactive",
    }, headers=AJAX_HEADERS)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        assert Material.query.get(mid).status == "inactive"

    resp = client.post(f"/material/edit/{mid}", data={
        "code": "E-1", "name": "继电器", "spec": "PF113A",
        "brand": "欧姆龙", "status": "已删除",
    }, headers=AJAX_HEADERS)
    assert resp.status_code == 400, "非法状态必须拒绝"


def test_new_material_defaults_to_active():
    """新增物料默认启用：不带 status 字段的老表单也不能把它建成停用。"""
    client = _client()
    resp = client.post("/material/add", data={
        "code": "N-1", "name": "新增物料", "spec": "SPEC-N", "brand": "",
    }, headers=AJAX_HEADERS)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        assert Material.query.filter_by(code="N-1").first().status == "active"
