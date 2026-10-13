# -*- coding: utf-8 -*-
"""BUG 台账读取helper（F4.4 台账拆分后的兼容层）。

## 为什么需要这个模块

F4.4（`9c5e5af7`）把 923KB 的 `WMS_BUG_BASELINE.md` 拆成：

    WMS_BUG_BASELINE.md          主文件——只保留活头部（规模统计、状态汇总、分片索引）
    docs/ledger/bugs/*.md        22 个按月分片，存放全部条目详情小节
    docs/ledger/bugs/INDEX.md    ID → 分片路径 的统一索引

拆分之后，**新登记的 BUG 条目一律落在分片里**（主文件不再承载详情小节）。
而 BUG 回归守护测试的「A13 台账登记」断言沿用 `content = _read(BASELINE)`
再 `assert "BUG-XXXX" in content` 的旧写法——只能看到主文件，于是对分片里的
条目误报「未登记进 WMS_BUG_BASELINE.md」。

实测受影响的 4 个文件（CI WMS CI #1533 上 verify-shard-1/2/3 各红一片）：

    tests/verify_bug_2026_10_04_001_scan_viewmodel_factory.py
    tests/verify_bug_2026_10_04_002_home_header_fab_position.py
    tests/verify_bug_2026_10_04_003_hero_selector_contrast.py
    tests/test_bug_2026_10_05_002_embedded_duplicate_fab.py

## 本模块提供什么

    from tests.ledger_reader import read_bug_baseline, find_bug_section

    content = read_bug_baseline()                  # 主文件 + 全部 bugs 分片（按 INDEX 顺序）
    m = find_bug_section(content, "BUG-2026-10-04-001")   # 取「## …BUG-ID…」到下一个 ## 为止

刻意**不**改成 `query_ledger.py` 子进程：那会让每个守护测试多付一次进程启动
（约 1.8s import 开销），而这些断言是 CI 分片里的主要负载。直接读文件仍是一次
IO，但把「读哪几个文件」的决策集中在一处。

## 为什么不改断言本身

`assert "BUG-ID" in content` 这个写法本身是对的（A13 只要求条目**存在**
且带「生效确认」字段）；错的是 content 的来源。改来源而不是改断言，可以让
修复对所有测试零侵入，也不必在 4 个文件里各写一遍分片 glob 逻辑。

## 边界

* 只覆盖 BUG 台账（`docs/ledger/bugs/`）。AI 台账 `docs/ledger/ai/` 的消费者是
  `verify_ai_ledger_consistency.py`，它在 F4.4 里已单独适配，不走本模块。
* 分片顺序取 `INDEX.md` 的登记顺序，与 `query_ledger.py` 一致——保证「读到的
  条目顺序」在不同入口下相同，跨文件的顺序型断言（如状态分布）不会因此漂移。
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE = REPO_ROOT / "WMS_BUG_BASELINE.md"
BUG_SHARDS_DIR = REPO_ROOT / "docs" / "ledger" / "bugs"
INDEX = BUG_SHARDS_DIR / "INDEX.md"

# 拼接分隔符里显式带上分片名，便于失败信息反查条目落在哪个文件。


def _shard_paths() -> list[Path]:
    """按 INDEX.md 的登记顺序返回分片路径；INDEX 缺失时退化为按文件名排序。

    排序保证「同一份台账在多次运行/不同入口下读到的顺序一致」——跨文件的
    顺序敏感断言（如 monthly_bug_review 的状态分布回归锁）依赖这一点。
    """
    if not INDEX.exists():
        return sorted(BUG_SHARDS_DIR.glob("*.md"))
    ordered: list[Path] = []
    seen: set[str] = set()
    for line in INDEX.read_text(encoding="utf-8").splitlines():
        m = re.search(r"\(([^()]*\.md)\)", line)
        if not m:
            continue
        name = m.group(1).strip()
        if not name or name == "INDEX.md" or name in seen:
            continue
        p = BUG_SHARDS_DIR / name
        if p.exists():
            ordered.append(p)
            seen.add(name)
    # INDEX 里没登记的既有分片也要读到（防止新增分片漏登记导致静默漏读）
    for p in sorted(BUG_SHARDS_DIR.glob("*.md")):
        if p.name != "INDEX.md" and p.name not in seen:
            ordered.append(p)
    return ordered


def read_bug_baseline() -> str:
    """返回 BUG 台账全文：主文件（活头部） + 全部 bugs 分片，按 INDEX 顺序拼接。

    主文件在最前——它含规模统计与状态汇总，部分消费者按「头部在前」解析；
    分片在后提供条目详情。中间用显式分隔符连接，避免上一个文件末尾与下一个
    文件首行被 `re.S` 贪婪匹配误当成同一小节。
    """
    assert BASELINE.exists(), f"BUG 台账主文件不存在：{BASELINE}"
    parts = [BASELINE.read_text(encoding="utf-8")]
    for shard in _shard_paths():
        parts.append(f"\n<!-- ledger-shard: {shard.name} -->\n")
        parts.append(shard.read_text(encoding="utf-8"))
    return "".join(parts)


def find_bug_section(content: str, bug_id: str) -> re.Match[str] | None:
    """在拼接全文中定位 bug_id 的小节，返回覆盖该小节的 match（不含下一个 ``##``）。

    小节起点 = 含该 BUG-ID 的 ``##`` 标题行；终点 = 下一个 ``##`` 行或文末。
    关键在用**惰性** ``.*?`` 配 ``(?=\\n##)`` 终止符，而不是 ``\\Z`` 贪婪匹配——
    后者会把该小节之后的所有内容一起吞进来，导致「相邻小节互相吞并」。
    """
    return re.search(
        r"^##[^\n]*\b" + re.escape(bug_id) + r"\b[^\n]*\n"  # 起点：含该 ID 的 ## 标题行
        r".*?"                                        # 惰性正文
        r"(?=\n##|\Z)",                               # 终点：下一个 ## 行或文末
        content,
        re.S | re.M,
    )


def bug_section_text(content: str, bug_id: str) -> str:
    """返回 bug_id 小节的纯文本；未找到时抛 AssertionError（附带排查建议）。"""
    m = find_bug_section(content, bug_id)
    assert m, (
        f"无法定位 {bug_id} 条目段落。"
        f"请确认该 BUG 已登记进 WMS_BUG_BASELINE.md 或 docs/ledger/bugs/ 的某个分片"
        f"（可用 python scripts/query_ledger.py --task {bug_id} 定位）"
    )
    return m.group(0)