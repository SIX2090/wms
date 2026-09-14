#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BUG-2026-09-13-001 回归守护：启动路径不得因加密存储损坏而崩溃。

现场现象：「WMS扫码屡次停止运行」——系统弹窗只说"停止运行"，没有堆栈。
根因是代码里两条真实缺陷，且**每次启动都会命中的确定性崩溃**：

1. **`encryptedPrefs` 是裸的 by lazy**（WmsRepository）。底层
   Android Keystore 在密钥损坏/丢失时会抛 KeyStoreException /
   InvalidAlgorithmParameterException / AEADBadTagException / IOException
   （系统升级、卸载重装、恢复出厂、换机克隆等场景都会命中）。
   而唯一的启动路径 AuthViewModel.init 在协程里调 getSavedToken()，
   异常无人接住 → 进程被杀 → 下次启动在同一行再崩 → **无限重启**。
   三个使用点里当时只有 logout 有 try/catch，启动路径和登录路径都是裸的。

2. **凭据半残**：token 存 EncryptedSharedPreferences、baseUrl 存 DataStore，
   两者损坏概率不同，而启动判断写的是 `token != null && baseUrl != null`
   （非空判断，空串 '' 也会通过），可能停在"界面已登录但请求必然失败"的死胡同。

本测试守的契约（都是"崩溃/不可用"级的强约束，不是风格偏好）：
A. 启动路径（AuthViewModel.init）整体有 runCatching 兜底；
B. 凭据必须成对且非空白：缺任一个都不得回填 isLoggedIn=true；
C. 加密存储的每个使用点都不得让异常冒泡（无裸 by lazy + 每个访问点有保护）；
D. 有进程级未捕获异常处理器把堆栈落盘（下次崩溃可直接定位，不再靠猜）；
E. 崩溃处理器不得吞掉异常（不能把崩溃变成静默失败）。
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SRC = (REPO / "app" / "android-native-wms" / "app" / "src" / "main"
       / "java" / "com" / "factory" / "wms")

FAILS = []


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _strip_comments(src: str) -> str:
    """去掉块/行注释（沿用仓库约定：块注释起点须顶格或空白后出现）。"""
    src = re.sub(r"(?<!\S)/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src


def _brace_block(body: str, header_re: str) -> str:
    """按花括号配平提取一个代码块（从匹配到的 '{' 起），返回块内文本。

    不能图省事用 `re.search(r"init\\s*\\{(.*?)\\n    \\}", ..., re.S)`——
    非贪婪匹配会在**后面某个**以 4 空格缩进的 `}` 处就停，把后续成员也吞进来。
    这正是本文件第一版测试②变成空跑的原因（块长 1797 字符，连
    unauthorizedEvents.collect 都包含进来，于是"去掉 runCatching"检测不出来）。
    """
    m = re.search(header_re, body)
    assert m, f"未能定位代码块：{header_re}"
    start = body.index("{", m.start())
    depth = 0
    for i in range(start, len(body)):
        if body[i] == "{":
            depth += 1
        elif body[i] == "}":
            depth -= 1
            if depth == 0:
                return body[start + 1:i]
    raise AssertionError(f"代码块花括号不配平：{header_re}")


# ── A. 启动路径整体兜底 ────────────────────────────────────────────────────
def test_auth_init_wrapped_in_runcatch():
    """A: AuthViewModel.init 的启动恢复流程必须整体被 runCatching 包住。

    这是"每次都崩"的那条路径。判据：init 块里（按花括号配平静确取的块）
    既有 runCatching，又有 onFailure 处理。
    """
    body = _strip_comments(
        _read(SRC / "ui" / "viewmodel" / "auth" / "AuthViewModel.kt"))
    init_body = _brace_block(body, r"\binit\s*\{")

    assert "runCatching" in init_body, (
        "AuthViewModel.init 的启动恢复流程没有 runCatching 兜底——"
        "加密存储损坏时会再次变成「屡次停止运行」")
    assert "onFailure" in init_body, (
        "runCatching 后必须处理失败分支（降级为未登录），否则失败被静默吞掉")

    # A2（结构性判据）：光查关键字不够——把 runCatching 换成别的写法、
    # 或者只包住一半、或者 onFailure 挂在别处的 runCatching 上，关键字检查都过得去。
    # 这里要求：**读凭据的那条语句必须真的落在 runCatching/try 的括号内**。
    # 做法：找到读取 token/baseUrl 的位置，要求它前面存在未闭合的 runCatching { 或 try {。
    for marker in ("getSavedToken()", "getSavedBaseUrl()"):
        idx = init_body.find(marker)
        assert idx != -1, f"init 中未找到 {marker}，启动恢复逻辑被改动过"
        head = init_body[:idx]
        # 取最后一个 try{ 或 runCatching{ 的位置，并用花括号深度判断是否仍未闭合
        last = max(head.rfind("runCatching"), head.rfind("try {"))
        assert last != -1, (
            f"{marker} 的调用没有落在 runCatching/try 保护内——"
            "启动路径上任何异常都会杀进程")
        seg = head[last:]
        assert seg.count("{") > seg.count("}"), (
            f"{marker} 的调用处花括号已闭合，说明它其实在保护块之外")


# ── B. 凭据必须成对且非空白 ────────────────────────────────────────────────
def test_credentials_require_both_non_blank():
    """B: 只有 token 与 baseUrl 同时非空白才可判为已登录。

    反例（修复前的写法）：`if (token != null && baseUrl != null)`——
    token='' 或 baseUrl='' 都会通过，产生"半个登录态"。
    """
    src = _strip_comments(
        _read(SRC / "ui" / "viewmodel" / "auth" / "AuthViewModel.kt"))

    assert "!token.isNullOrBlank() && !baseUrl.isNullOrBlank()" in src, (
        "启动判断必须用 isNullOrBlank（空串也算缺失），"
        "否则会停在「界面已登录、请求必然失败」的死胡同")


# ── C. 加密存储不得让异常冒泡 ──────────────────────────────────────────────
def test_secure_prefs_never_throws():
    """C: 加密存储的构造与每个访问点都必须有异常保护。"""
    raw = _read(SRC / "data" / "repository" / "WmsRepository.kt")
    body = _strip_comments(raw)

    # C1: 不允许任何形式的「加密存储构造放在 lazy 里」。
    #     不要写成"lazy { 里必须紧跟 create"——那样只拦得住最直白的写法，
    #     把构造抽成 buildEncryptedPrefs() 再 lazy 包一层就绕过去了
    #     （本文件第一版正是如此，破坏性测试立刻暴露它没拦住）。
    #     判据改为：出现 `lazy` 的行，其所属语句内不得出现加密存储构造。
    for i, line in enumerate(body.split("\n")):
        if "lazy" not in line:
            continue
        # 同一语句可能跨行，取 lazy 前后 3 行的窗口
        window = "\n".join(body.split("\n")[max(0, i - 1):i + 4])
        assert "EncryptedSharedPreferences.create" not in window \
            and "buildEncryptedPrefs" not in window, (
            f"WmsRepository.kt:{i + 1} 处用 lazy 构造加密存储："
            "Keystore 异常会越过 lazy 直接冒泡到启动路径。"
            "必须走带自愈重建的 encryptedPrefsOrNull()")

    # C2: 必须存在带自愈逻辑的工厂（两次尝试 → 重建 → 降级）
    assert "encryptedPrefsOrNull" in body, "缺少带异常保护的加密存储访问入口"
    assert "buildEncryptedPrefs" in body, "缺少可复用的加密存储构造点"
    assert "deleteSharedPreferences" in body, (
        "重建时必须先删除旧 prefs 文件，否则用已损坏的 key 去解新文件照样失败")

    # C3: 每个**调用点**都不得裸调。
    #     排除两类非调用点：
    #     ① 工厂函数自身的实现体（内部本来就该调 create，异常在那里被吃掉）；
    #     ② 函数声明行本身（"private fun encryptedPrefsOrNull()" 里的名字匹配）。
    factory_spans = []
    for fname in ("buildEncryptedPrefs", "encryptedPrefsOrNull"):
        start = body.find(f"private fun {fname}")
        if start == -1:
            continue
        nxt = re.search(r"\n    (?:@|private|fun|val|var|suspend)",
                        body[start + 1:])
        end = start + 1 + (nxt.start() if nxt else len(body) - start - 1)
        factory_spans.append((start, end))

    def in_factory(pos: int) -> bool:
        return any(a <= pos < b for a, b in factory_spans)

    lines = body.split("\n")
    offset = 0
    for i, line in enumerate(lines):
        pos = offset
        offset += len(line) + 1
        if "encryptedPrefsOrNull()" not in line:
            continue
        if in_factory(pos):
            continue
        # 声明行不是调用点
        if re.match(r"\s*(private|internal|public|protected)?\s*fun\s", line):
            continue
        window = "\n".join(lines[max(0, i - 8):i + 1])
        guarded = ("runCatching" in window) or ("try {" in window)
        assert guarded, (
            f"WmsRepository.kt:{i + 1} 处访问加密存储未加异常保护，"
            "启动路径上会崩")


# ── D. 必须有崩溃落盘装置 ──────────────────────────────────────────────────
def test_crash_logger_installed():
    """D: 进程级未捕获异常处理器必须安装，且把堆栈写到可取回的位置。"""
    src = _read(SRC / "WmsApplication.kt")

    assert "setDefaultUncaughtExceptionHandler" in src, (
        "缺少进程级崩溃捕获——现场只有一句「停止运行」，没有堆栈就无法定位")
    assert "last_crash.txt" in src, "崩溃堆栈必须落到固定文件名，便于现场取回"
    assert "onCreate" in src and "installCrashLogger" in src, (
        "崩溃处理器必须在 Application.onCreate 里安装，否则可能来不及生效")


# ── E. 崩溃处理器不得吞掉崩溃 ──────────────────────────────────────────────
def test_crash_logger_does_not_swallow():
    """E: 崩溃必须继续交给系统默认处理。

    吞掉异常会把"崩溃"变成"静默的数据错误"——用户以为提交成功了，
    实际什么都没发生。那比崩溃更危险，所以这里必须守住。
    """
    src = _strip_comments(_read(SRC / "WmsApplication.kt"))

    assert "defaultHandler?.uncaughtException" in src, (
        "崩溃处理器必须把异常交回系统默认处理；吞掉崩溃会掩盖缺陷、"
        "并把崩溃问题变成静默的数据错误")


def test_no_suspend_call_in_non_suspend_lambda():
    """F: onFailure/onSuccess 这类非 suspend lambda 里不得调 suspend 函数。

    真实踩坑（本次修复过程中）：在 `runCatching{...}.onFailure { e -> ... }` 里
    写了 `repository.clearCredentials()`，而 clearCredentials 是 suspend。
    `Result.onFailure` 的 lambda 不是 suspend 上下文 → Kotlin 编译失败
    「suspend function should be called only from a coroutine」→ APK 构建红。

    更麻烦的是**本地查不出来**：沙箱缺协程库，这个错误只表现为一行
    unresolved reference（"error: suspend function 'x' should be called..."），
    与 Compose/Android 库缺失造成的几百行噪音混在一起，很容易被当成噪音放过。
    所以用静态检查把这条约束钉死。

    判据：WmsRepository 中所有 suspend 函数名，不得出现在
    onFailure/onSuccess 的 lambda 体内（两者都不是 suspend 上下文）。
    """
    repo_body = _strip_comments(_read(SRC / "data" / "repository" / "WmsRepository.kt"))
    suspend_fns = set(re.findall(r"\bsuspend\s+fun\s+([A-Za-z_]\w*)", repo_body))
    assert suspend_fns, "未能解析出 WmsRepository 的 suspend 函数列表"

    offenders = []
    for kt in SRC.rglob("*.kt"):
        body = _strip_comments(_read(kt))
        # 逐行找 onFailure{ / onSuccess{ 的lambda 体（配对花括号）
        for m in re.finditer(r"\b(onFailure|onSuccess)\s*\{", body):
            try:
                lam = _brace_block(body, re.escape(m.group(0).rstrip("{").strip()) + r"\s*\{")
            except AssertionError:
                continue
            for fn in suspend_fns:
                if re.search(rf"\.{fn}\s*\(", lam):
                    offenders.append(f"{kt.name}: {m.group(1)} lambda 内调用了 "
                                     f"suspend 函数 {fn}()")

    assert not offenders, (
        "非 suspend lambda 内调用 suspend 函数会导致编译失败：\n  "
        + "\n  ".join(sorted(set(offenders))))


if __name__ == "__main__":
    import sys
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
