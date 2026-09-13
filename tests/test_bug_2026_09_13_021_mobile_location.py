from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / 'app/android-native-wms/app/src/main/java/com/factory/wms'


def test_outbound_location_input_and_line_binding():
    source = (ROOT / 'ui/screens/ScanScreens.kt').read_text(encoding='utf-8')
    outbound = source.split('fun OutboundScreen(', 1)[1]
    assert outbound.count('location_code = uiState.selectedLocation.ifBlank { null }') >= 2
    base = (ROOT / 'ui/screens/ScanScreenBase.kt').read_text(encoding='utf-8')
    assert 'ScanLocationSelector(viewModel)' in base
    selector = (ROOT / 'ui/components/ScanLocationSelector.kt').read_text(encoding='utf-8')
    assert '扫描库位标签' in selector
    assert 'continuous = false' in selector


def test_location_is_sent_in_outbound_request():
    source = (ROOT / 'data/model/ScanRequests.kt').read_text(encoding='utf-8')
    assert 'val location_code: String? = null' in source


def test_backend_still_requires_location_when_enabled():
    source = (Path(__file__).resolve().parents[1] / 'app/routes/native_api.py').read_text(encoding='utf-8')
    outbound = source.split("@app.route('/api/outbound'", 1)[1]
    assert 'location_management_enabled() and location_required_on_save()' in outbound
    assert "line.get('location_code')" in outbound
