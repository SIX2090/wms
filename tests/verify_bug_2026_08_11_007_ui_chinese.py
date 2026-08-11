"""
回归测试：BUG-2026-08-11-007 前端界面英文文案中文化

问题模式：AI Agent 任务、AI 文档任务、AI 运维看板、AI 验收、AI 业务质量等
前端界面把数据库英文枚举码（pending/completed/ocr_upload/allowlist 等）和
Agent 硬编码英文整句直接渲染到页面；多个单据详情页状态兜底分支裸露英文
原始值；部分打印/报表/登录页含英文标题。

修复：
1. app.py 新增 ai_agent_text / ai_agent_label / ai_doc_label 三个 Jinja
   过滤器及配套中英文映射表（固定整句 + 含数字正则句型 + 片段替换）。
2. 三个 Agent 函数（warehouse_patrol / purchase_followup / sales_followup）
   直接以中文写入任务目标、步骤名、数据范围、结果摘要和操作标签。
3. 12 个 AI 相关模板应用过滤器转换历史英文数据。
4. 10+ 业务详情页状态枚举兜底分支统一显示"未知"而非英文原值。
5. 打印页/报表中心/登录页等英文标题改中文。

验收标准：
- T1: app.py 注册三个中文化 Jinja 过滤器
- T2: 三个 Agent 函数直接以中文创建任务（无英文 objective 硬编码）
- T3: AI Agent 任务列表/详情模板应用中文化过滤器
- T4: AI 文档任务列表/详情模板应用 ai_doc_label 过滤器
- T5: AI 运维看板对灰度范围/运行状态/工具名应用过滤器
- T6: AI 验收页结论选项为"通过/不通过"，无 go/no_go 裸露
- T7: AI 业务质量页"Schema版本"统一为"结构版本"
- T8: 关键详情页状态兜底分支显示"未知"而非英文原值
- T9: 运行时过滤器行为：英文整句/含数字句型/枚举码均转中文
- T10: 模板静态扫描无常见英文按钮/选项/标题残留
"""

import os
import re
import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent.parent
APP_PY = WORKSPACE / "app" / "app.py"
TEMPLATES = WORKSPACE / "app" / "templates"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_src() -> str:
    return _read(APP_PY)


def _tpl(name: str) -> str:
    return _read(TEMPLATES / name)


# ---------- T1: app.py 注册三个中文化过滤器 ----------
def test_t1_filters_registered():
    src = _app_src()
    for fname in ("ai_agent_text", "ai_agent_label", "ai_doc_label"):
        assert f"app.jinja_env.filters['{fname}']" in src, (
            f"app.py 未注册 Jinja 过滤器 {fname}；"
            "BUG-2026-08-11-007：历史英文数据需渲染层转中文"
        )
    # 映射表存在
    for table in ("AI_AGENT_TYPE_LABELS", "AI_AGENT_TEXT_ZH", "AI_AGENT_TEXT_ZH_PATTERNS",
                  "AI_DOC_SOURCE_LABELS", "AI_DOC_JOB_STATUS_LABELS",
                  "AI_DOC_MATCH_STATUS_LABELS", "AI_ROLLOUT_MODE_LABELS"):
        assert table in src, f"app.py 缺少映射表 {table}"


# ---------- T2: Agent 函数直接以中文创建任务 ----------
def test_t2_agent_tasks_chinese_objectives():
    src = _app_src()
    for zh in ("'仓库每日巡检：库存风险、待处理单据、草稿阻塞和采购到货阻塞。'",
               "'采购跟进：逾期订单、即将到货、待处理申请和低库存补货。'",
               "'销售履约跟进：待发货、逾期订单、部分发货停滞、缺货、客户催发货和合单候选。'"):
        assert zh in src, f"Agent 任务目标未中文化：{zh}"
    # 英文 objective 不得再作为新任务硬编码写入（映射表 key 中允许存在）
    create_calls = re.findall(r"_ai_create_agent_task\(\s*'[a-z_]+',\s*'([^']+)'", src)
    assert create_calls, "未找到 _ai_create_agent_task 调用"
    for obj in create_calls:
        assert not re.search(r"[A-Za-z]{4,}", obj), (
            f"_ai_create_agent_task 仍写入英文目标：{obj}"
        )


# ---------- T3: AI Agent 任务模板应用过滤器 ----------
def test_t3_agent_task_templates_use_filters():
    list_tpl = _tpl("ai_agent_tasks.html")
    assert "task.agent_type|ai_agent_label('agent_type')" in list_tpl
    assert "task.status|ai_agent_label('task_status')" in list_tpl
    assert "task.objective|ai_agent_text" in list_tpl
    assert "task.summary|ai_agent_text" in list_tpl

    detail_tpl = _tpl("ai_agent_task_detail.html")
    assert "task.objective|ai_agent_text" in detail_tpl
    assert "step.name|ai_agent_text" in detail_tpl
    assert "step.tool_name|ai_agent_label('tool')" in detail_tpl
    assert "step.risk_level|ai_agent_label('risk')" in detail_tpl
    assert "step.status|ai_agent_label('step_status')" in detail_tpl
    assert "step.result_summary|ai_agent_text" in detail_tpl


# ---------- T4: AI 文档任务模板应用 ai_doc_label ----------
def test_t4_document_job_templates_use_filters():
    list_tpl = _tpl("ai_document_jobs.html")
    assert "job.source|ai_doc_label('source')" in list_tpl
    assert "ai_doc_label('doc_type')" in list_tpl
    assert "ai_doc_label('job_status')" in list_tpl

    detail_tpl = _tpl("ai_document_job_detail.html")
    assert "ai_doc_label('source')" in detail_tpl
    assert "ai_doc_label('match_status')" in detail_tpl
    assert "ai_doc_label('job_status')" in detail_tpl
    assert "ai_doc_label('rating')" in detail_tpl
    assert "ai_doc_label('error_type')" in detail_tpl


# ---------- T5: AI 运维看板应用过滤器 ----------
def test_t5_ops_dashboard_uses_filters():
    tpl = _tpl("ai_ops_dashboard.html")
    assert "ai_doc_label('rollout_mode')" in tpl, "灰度范围未中文化"
    assert "ai_doc_label('run_status')" in tpl, "运行状态未中文化"
    assert "ai_agent_label('tool')" in tpl, "工具名未中文化"


# ---------- T6: AI 验收页结论中文化 ----------
def test_t6_acceptance_page_chinese():
    tpl = _tpl("ai_acceptance.html")
    assert ">不通过</option>" in tpl and ">通过</option>" in tpl, (
        "AI 验收页结论选项未中文化"
    )
    # 展示层不得把 go/no_go 直接作为可见文本
    assert ">go</option>" not in tpl and ">no_go</option>" not in tpl
    # 角色映射
    assert "'admin': '管理员'" in tpl and "'warehouse': '仓库'" in tpl


# ---------- T7: AI 业务质量页"结构版本" ----------
def test_t7_business_quality_schema_zh():
    tpl = _tpl("ai_business_quality.html")
    assert "结构版本" in tpl
    # 可见文案不得再出现 "Schema版本"（schema_version 字段名 id/key 允许）
    visible = re.sub(r"id=\"[^\"]*\"", "", tpl)
    visible = re.sub(r"'schema_version'", "", visible)
    assert "Schema版本" not in visible and "Schema 版本" not in visible, (
        "AI 业务质量页仍可见 Schema版本 英文文案"
    )


# ---------- T8: 详情页状态兜底显示"未知" ----------
def test_t8_status_fallback_unknown_zh():
    checks = {
        "approval.html": "未知",
        "operation_audit.html": "未知",
        "in_order_detail.html": "未知",
        "out_order_detail.html": "未知",
        "sales_order_detail.html": "未知",
        "subcontract_detail.html": "未知",
        "purchase_request_detail.html": "未知",
        "after_sale_out_detail.html": "未知",
    }
    for name, fallback in checks.items():
        tpl = _read(TEMPLATES / name)
        assert re.search(r"\{%\s*else\s*%\}\s*" + fallback + r"\s*\{%\s*endif\s*%\}", tpl) \
            or f">{fallback}<" in tpl, (
            f"{name} 状态兜底分支未显示{fallback}（会裸露英文状态码）"
        )
        # 兜底分支不得直接渲染原始状态变量
        assert not re.search(r"\{%\s*else\s*%\}\s*\{\{\s*\w+\.status\s*\}\}", tpl), (
            f"{name} 状态兜底仍直接输出英文原值"
        )


# ---------- T9: 运行时过滤器行为 ----------
def test_t9_filter_runtime_behavior():
    sys.path.insert(0, str(WORKSPACE / "app"))
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("WMS_BOOTSTRAP_PASSWORD", "admin")
    os.environ.setdefault("WMS_DEBUG", "0")
    os.environ.setdefault("WMS_SKIP_AUTO_UPDATE", "1")
    import app as app_module

    text_f = app_module._ai_agent_text_zh
    # 英文整句 → 中文
    assert text_f(
        "Warehouse daily patrol: stock risks, pending documents, drafts, and purchase arrival blockers."
    ) == "仓库每日巡检：库存风险、待处理单据、草稿阻塞和采购到货阻塞。"
    # 含数字句型 → 中文并保留数字
    assert text_f("Negative stock: 2; low stock: 5.") == "负库存：2 项；低库存：5 项。"
    # 片段替换
    frag = text_f("inbound drafts: 2; outbound drafts: 1")
    assert "inbound drafts" not in frag and "入库草稿" in frag
    # 空值/未知值原样返回
    assert text_f("") == ""
    assert text_f(None) is None

    agent_label = app_module._ai_agent_label_zh
    assert agent_label("warehouse_patrol", "agent_type") == "仓库巡检"
    assert agent_label("completed", "task_status") == "已完成"
    assert agent_label("warehouse_insights", "tool") == "仓库洞察"
    assert agent_label(None, "tool") is None

    doc_label = app_module._ai_doc_label_zh
    assert doc_label("ocr_upload", "source") == "拍照识别"
    assert doc_label("pending_confirmation", "job_status") == "待确认"
    assert doc_label("matched", "match_status") == "已匹配"
    assert doc_label("allowlist", "rollout_mode") == "白名单"
    assert doc_label("in_order", "doc_type") == "入库单"


# ---------- T10: 模板静态扫描无英文 UI 残留 ----------
def test_t10_no_english_ui_residue():
    # 常见英文按钮/操作词作为独立可见文本不得出现
    btn_pat = re.compile(
        r">\s*(Save|Cancel|Delete|Edit|Submit|Confirm|Close|Search|Reset|Export|"
        r"Import|Print|Back|Next|Loading|Yes|No|Select All)\s*<"
    )
    # 英文状态码作为独立可见文本不得出现（<code> 技术说明除外，逐模板白名单）
    status_pat = re.compile(
        r">\s*(pending|completed|success|failed|matched|unmatched|cancelled|"
        r"approved|rejected|processing|uploading|recognizing|recognized)\s*<"
    )
    allowed_status_files = {"system_settings.html"}  # <code>completed</code> 技术说明
    offenders = []
    for tpl_path in sorted(TEMPLATES.glob("*.html")):
        content = _read(tpl_path)
        m = btn_pat.search(content)
        if m:
            offenders.append(f"{tpl_path.name}: 英文按钮 {m.group(1)}")
        if tpl_path.name not in allowed_status_files:
            m2 = status_pat.search(content)
            if m2:
                offenders.append(f"{tpl_path.name}: 英文状态 {m2.group(1)}")
    assert not offenders, "模板存在英文 UI 残留：\n" + "\n".join(offenders)


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = []
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
            failures.append(t.__name__)
    if failures:
        sys.exit(1)
    print(f"\n所有 {len(tests)} 个 BUG-2026-08-11-007 回归测试通过")
