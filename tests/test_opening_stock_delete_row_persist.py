# -*- coding: utf-8 -*-
"""期初库存「行内删除图标」回归（BUG-2026-09-16-004）。

问题（用户反馈延续 BUG-2026-09-16-001 的排查）：
行内删除图标 `deleteRow(index)` 原本只做 `rows.splice()` —— 删的是**前端数组**。
已建账的行必须再点一次「保存」才会由后端差集回冲落库，而界面**没有任何提示**：
用户点删除图标后看见行消失了，以为删成功就直接离开页面，下次打开该行又回来了
（库存也没回冲）。属"静默失效"——操作看着生效、实际没落库。

修复口径（与 batchDeleteSelectedRows 完全一致，避免同类点规则漂移 R6）：
  · 已建账行（有 line_id）→ 调 `POST /opening_stock/<id>/lines/delete` 传单个 id，
    立即物理删除 + 库存回冲；删除前确认框说明"将从库存扣回、不可恢复"；
  · 未保存行 → 仅从录入网格移除，但必须提示"尚未保存，点保存后才生效"，
    不再让用户误以为已落库。

覆盖：
  T1 已建账行：调用批量接口（单 id），成功后本地摘行 + 成功提示
  T2 已建账行：确认框说明会回冲库存；用户取消则不发请求、行保持不动
  T3 已建账行：接口失败时不摘行（避免界面与后端不一致），给出错误提示
  T4 未保存行：不发任何请求，本地移除，且提示含"尚未保存"
  T5 无 OPENING_DOC 时不误打不存在的单据 id
  T6 静态：不得再存在"只 splice 不落库且无提示"的旧实现
  T7 删除图标 tooltip 区分已建账/未保存
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
TEMPLATE = APP_DIR / "templates" / "opening_stock.html"
NODE = shutil.which("node")


def _template_src() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _extract_function(src: str, name: str) -> str:
    m = re.search(r"^function %s\b[\s\S]*?^}" % re.escape(name), src, re.M)
    assert m, f"模板中未找到函数 {name}"
    return m.group(0)


@pytest.fixture(scope="module")
def js_runtime(tmp_path_factory):
    """抽出模板真实函数，在 node 中执行 deleteRow 的真实逻辑。"""
    if not NODE:
        pytest.skip("未安装 node，跳过 deleteRow 动态验证")

    src = _template_src()
    funcs = "\n\n".join(
        _extract_function(src, n)
        for n in ("syncSelectedFlags", "renderRows", "deleteRow")
    )

    harness = tmp_path_factory.mktemp("os_delrow") / "harness.js"
    harness.write_text(
        funcs
        + """

let rows = [];
let selectedFlags = [];
let OPENING_DOC = null;
const calls = [];       // 记录 WMS.api.post 调用
let confirmAnswer = true;
let nextResponse = { status: 'success', msg: '明细行已删除，库存已回冲' };
const toasts = [];

function confirm(msg) { calls.push({ type: 'confirm', msg }); return confirmAnswer; }
function showToast(msg, type) { toasts.push({ msg, type }); }
// renderRows 依赖 DOM，桩掉（本测试只关心状态与网络调用）
function renderRows() { calls.push({ type: 'render' }); }
const document = { getElementById: () => null };

const WMS = {
    api: {
        post(url, payload) {
            calls.push({ type: 'post', url, payload });
            if (nextResponse instanceof Error) {
                return Promise.reject(nextResponse);
            }
            return Promise.resolve(nextResponse);
        },
    },
};

function reset(state) {
    rows = (state.rows || []).map(r => Object.assign({}, r));
    selectedFlags = rows.map(() => false);
    OPENING_DOC = state.doc === undefined ? { id: 5, doc_no: 'QS26090005' } : state.doc;
    calls.length = 0;
    toasts.length = 0;
    confirmAnswer = state.confirm === undefined ? true : state.confirm;
    nextResponse = state.response || { status: 'success', msg: '明细行已删除，库存已回冲' };
}

// 驱动并等一个微任务轮次，让 Promise 回调跑完
async function drive(index) {
    deleteRow(index);
    await new Promise(r => setTimeout(r, 0));
    return {
        calls: calls.slice(),
        toasts: toasts.slice(),
        rows: rows.map(r => r.material_code),
        rowCount: rows.length,
    };
}

module.exports = { reset, drive };
""",
        encoding="utf-8",
    )
    return harness


def _run_node(harness: Path, script: str) -> dict:
    r = subprocess.run(
        [NODE, "-e", f"const h = require({str(harness)!r});\n(async () => {{\n{script}\n}})();"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert r.returncode == 0, f"node 执行失败：{r.stderr[:600]}"
    return json.loads(r.stdout)


class TestOpeningStockDeleteRow:
    """行内删除图标的落库行为（已建账立即删 / 未保存仅本地）。"""

    def test_t1_saved_row_calls_batch_endpoint_and_removes(self, js_runtime):
        """已建账行：应调批量接口（单个 line_id），成功后本地摘行并提示。"""
        out = _run_node(js_runtime, """
h.reset({
  rows: [
    { material_id: 1, line_id: 11, material_code: 'M001', material_name: '轴承' },
    { material_id: 2, line_id: 12, material_code: 'M002', material_name: '电机' },
  ],
});
const r = await h.drive(0);
console.log(JSON.stringify(r));
""")
        posts = [c for c in out["calls"] if c["type"] == "post"]
        assert len(posts) == 1, f"应恰好发一次删除请求，实际 {len(posts)}"
        assert posts[0]["url"] == "/opening_stock/5/lines/delete", (
            f"应走批量接口（语义一致），实际 {posts[0]['url']}"
        )
        assert posts[0]["payload"] == {"line_ids": [11]}, (
            f"应只传被删行的 line_id，实际 {posts[0]['payload']}"
        )
        assert out["rows"] == ["M002"], f"应摘掉 M001，实际剩下 {out['rows']}"
        assert any("已删除" in t["msg"] or "回冲" in t["msg"] for t in out["toasts"]), (
            f"应有成功提示，实际 {out['toasts']}"
        )

    def test_t2_saved_row_requires_confirm_and_mentions_stock_reversal(self, js_runtime):
        """已建账行：确认框须说明会回冲库存；用户取消则不发请求、行不动。"""
        # 取消场景
        out = _run_node(js_runtime, """
h.reset({
  rows: [{ material_id: 1, line_id: 11, material_code: 'M001', material_name: '轴承' }],
  confirm: false,
});
const r = await h.drive(0);
console.log(JSON.stringify(r));
""")
        confirms = [c for c in out["calls"] if c["type"] == "confirm"]
        assert confirms, "已建账行删除前应有确认框"
        assert "库存" in confirms[0]["msg"], (
            f"确认框应说明会回冲库存，实际文案：{confirms[0]['msg']}"
        )
        assert not [c for c in out["calls"] if c["type"] == "post"], (
            "用户取消后不得发删除请求"
        )
        assert out["rowCount"] == 1, "取消后行应原样保留"

    def test_t3_saved_row_keeps_row_when_api_fails(self, js_runtime):
        """接口失败时不得摘行——否则界面显示已删、后端其实还在。"""
        out = _run_node(js_runtime, """
h.reset({
  rows: [{ material_id: 1, line_id: 11, material_code: 'M001', material_name: '轴承' }],
  response: { status: 'error', msg: '所选明细行不属于本单据或已被删除，请刷新后重试' },
});
const r = await h.drive(0);
console.log(JSON.stringify(r));
""")
        assert out["rowCount"] == 1, "接口失败时行必须保留（避免界面与后端不一致）"
        assert any(t["type"] == "danger" for t in out["toasts"]), (
            f"失败应给 danger 提示，实际 {out['toasts']}"
        )

    def test_t4_unsaved_row_is_local_only_and_warns(self, js_runtime):
        """未保存行：不发请求，本地移除，且必须提示"尚未保存"。"""
        out = _run_node(js_runtime, """
h.reset({
  rows: [{ material_id: 1, material_code: 'M001', material_name: '轴承' }],
});
const r = await h.drive(0);
console.log(JSON.stringify(r));
""")
        assert not [c for c in out["calls"] if c["type"] == "post"], (
            "未保存行不应发任何后端请求"
        )
        assert out["rowCount"] == 0, "未保存行应被本地移除"
        assert out["toasts"], "未保存行删除应有提示（原实现完全静默）"
        assert any("未保存" in t["msg"] or "保存" in t["msg"] for t in out["toasts"]), (
            f"提示应告知用户尚未落库、需保存，实际 {out['toasts']}"
        )

    def test_t5_no_doc_falls_back_to_local_removal(self, js_runtime):
        """理论不可达（无单据却有 line_id）：兜底本地移除，不误打单据 id。"""
        out = _run_node(js_runtime, """
h.reset({
  rows: [{ material_id: 1, line_id: 11, material_code: 'M001', material_name: '轴承' }],
  doc: null,
});
const r = await h.drive(0);
console.log(JSON.stringify(r));
""")
        assert not [c for c in out["calls"] if c["type"] == "post"], (
            "无单据时不得请求 /opening_stock/null/lines/delete"
        )
        assert out["rowCount"] == 0, "无单据时兜底本地移除"


class TestOpeningStockDeleteRowStatic:
    """静态契约：防止退回"静默失效"的旧实现。"""

    def test_t6_delete_row_not_silent_anymore(self):
        """deleteRow 不得再是"只 splice、不落库、不提示"的三无实现。"""
        src = _template_src()
        body = _extract_function(src, "deleteRow")
        # 必须按是否已建账分流
        assert "line_id" in body, "deleteRow 必须区分已建账行与未保存行"
        assert "lines/delete" in body, "已建账行必须走删除接口立即落库"
        # 未保存分支必须有提示（原实现完全没有 showToast）
        assert body.count("showToast") >= 2, (
            "已建账与未保存两条分支都应有提示，避免静默失效"
        )
        # 已建账行删除前应有确认（会回冲库存，不可恢复）
        assert "confirm(" in body, "已建账行删除前应有确认框"
        assert "库存" in body, "确认文案应说明会回冲库存"

    def test_t7_delete_icon_tooltip_distinguishes_state(self):
        """删除图标 tooltip 应区分"已建账会回冲"与"尚未保存"。"""
        src = _template_src()
        m = re.search(r'onclick="deleteRow\(\$\{index\}\)"[^>]*title="([^"]*)"', src)
        assert m, "未找到删除图标的 title 定义"
        title = m.group(1)
        assert "line_id" in title, "tooltip 应按 row.line_id 区分状态"
        assert "已建账" in title and "尚未保存" in title, (
            f"tooltip 应分别说明两种状态，实际：{title}"
        )

    def test_t8_unsaved_hint_present(self):
        """未保存行的移除提示必须点明"点保存后才生效"。"""
        src = _template_src()
        body = _extract_function(src, "deleteRow")
        assert "尚未保存" in body, "未保存行提示应含「尚未保存」字样"
        assert "保存" in body
