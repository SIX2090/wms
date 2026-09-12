# -*- coding: utf-8 -*-
"""回归：Kotlin 侧「注解与声明被注释/新代码插开」的静态门禁。

根因（同一根因两次发生，R6：同类消费点必须一次修干净）：

1. BUG-A（2026-09-13，Android APK Build #437 红）：ScanScreens.kt 里新写的
   StockListSortFilterBar 被插在 StockListRow 的 KDoc 与 @Composable 之间，
   于是那个 @Composable 落到了新函数头上，StockListRow 变成普通函数却仍调用
   Card()/Text()——Compose 编译器报
   "Functions which invoke @Composable must be marked with the @Composable
   annotation"，assembleRelease 直接失败。
2. BUG-B（同日更早，本地已捕获）：WmsApiService.kt 的 KDoc 写在既有注释的
   `*/` 之后，孤立出几行 KDoc 正文，报 "expecting member declaration"。

两者都是「往注释块中间插代码」这一个动作的产物。危害在于**本地看不见**：
沙箱内没有 Compose 编译器插件与 Compose 库，kotlinc 只报 unresolved
reference，Compose 的注解检查不会执行；基线对比编译对此 0 新增错误。只有 CI
的 assembleRelease 会红，而 Android CI 日志在本机取不到，一次红灯要 12 分钟
才暴露。故把这类形状做成静态检查，在本地与 CI 第 12 步（本文件 pytest 风格，
被 verify_*.py 循环纳入）1 秒内拦住。

检测三种形状（只做形状判断，不解析 Kotlin 语法，避免误报）：
A. 块注释正文行（`*`/`*/` 开头）不在任何块注释内部 → 注释被写到了块外。
B. 注解行紧跟着块注释起始 → 注解链被文档注释打断（KDoc 必须在注解之前）。
C. 一个 KDoc 之后（跳过空行与注解）又是另一个 KDoc → 前一个 KDoc 没有归属
   的声明，即有人把新代码插在了「KDoc + 注解」与「声明」之间。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KT_ROOT = ROOT / "app" / "android-native-wms"

FUN_DECL = re.compile(r"\bfun\s")

# 整行只写一个注解：`@Composable`、`@SerializedName("x")` 等；
# 注解与声明写在同一行（`@Transient val x` / `@GET("a") suspend fun b()`）不算。
PURE_ANNOTATION = re.compile(r"^@[A-Za-z_][\w.]*(\s*\(.*\))?\s*(//.*)?$")


def pure_annotation_line(s):
    return bool(PURE_ANNOTATION.match(s))


def _kotlin_files():
    if not KT_ROOT.exists():
        return []
    return [
        p
        for p in KT_ROOT.rglob("*.kt")
        if "/build/" not in str(p) and ".gradle" not in str(p)
    ]


def _block_mask(lines):
    """标记每一行是否处于块注释内部（含起始行与结束行）。"""
    mask = [False] * len(lines)
    in_block = False
    for i, raw in enumerate(lines):
        s = raw.strip()
        if in_block:
            mask[i] = True
            if "*/" in s:
                in_block = False
            continue
        if s.startswith("/*"):
            mask[i] = True
            if "*/" not in s:
                in_block = True
    return mask


def _skip_noise(lines, start):
    """从 start 起跳过空行、// 行注释、块注释、注解，返回首个有效行号。"""
    i = start
    in_block = False
    while i < len(lines):
        s = lines[i].strip()
        if in_block:
            if "*/" in s:
                in_block = False
            i += 1
            continue
        if s.startswith("/*"):
            if "*/" not in s:
                in_block = True
            i += 1
            continue
        if not s or s.startswith("//") or s.startswith("*") or s.startswith("@"):
            i += 1
            continue
        return i
    return -1


def _next_visible(lines, start, mask):
    """下一个非空的、且不在块注释内的行号（注解行也算可见）。"""
    i = start
    while i < len(lines):
        if lines[i].strip() and not mask[i]:
            return i
        i += 1
    return -1


def _collect_violations(path):
    """返回 [(行号, 说明)]。"""
    lines = path.read_text(encoding="utf-8").split("\n")
    mask = _block_mask(lines)
    out = []

    # A. 孤立的块注释正文行
    for i, raw in enumerate(lines):
        if mask[i]:
            continue
        s = raw.strip()
        if s.startswith("*/") or (s.startswith("*") and not s.startswith("/*")):
            out.append((i + 1, f"块注释正文行不在注释块内：{s[:50]}"))

    # B. 注解被紧随的块注释打断（仅针对「整行只有一个注解」的情况；
    #    `@SerializedName("x") val y = ...` 这类注解与声明同一行的合法写法不算）
    for i, raw in enumerate(lines):
        if mask[i]:
            continue
        s = raw.strip()
        if not s.startswith("@"):
            continue
        if not pure_annotation_line(s):
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].strip().startswith("/*"):
            out.append(
                (j + 1, f"注解 {s[:24]} 被紧随的块注释打断（KDoc 应写在注解之前）")
            )

    # C. KDoc 之后又是 KDoc：前一个 KDoc 没有归属的声明
    for i, raw in enumerate(lines):
        if not raw.strip().startswith("/**"):
            continue
        j = _next_visible(lines, i + 1, mask)
        while 0 <= j < len(lines) and lines[j].strip().startswith("@"):
            j = _next_visible(lines, j + 1, mask)
        if 0 <= j < len(lines) and lines[j].strip().startswith("/**"):
            out.append((j + 1, "前一个 KDoc 未绑定声明（新代码插在了 KDoc/注解与声明之间）"))

    return out


def test_android_annotation_binding():
    files = _kotlin_files()
    assert files, f"未找到 Kotlin 源文件：{KT_ROOT}"

    problems = []
    for p in files:
        for lineno, msg in _collect_violations(p):
            problems.append(f"{p.relative_to(ROOT)}:{lineno} {msg}")

    assert not problems, "Kotlin 注解/注释绑定异常:\n  " + "\n  ".join(problems)


if __name__ == "__main__":
    test_android_annotation_binding()
    print(f"OK：{len(_kotlin_files())} 个 Kotlin 文件，注解与注释绑定检查通过")
