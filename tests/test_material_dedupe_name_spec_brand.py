# -*- coding: utf-8 -*-
"""物料建档判重口径（名称 + 规格 + 品牌）回归。

背景（2026-09-25，生产库实测）：
  生产库 1261 条物料里「名称 + 规格」完全相同的只有 3 组 6 条，看似判重有效；
  但全库 8 个建物料入口中**只有新增/编辑两个**做了判重，Excel 导入、单据批量
  导入、BOM 导入、手机端未匹配建档、AI 单据识别建档一条都没做。那 3 组的
  created_at 相差 0~3 毫秒 —— 实锤来自批量导入，不是手工录入。
  另有 3 组是精确匹配被空格/大小写绕过的真一物多码（'25KA' vs '25kA'、
  'LA38-11 绿色' vs 'LA38-11绿色'、'10kV…XGN - 12/V' vs '10KV…XGN-12/V'）。

口径（与业务方确认 2026-09-25，第二轮收紧）：
  - 硬挡键 = 名称 + 规格 + **品牌**，归一化到「去空格 + 转小写」后比较：
    现场两种写法（'LA38-11 绿色' / 'LA38-11绿色'、'JKDB-25I/4P 25KA' / '25kA'）
    几乎都是同一件东西的录入误差，生产库 6 条疑似一物多码里 3 条正是这么
    进来的，必须挡住。
  - 仍**不**做 NFKC：存量 88 条规格含全角字符（'SC-120-12-镀锡（C）'），
    而 SQLite 无法对列值做 NFKC，只归一入参反而让全角/半角两种写法在库里
    双双对不上，检出率不升反降。
  - 品牌进键：同型号不同品牌是两个物料（欧姆龙 vs 西门子模块），生产库已有
    10 组同名不同品牌，不加品牌会把正常业务挡在门外。
  - 剩下两类差异（全角/半角、仅品牌不同）由 find_similar_materials() 做
    **软提示**：两端同时归一（NFKC + 去空白 + 转小写），提示存在、不阻断保存。

本测试钉死这套分工：硬挡只挡真正撞车的，软提示覆盖录入误差，两者不越界。
"""
from __future__ import annotations

import os
import sys
from io import BytesIO
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


def _reset_db():
    db.drop_all()
    db.create_all()


def _seed_admin():
    db.session.add(User(username="admin",
                        password_hash=generate_password_hash("admin"),
                        role="admin", must_change_password=False))
    db.session.commit()


def _client():
    """每个用例独立重置库并登录，避免用例间相互污染。"""
    with app_module.app.app_context():
        _reset_db()
        _seed_admin()
    client = app_module.app.test_client()
    client.post("/login", data={"username": "admin", "password": "admin"},
                content_type="application/x-www-form-urlencoded")
    return client


def _seed(code, name, spec=None, brand=None):
    with app_module.app.app_context():
        m = Material(code=code, name=name, spec=spec, brand=brand, stock=0)
        db.session.add(m)
        db.session.commit()
        return m.id


def _exists(name, spec=None, brand=None, exclude_id=None):
    with app_module.app.app_context():
        from app import material_name_spec_exists
        return material_name_spec_exists(name, spec, brand, exclude_id=exclude_id)


def _similar(name, spec=None, exclude_id=None):
    with app_module.app.app_context():
        from app import find_similar_materials
        return find_similar_materials(name, spec, exclude_id=exclude_id)


def _add(client, code, name, spec=None, brand=None):
    return client.post("/material/add", data={
        "code": code, "name": name, "spec": spec or "", "brand": brand or "",
    }, headers=AJAX_HEADERS)


def _make_xlsx(rows, headers=None):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(headers or ["编码", "名称", "规格", "品牌", "单价"])
    for r in rows:
        ws.append(r)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def _import(client, buf):
    return client.post("/material/import",
                       data={"file": (buf, "test.xlsx")},
                       content_type="multipart/form-data",
                       headers=AJAX_HEADERS)


# ---------------------------------------------------------------- 归一化函数

def test__material_dedupe_key():
    """硬挡键：去首尾与内部空白 + 转小写；不做 NFKC。"""
    from app import _material_dedupe_key

    assert _material_dedupe_key("  继电器  ") == "继电器"
    assert _material_dedupe_key(None) == ""
    assert _material_dedupe_key("LA38-11 绿色") == "la38-11绿色", "内部空格必须去掉"
    assert _material_dedupe_key("LA38-11绿色") == _material_dedupe_key("LA38-11 绿色"), \
        "空格差异必须归一到同一个键"
    assert _material_dedupe_key("25kA") == _material_dedupe_key("25KA"), "大小写必须归一"
    assert _material_dedupe_key("镀锡（C）") == "镀锡（c）", "硬挡键不做 NFKC（全角括号保留）"


def test__material_dedupe_expr_matches_python_key():
    """SQL 侧表达式必须与 Python 侧键完全等价，否则判重会漏。

    这是本次最容易出错的地方：SQL 走 replace/lower，Python 走 str.replace/lower，
    两边一旦不一致（比如漏替全角空格），某些写法就会静默溜过判重。
    """
    from app import (_material_dedupe_expr, _material_dedupe_key, Material, db)

    samples = ["LA38-11 绿色", "JKDB-25I/4P 25KA", "SC-120-12-镀锡（C）",
               "  两端空白  ", "全角　空格", ""]
    with app_module.app.app_context():
        for text in samples:
            row = db.session.query(
                _material_dedupe_expr(db.literal(text)).label('k')
            ).first()
            assert row.k == _material_dedupe_key(text), f"SQL 与 Python 归一化不一致: {text!r}"


def test__material_similarity_key():
    """软提示键强归一：NFKC + 去全部空白 + 转小写。"""
    from app import _material_similarity_key

    assert _material_similarity_key("LA38-11 绿色") == "la38-11绿色"
    assert _material_similarity_key("LA38-11绿色") == "la38-11绿色"
    assert _material_similarity_key("JKDB-25I/4P 25KA") == _material_similarity_key("jkdb-25i/4p 25kA")
    assert _material_similarity_key("镀锡（C）") == _material_similarity_key("镀锡(C)"), "全角半角归一"
    assert _material_similarity_key(None) == ""


# ---------------------------------------------------------------- 硬挡判重

def test_material_name_spec_exists():
    """硬挡：名称+规格+品牌三者同时相同才判重，缺一不可。"""
    _client()
    _seed("DUP-1", "继电器底座", "PF113A-E", "欧姆龙")

    assert _exists("继电器底座", "PF113A-E", "欧姆龙") is True, "三键全同 → 判重"
    assert _exists("继电器底座", "PF113A-E", "西门子") is False, "品牌不同 → 不判重"
    assert _exists("继电器底座", "PF113A-EX", "欧姆龙") is False, "规格不同 → 不判重"
    assert _exists("接触器底座", "PF113A-E", "欧姆龙") is False, "名称不同 → 不判重"

    # 空格与大小写差异同样判重（2026-09-25 第二轮口径）
    _seed("DUP-2", "按钮", "LA38-11 绿色", None)
    assert _exists("按钮", "LA38-11绿色", None) is True, "去空格后相同 → 判重"

    _seed("DUP-3", "浪涌后备保护", "JKDB-25I/4P 25KA", None)
    assert _exists("浪涌后备保护", "JKDB-25I/4P 25kA", None) is True, "不分大小写后相同 → 判重"
    # 两者叠加也要挡住
    assert _exists("浪涌后备保护", "jkdb-25i/4p 25ka", None) is True


def test_material_name_spec_exists_excludes_self():
    """编辑时 exclude_id 必须生效，否则物料永远无法保存自己的原值。"""
    _client()
    mid = _seed("DUP-4", "模块前连接器40针", "6ES75921BM000XB0", "西门子")
    assert _exists("模块前连接器40针", "6ES75921BM000XB0", "西门子", exclude_id=mid) is False
    assert _exists("模块前连接器40针", "6ES75921BM000XB0", "西门子") is True


# ---------------------------------------------------------------- 软提示

def test_find_similar_materials():
    """软提示：忽略大小写/空格/全角/品牌后的撞车都要能被找出来。"""
    _client()
    _seed("SIM-1", "按钮", "LA38-11 绿色", None)          # 空格差异
    _seed("SIM-2", "浪涌后备保护", "JKDB-25I/4P 25KA", None)  # 大小写差异
    _seed("SIM-3", "SC铜接线端子", "SC-120-12-镀锡（C）", None)  # 全角差异
    _seed("SIM-4", "继电器底座", "PF113A-E", "欧姆龙")      # 品牌差异
    _seed("SIM-5", "微型断路器", "DZ47-60 C32", None)      # 无关物料，不应命中

    hit = _similar("按钮", "LA38-11绿色")
    assert any(h["code"] == "SIM-1" for h in hit), "空格差异必须提示"

    hit = _similar("浪涌后备保护", "JKDB-25I/4P 25kA")
    assert any(h["code"] == "SIM-2" for h in hit), "大小写差异必须提示"

    hit = _similar("SC铜接线端子", "SC-120-12-镀锡(C)")
    assert any(h["code"] == "SIM-3" for h in hit), "全角半角差异必须提示"

    hit = _similar("继电器底座", "PF113A-E")
    assert any(h["code"] == "SIM-4" for h in hit), "仅品牌不同也要提示（可能是漏填品牌）"

    hit = _similar("微型断路器", "DZ47-60 C32")
    assert not any(h["code"] == "SIM-1" for h in hit), "不得串到无关物料"

    assert _similar("", "") == [], "空名称不应触发全表扫描式的误报"
    mid = _seed("SIM-6", "空气开关", "SPEC-X", None)
    assert _similar("空气开关", "SPEC-X", exclude_id=mid) == [], "编辑时应排除自身"


# ---------------------------------------------------------------- 新增/编辑路由

def test_add_rejects_same_name_spec_brand():
    """T1：新增与存量「名称+规格+品牌」全同 → 400 且不落库。"""
    client = _client()
    _seed("ADD-1", "模块前连接器40针", "6ES75921BM000XB0", "西门子")
    resp = _add(client, "ADD-2", "模块前连接器40针", "6ES75921BM000XB0", "西门子")
    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "不能同时重复" in (resp.get_json().get("msg") or "")
    with app_module.app.app_context():
        assert Material.query.filter_by(code="ADD-2").first() is None


def test_add_allows_different_brand():
    """T2：同名同规格但品牌不同 → 放行（同型号不同品牌是两个物料）。"""
    client = _client()
    _seed("ADD-3", "模拟量输入模块", "AI-8CH", "欧姆龙")
    resp = _add(client, "ADD-4", "模拟量输入模块", "AI-8CH", "西门子")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    with app_module.app.app_context():
        assert Material.query.filter_by(code="ADD-4").first() is not None


def test_add_rejects_space_and_case_variants():
    """T3：空格 / 大小写差异同样被硬挡（口径收紧后这两个不再放行）。"""
    client = _client()
    _seed("ADD-5", "按钮", "LA38-11 绿色", None)
    resp = _add(client, "ADD-6", "按钮", "LA38-11绿色", None)
    assert resp.status_code == 400, "去空格后撞车必须拒绝"
    assert "忽略空格与大小写" in (resp.get_json().get("msg") or "")
    with app_module.app.app_context():
        assert Material.query.filter_by(code="ADD-6").first() is None

    # 大小写差异同样拒绝
    _seed("ADD-7", "浪涌后备保护", "JKDB-25I/4P 25KA", None)
    resp = _add(client, "ADD-8", "浪涌后备保护", "JKDB-25I/4P 25kA", None)
    assert resp.status_code == 400, "不分大小写后撞车必须拒绝"
    with app_module.app.app_context():
        assert Material.query.filter_by(code="ADD-8").first() is None


def test_edit_rejects_same_name_spec_brand():
    """T4：编辑改成与另一条物料撞车 → 400；改成自己的原值 → 200。"""
    client = _client()
    other = _seed("EDIT-1", "塑壳断路器", "JKM1-1250M/3300 1250A", "正泰")
    mid = _seed("EDIT-2", "塑壳断路器待改", "SPEC-A", None)

    resp = client.post(f"/material/edit/{mid}", data={
        "code": "EDIT-2", "name": "塑壳断路器",
        "spec": "JKM1-1250M/3300 1250A", "brand": "正泰",
    }, headers=AJAX_HEADERS)
    assert resp.status_code == 400, "与 EDIT-1 撞车必须拒绝"

    resp = client.post(f"/material/edit/{mid}", data={
        "code": "EDIT-2", "name": "塑壳断路器待改", "spec": "SPEC-A", "brand": "",
    }, headers=AJAX_HEADERS)
    assert resp.status_code == 200, "保存自己的原值不得被自身判重挡住"
    assert other  # 仅确保变量被使用（EDIT-1 未被误改）


# ---------------------------------------------------------------- Excel 导入

def test_import_skips_duplicate_name_spec_brand():
    """T5：Excel 导入命中已存在的「名称+规格+品牌」→ 该行跳过并说明原因。

    这条是本次修复的主战场：导入此前**只查 code 重复**，生产库 3 组真重复里
    有 2 组由此进来。
    """
    client = _client()
    _seed("IMP-1", "10KV户内空气绝缘计量柜 XGN-12/M G02", None, None)
    buf = _make_xlsx([["IMP-2", "10KV户内空气绝缘计量柜 XGN-12/M G02", "", "", 0]])
    data = _import(client, buf).get_json()
    assert data["status"] == "success", data
    assert data["count"] == 0, "重复行必须被跳过"
    assert "重复" in (data.get("warnings") or ""), "必须告知跳过原因"
    with app_module.app.app_context():
        assert Material.query.filter_by(code="IMP-2").first() is None


def test_import_duplicate_does_not_abort_batch():
    """T6：重复行只跳过自己，同批次的正常行照常导入（不中断整批）。"""
    client = _client()
    _seed("IMP-3", "继电器底座", "PF113A-E", "欧姆龙")
    buf = _make_xlsx([
        ["IMP-4", "继电器底座", "PF113A-E", "欧姆龙", 0],   # 重复 → 跳过
        ["IMP-5", "接触器", "CJX2-1210", "正泰", 0],        # 正常 → 导入
    ])
    data = _import(client, buf).get_json()
    assert data["status"] == "success", data
    assert data["count"] == 1, "1 条正常行应导入"
    with app_module.app.app_context():
        assert Material.query.filter_by(code="IMP-4").first() is None
        assert Material.query.filter_by(code="IMP-5").first() is not None


def test_import_skips_intra_batch_duplicate():
    """T7：同一份 Excel 内部两行互相重复 → 第二行也要跳过（不能只查库）。"""
    client = _client()
    buf = _make_xlsx([
        ["IMP-6", "微型断路器", "DZ47-60 C32", "正泰", 0],
        ["IMP-7", "微型断路器", "DZ47-60 C32", "正泰", 0],
    ])
    data = _import(client, buf).get_json()
    assert data["status"] == "success", data
    assert data["count"] == 1, "同批次内部重复必须拦住第二条"
    with app_module.app.app_context():
        assert Material.query.filter_by(code="IMP-7").first() is None


def test_import_rejects_space_and_case_variants():
    """T8：导入仅空格/大小写不同的变体 → 同样跳过（不再放行 + 软提示）。"""
    client = _client()
    _seed("IMP-8", "按钮", "LA38-11 绿色", None)
    _seed("IMP-10", "浪涌后备保护", "JKDB-25I/4P 25KA", None)
    buf = _make_xlsx([
        ["IMP-9", "按钮", "LA38-11绿色", "", 0],                # 仅空格不同
        ["IMP-11", "浪涌后备保护", "JKDB-25I/4P 25kA", "", 0],   # 仅大小写不同
    ])
    data = _import(client, buf).get_json()
    assert data["status"] == "success", data
    assert data["count"] == 0, "空格/大小写变体必须被挡住"
    assert "重复" in (data.get("warnings") or ""), "必须告知跳过原因"
    with app_module.app.app_context():
        assert Material.query.filter_by(code="IMP-9").first() is None
        assert Material.query.filter_by(code="IMP-11").first() is None
