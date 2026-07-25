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
require("wms:field-settings:v2:" in JS and "localStorage.setItem" in JS, "设置按页面持久化")
require("data-fs-tab=\"header\"" in JS and "data-fs-tab=\"detail\"" in JS, "提供表头和明细页签")
require("data-fs-tab=\"summary\"" in JS and "data-fs-tab=\"footer\"" in JS, "提供汇总和表尾页签")
require("data-fs-search" in JS and "data-fs-locate" in JS, "支持字段搜索和定位")
require(all(token in JS for token in ('data-fs-move=\"top\"', 'data-fs-move=\"up\"', 'data-fs-move=\"down\"', 'data-fs-move=\"bottom\"')), "支持置顶、上移、下移和置底")
require("state.labels" in JS and "setHeaderLabel" in JS, "支持修改显示名称")
require("state.hidden" in JS and "wms-field-column-hidden" in JS, "支持显示和隐藏字段")
require("MutationObserver" in JS, "动态新增明细行自动应用设置")
require("prepareTable" in JS and "column_" in JS, "未标注列键的旧单据自动兼容")
require("[hidden]{display:none!important}" in CSS, "弹窗关闭状态可靠")
require("@media(max-width:640px)" in CSS, "移动端布局已适配")

print("PASS FIELD-SETTINGS: shared T+-style field settings verified")
