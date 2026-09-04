# -*- coding: utf-8 -*-
"""BUG-2026-09-04-003 回归测试：CI 固定 debug 签名（方案B 锚点验证）。

现象：CI 每次构建生成的 debug.keystore 都不同（实测 #285 产物证书有效期起点
= 本次构建时刻），任意旧版本 APK 均无法被新包覆盖安装（签名冲突）。

修复：android-build.yml 在构建前把仓库 Secret WMS_FIXED_DEBUG_KEYSTORE_B64
还原到 ~/.android/debug.keystore，让 AGP 每次使用同一 debug 签名；Secret
未配置时输出 warning 不阻塞构建。

本测试以静态锚点固化该修复，防止后续改 workflow 时回退。
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WF = ROOT / ".github" / "workflows" / "android-build.yml"


def _workflow_text():
    return WF.read_text(encoding="utf-8")


def test_restore_step_exists_before_build():
    """还原 keystore 步骤必须存在且位于构建步骤之前。"""
    src = _workflow_text()
    restore = src.find("Restore fixed debug keystore (BUG-2026-09-04-003)")
    build = src.find("Build Release APK (R8 瘦身)")
    assert restore != -1, "缺少还原固定 keystore 步骤"
    assert build != -1
    assert restore < build, "还原 keystore 必须发生在构建之前"


def test_secret_name_and_decode_target():
    """Secret 名与还原目标路径必须正确。"""
    src = _workflow_text()
    assert "secrets.WMS_FIXED_DEBUG_KEYSTORE_B64" in src
    assert "~/.android/debug.keystore" in src
    assert "base64 -d" in src


def test_missing_secret_degrades_to_warning():
    """Secret 未配置时降级为 warning，不阻塞构建。"""
    src = _workflow_text()
    assert "::warning::未配置 Secret WMS_FIXED_DEBUG_KEYSTORE_B64" in src
    assert "if [ -n \"$WMS_FIXED_DEBUG_KEYSTORE_B64\" ]" in src


def test_workflow_yaml_parses():
    """workflow 必须是合法 YAML（语法防回归）。"""
    try:
        import yaml  # noqa: F401
    except ImportError:
        return  # 沙箱无 pyyaml 时跳过（CI 上 pyyaml 恒可用）
    data = yaml.safe_load(WF.read_text(encoding="utf-8"))
    steps = data["jobs"]["build"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert "Restore fixed debug keystore (BUG-2026-09-04-003)" in names
