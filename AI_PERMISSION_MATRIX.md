# WMS AI 能力权限矩阵

## 权限原则

- `admin` 可以使用全部 AI 能力，但提交、审核、完成、反审、作废、删除和恢复备份仍必须走人工业务页面。
- AI 只允许在当前登录人员打开确认页并明确点击后生成草稿，不允许通过模型、工具编排器或 Agent 直接建单。
- 权限在服务端工具执行层校验，不能只依赖前端按钮或页面入口。
- 外部模型只能提出结构化意图，最终权限由 `AI_CAPABILITY_ROLES` 判断。

## 当前能力矩阵

| 能力键 | admin | warehouse | purchase | sales | production | user | 风险级别 |
|---|---:|---:|---:|---:|---:|---:|---|
| `out_order_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `sales_out_draft` | 允许 | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 草稿 |
| `after_sale_out_draft` | 允许 | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 草稿 |
| `sales_outbound_draft` | 允许 | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 草稿 |
| `in_order_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `voice_out_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `purchase_receive_draft` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `transfer_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `check_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `adjustment_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 草稿 |
| `purchase_request_draft` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `warehouse_insights` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 只读 |
| `purchase_insights` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `sales_insights` | 允许 | 禁止 | 禁止 | 允许 | 禁止 | 禁止 | 只读 |
| `warehouse_patrol_agent` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 只读 Agent |
| `purchase_followup_agent` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 禁止 | 只读 Agent |
| `sales_followup_agent` | 允许 | 禁止 | 禁止 | 允许 | 禁止 | 禁止 | 只读 Agent |
| `replenishment_planning` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `replenishment_smart` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `inventory_health` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `supplier_evaluation` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `location_recommendation` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 只读 |
| `demand_forecast` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `knowledge_base` | 允许 | 允许 | 允许 | 允许 | 允许 | 允许 | 只读 |
| `master_data_insights` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 只读 |
| `admin_insights` | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 禁止 | 敏感只读 |
| `alias_management` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读/维护入口 |

## 工具语义说明（AI-SALES-F01-FIX-02 / AI-SALES-F02）

- `sales_out_draft`：**已废弃别名**，行为等同 `after_sale_out_draft`，仅为向后兼容保留。新增 AI 调用应使用 `after_sale_out_draft` 或 `sales_outbound_draft`。
- `after_sale_out_draft`：售后出库草稿，对应业务端点 `add_after_sale_out_order`，创建 `AfterSaleOutOrder`（客户退货、换货、保修发货等场景）。
- `sales_outbound_draft`：销售出库草稿，对应业务端点 `create_sales_outbound_draft`，从已确认销售订单生成 `OutOrder`（按订单未发货数量自动生成明细）。
- `sales_insights`：销售只读洞察，对应业务端点 `sales_order_list`，handler `_ai_sales_insights_response`，返回销售工作台、客户跟进清单和销售异常汇总。
- `sales_followup_agent`：销售履约跟进 Agent，对应业务端点 `ai_agent_run_sales_followup`，handler `_ai_run_sales_followup_agent`，走 4 步 AIAgentTask 流程，催发货话术恒不自动发送，需人工确认。
- `voice_out_draft`：**手机端语音建领料单草稿**（AI-VOICE-OUT-F01），对应业务端点 `add_out_order`，入口 `POST /api/mobile/voice_out_draft`。用户说「领8*25螺丝 1000个」→ 服务端做文本归一化（同音纠正/中文数字/分隔符统一）→ 锁定规格再找数量 → 六层降级物料匹配（别名 → 精确编码 → 全模糊 → 词根兜底+规格相似度 → 仅规格 → AI 四层）。多命中必须由用户在候选列表点选后才建单；语音未说数量时不猜、要求人工填写。**只生成 `status=pending` 的 `OutOrder`（business_type='领料单'），绝不扣库存**，提交/完成仍由人工在出库页执行。

> 注：`voice_out_draft` 走 `@api_role_required` 的 Bearer Token 通道，其能力校验不能调 `_ai_capability_allowed()`（该函数读 Flask-Login 的 `current_user`，与 Bearer 通道互不相通，会拿到 `AnonymousUser` 而误拒）。端点改用 `is_ai_capability_allowed_for_role(cap, user.role, business_roles=...)` + `evaluate_rollout_access(...)` 组合判定，效果等价且与 `AI_CAPABILITY_ROLES` / 灰度 / 总开关 / 草稿开关全部打通。

## LLM 计费端点门禁（AI-LLM-GATE-002，2026-09-11 补登记）

`BUG-2026-08-16-013` 给 LLM 端点加了角色门禁，但当时扫描不全，以下 5 个内部调 `_ai_call_llm_chat` 的端点漏网（仅 `@login_required`，viewer/user 可刷计费、灰度开关无效），已全部补齐：

| 端点 | 门禁方式 | 说明 |
|---|---|---|
| `POST /api/ai/supplier_evaluation` | 新能力键 `supplier_evaluation` | 供应商智能评估，`require_role('warehouse','purchase')` 与页面一致 |
| `POST /api/ai/recommend_location` | 新能力键 `location_recommendation` | 智能库位推荐，页面同步补 `@require_role('warehouse')` |
| `POST /api/ai/demand_forecast` | 新能力键 `demand_forecast` | 需求预测，页面同步补 `@require_role('warehouse','purchase')` |
| `POST /api/ai/replenishment_suggestions` | 复用 `replenishment_planning` | 补货规划页面族的 JSON API（当前无前端调用方，属孤儿端点） |
| `POST /api/ai/inventory_health` | 复用 `inventory_health` | 库存健康页面族的 JSON API（当前无前端调用方，属孤儿端点） |

> 维护要求：任何新增内部调用 `call_llm*` / `_ai_call_llm_*` 的端点，必须先登记能力键（四处齐）并加 `_ai_capability_allowed` 门禁；`scripts/verify_wms_bugs.py` 的 `AI-LLM-GATE-002` 检查会对已登记端点断言门禁存在。

## 高风险动作

以下动作不注册为 AI 可执行工具：

- 提交、审核、完成、关闭。
- 反审、作废、删除。
- 直接增加或扣减库存。
- 恢复数据库备份。
- 修改用户角色、停用账号、重置密码。
- 修改 AI API Key 或其他系统密钥。

草稿工具统一标记为 `draft + confirmation_required`；仅 `read/sensitive_read` 能力可以由编排器自主执行。一次确认令牌只允许生成一次草稿，生成后立即从会话删除。

## 维护要求

1. 新增 AI 技能时必须先增加能力键和角色矩阵。
2. 草稿工具必须具有幂等保护和操作审计。
3. 页面权限与 AI 工具权限不一致时，以更严格的权限为准。
4. 权限变更必须同步更新 `scripts/verify_wms_bugs.py` 回归检查。
