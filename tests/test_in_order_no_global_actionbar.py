# -*- coding: utf-8 -*-
"""采购入库明细表「单工具栏」回归：页面 opt-out 全局工具栏注入。

## 背景

采购入库明细表（/in_order?type=purchase_in）在 Tab 嵌入模式下曾出现
「全局工具栏（app.js 注入的 #cbGlobalActionBar）+ 页面自带工具栏」两套并存：

  - 全局栏：新增 / 删除 / 打印 / 导入 / 导出 / 导入导出模板 / 智能分享
  - 页面栏：新增采购入库 / 完成已选 / 更多▾ / 删除已选

页面栏已收敛为一层完整工具栏后，全局栏的注入纯属重复。本修复给
insertGlobalActionBar() 增加 additive opt-out：body 带 wms-no-global-actionbar
类（页面经 base.html 的 body_class 块开启）时直接 return，不再注入全局栏。

只影响显式开启的页面；其它页面（未开启）全局栏行为不变。

## 测试策略

T1/T2 源码断言（接线存在）；T3 node 真实执行 insertGlobalActionBar，验证
opt-out 类存在时**提前 return**（不读 .embedded-content、不创建 bar），且不带
opt-out 类时**不被此开关拦截**（继续往下走）。
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "app" / "static" / "js" / "app.js"
TEMPLATE = ROOT / "app" / "templates" / "in_order.html"


def _src() -> str:
    return APP_JS.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# T1：in_order.html 通过 body_class 块开启 opt-out
# --------------------------------------------------------------------------

def test_t1_template_opts_out_via_body_class():
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "{% block body_class %}wms-no-global-actionbar{% endblock %}" in html, \
        "in_order.html 未通过 body_class 块开启 wms-no-global-actionbar"


# --------------------------------------------------------------------------
# T2：app.js insertGlobalActionBar 有 opt-out 提前 return
# --------------------------------------------------------------------------

def test_t2_app_js_has_optout_gate():
    src = _src()
    assert "document.body.classList.contains('wms-no-global-actionbar')" in src, \
        "insertGlobalActionBar 缺少 wms-no-global-actionbar opt-out 判断"
    # opt-out 必须放在 isWmsEmbeddedPage 之后、getWmsActionModule 之前，
    # 否则仍会读 module/注入。用位置断言锁顺序。
    i_embed = src.index("if (!isWmsEmbeddedPage()) return;")
    i_opt = src.index("document.body.classList.contains('wms-no-global-actionbar')")
    i_module = src.index("var module = getWmsActionModule();", i_embed)
    assert i_embed < i_opt < i_module, \
        "opt-out 判断顺序错误（应在 isWmsEmbeddedPage 之后、getWmsActionModule 之前）"


# --------------------------------------------------------------------------
# T3：node 真实执行——opt-out 提前 return；无 opt-out 不被拦截
# --------------------------------------------------------------------------

def _build_harness(payload_js: str) -> str:
    prelude = [
        "const fs = require('fs');",
        "const src = fs.readFileSync(process.argv[2], 'utf8');",
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
        # 函数源码必须塞进 code 字符串（new Function 只认全局/自身作用域，
        # 模块顶层 eval 定义的函数在 new Function 体内不可见）。
        "const parts = [];",
        "parts.push(extract('function insertGlobalActionBar()'));",
        "const code = parts.join('\\n') + '\\nreturn JSON.stringify((function(){ ' + " + json.dumps(payload_js) + " + ' })());';",
        "const out = new Function('global', code)(global);",
        "console.log(out);",
    ]
    return "\n".join(prelude) + "\n"


def _run(payload_js: str) -> dict:
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    harness = ROOT / ".t_noactionbar_harness.js"
    harness.write_text(_build_harness(payload_js), encoding="utf-8")
    try:
        result = subprocess.run([node, str(harness), str(APP_JS)],
                                capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert result.returncode == 0, f"harness 执行失败:\n{result.stderr[:1500]}"
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_t3_optout_early_return_behavior():
    out = _run(r"""
        function mkEnv(hasOptout) {
          var state = { querySelectorCalled: false, barCreated: false, moduleCalled: false };
          global.isWmsEmbeddedPage = function () { return true; };
          global.getWmsActionModule = function () { state.moduleCalled = true; return null; };
          global.document = {
            getElementById: function () { return null; },
            querySelector: function () { state.querySelectorCalled = true; return null; },
            createElement: function () { state.barCreated = true;
              return { className: '', id: '', classList: { add: function () {} }, appendChild: function () {} }; },
            body: { classList: {
              contains: function (c) { return hasOptout && c === 'wms-no-global-actionbar'; },
              add: function () {}
            } }
          };
          return state;
        }

        // A) 带 opt-out 类：必须在读 .embedded-content / getWmsActionModule 之前 return
        var a = mkEnv(true);
        insertGlobalActionBar();

        // B) 不带 opt-out 类：不应被此开关拦截，会继续走到 getWmsActionModule（此处返回 null 而再 return）
        var b = mkEnv(false);
        insertGlobalActionBar();

        return {
          aModuleCalled: a.moduleCalled,
          aQuerySelector: a.querySelectorCalled,
          aBarCreated: a.barCreated,
          bModuleCalled: b.moduleCalled,
        };
    """)

    # A：opt-out 生效 —— getWmsActionModule 与 querySelector 都不该被调用，bar 未创建
    assert out["aModuleCalled"] is False, "带 opt-out 类时仍调用了 getWmsActionModule（未提前 return）"
    assert out["aQuerySelector"] is False, "带 opt-out 类时仍读取了 .embedded-content（未提前 return）"
    assert out["aBarCreated"] is False, "带 opt-out 类时仍创建了全局栏"
    # B：无 opt-out —— 不被此开关拦截，继续走到 getWmsActionModule
    assert out["bModuleCalled"] is True, "不带 opt-out 类时被误拦截（opt-out 影响了未开启页面）"


# --------------------------------------------------------------------------
# T4：app.js 语法检查
# --------------------------------------------------------------------------

def test_t4_app_js_syntax():
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    result = subprocess.run([node, "--check", str(APP_JS)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, f"app.js 语法错误:\n{result.stderr[:1200]}"
