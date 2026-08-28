# -*- coding: utf-8 -*-
"""AI-MOB-UI-F01 回归：手机端界面精修特征静态断言。

背景：手机端 H5（mobile_scan/mobile_connect/mobile_app_download_fallback）
视觉升级为「淡雅渐变背景 + 胶囊分段 Tab + 大圆角柔和阴影卡片 + 渐变主按钮 +
按压回弹微交互 + focus 光环」。本测试锁定关键 CSS 特征，防止后续改动把
精修样式改回扁平旧版；同时断言 JS 钩子 class 名/DOM id 未被破坏
（mobile_scan 的 JS 与 tests 依赖这些锚点）。

验收：
T1. custom.css 含精修特征：渐变 Tab / focus 光环 / 卡片阴影 / 按压 scale /
    fadeUp 动画 / 库存数字渐变文字。
T2. mobile_scan.html 内联样式含精修特征：扫码框圆角+发光扫描线 / 待确认卡片
    :has 类型色条 / 批量面板渐变按钮。
T3. JS 钩子完整性：mobile_scan.html 仍含全部关键 class 与 id 锚点
    （scanStatus/materialCard/batchPanel/confirmList/loadMore 等）。
T4. mobile_connect.html 含精修特征（二维码卡片阴影/渐变按钮）。
T5. 5 个 Tab 一栏排齐（grid-template-columns: repeat(5)），不再 4+1 换行。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS_PATH = ROOT / "app" / "static" / "css" / "custom.css"
SCAN_TPL = ROOT / "app" / "templates" / "mobile_scan.html"
CONNECT_TPL = ROOT / "app" / "templates" / "mobile_connect.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestMobileUiPolish:
    def test_custom_css_polish_features(self):
        """T1：custom.css 含全部精修特征。"""
        css = _read(CSS_PATH)
        features = {
            "渐变页面背景": r"body\.mobile-scan-page\s*\{[^}]*linear-gradient",
            "胶囊 Tab 激活渐变": r"\.mobile-scan-tab\.active\s*\{[^}]*linear-gradient\(135deg, #2563eb",
            "Tab 按压回弹": r"\.mobile-scan-tab:active\s*\{[^}]*scale\(0\.94\)",
            "卡片大圆角": r"\.mobile-scan-panel\s*\{[^}]*border-radius:\s*16px",
            "卡片柔和阴影": r"\.mobile-scan-panel\s*\{[^}]*box-shadow:\s*0 4px 20px",
            "heading 图标渐变": r"\.mobile-scan-heading-icon\s*\{[^}]*linear-gradient\(135deg, #0d9488",
            "输入框 focus 光环": r"\.mobile-scan-field \.form-control:focus\s*\{[^}]*0 0 0 4px rgba\(37, 99, 235, 0\.12\)",
            "主按钮渐变": r"\.mobile-scan-submit\s*\{[^}]*linear-gradient\(135deg, #2563eb",
            "主按钮按压回弹": r"\.mobile-scan-submit:active:not\(:disabled\)\s*\{[^}]*scale\(0\.97\)",
            "物料卡顶部渐变条": r"\.mobile-material-card::before\s*\{[^}]*linear-gradient\(90deg, #2563eb",
            "库存数字渐变文字": r"\.mobile-material-stock strong\s*\{[^}]*-webkit-text-fill-color:\s*transparent",
            "历史项左侧竖条": r"\.mobile-history-item::before\s*\{[^}]*linear-gradient\(180deg, #22c55e",
            "fadeUp 动画": r"@keyframes mobileFadeUp",
        }
        missing = [name for name, pat in features.items() if not re.search(pat, css)]
        assert not missing, f"custom.css 缺少精修特征: {missing}"

    def test_scan_template_inline_polish_features(self):
        """T2：mobile_scan.html 内联样式含精修特征。"""
        html = _read(SCAN_TPL)
        features = {
            "扫码框圆角": r"\.mobile-barcode-frame\s*\{[^}]*border-radius:\s*14px",
            "扫描线发光": r"\.mobile-barcode-scan-line\s*\{[^}]*box-shadow:\s*0 0 14px 3px rgba\(96, 165, 250",
            "待确认卡片入库色条": r"\.mobile-confirm-card:has\(\.mobile-confirm-tag-in\)::before\s*\{[^}]*linear-gradient\(180deg, #22c55e",
            "待确认卡片出库色条": r"\.mobile-confirm-card:has\(\.mobile-confirm-tag-out\)::before\s*\{[^}]*linear-gradient\(180deg, #f97316",
            "待确认 tag 渐变": r"\.mobile-confirm-tag-in\s*\{[^}]*linear-gradient\(135deg, #16a34a",
            "批量提交按钮渐变": r"\.mobile-batch-header \.btn\s*\{[^}]*linear-gradient\(135deg, #2563eb",
            "识别预览卡片阴影": r"\.mobile-recognize-preview\s*\{[^}]*box-shadow:\s*0 2px 10px",
        }
        missing = [name for name, pat in features.items() if not re.search(pat, html)]
        assert not missing, f"mobile_scan.html 缺少精修特征: {missing}"

    def test_scan_template_js_hooks_intact(self):
        """T3：JS 钩子 class/id 锚点完整（美化不得破坏 DOM 结构）。"""
        html = _read(SCAN_TPL)
        hooks = [
            'id="scanCode"', 'id="lookupBtn"', 'id="scanStatus"',
            'id="matchList"', 'id="materialCard"', 'id="scanForm"',
            'id="submitBtn"', 'id="quantityInput"', 'id="warehouseInput"',
            'id="batchMode"', 'id="batchPanel"', 'id="batchList"',
            'id="batchCount"', 'id="batchSubmitBtn"',
            'id="confirmList"', 'id="confirmRefreshBtn"',
            'id="confirmWarehouseSelect"',
            'id="barcodeScanner"', 'id="barcodeVideo"',
            'id="recognizePreview"', 'id="recognizePreviewImg"',
            "loadMore", "fetchPendingPage", "confirmMoreBtn",
            "mobile-batch-row", "mobile-confirm-card",
            "mobile-confirm-tag-in", "mobile-confirm-tag-out",
            "'&page=' + page", "已全部加载",
        ]
        missing = [h for h in hooks if h not in html]
        assert not missing, f"mobile_scan.html JS 钩子被破坏: {missing}"

    def test_connect_template_polish(self):
        """T4：mobile_connect.html 含精修特征。"""
        html = _read(CONNECT_TPL)
        features = {
            "二维码卡片阴影": r"\.mobile-connect-qr\s*\{[^}]*box-shadow:\s*0 4px 16px",
            "复制按钮渐变": r"\.mobile-connect-url-row \.btn\s*\{[^}]*linear-gradient\(135deg, #2563eb",
            "下载按钮渐变": r"\.mobile-connect-actions \.btn-success\s*\{[^}]*linear-gradient\(135deg, #16a34a",
        }
        missing = [name for name, pat in features.items() if not re.search(pat, html)]
        assert not missing, f"mobile_connect.html 缺少精修特征: {missing}"

    def test_tabs_five_columns(self):
        """T5：5 个 Tab（入库/出库/查询/盘点/待确认）一栏排齐，不再 4+1 换行。"""
        css = _read(CSS_PATH)
        m = re.search(r"\.mobile-scan-tabs\s*\{[^}]*grid-template-columns:\s*repeat\((\d+)", css)
        assert m, "未找到 .mobile-scan-tabs 的列定义"
        assert m.group(1) == "5", (
            f"Tab 应为 5 列（模板有 5 个 Tab），实际 {m.group(1)} 列"
        )
