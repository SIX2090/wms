"""
回归验证：报表表格点击单据编号新标签页打开（2026-08-25 用户需求）

需求：
- 库存台账（以及任何带 link_field 的报表列）点击单据编号必须在新浏览器标签页打开单据详情；
- 原报表页保持打开、不关闭，便于对照查询。
- 不影响：单据详情本身渲染、Excel 导出、打印按钮等。

验收标准：
- T1: report_view.html 渲染的 report-doc-link <a> 必须含 target="_blank" 与 rel="noopener"
- T2: 后端 _report_detail_url 仍产出正确 in_order/<id>/out_order/<id> 路由（防退化）
- T3: 后端 REPORT_REFERENCE_LINKS 覆盖主流单据类型（in_order / out_order 等）
- T4: 全 report_view.html 中所有 report-doc-link 渲染点都已加 target="_blank"
- T5: 模板中链接样式保留（report-doc-link 类名未移除，hover 行为存在）
"""

import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
TEMPLATE = WORKSPACE / "app/templates/report_view.html"
APP_PY = WORKSPACE / "app/app.py"


def _template_text() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _app_text() -> str:
    return APP_PY.read_text(encoding="utf-8")


def test_t1_anchor_has_blank_and_noopener():
    """report-doc-link <a> 必须含 target=_blank 和 rel=noopener。"""
    src = _template_text()
    # 匹配包含 report-doc-link 类的 a 标签开始
    pat = re.compile(r'<a\s+class="report-doc-link"\s+([^>]*)>')
    matches = pat.findall(src)
    assert matches, "未找到 <a class=\"report-doc-link\"> 渲染点"
    for attrs in matches:
        assert 'target="_blank"' in attrs, (
            f"report-doc-link 缺少 target=\"_blank\"：{attrs}"
        )
        assert 'rel="noopener"' in attrs, (
            f"report-doc-link 缺少 rel=\"noopener\"：{attrs}"
        )


def test_t2_url_builder_returns_flask_routes():
    """_report_detail_url 必须使用 url_for 产出有效路由。"""
    src = _app_text()
    m = re.search(r"def\s+_report_detail_url\s*\([^)]*\)\s*:.*?(?=\ndef\s|\nclass\s|\Z)",
                   src, re.DOTALL)
    assert m, "_report_detail_url 未找到"
    body = m.group(0)
    assert "url_for(endpoint, id=doc_id)" in body, (
        f"_report_detail_url 必须走 url_for 生成链接，当前实现：\n{body[:300]}"
    )


def test_t3_reference_links_covers_main_order_types():
    """REPORT_REFERENCE_LINKS 必须覆盖主流单据类型，库存台账可点入 in_order/out_order。"""
    src = _app_text()
    m = re.search(r"REPORT_REFERENCE_LINKS\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
    assert m, "REPORT_REFERENCE_LINKS 配置未找到"
    body = m.group(1)
    for required in ("'in_order'", "'out_order'"):
        assert required in body, (
            f"REPORT_REFERENCE_LINKS 缺少 {required}：库存台账点击领料/入库单号无法跳转"
        )


def test_t4_all_link_anchors_in_template_have_blank():
    """模板中所有 report-doc-link 渲染点都已加 target=_blank（防止遗漏）。"""
    src = _template_text()
    pat = re.compile(r'<a\s+class="report-doc-link"[^>]*>')
    matches = pat.findall(src)
    assert matches, "未找到任何 report-doc-link 渲染"
    for full in matches:
        assert 'target="_blank"' in full, f"遗漏 target=_blank：{full}"


def test_t5_link_styling_preserved():
    """链接样式仍存在（保留 hover / cursor 视觉反馈）。"""
    src = _template_text()
    assert ".report-doc-link {" in src, "report-doc-link 基础样式被移除"
    assert ".report-doc-link:hover" in src, "report-doc-link hover 样式被移除"
    assert "cursor: pointer" in src, "建议增加 cursor: pointer 让单据链接更明显"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        sys.exit(1)
    print(f"\n所有 {len(tests)} 个报表链接新标签页打开回归验证通过")