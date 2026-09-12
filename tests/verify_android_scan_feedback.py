# -*- coding: utf-8 -*-
"""扫码声音/震动反馈 —— 静态契约测试（AI-MOB-SCAN-UX-01）。

需求背景（用户原话：「wms手机端app怎么把它打造一个很好用很实用的app?」→「按你的思路来做」）

为什么需要
--------------------------------------------------------------------
仓库现场的特征是：环境嘈杂、工人戴手套、货架间光线差。**工人基本不看屏幕**。
扫中/扫失败没有任何声音和震动反馈，就必须盯着屏幕逐条确认 ——
这直接把扫码的效率优势抵消掉了。

诊断时全项目搜 `ToneGenerator|RingtoneManager|Vibrator|MediaPlayer` 零命中，
`AndroidManifest.xml` 也没有 VIBRATE 权限。

本测试锁定的契约
--------------------------------------------------------------------
T1. `AndroidManifest.xml` 声明 VIBRATE 权限（普通权限，安装即授予）。
T2. `ScanFeedback` 对象存在，提供 success / failure 两个入口，
    且**两者在手感与听感上必须可区分**（不同音调 + 不同震动节奏）。
T3. `ToneGenerator` 必须 release（系统音频资源，泄漏会导致后续拿不到实例）。
T4. 反馈**不得抛出异常**：无马达/静音/音频占用都不应让扫码崩掉。
T5. 三个扫码场景都接线：ScanScreenBase（入库/出库/盘点）、OpeningStockScreen、StockQueryScreen。
T6. 成功/失败判定走 `materialExists`，且该方法**在网络异常时返回 true**
    （断网不该把"查不到"误报成"物料不存在"，否则会给工人错误的失败反馈）。
T7. 开关可关闭，且**默认开启**；开关状态走内存缓存，
    不在扫码回调（相机分析线程）里做磁盘 IO。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANDROID = ROOT / "app" / "android-native-wms" / "app" / "src" / "main"
SRC = ANDROID / "java" / "com" / "factory" / "wms"

MANIFEST = ANDROID / "AndroidManifest.xml"
FEEDBACK = SRC / "util" / "ScanFeedback.kt"
APP = SRC / "WmsApplication.kt"
SCAN_BASE = SRC / "ui" / "screens" / "ScanScreenBase.kt"
OPENING = SRC / "ui" / "screens" / "OpeningStockScreen.kt"
SCREENS = SRC / "ui" / "screens" / "ScanScreens.kt"
PROFILE = SRC / "ui" / "screens" / "ProfileScreen.kt"
VIEWMODEL = SRC / "ui" / "viewmodel" / "scan" / "ScanViewModel.kt"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_t1_vibrate_permission_declared():
    m = _read(MANIFEST)
    assert re.search(r'<uses-permission\s+android:name="android\.permission\.VIBRATE"\s*/>', m), (
        "AndroidManifest 未声明 VIBRATE 权限 —— 没有它 Vibrator.vibrate() 会抛 "
        "SecurityException（被 try-catch 吞掉后表现就是「完全没有震动」，很难排查）"
    )


def test_t2_feedback_distinguishes_success_and_failure():
    src = _read(FEEDBACK)
    assert "object ScanFeedback" in src, "缺少 ScanFeedback 单例"
    assert re.search(r"fun\s+success\s*\(", src), "缺少 success 入口"
    assert re.search(r"fun\s+failure\s*\(", src), "缺少 failure 入口"

    # 两者必须用不同音调常量
    tones = re.findall(r"private\s+const\s+val\s+TONE_\w+\s*=\s*ToneGenerator\.\w+", src)
    assert len(tones) >= 2, (
        f"success/failure 必须使用不同的音调常量（当前只有 {len(tones)} 个）—— "
        "只震动不区分等于没反馈，工人不知道自己这一下扫上了没有"
    )
    # 且取值真的不同
    vals = re.findall(r"TONE_\w+\s*=\s*(ToneGenerator\.\w+)", src)
    assert len(set(vals)) >= 2, "两个音调常量取了同一个 ToneGenerator 值，听感上无法区分"

    # 震动节奏必须不同：成功单次，失败多次
    success_region = re.search(r"fun\s+success\s*\((?P<body>.*?)\n    \}", src, re.DOTALL)
    failure_region = re.search(r"fun\s+failure\s*\((?P<body>.*?)\n    \}", src, re.DOTALL)
    assert success_region and failure_region, "无法定位 success/failure 函数体"

    def _vib_pattern(body: str) -> str:
        m = re.search(r"vibrate\s*\([^,]+,\s*(?P<pat>[^,]+),", body)
        assert m, "未找到 vibrate 调用"
        return m.group("pat").strip()

    assert _vib_pattern(success_region.group("body")) != _vib_pattern(failure_region.group("body")), (
        "success 与 failure 的震动模式相同 —— 现场靠手感分辨不出来"
    )
    # 失败必须是双震及以上（节奏上区分于成功的单次短震）
    assert "FAILURE_VIBRATE_PATTERN" in src, "失败反馈应使用具名震动模式常量"
    pattern_def = re.search(r"FAILURE_VIBRATE_PATTERN\s*=\s*longArrayOf\((?P<v>[^)]*)\)", src)
    assert pattern_def, "未找到 FAILURE_VIBRATE_PATTERN 定义"
    vals_n = len([x for x in pattern_def.group("v").split(",") if x.strip()])
    assert vals_n >= 4, (
        f"失败震动模式只有 {vals_n} 段，至少要 [等待,震,等待,震] 四段才能形成「双震」节奏"
    )


def test_t3_tone_generator_is_released():
    src = _read(FEEDBACK)
    assert "ToneGenerator(" in src, "未使用 ToneGenerator"
    assert re.search(r"\.release\s*\(\s*\)", src), (
        "ToneGenerator 必须 release —— 它是系统音频资源，不释放会泄漏，"
        "多次开关相机后可能再也拿不到实例（实测部分机型约 30 个后返回 null）"
    )


def test_t4_feedback_never_throws():
    src = _read(FEEDBACK)
    # 必须有多处 try-catch 兜底
    assert src.count("catch") >= 4, (
        f"ScanFeedback 的异常兜底不足（当前 {src.count('catch')} 处）—— "
        "反馈是锦上添花：无震动马达、静音模式、音频被占用都不该让扫码崩掉"
    )
    # 不得有裸抛
    assert not re.search(r"\bthrow\s+\w*Exception", src), (
        "ScanFeedback 不应抛异常（它是附加反馈，失败只打日志）"
    )
    # 拿不到 vibrator 要能安全返回
    assert re.search(r"hasVibrator\s*\(\s*\)", src), (
        "缺少 hasVibrator() 判断 —— 部分设备（如某些平板/模拟器）没有马达，"
        "不判断会走到异常路径"
    )


def test_t5_all_scan_paths_wired():
    for path, label in (
        (SCAN_BASE, "ScanScreenBase（入库/出库/盘点）"),
        (OPENING, "OpeningStockScreen（期初库存）"),
        (SCREENS, "ScanScreens（查库存）"),
    ):
        src = _read(path)
        assert "ScanFeedback.success" in src, f"{label} 未接入成功反馈"
        assert "ScanFeedback.failure" in src, f"{label} 未接入失败反馈"
        # 必须有 import，否则编译不过
        assert "import com.factory.wms.util.ScanFeedback" in src, f"{label} 缺少 ScanFeedback import"


def test_t6_material_exists_is_safe_on_network_failure():
    src = _read(VIEWMODEL)
    assert re.search(r"suspend\s+fun\s+materialExists\s*\(", src), (
        "ScanViewModel 缺少 materialExists（扫码反馈的成功/失败判定依据）"
    )
    body = re.search(r"suspend\s+fun\s+materialExists\s*\([^)]*\)\s*:\s*Boolean\s*\{(?P<b>.*?)\n    \}", src, re.DOTALL)
    assert body, "无法定位 materialExists 函数体"
    b = body.group("b")
    assert "catch" in b, "materialExists 必须兜住异常"
    # 关键：catch 分支必须返回 true。
    # 兼容两种 Kotlin 写法（本仓库既有约定，见 verify_bug_2026_08_09_003）：
    #   a) `} catch (...) { ... return true }`
    #   b) `return try { ... } catch (...) { true }`（catch 块最后表达式为 true）
    assert re.search(r"catch\s*\([^)]*\)\s*\{[^}]*return\s+true", b, re.DOTALL) or re.search(
        r"catch\s*\([^)]*\)\s*\{[^}]*\btrue\b\s*\}?\s*$", b.strip(), re.DOTALL
    ), (
        "materialExists 在网络异常时必须返回 true —— "
        "断网时把「查不到」误报成「物料不存在」，会给工人错误的失败反馈，"
        "反而让人以为扫错了码而重复扫"
    )


def test_t7_switch_exists_and_defaults_on():
    src = _read(FEEDBACK)
    # 默认开启
    assert re.search(r"var\s+enabled\s*:\s*Boolean\s*=\s*true", src), (
        "反馈开关默认值必须为 true —— 现场场景默认需要反馈，"
        "宁可没设置过也有反馈，而不是让用户先去设置里找"
    )
    # 两个入口都要受开关控制
    for fn in ("success", "failure"):
        body = re.search(rf"fun\s+{fn}\s*\([^)]*\)\s*\{{(?P<b>.*?)\n    \}}", src, re.DOTALL)
        assert body, f"无法定位 {fn} 函数体"
        assert re.search(r"if\s*\(\s*!\s*enabled\s*\)\s*return", body.group("b")), (
            f"{fn} 未受开关控制"
        )
    # 内存缓存（不在扫码回调里做磁盘 IO）
    assert re.search(r"fun\s+warmUp\s*\(", src), "缺少 warmUp（进程启动时预热开关到内存）"
    assert "@Volatile" in src, (
        "开关的内存缓存必须 @Volatile —— 它在启动时主线程写、扫码时相机分析线程读"
    )
    # Application 里确实调了 warmUp
    assert "ScanFeedback.warmUp" in _read(APP), (
        "WmsApplication 未调用 ScanFeedback.warmUp —— 开关会一直是默认值，改设置不生效"
    )


def test_t8_profile_toggle_wired():
    src = _read(PROFILE)
    assert "scan_feedback_enabled" in _read(FEEDBACK), "缺少持久化键"
    assert "ScanFeedback.setEnabled" in src, (
        "「我的」页未接线开关 —— 用户无法关闭反馈（会议室/办公室场景会嫌吵）"
    )
    assert re.search(r"ProfileToggleRow", src), "缺少开关行组件"
    assert "Switch(" in src, "开关行未使用 Switch 控件"
    # 开关行要带说明，否则用户不知道开了会怎样
    assert re.search(r"description\s*:", src), "开关行缺少副标题说明"
