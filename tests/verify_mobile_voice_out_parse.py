# -*- coding: utf-8 -*-
"""语音建单文本解析（Android 语音 → 领料单草稿）—— 归一化与结构化抽取测试。

背景：用户说「领8*25螺丝 1000个」，需要抽出物料关键词「螺丝」+ 规格「8*25」+ 数量 1000。

为何不复用 `app.py` 的 `_ai_parse_material_lines`：实测该函数在本场景直接失效——
   「领8*25螺丝 1000个」 → 候选「25螺丝」（规格被截断）
   「领8*25螺丝」       → 空
   「领料 螺丝8*25 1000个」→ 数量张冠李戴（8 被当数量）
根因是它的正则把「数字」一律当数量，不理解「8*25」是整体规格。
本实现的核心差别：**先锁定规格片段，再在规格之外找数量**。

验收：
- T1 回归：现有解析器失效的三个用例必须被正确解析
- T2 规格分隔符变体（* x X × - / 乘 叉 杠）统一为规格
- T3 中文数字归一（含「二十五」「一千」「三千五百」）
- T4 数量只在「规格之外 + 带量词」时抽取（防张冠李戴）
- T5 无数量 → quantity=None（不猜，交人工填写）
- T6 建单动词/标记词剥离（领/出库/拿/规格/型号/的）
- T7 同音纠错（罗丝→螺丝、零→领、螺栓→螺丝）
- T8 纯导航语（"领料"/"出库"）不产生物料关键词
- T9 规格可带字母前缀（M8*25）
- T10 语序倒装 / 数量在规格前
"""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))


def _load_module():
    """直接加载 native_api.py 模块级纯函数（不触发 Flask 注册）。"""
    import db  # noqa: F401  —— native_api 顶部依赖
    spec = importlib.util.spec_from_file_location(
        "_na_voice_parse", ROOT / "app/routes/native_api.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


M = _load_module()
parse = M._parse_voice_out_text
normalize = M._normalize_voice_text
cn2int = M._voice_cn_number_to_int


# ── T1 回归：现有解析器失效的三个用例 ──────────────────────────────

def test_t1_regression_cases_that_broke_legacy_parser():
    # 用例 1：规格曾被截断成「25螺丝」
    r = parse("领8*25螺丝 1000个")
    assert r["spec_hint"] == "8*25"
    assert r["keyword"] == "螺丝"
    assert r["quantity"] == 1000.0

    # 用例 2：曾完全解析不出（无数量）
    r = parse("领8*25螺丝")
    assert r["spec_hint"] == "8*25"
    assert r["keyword"] == "螺丝"
    assert r["quantity"] is None

    # 用例 3：曾把规格里的 8 当数量
    r = parse("领料 螺丝8*25 1000个")
    assert r["quantity"] == 1000.0, "规格里的 8 不得被当成数量"
    assert r["keyword"] == "螺丝"


# ── T2 规格分隔符变体 ─────────────────────────────────────────────

def test_t2_spec_separator_variants():
    for text in (
        "领8*25螺丝 500个",
        "领8x25螺丝 500个",
        "领8X25螺丝 500个",
        "领8×25螺丝 500个",
        "领8-25螺丝 500个",
        "领八乘二十五螺丝五百个",
        "领八叉二十五螺丝五百个",
        "领八杠二十五螺丝五百个",
    ):
        r = parse(text)
        assert r["spec_hint"] == "8*25", f"{text} 规格归一失败：{r['spec_hint']}"
        assert r["keyword"] == "螺丝", text
        assert r["quantity"] == 500.0, text


def test_t2b_spec_separator_normalization_directly():
    # 归一化后允许残留空格，比较时统一去空格（真实消费方走 _parse_voice_out_text，会再压缩空白）
    for raw in ("8乘25", "8x25", "8X25", "8×25", "8-25", "8 乘 25"):
        got = normalize(raw).replace(" ", "")
        assert got == "8*25", f"{raw} -> {got}"


# ── T3 中文数字 ──────────────────────────────────────────────────

def test_t3_chinese_numerals():
    for token, expect in (
        ("八", 8), ("十", 10), ("十五", 15), ("二十", 20), ("二十五", 25),
        ("八十五", 85), ("一百", 100), ("一百三十", 130), ("一千", 1000),
        ("两千", 2000), ("三千五百", 3500), ("零", 0),
    ):
        assert cn2int(token) == expect, f"{token} -> {cn2int(token)}"


def test_t3b_chinese_quantity_in_sentence():
    r = parse("领8*25螺丝一千个")
    assert r["quantity"] == 1000.0
    assert r["spec_hint"] == "8*25"

    r = parse("领8*25螺丝一百个")
    assert r["quantity"] == 100.0


# ── T4 数量抽取边界 ──────────────────────────────────────────────

def test_t4_quantity_requires_unit():
    # 裸数字（无规格、无量词）不得被当数量
    r = parse("领8*25螺丝 1000")
    assert r["quantity"] is None, "无「数字+量词」不应猜数量"
    assert r["spec_hint"] == "8*25"
    assert r["keyword"] == "螺丝"


def test_t4b_quantity_only_outside_spec():
    # 规格 25*8 里的数字不得被当数量
    r = parse("领25*8螺丝 10个")
    assert r["spec_hint"] == "25*8"
    assert r["quantity"] == 10.0
    assert r["keyword"] == "螺丝"


# ── T5 无数量 → None ────────────────────────────────────────────

def test_t5_no_quantity_returns_none():
    r = parse("领8*25螺丝")
    assert r["quantity"] is None
    assert r["unit"] == ""


# ── T6 动词与标记词剥离 ──────────────────────────────────────────

def test_t6_verb_and_marker_stripping():
    for text in (
        "领8*25螺丝 100个",
        "出库 8*25螺丝 100个",
        "拿8*25螺丝 100个",
        "领用8*25螺丝 100个",
    ):
        r = parse(text)
        assert r["keyword"] == "螺丝", f"{text} -> {r['keyword']!r}"
        assert r["quantity"] == 100.0

    # 标记词「规格/型号/的」不得混入关键词
    r = parse("领螺丝 1000个 规格8*25")
    assert r["keyword"] == "螺丝"
    assert r["spec_hint"] == "8*25"


# ── T7 同音纠错 ──────────────────────────────────────────────────

def test_t7_homophone_correction():
    assert parse("领罗丝8*25 200个")["keyword"] == "螺丝"
    assert parse("领零8*25螺丝 200个")["keyword"] == "螺丝"
    assert parse("领M8*25螺栓 200套")["keyword"] == "螺丝"


# ── T8 纯导航语不产生物料关键词 ──────────────────────────────────

def test_t8_navigation_only_yields_empty_keyword():
    for text in ("领料", "出库", "领用", "出库单"):
        r = parse(text)
        assert r["keyword"] == "", f"{text} 不应产生物料关键词：{r['keyword']!r}"
        assert r["quantity"] is None


def test_t8b_empty_input_is_safe():
    for text in ("", "   ", None):
        r = parse(text or "")
        assert r["keyword"] == ""
        assert r["quantity"] is None
        assert r["spec_hint"] == ""


# ── T9 规格字母前缀 ─────────────────────────────────────────────

def test_t9_spec_with_letter_prefix():
    r = parse("领M8*25螺栓 200套")
    assert r["spec_hint"] == "M8*25"
    assert r["quantity"] == 200.0
    assert r["unit"] == "套"


# ── T10 语序倒装 / 数量在前 ─────────────────────────────────────

def test_t10_word_order_tolerance():
    r = parse("拿十个8*25螺丝")
    assert r["quantity"] == 10.0
    assert r["spec_hint"] == "8*25"
    assert r["keyword"] == "螺丝"


def test_t10b_raw_fields_preserved():
    r = parse("领8*25螺丝 1000个")
    assert r["raw"] == "领8*25螺丝 1000个"
    assert r["normalized"]
