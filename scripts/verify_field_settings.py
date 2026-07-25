"""Regression checks for the shared document field-settings panel."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "app/static/js/app.js").read_text(encoding="utf-8")
CSS = (ROOT / "app/static/css/custom.css").read_text(encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS {message}")


require("window.WmsFieldSettings" in JS, "共享栏目设置 API 已注册")
require("wms:field-settings:v3:" in JS and "localStorage.setItem" in JS, "设置按页面持久化")
require("data-fs-tab=\"header\"" in JS and "data-fs-tab=\"detail\"" in JS, "提供表头和明细页签")
require("data-fs-tab=\"summary\"" in JS and "data-fs-tab=\"footer\"" in JS, "提供汇总和表尾页签")
require("data-fs-search" in JS and "data-fs-locate" in JS, "支持字段搜索和定位")
require(all(token in JS for token in ('data-fs-move=\"top\"', 'data-fs-move=\"up\"', 'data-fs-move=\"down\"', 'data-fs-move=\"bottom\"')), "支持置顶、上移、下移和置底")
require("state.labels" in JS and "setHeaderLabel" in JS, "支持修改显示名称")
require("state.hidden" in JS and "wms-field-column-hidden" in JS, "支持显示和隐藏字段")
require("'contract_no','project_name'" in JS and "column && !column.locked" in JS, "合同编号和工程名称保持明细必显")
require("MutationObserver" in JS, "动态新增明细行自动应用设置")
require("prepareTable" in JS and "column_" in JS, "未标注列键的旧单据自动兼容")
require("[hidden]{display:none!important}" in CSS, "弹窗关闭状态可靠")
require("@media(max-width:640px)" in CSS, "移动端布局已适配")
require("window.WmsFillDown" in JS and "wms-fill-down-btn" in JS, "全局明细字段向下填充已注册")
require("table.addEventListener('focusin'" in JS, "向下填充以当前编辑行作为起点")
require("control.dispatchEvent(new Event('input'" in JS and "control.dispatchEvent(new Event('change'" in JS, "填充后触发金额等联动计算")
excluded_line = next(line for line in JS.splitlines() if "var excludedKeys = new Set" in line)
require("contract_no" not in excluded_line and "project_name" not in excluded_line, "合同编号和工程名称支持向下填充")

print("PASS FIELD-SETTINGS: shared T+-style field settings verified")
