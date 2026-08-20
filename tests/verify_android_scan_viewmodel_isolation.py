from pathlib import Path


def test_scan_workflows_use_independent_viewmodels():
    source = (Path(__file__).resolve().parents[1] / "app" / "android-native-wms" / "app" /
              "src" / "main" / "java" / "com" / "factory" / "wms" / "ui" /
              "navigation" / "NavGraph.kt").read_text(encoding="utf-8")

    for key in ("inbound_scan", "outbound_scan", "stock_query", "stocktake"):
        assert f'viewModel(key = "{key}")' in source

    assert "viewModel = inboundScanViewModel" in source
    assert "viewModel = outboundScanViewModel" in source
    assert "viewModel = stockQueryViewModel" in source
    assert "viewModel = stocktakeViewModel" in source
