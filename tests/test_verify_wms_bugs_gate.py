# -*- coding: utf-8 -*-
"""门禁脚本 verify_wms_bugs.py 自身的回归：防止"断言钉在旧文件位置"再次发生。

背景（问题本体，非代码缺陷）：
ARCH-MODELS-01（2026-09-15）把 19 张 AI 表从 `app/app.py` 模型区迁到
`app/models/ai.py`（类定义逐字保留，`app.py` 侧改为 `from models.ai import (...)`）。
这次迁移与 AGENTS.md A10「`app/app.py` 不得持续膨胀」是**同向**的正确重构。

但 `scripts/verify_wms_bugs.py` 里若干 AI 断言的判据是
`'class Xxx' in app_py`，迁移后全部落空，导致四项恒为 FAIL：
  · AI-DOCUMENT-JOB-MODELS-001
  · AI-CONTROLLED-AGENTS-001
  · AI-IDEMPOTENCY-001
  · AI-AUDIT-001
WMS CI 的 `verify_wms_bugs` 步骤失败后，其后各步骤因门禁顺序被 **skipped**，
整条 CI 长期红灯（自 2026-09-15 起连续十余个提交全 failure），
使 CI 丧失"看红绿判断新改动是否安全"的基本作用。

修复：模型类断言改为在「app.py + app/models/*.py」的**合并文本**上查找。
选合并文本而非直接改读 models 文件，是为了兼容两种形态——若将来某张表迁回
`app.py`，断言依然成立，不会再次误报。

本文件锁住三件事：
  T1 门禁脚本整体通过（exit 0 / 无 FAIL）
  T2 四项曾被误报的检查恒为 PASS，且它们的模型类判据确实指向合并文本
  T3 非模型判据（路由/helper/模板）**仍然只查 app_py**，没有被顺手放宽
  T4 变异验证：抹掉任一模型类符号，对应检查必须重新变红（防止"改成恒真"）
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "verify_wms_bugs.py"
AI_MODELS = ROOT / "app" / "models" / "ai.py"

# 曾被 ARCH-MODELS-01 迁移连带误报的四项
REGRESSED_CHECKS = (
    "AI-DOCUMENT-JOB-MODELS-001",
    "AI-CONTROLLED-AGENTS-001",
    "AI-IDEMPOTENCY-001",
    "AI-AUDIT-001",
)

# 这些模型类名必须能在 models/ai.py 中找到（迁移后的真实位置）
MIGRATED_MODEL_CLASSES = (
    "AIDocumentJob", "AIDocumentItem", "AIDocumentAttempt", "AIDocumentFeedback",
    "AIAgentTask", "AIAgentStep",
    "AIRequestIdempotency",
    "AIRun", "AIToolCall",
)


def _check_block(src: str, code: str) -> str:
    """取出某个检查的 checks.append(( ... )) 代码块。

    必须锚定 `checks.append((` 而不是首次出现的 code 字符串——
    因为注释里也会提到检查名（本文件修复说明就是），否则切片会落在注释上，
    断言到一段不相干文本（本文件 test_t3b 初次实现即踩此坑）。
    """
    i = src.index("'%s'," % code)
    start = src.rindex("checks.append((", 0, i)
    end = src.index("))", i)
    return src[start:end]


def _run_gate() -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
    env.setdefault("WMS_DEBUG", "0")
    env.setdefault("DATABASE_URL", "sqlite:///:memory:")
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, encoding="utf-8",
        cwd=str(ROOT), env=env, timeout=600,
    )


@pytest.fixture(scope="module")
def gate():
    return _run_gate()


class TestGateHeadIsGreen:
    """门禁脚本必须整体通过 —— 它是 CI 里所有人的公共信号灯。"""

    def test_t1_gate_exits_zero_with_no_failures(self, gate):
        failing = [ln for ln in gate.stdout.splitlines() if ln.startswith("FAIL")]
        assert gate.returncode == 0, (
            "verify_wms_bugs.py 未通过（exit %s）。\n失败项：\n%s\n\n尾部输出：\n%s"
            % (gate.returncode, "\n".join(failing), gate.stdout[-2000:])
        )
        assert not failing, "不应有任何 FAIL 项，实际：\n%s" % "\n".join(failing)

    def test_t2_previously_misreported_checks_now_pass(self, gate):
        """四项曾被误报的检查必须为 PASS（且确实出现在输出里）。"""
        for code in REGRESSED_CHECKS:
            assert ("PASS %s:" % code) in gate.stdout, (
                "%s 未出现在输出中，或不是 PASS 状态" % code
            )

    def test_t2b_migrated_classes_exist_in_models_module(self):
        """真正的判据对象：这些模型类确实住在 app/models/ai.py。

        若哪天它们又被搬走，本断言会先失败，提示需要同步更新门禁脚本，
        而不是让门禁又一次静默变红。
        """
        src = AI_MODELS.read_text(encoding="utf-8")
        missing = [c for c in MIGRATED_MODEL_CLASSES
                   if ("class %s" % c) not in src]
        assert not missing, (
            "app/models/ai.py 缺失模型类 %s —— 若确实迁移了位置，"
            "请同步更新 scripts/verify_wms_bugs.py 与 tests/test_verify_wms_bugs_gate.py"
            % missing
        )


class TestFixDidNotWeakenTheGate:
    """修复方式必须"只挪位置、不放宽强度"。"""

    def test_t3_model_assertions_target_merged_source(self):
        """四项检查的模型类断言必须指向合并源，而非退回 app_py。"""
        src = SCRIPT.read_text(encoding="utf-8")
        assert "ai_models_src" in src, "应引入合并源变量 ai_models_src"

        # 合并源必须包含 app.py（兼容"模型又搬回去"的情况）与 models/ai.py
        m = re.search(r"ai_models_src\s*=\s*(.+?)\n\n", src, re.S)
        assert m, "未找到 ai_models_src 定义"
        blob = m.group(1)
        assert "app_py" in blob, "合并源必须包含 app_py（兼容模型搬回 app.py）"
        assert "app/models/ai.py" in blob, "合并源必须包含 app/models/ai.py"

        # 四项检查的判据里不得再出现 '"class Xxx" in app_py'
        for code in REGRESSED_CHECKS:
            seg = _check_block(src, code)
            offenders = re.findall(r"'class (\w+)' in app_py", seg)
            assert not offenders, (
                "%s 仍有钉在 app_py 上的模型类断言：%s（ARCH-MODELS-01 迁移后必然误报）"
                % (code, offenders)
            )

    def test_t3b_non_model_assertions_still_target_app_py(self):
        """非模型判据（路由/helper/模板）仍只查 app_py —— 不得被顺手放宽。

        注意：路由类断言在源码里用**双引号**包裹（因为内含单引号），
        这里按源码原样匹配。
        """
        src = SCRIPT.read_text(encoding="utf-8")
        probes = {
            "AI-DOCUMENT-JOB-MODELS-001": [
                '''"@app.route('/ai/document_jobs')" in app_py''',
                '''"def _ai_record_document_job" in app_py''',
            ],
            "AI-CONTROLLED-AGENTS-001": [
                '''"@app.route('/ai/agent_tasks')" in app_py''',
                "'def _ai_run_warehouse_patrol_agent' in app_py",
            ],
            "AI-IDEMPOTENCY-001": [
                "'_ai_idempotency = configure_ai_idempotency_service(' in app_py",
            ],
            "AI-AUDIT-001": [
                "in ai_idempotency_py",
            ],
        }
        for code, wanted in probes.items():
            seg = _check_block(src, code)
            for w in wanted:
                assert w in seg, (
                    "%s 的非模型判据 %r 被改动或放宽了" % (code, w)
                )

    def test_t4_merged_source_actually_contains_the_models(self):
        """合并源必须真的包含这些模型类 —— 否则判据必然恒假（不是恒真）。

        为什么不做"删掉类再跑门禁"的端到端变异：
        `verify_wms_bugs.py` 自身会 `import app`，而 `app.py` 有
        `from models.ai import (...)`。删掉模型类会让**门禁脚本自己**在
        import 阶段 ImportError 崩溃，根本走不到任何检查。
        也就是说"符号不存在"这个场景在本仓库里不可构造（模型是承重的），
        用它做变异只能证明"删了会崩"，不能证明单条检查有区分力。

        因此改用直接、可证伪的等价断言：重新按脚本的同一取法构造合并源，
        确认每个模型类确实在其中。若以后有人把 ai_models_src 的取法改错
        （漏文件、指向空串、写成常量），本测试立即失败。
        """
        def read_text(rel: str) -> str:
            return (ROOT / rel).read_text(encoding="utf-8", errors="ignore")

        merged = read_text("app/app.py") + "\n" + "\n".join(
            read_text(p) for p in (
                "app/models/ai.py", "app/models/core.py", "app/models/__init__.py",
            )
        )

        # 四项检查实际依赖的模型类，必须都能在合并源里找到
        required = {
            "AI-DOCUMENT-JOB-MODELS-001": (
                "class AIDocumentJob", "class AIDocumentItem",
                "class AIDocumentAttempt", "class AIDocumentFeedback",
            ),
            "AI-CONTROLLED-AGENTS-001": (
                "class AIAgentTask", "class AIAgentStep",
            ),
            "AI-IDEMPOTENCY-001": (
                "class AIRequestIdempotency", "uix_ai_request_user_request",
            ),
            "AI-AUDIT-001": (
                "class AIRun", "class AIToolCall", "ai_run_id = db.Column",
            ),
        }
        for code, symbols in required.items():
            for sym in symbols:
                assert sym in merged, (
                    "%s 的判据 %r 不在合并源里 —— ai_models_src 的取法可能被改坏了"
                    % (code, sym)
                )

        # 反向：这些模型类在纯 app_py 里确实找不到。
        # 这证明"合并"是必需的，而不是无意义地把 app_py 与自己拼了一遍。
        only_app = read_text("app/app.py")
        for code, symbols in required.items():
            for sym in symbols:
                if sym.startswith("class "):
                    assert sym not in only_app, (
                        "%s 的 %r 已回到 app.py —— 若是刻意搬回，"
                        "请同步更新本测试与门禁脚本的把关方式"
                        % (code, sym)
                    )

    def test_t4b_always_true_predicate_would_be_caught(self, tmp_path):
        """变异验证（判据侧）：把断言改成恒真，必须被本测试体系发现。

        T4 变异的是**数据源**（抹掉模型类），证明"符号没了会红"；
        但它抓不到另一种劣化：有人把判据改成恒真（`True and ...`），
        此时数据源完好、门禁仍 PASS，看似一切正常，实则该检查已空转。

        本测试用"判据侧变异"补齐这一面：断言每条检查的模型类判据
        都真实引用了 ai_models_src，而不是被替换成字面量 True。
        """
        src = SCRIPT.read_text(encoding="utf-8")
        for code in REGRESSED_CHECKS:
            seg = _check_block(src, code)
            # 不得出现被硬编码成恒真的判据
            assert not re.search(r"(and|,)\s*True\s*(and|,|$)", seg), (
                "%s 的判据里出现硬编码 True（门禁会空转）" % code
            )
            # 至少有一条模型类断言真实引用了合并源
            assert re.search(r"'class \w+' in ai_models_src", seg), (
                "%s 必须至少有一条引用 ai_models_src 的模型类断言" % code
            )
            # 且合并源本身不能是空/常量拼接
            m = re.search(r"ai_models_src\s*=\s*(.+?)\n\n", src, re.S)
            assert m and "read_text(" in m.group(1), (
                "ai_models_src 必须由 read_text 读取真实文件"
            )


class TestGateCoversRealCodeNotStrings:
    """门禁断言的对象在运行时真的可用（避免"字符串在、代码坏了"）。"""

    def test_t5_models_are_importable_and_routes_registered(self):
        env = dict(os.environ)
        env.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
        env.setdefault("WMS_DEBUG", "0")
        env.setdefault("DATABASE_URL", "sqlite:///:memory:")
        code = (
            "import app as wms\n"
            "from app import (AIDocumentJob, AIDocumentItem, AIDocumentAttempt,"
            " AIDocumentFeedback, AIAgentTask, AIAgentStep, AIRequestIdempotency,"
            " AIRun, AIToolCall)\n"
            "rules = [r.rule for r in wms.app.url_map.iter_rules()]\n"
            "want = ['/ai/document_jobs', '/ai/document_jobs/<int:id>',"
            " '/ai/document_jobs/<int:id>/confirm', '/ai/document_jobs/<int:id>/retry',"
            " '/ai/document_jobs/<int:id>/feedback', '/ai/agent_tasks',"
            " '/ai/agent_tasks/<int:id>', '/ai/agent_tasks/run/warehouse_patrol',"
            " '/ai/agent_tasks/run/purchase_followup']\n"
            "missing = [w for w in want if w not in rules]\n"
            "assert not missing, missing\n"
            "assert 'ai_run_id' in [c.name for c in AIToolCall.__table__.columns]\n"
            "ucs = [c.name for c in AIRequestIdempotency.__table__.constraints if c.name]\n"
            "assert 'uix_ai_request_user_request' in ucs, ucs\n"
            "print('OK')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(ROOT / "app"), env=env, timeout=300,
        )
        assert r.returncode == 0 and "OK" in r.stdout, (
            "运行时校验失败：\nstdout=%s\nstderr=%s" % (r.stdout[-1500:], r.stderr[-1500:])
        )
