# -*- coding: utf-8 -*-
"""BUG-2026-09-23-008 回归：别名列表页绕过 005/006 两轮修复。

## 缺陷

委外发料 / 委外入库存在**同一路由的别名 URL**：后端用「一个函数 + 两个
装饰器」同时注册两个路径，渲染同一个模板，因此它们是**同一个列表页**：

    app/routes/subcontract.py:969-970
        @app.route('/subcontract_issue')
        @app.route('/subcontract/issue')
        def subcontract_issue_list(): ...

    app/routes/subcontract.py:1630-1631
        @app.route('/subcontract_receive')
        @app.route('/subcontract/receive')
        def subcontract_receive_list(): ...

但 WMS_ACTION_MODULES 只声明了「下划线版」为 listUrl。由于
isWmsListPage() 与 listUrl 做**严格等值**比对：

    /subcontract/issue  !==  /subcontract_issue   → false（误判！）

于是以下两轮修复在该 URL 上**全部静默失效**：
  * BUG-2026-09-23-005：导航组整组隐藏失效 → 「首张/上一张/下一张/末张」
    重新出现，点击会无提示跳转到最后一张单并丢掉筛选条件（原 P1 静默陷阱）；
    同时「保存」死按钮回归（点它命中的是筛选表单）。
  * BUG-2026-09-23-006：重复按钮去重失效 → 全局栏重新渲染
    「导入 / 导出 / 导入导出模板」，与页面自带工具条形成双入口。

这两个 URL 是**真实入口**，不是臆想的：
    app/templates/subcontract_progress.html:91
        <a href="/subcontract/issue" ...>去发料</a>
    app/templates/subcontract_progress.html:93
        <a href="/subcontract/receive" ...>去入库</a>

真实浏览器实测（Chrome，?embedded=1，已登录）全局栏按钮：
    /subcontract_issue   → 新增/删除/设置/打印/智能分享                 ✅
    /subcontract/issue   → 新增/保存/删除/设置/打印/导入/导出/
                           导入导出模板/智能分享/查找单据/首张/上一张/
                           下一张/末张                                 ❌
    /subcontract_receive → 新增/删除/设置/打印/智能分享                 ✅
    /subcontract/receive → 同 issue                                   ❌

## 修复

给模块表引入**声明式** `listAliases` 数组，isWmsListPage 在 listUrl 之外
同时做别名等值比对。刻意**不用正则**——正则会重新引入 match 式的
「列表/详情/新增」歧义，而 strict equality 天然把详情页排除在外。

## 同根因排查（R6，已全量扫描 23 个模块的 match vs listUrl）

  * subcontract_issue   /subcontract/issue    有路由（同函数双装饰器）→ 本 BUG，修
  * subcontract_receive /subcontract/receive  有路由（同函数双装饰器）→ 本 BUG，修
  * check               /inventory_check      **无路由**（全仓 grep 无命中）→ 死分支，不修
  * requisition         /production_requisition 有路由但是**表单页**(302)非列表页 → 不修

即修复面恰好 2 个模块。T6 把「不修的那两个」也锁住，防止将来有人
不加复核就给无路由的虚假别名补 listAliases。

## 测试策略

沿用 005 的 harness：Python 逐行拼装 JS → node 用 new Function **真实执行**
normalizeWmsPath / isWmsListPage 后再断言返回值，而不是断言源码字符串。
（该项目踩过「注释里写了、代码没写」的假绿坑，故行为断言为主。）
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


def _run_helpers(payload_js: str) -> dict:
    """在 node 里真实执行 normalizeWmsPath / isWmsListPage。

    payload_js 内可用 __norm() / __isList() / __sc(path) 三个桥接函数。
    """
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")

    harness = ROOT / ".t8_listalias_harness.js"
    harness.write_text(_build_harness(payload_js), encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness), str(APP_JS)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)

    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


# 说明：harness 用 Python 列表逐行拼装，**不用三引号字面量**。
# 踩坑记录（沿用 005）：三引号里的 "\\n" 会被 Python 解析成**真实换行**，
# 拼出的 JS 变成 `... + "<换行>" +`——字符串未闭合，node 报
# Invalid or unexpected token。逐行列表 + 显式 \\n 转义可稳定产出。
def _build_harness(payload_js: str) -> str:
    prelude = [
        "const fs = require('fs');",
        # argv[0]=node argv[1]=本 harness argv[2]=被读取的 app.js
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
        "parts.push(extract('function normalizeWmsPath(pathname)'));",
        "parts.push(extract('function isWmsListPage(module)'));",
        "parts.push('function __norm(p){ return normalizeWmsPath(p); }');",
        "parts.push('function __isList(m){ return isWmsListPage(m); }');",
        "parts.push('function __sc(path){');",
        "parts.push('  window.location = { pathname: path, search: \"\", origin: \"http://localhost\" };');",
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
# T1：别名 URL 判定矩阵（真实执行）
# --------------------------------------------------------------------------

def test_t1_alias_url_matrix():
    """委外发料/入库的别名 URL 必须与下划线版**同等**判定为列表页。

    同时锁住反向风险：别名下的**详情页 / 新增页**绝不能被误判为列表页，
    否则会制造比原 BUG 更严重的新问题（详情页丢掉导航组与保存按钮）。
    """
    out = _run_helpers("""
        var issue = { listUrl: '/subcontract_issue',
                      listAliases: ['/subcontract/issue'] };
        var receive = { listUrl: '/subcontract_receive',
                        listAliases: ['/subcontract/receive'] };
        return {
          aliasIssue:        __sc('/subcontract/issue')        || __isList(issue),
          aliasIssueSlash:   __sc('/subcontract/issue/')       || __isList(issue),
          aliasIssueQuery:   __sc('/subcontract/issue')        || __isList(issue),
          aliasReceive:      __sc('/subcontract/receive')      || __isList(receive),
          aliasReceiveSlash: __sc('/subcontract/receive/')     || __isList(receive),
          detailAlias:       __sc('/subcontract/issue/12')     || __isList(issue),
          detailAliasEdit:   __sc('/subcontract/issue/12/edit')|| __isList(issue),
          addAlias:          __sc('/subcontract/issue/add')    || __isList(issue),
          detailReceive:     __sc('/subcontract/receive/7')    || __isList(receive),
          nestedDeeper:      __sc('/subcontract/issue/12/print') || __isList(issue)
        };
    """)

    assert out["aliasIssue"] is True, "/subcontract/issue 别名必须判定为列表页"
    assert out["aliasIssueSlash"] is True, "别名带尾斜杠也应等价"
    assert out["aliasIssueQuery"] is True
    assert out["aliasReceive"] is True, "/subcontract/receive 别名必须判定为列表页"
    assert out["aliasReceiveSlash"] is True

    # 反向锁：详情 / 新增 绝不能被别名匹配吞掉
    assert out["detailAlias"] is False, \
        "别名详情页 /subcontract/issue/12 不得被判为列表页（严格等值的关键意义）"
    assert out["detailAliasEdit"] is False
    assert out["addAlias"] is False, "别名新增页不得被判为列表页"
    assert out["detailReceive"] is False
    assert out["nestedDeeper"] is False, "更深的子路径不得被判为列表页"


# --------------------------------------------------------------------------
# T2：原有判定语义不回归（对照：回退前后都应绿）
# --------------------------------------------------------------------------

def test_t2_original_semantics_not_regressed():
    """加别名支持不得破坏 005 建立的原语义。"""
    out = _run_helpers("""
        var issue = { listUrl: '/subcontract_issue',
                      listAliases: ['/subcontract/issue'] };
        var material = { listUrl: '/material' };
        var inOrder = { listUrl: '/in_order' };
        return {
          canonical:   __sc('/subcontract_issue')   || __isList(issue),
          canonicalSl: __sc('/subcontract_issue/')  || __isList(issue),
          inOrder:     __sc('/in_order')            || __isList(inOrder),
          inOrderDet:  __sc('/in_order/1')          || __isList(inOrder),
          inOrderAdd:  __sc('/in_order/add')        || __isList(inOrder),
          material:    __sc('/material')            || __isList(material),
          crossA:      __sc('/subcontract/issue')   || __isList(material),
          crossB:      __sc('/material')            || __isList(issue)
        };
    """)

    assert out["canonical"] is True, "下划线版（listUrl 本体）必须仍为 True"
    assert out["canonicalSl"] is True
    assert out["inOrder"] is True
    assert out["inOrderDet"] is False
    assert out["inOrderAdd"] is False
    assert out["material"] is True
    assert out["crossA"] is False, "跨模块路径不得因别名而误判"
    assert out["crossB"] is False


# --------------------------------------------------------------------------
# T3：保守语义（对照）
# --------------------------------------------------------------------------

def test_t3_conservative_semantics_preserved():
    """module / listUrl 缺失时必须保守返回 False（不隐藏任何按钮）。"""
    out = _run_helpers("""
        var onlyAliases = { listAliases: ['/subcontract/issue'] };
        var emptyAliases = { listUrl: '/subcontract_issue', listAliases: [] };
        var noAliases = { listUrl: '/subcontract_issue' };
        var nullMod = null;
        return {
          onlyAliases:  __sc('/subcontract/issue')  || __isList(onlyAliases),
          emptyAliases: __sc('/subcontract_issue')  || __isList(emptyAliases),
          noAliases:    __sc('/subcontract_issue')  || __isList(noAliases),
          nullMod:      __sc('/subcontract/issue')  || __isList(nullMod),
          emptyObj:     __sc('/subcontract_issue')  || __isList({})
        };
    """)

    assert out["onlyAliases"] is False, \
        "只声明 listAliases 而无 listUrl 必须保守返回 False（保持 005 的保守语义）"
    assert out["emptyAliases"] is True, "空别名数组不应影响 listUrl 本体判定"
    assert out["noAliases"] is True
    assert out["nullMod"] is False
    assert out["emptyObj"] is False


# --------------------------------------------------------------------------
# T4：多别名支持（真实执行）
# --------------------------------------------------------------------------

def test_t4_multiple_aliases_supported():
    out = _run_helpers("""
        var multi = { listUrl: '/alpha',
                      listAliases: ['/beta', '/gamma/delta'] };
        return {
          canonical: __sc('/alpha')        || __isList(multi),
          alias1:    __sc('/beta')         || __isList(multi),
          alias2:    __sc('/gamma/delta')  || __isList(multi),
          alias2Sl:  __sc('/gamma/delta/') || __isList(multi),
          notAlias:  __sc('/delta')        || __isList(multi),
          deeper:    __sc('/beta/9')       || __isList(multi)
        };
    """)

    assert out["canonical"] is True
    assert out["alias1"] is True
    assert out["alias2"] is True, "第二个别名也必须命中"
    assert out["alias2Sl"] is True
    assert out["notAlias"] is False
    assert out["deeper"] is False, "别名下的子路径不得命中（严格等值）"


# --------------------------------------------------------------------------
# T5：接线与 005/006 逐字锁
# --------------------------------------------------------------------------

def test_t5_wiring_and_verbatim_locks():
    src = _src()

    # 两个真实缺陷模块必须声明别名
    assert "listAliases: ['/subcontract/issue']" in src, \
        "subcontract_issue 未声明 /subcontract/issue 别名"
    assert "listAliases: ['/subcontract/receive']" in src, \
        "subcontract_receive 未声明 /subcontract/receive 别名"

    # isWmsListPage 必须读取 listAliases
    body_start = src.index("function isWmsListPage(module)")
    body = src[body_start:body_start + 900]
    assert "module.listAliases" in body, "isWmsListPage 未消费 listAliases"
    assert "normalizeWmsPath(aliases[i])" in body, "别名未走归一化比对"

    # 005 的保守守卫必须保留
    assert "if (!module || !module.listUrl) return false;" in body, \
        "005 的保守守卫被破坏"

    # 005 / 006 的既有逐字锁（跨 BUG 不回归）
    assert "var isListPage = isWmsListPage(module);" in src
    assert "function createDocumentNavigationGroup(module, isListPage)" in src
    assert "function normalizeWmsPath(pathname)" in src
    assert "function pageHasOwnButton(texts, selfBar)" in src
    assert "function trimWmsActionbarDividers(buttons)" in src


# --------------------------------------------------------------------------
# T6：防未来踩坑（对照）
# --------------------------------------------------------------------------

def test_t6_no_bogus_aliases_added():
    """不修的两个「假别名」不得被顺手补上 listAliases。

    R6 排查结论：
      * check 的 match 含 /inventory_check，但**全仓无该路由** → 死分支；
        将来若真新增了 /inventory_check 列表页，应先被本断言拦下并显式复核，
        而不是有人悄悄补一条 listAliases 就算完。
      * requisition 的 /production_requisition 是**表单页**（302 跳转），
        不是列表页，绝不可当别名。

    另锁死 listAliases 的使用范围：目前**只有**这两个模块该有别名，
    防止它被滥用成第二套模糊匹配机制。
    """
    src = _src()

    assert "/inventory_check" not in _module_block(src, "check"), \
        "check 模块不得声明无路由的 /inventory_check 别名（死分支；如确需请先补路由并复核）"
    assert "listAliases" not in _module_block(src, "requisition"), \
        "requisition 不得把表单页 /production_requisition 当作列表别名"

    # listAliases 只出现在这两个模块
    assert src.count("listAliases: [") == 2, \
        f"listAliases 声明数应为 2（仅两个委外别名模块），实际 {src.count('listAliases: [')}"

    # 别名数组里只允许路径字面量，不许塞正则/函数，防止演变成模糊匹配
    assert "listAliases: [/" not in src, "listAliases 不得包含正则字面量"


def _module_block(src: str, key: str) -> str:
    """截取 WMS_ACTION_MODULES 里某个模块的声明块（到下一个同级 key 为止）。"""
    import re
    anchor = src.index("WMS_ACTION_MODULES = {")
    start = src.index(f"\n    {key}: {{", anchor)
    # 逐行找到下一个 "    <ident>: {" 形态的兄弟键
    m = re.search(r"\n    \w+:\s*\{", src[start + 5:])
    end = start + 5 + m.start() if m else len(src)
    return src[start:end]


# --------------------------------------------------------------------------
# T7：app.js 语法
# --------------------------------------------------------------------------

def test_t7_app_js_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    result = subprocess.run([node, "--check", str(APP_JS)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"app.js 语法错误:\n{result.stderr[:1200]}"
