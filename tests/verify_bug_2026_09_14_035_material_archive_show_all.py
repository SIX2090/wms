# -*- coding: utf-8 -*-
"""
BUG-2026-09-14-035 回归测试：手机端物料档案展示全部物料。

根因：
- 后端 `/mobile/api/material_archive/search` 原 `.limit(50)`，空关键字浏览被截断为前 50
  （R1：默认上限被当成全量）；界面为纯搜索屏，进入不加载。
- 隐患：每条物料 image_count 逐条 COUNT + unit/category 惰性加载，取全会放大为 N+1。

修复：
- 后端返回全部匹配物料（主数据量可控），附 total / truncated 元数据，安全上限
  `_MATERIAL_ARCHIVE_BROWSE_MAX`；image_count 改一次 GROUP BY 批量预取；unit/category joinedload。
- Android `MaterialArchiveSearchScreen` 进入即 `LaunchedEffect(Unit){ viewModel.search() }` 自动加载全部。

验收点：
T1. 空关键字返回全部物料（>50 也全量），total 元数据正确。
T2. 取全为常量次 SQL（批量统计 + 预加载，无 N+1）。
T3. 超安全上限时 truncated=True 且 total 为真实总数。
T4. 关键字仍正确模糊过滤并返回全部命中。
T5. 批量 image_count 数值正确。
T6. Android 端进入即自动加载（静态断言）+ 后端不再硬编码 .limit(50)。
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
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")

import app as app_module  # noqa: E402
from app import db  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

KT = ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/MaterialArchiveScreens.kt"


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    from werkzeug.security import generate_password_hash
    from app import User
    db.session.add(User(username="admin", password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _login(client):
    r = client.post("/login", data={"username": "admin", "password": "admin",
                                    "login_mode": "user", "usage_consent": "1"})
    assert r.status_code in (200, 302), r.get_data(as_text=True)


def _seed_material(code, name="物料", spec="", brand=""):
    from app import Material
    m = Material(code=code, name=name, spec=spec, brand=brand)
    db.session.add(m)
    db.session.commit()
    return m.id


def _seed_image(mid, name="a.png"):
    from app import MaterialImage
    db.session.add(MaterialImage(material_id=mid, image=f"uploads/material_images/{name}", sort_order=0))
    db.session.commit()


import pytest  # noqa: E402


@pytest.fixture()
def client():
    from app import Material, MaterialImage
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    c = app_module.app.test_client()
    _login(c)
    yield c
    with app_module.app.app_context():
        Material.query.delete()
        MaterialImage.query.delete()
        db.session.commit()


class TestShowAll:
    def test_t1_empty_keyword_returns_all(self, client):
        with app_module.app.app_context():
            for i in range(60):
                _seed_material(f"M{i:03d}", f"物料{i}")
        r = client.get("/mobile/api/material_archive/search")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert body["status"] == "success"
        assert len(body["data"]) == 60, f"应返回全部 60 条，实际 {len(body['data'])}"
        assert body["total"] == 60
        assert body["truncated"] is False

    def test_t2_no_n_plus_1(self, client):
        from sqlalchemy import event
        with app_module.app.app_context():
            for i in range(30):
                mid = _seed_material(f"N{i:03d}", f"物料{i}")
                _seed_image(mid, f"a{i}.png")
                _seed_image(mid, f"b{i}.png")
        queries = []

        def _listener(*a, **k):
            queries.append(1)

        with app_module.app.app_context():
            event.listen(db.engine, "before_cursor_execute", _listener)
            try:
                r = client.get("/mobile/api/material_archive/search")
            finally:
                event.remove(db.engine, "before_cursor_execute", _listener)
        assert r.status_code == 200
        # 批量统计 + joinedload：常量次 SQL；若 N+1 则 30 物料 → 30+ 次图片 COUNT
        assert len(queries) <= 12, f"疑似 N+1，SQL 次数 {len(queries)}"

    def test_t3_browse_max_truncated(self, client, monkeypatch):
        monkeypatch.setattr("routes.mobile._MATERIAL_ARCHIVE_BROWSE_MAX", 5)
        with app_module.app.app_context():
            for i in range(8):
                _seed_material(f"C{i:03d}", f"物料{i}")
        r = client.get("/mobile/api/material_archive/search")
        body = r.get_json()
        assert len(body["data"]) == 5, "超过安全上限应截断到上限"
        assert body["truncated"] is True
        assert body["total"] == 8, "total 应为真实总数"

    def test_t4_keyword_filter_returns_all_matches(self, client):
        with app_module.app.app_context():
            _seed_material("6204", "深沟球轴承", brand="SKF")
            _seed_material("6205", "深沟球轴承", brand="NSK")
            _seed_material("M8", "六角螺母")
        r = client.get("/mobile/api/material_archive/search?keyword=轴承")
        body = r.get_json()
        assert len(body["data"]) == 2
        assert body["total"] == 2
        codes = {d["code"] for d in body["data"]}
        assert codes == {"6204", "6205"}

    def test_t5_batched_image_count_correct(self, client):
        with app_module.app.app_context():
            m1 = _seed_material("IMG1", "有图")
            m2 = _seed_material("IMG2", "无图")
            _seed_image(m1, "x.png")
            _seed_image(m1, "y.png")
        r = client.get("/mobile/api/material_archive/search")
        body = r.get_json()
        counts = {d["code"]: d["image_count"] for d in body["data"]}
        assert counts["IMG1"] == 2
        assert counts["IMG2"] == 0


class TestAndroidAutoLoad:
    def test_t6_auto_load_on_open_and_no_hard_limit(self):
        src = KT.read_text(encoding="utf-8")
        assert "LaunchedEffect(Unit)" in src, "进入页面应自动触发加载"
        assert "viewModel.search()" in src
        # 后端 search 路由不再硬编码 .limit(50)（只检查非注释代码行，注释里的历史描述不算）
        mobile_src = (ROOT / "app/routes/mobile.py").read_text(encoding="utf-8")
        code_lines = [l for l in mobile_src.splitlines() if l.strip() and not l.strip().startswith("#")]
        assert not any(".limit(50)" in l for l in code_lines), "物料档案搜索不应再硬编码 .limit(50)"
        assert ".limit(_MATERIAL_ARCHIVE_BROWSE_MAX)" in mobile_src
