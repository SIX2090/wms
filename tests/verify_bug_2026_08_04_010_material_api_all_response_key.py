# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-010 回归测试：复制物料后采购入库单不显示

原 Bug：
  各单据页（in_order_add.html、out_order_add.html、adjustment_add.html、
  document_table_form.html）的“刷新物料”逻辑只拉取第一页（默认 500 条），
  而物料按编码升序排列，新增/复制的物料编码通常排在末尾，被分页截断后
  永远无法出现在采购入库单等单据的下拉列表中。

修复：
  后端 `/material/api/all` 返回 `materials` 数组（前端实际读取的键）与分页元数据；
  前端 `refreshMaterials` 改为递归分页拉取全部物料，避免新增/复制物料（按编码
  升序排在末尾）因分页截断而看不到。

测试：
  T1. /material/api/all 返回 materials 数组与分页元数据（total/page/per_page/truncated/next_page）
  T2. /material/api/all 返回 materials 数组（前端实际读取的键）
  T3. 复制物料 -> 改规格 -> 保存，新物料出现在 /material/api/all 的 materials 中
  T3b.（反向断言）复制草稿的 name/spec 与原物料完全相同时必须被拒——
      「同名同规格不能重复」是业务规则，不是 bug

口径说明（BUG-2026-08-16-017 F4，2026-09-12 定稿）：
  /material/<id>/copy 的 docstring 是 "Return a material draft for user review
  before creating a new record" —— 它是 **草稿 DRAFT**，设计意图就是预填后由
  用户改动。name+spec 唯一性校验（material_name_spec_exists，不看 code）是
  有意为之：否则库里会出现两条完全相同的物料记录，那才是真问题。
  故 T3 走真实正确流程「复制 → 改规格 → 保存」，并用 T3b 把该规则钉死；
  若哪天有人把唯一性校验改松，T3b 立刻红。
"""
from __future__ import annotations

import os
import sys
import re
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
from app import db, User, Material  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    db.session.add(user)
    db.session.commit()


def _login(client):
    login_page = client.get("/login").get_data(as_text=True)
    m = re.search(r'name="csrf_token".*?value="([^"]+)"', login_page)
    token = m.group(1) if m else ""
    client.post("/login", data={
        "username": "admin", "password": "admin", "csrf_token": token})


class TestBug20260804010MaterialApiAllResponseKey:
    """/material/api/all 必须返回前端读取的 materials 键。"""

    def _seed_material(self):
        db.session.add(Material(code="M001", name="轴承", spec="6204", price=10))
        db.session.commit()

    def test_T1_returns_pagination_metadata(self):
        """返回分页元数据（total/page/per_page/pages），前端据此递归翻页。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            self._seed_material()
            client = app_module.app.test_client()
            _login(client)
            resp = client.get("/material/api/all")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success"
            assert isinstance(data["materials"], list), "materials 应为数组"
            assert data["total"] == 1
            assert data["page"] == 1
            assert data["per_page"] >= 1
            assert "truncated" in data
            assert "next_page" in data

    def test_T2_returns_materials_array(self):
        """materials 键为数组且包含物料（前端实际读取的键）。"""
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            self._seed_material()
            client = app_module.app.test_client()
            _login(client)
            resp = client.get("/material/api/all")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            assert data["status"] == "success"
            assert isinstance(data["materials"], list), "materials 应为数组"
            assert any(m["code"] == "M001" for m in data["materials"])

    def test_T3_copied_material_appears_in_materials(self):
        """复制物料 -> 改规格 -> 保存后，新物料出现在 materials 中。

        复制拿到的是**草稿**（docstring: "a material draft for user review"），
        必须改动 name 或 spec 才能保存——同名同规格会被唯一性校验拒掉。
        """
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            self._seed_material()
            client = app_module.app.test_client()
            _login(client)

            # 复制物料，获取建议编码
            copy_resp = client.post("/material/1/copy")
            assert copy_resp.status_code == 200, copy_resp.get_data(as_text=True)
            copy_data = copy_resp.get_json()
            assert copy_data["status"] == "success", copy_data
            suggested_code = copy_data["material"]["suggested_code"]
            suggested_name = copy_data["material"]["name"]
            assert suggested_code, "应生成建议编码"

            # 保存复制后的物料：spec 改成不同值（区分新旧物料）
            new_spec = "6204-1"
            add_resp = client.post("/material/add", data={
                "code": suggested_code,
                "name": suggested_name,
                "spec": new_spec,
                "brand": "",
                "price": "10",
            })
            assert add_resp.status_code == 200, add_resp.get_data(as_text=True)
            add_data = add_resp.get_json()
            assert add_data["status"] == "success", add_data

            # 新物料必须出现在 /material/api/all 的 materials 中
            resp = client.get("/material/api/all")
            assert resp.status_code == 200, resp.get_data(as_text=True)
            data = resp.get_json()
            codes = [m["code"] for m in data["materials"]]
            assert suggested_code in codes, \
                f"复制后的物料 {suggested_code} 应出现在 materials 中，实际为 {codes}"

    def test_T3b_copy_draft_unchanged_name_spec_rejected(self):
        """反向断言：复制草稿原样提交（name+spec 与原物料全同）必须被拒。

        锁定业务规则「同名同规格不能重复」——不校验 code 而校验 name+spec，
        是为了避免库里出现两条完全相同的物料。若此断言失败，说明唯一性校验
        被改松了，需人工确认是否有意为之。
        """
        with app_module.app.app_context():
            _reset_db()
            _seed_admin()
            self._seed_material()  # Material(code="M001", name="轴承", spec="6204")
            client = app_module.app.test_client()
            _login(client)

            copy_resp = client.post("/material/1/copy")
            assert copy_resp.status_code == 200, copy_resp.get_data(as_text=True)
            copy_data = copy_resp.get_json()
            draft = copy_data["material"]

            # 用草稿原样的 name + spec 提交（只换了 code）——必须被拒
            add_resp = client.post("/material/add", data={
                "code": draft["suggested_code"],
                "name": draft["name"],
                "spec": draft["spec"],
                "brand": "",
                "price": "10",
            })
            add_data = add_resp.get_json()
            assert add_resp.status_code == 400, add_data
            assert add_data["status"] == "error", add_data
            assert "重复" in add_data["msg"], add_data

            # 确认没有偷偷写进库
            from app import Material as _M
            assert _M.query.filter_by(code=draft["suggested_code"]).first() is None, \
                "被拒的复制不应落库"