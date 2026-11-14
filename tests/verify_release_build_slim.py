# -*- coding: utf-8 -*-
"""AI-MOB-APK-001：CI 走 assembleRelease（R8 瘦身）+ F3.12 签名三态契约。

背景：debug 包不做 R8/资源收缩，material-icons-extended 全量图标、Compose、
MLKit 等依赖全量进 dex，是 APK 200MB 的另一半根因（sherpa 70MB 已移除）。
release 变体 isMinifyEnabled/isShrinkResources 已开启，R8 会剔除未用图标
（Compose 图标是纯代码 ImageVector，无字体资源）与未用代码。

签名（F3.12，审计 §4.6）：未设 WMS_STORE_FILE 时构建**失败**，不再静默
debug 签名——防止「名为 release 实为 debug 签名」的包流出当正式包分发。
debug 签名必须显式选择：WMS_ALLOW_DEBUG_SIGNED_RELEASE=1（CI 内部测试包，
配合固定 debug.keystore 跨构建稳定、可覆盖安装）；配置 WMS_STORE_FILE 时
走正式签名并强制校验参数齐全。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CI = (ROOT / ".github" / "workflows" / "android-build.yml").read_text(encoding="utf-8")
GRADLE = (ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts").read_text(encoding="utf-8")


def _gradle_cmds() -> list[str]:
    return [
        ln.strip() for ln in CI.splitlines()
        if re.match(r"\s*run:\s*\./gradlew", ln)
    ]


def test_ci_uses_assemble_release() -> None:
    """T1：CI 构建命令必须全部走 release 变体（R8 瘦身才生效）。"""
    cmds = _gradle_cmds()
    assert cmds, "CI 未找到 gradlew 命令"
    assert any("assembleRelease" in c for c in cmds), (
        f"CI 必须用 assembleRelease（R8/资源收缩只在 release 变体生效）：{cmds}"
    )
    legacy = [c for c in cmds if re.search(r"assembleDebug|lintDebug|testDebugUnitTest", c)]
    assert not legacy, f"CI 仍在跑 debug 变体（应改为 release 变体）：{legacy}"


def test_ci_artifacts_point_to_release_apk() -> None:
    """T2：Upload/Publish 的 APK 路径必须指向 release 产物。"""
    assert "outputs/apk/release/app-release.apk" in CI, (
        "Upload/Publish 路径应指向 outputs/apk/release/app-release.apk"
    )
    assert "outputs/apk/debug/app-debug.apk" not in CI, "Upload/Publish 仍指向 debug APK"
    assert "name: app-release" in CI, "Upload artifact 名应为 app-release"
    assert "name: app-debug" not in CI, "Upload artifact 名仍是 app-debug"


def test_ci_uploads_r8_mapping() -> None:
    """T3：release 混淆后必须上传 mapping.txt，崩溃堆栈才能还原。"""
    assert "outputs/mapping/release/mapping.txt" in CI, (
        "release 混淆包必须随 artifact 上传 mapping.txt（崩溃还原必需）"
    )


def test_release_keeps_minify_and_shrink() -> None:
    """T4：release 变体必须保持 R8 与资源收缩开启（瘦身的前提）。"""
    m = re.search(r"release \{.*?\n    \}", GRADLE, re.S)
    assert m, "build.gradle.kts 未找到 release buildType 块"
    block = m.group(0)
    assert "isMinifyEnabled = true" in block, "release 必须开启 R8（isMinifyEnabled）"
    assert "isShrinkResources = true" in block, "release 必须开启资源收缩（isShrinkResources）"
    assert "proguard-rules.pro" in block, "release 必须挂 proguard-rules.pro"


def test_release_signing_three_way_contract() -> None:
    """T5（F3.12）：release 签名三态——正式签名 / 显式 debug / 拒绝静默回退。"""
    m = re.search(r"release \{.*?\n    \}", GRADLE, re.S)
    assert m, "build.gradle.kts 未找到 release buildType 块"
    block = m.group(0)
    assert 'System.getenv("WMS_STORE_FILE") != null' in block, (
        "release 签名必须按 WMS_STORE_FILE 条件切换"
    )
    assert 'WMS_ALLOW_DEBUG_SIGNED_RELEASE' in block and 'getByName("debug")' in block, (
        "debug 签名必须显式经 WMS_ALLOW_DEBUG_SIGNED_RELEASE=1 选择（F3.12 拒绝静默回退）"
    )
    assert "else -> null" in block, (
        "两者皆未配置时 signingConfig 必须为 null（由校验任务抛出明确错误），"
        "不得再默认回退 debug 签名"
    )


def test_signing_validation_rejects_silent_debug_fallback() -> None:
    """T6（F3.12）：未设 WMS_STORE_FILE 且未显式允许 debug 签名 → 构建失败。"""
    m = re.search(r'tasks\.configureEach \{.*?\n    \}', GRADLE, re.S)
    assert m, "build.gradle.kts 未找到签名校验 task"
    block = m.group(0)
    assert 'if (System.getenv("WMS_STORE_FILE") != null)' in block, (
        "正式签名参数校验必须包在「配置了 WMS_STORE_FILE 才校验」的条件下"
    )
    assert 'WMS_ALLOW_DEBUG_SIGNED_RELEASE' in block, "缺 debug 签名显式开关分支"
    reject = re.search(
        r'WMS_ALLOW_DEBUG_SIGNED_RELEASE"\)\s*!=\s*"1"\s*\)\s*\{.*?throw GradleException',
        block, re.S)
    assert reject, (
        "未配置 WMS_STORE_FILE 且未显式允许 debug 签名时必须 throw GradleException"
    )


def test_ci_explicitly_opts_into_debug_signing() -> None:
    """T7（F3.12）：CI 构建 release 必须显式设置 WMS_ALLOW_DEBUG_SIGNED_RELEASE=1。"""
    m = re.search(
        r"- name: Build Release APK \(R8 瘦身\)(.*?)\n\s*- name:", CI, re.S)
    assert m, "CI 未找到 Build Release APK 步骤"
    step = m.group(1)
    assert 'WMS_ALLOW_DEBUG_SIGNED_RELEASE: "1"' in step, (
        "CI 的 assembleRelease 必须显式设置 WMS_ALLOW_DEBUG_SIGNED_RELEASE=1，"
        "否则 F3.12 后构建必炸"
    )
