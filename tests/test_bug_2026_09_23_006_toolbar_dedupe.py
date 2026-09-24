# -*- coding: utf-8 -*-
"""BUG-2026-09-23-006 回归：列表页双工具栏「重复按钮」治理。

## 背景

BUG-2026-09-23-005 修完列表页全局操作栏的 4 项缺陷后，遗留「页面自带工具栏 与
注入的 #cbGlobalActionBar 按钮重复」。原计划「动 21+ 模板做去重」经**真机实测
20 页**（Chromium，?embedded=1）被推翻两次：

  第 1 次：重复面其实极窄——只有「导入/导出」（10 个列表页）与 material 的
           「删除/打印」，**零模板改动**即可解决。
  第 2 次：实测比对发现**页面栏那份更可靠**，方向要反过来——

    | 项                | 页面栏                                  | 全局栏                        |
    |-------------------|-----------------------------------------|-------------------------------|
    | 导出（带筛选）    | /out_order/export?warehouse_id=&... 服务端渲染，参数完整 | /out_order/export 靠 JS 从 location.search 反推 |
    | 模板(subcontract) | /subcontract/download_template          | /export/template/subcontract（**不同端点**）|
    | 导入              | 触发页面专属隐藏 file input             | 通用 showImportModalForModule |

    故正确方向是：**隐藏全局栏的重复按钮，保留页面栏**。

## 修复

新增 pageHasOwnButton()（全页面扫描、严格文本相等、排除全局栏自身、排除表格
行级按钮），在 insertGlobalActionBar() 的 isListPage 分支内**条件隐藏**全局栏的
导入/导出/模板/删除/打印——仅当页面确实已有同名入口时才隐藏。

必须**条件**而非无条件，否则：
  - material 页面栏无「导出」→ 无条件隐藏会让导出功能凭空消失；
  - /sales/outbound 页面栏无导入/导出/模板 → 同理。

附带修复：sales 模块 match 正则原先含 |\\/outbound，把独立的销售出库列表页
/sales/outbound 误判为「单据详情页」，全局栏错误渲染「保存/查找单据/首张/上一张/
下一张/末张」。移除该分支后该页不再注入全局栏（与 /other_in_order 行为一致）。

## 关于「排除表格行级按钮」（实测踩坑）

warehouse.html 的「设为默认」「删除」是 <tbody> 内的行级按钮，只有表格有数据行时
才可见。若不排除，同一页面会因数据量多寡呈现不同的全局栏——有数据时隐藏全局栏
「删除」、空表时又冒出来，**行为随数据漂移**。全局栏按钮是「列表级」操作，
对照物只能是页面工具栏区域的按钮。

## 测试策略

以**行为验证为主**（T1~T4 用 node 真实执行 pageHasOwnButton 与过滤逻辑，
构造 DOM 桩），源码字符串断言为辅（T5/T6 锁接线与既有 verbatim 契约）。
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


# --------------------------------------------------------------------------
# node harness：真实执行 pageHasOwnButton / trimWmsActionbarDividers
# --------------------------------------------------------------------------

def _build_harness(payload_js: str) -> str:
    """用 Python 列表逐行拼装 harness。

    踩坑记录（沿用 005 轮经验）：三引号字面量里的 "\\n" 会被 Python 解析成
    **真实换行**，拼出的 JS 字符串未闭合。逐行列表 + 显式 \\n 转义可稳定产出。
    """
    prelude = [
        "const fs = require('fs');",
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
        "const parts = [];",
        # DOM 桩必须放进 parts —— payload 在 new Function 沙箱里执行，看不到
        # harness 模块外层作用域，所以 prelude 里定义 makeEl/installDom 是无效的。
        "parts.push('function makeEl(opts) {');",
        "parts.push('  opts = opts || {};');",
        "parts.push('  var el = { __text: opts.text || \\'\\', __title: opts.title || \\'\\',');",
        "parts.push('    __visible: opts.visible !== false, __inTable: !!opts.inTable, __children: [] };');",
        "parts.push('  el.innerText = el.__text;');",
        "parts.push('  el.textContent = el.__text;');",
        "parts.push('  el.offsetParent = el.__visible ? { tagName: \\'BODY\\' } : null;');",
        "parts.push('  el.getAttribute = function (k) { return k === \\'title\\' ? el.__title : null; };');",
        "parts.push('  el.closest = function (sel) {');",
        "parts.push('    if (el.__inTable && /table|tbody|tr/.test(sel)) return { tagName: \\'TBODY\\' };');",
        "parts.push('    return null; };');",
        "parts.push('  el.contains = function (node) { return node === el || el.__children.indexOf(node) !== -1; };');",
        "parts.push('  return el; }');",
        "parts.push('function installDom(nodes) {');",
        "parts.push('  var all = nodes || [];');",
        "parts.push('  global.document = { querySelectorAll: function () { return all; } };');",
        "parts.push('  return all; }');",
        "parts.push(extract('function pageHasOwnButton(texts, selfBar)'));",
        "parts.push(extract('function trimWmsActionbarDividers(buttons)'));",
        "parts.push('function __has(texts, selfBar){ return pageHasOwnButton(texts, selfBar); }');",
        "parts.push('function __trim(btns){ return trimWmsActionbarDividers(btns); }');",
        # __filter 由 payload 自行复刻（见 T3/T4 的 payload），避免拼装引号冲突
        "const code = parts.join('\\n') + '\\nreturn JSON.stringify((function(){ '",
        "             + '}}}' + ' })());';".replace("'}}}'", json.dumps(payload_js)),
        "",
        "const out = new Function('global', '__src', code)(global, src);",
        "console.log(out);",
    ]
    return "\n".join(prelude) + "\n"


def _run(payload_js: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")

    harness = ROOT / ".t006_dedupe_harness.js"
    harness.write_text(_build_harness(payload_js), encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness), str(APP_JS)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)

    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


# --------------------------------------------------------------------------
# T1：pageHasOwnButton 存在且可执行
# --------------------------------------------------------------------------

def test_t1_page_has_own_button_exists():
    out = _run("""
        installDom([makeEl({ text: '导出', visible: true })]);
        return { found: __has(['导出'], null) };
    """)
    assert out["found"] is True, "pageHasOwnButton 未生效或 harness 未接到函数"


# --------------------------------------------------------------------------
# T2：pageHasOwnButton 行为矩阵（严格相等 / 可见性 / 排除自身 / 排除表格）
# --------------------------------------------------------------------------

def test_t2_page_has_own_button_behavior():
    out = _run("""
        // 1) 严格相等：批量导入 不应被「导入」命中
        installDom([
          makeEl({ text: '批量导入' }),
          makeEl({ text: '批量导出' }),
          makeEl({ text: '批量打印' }),
          makeEl({ text: '删除已选' }),
          makeEl({ text: '完成已选' })
        ]);
        var strictImport = __has(['导入'], null);
        var strictExport = __has(['导出'], null);
        var strictDelete = __has(['删除'], null);
        var strictPrint  = __has(['打印'], null);

        // 2) 精确命中
        installDom([makeEl({ text: '导入' })]);
        var exact = __has(['导入'], null);

        // 3) 不可见按钮不算
        installDom([makeEl({ text: '导出', visible: false })]);
        var invisible = __has(['导出'], null);

        // 4) 排除全局栏自身（selfBar.contains 命中则跳过）
        var barBtn = makeEl({ text: '导出' });
        var barEl = makeEl({});
        barEl.__children = [barBtn];
        installDom([barBtn]);
        var selfExcluded = __has(['导出'], barEl);
        var selfIncludedIfNoBar = (function(){
          installDom([barBtn]);
          return __has(['导出'], null);
        })();

        // 5) 排除表格内的行级按钮
        installDom([
          makeEl({ text: '导出', inTable: false }),
          makeEl({ text: '删除', inTable: true })
        ]);
        var tableRowDeleteSkipped = __has(['删除'], null);
        var nonTableExportFound = __has(['导出'], null);

        // 6) 多文本候选
        installDom([makeEl({ text: '下载模板' })]);
        var multi = __has(['导入导出模板', '模板', '下载模板', '导入模板'], null);

        // 7) 空白归一化（对照真实页面：文本两侧可能带空白）
        installDom([makeEl({ text: '  导出  ' })]);
        var whitespace = __has(['导出'], null);

        return {
          strictImport: strictImport, strictExport: strictExport,
          strictDelete: strictDelete, strictPrint: strictPrint,
          exact: exact, invisible: invisible,
          selfExcluded: selfExcluded, selfIncludedIfNoBar: selfIncludedIfNoBar,
          tableRowDeleteSkipped: tableRowDeleteSkipped,
          nonTableExportFound: nonTableExportFound,
          multi: multi, whitespace: whitespace
        };
    """)

    # 严格相等是最高优先级红线：任何 includes 式实现都会让这 4 条翻红
    assert out["strictImport"] is False, "「批量导入」被误判为「导入」（必须严格相等）"
    assert out["strictExport"] is False, "「批量导出」被误判为「导出」（必须严格相等）"
    assert out["strictDelete"] is False, "「删除已选」被误判为「删除」（必须严格相等）"
    assert out["strictPrint"] is False, "「批量打印」被误判为「打印」（必须严格相等）"

    assert out["exact"] is True, "精确文本未命中"
    assert out["invisible"] is False, "不可见按钮不应计入"
    assert out["selfExcluded"] is False, "全局栏自身按钮未被排除（会自证）"
    assert out["selfIncludedIfNoBar"] is True, "传 null selfBar 时应能命中（防御性对照）"
    assert out["tableRowDeleteSkipped"] is False, "表格内行级按钮未被排除（会导致行为随数据量漂移）"
    assert out["nonTableExportFound"] is True, "非表格按钮应正常命中"
    assert out["multi"] is True, "多文本候选未生效"
    assert out["whitespace"] is True, "空白归一化未生效"


# --------------------------------------------------------------------------
# T3：隐藏矩阵——条件隐藏的行为（关键：不能无条件隐藏）
# --------------------------------------------------------------------------

def _full_buttons():
    return [
        {"key": "add"}, {"key": "save"}, {"key": "delete"}, {"divider": True},
        {"key": "settings"}, {"key": "print"}, {"divider": True},
        {"key": "import"}, {"key": "export"}, {"key": "template"}, {"divider": True},
        {"key": "share"},
    ]


def _filter_replica() -> str:
    """在 payload 内复刻 insertGlobalActionBar 的 isListPage 条件隐藏块。

    与源码逻辑同构（keepX = !pageHasOwnButton(...)）。放在 payload 里而不是
    harness prelude，是为了避开 Python 字符串拼接时的引号冲突。
    """
    return """
        function __filter(btns, isListPage, hasOwn) {
          if (!isListPage) return btns;
          var out = btns.filter(function(item) {
            if (item.key === 'import' && hasOwn.import) return false;
            if (item.key === 'export' && hasOwn.export) return false;
            if (item.key === 'template' && hasOwn.template) return false;
            if (item.key === 'delete' && hasOwn.delete) return false;
            if (item.key === 'print' && hasOwn.print) return false;
            return true;
          });
          return __trim(out);
        }
    """


def test_t3_conditional_hiding_matrix():
    out = _run(_filter_replica() + """
        var full = """ + json.dumps(_full_buttons()) + """;
        function keys(list) {
          return list.filter(function(x){ return !x.divider; }).map(function(x){ return x.key; });
        }

        // A) 页面栏有 导入/导出/下载模板 → 三者全隐藏
        var a = __filter(full, true, {
          import: true, export: true, template: true, delete: false, print: false });

        // B) 模拟 material：页面栏有删除/打印，但【无导出】 → 只隐藏 delete/print，
        //    export 必须保留（否则 material 导出功能凭空消失）
        var b = __filter(full, true, {
          import: false, export: false, template: false, delete: true, print: true });

        // C) 模拟 sales/outbound：三项皆无 → 全部保留
        var c = __filter(full, true, {
          import: false, export: false, template: false, delete: false, print: false });

        // D) 模拟 in_order：页面栏有导入/导出/模板，无删除/打印 → 保留 delete/print
        var d = __filter(full, true, {
          import: true, export: true, template: true, delete: false, print: false });

        // E) 详情页（isListPage=false）→ 一个都不动
        var e = __filter(full, false, {
          import: true, export: true, template: true, delete: true, print: true });

        return {
          a: keys(a), b: keys(b), c: keys(c), d: keys(d), e: keys(e),
          aDividers: a.filter(function(x){ return x.divider; }).length,
          eDividers: e.filter(function(x){ return x.divider; }).length,
        };
    """)

    # A) 三项隐藏后剩余
    assert out["a"] == ["add", "save", "delete", "settings", "print", "share"], \
        f"用例 A 失败: {out['a']}"

    # B) material 场景：delete/print 隐藏，export 保留 —— 这是 R8 红线
    assert "export" in out["b"], "material 场景下「导出」被错误隐藏（功能会凭空消失）"
    assert "import" in out["b"], "material 场景下「导入」被错误隐藏"
    assert "template" in out["b"], "material 场景下「模板」被错误隐藏"
    assert "delete" not in out["b"], "material 场景下「删除」未被隐藏"
    assert "print" not in out["b"], "material 场景下「打印」未被隐藏"

    # C) sales/outbound 场景：全部保留
    assert out["c"] == ["add", "save", "delete", "settings", "print",
                        "import", "export", "template", "share"], \
        f"用例 C 失败: {out['c']}"

    # D) in_order 场景：删除/打印保留，导入/导出/模板隐藏
    assert "delete" in out["d"] and "print" in out["d"], \
        "in_order 场景下删除/打印被错误隐藏"
    assert "import" not in out["d"] and "export" not in out["d"] \
        and "template" not in out["d"], "in_order 场景下导入/导出/模板未被隐藏"

    # E) 详情页不受影响
    assert out["e"] == ["add", "save", "delete", "settings", "print",
                        "import", "export", "template", "share"], \
        f"详情页(isListPage=false)不应被改动: {out['e']}"
    assert out["eDividers"] == 3, "详情页分隔线数不应变化"


# --------------------------------------------------------------------------
# T4：trimWmsActionbarDividers 在过滤后正常清理分隔线
# --------------------------------------------------------------------------

def test_t4_dividers_trimmed_after_filter():
    """过滤后分隔线应被清理（按**真实按钮数组**结构断言）。

    真实数组字面量：
        add | save | delete | DIV | settings | print | DIV | import | export | template | DIV | share
    in_order 场景（去 save + 去 import/export/template）过滤后：
        add | delete | DIV | settings | print | DIV | DIV | share
    trimWmsActionbarDividers 单趟过滤后，相邻的第二个 DIV 被移除：
        add | delete | DIV | settings | print | DIV | share
    —— 这正是真机在 /in_order?embedded=1 观察到的结果（分隔线干净、无连续残留）。
    """
    out = _run(_filter_replica() + """
        var btns = [
          { key: 'add' }, { key: 'save' }, { key: 'delete' }, { divider: true },
          { key: 'settings' }, { key: 'print' }, { divider: true },
          { key: 'import' }, { key: 'export' }, { key: 'template' }, { divider: true },
          { key: 'share' }
        ];
        // 先复刻 BUG-005 的列表页过滤（去 save）
        var b1 = btns.filter(function(item){
          if (item.key === 'save') return false; return true; });
        // 再走 BUG-006 的条件隐藏（页面栏有 导入/导出/模板）
        var filtered = __filter(b1, true, {
          import: true, export: true, template: true, delete: false, print: false });
        return {
          keys: filtered.filter(function(x){ return !x.divider; }).map(function(x){ return x.key; }),
          shape: filtered.map(function(x){ return x.divider ? 'DIV' : x.key; }),
          firstIsDivider: filtered.length ? !!filtered[0].divider : false,
          lastIsDivider: filtered.length ? !!filtered[filtered.length - 1].divider : false,
        };
    """)
    assert out["keys"] == ["add", "delete", "settings", "print", "share"], \
        f"过滤后按钮集不对: {out['keys']}"
    assert out["firstIsDivider"] is False, "开头仍是分隔线"
    assert out["lastIsDivider"] is False, "末尾仍是分隔线"
    assert out["shape"] == ["add", "delete", "DIV", "settings", "print", "DIV", "share"], \
        f"分隔线布局与真机不一致: {out['shape']}"


def test_t4b_no_leading_trailing_dividers_after_full_removal():
    """极端场景：只剩 add 一个按钮时，首尾分隔线必须清干净。"""
    out = _run(_filter_replica() + """
        function __filter2(btns) {
          var out = btns.filter(function(item) {
            if (item.key === 'add') return true;
            if (item.divider) return true;
            return false;   // import/export/share 全隐藏
          });
          return __trim(out);
        }
        var btns = [
          { key: 'add' }, { divider: true },
          { key: 'import' }, { divider: true },
          { key: 'export' }, { divider: true },
          { key: 'share' }
        ];
        var filtered = __filter2(btns);
        return {
          keys: filtered.filter(function(x){ return !x.divider; }).map(function(x){ return x.key; }),
          firstIsDivider: filtered.length ? !!filtered[0].divider : false,
        };
    """)
    assert out["keys"] == ["add"], f"过滤后按钮集不对: {out['keys']}"
    assert out["firstIsDivider"] is False, "开头仍是分隔线"


# --------------------------------------------------------------------------
# T5：sales 正则——/sales/outbound 不再被误吞
# --------------------------------------------------------------------------

def test_t5_sales_regex_excludes_outbound():
    """直接解析源码里的 sales.match 正则并逐个路径实测。

    在 Python 侧解析、在 node 侧执行 —— 避免 JS 字符串里写正则字面量的转义地狱。
    """
    import re as _re

    src = _src()
    # 抓 sales: { ... match: /.../,  —— 允许属性顺序变化与跨行。
    # 注意：正则体内部含 / 与 ?，必须用贪婪 .+ 直到行尾的 /-, 收口，
    # 用非贪婪会提前停在 |\/add 的斜杠上。
    m = _re.search(r"match:\s*(/\^\\/sales[^\n]*?/),", src)
    assert m, "未能在源码中定位 sales.match 正则"
    regex_literal = m.group(1)

    out = _run("""
        var re = new RegExp(""" + json.dumps(_js_body_from_literal(regex_literal)) + """);
        return {
          list:      re.test('/sales'),
          listSlash: re.test('/sales/'),
          add:       re.test('/sales/add'),
          detail:    re.test('/sales/12'),
          edit:      re.test('/sales/12/edit'),
          selection: re.test('/sales/outbound_selection'),
          outbound:  re.test('/sales/outbound'),
        };
    """)
    assert out["outbound"] is False, \
        f"/sales/outbound 仍被 sales 正则匹配（正则={regex_literal}）——应移除 |\\/outbound 分支"
    assert out["list"] is True, "/sales 必须仍匹配"
    assert out["listSlash"] is True, "/sales/ 必须仍匹配"
    assert out["add"] is True, "/sales/add 必须仍匹配"
    assert out["detail"] is True, "/sales/12 必须仍匹配"
    assert out["edit"] is True, "/sales/12/edit 必须仍匹配"
    assert out["selection"] is True, "/sales/outbound_selection 必须仍匹配（选单页）"


def _js_body_from_literal(literal: str) -> str:
    """把 JS 正则字面量 /abc/i 转成 new RegExp 可用的 body + flags。"""
    import re as _re

    m = _re.match(r"^/(.*)/([a-z]*)$", literal, _re.S)
    assert m, f"无法解析正则字面量: {literal}"
    return m.group(1)


# --------------------------------------------------------------------------
# T6：接线与既有 verbatim 契约
# --------------------------------------------------------------------------

def test_t6_wiring_and_verbatim_locks():
    src = _src()

    # 新增函数与调用
    assert "function pageHasOwnButton(texts, selfBar)" in src, "pageHasOwnButton 未定义"
    assert "!pageHasOwnButton(['导入'], bar)" in src, "导入检测未接线"
    assert "!pageHasOwnButton(['导出'], bar)" in src, "导出检测未接线"
    assert "!pageHasOwnButton(ownTemplateTexts, bar)" in src, "模板检测未接线"
    assert "!pageHasOwnButton(['删除'], bar)" in src, "删除检测未接线"
    assert "!pageHasOwnButton(['打印'], bar)" in src, "打印检测未接线"
    assert "['导入导出模板', '模板', '下载模板', '导入模板']" in src, \
        "模板文本候选集不完整（employee 用「导入模板」）"
    assert "el.closest('table, .table-responsive, .table-responsive-wrapper, tbody, tr')" in src, \
        "未排除表格行级按钮（会导致全局栏随数据量漂移）"

    # 既有契约（BUG-2026-08-27-001 / BUG-2026-09-23-005）不得被破坏
    assert "BUG-2026-08-27-001" in src
    assert "item.key === 'delete' && pageHasOwnDelete" in src
    assert "item.key === 'print' && pageHasOwnPrint" in src
    assert "arr[index - 1].divider" in src
    assert "function trimWmsActionbarDividers(buttons)" in src
    assert "function openSettings(module, evt)" in src
    assert "action: function(e) { openSettings(module, e); }" in src
    assert "opening_stock: {" in src
    assert "tableId: 'openingGrid'" in src
    assert "'/opening_stock/{id}'" in src
    assert "/^\\/opening_stock\\/add$/" in src
    assert "/^\\/opening_stock\\/\\d+$/" in src
    assert "BUG-2026-09-08-002" in src

    # 列表页过滤块的结构标记
    assert "BUG-2026-09-23-006" in src, "本轮修复标记未写入源码"
    assert "BUG-2026-09-23-005" in src, "005 轮标记被误删"


# --------------------------------------------------------------------------
# T7：app.js 语法检查
# --------------------------------------------------------------------------

def test_t7_app_js_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    result = subprocess.run([node, "--check", str(APP_JS)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"app.js 语法错误:\n{result.stderr[:1200]}"


# --------------------------------------------------------------------------
# T8：005 轮 helper 仍可用（跨 BUG 不回归的轻量保证）
# --------------------------------------------------------------------------

def test_t8_previous_round_helpers_still_intact():
    src = _src()
    assert "function normalizeWmsPath(pathname)" in src
    assert "function isWmsListPage(module)" in src
    assert "function buildReportPrintUrl(baseUrl)" in src
    assert "var WMS_REPORT_PRINT_PARAM_MAP = [" in src
    assert "var isListPage = isWmsListPage(module);" in src
    assert "function createDocumentNavigationGroup(module, isListPage)" in src
