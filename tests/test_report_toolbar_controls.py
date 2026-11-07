"""Exercise shared report toolbar controls without a production database/browser."""
from html.parser import HTMLParser
from pathlib import Path
import shutil
import subprocess

import pytest
from jinja2 import DictLoader, Environment, FileSystemLoader, ChoiceLoader

ROOT = Path(__file__).resolve().parents[1]


class ToolbarTree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.nodes = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        node = {"tag": tag, "attrs": attrs, "parents": tuple(self.stack), "text": ""}
        if attrs.get("id"):
            assert attrs["id"] not in self.nodes, f"duplicate control id: {attrs['id']}"
            self.nodes[attrs["id"]] = node
        if tag not in {"input", "meta", "link", "br", "hr", "img"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index]["tag"] == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        for node in self.stack:
            node["text"] += data


def toolbar_tree():
    env = Environment(loader=ChoiceLoader([
        DictLoader({"base.html": "<body class='{% block body_class %}{% endblock %}'>{% block content %}{% endblock %}{% block scripts %}{% endblock %}</body>"}),
        FileSystemLoader(ROOT / "app/templates"),
    ]))
    env.globals.update(url_for=lambda name, **kw: "/" + name, csrf_token=lambda: "fixture-csrf")
    html = env.get_template("report_view.html").render(
        report_type="inventory", title="库存报表", summary_labels={"count": "记录数", "quantity": "数量", "amount": "金额"},
        summary_types={}, filters_config={}, warehouses=[], suppliers=[], default_warehouse=None,
    )
    tree = ToolbarTree()
    tree.feed(html)
    return tree


def test_report_has_one_read_only_toolbar_with_explicit_print_choices():
    tree = toolbar_tree()
    toolbar = tree.nodes["reportToolbar"]
    assert toolbar["attrs"].get("role") == "toolbar"
    for control in ["refreshReportBtn", "exportBtn", "reportPrintMenu", "columnSettingsBtn"]:
        assert toolbar in tree.nodes[control]["parents"], control
    for control in ["templateSelect", "templatePreviewBtn", "templatePrintBtn", "retryPrintTemplatesBtn", "printBtn"]:
        assert tree.nodes["reportPrintMenu"] in tree.nodes[control]["parents"], control
    assert tree.nodes["reportPrintMenu"]["tag"] == "details"
    assert "下载打印文件" in tree.nodes["templatePrintBtn"]["text"]
    assert "标准清单打印" in tree.nodes["printBtn"]["text"]
    assert not any(label in toolbar["text"] for label in ["新增", "保存", "删除", "完成单据", "反提交"])
    assert tree.nodes["reportTableSection"] not in tree.nodes["columnSettingsBtn"]["parents"]
    assert "filterForm" in tree.nodes and "filterPanel" in tree.nodes and "reportTable" in tree.nodes


@pytest.mark.parametrize("scenario", ["defaults", "builtin", "all_missing", "error_retry", "failure_http",
                                    "failure_business", "failure_malformed", "missing_warehouse", "outputs",
                                    "invalid_choice", "loading", "late_catalog", "refresh_escape"])
def test_report_toolbar_runtime(scenario):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for report toolbar runtime checks")
    result = subprocess.run(
        [node, "--max-old-space-size=96", str(ROOT / "tests/frontend_report_toolbar_controls.cjs"), str(ROOT), scenario],
        capture_output=True, text=True, encoding="utf-8", timeout=25,
    )
    assert result.returncode == 0, result.stdout + result.stderr
