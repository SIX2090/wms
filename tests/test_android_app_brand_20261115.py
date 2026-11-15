"""Current product name contracts; no APK, device, database or network access."""
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
ANDROID=ROOT/'app/android-native-wms/app/src/main'
def test_installed_name_uses_the_same_resource_as_h5_brand():
    application=ET.parse(ANDROID/'AndroidManifest.xml').getroot().find('application')
    assert application.attrib['{http://schemas.android.com/apk/res/android}label']=='@string/app_name'
    assert ET.parse(ANDROID/'res/values/strings.xml').getroot().find("string[@name='app_name']").text=='WMS'
def test_android_identity_and_existing_data_namespace_are_preserved():
    config=(ROOT/'app/android-native-wms/app/build.gradle.kts').read_text()
    assert 'applicationId = "com.factory.wms.mobile"' in config
    assert 'namespace = "com.factory.wms"' in config
def test_current_download_and_update_names_follow_user_requested_name():
    workflow=(ROOT/'.github/workflows/android-build.yml').read_text()
    updater=(ROOT/'scripts/android_update_release.py').read_text()
    assert 'WMS（候选构建' in workflow and 'WMS 手机端（候选构建' not in workflow
    assert 'WMS 更新；' in updater and 'WMS 手机端更新；' not in updater
def test_h5_visible_name_and_title_use_wms_without_mobile_suffix():
    header=(ROOT/'app/templates/_mobile_app_header.html').read_text()
    assert '<span>WMS</span>' in header
    assert 'WMS 手机端' not in header and 'WMS手机端' not in header
    assert 'WMS · ' in (ROOT/'app/templates/base.html').read_text()
