from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app/android-native-wms/app/src/main/java/com/factory/wms"


def test_camera_scan_never_uses_manual_quantity_in_any_operation():
    source = (ROOT / "ui/screens/ScanScreens.kt").read_text(encoding="utf-8")
    callbacks = source.split("onScanBarcode = { barcode ->")[1:]
    assert len(callbacks) == 3, "入库、出库和盘点应各有一个扫码回调"
    for callback in callbacks:
        body = callback.split("onSubmitClick", 1)[0]
        assert "manualQty" not in body, "相机扫码不得复用已取消的手输数量"
        assert "addCameraScanLine" in body or "quantity = 1.0" in body, "每次相机扫描应按一件处理"
