# -*- coding: utf-8 -*-
"""语音建单：六层降级物料匹配测试（AA2）。

设计信条（用户原话）："我需要是一个聪明的 AI，能管理仓库的 AI"。
即：匹配不到时**主动降级**（词根 → 规格 → AI 匹配），而不是甩一句"没听清"。

六层降级顺序（_match_voice_material）：
  1. 别名表直查        AIMaterialAlias.alias_key（用户上次纠正过的说法）
  2. 完整关键词精确 code
  3. 完整关键词模糊     code/name/spec LIKE
  4. 词根降级 + 规格相似度排序    ★ "聪明"的关键：8*25螺丝 匹配不到时退到搜「螺丝」
  5. 仅用规格搜 spec
  6. AI 四级匹配        _ai_material_match_one

验收：
- T1 精确 code 命中 → success
- T2 唯一模糊命中 → success
- T3 多命中 → multiple（带相似度排序）
- T4 **词根降级**：8*25螺丝 整体无匹配，退到「螺丝」并列出候选
- T5 降级后规格强命中且唯一 → 直接 success（省用户点选）
- T6 规格相似度排序正确（8*25 > 8*30）
- T7 别名表命中 → success
- T8 全失败 → not_found 且带 strategies_tried（可向用户解释试过什么，符合 R5）
- T9 空输入安全
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "app"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP_DIR))
os.chdir(APP_DIR)

os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["WMS_DATABASE_URI"] = "sqlite:///:memory:"
os.environ.setdefault("WMS_DEBUG", "0")
os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")

import app as app_module  # noqa: E402
from app import (  # noqa: E402
    AIMaterialAlias, Material, MaterialCategory, Unit, Warehouse, db,
)

app_module.app.config["TESTING"] = True
app_module.app.config["WTF_CSRF_ENABLED"] = False

import importlib.util  # noqa: E402

_na_spec = importlib.util.spec_from_file_location(
    "na_voice_match", APP_DIR / "routes/native_api.py"
)
NA = importlib.util.module_from_spec(_na_spec)
_na_spec.loader.exec_module(NA)

match = NA._match_voice_material
similarity = NA._voice_spec_similarity
split_root = NA._voice_split_root


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed():
    """建一个含多规格螺丝的物料档案，用于验证降级与排序。"""
    with app_module.app.app_context():
        _reset_db()
        db.session.add_all([
            Unit(name="个", code="PCS"),
            MaterialCategory(name="默认分类", code="CAT-DEFAULT"),
            Warehouse(code="WHA", name="仓库A", is_default=True, status="active"),
        ])
        db.session.commit()
        rows = [
            ("M001", "内六角螺丝", "8*25"),
            ("M002", "内六角螺丝", "8*30"),
            ("M003", "内六角螺丝", "10*25"),
            ("M004", "外六角螺栓", "8*25"),
            ("M005", "轴承", "6204"),
        ]
        for code, name, spec in rows:
            db.session.add(Material(code=code, name=name, spec=spec,
                                    category_id=1, unit_id=1, stock=0, price=1))
        db.session.commit()


def _codes(matches):
    return [m["material"].code for m in matches]


# ── T1 精确 code ────────────────────────────────────────────────

def test_t1_exact_code():
    _seed()
    with app_module.app.app_context():
        r = match("M001", "", None)
        assert r["status"] == "success"
        assert r["material"].code == "M001"
        assert "exact_code" in r["strategies_tried"]


# ── T2 唯一模糊 ─────────────────────────────────────────────────

def test_t2_unique_fuzzy():
    _seed()
    with app_module.app.app_context():
        # 「6204」只在 M005 的规格出现一次 → 唯一模糊命中
        r = match("6204", "", None)
        assert r["status"] == "success"
        assert r["material"].code == "M005"


# ── T3 多命中 ───────────────────────────────────────────────────

def test_t3_multiple_matches():
    _seed()
    with app_module.app.app_context():
        r = match("内六角螺丝", "", None)
        assert r["status"] == "multiple"
        assert len(r["matches"]) == 3  # M001/M002/M003
        # 多命中时不得擅自选一个
        assert r["material"] is None


# ── T4 词根降级（核心：聪明的地方）──────────────────────────────

def test_t4_root_fallback_never_gives_up():
    """「8*25螺丝」整体匹配不到，必须退到词根「螺丝」并给出候选。"""
    _seed()
    with app_module.app.app_context():
        r = match("8*25螺丝", "8*25", None)
        # 不得返回 not_found——降级搜索必须捞出候选
        assert r["status"] in ("success", "multiple"), f"不应放弃：{r}"
        assert "root_fallback" in r["strategies_tried"], r["strategies_tried"]
        assert r["root"] == "螺丝"
        # 候选必须都是螺丝类物料
        assert all("螺丝" in (m["material"].name or "") or
                   "螺栓" in (m["material"].name or "")
                   for m in r["matches"])


def test_t4b_root_fallback_ranks_spec_exact_first():
    """降级候选中，规格完全对上的（8*25）必须排在前面。"""
    _seed()
    with app_module.app.app_context():
        r = match("8*25螺丝", "8*25", None)
        codes = _codes(r["matches"])
        # M001（内六角螺丝 8*25）规格完全匹配，必须排第一
        assert codes[0] == "M001", f"排序错误：{codes}"
        # 规格相似度必须单调不增
        scores = [m["score"] for m in r["matches"]]
        assert scores == sorted(scores, reverse=True), scores


# ── T5 降级后强命中唯一 → 直接 success ──────────────────────────

def test_t5_strong_unique_becomes_success():
    """只有一条规格完全匹配时，直接命中，省用户一次点选。"""
    _seed()
    with app_module.app.app_context():
        # 先删掉重复的 8*25（M004），只剩 M001 一条 8*25
        m4 = Material.query.filter_by(code="M004").first()
        db.session.delete(m4)
        db.session.commit()

        r = match("8*25内六角螺丝", "8*25", None)
        assert r["status"] == "success", r
        assert r["material"].code == "M001"


# ── T6 相似度打分 ───────────────────────────────────────────────

def test_t6_similarity_scoring():
    assert similarity("8*25", "8*25") == 100
    assert similarity("8X25", "8*25") == 95
    assert similarity("M8*25", "8*25") == 90
    # 部分匹配（8 对上、25 vs 30 不对）应低于完全匹配
    assert similarity("8*30", "8*25") < similarity("8*25", "8*25")
    # 空规格给低分但不为负
    assert similarity("", "8*25") < 50
    assert similarity("8*25", "") == 0


# ── T7 别名表命中 ───────────────────────────────────────────────

def test_t7_alias_hit():
    _seed()
    with app_module.app.app_context():
        from app import _ai_material_alias_key
        alias_key = _ai_material_alias_key("老张家的螺丝")
        db.session.add(AIMaterialAlias(
            alias="老张家的螺丝", alias_key=alias_key, material_id=1,
            source="voice_out", use_count=5, disabled=False,
        ))
        db.session.commit()

        r = match("老张家的螺丝", "", None)
        assert r["status"] == "success"
        assert r["material"].code == "M001"
        assert r["matches"][0]["strategy"] == "alias"


# ── T8 全失败 → not_found 带诊断 ────────────────────────────────

def test_t8_not_found_reports_what_was_tried():
    _seed()
    with app_module.app.app_context():
        r = match("完全不存在的物料XYZ", "", None)
        assert r["status"] == "not_found"
        assert r["material"] is None
        # 必须能告诉用户「我试过哪些策略」，而不是干巴巴一句没听清
        assert r["strategies_tried"], "必须记录尝试过的策略"
        assert len(r["strategies_tried"]) >= 3


# ── T9 空输入安全 ───────────────────────────────────────────────

def test_t9_empty_input_safe():
    _seed()
    with app_module.app.app_context():
        for kw, sp in (("", ""), ("   ", ""), ("", "")):
            r = match(kw, sp, None)
            assert r["status"] == "not_found"
            assert r["material"] is None


def test_t9b_split_root_helper():
    assert split_root("8*25螺丝", "8*25") == ("螺丝", "8*25")
    assert split_root("螺丝", "8*25") == ("螺丝", "8*25")
    # 「6芯电缆」能识别出词根「电缆」
    assert split_root("6芯电缆", "") == ("电缆", "")
    # 未知专有叫法不丢失：整体当词根
    root, _ = split_root("特种石英砂", "")
    assert root == "特种石英砂"
