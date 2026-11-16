from pathlib import Path

from scripts.verify_wms_bugs import check_mobile_archive_spec_wrap_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'app/android-native-wms/app/src/main/java/com/factory/wms/ui/screens/MaterialArchiveScreens.kt'


def test_spec_guard_tracks_list_row_and_rejects_truncation():
    content = SOURCE.read_text(encoding='utf-8')
    start = content.index('Text(material.spec?')
    end = content.index('\n            Text("单位：', start)
    spec = content[start:end]
    assert check_mobile_archive_spec_wrap_source(content)[0]
    for replacement in (
        spec.replace('softWrap = true', 'softWrap = false'),
        spec.replace('softWrap = true', 'softWrap = true, maxLines = 1'),
        spec.replace('softWrap = true', 'softWrap = true, maxLines = 2'),
        spec.replace('softWrap = true', 'softWrap = true, overflow = TextOverflow.Ellipsis'),
        spec.replace('softWrap = true', 'softWrap = true, overflow = TextOverflow.Clip'),
    ):
        assert replacement != spec
        assert not check_mobile_archive_spec_wrap_source(content[:start] + replacement + content[end:])[0]
    assert not check_mobile_archive_spec_wrap_source(content.replace('internal fun MaterialArchiveRow(', 'internal fun RemovedRow('))[0]
