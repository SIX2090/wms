# -*- coding: utf-8 -*-
"""LABEL-FIX-2026-09-29-002：print_label.html 行高按 layout.rowHeights 占比分配，
且能渲染设计器保存的 cells 列表格式模板。

生效确认：
① 模板行高读取 rowHeights 而非均分（与 print_batch_labels.html rowHeightMm 同口径）；
② rowHeights 缺失/全 0 时回退均分，不除零、不 500；
③ 渲染级验证：rowHeights=[60,30] 时首行高度为次行 2 倍；
④ 后端 print_labels 把 cells 列表归一并转为 "行-列" 键控后传入 layout_json
   （此前设计器模板在本页全部渲染成占位灰格）。
"""
from pathlib import Path
import json
import re
from datetime import datetime

from jinja2 import BaseLoader, Environment

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "app" / "templates" / "print_label.html"
ROUTE = ROOT / "app" / "routes" / "label_barcode.py"


# ---------- 静态契约 ----------

def test_row_height_uses_row_heights_ratio():
    text = PAGE.read_text(encoding="utf-8")
    assert "rowHeights" in text, "行高未读取 layout.rowHeights（仍在均分）"
    assert "template.height * 3.78 / template.rows" not in text, "旧的均分公式必须移除"


def test_row_height_has_fallback_30():
    text = PAGE.read_text(encoding="utf-8")
    assert "else 30" in text, "缺少默认行高 30 的保底（rowHeights 缺失时除零风险）"


def test_route_converts_cells_to_keyed():
    text = ROUTE.read_text(encoding="utf-8")
    i = text.find("'/label_template/<int:id>/print'")
    assert i > 0
    j = text.find("@app.route(", i + 10)
    seg = text[i:j if j > 0 else len(text)]
    assert "_normalize_label_template_layout" in seg, "print_labels 未归一化 layout"
    assert "layout_json" in seg, "print_labels 未向模板传 layout_json（cells→键控转换）"


def test_template_prefers_layout_json():
    text = PAGE.read_text(encoding="utf-8")
    assert "layout_json" in text, "模板未优先使用 layout_json"


def test_full_template_compiles_with_production_jinja_config():
    """LABEL-FIX-2026-09-29-005 回归锁：整页模板必须在「生产实际 jinja 配置」下可编译。

    背景：本应用未启用 jinja2.ext.loopcontrols，而 print_label.html 历史上使用
    {% continue %}，导致 /label_template/<id>/print 长期 500（修复前实证）。
    测试桩若私自启用扩展会掩盖生产现实（假绿），故本锁用裸 Environment
    （仅注册 app.py 里 app.jinja_env.filters 登记过的过滤器名）编译整页模板。
    """
    import jinja2
    app_src = (ROOT / "app" / "app.py").read_text(encoding="utf-8")
    filter_names = re.findall(r"app\.jinja_env\.filters\['(\w+)'\]", app_src)
    env = jinja2.Environment()  # 裸环境：无扩展，与 app 一致
    for name in set(filter_names):
        env.filters[name] = lambda v, *a, **k: v  # 编译期只需名字存在
    src = PAGE.read_text(encoding="utf-8")
    env.from_string(src)  # 失败即 TemplateSyntaxError，测试变红（A12）


def test_no_loopcontrol_tags_anywhere():
    """模板不得使用 {% continue %}/{% break %}（app 未启用 loopcontrols）。"""
    text = PAGE.read_text(encoding="utf-8")
    # 先剥掉 Jinja 注释（注释里允许出现字面文字说明，解析器也忽略）
    stripped = re.sub(r"\{#.*?#\}", "", text, flags=re.DOTALL)
    assert "{% continue %}" not in stripped and "{% break %}" not in stripped


# ---------- 渲染级验证（防假绿：用真实模板文件片段渲染） ----------

class _Obj:
    pass


def _mk(**kw):
    o = _Obj()
    o.__dict__.update(kw)
    return o


def _render_table(layout_json_str, rows, cols, height=40):
    """从 print_label.html 抽 <table> 段，用 Jinja 真实渲染。"""
    src = PAGE.read_text(encoding="utf-8")
    start = src.find('<table class="label-table">')
    assert start > 0
    end = src.find('</table>', start) + len('</table>')
    frag = src[start:end]
    # 测试桩必须与生产 jinja 配置一致：本应用未启用 loopcontrols 等扩展
    # （LABEL-FIX-2026-09-29-005 实证：生产上 {% continue %} 直接 500），
    # 仅注册 app.py 中 app.jinja_env.filters 登记过的自定义过滤器。
    env = Environment(loader=BaseLoader())
    env.filters['from_json'] = lambda v: json.loads(v) if v else {}
    tpl = env.from_string("{% for material in materials %}" + frag + "{% endfor %}")
    template = _mk(width=60, height=height, rows=rows, cols=cols, layout='{}')
    material = _mk(id=1, code='MAT-1', name='轴承6204', spec='s', stock=5, price=1,
                   unit=_mk(name='套'), category=_mk(name='五金'), supplier=_mk(name='鑫达'))
    return tpl.render(template=template, materials=[material],
                      now=datetime(2026, 9, 29), layout_json=layout_json_str)


def _tr_heights(html):
    # Jinja round(0) 返回 float（如 101.0px），正则必须兼容小数
    return [float(m) for m in re.findall(r'<tr style="height: ([\d.]+)px;">', html)]


def test_render_row_height_ratio_2_to_1():
    # rowHeights=[60,30] → 首行高度应为次行 2 倍（容差：四舍五入 1px）
    layout = {
        'rowHeights': [60, 30],
        'cells': [],
        '0-0': {'field': 'name', 'style': {}},
        '1-0': {'field': 'code', 'style': {}},
    }
    html = _render_table(json.dumps(layout, ensure_ascii=False), rows=2, cols=1, height=40)
    heights = _tr_heights(html)
    assert len(heights) == 2, f"应渲染 2 行，实际 {heights}"
    ratio = heights[0] / heights[1]
    assert 1.8 <= ratio <= 2.2, f"行高比 {ratio} 不在 2:1 容差内（{heights}）"


def test_render_fallback_equal_heights_without_row_heights():
    layout = {'cells': [], '0-0': {'field': 'name', 'style': {}}}
    html = _render_table(json.dumps(layout, ensure_ascii=False), rows=2, cols=1, height=40)
    heights = _tr_heights(html)
    assert len(heights) == 2
    assert abs(heights[0] - heights[1]) <= 1, f"无 rowHeights 时应均分: {heights}"


def test_render_no_crash_on_zero_row_heights():
    layout = {'rowHeights': [0, 0], 'cells': [], '0-0': {'field': 'name', 'style': {}}}
    html = _render_table(json.dumps(layout, ensure_ascii=False), rows=2, cols=1, height=40)
    heights = _tr_heights(html)
    assert len(heights) == 2, "rowHeights 全 0 时不应崩溃且仍渲染 2 行"


def test_render_keyed_cell_outputs_value_and_text_fallback():
    layout = {
        'rowHeights': [30, 30],
        'cells': [],
        '0-0': {'field': 'name', 'style': {}},
        '1-0': {'field': '', 'text': '静态备注', 'style': {}},
    }
    html = _render_table(json.dumps(layout, ensure_ascii=False), rows=2, cols=1, height=40)
    assert '轴承6204' in html, "键控条目 field=name 未渲染物料名称"
    assert '静态备注' in html, "纯文本单元格（field 为空）未渲染 text 兜底"
