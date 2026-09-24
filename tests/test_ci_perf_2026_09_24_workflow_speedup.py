# -*- coding: utf-8 -*-
"""CI-PERF-2026-09-24 回归：CI 工作流耗时优化（>2 分钟的都要优化）。

## 背景

三个工作流实测耗时（2026-09-24）：
    Android APK Build      ~465s（7:45）— Build APK 325s + Lint 83s + 单测 36s 全串行
    WMS CI                 ~246s（4:06）— verify_*.py 178 文件串行 190s
    WMS AI Verification    ~178s（3:00）— verify_ai_all.py 58 脚本串行 86s

优化后预期：
    Android   三个 job 并行 + Gradle 缓存      → ~350s（受 build 单 job 限制）
    WMS CI    verify 切 4 片并行 + smoke 独立  → ~55s
    AI Verify 并发调度 + 拆静态/核心双 job      → ~35s

## 本测试锁死的不变量（缺一条优化就可能被无意回退）

1. **Android 拆并行但 `build` job 名不变** —— tests/test_bug_2026_09_04_003
   直接断言 `data["jobs"]["build"]["steps"]`，改名会让 keystore 回归静默失效；
2. **Android 三个目标仍在**：assembleRelease / lintRelease / testReleaseUnitTest
   一个都不能少（A12：只加强不削弱）；
3. **Android 加了 Gradle 缓存** —— 三个 job 各自 setup 的固有成本必须被缓存抵消；
4. **verify_ai_all.py 支持并发** —— 且默认并发度 >1（否则退回串行，优化白做）；
5. **verify_ai_all.py 保住 strict 语义** —— verify_ai_ledger_consistency.py 必须
   带 AI_LEDGER_ENFORCE=strict，否则会是**校验强度被削弱**（A12 红线）；
6. **run_verify_parallel.py 支持分片** —— 且分片不重不漏（每个 verify 文件恰好
   落进一片）；分片与并发同时生效才拿到跨 job 的加速；
7. **WMS CI 仍是 4 片 + smoke 独立 job**；
8. **verify.yml 的 AI core 清单覆盖原 workflow 的全部脚本**（不许漏项）。
"""
from __future__ import annotations

import ast
import glob
import os
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
WF_DIR = REPO / ".github" / "workflows"
ANDROID = WF_DIR / "android-build.yml"
CI = WF_DIR / "ci.yml"
VERIFY = WF_DIR / "verify.yml"
AI_ALL = REPO / "scripts" / "verify_ai_all.py"
RUN_PARALLEL = REPO / "scripts" / "run_verify_parallel.py"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def _load(p: Path) -> dict:
    return yaml.safe_load(_read(p))


# ------------------------------------------------- T1 Android 拆三个 job
def test_t1_android_has_three_parallel_jobs():
    """Android 必须拆成 build / lint / unit-test 三个互不依赖的 job。"""
    data = _load(ANDROID)
    jobs = data["jobs"]
    assert "build" in jobs, "缺少 build job（出包 + 发布 Release 资产）"
    assert "lint" in jobs, "缺少独立的 lint job（未拆出则 lint 仍占关键路径）"
    assert "unit-test" in jobs, "缺少独立的 unit-test job"
    for name, cfg in jobs.items():
        assert "needs" not in cfg, (
            f"{name} job 声明了 needs —— 拆并行就是为了互不依赖，"
            "加了 needs 又变回串行"
        )


def test_t1b_android_build_job_name_preserved_for_keystore_regression():
    """**关键**：job 名 `build` 不能改，否则 BUG-2026-09-04-003 回归静默失效。

    tests/test_bug_2026_09_04_003_fixed_debug_keystore.py::test_workflow_yaml_parses
    直接断言 `data["jobs"]["build"]["steps"]` 里有「Restore fixed debug keystore」。
    改名会让它 KeyError 或断言失败——即回归失效，故在此显式锁死这个耦合。
    """
    data = _load(ANDROID)
    assert "build" in data["jobs"], "job 名 build 被改掉了（keystore 回归会失效）"
    names = [s.get("name", "") for s in data["jobs"]["build"]["steps"]]
    assert "Restore fixed debug keystore (BUG-2026-09-04-003)" in names, (
        "build job 里丢了「Restore fixed debug keystore」步骤"
    )
    # 还原必须仍在构建之前（原测试的顺序断言依赖这一点）
    src = _read(ANDROID)
    build_job = src[src.index("  build:"):src.index("  lint:")]
    assert build_job.index("Restore fixed debug keystore") < build_job.index(
        "Build Release APK"
    ), "还原 keystore 必须发生在构建之前"


# ------------------------------------------- T2 Android 三个校验目标都在
def test_t2_android_three_targets_all_present():
    """assembleRelease / lintRelease / testReleaseUnitTest 一个都不能少。"""
    src = _read(ANDROID)
    gradle_cmds = [
        ln.strip() for ln in src.splitlines()
        if re.match(r"\s*run:\s*\./gradlew", ln)
    ]
    joined = " ".join(gradle_cmds)
    assert "assembleRelease" in joined, "丢了 assembleRelease（出包）"
    assert "lintRelease" in joined, "丢了 lintRelease（静态门禁）"
    assert "testReleaseUnitTest" in joined, "丢了 testReleaseUnitTest（单测门禁）"
    # A12：不许削弱成 debug 变体
    legacy = [c for c in gradle_cmds if re.search(
        r"assembleDebug|lintDebug|testDebugUnitTest", c)]
    assert not legacy, f"拆 job 时混入了 debug 变体命令：{legacy}"
    # -Pwms.sherpa 不得被重新加回（AI-MOB-APK-001）
    assert not [c for c in gradle_cmds if "-Pwms.sherpa=true" in c], \
        "gradlew 命令不得带 -Pwms.sherpa=true"


def test_t2b_android_gradle_cache_enabled():
    """三个 job 各自 setup 的固有成本必须靠 Gradle 缓存抵消。"""
    data = _load(ANDROID)
    for name in ("build", "lint", "unit-test"):
        uses = [s.get("uses", "") for s in data["jobs"][name]["steps"]]
        assert any("actions/cache" in u for u in uses), (
            f"{name} job 没有 Gradle 缓存 —— 拆并行后每 job 都要重下依赖，"
            "净收益会被 setup 开销吃掉"
        )
    src = _read(ANDROID)
    assert "~/.gradle/caches" in src, "Gradle 缓存未覆盖 ~/.gradle/caches"
    assert "~/.gradle/wrapper" in src, "Gradle 缓存未覆盖 ~/.gradle/wrapper"


# ------------------------------------------- T3 AI 校验脚本支持并发
def test_t3_verify_ai_all_uses_concurrency():
    """verify_ai_all.py 必须真并发（串行 for 循环 = 优化没做）。"""
    src = _read(AI_ALL)
    assert "ThreadPoolExecutor" in src, "verify_ai_all.py 未使用线程池并发"
    assert "as_completed" in src, "未用 as_completed 收集并发结果"
    # 默认并发度必须 >1
    m = re.search(r"def _resolve_workers.*?return min\((\d+), os\.cpu_count", src, re.S)
    assert m, "未找到 _resolve_workers 的默认并发度计算"
    assert int(m.group(1)) > 1, (
        f"默认并发度是 {m.group(1)} —— 等于串行，优化形同虚设"
    )


def test_t3b_verify_ai_all_keeps_isolated_temp_db():
    """并发后每个脚本仍必须用独立临时库（否则并发写同一文件 = 偶发假失败）。"""
    src = _read(AI_ALL)
    # TemporaryDirectory 必须在 run_script 内部（每脚本一次），而非提到模块级
    body = src[src.index("def run_script"):src.index("def _resolve_workers")]
    assert "TemporaryDirectory" in body, (
        "run_script 内没有独立临时目录了 —— 并发脚本会共享同一 SQLite 库"
    )


# ------------------------------- T4 strict 语义不得被削弱（A12 红线）
def test_t4_ledger_consistency_strict_preserved():
    """verify_ai_ledger_consistency.py 必须带 AI_LEDGER_ENFORCE=strict。

    原 verify.yml 是 `AI_LEDGER_ENFORCE=strict python3 ...` 直接跑；
    改由 verify_ai_all.py 统一调度后，若不带这个变量它会退回默认 gradual
    （宽松模式）—— 那是**校验强度被削弱**，属 AGENTS.md §六 A12 红线。
    """
    src = _read(AI_ALL)
    assert "SCRIPT_ENV_OVERRIDES" in src, "缺少脚本专属环境变量表"
    assert re.search(
        r"['\"]verify_ai_ledger_consistency\.py['\"]\s*:\s*\{\s*['\"]AI_LEDGER_ENFORCE['\"]\s*:\s*['\"]strict['\"]",
        src,
    ), "verify_ai_ledger_consistency.py 未声明 AI_LEDGER_ENFORCE=strict"
    # 必须是强制覆盖（update），不能是 setdefault（会被宽松默认值盖掉）
    body = src[src.index("def _verification_environment"):src.index("def run_script")]
    assert "environment.update(SCRIPT_ENV_OVERRIDES" in body, (
        "专属变量必须强制覆盖（update），用 setdefault 会被宽松默认值盖掉"
    )
    # 必须真的把脚本名传进去（否则查表永远查不到）
    assert "_verification_environment(database_path, name)" in src, (
        "调用 _verification_environment 时没传脚本名，专属环境变量永远不生效"
    )


# ------------------------------------------- T5 分片支持且不重不漏
def test_t5_run_verify_parallel_supports_sharding():
    """run_verify_parallel.py 必须支持 VERIFY_SHARDS / VERIFY_SHARD。"""
    src = _read(RUN_PARALLEL)
    assert "VERIFY_SHARDS" in src, "未支持 VERIFY_SHARDS 环境变量"
    assert "VERIFY_SHARD" in src, "未支持 VERIFY_SHARD 环境变量"
    assert re.search(r"i % shards == shard", src), (
        "分片判定未用取模 —— 取模能让每片均匀混入长短耗时的文件，"
        "连续区间切法会让某片全是慢文件"
    )
    assert "VERIFY_SHARD={shard} 越界" in src, "缺少 shard 越界防护"
    # 默认不分片，行为与历史一致
    assert re.search(r"VERIFY_SHARDS'\)\s*or\s*1", src), \
        "VERIFY_SHARDS 默认值必须是 1（不分片，保持历史行为）"


def test_t5b_sharding_is_complete_and_disjoint():
    """分片必须不重不漏：所有 verify 文件恰好落进一片（离线验算）。"""
    all_files = sorted(
        os.path.relpath(p, REPO)
        for p in glob.glob(str(REPO / "tests" / "verify_*.py"))
    )
    assert all_files, "没找到 tests/verify_*.py，本用例前提失效"
    shards = 4
    buckets = [
        [f for i, f in enumerate(all_files) if i % shards == s]
        for s in range(shards)
    ]
    flat = [f for b in buckets for f in b]
    assert sorted(flat) == all_files, "分片出现重复或遗漏"
    assert len(set(flat)) == len(all_files), "分片有重复文件"
    # 每片规模应大致均衡（取模分片的天然性质）
    sizes = [len(b) for b in buckets]
    assert max(sizes) - min(sizes) <= 1, f"分片规模不均衡：{sizes}"


# ------------------------------------------- T6 WMS CI 结构
def test_t6_ci_has_four_shards_and_independent_smoke():
    """WMS CI 必须是 4 个 verify 分片 + 独立 smoke job。"""
    data = _load(CI)
    jobs = data["jobs"]
    shard_jobs = [j for j in jobs if re.match(r"verify-shard-\d+$", j)]
    assert len(shard_jobs) == 4, f"verify 分片数应为 4，实际 {len(shard_jobs)}：{shard_jobs}"
    assert "smoke" in jobs, "smoke 必须是独立 job（拆出来才能与 verify 并行）"
    # 每个 shard 的 SHARDS/SHARD 必须自洽
    seen = set()
    for j in sorted(shard_jobs):
        for s in jobs[j]["steps"]:
            env = s.get("env", {})
            if "VERIFY_SHARD" in env:
                assert env["VERIFY_SHARDS"] == "4", f"{j} 的 VERIFY_SHARDS 不是 4"
                idx = int(env["VERIFY_SHARD"])
                assert 0 <= idx < 4, f"{j} 的 VERIFY_SHARD 越界：{idx}"
                seen.add(idx)
    assert seen == {0, 1, 2, 3}, f"分片序号未覆盖 0..3：{seen}"
    # smoke 不得依赖 verify 分片
    assert "needs" not in jobs["smoke"], "smoke 依赖了别的 job，就不能并行"


def test_t6b_ci_keeps_lint_and_unit_tests():
    """WMS CI 原有的静态门禁与主套件不能因优化而消失。"""
    data = _load(CI)
    jobs = data["jobs"]
    assert "lint-and-static" in jobs, "丢了 lint-and-static job"
    # CI-PERF-2026-09-24：unit-tests 拆成 3 片（unit-tests-shard-0/1/2），
    # 校验"主套件仍被完整跑"改为对分片求并集。
    shard_jobs = [j for j in jobs if re.match(r"unit-tests-shard-\d+$", j)]
    assert len(shard_jobs) == 3, \
        f"unit-tests 分片数应为 3，实际 {len(shard_jobs)}：{shard_jobs}"
    unit_cmds = " ".join(
        s.get("run", "") for j in shard_jobs for s in jobs[j]["steps"]
    )
    assert "run_tests_sharded.py" in unit_cmds, "分片未走 run_tests_sharded.py"
    # -n 4 --dist loadfile 的并发参数必须在分片脚本里保住
    script = _read(REPO / "scripts" / "run_tests_sharded.py")
    assert "-n" in script and "--dist" in script and "loadfile" in script, (
        "run_tests_sharded.py 丢了 -n / --dist loadfile 参数"
    )
    assert "-q" in script and "no:pylama" in script, \
        "run_tests_sharded.py 丢了原 unit-tests 的 -q -p no:pylama 参数"
    lint_cmds = " ".join(
        s.get("run", "") for s in jobs["lint-and-static"]["steps"] if s.get("run")
    )
    assert "lint_wms_rules.py" in lint_cmds, "丢了 lint_wms_rules 门禁"
    assert "verify_wms_bugs.py" in lint_cmds, "丢了 verify_wms_bugs 门禁"


def test_t6c_unit_test_shards_are_complete_and_disjoint():
    """unit-tests 分片必须不重不漏（每个 test_*.py 恰好落进一片）。"""
    all_files = sorted(
        os.path.relpath(p, REPO)
        for p in glob.glob(str(REPO / "tests" / "test_*.py"))
    )
    assert all_files, "没找到 tests/test_*.py，本用例前提失效"
    shards = 3
    buckets = [
        [f for i, f in enumerate(all_files) if i % shards == s]
        for s in range(shards)
    ]
    flat = [f for b in buckets for f in b]
    assert sorted(flat) == all_files, "分片出现重复或遗漏"
    sizes = [len(b) for b in buckets]
    assert max(sizes) - min(sizes) <= 1, f"分片规模不均衡：{sizes}"
    # 每个 shard job 的序号必须自洽
    data = _load(CI)
    seen = set()
    for j, cfg in data["jobs"].items():
        if not re.match(r"unit-tests-shard-\d+$", j):
            continue
        for s in cfg["steps"]:
            env = s.get("env", {})
            if "VERIFY_TEST_SHARD" in env:
                assert env["VERIFY_TEST_SHARDS"] == "3", f"{j} 的 SHARDS 不是 3"
                seen.add(int(env["VERIFY_TEST_SHARD"]))
    assert seen == {0, 1, 2}, f"分片序号未覆盖 0..2：{seen}"


# ------------------------------------------- T7 AI Verify 覆盖不缩水
def test_t7_ai_verify_covers_all_original_scripts():
    """verify.yml 的 AI core 清单必须覆盖原 workflow 调用的全部脚本。

    原 workflow 逐个 step 调用 30+ 个 verify_ai_*.py；改成 --level core 统一
    调度后，**任何一项都不能丢**（A12：只加强不削弱）。
    """
    orig = _read(VERIFY)
    # 当前 verify.yml 显式调用的脚本（static-checks job）
    static_scripts = set(re.findall(r"python3 scripts/(\S+\.py)", orig))

    # --level core 的清单：从源码里静态解析（含 _all_ai_scripts 的 glob 追加）
    src = _read(AI_ALL)
    core = set()
    for block_name in ("SMOKE_SCRIPTS = (", "CORE_SCRIPTS = SMOKE_SCRIPTS + ("):
        start = src.index(block_name)
        block = src[start:src.index(")", start)]
        core |= set(re.findall(r"['\"]([^'\"]+\.py)['\"]", block))
    # _all_ai_scripts 会把 scripts/verify_ai_*.py 全量补进 core
    core |= {
        os.path.basename(p)
        for p in glob.glob(str(REPO / "scripts" / "verify_ai_*.py"))
        if os.path.basename(p) != "verify_ai_all.py"
    }

    # 原 workflow（从 git 历史取）调用的脚本清单——用当前 HEAD 做基线
    import subprocess
    head_src = subprocess.run(
        ["git", "show", "HEAD:.github/workflows/verify.yml"],
        capture_output=True, text=True, cwd=str(REPO),
    ).stdout
    if head_src.strip():
        orig_scripts = set(re.findall(r"python3 scripts/(\S+\.py)", head_src))
        covered = core | static_scripts
        # verify_ai_all.py 是被调用者自身；不重复计入
        missing = orig_scripts - covered - {"verify_ai_all.py"}
        assert not missing, (
            f"以下脚本在原 verify.yml 里跑、优化后不再被任何 job 覆盖：{sorted(missing)}"
        )


def test_t7b_ai_verify_jobs_are_parallel():
    """verify.yml 至少要有 static-checks 与 ai-core 两个并行 job。"""
    data = _load(VERIFY)
    jobs = data["jobs"]
    assert "ai-core" in jobs, "缺少 ai-core job"
    assert "static-checks" in jobs, "缺少 static-checks job"
    for j, cfg in jobs.items():
        assert "needs" not in cfg, f"{j} 声明了 needs —— 拆并行后又变回串行"
    # ai-core 必须真跑 --level core
    core_cmds = " ".join(s.get("run", "") for s in jobs["ai-core"]["steps"])
    assert "--level core" in core_cmds, "ai-core job 没跑 --level core"
    # 并发度必须钉死（与 run_verify_parallel 同理由）
    envs = [s.get("env", {}) for s in jobs["ai-core"]["steps"]]
    assert any(e.get("VERIFY_AI_WORKERS") for e in envs), \
        "ai-core 未钉死 VERIFY_AI_WORKERS 并发度"


# ------------------------------------------- T8 三个 workflow 门禁不被破坏
def test_t8_gates_still_intact():
    """优化不得触碰门禁三要素：name 首行 / schedule / 三工作流齐全。"""
    for path, expected in (
        (ANDROID, "Android APK Build"),
        (CI, "WMS CI"),
        (VERIFY, "WMS AI Verification"),
    ):
        src = _read(path)
        head = src.splitlines()[0]
        assert head.startswith("name:"), f"{path.name} 首行不是 name"
        assert head.split(":", 1)[1].strip() == expected, f"{path.name} 的 name 被改了"
        assert re.search(r"^\s*schedule:", src, re.M), f"{path.name} 丢了 schedule"
        assert re.search(r"cron:\s*'\d+ \d+ \* \* \*'", src), \
            f"{path.name} 的 cron 不是每天一次"


def test_t8b_workflow_yaml_all_parse():
    """三个 workflow 必须都是合法 YAML（拆 job 最常见的就是缩进写错）。"""
    for path in (ANDROID, CI, VERIFY):
        data = yaml.safe_load(_read(path))
        assert isinstance(data, dict), f"{path.name} 解析结果不是 mapping"
        assert "jobs" in data, f"{path.name} 没有 jobs 段"
        assert data["jobs"], f"{path.name} 的 jobs 为空"
        for jname, cfg in data["jobs"].items():
            assert "steps" in cfg, f"{path.name} 的 {jname} job 没有 steps"
            assert cfg["steps"], f"{path.name} 的 {jname} job steps 为空"
            assert cfg.get("runs-on"), f"{path.name} 的 {jname} job 缺 runs-on"
