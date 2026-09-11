# WMS 进销存 + AI 能力详细修复方案

> 上游文档：`WMS_BUSINESS_AI_DIAGNOSIS.md`（诊断）→ 本文（修复方案）
> 编制日期：2026-09-11
> 适用仓库：`/workspace/wms`（Flask + SQLAlchemy 单体 + Android 原生 WMS）
> **本方案所有条目均已定位到具体文件与行号；未标"待核实"的结论都已实测。**

---

## 决策摘要（先看这 8 条）

1. **14 个修复项里，只有 3 项需要你先拍板**（见 §0.2）。其余 11 项是纯粹的"补登记 / 补闭环 / 去重"，机械可执行，不需要业务决策。
2. **最高性价比的动作是 P0-4**：`api_supplier_evaluation` 未注册能力键，是**已证实**的治理漏洞，这个洞今天就能补，成本约 30 分钟。
3. **P1-6「销售订单库存占用」我改了口径**：原诊断写的是"加 `reserved_quantity` 字段"，实测后发现**真正的问题不是缺字段，而是整条链路零校验**——下单不校验、下推不校验，只有在出库完成时才拦。**加字段是个陷阱**（详见 §3.6），推荐方案是「**软占用 + 双重校验**」，**不改数据模型**。
4. **P1-5「销售退货入库单」不要新建模型**：`InOrder` 的 `business_type` 本身就是自由字符串（`app/app.py:5396`，默认 `'采购入库'`），且已有 `customer_id` 字段——注释写明"其他入库 / 客供料归属方"（`app/app.py:5395`）。**这让退货入库几乎不用改模型**。建议**复用 `InOrder` + `business_type='销售退货入库'`**，而不是造第 90 个 `db.Model`（详见 §3.5）。
5. **P1-7「采购退货单」系统里已埋了开关**：`purchase_return_requires_order`（默认 `1`）在配置页写着"为后续采购退货流程预留"——这是个**半成品**，不是零起点（见 §3.7）。
6. **P0-2「反馈闭环」的真实断点已定位**：`create_feedback` → `list_feedbacks`（`app/ai/audit.py:144/166`）只被自己的路由调用，**写入后没有任何消费者**。闭环只需接上"差评→待修清单"这一段，**不需要新表**。
7. **执行纪律**：1 个原子动作 = 1 次提交 = 1 次推送；每个动作配**代码级验证**（不是"看一眼觉得对"）。方案里每项都给了验证命令。
8. **⛔ 安全提醒（必须处理）**：你之前暴露的 GitHub token（`ghp_pXWK…`，明文不落档——GitHub 密钥扫描会拒绝包含它的提交）**请立即吊销**。当前连接器网关已返回 404，下次推送前需要重新授权。

---

## 0. 执行总纲

### 0.1 分期与依赖关系

```
第 1 批（本周，零业务风险）
  P0-4 补齐 AI 治理漏洞 ────┐
  P0-1 AI 名实对齐      ────┤ 互不依赖，可并行
  P1-8 合并重复补货实现 ────┘
        │
        ▼
第 2 批（下周，需业务确认）
  P0-2 反馈闭环最小版
  P0-3 建议带置信度（依赖 P0-1 的文案口径统一）
        │
        ▼
第 3 批（2~3 周，动数据模型/单据流）
  P1-6 销售订单库存占用（先做，因为不改模型）
  P1-5 销售退货入库单（需迁移脚本）
  P1-7 采购退货单（复用 P1-5 的模式）
        │
        ▼
第 4 批（按需）
  P2-9 / P2-10 / P2-11
```

**为什么这个顺序**：第 1 批全部是"登记、改名、去重"，不碰业务数据，改错了也只是文案回到原样。第 3 批引入新单据类型和库存流向，必须排在治理收口之后——否则新代码会立刻成为 A11（库存真相规则）的新违规源。

### 0.2 需要你拍板的 3 个决策

| # | 决策点 | 选项 A | 选项 B | 我的建议 |
|---|---|---|---|---|
| **D1** | 库存占用是否落地为**阻断** | 软占用仅提示，允许负库存开单 | 软占用 + 下单时硬阻断 | **先 A 观察一个迭代，再切 B**。理由：现在仓库的实际作业习惯未知，直接阻断可能让已承诺的销售单卡死。 |
| **D2** | 销售退货用**哪张单** | 复用 `InOrder`（`business_type='销售退货入库'`） | 新建 `SalesReturnOrder` 模型 | **A**。B 会引入第 90 个模型 + 第 4 套单据流，而退货本质就是入库。 |
| **D3** | AI 名实对齐的**尺度** | 全改：叫"智能"的删掉"智能" | 折中：保留名称，加"依据"说明 | **B**。用户已经形成操作习惯，大规模改名会让培训成本上升；加"依据"栏能达到同样效果。 |

### 0.3 通用验收标准（每项都必须过）

```bash
# 1. 语法与静态检查（必须 0 违规）
PYENV_VERSION=3.11.1 python3 scripts/lint_wms_rules.py

# 2. bug 回归台账（必须全 PASS）
PYENV_VERSION=3.11.1 python3 scripts/verify_wms_bugs.py

# 3. AI 治理四件套
PYENV_VERSION=3.11.1 python3 scripts/verify_ai_permission_matrix.py
PYENV_VERSION=3.11.1 python3 scripts/verify_ai_tool_registry.py
PYENV_VERSION=3.11.1 python3 scripts/verify_ai_tool_schemas.py
PYENV_VERSION=3.11.1 python3 scripts/verify_ai_tool_compliance.py

# 4. 全量回归（必须 0 failed）
PYENV_VERSION=3.11.1 python3 -m pytest tests/ -q --ignore=tests/test_run_server_port_hint.py
```

> 上次实测基线：**372 passed, 5 skipped, 0 failed**。方案执行后不得低于此基线。

---

## 一、P0 修复项（低风险，高信任收益）

### P0-4 补齐 AI 治理漏洞 ⭐ 建议今天做

**问题（已实测确认）**

`api_supplier_evaluation` 位于 `app/app.py:32408`，装饰器只有：

```python
@app.route('/api/ai/supplier_evaluation', methods=['POST'])
@login_required                      # ← 只有登录校验
def api_supplier_evaluation():
```

它内部会调用 `_ai_call_llm_chat(prompt)`（`app/app.py:32508`），**是一条真实的 LLM 计费链路**，但：

- 未出现在 `AI_CAPABILITY_ROLES`（`app/ai/policies.py:30`）
- 未出现在 `AI_CAPABILITY_BUSINESS_ENDPOINTS`（`app/ai/policies.py:69`）
- 未出现在 `AI_CAPABILITY_RISK_LEVELS`（`app/ai/policies.py:95`）
- 未出现在 `AI_TOOL_REGISTRY`（`app/ai/tools/registry.py:357`）

**后果**：任意 `viewer` / `user` 角色登录后，直接 POST 该端点即可消耗 LLM 计费额度，且**灰度开关（rollout）对它完全无效**——这正是 `BUG-2026-08-16-013` 当初要修的那类洞，只是这条漏网了。

**修复动作（原子化）**

| 步 | 文件 | 改动 |
|---|---|---|
| 1 | `app/ai/policies.py` | `AI_CAPABILITY_ROLES` 增 `'supplier_evaluation': frozenset({'warehouse', 'purchase'})` |
| 2 | 同上 | `AI_CAPABILITY_BUSINESS_ENDPOINTS` 增 `'supplier_evaluation': 'ai_supplier_evaluation_page'` |
| 3 | 同上 | `AI_CAPABILITY_RISK_LEVELS` 增 `'supplier_evaluation': 'read'` |
| 4 | `app/ai/tools/registry.py` | 新增 `SUPPLIER_EVALUATION_SCHEMA`（空对象，无入参）+ `AI_TOOL_REGISTRY` 条目 |
| 5 | `app/app.py:32408` | 端点内加 `_ai_capability_allowed('supplier_evaluation')` 前置校验；页面路由补 `@require_ai_role` |
| 6 | `AI_PERMISSION_MATRIX.md` | 矩阵表补一行 + 工具语义说明 |
| 7 | `scripts/verify_ai_permission_matrix.py:32` | `EXPECTED` 补 `'supplier_evaluation': {'admin', 'warehouse', 'purchase'}` |
| 8 | `scripts/verify_ai_tool_schemas.py:23` | `VALID_PAYLOADS` 补 `'supplier_evaluation': {}` |
| 9 | `scripts/verify_wms_bugs.py` | 新增检查 `AI-SUPPLIER-EVAL-001`（见下） |
| 10 | `tests/verify_bug_2026_08_16_013_ai_role_gate.py` | `LLM_ENDPOINTS` 列表补 `/api/ai/supplier_evaluation` |

> **为什么必须"四处齐"**：能力键少登记任一处都会被静默拒绝（这是 `AI-VOICE-OUT-F01` 踩过的坑，已写进 `AI_PERMISSION_MATRIX.md` 的注）。

**验证方式**

```bash
# 新测试必须证明：viewer 被 403 拦、warehouse 放行
PYENV_VERSION=3.11.1 python3 -m pytest tests/test_bug_2026_08_16_013_ai_role_gate.py -v
```

```python
# scripts/verify_wms_bugs.py 新增的静态断言
checks.append((
    'AI-SUPPLIER-EVAL-001',
    "'supplier_evaluation'" in read_text('app/ai/policies.py')
    and "'supplier_evaluation': _tool(" in read_text('app/ai/tools/registry.py')
    and "_ai_capability_allowed('supplier_evaluation')" in function_body(
        routes_source(), 'api_supplier_evaluation'),
    '供应商评估端点必须登记能力键并做能力校验，禁止裸 login_required 直连 LLM',
))
```

**风险**：低。唯一副作用是 `viewer`/`user` 失去该页面——**这是期望行为**。

**同批顺手做的事**：全局扫描所有 `_ai_call_llm_*` 调用点，确认没有第二条漏网。执行命令：

```bash
grep -rn "_ai_call_llm_chat\|_ai_call_llm_intent\|call_llm(" app/app.py app/routes/*.py \
  | grep -v "def _ai_call_llm" | wc -l
```

对每个命中点核对其所在函数是否受 `_ai_capability_allowed` 或 `require_ai_role` 保护，产出**一次性清单**（若发现新的漏网，并入本项一并修，仍算 1 个原子动作）。

> **实测提示**：`_ai_call_llm_chat(prompt)` 在 `app/app.py` 中有 **5 处**命中（行 `29706` / `29822` / `32508` / `32685` / `32858`）。其中 `32508` 即本项已确认漏网的供应商评估。**其余 4 处必须在实施时逐一核对能力键登记情况**——它们同属"商品分析类"端点，风险画像相似，很可能存在同类漏网。这 5 处合并为 **1 个原子动作**提交。

---

### P0-1 AI 名实对齐

**问题（已实测确认）**

诊断报告的核心硬数据：**319 个 `_ai_*` 函数，仅 18 个（5.6%）真的调用 LLM；9 个名字带"智能/分析"的函数 0% 调 LLM；13 个 `ai_*_page` 页面 0% 调 LLM。**

已定位的前端文案与数据来源对照：

| 位置 | 当前文案 | 实际数据来源（实测行号） |
|---|---|---|
| `app/templates/ai_replenishment_smart.html:2` | 智能补货建议 | `_ai_smart_replenishment_report`（`app/app.py:17320`）——纯规则 |
| `app/templates/ai_replenishment_smart.html:8,9` | 基于AI分析的智能补货建议 | 同上 |
| `app/templates/ai_replenishment_smart.html:84` | 表头 `AI建议` | `app/app.py:17385-17395` 的**硬编码 if/else 字符串** |
| `app/templates/ai_replenishment_smart.html:110` | `{{ row.ai_suggestion }}` | 同上（如"该物料已断货，建议立即紧急补货"） |
| `app/templates/ai_supplier_evaluation.html:2,8` | 供应商智能评估 | `api_supplier_evaluation`——**这条真调 LLM**，文案可以留 |
| `app/templates/base.html:2521,2524` | 导航浮层链接 | — |
| `app/templates/in_order_detail.html:1342` | `<strong>AI建议：</strong>` | 待核实（同一批处理） |
| `app/templates/out_order_detail.html:1349` | `<strong>AI建议：</strong>` | 待核实 |
| `app/templates/ai_document_confirm.html:303,306` | AI 建议编号/分类，可修改 | OCR 真实 LLM 链路，**可保留** |

**关键区分（必须遵守原则）**

> **不能一刀切把"AI"字样全删。** 判断标准是"这个结论是不是模型生成的"：
> - 真调 LLM（`ai_supplier_evaluation`、`ai_document_confirm` 的 OCR）→ **保留 AI 字样**
> - 纯 if/else 规则（`ai_suggestion` 的 6 条硬编码）→ **改名 + 标注依据**

**修复动作**

采用 **决策 D3 的选项 B**（折中）：

1. `app/app.py:17385-17395` 的 6 条硬编码建议字符串，**不改逻辑**，但把字段名与文案分离：
   - 表头 `AI建议` → **`系统建议`**
   - 列头下方加副标题：`基于库存/消耗阈值的规则判断，非模型生成`
2. 页面主标题 `智能补货建议` → **`补货建议（规则）`**；`基于AI分析的智能补货建议` → **`基于近 N 天消耗与库存覆盖天数的规则判断`**
3. `ai_replenishment_smart.html:84,110` 的 CSV 导出表头（`app/app.py:19892` 附近）同步改成 `系统建议`
4. `in_order_detail.html` / `out_order_detail.html` 的 `AI建议：` **已核实为真 LLM 输出**（`app/routes/in_order.py:1467` 调 `_ai_call_llm_chat`，且端点已有 `@require_role('warehouse')`）——**保留 AI 字样不改**（该两端点本轮记为可接受残留，未新增能力键）
5. 导航浮层（`base.html:2521,2524`）的链接文案同步

**验证方式**

```bash
# 模板与后端导出的表头必须一致（不能一个叫 AI建议、一个叫 系统建议）
grep -rn "AI建议\|智能补货" app/templates/ app/app.py

# 静态断言（写进 tests/verify_ai_naming_truthfulness.py）
# T1: ai_replenishment_smart.html 不含 "AI建议"
# T2: 该模板含"规则"或"非模型生成"字样
# T3: ai_supplier_evaluation.html 仍保留 "智能"（证明不是无脑全删）
# T4: CSV 导出表头与模板表头字符串相同
```

**风险**：低（纯文案）。**注意**：模板改动需 **WMS 重启**才生效（AGENTS.md R3）。

---

### P0-2 反馈闭环最小版

**问题（已实测确认）**

```python
# app/ai/audit.py:144  写入
def create_feedback(user_id, rating, ai_run_id=None, ai_message_id=None,
                    error_type=None, note=None) -> AIFeedback: ...

# app/ai/audit.py:166  读取
def list_feedbacks(user_id=None, limit=50) -> list[AIFeedback]: ...

# app/ai/routes.py:275  POST /feedback  → create_feedback
# app/ai/routes.py:314  GET  /feedback  → list_feedbacks（仅按 user_id 过滤）
```

`AIFeedback` 模型（`app/ai/models.py:58`）**字段是齐的**：`rating` / `error_type` / `note` / `ai_run_id` / `created_at`，还有两个索引。

**唯一的问题**：`list_feedbacks` 只被 `feedback_list` 自己调用，**没有任何运营侧的消费者**——用户打了差评，进数据库就沉底了。

**修复动作（最小版，不新建表）**

1. 在 `app/ai/routes.py` 新增 `GET /ai/feedback/review_queue`（`@require_role('admin')`）：
   - 查 `AIFeedback.rating == 'bad'`（或 `rating` 非正面的全部取值，实施时先确认真实枚举）
   - 按 `error_type` 分组统计，输出：**待修清单**（error_type × 数量 × 最近一次时间 × 样例 note）
2. 在 `ai/replenishment_smart` 或 `admin_insights` 页面加只读区块，展示该清单
3. 物料别名纠错沉淀：`app/app.py` 中已存在 **`_ai_ff_save_feedback_record`（:14318）** 与 **`_ai_ff_query_feedback_records`（:14348）**——先核实这两者与 `AIFeedback` 的关系（**实施第一步就是读这两段代码**），避免重复造轮子

**验证方式**

```bash
# 新测试 tests/verify_ai_feedback_loop.py
# T1: review_queue 路由存在且 @require_role('admin')
# T2: 造 3 条 bad 反馈 → 调 review_queue → 断言按 error_type 分组且返回 3
# T3: viewer 调 review_queue → 403
# T4: review_queue 是只读（不得出现 db.session.add/commit）
```

**风险**：低。纯读接口 + 只读页面。

---

### P0-3 建议带置信度

**问题**

AGENTS.md **R5** 要求"AI 低置信度必须回落人工"。当前 LLM 链路有置信度（`app/app.py:5148` 的 `confidence`、`:13307` 的 `_ai_vision_low_confidence_items(threshold=0.75)`），但**规则型建议（占比 94.4%）完全没有置信度概念**。

**修复动作**

不引入新表，在**返回结构里加字段**：

```python
# 以 _ai_smart_replenishment_report（app/app.py:17320）为例
row = {
    ...,
    'ai_suggestion': ai_suggestion,
    'suggestion_basis': 'rule',        # rule | llm
    'suggestion_confidence': 0.9,      # 规则型按阈值距离计算；LLM 型取模型值
    'needs_review': False,             # confidence < 阈值时为 True
}
```

**置信度计算原则（规则型）**：不编造模型概率，用**可解释的阈值距离**：

| 规则分支 | 置信度依据 |
|---|---|
| 库存 < 安全库存 | `min(0.95, 0.5 + (min_stock - stock) / min_stock * 0.45)` |
| 近 90 天无出库（呆滞） | 固定 `0.8`（判定简单，但"呆滞"结论需人工确认） |
| 消耗趋势类 | 按样本天数折算：`min(0.9, 样本天数 / 90 * 0.9)` |

前端：`needs_review == True` 的行加黄色标记 + hover 说明"该建议依据不足，请人工复核"。

**验证方式**

```bash
# tests/verify_ai_suggestion_confidence.py
# T1: 报告返回的每行都含 suggestion_basis / suggestion_confidence / needs_review
# T2: 构造 stock=0, min_stock=100 → confidence >= 0.9
# T3: 构造 样本天数=10 → confidence <= 0.1（证明是算出来的不是常量）
# T4: needs_review 与 confidence 阈值严格一致
```

**风险**：低。**但注意**：置信度阈值一旦对外，就成了**业务承诺**——建议第一版阈值只用于"标黄提示"，不用于"自动阻断"。

---

## 二、P1 修复项 — 去重与收口

### P1-8 合并重复的补货实现

**问题（已实测确认）**

两个函数，同一份业务语义，两处代码：

| 函数 | 行号 | 行数 | 服务路由 | 模板 |
|---|---|---|---|---|
| `_ai_replenishment_report` | `app/app.py:17210` | 94 行 | `/ai/replenishment` | `ai_replenishment.html` |
| `_ai_smart_replenishment_report` | `app/app.py:17320` | 136 行 | `/ai/replenishment_smart` | `ai_replenishment_smart.html` |

两者签名几乎相同：

```python
def _ai_replenishment_report(days=30, coverage_days=30, limit=100, only_action=False)
def _ai_smart_replenishment_report(days=30, coverage_days=30, limit=200, only_action=False)
```

差异集中在：`limit` 默认值、趋势符号、优先级评分、`ai_suggestion`。**这正是"同逻辑两处代码，迟早不一致"的典型样本**——事实上 `ai_suggestion` 只在 smart 版本里有（`app/app.py:17385-17395`），另一个版本没有。

**修复动作**

1. **保留 `_ai_smart_replenishment_report` 作为唯一实现**（它是超集）
2. `_ai_replenishment_report` 改为**薄适配层**：

```python
def _ai_replenishment_report(days=30, coverage_days=30, limit=100, only_action=False):
    """兼容层：老页面 /ai/replenishment。全部逻辑下沉到 smart 实现。
    # AI-DEDUP-REPLENISH-001：禁止在此重复实现业务逻辑。
    """
    report = _ai_smart_replenishment_report(
        days=days, coverage_days=coverage_days, limit=limit, only_action=only_action)
    # 老模板不认识的字段直接忽略即可（Jinja 未引用），无需裁剪
    return report
```

3. 在 `DEVELOPMENT_RULES.md` 增加一条：**同一业务语义不得有两处实现**（已有 A1–A11，这是 A12 的候选）
4. `scripts/verify_wms_bugs.py` 加断言：`_ai_replenishment_report` 函数体行数 < 15 且不含 `Material.query`

**验证方式**

```bash
# 两个页面渲染结果的关键字段必须一致
PYENV_VERSION=3.11.1 python3 -m pytest tests/ -q -k "replenishment"
# 新增 T: 构造同一批物料 → 两函数返回的 rows 长度与 suggested_qty 逐条相等
```

**风险**：中。老页面可能依赖 smart 版本没有的字段 → **先跑一次两页面 diff 对比**（实施第一步）。

---

### P1-6 销售订单库存占用 ⚠️ 方案已修正

**我改了口径，请务必看这段**

原诊断的建议是"加 `reserved_quantity` 字段"。**实测后我认为那是个陷阱**，理由如下。

**实测发现（关键）**

销售链路的库存校验现状：

| 环节 | 位置 | 是否校验库存 |
|---|---|---|
| 销售下单（建 `SalesOrder`） | `app/routes/sales.py:132`（Excel 导入）/ 手工建单 | ❌ **不校验** |
| 下推生成出库草稿 | `app/routes/sales.py:360-400` | ❌ **不校验**（只校验数量不超未发货量 + 是否有 pending 草稿） |
| `build_sales_outbound_draft` | `app/app.py:33213` | ❌ **不校验** |
| 出库完成 | `app/routes/out_order.py:925-947` | ✅ 校验仓库级 `get_warehouse_stock_quantities`，不足则 `api_error` |

**所以真实的问题是**：`SalesOrder` 表头有 `shipped_amount` / `remaining_amount` / `shipment_status`，`SalesOrderItem` 有 `shipped_quantity`——**这是"已发货"口径，不是"可用量"口径**。销售在系统里下单时，系统对库存**一无所知**；等到仓库去出库时才发现没货。这就是"超卖"的实际发生路径。

**为什么加字段是陷阱**

1. `reserved_quantity` 是**第四套库存口径**——今天刚建立的 `INVENTORY_TRUTH.md` 三口径铁律（①总账 ②库位账 ③流水）会立刻被打破，A11 规则也管不住它
2. 有了字段就要维护：下单加、下推减、取消回滚、部分发货怎么算、仓库改单怎么同步——**每个生命周期节点都是一个新 BUG 温床**（参考 R2 的 20+ 多仓 BUG 就是这么来的）
3. 库存占用本质是**查询**，不是**状态**：`可用量 = 仓库级库存 − 已承诺未发量`，后者可由 `SalesOrderItem` 实时算出，**不需要存**

**修正后的推荐方案：软占用（派生计算）+ 双重校验**

**改动 1：新增一个派生函数**（放 `app/utils.py` 或 `app/routes/sales.py`）

```python
def get_committed_quantities(warehouse_id, exclude_sales_order_id=None):
    """返回 {material_id: 已承诺未发数量}。

    口径：status='confirmed' 且 shipment_status != 'shipped' 的销售订单，
    其 (quantity - shipped_quantity) 之和。
    # STOCK-TRUTH: 派生值，不落库；可用量 = get_warehouse_stock_quantities - 本函数
    """
```

**改动 2：下单时软校验（提示，不阻断）**

`app/routes/sales.py` 建单/改单路径加：

```
若 可用量 < 本次下单量：
    返回 warning（非 error），msg 形如
    "物料 8*25螺丝 在 主仓 可用量 100，本单占用 150，缺口 50。可继续，但请与仓库确认。"
```

**改动 3：下推断言（阻断，这次是硬校验）**

`app/routes/sales.py:360` 附近，在建出库草稿前：

```
若 可用量 < 下推数量：
    return 400，提示"缺口 N，请先补货或调整数量"
```

> **为什么下推要硬、下单要软**：下单是**承诺**（可以对客户说"我尽快安排"），下推是**作业指令**（一旦生成草稿，仓库就会去拣货）。在作业指令上硬拦，才不会让工人跑到库位发现没货。

**改动 4：可用量口径写入文档**

`INVENTORY_TRUTH.md` §2.2 增加一行：

| 用途 | 口径 | 理由 |
|---|---|---|
| 销售可承诺量 | `get_warehouse_stock_quantities(wh) − get_committed_quantities(wh)` | 派生，不落库 |

**执行编排（为什么这个顺序对了）**

`P0-1 A11 规则` → `P0-4 治理收口` → **P1-6 引进新的库存口径** ——新的 `get_committed_quantities` 是只读派生函数，**不触碰任何写入口**，所以不会成为 A11 的违规源。这是它排在 P1-5/P1-7 之前的原因。

**验证方式**

```bash
# tests/verify_sales_stock_commitment.py
# T1: 单仓库场景 — 库存 100，已确认订单占用 80，新单 30 → warning 且 msg 含缺口 10
# T2: 下推场景 — 同一数据 → 400 且 msg 含"缺口"
# T3: exclude_sales_order_id 生效（改单时不把自己的旧量算进占用）
# T4: shipment_status='shipped' 的订单不计入占用
# T5: **多仓回归** — A 仓有货、B 仓无货，B 仓下单必须提示缺口（防 R2 类回归）
# T6: 派生函数不写库（断言无 db.session.add/commit）
```

**风险**：中。**必须做 T5 多仓测试**——这个系统 20+ 个多仓 BUG 的根源就是踩了"只看全局库存"的坑。

---

### P1-5 销售退货入库单

**问题**

实测全库检索 `销售退货` / `SalesReturn` / `PurchaseReturn`：

```
app/app.py:2470   'label': '采购退货必须关联订单'
app/app.py:2473   'remark': '为后续采购退货流程预留；采购退货必须关联原采购订单或采购入库来源。'
```

**`SalesReturn` 类不存在（0 处）**。销售退货目前无处落账：客户退回的货，仓库要么走"其他入库"变通（丢了与原销售单的关联，退货率无法统计），要么干脆不入账。

**已有可复用资产（这决定了方案走向）**

- `AfterSaleOutOrder`（售后出库，`after_sale_out_draft` 能力）——**方向相反**，是"给客户补发"，不是"收客户退回"
- **`InOrder` 的 `business_type` 已是自由字符串**（`app/app.py:5396`，默认 `'采购入库'`）——**枚举扩展零成本，无需迁移**
- **`InOrder.customer_id` 已存在**（`app/app.py:5395`），注释："其他入库 / 客供料归属方"——**退货入库的客户归属字段已经在了**
- `InOrder.source_purchase_order_id` 已存在（`app/app.py:5399`）
- **`InOrder.source_sales_order_id` 不存在（已实测确认，需新增列 + 迁移）**
- `InOrderItem` 有 `source_purchase_order_item_id`（`app/app.py:5422`）和 `is_customer_supplied`（`:5430`）

**推荐方案（对应决策 D2 选项 A）：复用 `InOrder`，不新建模型**

| 改动 | 内容 |
|---|---|
| **1. 扩展 `business_type`** | 新增取值 `销售退货入库`。**该字段是 `db.String(50)` 自由字符串，零迁移成本**（对照 `app/app.py:5396`） |
| **2. `InOrder` 加 `source_sales_order_id`** | 已实测确认**不存在**，需新增。有 `OutOrder.source_sales_order_id`（`app/app.py:5456`）先例可照抄；同时加冗余 `source_sales_order_no`（照抄 `SalesOrder.contract_no` 的"历史单据不变"模式） |
| **2b. 复用 `customer_id`** | 退货入库的客户归属**直接用现有字段**（`:5395`），不要再造 `return_customer_id` |
| **3. `InOrderItem` 加 `source_sales_order_item_id`** | 用于计算"某销售订单行的退货数量"，防止超退 |
| **4. 退货数量校验** | 仿 `sales_outbound_remaining_check`（`app/routes/out_order.py:925` 处调用），新增 `sales_return_remaining_check`：退货量 ≤ 原行发货量 − 已退量 |
| **5. 入库时走标准库存写入口** | 必须用 `add_stock` + `update_location_inventory` **成对调用**（`INVENTORY_TRUTH.md` §2.1 的硬约束——`add_stock` 不自动同步库位账） |
| **6. 权限** | 沿用 `in_order_draft` 能力键（`warehouse`）；**不新增 AI 能力**（退货是高敏动作，AI 不参与） |
| **7. 迁移脚本** | `source_sales_order_id` 是新增列，需照抄 `backfill_stock_txn_warehouse_id()` 的**幂等启动回填**模式（`app/app.py`）。存量退货入库单（若有）历史归属留空，**不猜**——这与 `INVENTORY_TRUTH.md` §3 的铁律一致 |

**验证方式**

```bash
# tests/verify_sales_return_inbound.py
# T1: 退货入库后 ①material.stock ②location_inventory ③stock_transaction 三者增量一致（核心！）
# T2: stock_transaction.warehouse_id 正确归属（不得为 NULL）——对照 INVENTORY_TRUTH.md §3
# T3: 退货量 > 原发货量 → 400 拒绝
# T4: 一张销售订单多行退货，各行独立计限
# T5: 退货入库不产生 AI 草稿（能力键未登记 → 静默拒绝是正确的）
# T6: 重复提交幂等（照抄 OutOrder 的 _acquire_order_write_lock 模式）
```

**风险**：**高**。这是本方案唯一引入新库存流入路径的项。

> **强制要求**：实施前必须先写 `INVENTORY_TRUTH.md` 的对应章节（新增写入口清单一行），**文档先行**——否则新代码会绕过 A11 的约束。

---

### P1-7 采购退货单

**问题**

同上一节的实测结果——类不存在，但**开关已存在**：

```
app/app.py:2469   'key': 'purchase_return_requires_order'
app/app.py:2470   'label': '采购退货必须关联订单'
app/app.py:2471   'default': '1'
app/app.py:2473   'remark': '为后续采购退货流程预留...'
```

**这意味着**：产品设计时已经想清楚了规则（"必须关联原采购订单或采购入库来源"），只是流程没实现。**方案应该与 P1-5 保持同构**，降低理解成本。

**推荐方案**

| 改动 | 内容 |
|---|---|
| **1. 复用 `OutOrder`** | `business_type = '采购退货出库'`（货是退给供应商，方向是出库） |
| **2. 关联来源** | `OutOrder` 已有 `source_sales_order_id`，新增 `source_in_order_id` / `source_purchase_order_id` |
| **3. 尊重既有开关** | 读取 `purchase_return_requires_order`，为 `1` 时（默认）**强制**关联来源，为空则 400 |
| **4. 出库走标准扣减** | `deduct_stock_atomic` + `deduct_location_inventory_atomic` 成对（对照 `complete_out_order` 现有写法 `app/routes/out_order.py:948-968`） |
| **5. 数量校验** | 退货量 ≤ 原采购入库量 − 已退量 |

**验证方式**：与 P1-5 同构，重点仍是三账一致性（T1）与 `warehouse_id` 归属（T2），外加：

```bash
# T7: purchase_return_requires_order=1（默认）时，不填来源 → 400
# T8: purchase_return_requires_order=0 时，不填来源 → 放行（开关真实生效）
```

**风险**：中高。但与 P1-5 同构，**建议 P1-5 验收通过后再做**，复用其测试骨架。

---

## 三、P2 修复项（增强）

### P2-9 采购在途计算收口为单一函数

**问题**：诊断指出采购在途在多处重复实现。已定位的相关点：`app/app.py:10133`（逾期未到）、`:14049`、`:14075`、`api_supplier_evaluation` 的 `recent_orders` 统计。

**动作**：
1. 先做**消费点普查**：`grep -rn "received_quantity\|in_transit\|在途" app/app.py app/routes/*.py`
2. 定义唯一口径：`在途 = Σ(purchase_order_item.quantity − received_quantity)`，条件 `PurchaseOrder.status in ('pending','partial')`
3. 抽出 `get_purchase_in_transit(material_id=None, supplier_id=None)`，逐点替换
4. 加 R6 类型的静态检查（AGENTS.md R6：同一根因必须检查所有消费方）

**验证**：替换前后对同一数据集做数值 diff，**必须完全相等**（否则说明有实现是错的，那是另一个 BUG）。

**风险**：中。收口类改动容易漏消费点，**普查必须彻底**。

### P2-10 供应商履约指标

**关键前提（实测）**：`PurchaseOrderItem`（`app/app.py:6531`）字段是 `quantity` / `received_quantity` / `price` / `amount` / `remark` / `contract_id` / `contract_no` / `project_name`——**没有任何实际到货日期字段**。`PurchaseOrder.expected_date`（`:6517`）是**预计**日期。

**所以"到货准时率"当前算不出来**，必须先加字段：

```python
# PurchaseOrderItem 新增
actual_arrival_date = db.Column(db.Date)   # 实际最后一次到货日期
```

**动作顺序**：
1. 加字段 + 幂等启动回填（照抄 `backfill_stock_txn_warehouse_id()` 模式，从 `InOrder` 反查）
2. 入库完成时写入 `actual_arrival_date`
3. `api_supplier_evaluation` 复用已有的价格 CV 计算（`app/app.py:32440-32458`，已实现且正确），新增准时率：`准时 = actual_arrival_date <= PurchaseOrder.expected_date`
4. **顺手补 P0-4**（该端点需要能力键登记）

**风险**：低（纯增量字段）。

### P2-11 AI 建议 → 一键生成草稿

**价值**：这是"AI 在 WMS 的最大价值释放点"——补货建议、库存健康建议，目前只是**看**，看完还得手工建单。

**动作**：把现有建议行的 `material_id` / `suggested_qty` 接到已注册的 `purchase_request_draft` 能力（`app/ai/policies.py:52`），在建议表格加"生成请购草稿"按钮。

**强制边界（不可妥协）**：
- AI 只能创建 `status='pending'` 草稿（`AI_FORBIDDEN_RISK_LEVELS` 明令禁止 `submit`/`audit`/`stock_write`）
- `confirmation_required=True`——必须走人工确认页
- 一次确认令牌只生成一张草稿（`AI_PERMISSION_MATRIX.md` 维护要求 3）

**风险**：中。**注意**：不要为了让按钮"更好用"而绕过确认页——那会直接违反 `AI_FORBIDDEN_RISK_LEVELS`。

---

## 四、不做的部分（明确取舍）

| 项 | 结论 | 理由 |
|---|---|---|
| P3-12 应收/应付/账期 | **维持不做** | 单人记账场景未必需要；且引入后需对接财务口径，成本远超收益 |
| P3-13 客户信用额度 | **维持不做** | 依赖应收数据，同上 |
| P3-14 批次/序列号 | **维持不做** | `WMS_BUSINESS_SCOPE.md` 已明确边界，**不要反复动** |
| 94.4% 规则化 | **不改成 LLM** | 诊断报告已论证：规则化对 WMS 常常是**正确**的（确定性、可审计、零成本、离线可用）。问题在**命名**不在**实现** |

---

## 五、执行看板

> **执行进度（2026-09-11 更新）**：第 1 批 3 项已全部完成并推送——
> P0-4（提交 8846a78，AI-LLM-GATE-002：5 个漏网 LLM 端点补门禁，另发现 2 个孤儿端点复用既有键）、
> P0-1（提交 06c2340，AI-NAMING-TRUTH-001：规则页改名+标注依据；单据"AI建议"经核实为真 LLM 输出，保留）、
> P1-8（提交 035991f，AI-DEDUP-REPLENISH-001：补货报告 94 行重复实现并入 smart 版，等价性测试证明零行为差异）。
> 全量回归 1482 passed / 7 failed（7 项均为改动前已存在的打印条码环境性失败，与改动无关）。
> D1/D2 仍待拍板，阻塞第 3 批。

| ID | 任务 | 批 | 依赖 | 需拍板 | 风险 | 预估 |
|---|---|---|---|---|---|---|
| P0-4 | 补齐 AI 治理漏洞 | 1 | — | | 低 | 0.5 天 |
| P0-1 | AI 名实对齐 | 1 | — | D3 | 低 | 1 天 |
| P1-8 | 合并重复补货实现 | 1 | — | | 中 | 0.5 天 |
| P0-2 | 反馈闭环最小版 | 2 | P0-4 | | 低 | 1 天 |
| P0-3 | 建议带置信度 | 2 | P0-1 | | 低 | 1 天 |
| P1-6 | 销售订单库存占用（修正版） | 3 | P0-1/P0-4 | **D1** | 中 | 2 天 |
| P1-5 | 销售退货入库单 | 3 | P1-6 | **D2** | **高** | 3 天 |
| P1-7 | 采购退货单 | 3 | P1-5 | | 中高 | 2 天 |
| P2-9 | 采购在途收口 | 4 | — | | 中 | 1.5 天 |
| P2-10 | 供应商履约指标 | 4 | P0-4 | | 低 | 1.5 天 |
| P2-11 | 建议一键生成草稿 | 4 | P0-3 | | 中 | 1.5 天 |

**合计约 15 人日**。第 1 批（3 项，2 天）即可消除已证实的治理漏洞与信任风险，建议**本周先干完第 1 批**。

---

## 六、上线注意（容易漏）

1. **模板改动必须重启 WMS**（AGENTS.md R3）。涉及：`ai_replenishment_smart.html`、`base.html`、`in_order_detail.html`、`out_order_detail.html`。
2. **数据模型改动必须走幂等启动回填**，不得直接 `ALTER TABLE` 后假设数据已就绪（`backfill_stock_txn_warehouse_id()` 是标准范式）。
3. **每个新单据类型都要问一次**：它的库存写入口是否成对调用了 `add_stock`/`deduct_stock_atomic` **和** `update_location_inventory`？这是 `INVENTORY_TRUTH.md` §2.1 的硬约束，也是三账分裂的历史根因。
4. **每个新端点都要问一次**：能力键是否"四处齐"？少一处 = 静默拒绝（不是报错，是**永远 403**）。
5. **多仓回归必须做**：这个系统的 20+ 个多仓 BUG 全部源于"只看全局库存"。任何涉及库存校验的改动，**必须有 A 仓有货 / B 仓无货的测试**。

---

## 七、一句话结论

> **14 项里，只有 3 项需要业务决策；真正紧急的是 `api_supplier_evaluation` 这个已证实的治理漏洞（30 分钟可修）。**
> **最大的方案修正：销售库存占用不要加字段——它是查询不是状态，加字段等于亲手制造第四套库存口径，会立刻推翻刚立的 `INVENTORY_TRUTH.md` 三账铁律。**
> **最大的方案克制：销售退货复用 `InOrder`、采购退货复用 `OutOrder`，不新增模型——第 90 个 `db.Model` 和第 4 套单据流是这个系统最不需要的东西。**

---

## 附：本方案的核实记录

| 结论 | 核实方式 | 证据 |
|---|---|---|
| `api_supplier_evaluation` 未注册能力键 | 读源码 + grep 四个登记表 | `app/app.py:32407-32409` 只有 `@login_required`；四表均无该键 |
| 供应商评估**确实**调 LLM | 读函数体 + grep | `app/app.py:32508` `_ai_call_llm_chat(prompt)` |
| 销售链路零库存校验 | 逐段读下单/下推/建草稿/出库完成 | 前 3 处无校验，仅 `app/routes/out_order.py:925-947` 有 |
| `SalesReturn` 不存在 | 全库 grep | 仅命中 2 处"采购退货"配置文案，无类定义 |
| `PurchaseOrderItem` 无到货日期 | 读模型定义 | `app/app.py:6531-6551` 无 `actual_arrival_date` |
| 反馈无消费者 | grep `list_feedbacks` 调用点 | 仅 `app/ai/routes.py:318` 自身路由 |
| 两个补货实现重复 | 读两个函数 | `app/app.py:17210`(94行) vs `:17320`(136行) |

> **未核实项（实施第一步必须先看）**：
> 1. ~~`in_order_detail.html:1342` / `out_order_detail.html:1349` 的 `AI建议` 数据来源~~ → **已核实：真 LLM 输出，文案保留**（见 P0-1 第 4 条）
> 2. `_ai_ff_save_feedback_record`（`:14318`）与 `AIFeedback` 的关系，避免 P0-2 重复造轮子
> 3. ~~`InOrder` 是否已有 `source_sales_order_id`~~ → **已核实：不存在，需新增列**（见 §3.5）
> 4. `AIFeedback.rating` 的实际取值枚举（决定 P0-2 的差评筛选条件）
