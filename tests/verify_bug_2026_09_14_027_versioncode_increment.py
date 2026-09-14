# -*- coding: utf-8 -*-
"""BUG-2026-09-14-027：versionCode 必须每次发版递增 —— 静态契约测试。

背景（分发陷阱，「WMS扫码屡次停止运行」屡次复现的真正根因之一）：

BUG-2026-09-13-023 已实证并修复「WMS扫码屡次停止运行」的两个根因
（启动期数据持久化无兜底 + onCreate 里 setContent 之前申请权限），CI 多次转绿，
字节码级也确认修复进了新包。但用户反馈崩溃"又出现了"。

排查发现：app/build.gradle.kts 的 versionCode 自 14 起被**冻结**，
versionName 一直停在 3.8.0。Android 包管理器按 versionCode 判定"是否新版本"：
- 新旧包 versionCode 相同 → 覆盖安装被当作同版本，系统不替换旧代码；
- 用户在「应用信息」里看到的永远是 3.8.0，**无法分辨装的是修复前还是修复后**。

于是现场设备长期停留在修复前的旧包，崩溃"屡次复现"，运维却以为"已经发了新版"。
台账 BUG-2026-09-13-023 早已建议「统一递增 versionCode」，但一直未执行——本测试把它锁死。

本测试锁定的契约：
1. versionCode 必须 >= 15（即已越过被冻结的 14），且为整数。
2. versionName 必须 >= 3.8.1（与 versionCode 同步递增，便于用户自查）。
3. 防呆：build.gradle.kts 中必须保留「每次发版必须递增 versionCode」的注释，
   防止后续重构把这条防复发说明删掉后再次冻结版本号。

注意：本测试用 >= 而非 ==，允许后续继续递增，只禁止倒退/冻结。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRADLE = ROOT / "app" / "android-native-wms" / "app" / "build.gradle.kts"


def _read() -> str:
    assert GRADLE.exists(), f"未找到 {GRADLE}"
    return GRADLE.read_text(encoding="utf-8")


def _version_code(gradle: str) -> int:
    m = re.search(r"versionCode\s*=\s*(\d+)", gradle)
    assert m, "build.gradle.kts 未找到 versionCode"
    return int(m.group(1))


def _version_tuple(gradle: str) -> tuple:
    m = re.search(r'versionName\s*=\s*"([\d.]+)"', gradle)
    assert m, "build.gradle.kts 未找到 versionName"
    return tuple(int(x) for x in m.group(1).split("."))


# A9:no-test=reason=下面各 test_ 函数即本契约测试本体，被测对象为构建脚本与注释文本


def test_versioncode_not_frozen_at_14():
    """versionCode 必须已越过被冻结的 14（允许继续递增，禁止倒退/冻结）。"""
    code = _version_code(_read())
    assert code >= 15, (
        f"versionCode 被冻结/倒退: {code}。"
        "每次发版必须递增 versionCode，否则新旧包同号、系统拒绝覆盖安装，"
        "现场设备永远停留在旧代码（见 BUG-2026-09-14-027）。"
    )


def test_versionname_synced_with_versioncode():
    """versionName 与 versionCode 同步递增，便于用户在应用信息里自查。"""
    ver = _version_tuple(_read())
    assert ver >= (3, 8, 1), (
        f"versionName 未同步递增: {ver}。versionName 应随 versionCode 一起递增，"
        "否则用户无法在「应用信息」里分辨新旧包。"
    )


def test_increment_rule_comment_present():
    """构建脚本必须保留「每次发版必须递增 versionCode」的防复发注释。"""
    text = _read()
    assert "versionCode" in text and "递增" in text, (
        "build.gradle.kts 缺少「递增 versionCode」的注释说明，"
        "防复发指引可能被重构删除后再次冻结版本号。"
    )
