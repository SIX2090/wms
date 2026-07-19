# WMS AI 能力权限矩阵

## 权限原则

- `admin` 可以使用全部 AI 能力，但提交、审核、完成、反审、作废、删除和恢复备份仍必须走人工业务页面。
- AI 只允许在当前登录人员打开确认页并明确点击后生成草稿，不允许通过模型、工具编排器或 Agent 直接建单。
- 权限在服务端工具执行层校验，不能只依赖前端按钮或页面入口。
- 外部模型只能提出结构化意图，最终权限由 `AI_CAPABILITY_ROLES` 判断。

## 当前能力矩阵

| 能力键 | admin | warehouse | purchase | sales | production | user | 风险级别 |
|---|---:|---:|---:|---:|---:|---|
| `out_order_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `sales_out_draft` | 允许 | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 草稿 |
| `in_order_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `purchase_receive_draft` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 草稿 |
| `transfer_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `check_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `adjustment_draft` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 草稿 |
| `purchase_request_draft` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 草稿 |
| `warehouse_insights` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `purchase_insights` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 只读 |
| `warehouse_patrol_agent` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 Agent |
| `purchase_followup_agent` | 允许 | 禁止 | 允许 | 禁止 | 禁止 | 只读 Agent |
| `replenishment_planning` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 只读 |
| `replenishment_smart` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 只读 |
| `inventory_health` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 只读 |
| `knowledge_base` | 允许 | 允许 | 允许 | 允许 | 允许 | 只读 |
| `master_data_insights` | 允许 | 允许 | 禁止 | 禁止 | 禁止 | 只读 |
| `admin_insights` | 允许 | 禁止 | 禁止 | 禁止 | 禁止 | 敏感只读 |
| `alias_management` | 允许 | 允许 | 允许 | 禁止 | 禁止 | 只读/维护入口 |

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
