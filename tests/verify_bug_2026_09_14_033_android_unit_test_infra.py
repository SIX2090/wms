#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-14-033 回归：Android 单元测试基础设施必须真实存在且在 CI 中运行。

## 缺陷

`.github/workflows/android-build.yml` 自 BUG-2026-08-16-021 起包含：

    - name: Unit tests (BUG-2026-08-16-021)
      run: ./gradlew testReleaseUnitTest

但**同时存在两个导致该步骤形同虚设的事实**：
  1. `app/src/test` 目录**不存在** → Gradle 没有任何测试源可编译执行；
  2. `build.gradle.kts` 的 dependencies 里**没有任何测试依赖**
     （junit / robolectric / coroutines-test / androidx.test 全无）→
     即便写了测试也无法编译。

Gradle 对"零测试源"的 `testReleaseUnitTest` 任务会**成功退出**（NO-SOURCE），
所以 CI 一直显示绿色，门禁却从未真正拦住过任何东西。项目 55 个"Android 测试"
全部是 Python 正则匹配 Kotlin 源码字符串，**测不出任何运行时行为**——
BUG-2026-09-14-029 的冷启动闪退要修 5 轮才定位到真凶，根因就在这里。

## 本测试锁死的不变量

- 测试源目录存在且含真实 `@Test` 用例（不是空壳）；
- JUnit 与 Robolectric 依赖已声明；
- `testOptions.unitTests.isIncludeAndroidResources = true`（Robolectric 必需）；
- CI 工作流仍保留 `testReleaseUnitTest` 步骤（防被误删）。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ANDROID = REPO_ROOT / "app" / "android-native-wms"
TEST_SRC = ANDROID / "app" / "src" / "test"
GRADLE = ANDROID / "app" / "build.gradle.kts"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "android-build.yml"

# 必须有依赖的测试库（缺失则测试无法编译）
REQUIRED_TEST_DEPS = [
    "junit:junit",
    "org.robolectric:robolectric",
    "kotlinx-coroutines-test",
]


def test_033_test_source_dir_exists() -> None:
    """`app/src/test` 必须存在——否则 testReleaseUnitTest 是 NO-SOURCE 空跑。"""
    assert TEST_SRC.is_dir(), (
        f"Android 单元测试源目录不存在：{TEST_SRC}\n"
        "这正是 testReleaseUnitTest 一直空跑（NO-SOURCE 却显示绿色）的直接原因"
    )


def test_033_has_real_kotlin_test_files() -> None:
    """必须存在真实 Kotlin 测试文件，且含 @Test 用例。"""
    kt_files = list(TEST_SRC.rglob("*.kt"))
    assert kt_files, f"{TEST_SRC} 下没有任何 .kt 测试文件（目录存在但为空 = 同样空跑）"

    with_tests = []
    for f in kt_files:
        content = f.read_text(encoding="utf-8")
        if re.search(r"@Test\b", content):
            with_tests.append(f)
    assert with_tests, "测试文件里没有任何 @Test 用例（空壳文件不算）"


@pytest.mark.parametrize("dep", REQUIRED_TEST_DEPS)
def test_033_test_dependency_declared(dep: str) -> None:
    """测试依赖必须已声明——否则测试源码无法编译。"""
    assert GRADLE.exists(), f"未找到 {GRADLE}"
    content = GRADLE.read_text(encoding="utf-8")
    assert dep in content, (
        f"build.gradle.kts 未声明测试依赖 `{dep}`——"
        "缺失时 @Test/@RunWith(RobolectricTestRunner) 无法解析，CI 会在编译阶段失败"
    )


def test_033_robolectric_needs_android_resources() -> None:
    """Robolectric 需要 isIncludeAndroidResources=true 才能读资源/Manifest。"""
    content = GRADLE.read_text(encoding="utf-8")
    assert "isIncludeAndroidResources = true" in content, (
        "缺少 testOptions.unitTests.isIncludeAndroidResources = true——"
        "Robolectric 无法访问合并后的资源与 Manifest"
    )


def test_033_ci_still_runs_unit_tests() -> None:
    """CI 必须保留 testReleaseUnitTest 步骤（防被误删，门禁不能退回空跑）。"""
    assert WORKFLOW.exists(), f"未找到 {WORKFLOW}"
    wf = WORKFLOW.read_text(encoding="utf-8")
    assert "testReleaseUnitTest" in wf, (
        "android-build.yml 不再运行 testReleaseUnitTest——单元测试门禁被移除"
    )


def test_033_covers_the_three_real_crash_root_causes() -> None:
    """测试必须覆盖三个真实崩溃根因对应的契约（防测试被写成无关紧要的断言）。"""
    all_src = "\n".join(
        f.read_text(encoding="utf-8") for f in TEST_SRC.rglob("*.kt")
    )
    checks = {
        "BUG-2026-09-14-029 baseUrl 安全守卫": "服务器地址未配置",
        "BUG-2026-09-12-008 syncing 非终态": "resetStuckSyncing",
        "BUG-2026-09-12-008 失败必须可见": "countFailed",
    }
    missing = [name for name, token in checks.items() if token not in all_src]
    assert not missing, (
        "以下真实崩溃根因的契约未被测试覆盖：\n  " + "\n  ".join(missing)
    )


def test_033_no_placehold_only_tests() -> None:
    """反向断言：不允许只写空断言（assertTrue(true)）糊弄门禁。"""
    offenders = []
    for f in TEST_SRC.rglob("*.kt"):
        content = f.read_text(encoding="utf-8")
        for m in re.finditer(r"assertTrue\(\s*true\s*\)|assertNotNull\(\s*null\s*\?\s*:", content):
            line_no = content[: m.start()].count("\n") + 1
            offenders.append(f"{f.relative_to(TEST_SRC)}:{line_no}")
    assert not offenders, f"存在无实际意义的占位断言：{offenders}"


def test_033_baseline_registered() -> None:
    """BUG-2026-09-14-033 必须已登记进基线。"""
    baseline = REPO_ROOT / "WMS_BUG_BASELINE.md"
    assert baseline.exists(), "WMS_BUG_BASELINE.md 不存在"
    assert "BUG-2026-09-14-033" in baseline.read_text(encoding="utf-8"), (
        "BUG-2026-09-14-033 未登记进 WMS_BUG_BASELINE.md"
    )
