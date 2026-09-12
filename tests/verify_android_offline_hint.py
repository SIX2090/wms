# -*- coding: utf-8 -*-
"""离线（缓存回退）数据提示 —— 静态契约测试（AI-MOB-OFFLINE-HINT-01）。

需求背景（用户原话：「wms手机端app怎么把它打造一个很好用很实用的app?」→「按你的思路来做」）

诊断结论
--------------------------------------------------------------------
`WmsRepository.getMaterialInfo`（旧 :281-289）在网络失败时会回退到 Room 本地缓存：

    } catch (e: Exception) {
        val cached = materialDao.getByCode(code)
        if (cached != null) Result.success(cached.toDto())   // ← 直接返回，不给任何标记
        ...

**调用方无法区分**这是实时库存还是三天前的缓存。
用户看到「库存 5」就出库 5 —— 这是**业务风险**（超发/账面为负），不是体验问题。

`MaterialEntity` 里其实一直有 `last_sync_time` 字段，但**从未被用来提示**。

本测试锁定的契约
--------------------------------------------------------------------
T1. `MaterialDto` 增加 `fromCache` / `cachedAtMillis` 两个字段，且为 `@Transient`
    （后端不下发，纯客户端标记；不标记 @Transient 会参与 Gson 序列化往返，
    在 RequestBody 里多出无意义字段）。
T2. 两个字段必须**有默认值**，否则所有既有 `MaterialDto(...)` 构造调用会编译失败。
T3. Repository 的缓存回退分支必须**同时**置 `fromCache = true` 并带上
    `cachedAtMillis = cached.lastSyncTime` —— 只标记不给时间，用户不知道"有多旧"。
T4. 正常网络成功分支**不得**置 fromCache（否则横幅会常驻，变成噪音）。
T5. `OfflineDataBanner` 组件存在，文案必须明确"这是缓存、可能不是最新"
    （只说「离线数据」而不说后果，用户照样会照着念数字出库）。
T6. 时间格式化要处理**时钟回拨**（未来时间戳）—— 不处理会出现"−30 分钟前"。
T7. 库存结果卡接线：`material.fromCache` 为真时显示横幅。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java" / "com" / "factory" / "wms"

DTO = SRC / "data" / "model" / "MaterialDto.kt"
REPO = SRC / "data" / "repository" / "WmsRepository.kt"
COMPONENTS = SRC / "ui" / "components" / "WmsComponents.kt"
SCREENS = SRC / "ui" / "screens" / "ScanScreens.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# T1 + T2. DTO 字段
# ---------------------------------------------------------------------------
def test_t1_dto_has_cache_marker_fields():
    src = _read(DTO)
    assert re.search(r"val\s+fromCache\s*:\s*Boolean", src), (
        "MaterialDto 缺少 fromCache 标记 —— 调用方无法区分实时库存与缓存数据"
    )
    assert re.search(r"val\s+cachedAtMillis\s*:\s*Long\?", src), (
        "MaterialDto 缺少 cachedAtMillis —— 只标记不给时间，用户不知道数据有多旧"
    )
    # 必须 @Transient（后端不下发，纯客户端标记）
    for field in ("fromCache", "cachedAtMillis"):
        m = re.search(rf"@Transient\s+val\s+{field}", src)
        assert m, (
            f"{field} 必须标注 @Transient —— 后端不下发这两个字段，"
            "不标注会参与 Gson 序列化往返，在请求体里多出无意义字段"
        )


def test_t2_cache_fields_have_defaults():
    src = _read(DTO)
    assert re.search(r"val\s+fromCache\s*:\s*Boolean\s*=\s*false", src), (
        "fromCache 必须默认 false —— 缺省值才能让既有 MaterialDto(...) 构造调用继续编译，"
        "且未标记的数据默认按「实时」处理（保守方向正确：宁可漏提示也不误报）"
    )
    assert re.search(r"val\s+cachedAtMillis\s*:\s*Long\?\s*=\s*null", src), (
        "cachedAtMillis 必须默认 null"
    )


# ---------------------------------------------------------------------------
# T3 + T4. Repository 分支
# ---------------------------------------------------------------------------
def test_t3_cache_fallback_sets_marker_and_timestamp():
    src = _read(REPO)
    # 定位 getMaterialInfo 的 catch 分支
    m = re.search(
        r"val\s+cached\s*=\s*materialDao\.getByCode\(code\)(?P<body>.{0,600}?)Result\.failure",
        src, re.DOTALL,
    )
    assert m, "未找到缓存回退分支（materialDao.getByCode 后的处理）"
    body = m.group("body")
    assert "fromCache = true" in body, (
        "缓存回退时必须置 fromCache = true —— 否则 UI 无法显示离线横幅，"
        "用户会照着过期数字出库"
    )
    assert re.search(r"cachedAtMillis\s*=\s*cached\.lastSyncTime", body), (
        "缓存回退时必须带上 cachedAtMillis = cached.lastSyncTime —— "
        "MaterialEntity 里这个字段一直存在，就是用来表达「数据有多旧」的"
    )


def test_t4_network_success_path_does_not_set_cache_marker():
    src = _read(REPO)
    # getMaterialInfo 的网络成功分支：从请求发出到 catch 之前
    m = re.search(
        r"val\s+response\s*=\s*api\.materialInfo\(code,\s*warehouseCode\)"
        r"(?P<body>.*?)catch\s*\(\s*e\s*:\s*Exception\s*\)",
        src, re.DOTALL,
    )
    assert m, "无法定位 getMaterialInfo 的网络成功分支"
    body = m.group("body")
    assert "fromCache" not in body, (
        "网络成功分支不得置 fromCache —— 否则离线横幅会常驻显示，"
        "变成噪音后用户就再也不看它了（狼来了效应）"
    )


# ---------------------------------------------------------------------------
# T5 + T6. 组件与文案
# ---------------------------------------------------------------------------
def test_t5_banner_component_with_actionable_copy():
    src = _read(COMPONENTS)
    assert re.search(r"fun\s+OfflineDataBanner\s*\(", src), "缺少 OfflineDataBanner 组件"
    # 文案必须说明后果，不能只说"离线数据"
    assert re.search(r"可能不是最新", src), (
        "横幅文案必须说明「可能不是最新库存」—— "
        "只写「离线数据」用户不理解后果，照样会照着念数字出库"
    )
    assert re.search(r"本地缓存", src), "横幅文案应点明「本地缓存」"
    # 用 Warning 色系（警示而非错误/成功）
    assert "WarningContainer" in src, "横幅应使用 WarningContainer 底色（警示级，不是 Error）"


def test_t6_time_formatter_handles_clock_skew():
    src = _read(COMPONENTS)
    m = re.search(r"fun\s+formatCacheAge\s*\((?P<sig>[^)]*)\)(?P<body>.*?)\n\}", src, re.DOTALL)
    assert m, "缺少 formatCacheAge 时间格式化函数"
    body = m.group("body")
    # 负值/时钟回拨保护
    assert re.search(r"deltaMs\s*<\s*0|delta\s*<\s*0", body), (
        "formatCacheAge 必须处理时钟回拨（设备时间被改到过去时，"
        "deltaMs 会为负，不处理会显示「-30 分钟前」这种明显错误的文案）"
    )
    # null / 非法时间戳
    assert re.search(r"==\s*null|<=?\s*0L", body), "formatCacheAge 必须处理 null / 非法时间戳"
    # 分级文案
    for unit in ("分钟前", "小时前", "天前"):
        assert unit in body, f"formatCacheAge 缺少「{unit}」分级"


# ---------------------------------------------------------------------------
# T7. 接线
# ---------------------------------------------------------------------------
def test_t7_banner_wired_in_stock_result_card():
    src = _read(SCREENS)
    assert "OfflineDataBanner" in src, "查库存结果卡未接线离线横幅"
    assert re.search(r"material\.fromCache", src), (
        "横幅必须由 material.fromCache 条件渲染 —— "
        "无条件显示会让正常在线时也挂着警告条"
    )
    assert re.search(r"cachedAtMillis\s*=\s*material\.cachedAtMillis", src), (
        "横幅应把 cachedAtMillis 传下去，否则用户看不到「3 小时前」这个关键信息"
    )
    assert "import com.factory.wms.ui.components.OfflineDataBanner" in src, (
        "缺少 OfflineDataBanner 的 import"
    )
