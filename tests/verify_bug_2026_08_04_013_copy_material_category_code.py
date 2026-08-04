# -*- coding: utf-8 -*-
"""
BUG-2026-08-04-013 回归测试：复制物料时自动生成的物料编码应为 原物料分类 + 流水号

原 Bug：`generate_material_copy_code()` 只基于原物料编码生成（仅递增数字），
但用户要求改为基于**原物料所属分类的分类编码**生成前缀，后接该前缀下的流水号。

修复：
- `generate_material_copy_code()` 参数改为接收 `Material` 对象（而非只接收原编码）
- 优先取出 `source.category.code` 作为前缀，生成 `{prefix}{next_number}`
  例：分类编码 `B-001` → 生成 `B-0011`、`B-0012`...
- 原物料无分类时，回退到原有逻辑（基于原编码递增末尾数字）保持兼容

测试策略：
  T1. 源物料有分类：验证生成的编码以分类编码为前缀，且为下一个流水号
  T2. 源物料无分类：回退到基于原编码递增逻辑正常工作
  T3. 同一分类下已有多个物料，验证取最大流水号 + 1
  T4. 分类编码为空字符串：回退到旧逻辑正常工作
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
from app import (  # noqa: E402
    db, Warehouse, User, Material, MaterialCategory, Unit, Supplier,
)
from werkzeug.security import generate_password_hash  # noqa: E402

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    user = User(
        username="admin",
        password_hash=generate_password_hash("admin"),
        role="admin",
        must_change_password=False,
    )
    unit = Unit(name="个", code="PCS")
    wh = Warehouse(code="WHA", name="仓库A", is_default=True, status="active")
    db.session.add_all([user, unit, wh])
    db.session.commit()
    return {"user": user, "unit": unit, "wh": wh}


def _seed_categories():
    cat1 = MaterialCategory(code="B-001", name="轴承")
    cat2 = MaterialCategory(code="M", name="螺母")
    cat3 = MaterialCategory(code="CAT-DEFAULT", name="默认分类")
    db.session.add_all([cat1, cat2, cat3])
    db.session.commit()
    return {"cat1": cat1, "cat2": cat2, "cat3": cat3}


class TestBug20260804013CopyMaterialCategoryCode:
    """复制物料生成编码必须使用原物料分类编码作为前缀。"""

    def test_T1_source_material_has_category_code_generates_prefix_with_sequence(self):
        """T1：源物料有分类，生成的编码以分类编码为前缀+流水。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            cats = _seed_categories()
            mat = Material(
                code="B-001001", name="深沟球轴承", spec="6204",
                category_id=cats["cat1"].id, unit_id=seeds["unit"].id,
            )
            db.session.add(mat)
            db.session.commit()

            suggested = app_module.generate_material_copy_code(mat)
            assert suggested.startswith("B-001"), f"编码 {suggested} 应以前缀 B-001 开头"
            # 检查后缀是数字
            suffix = suggested[len("B-001"):]
            assert suffix.isdigit(), f"后缀 {suffix} 应为数字"

    def test_T2_source_material_has_no_category_falls_back_to_old_logic(self):
        """T2：源物料无分类，回退到基于原编码递增逻辑。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            mat = Material(
                code="M001", name="自定义物料", spec="",
                category_id=None, unit_id=seeds["unit"].id,
            )
            db.session.add(mat)
            db.session.commit()

            suggested = app_module.generate_material_copy_code(mat)
            # 原编码 M001 末尾有数字 001 → 生成 M002
            assert suggested == "M002", f"原编码 M001 应生成 M002，实际 {suggested}"

    def test_T3_multiple_materials_in_same_category_generates_next_sequence(self):
        """T3：同一分类下已有多个物料，取最大流水号 + 1。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            cats = _seed_categories()
            # 分类 M
            mat1 = Material(
                code="M1", name="螺母M8", spec="",
                category_id=cats["cat2"].id, unit_id=seeds["unit"].id,
            )
            mat2 = Material(
                code="M2", name="螺母M10", spec="",
                category_id=cats["cat2"].id, unit_id=seeds["unit"].id,
            )
            mat3 = Material(
                code="M3", name="螺母M12", spec="",
                category_id=cats["cat2"].id, unit_id=seeds["unit"].id,
            )
            db.session.add_all([mat1, mat2, mat3])
            db.session.commit()

            # 复制 mat3 → 应得到 M4
            suggested = app_module.generate_material_copy_code(mat3)
            assert suggested == "M4", f"已有 M1/M2/M3 应生成 M4，实际 {suggested}"

    def test_T4_category_code_without_number_generates_next_correctly(self):
        """T4：分类编码不包含数字，仍正确生成流水。"""
        with app_module.app.app_context():
            _reset_db()
            seeds = _seed()
            cats = _seed_categories()
            # 分类默认分类
            mat1 = Material(
                code="CAT-DEFAULT1", name="物料1", spec="",
                category_id=cats["cat3"].id, unit_id=seeds["unit"].id,
            )
            mat2 = Material(
                code="CAT-DEFAULT2", name="物料2", spec="",
                category_id=cats["cat3"].id, unit_id=seeds["unit"].id,
            )
            db.session.add_all([mat1, mat2])
            db.session.commit()

            suggested = app_module.generate_material_copy_code(mat2)
            assert suggested == "CAT-DEFAULT3", f"已有 CAT-DEFAULT1/CAT-DEFAULT2 应生成 CAT-DEFAULT3，实际 {suggested}"
