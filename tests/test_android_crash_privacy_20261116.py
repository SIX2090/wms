from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "app/android-native-wms/app/src/main/java/com/factory/wms"

def test_startup_keeps_local_report_but_does_not_invoke_automatic_upload():
    application = (ROOT / "WmsApplication.kt").read_text(encoding="utf-8")
    assert "CrashReporter.writePendingReport(" in application
    assert all("CrashReporter.uploadPendingAsync(" not in p.read_text(encoding="utf-8") for p in ROOT.rglob("*.kt"))

def test_report_keeps_manual_copy_and_continue():
    activity = (ROOT / "MainActivity.kt").read_text(encoding="utf-8")
    assert "复制崩溃信息" in activity
    assert "我已记录，继续使用" in activity
    assert "clearPendingCrash()" in activity
