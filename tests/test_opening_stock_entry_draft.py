# -*- coding: utf-8 -*-
"""P1-D 期初录入草稿防丢回归。

用户场景（原话大意）：「期初几百个物料，扫码枪扫到一半刷新一下，全没了，
只能重扫一遍 —— 而且扫漏了自己都不知道。」

方案：把当前录入网格 + 表头三件套按**单据维度**存进 localStorage；
重新进入页面时若检测到未保存草稿，显形提示条，用户点「恢复草稿」才应用。

本文件覆盖能在服务端/静态层验证的部分：
  T1  模板渲染出草稿提示条（默认 hidden，不打扰正常用户）
  T2  草稿 key 按单据隔离：新建页与编辑页的 DRAFT_SCOPE 不同
  T3  编辑页的草稿作用域含单据 id（不串到新建页）
  T4  关键函数齐备（collectDraftRows / persistDraftNow / restoreDraft / ...）
  T5  保存成功后清草稿（否则下次进来提示"有草稿"，恢复出已落库的行）
  T6  清空录入 / 新增 会一并清草稿（用户明确说"不要了"）
  T7  空行不入草稿（避免刚打开页面就凭空多一行）
  T8  已建账行也入草稿且保留 line_id（否则恢复后保存会变新增行）
  T9  localStorage 读写都有 try/catch 兜底（无痕模式/配额满不得报错）
  T10 beforeunload / pagehide 补写（防抖窗口内直接关页也不丢）
  T11 恢复必须由用户点按钮触发，不自动覆盖当前内容
  T12 表头三件套（日期/仓库/备注）也在草稿里
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

TEMPLATE = APP_DIR / "templates" / "opening_stock.html"


def _template_src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


class TestOpeningStockDraftTemplate:
    """静态契约：模板里草稿机制的代码与结构。"""

    def test_t1_template_has_hidden_draft_banner(self):
        src = _template_src()
        assert 'id="draftBanner"' in src, "必须有草稿提示条容器"
        # 默认 hidden：没草稿时不能占位打扰用户
        m = re.search(r'<div class="draft-banner" id="draftBanner"([^>]*)>', src)
        assert m, "草稿提示条结构未找到"
        assert "hidden" in m.group(1), "草稿提示条必须默认 hidden"

    def test_t1b_banner_has_restore_and_discard(self):
        src = _template_src()
        assert "restoreDraft()" in src, "必须有「恢复草稿」按钮"
        assert "discardDraft()" in src, "必须有「丢弃并清除」按钮"

    def test_t4_required_functions_declared(self):
        src = _template_src()
        for fn in ("collectDraftRows", "collectDraftHeader", "persistDraftNow",
                   "scheduleDraftSave", "clearDraft", "readDraft",
                   "checkDraftOnLoad", "restoreDraft", "discardDraft",
                   "hideDraftBanner", "isMeaningfulRow", "draftSavedAgoText"):
            assert re.search(r"function\s+%s\s*\(" % fn, src), "缺少函数 %s" % fn

    def test_t2_draft_key_is_scoped_per_document(self):
        """草稿 key 必须按单据维度：新建页是 'new'，编辑页是单据 id。"""
        src = _template_src()
        assert "DRAFT_KEY_PREFIX" in src, "草稿 key 必须有统一前缀"
        assert "const DRAFT_SCOPE" in src, "必须有草稿作用域计算"
        assert "OPENING_DOC.id" in src.split("const DRAFT_SCOPE")[1][:200], (
            "草稿作用域必须取自当前单据 id"
        )
        # 新建页回落到 'new'
        assert re.search(r"OPENING_DOC\.id\s*\?", src), (
            "新建页（无 OPENING_DOC）必须回落到固定 scope"
        )

    def test_t5_save_success_clears_draft(self):
        """保存成功后必须清草稿 —— 草稿语义是'未落库的改动'。"""
        src = _template_src()
        seg = src[src.index("function saveDocument"):]
        seg = seg[:seg.index("function showPasteModal")]
        assert "clearDraft()" in seg, "saveDocument 成功后必须调用 clearDraft()"

    def test_t6_clear_and_reset_clear_draft(self):
        for fn_name, next_fn in (("function clearEntryRows", "function copyPreviousRow"),
                                 ("function resetDocument", "function navigateOpeningDoc")):
            src = _template_src()
            seg = src[src.index(fn_name):]
            seg = seg[:seg.index(next_fn)]
            assert "clearDraft()" in seg, "%s 必须清草稿（用户明确说不要了）" % fn_name

    def test_t7_empty_rows_excluded(self):
        src = _template_src()
        seg = src[src.index("function isMeaningfulRow"):]
        seg = seg[:seg.index("function collectDraftRows")]
        assert "material_id" in seg and "quantity" in seg, "空行判定必须看业务字段"
        # collectDraftRows 必须用 isMeaningfulRow 过滤
        seg2 = src[src.index("function collectDraftRows"):]
        seg2 = seg2[:seg2.index("function collectDraftHeader")]
        assert "filter(isMeaningfulRow)" in seg2, "草稿必须只收集动过的行"

    def test_t8_saved_lines_keep_line_id(self):
        """已建账行（line_id）必须一起存 —— 详情页改了没保存就刷新同样会丢。"""
        src = _template_src()
        seg = src[src.index("function collectDraftRows"):]
        seg = seg[:seg.index("function collectDraftHeader")]
        assert "line_id" in seg, "草稿必须保留 line_id，否则恢复后保存会变新增行"

    def test_t9_localstorage_calls_are_guarded(self):
        """localStorage 读写必须在 try/catch 内（无痕模式会直接抛异常）。"""
        src = _template_src()
        for fn_name, next_fn in (("function readDraft", "function persistDraftNow"),
                                 ("function persistDraftNow", "function scheduleDraftSave"),
                                 ("function clearDraft", "function draftSavedAgoText")):
            seg = src[src.index(fn_name):]
            seg = seg[:seg.index(next_fn)]
            if "localStorage." in seg:
                assert "try" in seg and "catch" in seg, (
                    "%s 里的 localStorage 调用必须包 try/catch（草稿不能拖垮录入）"
                    % fn_name
                )

    def test_t10_flush_on_unload(self):
        src = _template_src()
        assert "beforeunload" in src, "必须在 beforeunload 补写草稿"
        assert "pagehide" in src, "必须补 pagehide（iOS Safari 不一定触发 beforeunload）"

    def test_t11_draft_not_auto_applied(self):
        """草稿不得自动覆盖当前内容 —— 只有用户点「恢复」才应用。"""
        src = _template_src()
        seg = src[src.index("function checkDraftOnLoad"):]
        seg = seg[:seg.index("function restoreDraft")]
        assert "banner.hidden = false" in seg, "加载时只负责显形提示条"
        assert "rows =" not in seg, "加载检查阶段不得直接改 rows（那是自动应用）"

    def test_t12_header_fields_in_draft(self):
        src = _template_src()
        seg = src[src.index("function collectDraftHeader"):]
        seg = seg[:seg.index("function readDraft")]
        for field in ("headerDocDate", "headerWarehouse", "headerRemark"):
            assert field in seg, "表头字段 %s 必须进草稿" % field

    def test_t13_render_rows_must_not_write_draft(self):
        """renderRows() 不得落草稿 —— 这是踩过的坑，必须锁死。

        背景（实测复现）：曾把 scheduleDraftSave() 放在 renderRows() 末尾。
        renderRows() 不只在用户编辑时跑，它在**页面加载 / 服务端行回填**时也跑，
        于是：
          ① 打开一张已建账的单据就凭空写出一份草稿 → 用户什么都没改，
             刷新却提示"检测到未保存的草稿"；
          ② 保存成功后 clearDraft() 刚把草稿清掉，紧随其后的 700ms 跳转
             重新加载页面，renderRows() 又把它写回来 → 草稿"复活"，
             用户下次进来恢复出一堆已经落库的行，以为保存没生效。
        修法：落草稿一律由"用户意图"驱动（updateField / addRow / insertRowAfter /
        copyPreviousRow / selectMaterial / deleteRow / 表头输入），renderRows() 只渲染。
        """
        src = _template_src()
        seg = src[src.index("function renderRows()"):]
        # 函数体直到下一个顶层 function 定义为止
        nxt = seg.index("\nfunction ", 1)
        body = seg[:nxt]
        # 注释里提到 scheduleDraftSave 是允许的（说明为什么不能放），
        # 但不能出现**实际调用** —— 去掉注释行后再断言。
        code_only = "\n".join(
            ln for ln in body.splitlines()
            if not ln.lstrip().startswith("//")
        )
        assert "scheduleDraftSave()" not in code_only, (
            "renderRows() 里不得调用 scheduleDraftSave()：页面加载/行回填也会走这里，"
            "会写出幽灵草稿并在保存后把已清草稿重新写回"
        )

    def test_t14_draft_written_by_user_intent_entries(self):
        """草稿必须由用户意图入口写 —— 与 T13 配对，防止"哪都不写"。

        T13 禁止 renderRows() 落草稿；如果只做 T13 而漏了这些入口，
        草稿功能就等于整个失效（用户录入半天一行都没存）。两条一起才完整。
        """
        src = _template_src()

        def body_of(fn_name: str) -> str:
            """取函数体：从签名到下一个顶层 function 定义为止（不依赖函数顺序）。"""
            seg = src[src.index(fn_name):]
            nxt = seg.find("\nfunction ", 1)
            return seg if nxt < 0 else seg[:nxt]

        for fn_name in ("updateField", "addRow", "insertRowAfter",
                        "copyPreviousRow", "deleteRow", "selectMaterial"):
            assert "scheduleDraftSave()" in body_of("function %s(" % fn_name), (
                "%s 是用户意图入口，必须落草稿（否则录入内容在刷新后仍会丢）" % fn_name
            )

    def test_t15_save_clears_draft_in_every_persist_path(self):
        """所有真正的落库路径成功后都必须清草稿。

        期初有两条落库路径：手工「保存」(saveDocument) 与「粘贴导入」
        (doPasteImport)。两条都直接写库，草稿在成功后都必须消失，
        否则 700ms 跳转后的详情页会拿残留草稿提示"有未保存改动"。
        """
        src = _template_src()
        assert src.count("clearDraft()") >= 3, (
            "至少三处要清草稿：saveDocument 成功分支、doPasteImport 成功分支、清空/重置"
        )
        # 两条落库路径的成功分支各自都要有
        for fn_name in ("function saveDocument", "function doPasteImport"):
            seg = src[src.index(fn_name):]
            seg = seg[:seg.index("\nfunction ", 1)]
            assert "clearDraft()" in seg, "%s 成功落库后必须清草稿" % fn_name


class TestOpeningStockDraftRendered:
    """渲染层：页面真的能跑起来，且草稿 key 按单据隔离。"""

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
        db.session.add(self.wh1)
        db.session.flush()
        self.m1 = Material(code="M001", name="螺丝", unit_id=unit.id, stock=0)
        db.session.add(self.m1)
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

    def _add_page(self):
        resp = self.client.get("/opening_stock/add")
        assert resp.status_code == 200, resp.status_code
        return resp.get_data(as_text=True)

    def _edit_page(self):
        resp = self.client.post("/opening_stock/save", json={
            "warehouse_id": self.wh1.id, "date": "2026-09-01",
            "items": [{"material_id": self.m1.id, "warehouse_id": self.wh1.id,
                       "quantity": 100, "price": 1.0}],
        })
        assert resp.status_code == 200, resp.get_data(as_text=True)
        doc_id = resp.get_json()["doc_id"]
        resp = self.client.get("/opening_stock/%d" % doc_id)
        assert resp.status_code == 200, resp.status_code
        return doc_id, resp.get_data(as_text=True)

    def test_t13_add_page_renders_draft_scope_new(self):
        html = self._add_page()
        assert 'id="draftBanner"' in html, "新建页应有草稿提示条"
        assert "window.__OPENING_DOC__ = null" in html, "新建页单据上下文应为空"
        # 作用域回落到 'new'
        assert "'new'" in html or '"new"' in html, "新建页草稿作用域应为 new"

    def test_t14_edit_page_scopes_draft_to_doc_id(self):
        doc_id, html = self._edit_page()
        assert 'id="draftBanner"' in html, "编辑页应有草稿提示条"
        # 单据 id 注入到页面（供草稿作用域用）
        assert re.search(r"id:\s*%d\b" % doc_id, html), "编辑页必须注入单据 id"
        assert "const DRAFT_SCOPE" in html, "编辑页必须计算草稿作用域"

    def test_t15_draft_banner_starts_hidden_on_both_pages(self):
        for html in (self._add_page(), self._edit_page()[1]):
            m = re.search(r'<div class="draft-banner" id="draftBanner"([^>]*)>', html)
            assert m and "hidden" in m.group(1), "服务端渲染时必须 hidden"

    def test_t16_draft_js_survives_template_render(self):
        """模板渲染后草稿逻辑不能出现 Jinja 未替换的残渣。"""
        html = self._add_page()
        assert "{{" not in html.split("draftBanner")[1][:3000], (
            "草稿区块附近不应有未渲染的 Jinja 表达式"
        )
        assert "localStorage" in html, "草稿机制必须真的输出到页面"
