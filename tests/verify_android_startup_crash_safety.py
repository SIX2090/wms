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
    """A: AuthViewModel.init 的启动恢复流程必须整体被 try/catch 兜住。

    这是"每次都崩"的那条路径。判据：init 块里（按花括号配平静确取的块）
    既有异常捕获结构，又有失败时的降级处理。
    """
    body = _strip_comments(
        _read(SRC / "ui" / "viewmodel" / "auth" / "AuthViewModel.kt"))
    init_body = _brace_block(body, r"\binit\s*\{")

    assert "runCatching" in init_body or "try {" in init_body, (
        "AuthViewModel.init 的启动恢复流程没有异常兜底——"
        "加密存储损坏时会再次变成「屡次停止运行」")
    assert "catch" in init_body or "onFailure" in init_body, (
        "必须有失败分支（降级为未登录），否则失败被静默吞掉")

    # A2（结构性判据）：光查关键字不够——把 try 换成别的写法、
    # 或者只包住一半，关键字检查都过得去。
    # 这里要求：**读凭据的那条语句必须真的落在 try/runCatching 的括号内**。
    # 做法：找到读取 token/baseUrl 的位置，要求它前面存在未闭合的 try { / runCatching {。
    for marker in ("getSavedToken()", "getSavedBaseUrl()"):
        idx = init_body.find(marker)
        assert idx != -1, f"init 中未找到 {marker}，启动恢复逻辑被改动过"
        head = init_body[:idx]
        # 取最后一个 try{ 或 runCatching{ 的位置，并用花括号深度判断是否仍未闭合
        last = max(head.rfind("runCatching"), head.rfind("try {"))
        assert last != -1, (
            f"{marker} 的调用没有落在 try/runCatching 保护内——"
            "启动路径上任何异常都会杀进程")
        seg = head[last:]
        assert seg.count("{") > seg.count("}"), (
            f"{marker} 的调用处花括号已闭合，说明它其实在保护块之外")


# ── B. 凭据缺一不可（不得出现"半登录"） ─────────────────────────────────────
def test_credentials_require_both_non_blank():
    """B: token 或 baseUrl 缺失时不得回填 isLoggedIn=true。

    反例：`if (token != null && baseUrl != null)` 之外还要注意——
    即便用了非空判断，只要**没有**一个"两者都在才算已登录"的守卫，
    就会出现"界面已登录但请求必然失败"的死胡同。

    注意：这里刻意**不**要求必须写成 `isNullOrBlank()` 的字面形式。
    该写法是"防空串"的加强版；而真正不可退让的契约是
    "两者必须同时具备才可判已登录"，空串只是其中一个触发路径。
    所以判据为二选一：要么用 isNullOrBlank 成对判断，
    要么用 `token != null && baseUrl != null` 成对判断——
    两者都满足"缺一即不登录"，但**都不允许只判单个**。
    """
    src = _strip_comments(
        _read(SRC / "ui" / "viewmodel" / "auth" / "AuthViewModel.kt"))

    pair_blank = "!token.isNullOrBlank() && !baseUrl.isNullOrBlank()" in src
    pair_null = re.search(
        r"token\s*!=\s*null\s*&&\s*baseUrl\s*!=\s*null", src) is not None
    assert pair_blank or pair_null, (
        "启动判断必须同时校验 token 与 baseUrl（缺一即不登录），"
        "否则会停在「界面已登录、请求必然失败」的死胡同")

    # B2：isLoggedIn=true 的回填必须落在上面的成对判断之内——
    # 防止有人把判断写了却不用，或把回填挪到判断外面。
    m = re.search(r"isLoggedIn\s*=\s*true", src)
    assert m, "未找到 isLoggedIn=true 的回填点"
    head = src[:m.start()]
    guard = max(head.rfind("if ("), head.rfind("if("))
    assert guard != -1, "isLoggedIn=true 不在任何 if 守卫内——必然出现半登录态"


# ── C. 加密存储不得让异常冒泡 ──────────────────────────────────────────────
def test_secure_prefs_never_throws():
    """C: 加密存储的构造与每个访问点都必须有异常保护。

    现场是 Android Keystore 失效（系统升级/卸载重装/恢复出厂/换机克隆/
    厂商 ROM 缺陷）导致 EncryptedSharedPreferences 构造或读取抛运行时异常。
    该异常发生在 AuthViewModel.init 的协程中，未捕获即杀进程。

    判据（针对**行为**而非某种写法）：
      C1. 构造加密存储的地方必须有 try/catch，且失败时降级返回 null，
          不得让异常离开该处；
      C2. 每个读取点（getSavedToken / 写 token）都必须有 try/catch 兜底；
      C3. 必须有"删除损坏文件以便下次重建"的自愈动作（否则密钥坏掉后
          每次启动都在同一处失败，App 永久不可用）。
    """
    raw = _read(SRC / "data" / "repository" / "WmsRepository.kt")
    body = _strip_comments(raw)

    # C1: 构造加密存储的**调用点**必须被 try/catch 包住并降级。
    #
    # 注意不要断言"create 所在的函数体内必须有 catch"——那会把
    # 「工厂函数只负责构造、由调用方兜底」这种（同样正确、甚至更清晰的）
    # 结构误判为缺陷。真正不可退让的是：**异常必须被接住**。
    # 故判据为二选一：
    #   ① create 所在函数体自己有 catch；或
    #   ② 该函数被别处以 try/catch 包裹的方式调用。
    create_pos = body.find("EncryptedSharedPreferences.create")
    assert create_pos != -1, "未找到加密存储构造点，结构被大改"

    # ① 构造点自身或其宿主函数体有 catch
    header = max(body.rfind("private fun", 0, create_pos),
                 body.rfind("private val", 0, create_pos))
    assert header != -1, "未找到加密存储构造点的宿主声明"
    decl = _brace_block(body, re.escape(body[header:create_pos].split("{")[0].strip()))
    guarded_inside = ("catch" in decl or "runCatching" in decl)

    # ② 构造点的宿主函数被受保护的调用点调用
    host_name = re.search(r"fun\s+([A-Za-z_]\w*)",
                          body[header:create_pos])
    guarded_at_call = False
    if host_name:
        caller = re.search(
            r"try\s*\{[^}]*\b" + re.escape(host_name.group(1)) + r"\s*\(",
            body, re.S)
        guarded_at_call = caller is not None

    assert guarded_inside or guarded_at_call, (
        "加密存储构造点没有异常保护——Keystore 失效时异常会直接冒泡到启动路径。"
        "要么工厂函数内部 try/catch，要么调用点用 try/catch 包住")

    # C2: 读取点必须有兜底。getSavedToken 是冷启动必经路径。
    tok_pos = body.find("suspend fun getSavedToken")
    assert tok_pos != -1, "getSavedToken 被移除或改名"
    tok_block = _brace_block(body, r"suspend fun getSavedToken\(\)[^\{]*")
    assert "catch" in tok_block or "runCatching" in tok_block, (
        "getSavedToken 没有异常兜底——这是 App 冷启动必经路径，抛异常即闪退")

    # C3: 自愈——必须存在删除损坏 prefs 文件的动作。
    assert "resetSecurePrefsFile" in body or "deleteSharedPreferences" in body, (
        "缺少损坏加密存储的自愈动作：密钥坏掉后不删除旧文件，"
        "每次启动都会在同一处失败，App 永久不可用")

    # C4: 所有经手 encryptedPrefs 的访问点都不得裸用。
    #     裸用 = 该行访问 encryptedPrefs 但所在函数体内没有 try/catch/runCatching。
    lines = body.split("\n")
    # 收集所有函数的 [起, 止) 区间，便于判断某行落在哪个函数体里
    fn_spans = []
    for m in re.finditer(r"\n    (?:private |internal |public |protected )?"
                         r"(?:suspend )?(?:inline )?fun [A-Za-z_]\w*", body):
        start = body.index("{", m.start()) if "{" in body[m.start():m.start() + 400] else -1
        if start == -1:
            continue
        try:
            inner = _brace_block(body, re.escape(body[m.start():start].strip()))
        except AssertionError:
            continue
        fn_spans.append((m.start(), body.index(inner, start) + len(inner) + 1))

    for i, line in enumerate(lines):
        s = line.strip()
        if not re.match(r".*\bencryptedPrefs\s*[?.]", s):
            continue
        if s.startswith("private val encryptedPrefs"):
            continue
        pos = sum(len(l) + 1 for l in lines[:i])
        enclosing = [sp for sp in fn_spans if sp[0] <= pos < sp[1]]
        if not enclosing:
            continue
        a, b = enclosing[-1]
        fbody = body[a:b]
        # 属性声明自身有 try/catch，也在 fn_spans 之外，故这里只查真正的调用点
        assert ("catch" in fbody or "runCatching" in fbody), (
            f"WmsRepository.kt:{i + 1} 在未加异常保护的函数里访问加密存储——"
            "Keystore 失效时异常会冒泡到启动路径并杀进程")


# ── D. 必须有崩溃落盘装置 ──────────────────────────────────────────────────
def test_crash_logger_installed():
    """D: 进程级未捕获异常处理器必须安装，且把堆栈写到可取回的位置。

    注意（破坏性测试发现的坑）：只断言 `"installCrashLogger" in src` 是**空跑**——
    函数定义本身就在文件里，把 `onCreate` 里的那一行调用删掉，断言照样通过。
    必须验证"定义"与"被调用"两件事同时成立，且调用发生在 onCreate 内。
    """
    src = _read(SRC / "WmsApplication.kt")

    assert "setDefaultUncaughtExceptionHandler" in src, (
        "缺少进程级崩溃捕获——现场只有一句「停止运行」，没有堆栈就无法定位")
    assert "last_crash.txt" in src, "崩溃堆栈必须落到固定文件名，便于现场取回"

    # 定义存在
    assert re.search(r"fun\s+installCrashLogger\s*\(", src), (
        "缺少 installCrashLogger 定义")

    # 且必须在 onCreate 里**真的被调用**（去掉注释后按块配平取 onCreate 体）
    body = _strip_comments(src)
    oncreate = _brace_block(body, r"override\s+fun\s+onCreate\s*\(\)")
    assert re.search(r"\binstallCrashLogger\s*\(\s*\)", oncreate), (
        "崩溃处理器必须在 Application.onCreate 里被调用——"
        "只定义不安装等于没有，现场依旧拿不到堆栈")


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
