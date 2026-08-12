# WMS AI 提示词修复提示词（2026-08-12）

> 用途：把 2026-08-12 提示词审计确认的 3 个真实缺陷固化为逐条可执行的修复指令。
> 执行方式：每条指令 = 1 个 atomic action（独立 commit + push 到 main），修复后在 `WMS_BUG_BASELINE.md` 标记已修复。
> 审计更正：后端"采购入库必须关联采购订单"的强制校验均由 `purchase_in_order_requires_order()` 开关守卫且默认停用（BUG-2026-08-02-019 已修复），本轮只修提示词/知识层表述与提示词链路缺陷，不动后端业务逻辑。

---

## FIX-1（BUG-2026-08-12-001）AI 知识库与工具描述仍宣称"采购入库必须关联采购订单"

**证据**

- `app/ai/knowledge.py:24`：`rule='采购入库必须关联采购订单；送货单识别只能生成草稿或确认页，不能直接完成入库。'`
- `app/ai/tools/registry.py:348`：`'Create a purchase receiving draft linked to a purchase order.'`

**规则依据**：`AGENTS.md` —— 采购订单仅作为可选来源，采购入库允许手工新增、编辑、保存和完成；有关联订单时保留来源、数量和执行进度跟踪。

**修改点**

1. `app/ai/knowledge.py` `purchase_receive_sop.rule` 改为：
   `采购订单是采购入库的可选来源，采购入库允许手工新增、编辑、保存和完成；有关联采购订单时必须保留来源、数量与执行进度跟踪。送货单识别只能生成草稿或确认页，不能直接完成入库。`
2. `app/ai/tools/registry.py` `purchase_receive_draft` 工具描述改为：
   `Create a purchase receiving draft. A purchase order is only an optional source; when linked, keep source, quantity and progress tracking.`

**验收标准**

- 全仓 grep 不再有 AI 面向文本宣称"采购入库必须关联采购订单"（后端开关守卫内的报错文案除外）。
- 新增回归测试 `tests/test_bug_2026_08_12_001_purchase_optional_prompt.py` 通过。
- `python3 scripts/verify_wms_bugs.py`、`python3 scripts/verify_ai_tool_schemas.py` 无回归。

**验证命令**

```bash
pytest tests/test_bug_2026_08_12_001_purchase_optional_prompt.py -q
python3 scripts/verify_wms_bugs.py
python3 scripts/verify_ai_tool_schemas.py
```

---

## FIX-2（BUG-2026-08-12-002）v2 调试接口允许任意登录用户覆盖 system_prompt

**证据**

- `app/ai/v2_routes.py:207`：`system_prompt = payload.get('system_prompt', '你是仓库管理系统的AI助手。')`
- `app/ai/v2_routes.py:228`：`system_prompt = payload.get('system_prompt', '你是意图解析器，输出JSON。')`

任何登录用户（含 `user`/`production` 等低权限角色）都可提交自定义 system_prompt，绕过 WMS 角色与业务边界约束。

**修改点**（`app/ai/v2_routes.py`）

1. 新增 helper `_resolve_debug_system_prompt(payload, default)`：
   - 非 admin：忽略 payload 中的 `system_prompt`，返回服务端默认提示词。
   - admin：允许自定义（调试用），截断到 2000 字符，并 `logger.warning` 审计（user id、prompt 长度）。
2. `v2_llm_chat` / `v2_llm_intent` 两路由改用该 helper。

**验收标准**

- 非 admin 传 `system_prompt` 时，实际调用 LLM 的提示词是服务端默认值。
- admin 自定义生效且有审计日志。
- 新增回归测试 `tests/test_bug_2026_08_12_002_v2_system_prompt_guard.py` 通过。
- `python3 scripts/verify_wms_bugs.py` 无回归。

**验证命令**

```bash
pytest tests/test_bug_2026_08_12_002_v2_system_prompt_guard.py -q
python3 scripts/verify_wms_bugs.py
```

---

## FIX-3（BUG-2026-08-12-003）统一系统提示词缺少核心业务红线

**证据**

- `app/ai/prompts.py` `legacy-v1` 仅一句英文泛化描述，未包含任何 WMS 业务红线。
- `app/app.py` 运行时聊天/意图提示词硬编码且不含"送货通知→入库草稿（禁止采购申请）""仓库必填""密码不可重置"等红线。

**规则依据**：`AGENTS.md` —— AI 只能创建草稿，提交/审核/完成/作废/删除保持人工；微信送货通知必须生成入库草稿而非采购申请；仓库始终必填；AI 不得修改/重置任何账号密码。

**修改点**

1. `app/ai/prompts.py`：扩充 `legacy-v1` 的 `system_prompt`，在保留 `Never auto-submit` 原句（`scripts/verify_ai_platform_foundations.py` 断言依赖）的前提下，追加中文红线：
   - AI 只能创建草稿；提交、审核、完成、反审、作废、删除和直接改库存必须由人工在业务页面确认。
   - 微信文字/截图送货通知是供应商到货通知，只能生成采购入库/其他入库草稿，严禁生成采购申请。
   - 采购订单是采购入库的可选来源，不是强制条件。
   - 所有出入库单据仓库必填；启用库位管理时库位也必填；缺仓库/库位时必须标记待补充，不得猜测默认值。
   - 库存、数量、金额、单据状态必须经实时工具查询，不得编造。
   - 不得修改、重置或生成任何账号密码。
2. `app/app.py` 聊天系统提示词（`_ai_chat` 相关）引用 `get_prompt_spec().system_prompt` 作为基础约束，再拼接页面上下文。

**验收标准**

- `python3 scripts/verify_ai_platform_foundations.py` 通过（保留 `Never auto-submit`）。
- 新增回归测试 `tests/test_bug_2026_08_12_003_system_prompt_redlines.py`：断言红线关键词在统一提示词与 app.py 聊天提示词链路中均存在。
- `python3 scripts/verify_wms_bugs.py` 无回归。

**验证命令**

```bash
pytest tests/test_bug_2026_08_12_003_system_prompt_redlines.py -q
python3 scripts/verify_ai_platform_foundations.py
python3 scripts/verify_wms_bugs.py
```
