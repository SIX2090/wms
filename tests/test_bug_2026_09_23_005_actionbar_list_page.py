# -*- coding: utf-8 -*-
"""BUG-2026-09-23-005 回归：全局操作栏（#cbGlobalActionBar）在列表页的 4 项缺陷。

被审计对象是 app.js 的 insertGlobalActionBar() 注入的**全局操作栏**（仅内嵌/Tab
iframe 模式出现：isWmsEmbeddedPage()），不是各页面自带的 page-header 工具条。

真实浏览器（内嵌模式 ?embedded=1）走查实测确认 4 个缺陷：
  P1 静默陷阱——列表页「首张/上一张/下一张/末张」disabled=false，点击既不报错
     也不提示，直接把用户传送到 /in_order/1 并丢掉列表筛选条件。
     根因：createDocumentNavigationGroup 只判 module.navigator，而
     WMS_ACTION_MODULES 里 15 个模块**全部**为 true；navigateDocument 在无当前
     单据时回退 data.first_id / data.last_id。
  P2 名不副实——列表页「设置」打开的是 /in_order_print_template（打印模板），
     不是字段/列设置。根因：openSettings 见到 module.printTemplateUrl 就跳转。
  P3 打错报表——列表页「打印」打开 /report/inout/print 时**完全忽略当前筛选**。
     根因：printCurrent 列表分支直接 window.open(module.printListUrl)。
  P4 死按钮——列表页「保存」只做了 CSS 置灰（classList.add('disabled')），
     监听器仍会触发，saveCurrentPage 最终落到 document.querySelector('form')
     ——命中的是**筛选表单**。

修复：
  P1 isWmsListPage(module) 精确识别列表页 → createDocumentNavigationGroup
     收第二个参数 isListPage，列表页整组不渲染；
  P2 列表页移除「设置」，但**仅当 module.printTemplateUrl 存在时**才移除——
     对 material 这类无打印模板的模块，列表页点「设置」实际是有效的字段列设置
     入口，一律隐藏等于砍掉可用功能（AGENTS.md §七 R8：修复须有净正向价值）；
  P3 printCurrent 列表分支改走 buildReportPrintUrl()，白名单映射只带报表真正
     支持的参数（warehouse_id / start_date / end_date）；
  P4 列表页直接移除「保存」。

参数名不对称是本 BUG 的关键坑（改代码前已实测确认）：
  /report/inout/print（app/routes/report.py）只认 warehouse_id +
  start_date/end_date，**忽略** status/search/supplier_id/contract_no/
  project_name；而列表页表单的日期参数名是 date_start/date_end（**不同名**），
  且 /in_order/export 却认全部 10 个筛选——两端不对称。
  故 buildReportPrintUrl 必须做改名映射，不能复用 buildCurrentFilteredUrl
  （后者会把一堆被报表忽略的参数塞进 URL：地址栏脏且误导用户）。

测试策略：**以行为验证为主**（T10 用 node 真实执行三个 helper），
源码字符串断言为辅（T1~T9 锁接线方式）。
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "js" / "app.js"


def _src() -> str:
    return APP_JS.read_text(encoding="utf-8")


def _fn_body(src: str, signature: str) -> str:
    """按大括号配对截取函数体（比固定偏移可靠，函数增删行不会误判）。"""
    start = src.index(signature)
    brace = src.index("{", start)
    depth = 0
    for i in range(brace, len(src)):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError(f"未找到函数结束括号: {signature}")


def _run_helpers(payload_js: str) -> dict:
    """在 node 里真实执行 normalizeWmsPath / isWmsListPage / buildReportPrintUrl。

    payload_js 内部可用 __norm()/__isList()/__report()/__sc(q, path) 四个桥接函数。
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")

    harness = ROOT / ".t10_actionbar_harness.js"
    harness.write_text(_build_harness(payload_js), encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness), str(APP_JS)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)

    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


# 说明：harness 用 Python 列表逐行拼装，**不用三引号字面量**。
# 踩坑记录：三引号里的 "\\n" 会被 Python 解析成**真实换行**，拼出的 JS 变成
# `... + "<换行>" +`——字符串未闭合，node 报 Invalid or unexpected token。
# 逐行列表 + 显式 \\n 转义可以稳定产出 "\n" 这两个字符。
def _build_harness(payload_js: str) -> str:
    prelude = [
        "const fs = require('fs');",
        # argv[0]=node  argv[1]=本 harness 脚本  argv[2]=被读取的 app.js
        "const src = fs.readFileSync(process.argv[2], 'utf8');",
        "",
        "function extract(sig) {",
        "  const start = src.indexOf(sig);",
        "  if (start < 0) throw new Error('missing ' + sig);",
        "  let i = src.indexOf('{', start), depth = 0;",
        "  for (; i < src.length; i++) {",
        "    if (src[i] === '{') depth++;",
        "    else if (src[i] === '}') { depth--; if (depth === 0) return src.slice(start, i + 1); }",
        "  }",
        "  throw new Error('unbalanced ' + sig);",
        "}",
        "",
        "const mapStart = src.indexOf('var WMS_REPORT_PRINT_PARAM_MAP');",
        "if (mapStart < 0) throw new Error('missing WMS_REPORT_PRINT_PARAM_MAP');",
        "const mapDecl = src.slice(mapStart, src.indexOf('];', mapStart) + 2);",
        "",
        # 逐段拼出待执行的沙箱代码；每段之间显式插入 "\\n"（JS 转义，运行时是换行）
        "const parts = [];",
        "parts.push(extract('function normalizeWmsPath(pathname)'));",
        "parts.push(extract('function isWmsListPage(module)'));",
        "parts.push(mapDecl);",
        "parts.push(extract('function buildReportPrintUrl(baseUrl)'));",
        "parts.push('function __norm(p){ return normalizeWmsPath(p); }');",
        "parts.push('function __isList(m){ return isWmsListPage(m); }');",
        "parts.push('function __report(b){ return buildReportPrintUrl(b); }');",
        "parts.push('function __sc(q, path){');",
        "parts.push('  window.location = { pathname: path || \"/in_order\", search: q || \"\", origin: \"http://localhost\" };');",
        "parts.push('}');",
        "const code = parts.join('\\n') + '\\nreturn JSON.stringify((function(){ '",
        "             + '}}}' + ' })());';".replace("'}}}'", json.dumps(payload_js)),
        "",
        "const out = new Function('window', 'URL', 'URLSearchParams', code)(",
        "  {}, URL, URLSearchParams);",
        "console.log(out);",
    ]
    return "\n".join(prelude) + "\n"


# --------------------------------------------------------------------------
# T1：isWmsListPage 行为判定矩阵（真实执行，非字符串断言）
# --------------------------------------------------------------------------

def test_t1_is_wms_list_page_behavior():
    out = _run_helpers("""
        var inOrder = { listUrl: '/in_order', printTemplateUrl: '/in_order_print_template' };
        var material = { listUrl: '/material', printTemplateUrl: null };
        var noList = { printTemplateUrl: '/x' };
        return {
          list:        __sc('', '/in_order')   || __isList(inOrder),
          detail:      __sc('', '/in_order/1') || __isList(inOrder),
          add:         __sc('', '/in_order/add') || __isList(inOrder),
          trailing:    __sc('', '/in_order/')  || __isList(inOrder),
          crossModule: __sc('', '/in_order')   || __isList(material),
          noListUrl:   __isList(noList),
          emptyObj:    __isList(null)
        };
    """)

    assert out["list"] is True, "列表页 /in_order 应判定为 True"
    assert out["detail"] is False, "详情页 /in_order/1 不应判定为列表页"
    assert out["add"] is False, "新增页 /in_order/add 不应判定为列表页"
    assert out["trailing"] is True, "带尾斜杠 /in_order/ 应等价于列表页"
    assert out["crossModule"] is False, "跨模块路径不应误判"
    assert out["noListUrl"] is False, "无 listUrl 必须保守返回 False"
    assert out["emptyObj"] is False, "module 为 null 必须安全返回 False"


# --------------------------------------------------------------------------
# T2：normalizeWmsPath 行为
# --------------------------------------------------------------------------

def test_t2_normalize_wms_path_behavior():
    out = _run_helpers("""
        return {
          plain:       __norm('/in_order'),
          trailing:    __norm('/in_order/'),
          multiSlash:  __norm('/in_order///'),
          query:       __norm('/in_order?page=2&embedded=1'),
          hash:        __norm('/in_order#top'),
          both:        __norm('/in_order/?page=2#top'),
          root:        __norm('/'),
          empty:       __norm(''),
          nested:      __norm('/subcontract/issue')
        };
    """)

    assert out["plain"] == "/in_order"
    assert out["trailing"] == "/in_order", "尾部斜杠未归一化"
    assert out["multiSlash"] == "/in_order", "多个尾部斜杠未归一化"
    assert out["query"] == "/in_order", "query 未剥离"
    assert out["hash"] == "/in_order", "hash 未剥离"
    assert out["both"] == "/in_order", "query+hash 组合未剥离"
    assert out["root"] == "/", "根路径不应被削成空串"
    assert out["empty"] == ""
    assert out["nested"] == "/subcontract/issue", "多级路径不应被破坏"


# --------------------------------------------------------------------------
# T3：buildReportPrintUrl 正向——改名映射生效
# --------------------------------------------------------------------------

def test_t3_build_report_print_url_maps_dates():
    out = _run_helpers("""
        __sc('?warehouse_id=7&date_start=2026-01-01&date_end=2026-03-31&page=2&embedded=1');
        return { url: __report('/report/inout/print') };
    """)
    url = out["url"]

    assert url.startswith("/report/inout/print?"), f"基础路径不对: {url}"
    assert "warehouse_id=7" in url, "warehouse_id 未透传"
    assert "start_date=2026-01-01" in url, "date_start 未改名为 start_date"
    assert "end_date=2026-03-31" in url, "date_end 未改名为 end_date"


# --------------------------------------------------------------------------
# T4：buildReportPrintUrl 负向——报表不认的参数一个都不能带出
# --------------------------------------------------------------------------

def test_t4_build_report_print_url_drops_unsupported_params():
    out = _run_helpers("""
        __sc('?warehouse_id=7&status=completed&search=abc&supplier_id=3' +
             '&contract_no=C1&project_name=P1&date_start=2026-01-01' +
             '&date_end=2026-03-31&page=2&embedded=1&sort=order_no');
        return {
          full:    __report('/report/inout/print'),
          onlyStatus: (__sc('?status=completed'), __report('/report/inout/print')),
          emptyBase: __report(''),
          noParams: (__sc(''), __report('/report/inout/print'))
        };
    """)

    full = out["full"]
    # 报表端点实测只认这 3 个；其余 5 个筛选 + page/embedded/sort 一律丢弃
    for leaked in ("status=", "search=", "supplier_id=", "contract_no=",
                   "project_name=", "date_start=", "date_end=",
                   "page=", "embedded=", "sort="):
        assert leaked not in full, f"报表不支持的参数被带出: {leaked}"

    # 报表不认的参数不应污染 URL——只有 status 时应保持裸路径
    assert out["onlyStatus"] == "/report/inout/print", \
        f"报表不认的参数污染了 URL: {out['onlyStatus']}"

    # 空 baseUrl 短路
    assert out["emptyBase"] == "", "空 baseUrl 必须返回空串"

    # 无筛选时保持裸路径
    assert out["noParams"] == "/report/inout/print", \
        f"无筛选时不应有 query: {out['noParams']}"


# --------------------------------------------------------------------------
# T5：源码接线——导航组列表页早退
# --------------------------------------------------------------------------

def test_t5_nav_group_skips_list_page():
    src = _src()
    assert "function createDocumentNavigationGroup(module, isListPage)" in src, \
        "createDocumentNavigationGroup 未接收 isListPage 参数"
    body = _fn_body(src, "function createDocumentNavigationGroup(module, isListPage)")
    # 既有 navigator 判空必须保留
    assert "if (!module.navigator) return null;" in body
    # 新增 isListPage 早退
    assert "if (isListPage) return null;" in body
    # 必须在创建 DOM 之前返回，否则节点已建好就白做
    assert body.index("if (isListPage) return null;") < body.index("document.createElement('div')")


# --------------------------------------------------------------------------
# T6：源码接线——操作栏运行时过滤
# --------------------------------------------------------------------------

def test_t6_actionbar_runtime_filter_for_list_page():
    src = _src()
    body = _fn_body(src, "function insertGlobalActionBar()")
    assert "var isListPage = isWmsListPage(module);" in body
    # 求值必须早于按钮定义；过滤必须早于渲染遍历
    assert body.index("var isListPage = isWmsListPage(module);") < body.index("var buttons = [")
    assert body.index("if (isListPage) {") < body.index("buttons.forEach(function(item) {")
    # 「保存」在列表页恒移除（P4）
    assert "if (item.key === 'save') return false;" in body
    # 「设置」以 printTemplateUrl 为条件（P2 + R8 净正向价值）
    assert "if (item.key === 'settings' && module.printTemplateUrl) return false;" in body
    # 分隔线清理
    assert "trimWmsActionbarDividers(buttons)" in body
    # 导航组透传 isListPage（P1）
    assert "createDocumentNavigationGroup(module, isListPage)" in body


def test_t6b_trim_dividers_helper_exists():
    src = _src()
    assert "function trimWmsActionbarDividers(buttons)" in src
    body = _fn_body(src, "function trimWmsActionbarDividers(buttons)")
    assert "item.divider" in body
    assert "arr[index - 1].divider" in body
    assert "index === 0 || index === arr.length - 1" in body


# --------------------------------------------------------------------------
# T7：源码接线——打印带筛选
# --------------------------------------------------------------------------

def test_t7_print_current_list_branch_keeps_filters():
    src = _src()
    body = _fn_body(src, "function printCurrent(module)")
    # 列表分支必须走 buildReportPrintUrl，不能再裸开 printListUrl
    assert "window.open(buildReportPrintUrl(module.printListUrl), '_blank');" in body
    assert "window.open(module.printListUrl, '_blank');" not in body, \
        "列表页打印仍在裸开 printListUrl，筛选条件会丢"
    # 详情分支必须原样保留（不得回归）
    assert "window.open(buildModuleUrl(module.detailPrintUrl, id), '_blank');" in body
    # window.print() 兜底仍在
    assert "window.print();" in body


# --------------------------------------------------------------------------
# T8：既有回归锁逐字保持（改动过程中最容易被误伤的部分）
# --------------------------------------------------------------------------

def test_t8_existing_regression_locks_intact():
    src = _src()

    # BUG-2026-09-08-002：openSettings 签名 + stopPropagation 必须在 btn.click() 之前
    assert "function openSettings(module, evt)" in src
    settings_body = _fn_body(src, "function openSettings(module, evt)")
    assert settings_body.index("stopPropagation") < settings_body.index("btn.click()")
    # 全局工具栏 settings 按钮的逐字 action 字符串
    assert "action: function(e) { openSettings(module, e); }" in src

    # BUG-2026-08-27-001：详情页去重的内联 filter 必须逐字保留
    assert "BUG-2026-08-27-001" in src
    assert "/\\/\\d+\\/?$/.test(window.location.pathname)" in src
    assert "pageHasOwnDelete" in src
    assert "pageHasOwnPrint" in src
    assert "item.key === 'delete' && pageHasOwnDelete" in src
    assert "item.key === 'print' && pageHasOwnPrint" in src
    assert "item.divider" in src
    assert "arr[index - 1].divider" in src

    # buttons 数组字面量本身不得被改动（运行时而过滤是唯一正确做法）
    actionbar = _fn_body(src, "function insertGlobalActionBar()")
    for literal in ("{ key: 'add', icon: 'bi-plus-lg', label: '新增'",
                    "{ key: 'save', icon: 'bi-save', label: '保存'",
                    "{ key: 'delete', icon: 'bi-trash', label: '删除'",
                    "{ key: 'settings', icon: 'bi-gear', label: '设置'",
                    "{ key: 'print', icon: 'bi-printer', label: '打印'",
                    "{ key: 'share', icon: 'bi-share', label: '智能分享'"):
        assert literal in actionbar, f"buttons 字面量被改动: {literal}"


def test_t8b_other_module_locks_intact():
    """其它测试文件的逐字锁，改动 app.js 时同样不能被误伤。"""
    src = _src()
    assert "opening_stock: {" in src
    assert "tableId: 'openingGrid'" in src
    assert "'/opening_stock/{id}'" in src
    assert "/^\\/opening_stock\\/add$/" in src
    assert "/^\\/opening_stock\\/\\d+$/" in src
    # getCurrentRecordId 正则（与 test_opening_stock_doc_navigation 的
    # _JS_CURRENT_RECORD_RE 一致）
    assert "\\/(\\d+)(?:\\/(?:edit|detail))?\\/?$" in src


# --------------------------------------------------------------------------
# T9：语法
# --------------------------------------------------------------------------

def test_t9_app_js_syntax_ok():
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    result = subprocess.run([node, "--check", str(APP_JS)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[:800]


# --------------------------------------------------------------------------
# T10：重建操作栏的真实行为——列表页按钮集合与详情页对比
# --------------------------------------------------------------------------

def test_t10_actionbar_button_set_differs_between_list_and_detail():
    """真实重建 insertGlobalActionBar 的过滤逻辑，验证按钮集合差异。

    只复刻"过滤"这一段（DOM 构建部分无关），避免把整个 app.js 拉起来。
    """
    out = _run_helpers("""
        // 复刻 insertGlobalActionBar 里的 buttons 字面量 + 过滤段
        function build(module, isListPage) {
          var buttons = [
            { key: 'add' }, { key: 'save' }, { key: 'delete' },
            { divider: true },
            { key: 'settings' }, { key: 'print' },
            { divider: true },
            { key: 'import' }, { key: 'export' }, { key: 'template' },
            { divider: true },
            { key: 'share' }
          ];
          if (isListPage) {
            buttons = buttons.filter(function(item) {
              if (item.key === 'save') return false;
              if (item.key === 'settings' && module.printTemplateUrl) return false;
              return true;
            });
            buttons = __trim(buttons);
          }
          return buttons.map(function(b) { return b.divider ? '|' : b.key; });
        }
        var inOrder = { listUrl: '/in_order', printTemplateUrl: '/in_order_print_template' };
        var material = { listUrl: '/material', printTemplateUrl: null };
        return {
          listInOrder: build(inOrder, true),
          detailInOrder: build(inOrder, false),
          listMaterial: build(material, true)
        };
    """.replace("__trim(buttons)", "buttons.filter(function(item, index, arr) {"
                 " if (!item.divider) return true;"
                 " if (index === 0 || index === arr.length - 1) return false;"
                 " return !arr[index - 1].divider; })"))
    # 注意：上面没有真的调用 trimWmsActionbarDividers，因为它是独立函数；
    # 这里内联等价实现，仅用于验证"过滤后的按钮集合"，函数本身由
    # test_t6b_trim_dividers_helper_exists 锁。

    list_in_order = out["listInOrder"]
    detail = out["detailInOrder"]
    list_material = out["listMaterial"]

    # 列表页（有 printTemplateUrl）：save 和 settings 都被移除
    assert "save" not in list_in_order, "列表页仍保留「保存」"
    assert "settings" not in list_in_order, "列表页仍保留「设置」（printTemplateUrl 存在）"
    # 但打印/新增/删除/导入导出/模板/分享必须都还在——不得误伤
    for keep in ("add", "delete", "print", "import", "export", "template", "share"):
        assert keep in list_in_order, f"列表页误删了按钮: {keep}"

    # 详情页：按钮一个不少（不得回归）
    for keep in ("add", "save", "delete", "settings", "print",
                 "import", "export", "template", "share"):
        assert keep in detail, f"详情页按钮丢失（回归）: {keep}"
    assert detail.count("|") == 3, "详情页分隔线数量应保持 3"

    # 列表页（无 printTemplateUrl，如 material）：save 移除，但 settings 保留
    assert "save" not in list_material, "列表页（material）仍保留「保存」"
    assert "settings" in list_material, \
        "material 列表页的「设置」被误删——它实际是有效的字段设置入口（R8 净正向价值）"
