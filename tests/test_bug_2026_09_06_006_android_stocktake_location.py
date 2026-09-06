from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQ = (ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/data/model/ScanRequests.kt").read_text(encoding="utf-8")
VM = (ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/viewmodel/scan/ScanViewModel.kt").read_text(encoding="utf-8")
SCREEN = (ROOT / "app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/ScanScreens.kt").read_text(encoding="utf-8")
NATIVE = (ROOT / "app/routes/native_api.py").read_text(encoding="utf-8")

def test_android_stocktake_carries_area():
    assert "val area: String? = null" in REQ
    assert "area = line.location_code?.trim()?.ifBlank { null }" in VM
    assert "盘点库位/区域" in SCREEN
    assert "location_code = stocktakeArea.trim().ifBlank { null }" in SCREEN

def test_android_supports_same_material_multiple_locations():
    assert "it.location_code.orEmpty() == line.location_code.orEmpty()" in VM
    assert "line.location_code" in SCREEN

def test_native_stocktake_requires_location_for_differences():
    assert "line.get('location')" in NATIVE
    assert "盘点差异必须填写库位/区域" in NATIVE