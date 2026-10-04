from pathlib import Path


def test_scan_workflows_use_independent_viewmodels():
    source = (Path(__file__).resolve().parents[1] / "app" / "android-native-wms" / "app" /
              "src" / "main" / "java" / "com" / "factory" / "wms" / "ui" /
              "navigation" / "NavGraph.kt").read_text(encoding="utf-8")

    # BUG-2026-10-04-001：创建点现追加 factory = ScanViewModel.Factory（两参构造必需），
    # 断言同步为按 key 前缀匹配——语义不变：4 个流程仍各用独立 key 的独立实例
    for key in ("inbound_scan", "outbound_scan", "stock_query", "stocktake"):
        assert f'viewModel(key = "{key}"' in source

    assert "viewModel = inboundScanViewModel" in source
    assert "viewModel = outboundScanViewModel" in source
    assert "viewModel = stockQueryViewModel" in source
    assert "viewModel = stocktakeViewModel" in source
