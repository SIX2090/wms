# -*- coding: utf-8 -*-
"""
BUG-2026-09-07-002 静态回归：语音指令领域词纠正双端一致性门禁。

覆盖：
T1. Android VoiceCommandViewModel.kt 含 VOICE_ASR_DOMAIN_CORRECTIONS 词表，
    且必须含用户实测两条（饮料→领料、欲哭→入库）；
T2. Android onResult 在 parseCommand 前调用 correctVoiceAsrText；
T3. Android parseCommand 含 领料→Outbound 分支；
T4. 服务端 mobile.py 路由调用 correct_voice_asr_text 且热词核心词权重 = 100；
T5. 双端词表逐项一致（Python dict 与 Kotlin list 不得漂移）；
T6. 双端均不收「推出→退出」（破坏性登出防误触发）。

使用方法：
  cd /workspace && python -m pytest tests/verify_bug_2026_09_07_002_voice_domain_correction.py -xvs --noconftest
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICE_VM = (
    ROOT / "app" / "android-native-wms" / "app" / "src" / "main" / "java"
    / "com" / "factory" / "wms" / "ui" / "viewmodel" / "voice" / "VoiceCommandViewModel.kt"
)
MOBILE_ROUTE = ROOT / "app" / "routes" / "mobile.py"
sys.path.insert(0, str(ROOT / "app"))

from tencent_asr import VOICE_ASR_DOMAIN_CORRECTIONS as PY_MAP  # noqa: E402


def _read(path: Path) -> str:
    assert path.is_file(), f"missing {path}"
    return path.read_text(encoding="utf-8")


def _kotlin_map(src: str) -> dict:
    m = re.search(
        r"VOICE_ASR_DOMAIN_CORRECTIONS\s*=\s*listOf\((.*?)\)", src, re.S
    )
    assert m, "Kotlin 侧必须定义 VOICE_ASR_DOMAIN_CORRECTIONS = listOf(...)"
    return dict(re.findall(r'"([^"]+)"\s+to\s+"([^"]+)"', m.group(1)))


def test_t1_kotlin_correction_table_present() -> None:
    src = _read(VOICE_VM)
    km = _kotlin_map(src)
    assert km.get("饮料") == "领料", "Kotlin 词表必须含 饮料→领料（用户实测）"
    assert km.get("欲哭") == "入库", "Kotlin 词表必须含 欲哭→入库（用户实测）"


def test_t2_onresult_applies_correction() -> None:
    src = _read(VOICE_VM)
    idx = src.find("override fun onResult(")
    assert idx != -1, "缺少 onResult 回调"
    body = src[idx:idx + 1500]
    assert "correctVoiceAsrText(" in body, "onResult 必须调用 correctVoiceAsrText"
    # 纠正必须先于指令解析（同在 onResult 函数体内比较）
    assert body.index("correctVoiceAsrText(") < body.index("parseCommand(text)"), \
        "onResult 内 correctVoiceAsrText 必须先于 parseCommand"


def test_t3_lingliao_command_branch() -> None:
    src = _read(VOICE_VM)
    assert re.search(r'lt\.contains\("领料"\)\s*->\s*VoiceCommand\.Navigate\(Screen\.Outbound\)', src), \
        "parseCommand 必须含 领料→Outbound 分支（领料出库）"


def test_t4_route_wiring_and_hotword_weights() -> None:
    src = _read(MOBILE_ROUTE)
    assert "correct_voice_asr_text" in src, "mobile_asr 路由必须调用 correct_voice_asr_text"
    m = re.search(r"hotword_list='([^']+)'", src)
    assert m, "mobile_asr 必须传 hotword_list"
    pairs = dict(item.split("|") for item in m.group(1).split(","))
    for word in ("入库", "出库", "领料", "盘点", "查库存", "库存",
                 "识物", "识别", "期初", "送货单", "退货", "调拨"):
        assert pairs.get(word) == "100", f"热词 {word} 权重必须 = 100，实际 {pairs.get(word)}"


def test_t5_dual_side_parity() -> None:
    """双端词表逐项一致——任何一端改词表必须同步另一端。"""
    km = _kotlin_map(_read(VOICE_VM))
    assert km == dict(PY_MAP), (
        "双端词表漂移：\n"
        f"仅 Kotlin 有: {sorted(set(km.items()) - set(PY_MAP.items()))}\n"
        f"仅 Python 有: {sorted(set(PY_MAP.items()) - set(km.items()))}"
    )


def test_t6_no_destructive_logout_correction() -> None:
    src = _read(VOICE_VM)
    km = _kotlin_map(src)
    assert "推出" not in km and "推出" not in PY_MAP, \
        "双端均不得收「推出→退出」（防口误误触发登出）"
