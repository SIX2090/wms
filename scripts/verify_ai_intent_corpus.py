"""AI助手文本意图回归用例集。

覆盖开发计划中定义的5层能力：
- L1: 自然语言导航与帮助
- L2: 真实数据查询与解释
- L3: 业务分析与任务建议
- L4: 文档识别与草稿生成
- L5: 受控业务Agent

每条用例包含：
- id: 唯一标识
- category: 意图分类
- message: 用户输入
- expected_skill: 期望命中的本地技能或规则
- notes: 备注说明
"""

INTENT_CORPUS = [
    # ===== L1: 自然语言导航与帮助 =====
    {"id": "nav-001", "category": "navigation", "message": "打开物料列表", "expected_skill": "usage_help", "notes": "页面导航"},
    {"id": "nav-002", "category": "navigation", "message": "查看采购订单", "expected_skill": "usage_help", "notes": "页面导航"},
    {"id": "nav-003", "category": "navigation", "message": "进入待处理中心", "expected_skill": "usage_help", "notes": "页面导航"},
    {"id": "nav-004", "category": "navigation", "message": "打开库存查询", "expected_skill": "usage_help", "notes": "页面导航"},
    {"id": "nav-005", "category": "navigation", "message": "系统设置在哪里", "expected_skill": "usage_help", "notes": "页面导航"},
    {"id": "nav-006", "category": "sop", "message": "怎么入库", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-007", "category": "sop", "message": "如何领料出库", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-008", "category": "sop", "message": "采购流程是什么", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-009", "category": "sop", "message": "怎么扫码入库", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-010", "category": "sop", "message": "盘点怎么操作", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-011", "category": "sop", "message": "基础资料怎么维护", "expected_skill": "usage_help", "notes": "SOP流程解释"},
    {"id": "nav-012", "category": "sop", "message": "这个系统怎么用", "expected_skill": "usage_help", "notes": "通用帮助"},

    # ===== L2: 真实数据查询 =====
    {"id": "query-001", "category": "material_query", "message": "查A001库存", "expected_skill": "rule_based", "notes": "物料库存查询"},
    {"id": "query-002", "category": "material_query", "message": "M001还有多少", "expected_skill": "rule_based", "notes": "物料库存查询"},
    {"id": "query-003", "category": "material_query", "message": "查一下轴承的库存", "expected_skill": "rule_based", "notes": "按名称模糊查询"},
    {"id": "query-004", "category": "material_query", "message": "A001最近流水", "expected_skill": "rule_based", "notes": "物料流水查询"},
    {"id": "query-005", "category": "order_query", "message": "查IN26050001", "expected_skill": "rule_based", "notes": "按单号查单据"},
    {"id": "query-006", "category": "order_query", "message": "打开PO26050001这张采购单", "expected_skill": "rule_based", "notes": "按单号查采购单"},
    {"id": "query-007", "category": "today_summary", "message": "今天概况", "expected_skill": "rule_based", "notes": "今日汇总"},
    {"id": "query-008", "category": "today_summary", "message": "今天出库了哪些物料", "expected_skill": "rule_based", "notes": "今日出库"},
    {"id": "query-009", "category": "today_summary", "message": "今天到货了什么", "expected_skill": "rule_based", "notes": "今日到货"},
    {"id": "query-010", "category": "pending", "message": "有哪些待办", "expected_skill": "rule_based", "notes": "待处理查询"},
    {"id": "query-011", "category": "pending", "message": "待入库的单据", "expected_skill": "rule_based", "notes": "待处理查询"},
    {"id": "query-012", "category": "pending", "message": "未完成的单据有哪些", "expected_skill": "rule_based", "notes": "待处理查询"},
    {"id": "query-013", "category": "alert", "message": "库存预警", "expected_skill": "rule_based", "notes": "库存异常"},
    {"id": "query-014", "category": "alert", "message": "负库存物料", "expected_skill": "rule_based", "notes": "负库存查询"},
    {"id": "query-015", "category": "alert", "message": "低库存有哪些", "expected_skill": "rule_based", "notes": "低库存查询"},

    # ===== L3: 业务分析与建议 =====
    {"id": "analysis-001", "category": "analysis", "message": "库存周转分析", "expected_skill": "rule_based", "notes": "周转分析"},
    {"id": "analysis-002", "category": "analysis", "message": "库存金额多少", "expected_skill": "rule_based", "notes": "库存价值"},
    {"id": "analysis-003", "category": "analysis", "message": "供应商排行", "expected_skill": "rule_based", "notes": "供应商分析"},
    {"id": "analysis-004", "category": "analysis", "message": "A001消耗趋势", "expected_skill": "rule_based", "notes": "消耗趋势"},
    {"id": "analysis-005", "category": "analysis", "message": "补货建议", "expected_skill": "rule_based", "notes": "补货建议"},
    {"id": "analysis-006", "category": "analysis", "message": "滞销物料有哪些", "expected_skill": "stage4", "notes": "阶段4深度分析"},
    {"id": "analysis-007", "category": "analysis", "message": "缺料清单", "expected_skill": "rule_based", "notes": "缺料报告"},
    {"id": "analysis-008", "category": "analysis", "message": "盘点差异分析", "expected_skill": "stage4", "notes": "阶段4深度分析"},
    {"id": "analysis-009", "category": "analysis", "message": "供应商履约情况", "expected_skill": "stage4", "notes": "阶段4深度分析"},
    {"id": "analysis-010", "category": "analysis", "message": "预计可用天数", "expected_skill": "stage4", "notes": "阶段4深度分析"},

    # ===== L4: 草稿生成 =====
    {"id": "draft-001", "category": "out_order_draft", "message": "生成领料单 A001 20 B002 5", "expected_skill": "rule_based", "notes": "领料单草稿"},
    {"id": "draft-002", "category": "out_order_draft", "message": "创建出库单 M001 100", "expected_skill": "rule_based", "notes": "出库单草稿"},
    {"id": "draft-003", "category": "in_order_draft", "message": "生成产品入库单 A001 50", "expected_skill": "rule_based", "notes": "入库单草稿"},
    {"id": "draft-004", "category": "transfer_draft", "message": "从A仓库转到B仓库 M001 100 M002 20", "expected_skill": "rule_based", "notes": "调拨单草稿"},
    {"id": "draft-005", "category": "transfer_draft", "message": "把A仓库的物料调到B仓库 A001 30", "expected_skill": "rule_based", "notes": "调拨单草稿"},
    {"id": "draft-006", "category": "check_draft", "message": "盘点 M001 M002 M003", "expected_skill": "rule_based", "notes": "盘点单草稿"},
    {"id": "draft-007", "category": "check_draft", "message": "生成盘点单 A001 A002", "expected_skill": "rule_based", "notes": "盘点单草稿"},
    {"id": "draft-008", "category": "adjustment_draft", "message": "报废 M001 5", "expected_skill": "rule_based", "notes": "调整单草稿-报废"},
    {"id": "draft-009", "category": "adjustment_draft", "message": "盘亏 A002 3", "expected_skill": "rule_based", "notes": "调整单草稿-盘亏"},
    {"id": "draft-010", "category": "adjustment_draft", "message": "盘盈 B001 10", "expected_skill": "rule_based", "notes": "调整单草稿-盘盈"},
    {"id": "draft-011", "category": "purchase_receive", "message": "把这张采购单生成入库单", "expected_skill": "purchase_order_receive", "notes": "采购单下推入库"},
    {"id": "draft-012", "category": "purchase_receive", "message": "PO26050001生成采购入库单", "expected_skill": "purchase_order_receive", "notes": "指定采购单号下推入库"},

    # ===== L5: Agent任务 =====
    {"id": "agent-001", "category": "agent_patrol", "message": "仓库巡检", "expected_skill": "agent", "notes": "仓库巡检Agent"},
    {"id": "agent-002", "category": "agent_patrol", "message": "每日巡检", "expected_skill": "agent", "notes": "仓库巡检Agent"},
    {"id": "agent-003", "category": "agent_followup", "message": "采购跟进", "expected_skill": "agent", "notes": "采购跟进Agent"},
    {"id": "agent-004", "category": "agent_followup", "message": "催交供应商", "expected_skill": "agent", "notes": "采购跟进Agent"},

    # ===== 知识库 =====
    {"id": "kb-001", "category": "knowledge", "message": "采购入库SOP是什么", "expected_skill": "knowledge_base", "notes": "知识库-SOP"},
    {"id": "kb-002", "category": "knowledge", "message": "领料出库流程", "expected_skill": "knowledge_base", "notes": "知识库-SOP"},
    {"id": "kb-003", "category": "knowledge", "message": "盘点差异怎么处理", "expected_skill": "knowledge_base", "notes": "知识库-SOP"},
    {"id": "kb-004", "category": "knowledge", "message": "库存报表的数据来源是什么", "expected_skill": "knowledge_base", "notes": "知识库-报表口径"},
    {"id": "kb-005", "category": "knowledge", "message": "单据状态有哪些", "expected_skill": "knowledge_base", "notes": "知识库-状态规则"},

    # ===== 视觉能力 =====
    {"id": "vision-001", "category": "vision", "message": "识图能力状态", "expected_skill": "vision_status", "notes": "视觉能力自检"},
    {"id": "vision-002", "category": "vision", "message": "OCR配置检查", "expected_skill": "vision_status", "notes": "视觉能力自检"},
    {"id": "vision-003", "category": "vision", "message": "送货单识别怎么配", "expected_skill": "vision_status", "notes": "视觉能力自检"},

    # ===== 基础对话 =====
    {"id": "basic-001", "category": "greeting", "message": "你好", "expected_skill": "basic_conversation", "notes": "问候"},
    {"id": "basic-002", "category": "greeting", "message": "在吗", "expected_skill": "basic_conversation", "notes": "问候"},
    {"id": "basic-003", "category": "model_status", "message": "你是什么模型", "expected_skill": "basic_conversation", "notes": "模型状态"},
    {"id": "basic-004", "category": "model_status", "message": "大模型配置了吗", "expected_skill": "basic_conversation", "notes": "模型状态"},
    {"id": "basic-005", "category": "time", "message": "现在几点", "expected_skill": "basic_conversation", "notes": "时间查询"},
    {"id": "basic-006", "category": "time", "message": "今天几号", "expected_skill": "basic_conversation", "notes": "日期查询"},

    # ===== 技能清单/API =====
    {"id": "meta-001", "category": "skill_catalog", "message": "你会什么", "expected_skill": "skill_catalog", "notes": "技能清单"},
    {"id": "meta-002", "category": "skill_catalog", "message": "AI有哪些能力", "expected_skill": "skill_catalog", "notes": "技能清单"},
    {"id": "meta-003", "category": "api_catalog", "message": "系统有哪些API接口", "expected_skill": "system_api_catalog", "notes": "API清单"},
    {"id": "meta-004", "category": "api_catalog", "message": "列出所有接口路由", "expected_skill": "system_api_catalog", "notes": "API清单"},

    # ===== 缺料处理 =====
    {"id": "shortage-001", "category": "shortage", "message": "库存不足怎么办", "expected_skill": "stock_shortage_help", "notes": "缺料处理"},
    {"id": "shortage-002", "category": "shortage", "message": "A001缺货了", "expected_skill": "stock_shortage_help", "notes": "缺料处理-指定物料"},
    {"id": "shortage-003", "category": "shortage", "message": "负库存怎么处理", "expected_skill": "stock_shortage_help", "notes": "负库存处理"},
]


def main():
    categories = {}
    for case in INTENT_CORPUS:
        cat = case["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"Total intent test cases: {len(INTENT_CORPUS)}")
    print(f"Categories: {len(categories)}")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    # Verify all IDs are unique
    ids = [c["id"] for c in INTENT_CORPUS]
    assert len(ids) == len(set(ids)), f"Duplicate IDs found: {[x for x in ids if ids.count(x) > 1]}"
    print("All IDs unique: OK")

    # Verify all required fields present
    required = {"id", "category", "message", "expected_skill", "notes"}
    for case in INTENT_CORPUS:
        missing = required - set(case.keys())
        assert not missing, f"Case {case.get('id', '?')} missing fields: {missing}"
    print("All fields present: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
