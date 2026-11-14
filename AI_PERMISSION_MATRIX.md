# WMS AI 能力权限矩阵

## 2026-11-14 媒体入口权限补齐（AI-MOB-MEDIA-FIX-20261114-001）

用户明确批准：独立识物、独立音频转文字沿用 admin/warehouse/purchase/sales/production，viewer/user 禁止；二者跟随 AI 总开关及现有灰度。关闭总开关时管理员也禁止，灰度 off 对管理员的原有例外保留。

| 能力键 | 既有角色范围（含 admin） | 接口 | 输出边界 |
|---|---|---|---|
| material_recognition | admin、warehouse、purchase、sales、production | POST /mobile/api/recognize_material | 候选物料，人工选择，不建单/扣库存 |
| audio_transcription | admin、warehouse、purchase、sales、production | POST /mobile/api/asr | 仅文字，不等同 voice_out_draft |
| document_retry | admin、warehouse、purchase、sales、production | POST /ai/document_jobs/<id>/retry | 保留已有任务归属；仅重试提取，人工确认边界不变 |
| document_recognition | admin、warehouse、purchase | POST /api/ai/document_ocr、POST /api/ai/document_ocr_excel | 保留原角色及识别/人工确认/导出流程 |

四项既有识别/重试能力补齐 roles/business-endpoints/risk/registry，不新增路由、模型、开关或自主 dispatcher。注册表不承诺外部模型请求幂等（idempotent=False）。共同复用现有策略和灰度计算，真实主体按既有“会话优先，否则 Bearer”解析，保留会话 CSRF；灰度名单按实际用户 ID，不能拿 AnonymousUser 判定 Bearer。

实际提供方尝试前再次核对权限/总开关/灰度；OCR 重试及证据包装回退也通过该边界。拒绝写既有 AIRolloutAudit；调用尝试写既有 OperationLog 并绑定实际 user_id，仅记能力、不记图片/音频/转写/密钥/提供方原文。调用审计失败返回 503，不调用提供方。记录一次尝试不表示模型成功或计费对账完成。

识物保留原进程内每用户 5 次/60 秒限流，独立 ASR 复用同一滑动窗口实现及阈值，使用独立 asr:user:<id> 键，互不消耗对方配额；超限 429，未执行提供方调用。该限流不声称跨进程共享或供应商实际账单上限。语音旧客户端在只读角色、总开关关闭或灰度拒绝时现在收到 403，这是本次批准的兼容变化；正常音频验证、腾讯优先、TokenHub 回退和同音纠正保留。

本批代码/回退/CI/生产状态分别见 [第二批验收记录](docs/audit/2026-11-14-media-opening-remediation.md)。


## 权限原则

- `admin` 可以使用全部 AI 能力，但提交、审核、完成、反审、作废、删除和恢复备份仍必须走人工业务页面。
- AI 只允许在当前登录人员打开确认页并明确点击后生成草稿，不允许通过模型、工具编排器或 Agent 直接建单。
- 权限在服务端工具执行层校验，不能只依赖前端按钮或页面入口。
- 外部模型只能提出结构化意图，最终权限由 `AI_CAPABILITY_ROLES` 判断。
- 2026-10-21（AI-C01-FIX-ROLE-UI-001）：PC助手入口按 `AI_USE_ROLES` 显示；管理员保留全部建议，业务角色只显示通用及本角色建议。界面筛选不替代服务端能力、业务接口权限与人工确认校验。

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

## 2026-11-03 工作台草稿队列（AI-R10-F02）

`GET /ai/drafts` 仅允许已登录 admin/warehouse 查看 processing 状态的幂等草稿记录，按每页30条分页；其他角色拒绝访问（财务浏览器请求由既有全局门禁重定向首页，JSON请求403）。只显示记录编号、草稿类型、来源及时间，不展示请求载荷/凭据，不触发草稿生成、确认、提交、删除或外发。该入口是仓库工作台既有未完成草稿链接的只读落点，不增加AI工具权限。

文档任务重试依据现有 AI_USE_ROLES 的“消耗 LLM 计费端点”规则补齐 document_retry；该任务本就要求登录并核对归属，继续保留非管理员只能访问本人任务、管理员可处理他人任务的既定范围。只读 viewer/user 不再触发付费重试，总开关/灰度在重试时重新判定。识别 AI 功能开关 ai_feature_vision_enabled 和 LLM vision 配置由现有 _ai_llm_vision_enabled 保留检查，关闭仍返回既有 400，不把已存在的正面防护再改成新政策。
