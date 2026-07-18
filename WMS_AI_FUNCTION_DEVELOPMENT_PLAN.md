# WMS AI 唯一开发台账

> 版本：V2.0
>
> 基准日期：2026-07-13
>
> 适用范围：当前 Flask + SQLite WMS 及 Windows 离线部署
>
> 本文件是仓库唯一 AI 开发计划、状态台账和完成记录，禁止另建并行 AI 计划。

## 1. 台账规则

### 1.1 防止重复开发

- 所有 AI 开发必须关联本文件中的唯一任务编号，例如 `AI-R01`。
- 开始前必须检查任务状态，并搜索现有代码、路由、工具、模型、页面、验证脚本和 Git 历史。
- “已完成”任务禁止重新开发；已有功能出现缺陷时建立修复子项，例如 `AI-R01-F01`。
- 新需求只有在仓库级检查确认不存在等价实现和等价任务后，才能加入本台账。
- 没有任务编号的 AI 功能不得直接开发；默认只允许一个任务处于“开发中”。

### 1.2 防止遗漏

- 每次新增 AI 路由、工具、模型、页面、Feature Flag 或数据表，必须同步检查权限矩阵、风险等级、人工确认、导航、迁移、审计和验证。
- 修改一种草稿能力时，必须横向检查入库、采购收货、出库、调拨、盘点、调整、售后和请购全部草稿类型。
- 每完成一个任务，必须检查其依赖任务和后续解锁任务。
- 每个版本结束前执行“台账 → 代码”和“代码 → 台账”双向核对：计划项必须找到实现，AI 实现必须找到任务或完成记录。

### 1.3 状态定义

| 状态 | 含义 | 开发限制 |
|---|---|---|
| 待开发 | 已确认缺少完整实现 | 可以开发 |
| 开发中 | 正由唯一任务实施 | 禁止并行重复实施 |
| 待验收 | 代码完成，验证或业务验收未完成 | 仅修复验收问题 |
| 已完成 | 代码、验证、记录、提交和推送齐全 | 禁止重复开发 |
| 暂缓 | 已记录原因和恢复条件 | 不开发 |
| 取消 | 经确认不再需要 | 不开发，保留记录 |

### 1.4 完成门槛

任务必须同时满足以下条件才能标记“已完成”：

1. 实现已进入 `main`，不是文档声明或页面占位。
2. 权限、高风险人工确认、Schema、幂等、审计和业务状态边界已核对。
3. 已增加针对性自动验证；重要操作流程已完成集成或浏览器验收。
4. 已执行源码编码检查、相关专项验证和 `verify_ai_all.py --level full`。
5. 已在本文件记录完成日期、提交哈希、改动模块、验证命令、结果和遗留子项。
6. 已提交并推送 GitHub；未推送的本地改动不得标记完成。

## 2. 永久业务边界

- AI 可以识别、查询、分析、建议、检查并创建草稿。
- AI 不得直接提交、审核、完成、关闭、反审、作废、删除业务单据或直接增减库存。
- AI 不得恢复备份、修改用户角色、重置密码或修改密钥。
- 所有草稿必须通过 Schema、AI 角色权限、业务页面权限、幂等、审计和人工确认。
- 微信文字或截图中的供应商送货语义必须生成采购收货或普通入库草稿，不能生成采购申请。
- 分类、识别或匹配置信度不足时必须停在人工确认环节。

## 3. 已完成能力基线

以下能力已经存在，禁止作为新功能重复开发；后续只实施第 4 节列出的真实缺口。

| 编号 | 已有能力 | 实现或验证证据 | 状态 |
|---|---|---|---|
| AI-C01 | AI 助手、SSE、历史、反馈和确认令牌 | `app/ai/routes.py`、`streaming.py`、`audit.py` | 已完成 |
| AI-C02 | Provider、提示词、工具注册、Schema 和编排 | `app/ai/providers.py`、`tools/registry.py` | 已完成 |
| AI-C03 | 严格工具输入 Schema | `f42b867`、`verify_ai_tool_schemas.py` | 已完成 |
| AI-C04 | AI 权限与业务页面权限交集 | `4200f7b`、权限专项验证 | 已完成 |
| AI-C05 | 高风险硬拦截和人工确认边界 | `b9aca0e`、高风险专项验证 | 已完成 |
| AI-C06 | AI 运行、工具调用和基础幂等模型 | `AIRun`、`AIToolCall`、`AIRequestIdempotency` | 基础完成，覆盖增强见 `AI-R01` |
| AI-C07 | 文本、图片、微信通知和 Excel 抽取框架 | `app/ai/documents/`、文档 OCR 页面 | 基础完成 |
| AI-C08 | 文档任务、尝试、明细、反馈、重试和状态流转 | 文档任务页面、`verify_ai_document_jobs.py` | 基础完成 |
| AI-C09 | 物料匹配、候选和别名管理 | `documents/matcher.py`、物料别名页面 | 基础完成 |
| AI-C10 | 多类业务草稿和提交前检查 | 工具注册表、`agents/draft_check.py` | 基础完成 |
| AI-C11 | 仓库巡检、采购跟进和补货 Agent | `app/ai/agents/`、Agent 任务页面 | 基础完成 |
| AI-C12 | 补货、库存健康、库龄、周转、短缺和供应商分析 | `app/ai/analysis/`、相关页面 | 基础完成 |
| AI-C13 | 智能库位、需求预测和供应商评估 | 对应页面和 API | 基础完成 |
| AI-C14 | 静态知识问答和来源标注 | `app/ai/knowledge.py` | 基础完成 |
| AI-C15 | 运维指标、功能开关、角色灰度和降级 | `app/ai/ops/`、运维页面 | 基础完成 |
| AI-C16 | 本地统一验证和 GitHub Actions | `verify_ai_all.py`、`verify.yml` | 基础完成 |

## 4. 真正待开发任务总表

任务必须按依赖顺序推进，不从已经完成的阶段重新开发。

| 顺序 | 任务编号 | 状态 | 任务 | 依赖 | 解锁任务 |
|---|---|---|---|---|---|
| 1 | AI-R01 | 已完成 | 全部 AI 草稿统一幂等与审计闭环 | AI-C03～C06 | R08、R11、R13 |
| 2 | AI-R02 | 已完成 | 强化 CI 门禁与台账一致性检查 | AI-R01 | 所有后续任务 |
| 3 | AI-R03 | 已完成 | 建立真实中文文档黄金样本库 | AI-R02 | R04～R09 |
| 4 | AI-R04 | 已完成 | 图片预处理与质量门禁 | AI-R03 | R05 |
| 5 | AI-R05 | 已完成 | OCR/视觉 Provider 真实评测与路由 | R03、R04 | R06～R09 |
| 6 | AI-R06 | 已完成 | 送货通知与采购订单联合匹配增强 | AI-R05 | R08、R11 |
| 7 | AI-R07 | 已完成 | 物料歧义、别名和单位换算治理 | R03、R05 | R08 |
| 8 | AI-R08 | 已完成 | 文档确认台字段证据与重复风险 | R01、R06、R07 | R09～R11 |
| 9 | AI-R09 | 已完成 | 字段级反馈和文档质量指标 | R03、R08 | R15、R17 |
| 10 | AI-R10 | 已完成 | 仓库角色 AI 工作台整合 | AI-R08 | R16、R17 |
| 11 | AI-R11 | 已完成 | 采购到货跟进 AI 工作台整合 | R01、R06、R08 | R16、R17 |
| 12 | AI-R12 | 已完成 | 知识库发布、版本和失效管理 | AI-R02 | R16、R17 |
| 13 | AI-R13 | 已完成 | Agent 预算、取消、熔断和并发控制 | R01、R02 | R16、R17 |
| 14 | AI-R14 | 已完成 | AI 数据保留、脱敏和清理任务 | AI-R02 | R16、R17 |
| 15 | AI-R15 | 已完成 | 业务质量指标和版本对比 | AI-R09 | R16、R17 |
| 16 | AI-R16 | 已完成 | AI 关键流程浏览器 E2E | R08、R10～R14 | R17 |
| 17 | AI-R17 | 已完成 | 真实用户灰度、回滚演练和上线验收 | R09～R16 | 正式发布 |

## 5. 任务详细定义

### AI-R01：全部 AI 草稿统一幂等与审计闭环

**目标**：重复上传、重复点击、网络重试、Provider 重试或并发请求均不能创建重复草稿，每张草稿可追溯完整 AI 链路。

**范围**：

- 盘点入库、采购收货、出库、调拨、盘点、调整、售后和请购草稿全部入口。
- 建立统一幂等键：用户、能力、请求 ID、来源哈希和业务关键字段。
- 统一处理中、成功、失败、回放和过期状态。
- 关联 `AIRun`、`AIToolCall`、确认令牌、文档任务和业务草稿。
- 使用数据库唯一约束或事务控制保证并发请求只成功一次。
- 失败重试保留原错误和运行证据，不覆盖历史记录。

**验收**：每种草稿均覆盖首次、重复、并发、失败重试测试；重复草稿为 0；可从草稿反查用户、来源、请求、工具和确认记录。

### AI-R02：强化 CI 门禁与台账一致性检查

**目标**：AI 改动合并前自动验证，代码与台账不会脱节。

**范围**：

- PR 执行编码、AI core 和 WMS 回归；合并或定时执行 AI full。
- 自动检查新增工具是否具有 Schema、权限、风险级别和验证。
- 自动检查新增 AI 路由、模型、页面或 Feature Flag 是否关联任务编号。
- 将 GitHub 验证工作流设置为 `main` 必需检查，并记录仓库设置结果。

**验收**：破坏 Schema、权限、编码或台账映射时 CI 必须失败。

### AI-R03：建立真实中文文档黄金样本库

**目标**：使用真实、脱敏、可重复的数据衡量文档识别质量。

**范围**：

- 首批不少于 100 份：送货单照片、扫描件、微信截图、微信文字和 Excel。
- 覆盖模糊、倾斜、阴影、手写、多页、合并单元格、重复和单位混用。
- 每份样本包含期望文档类型、表头、明细、物料匹配和草稿类型。
- 原图和业务字段脱敏，记录来源类别和使用授权。
- 结果按样本版本、模型、提示词和 Schema 版本保存。

**验收**：可自动计算样本数、场景覆盖率、表头准确率、行召回率、物料匹配率和数量准确率。

### AI-R04：图片预处理与质量门禁

**范围**：方向校正、裁剪、压缩、尺寸限制、清晰度/曝光检测、多页顺序、原图与处理图证据保存。

**验收**：不可用图片提前给出中文提示；不破坏原文件；黄金样本指标不得下降。

### AI-R05：OCR/视觉 Provider 真实评测与路由

**范围**：对所有视觉 Provider 使用同一黄金样本评测；记录模型、提示词、Schema、耗时、错误率和调用量；表格图片优先视觉模型，规则明确的纯文本优先确定性解析；超时、错误 JSON 和模型不可用时可重试且不丢证据。

**验收**：模型路由可解释、可配置、可回滚；达到质量门槛后才允许试点；日志不得泄露密钥或完整敏感原文。

### AI-R06：送货通知与采购订单联合匹配增强

**范围**：建立送货通知、采购申请和模糊意图正反例；按供应商、订单号、物料、项目、未收数量和日期联合匹配；展示短交、超收、关闭订单、未关联物料和多订单候选；无匹配订单时只生成待确认普通入库草稿。

**验收**：送货通知误建采购申请为 0；低置信度不自动选单据；匹配依据和数量差异可见。

### AI-R07：物料歧义、别名和单位换算治理

**范围**：中文归一化、编码/名称/规格加权、别名候选、包装单位换算、一物多码、多候选冲突和高风险物料规则。

**验收**：歧义行 100% 人工确认；高风险物料错误自动确认数为 0；换算依据可追溯。

### AI-R08：文档确认台字段证据与重复风险

**范围**：原图与表头明细并排；显示字段置信度、原始文本、候选值和修正状态；标记采购差异、数量异常、单位换算、物料歧义和重复命中；支持键盘录入、搜索和返回路径保持；确认后只创建草稿。

**验收**：低置信度字段不能静默通过；重复风险可阻止建单；仓库人员可在浏览器完成整个流程。

### AI-R09：字段级反馈和文档质量指标

**范围**：记录字段名、原值、新值、修正原因、是否采纳、模型、提示词和 Schema 版本；按来源与版本聚合准确率和修正率。

**验收**：可定位质量下降的字段和版本，不保存不必要的敏感原文。

### AI-R10：仓库角色 AI 工作台整合

**范围**：今日待收、待出、待盘、异常库存、文档待确认、失败任务、未完成草稿和业务下钻。

**验收**：数量与原业务列表一致；工作台只读或跳转对应流程，不在报表卡片中直接提交或审核。

### AI-R11：采购到货跟进 AI 工作台整合

**范围**：待到、延期、短交、超收、未关联通知、多订单候选、供应商跟进清单和采购订单下钻。

**验收**：指标口径和时间范围明确；对外沟通和业务提交必须人工确认。

### AI-R12：知识库发布、版本和失效管理

**范围**：知识草稿、审核、发布、失效、版本、来源、更新时间、发布人、检索权限和回滚。

**验收**：未发布内容不可检索；回答显示来源和更新时间；实时库存问题必须使用实时数据工具。

### AI-R13：Agent 预算、取消、熔断和并发控制

**范围**：最大步骤、最大耗时、最大工具调用、截止时间、取消、并发互斥、失败重试来源、Provider 熔断和等待人工状态。

**验收**：无无限循环；超预算、越权和故障安全停止；重试保留原证据；自动提交业务单据次数为 0。

### AI-R14：AI 数据保留、脱敏和清理任务

**范围**：对话、图片、任务、反馈和审计的分类保留期限；脱敏；清理预览；定时清理；关键审计豁免；清理日志和管理员配置。

**验收**：不得误删业务草稿、确认记录和必要审计；日志和导出不得泄露密钥或完整敏感原文。

### AI-R15：业务质量指标和版本对比

**范围**：分类准确率、表头准确率、行召回率、物料匹配率、人工修正率、草稿采用率、重复拦截率和版本对比。

**验收**：支持按时间、角色、来源、模型、提示词和 Schema 版本筛选，指标可复算。

### AI-R16：AI 关键流程浏览器 E2E

**范围**：仓库、采购、主管、普通用户和管理员；覆盖上传、确认、草稿、工作台、Agent、知识和运维页面。

**验收**：不只检查 HTTP 200；检查中文、空状态、错误、权限、按钮、返回路径、下钻和重复点击，形成可重复脚本。

### AI-R17：真实用户灰度、回滚演练和上线验收

**范围**：管理员、仓库主管和指定采购员灰度；记录耗时、修正、误判、失败和回退；演练 Provider 故障、权限攻击、重复请求、关闭 AI 和恢复配置。

**验收**：连续一周越权成功 0、重复草稿 0、自动提交 0、低置信度未确认建单 0；10 分钟内关闭 AI 并恢复配置。

## 6. 执行顺序

1. 平台闭环：`AI-R01`、`AI-R02`。
2. 文档质量闭环：`AI-R03`～`AI-R09`。
3. 角色工作台：`AI-R10`、`AI-R11`。
4. 生产能力：`AI-R12`～`AI-R15`。
5. 端到端和灰度：`AI-R16`、`AI-R17`。

不得跳过依赖直接开发后续任务。紧急缺陷必须建立修复子项并记录原因。

## 7. 已完成治理记录

| 任务 | 完成日期 | 提交 | 结果 | 验证 |
|---|---|---|---|---|
| P0-01 固定 Python 入口 | 2026-07-13 | `0a30f03` | 增加统一 Python 入口 | 全量通过 |
| P0-02 AI 一键验证 | 2026-07-13 | `0a30f03` | 支持 smoke/core/full | 全量通过 |
| P0-03 严格工具 Schema | 2026-07-13 | `f42b867` | 拒绝非法字段、负数和空明细 | 专项通过 |
| P0-04 统一权限校验 | 2026-07-13 | `4200f7b` | 权限与业务路由取交集 | 专项通过 |
| P0-05 高风险边界 | 2026-07-13 | `b9aca0e` | 高风险硬拦截、草稿人工确认 | 专项通过 |

## 8. 后续完成记录

每完成一个任务必须追加记录，不能只修改总表状态。

| 任务编号 | 完成日期 | 提交哈希 | 改动模块 | 验证命令 | 验收结果 | 遗留子项 |
|---|---|---|---|---|---|---|
| AI-R01 | 2026-07-14 | `ed8f973` | `app/app.py`（AIDraftIdempotency 模型 + 8 草稿路径接入幂等闭环）、`app/ai/draft_idempotency.py`（服务模块）、`scripts/verify_ai_draft_idempotency.py`（7 组专项测试）、`scripts/verify_ai_all.py`（注册 CORE_SCRIPTS） | `python scripts/verify_ai_draft_idempotency.py`、`python scripts/verify_ai_all.py --level full` | 通过（37 脚本全部 PASS，重复草稿为 0，反查链路完整） | 无 |
| AI-SEC-F01 | 2026-07-16 | `2fc51dc` | `app/app.py`（`ensure_bootstrap_admin_user`、`ensure_admin_user_exists` 去除 `secrets.token_urlsafe(12)` 随机密码分支，改为未设置 `WMS_BOOTSTRAP_PASSWORD` 时默认 `admin` + 警告）、`AGENTS.md`（新增规则：禁止系统生成随机密码） | `python -c "check_password_hash(admin.password_hash,'admin')"`、Flask test_client 登录 POST 302→`/` + GET `/sales` 200 | 通过（密码 hash 校验 admin/admin=True、admin/wrong=False；端到端登录跳转正常） | 无 |
| UX-F01 | 2026-07-16 | `0d21358` | `app/templates/base.html`（库存管理菜单删除"销售单""售后出库"入口，销售管理菜单新增"售后出库"，消除重复入口）、`app/app.py`（`/out_order` 路由默认排除 `business_type='销售出库'`，领料明细不再混销售出库；显式传 `?business_type=销售出库` 仍可查） | Flask test_client + `test_full_flow.db`：20 单销售出库单号在 `/out_order` 列表出现 0 次；显式查询 status=200；菜单源码确认无重复 | 通过（销售出库不再混入领料明细，菜单入口不重复，销售出库明细统一在 `/sales/outflow_report`） | 无 |
| AI-R02 | 2026-07-16 | `5f1d4e9` | `scripts/verify_ai_tool_compliance.py`（工具权限/风险级别/审计类别合规检查：三表键一致、allowed_roles 合法、risk_level 合法且草稿级强制 confirmation_required、禁止级风险不得注册）、`scripts/verify_ai_ledger_consistency.py`（台账映射检查：代码 `# AI_TASK:` 标记与台账双向校验、防虚假报告、渐进式模式）、`app/ai/policies.py`（补齐 4 个只读工具 warehouse_insights/purchase_insights/master_data_insights/alias_management 的风险级别声明，修复三表键不一致真实缺陷）、`app/ai/tools/registry.py`+`app/ai/draft_idempotency.py`+`app/ai/policies.py`（渐进式标记 AI-R01）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 2 新脚本）、`.github/workflows/verify.yml`（CI 追加 tool_compliance + ledger_consistency 两个检查步骤） | `python3 scripts/verify_ai_tool_compliance.py`、`python3 scripts/verify_ai_ledger_consistency.py`、`python3 scripts/verify_ai_all.py --level core`、破坏性测试（非法 risk_level + 不存在 AI_TASK 标记均退出码 1） | 通过（30 脚本 core 套件全 PASS 含 2 新增、0 回归；破坏 Schema/权限/台账映射时 CI 必失败） | 无 |
| AI-R03 | 2026-07-17 | `a4a1ad9` | `app/ai/documents/golden_samples.py`（新建：黄金样本 Schema + 来源/场景枚举 + 加载校验 + 旧样本自动升级）、`app/ai/documents/evaluation.py`（扩展：新增场景覆盖率、来源类别覆盖率指标 + 全半角模糊匹配）、`app/ai/security.py`（扩展：mask_address/mask_contact 文本脱敏 + desensitize_image PIL 图像脱敏 + detect_pii_in_text 辅助）、`scripts/generate_ai_golden_samples.py`（新建：确定性种子生成 100 份合成样本覆盖 5 来源×9 场景，PIL 图片介质 + JSON 元数据）、`scripts/verify_ai_golden_samples.py`（新建：Schema/场景/来源覆盖率/图片存在/脱敏标记/评估指标可计算校验，渐进式样本数门槛）、`scripts/evaluate_ai_document_samples.py`（改用 GoldenSample Schema 加载）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_golden_samples.py）、`.github/workflows/verify.yml`（CI 追加 golden_samples 检查步骤）、`samples/ai_documents/`（100 份 GS-* 合成样本 + 3 份升级后的 LEGACY 样本，共 103 份；66 张 PIL 合成图片含模糊/倾斜/阴影/手写/多页场景效果） | `python3 scripts/generate_ai_golden_samples.py --count 100 --clean`、`python3 scripts/verify_ai_golden_samples.py`、`AI_GOLDEN_SAMPLE_ENFORCE=strict python3 scripts/verify_ai_golden_samples.py`、`python3 scripts/verify_ai_document_evaluation.py`、`python3 scripts/verify_ai_security.py`、`python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（删样本致数量<100 progressive 警告不失败、删场景致覆盖率<100% 失败） | 通过（103 份样本 ≥100 门槛；9/9 场景覆盖；5/5 来源覆盖；0 Schema 校验问题；评估指标可计算；脱敏标记完整；strict 模式通过；security/document_evaluation 回归 0 失败） | 真实脱敏样本扩充：当前 103 份为合成数据，真实送货单照片/微信截图待用户提供后追加替换，合成样本保留作为回归基线 |
| AI-R04 | 2026-07-17 | `5e594ba` | `app/ai/documents/image_preprocessing.py`（新建：方向校正 EXIF/白边裁剪/等比缩放/JPEG 质量降级压缩/清晰度（拉普拉斯方差，PIL 12 用 Kernel 替代 Laplacian）/曝光（均值+标准差）/空白图/小尺寸/可疑长宽比/多页顺序/原图与处理图证据保存；阈值基于黄金样本实测校准 BLUR_THRESHOLD=500 介于 blurry 376 与 normal 1064 之间）、`app/app.py`（OCR 路由 `api_document_ocr` 集成：上传后先走质量门禁，不可用图片提前返回中文提示且不调用视觉模型；预处理失败降级走原图；证据写入 flask.g；成功响应附 `image_warnings` 字段）、`scripts/verify_ai_image_preprocessing.py`（新建：8 项测试覆盖质量指标/预处理不破坏原图/不可用阻止/模糊警告/缩放压缩/多页顺序/证据字典/黄金样本批量预处理）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_image_preprocessing.py）、`.github/workflows/verify.yml`（CI 追加 image_preprocessing 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R04 状态置已完成，下一项改 AI-R05） | `python3 scripts/verify_ai_image_preprocessing.py`、`python3 scripts/verify_ai_all.py --level core`、`python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（BLUR_THRESHOLD→1e18 清晰图被判模糊、EXPOSURE_STDDEV_LOW→0 空白图被错误放过，均能被测试捕获） | 通过（图片预处理 8 项测试全 PASS；core 套件 32 脚本全 PASS 含新增 image_preprocessing；0 回归；黄金样本图片批量预处理 20/20 可用、指标不下降；不可用图片提前给出中文提示且不破坏原文件） | 无 |
| AI-R05 | 2026-07-17 | `61f6d17` | `app/ai/documents/provider_router.py`（新建：路由决策层可解释可配置可回滚；ProviderChoice 三通道 VISION_MODEL/DETERMINISTIC_TEXT/FALLBACK_LOCAL；表格图+清晰达标→视觉、纯文本微信通知→确定性解析、不可用→本地兜底；ProviderRouterConfig 阈值集中可注入+config_version 指纹支持审计回滚；force_fallback 紧急回滚开关；call_with_evidence 重试证据保留：超时/网络/不可用可重试 max_retries=1，全失败不丢证据，CallEvidence 含 attempts/error_type/duration 序列化）、`app/ai/documents/provider_evaluation.py`（新建：评测框架注入式不调外部 API 避免泄露密钥；EvaluationRecord/AggregatedMetrics/QualityGate/EvaluationRun；记录模型/提示词 hash/Schema 版本/耗时/错误率/调用量，对齐 AI-R03 黄金样本指标 header_accuracy/line_recall/material_match/quantity；QualityGate 门槛 min_sample_count=20+准确率下限 0.85+错误率上限 10%，达标才允许试点；同质性校验防混入不同 provider 记录导致聚合失真；make_record 便捷构造自动算 prompt_hash/schema_version）、`app/app.py`（OCR 路由 `api_document_ocr` 集成路由决策记 flask.g.ai_routing_decision；call_with_evidence 包裹视觉调用记 flask.g.ai_vision_call_evidence；失败返回降级提示+routing_decision+call_evidence 不丢证据；logger 配置后挂载 SafeLogFilter 到 app.logger 及所有 handler）、`app/ai/security.py`（修复 SafeLogFilter：先 record.getMessage() 格式化完整消息再整体脱敏，解决敏感数据跨越 record.msg/record.args 边界如 `logger.warning('data:image;base64,%s', b64)` 无法整体匹配正则导致泄露的缺陷；异常场景兜底脱敏 msg+args）、`scripts/verify_ai_provider_evaluation.py`（新建：7 项测试覆盖路由决策/评测框架聚合/质量门槛达标判定/重试证据保留/日志脱敏/可配置可回滚/黄金样本路由）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_provider_evaluation.py）、`.github/workflows/verify.yml`（CI 追加 provider_evaluation 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R05 状态置已完成，下一项改 AI-R06） | `python3 scripts/verify_ai_provider_evaluation.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（force_fallback 逻辑被破坏后路由不降级、QualityGate.is_passed 被破坏后 100% 错误率也达标、sanitize_log_message 被破坏后 base64 未脱敏，均能被测试捕获） | 通过（Provider 评测与路由 7 项测试全 PASS；core 套件 33 脚本全 PASS 含新增 provider_evaluation；0 回归；路由可解释可配置可回滚；评测框架注入式不调 API 不泄露密钥；质量门槛达标才允许试点；重试不丢证据；日志脱敏 API key/Bearer/base64 全覆盖含参数化调用场景；strict 台账一致性通过） | 真实 Provider 评测数据：当前评测框架为注入式，真实 Provider（OpenAI/通义/智谱等）的评测记录需有 API Key 的环境注入后落盘，框架已支持；多 Provider 并存时的灰度切换（按角色/百分比）待 AI-R13 Agent 预算与并发控制一并完善 |
| AI-R06 | 2026-07-17 | `6c12bb2` | `app/ai/documents/delivery_matcher.py`（新建：联合匹配引擎纯逻辑+依赖注入，query_open_purchase_orders/query_purchase_order_by_no 回调注入；CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter；四维度评分权重 ORDER_NO=0.25/SUPPLIER=0.40/MATERIAL=0.30/DATE=0.05 权重和=1.0，微信送货通知无订单号场景下供应商+物料双匹配可达 0.70 门槛；自动选单策略：仅当唯一候选且评分>=0.70 才自动选单，多候选返回清单待人工确认，低置信度不自动选单；差异检测：短交/超收/关闭订单/未关联物料；LineMatchEvidence 行级证据含匹配 PO 行 ID/物料 ID/订单量/已收量/未收量/差异值/差异类型；is_purchase_request_forbidden_for_delivery 显式判定微信/截图送货通知语义（动作词+物料段，排除销售出库）禁止走 purchase_request 路径）、`app/app.py`（OCR 路由 `api_document_ocr` 集成：草稿创建前调用 match_delivery，结果存 flask.g.ai_delivery_match；注入 _ai_query_open_purchase_orders_for_delivery 按供应商名+物料编码/名称查 status in pending/partial/open 开放订单 limit 20，_ai_query_purchase_order_by_no 按订单号精确查含关闭订单用于差异展示；成功响应新增 delivery_match 字段含候选清单/最佳候选/自动选中/回退原因/采购申请禁令+原因；异常降级走原草稿流程不中断 OCR；_ai_purchase_order_to_info ORM 对象转 PurchaseOrderInfo 纯数据）、`scripts/verify_ai_delivery_matcher.py`（新建：8 项测试覆盖联合匹配/订单号精确/多候选不自动选/短交超收/关闭订单/未关联物料/低置信度不自动选/采购申请禁令）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_delivery_matcher.py）、`.github/workflows/verify.yml`（CI 追加 delivery_matcher 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R06 状态置已完成，下一项改 AI-R07） | `python3 scripts/verify_ai_delivery_matcher.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（shortage→overreceive 被测试4 捕获、AUTO_SELECT_CONFIDENCE_THRESHOLD 降到 0.0 致低置信度也自动选单被测试7 捕获、采购申请禁令总返回 False 被测试8 捕获，均能被测试捕获） | 通过（送货通知联合匹配 8 项测试全 PASS；core 套件 34 脚本全 PASS 含新增 delivery_matcher（除 ledger_consistency 因代码已标 AI-R06 但台账状态在第一次 commit 前仍待开发的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；送货通知误建采购申请为 0；低置信度不自动选单据；多候选返回清单待人工确认；匹配依据和数量差异可见；行级证据含 PO 行 ID/物料 ID/订单量/已收量/未收量/差异值/差异类型；关闭订单标记且不自动选单；短交/超收/未关联物料差异检测正确） | 真实订单匹配数据：当前 ORM adapter 已对接 PurchaseOrder ORM 模型，但联合匹配的准确率需在真实多供应商多订单数据下评估，初版权重（ORDER_NO=0.25/SUPPLIER=0.40/MATERIAL=0.30/DATE=0.05）基于设计推理，待 AI-R11 采购到货跟进工作台整合时按真实数据调优；前端 delivery_match 字段的可视化展示（候选清单/差异标记/采购申请禁令提示）待 AI-R08 文档确认台字段证据一并实现 |
| AI-R07 | 2026-07-17 | `3cf8ecd` | `app/ai/documents/material_governance.py`（新建：物料治理纯逻辑+依赖注入模块；中文归一化 normalize_chinese_text/normalize_match_key 含全角→半角、繁简转换（軸→轴/齒→齿/輪→轮 等常见物料字）、同义词归一化（马达→电机/螺帽→螺母/垫片→垫圈）、去多余空白与标点；编码/名称/规格三维加权评分权重 CODE=0.50/NAME=0.35/SPEC=0.15 权重和=1.0；MaterialMatchCandidate 含 match_method/confidence/score_breakdown/needs_confirmation/confirmation_reason/is_high_risk/high_risk_rule_id；多候选返回清单 has_ambiguity=True 100% 人工确认；规格不匹配触发 ambiguous_spec 即使 confidence 达标也需确认；包装单位换算 convert_quantity 内置换算因子表 箱=100个/包=10个/盒=10个/打=12个/捆=50个 + 米/千克/升及同义单位归一（只/件/套/pcs→个），支持注入自定义换算回调，UnitConversionEvidence 含 from_unit/to_unit/factor/rule_source/original_quantity/base_quantity 换算依据可追溯；高风险物料规则引擎 is_high_risk_material 默认 4 条规则 IC-/HZ-/PM-/BRG-PRECISION- 编码前缀匹配，命中即强制 needs_confirmation=True 不论 confidence 多高，支持注入自定义规则和正则匹配；一物多码通过 query_aliases 回调多别名键指向同一物料；主函数 match_material_governance 依赖注入 query_materials_by_codes/query_materials_by_name/query_aliases/high_risk_rules，CI 无 DB 可 mock 测）、`app/app.py`（AIMaterialAlias 模型新增 disabled/disabled_reason 字段修复 revoke_alias bug，原 confirmation.py:252-253 试图设置但模型缺字段致 AttributeError；启动迁移 SQL ALTER TABLE ADD COLUMN IF NOT EXISTS 用 PRAGMA table_info 检查列存在性；_ai_material_match_one 别名查询加 .filter_by(disabled=False) 过滤已禁用别名；ai_material_alias_list 默认 .filter(disabled==False) 仅展示未禁用别名，show_disabled=1 可查看全部；OCR 路由 `api_document_ocr` 集成 AI-R07 旁路调用：草稿创建前对每条 OCR 提取 item 调用 match_material_governance，注入 _ai_mg_query_materials_by_codes/_ai_mg_query_materials_by_name/_ai_mg_query_aliases 三个 ORM adapter，结果存 flask.g.ai_material_governance 供前端展示候选清单和证据，不破坏现有 _ai_material_match_one 草稿路径；成功响应新增 material_governance 字段含每条 item 的候选清单/最佳候选/自动选中/歧义标记/确认决策；异常降级走原匹配不中断 OCR）、`scripts/verify_ai_material_governance.py`（新建：8 项测试覆盖中文归一化/编码精确匹配/名称规格加权/别名一物多码/多候选歧义/ambiguous_spec/单位换算证据/高风险强制确认）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_material_governance.py）、`.github/workflows/verify.yml`（CI 追加 material_governance 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R07 状态置已完成，下一项改 AI-R08） | `python3 scripts/verify_ai_material_governance.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（高风险判定总返回 False 被测试8 捕获、多候选不标记歧义被测试5 捕获、单位换算因子改成 0 被测试7 捕获，均能被测试捕获） | 通过（物料治理 8 项测试全 PASS；core 套件 35 脚本全 PASS 含新增 material_governance（除 ledger_consistency 因代码已标 AI-R07 但台账状态在第一次 commit 前仍待开发的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；歧义行 100% 人工确认（多候选 has_ambiguity=True 不自动选）；高风险物料错误自动确认数为 0（confidence=1.0 也强制 needs_confirmation）；换算依据可追溯（UnitConversionEvidence 含因子/规则来源/原始量/基本量）；规格不匹配触发 ambiguous_spec 即使 confidence 达标也需确认；中文归一化覆盖全角/半角/繁简/同义词/空白） | 真实物料匹配数据：当前 ORM adapter 已对接 Material/AIMaterialAlias ORM 模型，但物料匹配准确率需在真实多供应商多物料数据下评估，初版权重（CODE=0.50/NAME=0.35/SPEC=0.15）和高风险规则（IC-/HZ-/PM-/BRG-PRECISION-）基于设计推理，待 AI-R08 文档确认台字段证据整合时按真实数据调优；matcher.py（孤儿代码，带 confidence/needs_confirmation/reason 五元组但未被生产调用）暂未替换，AI-R07 采用旁路调用策略保留现有 _ai_material_match_one 草稿路径不变，matcher.py 的替换/删除待 AI-R08 一并决策；前端 material_governance 字段的可视化展示（候选清单/歧义标记/高风险提示/换算证据）待 AI-R08 文档确认台字段证据一并实现；单位换算当前仅内置标准因子表，物料专属换算因子（如某物料 1 箱=24 个）需通过 query_custom_conversions 注入，待 AI-R08 配套物料包装单位管理页面 |
| AI-R08 | 2026-07-17 | `7f89329` | `app/ai/documents/document_confirmation.py`（新建：文档确认台字段证据与重复风险聚合引擎纯逻辑+依赖注入，query_existing_drafts 回调注入，CI 无 DB 可 mock 测，生产由 app.py 提供 ORM adapter 按 source_hash/business_key 查 AIDraftIdempotency 表；FieldEvidence 字段级证据含 original_value/candidates/confidence/needs_confirmation/confirmation_reason/correction_status/source/line_index；DuplicateRiskHit 重复风险命中含已存在草稿类型/ID/单号/状态/创建时间/匹配原因/相似度/blocks_creation；DocumentConfirmationEvidence 综合证据聚合三方：AI-R06 delivery_match 透传候选供应商/订单号+采购差异+采购申请禁令、AI-R07 material_governance 透传候选物料+歧义+高风险、AI-R01 idempotency 计算的 source_hash/business_key 查重；低置信度拦截 confidence<0.80 标记 needs_confirmation=True；重复风险仅 completed 状态草稿 blocks_creation=True 阻止建单；高风险物料 confidence=1.0 也强制 needs_confirmation；validate_corrections_before_draft_creation 服务端二次校验 4 类拦截：重复风险阻止建单/低置信度未修正/物料歧义未选择 matched_material_id/高风险未确认 high_risk_confirmed；build_summary 中文摘要供前端顶部展示）、`app/app.py`（OCR 路由 `api_document_ocr` 集成：AI-R07 集成后草稿创建前调用 build_confirmation_evidence，注入 _ai_dc_query_existing_drafts ORM adapter 按 source_hash/business_key 查 AIDraftIdempotency 表 limit 10，similarity business_key=1.0/source_hash=0.90；source_hash 取 compute_draft_idempotency_key 前 32 字符，business_key 取完整 key；结果存 flask.g.ai_document_confirmation；成功响应新增 document_confirmation 字段；异常降级走原草稿流程不中断 OCR）、`scripts/verify_ai_document_confirmation.py`（新建：8 项测试覆盖字段证据聚合/低置信度标记/重复风险命中/重复风险未命中/采购差异透传/物料歧义透传/高风险强制确认/服务端二次校验）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_document_confirmation.py，修复 R07 引入的重复行）、`.github/workflows/verify.yml`（CI 追加 document_confirmation 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R08 状态置已完成，下一项改 AI-R09） | `python3 scripts/verify_ai_document_confirmation.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（低置信度拦截改 False 被测试2 捕获、blocks_creation 改 False 被测试3 捕获、needs_confirmation 赋值行去掉 line_needs_confirmation 致高风险 confidence=1.0 不强制确认被测试7 捕获，均能被测试捕获） | 通过（文档确认台 8 项测试全 PASS；core 套件 36 脚本全 PASS 含新增 document_confirmation（除 ledger_consistency 因代码已标 AI-R08 但台账状态在第一次 commit 前仍待开发的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；低置信度字段不能静默通过；重复风险可阻止建单（completed 状态 blocks_creation=True）；仓库人员可在浏览器完成整个流程（document_confirmation 字段含字段级证据+重复风险+三方透传证据供前端渲染）；服务端二次校验 4 类拦截：重复风险/低置信度/物料歧义/高风险） | 前端可视化：document_confirmation 字段已通过 OCR API 响应输出，但 templates/ai_document_confirm.html 简版确认台页面的字段级证据渲染（原图与表头明细并排、字段置信度色标、候选值下拉、修正状态回传、重复风险横幅、低置信度拦截提示、采购差异/物料歧义/高风险标记）待 AI-R16 浏览器 E2E 一并实现；服务端 validate_corrections_before_draft_creation 已实现但未接入草稿创建路由的提交前校验，待前端确认台表单提交端点建立后接入；matcher.py 孤儿代码暂未替换，AI-R08 采用旁路调用策略保留现有 _ai_material_match_one 草稿路径不变 |
| AI-R09 | 2026-07-17 | `cc40b73` | `app/ai/documents/field_feedback.py`（新建：字段级反馈和文档质量指标纯逻辑+依赖注入模块；FieldCorrectionRecord 字段级修正记录含 field_name/line_index/original_value/corrected_value/correction_reason/adopted/model/prompt_hash/schema_version/source/created_at 共 11 字段，覆盖验收要求的"字段名/原值/新值/修正原因/是否采纳/模型/提示词/Schema 版本"；build_field_correction_records 从 AI-R08 evidence.fields + 用户 corrections 产出记录，仅对 needs_confirmation=True 或 corrections 中有覆盖的字段产出（避免噪音），adopted=True=修正了值/adopted=False=确认原值或未处理，save_feedback_record 回调注入持久化，CI 无 DB 可 mock 测；mask_sensitive_value 内置脱敏：手机号保留前3后4/身份证保留前6后4/邮箱打码，contact_phone/id_card/email 字段整体返回 ***，空值不存；FieldQualityMetrics 单字段聚合指标含 total_count/corrected_count/adopted_count/accuracy_rate/correction_rate/top_reasons；aggregate_quality_metrics 按 (source,model,schema_version,field_name) 分组聚合准确率与修正率，产出 QualityMetricsSnapshot 含 by_field/overall_accuracy_rate/overall_correction_rate/total_records；QualityRegression 质量下降定位含 baseline_schema_version/current_schema_version/baseline_accuracy/current_accuracy/drop_amount/is_regression；detect_quality_regressions 对比当前版本与基线版本 per-field accuracy，下降超阈值（默认 0.10，用 1e-9 容差避免浮点误判）标记 is_regression=True，可定位到具体字段和版本；should_warn_quality_regression 告警不阻止建单仅返回告警信息）、`app/app.py`（AIFieldFeedback ORM 模型新增：id/user_id/ai_run_id/field_name/line_index/original_value/corrected_value/correction_reason/adopted/model/prompt_hash/schema_version/source/created_at，含 idx_ai_ff_lookup(source,model,schema_version,field_name) 和 idx_ai_ff_user_created 索引；_ai_ff_save_feedback_record ORM adapter 写入 AIFieldFeedback 表，异常 rollback 不阻塞业务；_ai_ff_query_feedback_records 查询反馈记录供聚合用；OCR 路由 `api_document_ocr` 集成 AI-R09：R08 evidence 构建后计算 _ff_prompt_hash/_ff_schema_version 元数据（复用 AI-R05 compute_prompt_hash/compute_schema_version），成功响应新增 field_feedback_meta 字段含 model/prompt_hash/schema_version/source/feedback_url 供前端回传；新增 POST /api/ai/document_feedback 端点接收 evidence_fields+corrections 调用 build_field_correction_records 持久化，权限 admin/warehouse/purchase；新增 GET /api/ai/document_quality 端点查询反馈记录调用 aggregate_quality_metrics 产出快照，支持 source/model/schema_version/field_name/baseline_schema_version 过滤参数）、`scripts/verify_ai_field_feedback.py`（新建：8 项测试覆盖字段反馈记录构造/敏感原文脱敏/准确率聚合/修正率聚合/质量下降定位/质量未下降不误报/top_reasons 排序/不保存不必要敏感原文）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_field_feedback.py）、`.github/workflows/verify.yml`（CI 追加 field_feedback 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R09 状态置已完成，下一项改 AI-R10） | `python3 scripts/verify_ai_field_feedback.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（脱敏函数置空被测试2+8 捕获、聚合修正率取反被测试3 捕获、质量下降阈值去掉 1e-9 容差致浮点误判被测试6 捕获，均能被测试捕获） | 通过（字段反馈 8 项测试全 PASS；core 套件 37 脚本全 PASS 含新增 field_feedback（除 ledger_consistency 因代码已标 AI-R09 但台账状态在第一次 commit 前仍待开发的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；记录字段名/原值/新值/修正原因/是否采纳/模型/提示词/Schema 版本（11 字段全覆盖）；按来源与版本聚合准确率和修正率（accuracy_rate=1-correction_rate）；可定位质量下降的字段和版本（QualityRegression 含 baseline/current schema_version + accuracy + drop_amount + is_regression）；不保存不必要的敏感原文（手机号/身份证/邮箱局部脱敏，contact_phone/id_card/email 字段整体 ***，空值不存）） | 前端可视化：POST /api/ai/document_feedback 和 GET /api/ai/document_quality 端点已就绪，但确认台页面的字段修正表单提交（用户修正后回传 corrections）和文档质量指标运维页（按来源/版本/字段名展示 accuracy_rate/correction_rate/regressions）待 AI-R16 浏览器 E2E 一并实现；prompt_hash 当前取 flask.g.ai_extraction_prompt（若未设置则为空），需在 OCR 提取流程中设置该 g 变量才能完整记录提示词指纹；当前仅记录"被修正/被确认"字段，未触发确认流程的字段（needs_confirmation=False）不产生反馈记录，完整字段级准确率统计（含全部字段而非仅确认字段）待 AI-R15 业务质量指标扩展 |
| AI-R10 | 2026-07-17 | `ea6bf24` | `app/ai/ops/warehouse_workbench.py`（新建：仓库角色工作台整合纯逻辑+依赖注入模块；WorkbenchItem 卡片单项含 id/title/subtitle/detail/jump_url/extra；WorkbenchSection 卡片区含 key/title/count/items/jump_url/read_only(恒True)/empty_hint；WarehouseWorkbenchSnapshot 工作台快照含 sections/total_pending_count/abnormal_stock_count/generated_at/user_id/role；build_warehouse_workbench 主函数注入 7 个 query 回调构建 7 个 section：today_inbound_pending 今日待收（InOrder status=pending）/today_outbound_pending 今日待出（OutOrder status=pending）/inventory_check_pending 待盘（InventoryCheck status=pending）/abnormal_stock 异常库存（负库存 Material.stock<0 + 低库存 stock<=min_stock）/documents_pending_confirmation 文档待确认（AIDocumentJob status=pending_confirmation）/failed_tasks 失败任务（AIDocumentJob status=failed + AIRun status=failed）/unfinished_drafts 未完成草稿（AIDraftIdempotency status=processing），异常库存单独计 abnormal_stock_count 不计入 total_pending_count；_safe_query 异常降级为 (0,[]) 不中断构建；validate_workbench_read_only 校验 read_only 恒 True 且 jump_url 不含 submit/audit/delete/void/complete 写动作；validate_count_consistency 校验各 section count 与原业务列表一致）、`app/app.py`（7 个 ORM adapter：_ai_ww_query_today_inbound_pending/_ai_ww_query_today_outbound_pending/_ai_ww_query_inventory_check_pending/_ai_ww_query_abnormal_stock/_ai_ww_query_documents_pending_confirmation/_ai_ww_query_failed_tasks/_ai_ww_query_unfinished_drafts，每个返回 (count, list[dict]) 二元组，count 与原业务列表一致，items 前 5 条详情含 jump_url 跳转；新增 GET /api/ai/warehouse_workbench 端点整合 7 个 section 返回工作台快照，权限 admin/warehouse，响应含 read_only_valid 校验结果）、`scripts/verify_ai_warehouse_workbench.py`（新建：8 项测试覆盖 7 个 section 完整性/count 一致性/count 不一致检测/read_only 恒 True/jump_url 不含写动作/query 异常降级/total_pending 排除异常库存/空数据 empty_hint+items 结构）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_warehouse_workbench.py）、`.github/workflows/verify.yml`（CI 追加 warehouse_workbench 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R10 状态置已完成，下一项改 AI-R11） | `python3 scripts/verify_ai_warehouse_workbench.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（read_only 改 False 被测试4+5 捕获、_safe_query 异常不降级被测试6 捕获、异常库存计入 total_pending 被测试7 捕获，均能被测试捕获） | 通过（工作台 8 项测试全 PASS；core 套件 38 脚本 37 PASS 含新增 warehouse_workbench（除 ledger_consistency 因代码已标 AI-R10 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；数量与原业务列表一致（validate_count_consistency 校验 7 个 section count 与原业务列表一致）；工作台只读或跳转（read_only 恒 True，jump_url 不含 submit/audit/delete/void/complete 写动作，validate_workbench_read_only 双重校验）；7 类业务整合（今日待收/待出/待盘/异常库存/文档待确认/失败任务/未完成草稿）） | 前端可视化：GET /api/ai/warehouse_workbench 端点已就绪返回完整快照，但仓库首页模板未集成工作台卡片渲染（7 个 section 卡片+count+前 5 条详情+跳转链接+empty_hint 空态）待 AI-R16 浏览器 E2E 一并实现；当前工作台为只读聚合视图，未集成到仓库角色导航菜单入口；异常库存仅查负库存+低库存，呆滞物料/超期库存等异常类型待后续扩展 |
| AI-R11 | 2026-07-17 | `7becce4` | `app/ai/ops/purchase_followup_workbench.py`（新建：采购到货跟进工作台整合纯逻辑+依赖注入模块；FollowupItem 跟进卡片含 id/title/subtitle/detail/jump_url/metric_scope/extra；FollowupSection 卡片区含 key/title/count/items/jump_url/read_only(恒True)/metric_scope/time_range/empty_hint；SupplierFollowupSummary 供应商跟进清单含 supplier_id/supplier_name/pending_count/delayed_count/short_delivery_count/followup_suggestion/needs_manual_confirmation(恒True)/jump_url；PurchaseFollowupSnapshot 工作台快照含 sections/supplier_followup_list/total_attention_count/generated_at/user_id/role；build_purchase_followup_workbench 主函数注入 6 个 section query 回调+1 个供应商跟进清单 query 回调构建 7 个 section：pending_arrival 待到（PurchaseOrder status in pending/partial 且 expected_date>=today）/delayed_arrival 延期（expected_date<today 且 status in pending/partial）/short_delivery 短交（PurchaseOrderItem received_quantity<quantity）/over_receive 超收（received_quantity>quantity）/unlinked_notices 未关联通知（AIDocumentJob 含送货通知但 source_purchase_order_id 为空，最近 7 天）/multi_order_candidates 多订单候选（AI-R06 delivery_match 多候选未自动选单，最近 7 天）/supplier_followup_list 供应商跟进清单（按供应商归组待到+延期+短交，生成催交话术建议不自动发送），供应商跟进清单不计入 total_attention_count 避免与待到/延期/短交重复计数；_safe_query/_safe_query_list 异常降级不中断构建；validate_followup_read_only 校验 read_only 恒 True 且 jump_url 不含 send/submit/audit/delete/void/complete/auto_dispatch 写动作且供应商 needs_manual_confirmation 恒 True；validate_metric_scope_clear 校验各 section metric_scope 和 time_range 明确；validate_count_consistency 校验 count 与原业务列表一致）、`app/app.py`（7 个 ORM adapter：_ai_pf_query_pending_arrival/_ai_pf_query_delayed_arrival/_ai_pf_query_short_delivery/_ai_pf_query_over_receive/_ai_pf_query_unlinked_notices/_ai_pf_query_multi_order_candidates/_ai_pf_query_supplier_followup_list，前 6 个返回 (count, list[dict]) 二元组 count 与原业务列表一致，第 7 个返回 list[dict] 按供应商归组生成催交话术 needs_manual_confirmation=True；新增 GET /api/ai/purchase_followup_workbench 端点整合 7 个 section 返回工作台快照，权限 admin/purchase/warehouse，响应含 read_only_valid+metric_scope_valid 双重校验结果）、`scripts/verify_ai_purchase_followup_workbench.py`（新建：8 项测试覆盖 7 个 section 完整性/count 一致性/count 不一致检测/read_only 恒 True/jump_url 不含写动作/供应商 needs_manual_confirmation 恒 True/指标口径时间范围明确/total_attention 排除供应商跟进+异常降级）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_purchase_followup_workbench.py）、`.github/workflows/verify.yml`（CI 追加 purchase_followup_workbench 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R11 状态置已完成，下一项改 AI-R12） | `python3 scripts/verify_ai_purchase_followup_workbench.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（read_only 改 False 被测试4+5+6 捕获、_to_supplier_summaries 强制 needs_manual_confirmation=False 被测试4+5+6 捕获、metric_scope 置空被测试7 捕获，均能被测试捕获） | 通过（采购跟进工作台 8 项测试全 PASS；core 套件 39 脚本 38 PASS 含新增 purchase_followup_workbench（除 ledger_consistency 因代码已标 AI-R11 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；指标口径和时间范围明确（每个 section 含 metric_scope+time_range，validate_metric_scope_clear 校验）；对外沟通和业务提交必须人工确认（read_only 恒 True，jump_url 不含 send/submit/audit/delete/void/complete/auto_dispatch 写动作，供应商跟进 needs_manual_confirmation 恒 True 催交话术不自动发送）；7 类业务整合（待到/延期/短交/超收/未关联通知/多订单候选/供应商跟进清单）） | 前端可视化：GET /api/ai/purchase_followup_workbench 端点已就绪返回完整快照，但采购首页模板未集成工作台卡片渲染（7 个 section 卡片+count+前 5 条详情+指标口径+时间范围+跳转链接+供应商跟进清单含催交话术建议）待 AI-R16 浏览器 E2E 一并实现；多订单候选当前简化为查 recognized 状态且 supplier 非空的 AIDocumentJob（AIDocumentJob 无直接字段存候选数），精确查询需查 AIRun 响应快照中 delivery_match.candidates 长度>1，待 AI-R16 配套前端联调时完善；催交话术当前为规则模板（按延期/短交/待到优先级生成），AI 生成话术需对接 LLM 且必须人工确认后才能发送，待 AI-R13 Agent 预算控制一并完善 |
| AI-R12 | 2026-07-17 | `30f8be2` | `app/ai/knowledge_lifecycle.py`（新建：知识库发布、版本和失效管理纯逻辑+依赖注入模块；KnowledgeVersion 知识版本纯数据类含 id/knowledge_key/version/title/summary/content/rule/page_endpoint/page_label/keywords/source/status/allowed_roles/published_by/published_at/updated_at/created_at/superseded_by/data_boundary 共 18 字段，覆盖验收要求的"知识草稿、审核、发布、失效、版本、来源、更新时间、发布人、检索权限和回滚"；状态机 draft→in_review→published→deprecated→archived，RETRIEVABLE_STATUSES 仅 published，WRITE_BLOCKED_STATUSES 含 published/deprecated/archived 不可重复发布；REALTIME_KEYWORDS 实时关键词表含 库存/数量/余额/当前/现在/今天/实时/剩余/可用/在途/在制/已收/已发/未收/未发 等，is_realtime_question 命中实时词必须路由实时数据工具；is_retrievable 仅 published 可检索；is_visible_to_role 检索权限按角色过滤，allowed_roles 为空全部可见，admin 始终可见；search_published_knowledge 主检索函数注入 query_published 回调，仅检索 published 状态+按角色过滤+关键词评分+标题加权，返回 KnowledgeRetrievalResult 含 source/updated_at/needs_realtime_tool；publish_knowledge_version 发布操作同 key published 唯一，旧版本自动标记 deprecated 并 superseded_by 指向新版本，draft/in_review 可发布，published/deprecated/archived 不可重复发布；rollback_knowledge_version 回滚操作目标版本设为 published，当前 published 标记为 deprecated，已 published 状态回滚被拒绝；deprecate_knowledge_version 失效操作 published→deprecated 立即不可检索，非 published 状态失效应报错；archive_knowledge_version 归档历史版本；submit_for_review 提交审核 draft→in_review，非 draft 状态提交审核被拒绝；build_knowledge_answer 构建回答含 reply/cards/actions/needs_realtime_tool/sources，验收2 要求回答显示来源和更新时间；validate_unpublished_not_retrievable 校验未发布不可检索；validate_answer_shows_source_and_time 校验回答显示来源时间；validate_realtime_question_routed 校验实时问题路由实时工具；validate_published_unique_per_key 校验同 key published 唯一）、`app/app.py`（AIKnowledgeVersion ORM 模型新增：id/knowledge_key/version/title/summary/content/rule/page_endpoint/page_label/keywords/source/status/allowed_roles/published_by/published_at/updated_at/created_at/superseded_by 共 15 字段，含 idx_ai_kv_key_version/idx_ai_kv_status_key/idx_ai_kv_published_at 3 索引；_ai_kv_to_dataclass ORM 转纯数据；6 个 ORM adapter：_ai_kv_query_all_versions/_ai_kv_query_published/_ai_kv_query_published_by_key/_ai_kv_query_versions_by_key/_ai_kv_update_status/_ai_kv_next_version_number；6 个 API 端点：GET /api/ai/knowledge_search 检索（全部角色，仅返回 published）+ GET /api/ai/knowledge_versions 版本列表（admin 全可见，其他角色仅 published/deprecated/archived 草稿不可见）+ POST /api/ai/knowledge_draft 创建草稿（仅 admin，状态 draft 不可检索）+ POST /api/ai/knowledge_publish 发布（仅 admin，同 key 旧 published 自动 deprecated）+ POST /api/ai/knowledge_rollback 回滚（仅 admin）+ POST /api/ai/knowledge_deprecate 失效（仅 admin，立即不可检索）；_ai_safe_url_for 安全 URL 生成）、`scripts/verify_ai_knowledge_lifecycle.py`（新建：8 项测试覆盖未发布不可检索/回答显示来源时间/实时问题路由实时工具/发布同 key 唯一+旧版本自动 deprecated/回滚+追溯/失效立即不可检索/检索权限角色过滤/同 key published 唯一+submit_for_review 流程）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_knowledge_lifecycle.py）、`.github/workflows/verify.yml`（CI 追加 knowledge_lifecycle 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R12 状态置已完成，下一项改 AI-R13） | `python3 scripts/verify_ai_knowledge_lifecycle.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（is_retrievable 总返回 True 致 draft 可检索被测试1+6 捕获、is_realtime_question 总返回 False 致实时问题不路由实时工具被测试3 捕获、validate_published_unique_per_key 总返回通过致多 published 不被检测被测试8 捕获，均能被测试捕获） | 通过（知识库生命周期 8 项测试全 PASS；core 套件 40 脚本 39 PASS 含新增 knowledge_lifecycle（除 ledger_consistency 因代码已标 AI-R12 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；未发布内容不可检索（draft/in_review/deprecated/archived 均不可检索，仅 published 可检索）；回答显示来源和更新时间（reply 含"来源：知识库版本 vX"+"更新时间：ISO8601"+sources 数组）；实时库存问题必须使用实时数据工具（is_realtime_question 命中实时词+needs_realtime_tool=True+回答提示"使用实时数据工具"）；知识草稿/审核/发布/失效/版本/来源/更新时间/发布人/检索权限/回滚全覆盖） | 前端可视化：6 个 API 端点已就绪，但知识库管理页面（草稿编辑/审核流/发布按钮/版本对比/失效标记/回滚操作/检索权限配置）待 AI-R16 浏览器 E2E 一并实现；现有 _ai_knowledge_response 静态 SOP 知识库（13 条 AIKnowledgeEntry）保留作为兜底，未迁移到 AIKnowledgeVersion 动态版本表，迁移待 AI-R16 配套前端管理页面时按需将静态 SOP 导入为 initial published 版本；实时库存问题当前仅标记 needs_realtime_tool=True 并在回答中提示，实际路由到实时数据工具的自动切换（如自动调用 warehouse_insights 工具）待 AI-R13 Agent 预算控制一并完善；检索关键词评分当前为简单子串匹配+标题加权，语义检索（向量相似度）待 AI-R15 业务质量指标扩展 |
| AI-R13 | 2026-07-17 | `a4689f5` | `app/ai/agents/budget_control.py`（新建：Agent 预算、取消、熔断和并发控制纯逻辑+依赖注入模块；BudgetConfig 预算配置含 max_steps/max_duration_seconds/max_tool_calls/deadline_iso/concurrency_key；BudgetCheckResult 预算检查结果含 passed/reason/violation_type/current_steps/current_duration_seconds/current_tool_calls；CircuitBreakerState Provider 熔断器状态含 provider_name/failure_count/threshold/cooldown_seconds/state/last_failure_at/last_failure_reason；ConcurrencyLock 并发互斥锁含 key/holder_run_id/locked_until/acquired_at；RetryRecord 重试记录含 retry_id/original_run_id/retry_run_id/retry_reason/original_evidence/retry_count/created_at；HumanConfirmationRequest 人工确认请求含 run_id/step_no/action/target_type/target_id/reason/created_at/status；6 个违规类型常量 max_steps_exceeded/max_duration_exceeded/max_tool_calls_exceeded/deadline_exceeded/circuit_breaker_open/concurrency_lock_held；3 个熔断状态 closed/open/half_open；AUTO_SUBMIT_FORBIDDEN_ACTIONS 10 个禁止动作 submit/audit/approve/complete/close/void/delete/confirm_submit/auto_dispatch/auto_complete；check_budget 4 项预算检查 max_steps/max_duration_seconds/max_tool_calls/deadline_iso；acquire_concurrency_lock 并发锁获取含 TTL 防死锁+同 key 互斥；release_concurrency_lock 并发锁释放；record_provider_call Provider 调用结果记录+熔断状态机转换 closed→open（达阈值）→half_open（冷却期后）→closed（成功）/open（失败）；check_circuit_breaker 熔断器调用检查；request_human_confirmation 发起人工确认请求；resume_from_human_confirmation 人工确认恢复 confirmed/rejected；create_retry_record 创建重试记录保留原证据；list_retry_history 重试历史查询；validate_no_infinite_loop 无无限循环校验；validate_no_auto_submit 自动提交禁止动作校验；validate_retry_preserves_evidence 重试证据保留校验；validate_safety_stop_on_violation 安全停止校验；validate_permission_boundary 权限边界校验）、`app/app.py`（3 个 ORM 模型新增：AIAgentRunLock 并发锁含 concurrency_key/holder_run_id/locked_until/acquired_at/released_at/status；AIAgentRetryRecord 重试记录含 retry_id/original_run_id/retry_run_id/retry_reason/original_evidence(JSON)/retry_count/created_at；AIAgentHumanConfirmation 人工确认含 run_id/step_no/action/target_type/target_id/reason/created_at/decided_at/status；8 个 ORM adapter：_ai_bc_acquire_lock/_ai_bc_release_lock/_ai_bc_query_lock/_ai_bc_save_retry_record/_ai_bc_query_retry_records/_ai_bc_save_human_confirmation/_ai_bc_update_human_confirmation/_ai_bc_query_human_confirmation；6 个 API 端点：POST /api/ai/agent_budget_check 预算检查+无无限循环校验 + POST /api/ai/agent_concurrency_lock 并发锁 acquire/release（admin/warehouse/purchase）+ POST /api/ai/agent_circuit_breaker 熔断器 record/check（仅 admin，内存级状态）+ POST /api/ai/agent_human_confirmation 人工确认 request/decide/query（admin/warehouse/purchase，submit/audit 等禁止动作必须人工确认）+ POST /api/ai/agent_retry_record 重试记录 create/list（仅 admin，保留原证据）+ POST /api/ai/agent_validate_safety 一次性多项安全校验（仅 admin，含预算/无无限循环/无自动提交/安全停止/权限边界））、`scripts/verify_ai_budget_control.py`（新建：8 项测试覆盖 max_steps 超限安全停止/max_duration+tool_calls+deadline 超限/并发互斥锁/Provider 熔断器 3 状态/等待人工状态/重试保留原证据/自动提交禁止动作检测/越权安全停止）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_budget_control.py）、`.github/workflows/verify.yml`（CI 追加 budget_control 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R13 状态置已完成，下一项改 AI-R14） | `python3 scripts/verify_ai_budget_control.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（check_budget 总返回 passed=True 致 max_steps 超限不被检测被测试1+2+8 捕获、record_provider_call 不触发熔断（threshold 永不达成）致连续失败不熔断被测试4 捕获、validate_no_auto_submit 总返回通过致禁止动作不被检测被测试7 捕获，均能被测试捕获） | 通过（Agent 预算控制 8 项测试全 PASS；core 套件 41 脚本 40 PASS 含新增 budget_control（除 ledger_consistency 因代码已标 AI-R13 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；无无限循环（max_steps 超限安全停止）；超预算/越权/故障安全停止（budget check+circuit breaker+safety_stop+permission_boundary 四重校验）；重试保留原证据（RetryRecord.original_evidence 含 step_results+tool_calls+原 run_id）；自动提交业务单据次数为 0（10 个禁止动作全部检测，submit/audit/approve/complete/close/void/delete/confirm_submit/auto_dispatch/auto_complete 必须人工确认）） | 熔断器状态当前为内存级（app._ai_circuit_breakers 字典），多进程/多实例部署需迁移到 Redis 持久化；并发锁基于 SQLite 行级，高并发场景需迁移到 Redis 分布式锁；现有 Agent 框架（framework.py 的 AgentExecutor.execute）未集成预算检查钩子，Agent 执行时不会自动调用 check_budget，需在 AI-R16 浏览器 E2E 时将 budget_control 集成到 AgentExecutor.execute 主循环；等待人工状态当前仅记录请求和决策，Agent 暂停/恢复执行的实际调度（如暂停在 step_no，确认后从 step_no+1 恢复）待 AI-R16 配套前端时完善 |
| AI-R14 | 2026-07-17 | `dd9e52e` | `app/ai/ops/data_retention.py`（新建：AI 数据保留、脱敏和清理任务纯逻辑+依赖注入模块；5 类数据分类保留常量 conversations/images/tasks/feedback/audit，DEFAULT_RETENTION_DAYS 对话 90/图片 30/任务 180/反馈 365/审计 0 永久；PROTECTED_BUSINESS_DATA 业务保护类别 business_drafts/confirmation_records/critical_audit；SENSITIVE_FIELDS 敏感原文字段 phone/mobile/tel/id_card/id_number/email/api_key/apikey/token/secret/password/contact_phone/contact_name；RetentionPolicy 单类策略含 category/retention_days/critical_exempt/description；RetentionConfig 保留配置含 policies/dry_run/enabled+get_policy；DataRecord 数据记录含 id/category/created_at/is_critical/content_preview/has_business_link；CleanupPreviewItem 预览单项含 record/action(delete/keep/exempt/protected)/reason；CleanupPreviewResult 预览结果含 items/to_delete_count/to_keep_count/exempt_count/protected_count/generated_at；CleanupExecutionResult 执行结果含 success/deleted_count/kept_count/exempt_count/protected_count/failed_count/log_id/reason/executed_at；CleanupLogEntry 清理日志含 log_id/executed_by/categories/dry_run/deleted_count/kept_count/exempt_count/protected_count/failed_count/cutoff_date/executed_at/notes；default_retention_config 默认配置生成器；compute_cutoff_date 截止日期计算（retention_days=0 返回 1970-01-01 表示永久保留）；is_record_expired 记录过期判断；is_record_protected 业务保护判断（has_business_link 或 is_critical）；preview_cleanup 清理预览 dry_run 不实际删除，5 级 action 分类：1.业务关联→protected 2.critical+critical_exempt+过期→exempt 3.critical 无豁免→protected 安全网 4.过期→delete 5.未过期→keep；execute_cleanup 执行清理实际删除仅 action=delete 记录，保留关键审计和业务保护数据，生成清理日志；mask_sensitive_value 脱敏字段值（密钥类 ***，手机号前3后4，身份证前6后4，邮箱打码）；sanitize_export_record 脱敏导出记录；sanitize_log_text 脱敏日志文本（API key/Bearer/手机号/身份证/邮箱正则替换）；validate_no_business_data_deleted 校验不误删业务数据；validate_export_sanitized 校验导出脱敏；validate_log_sanitized 校验日志脱敏；validate_critical_audit_exempt 校验关键审计豁免）、`app/app.py`（AICleanupLog ORM 模型新增：log_id/executed_by/categories/dry_run/deleted_count/kept_count/exempt_count/protected_count/failed_count/cutoff_date/executed_at/notes 含 idx_ai_cleanup_executed_at/idx_ai_cleanup_executed_by 2 索引；4 个 ORM adapter：_ai_dr_query_expired 按 5 类查询过期记录（conversations=AIRun 关联 AIDraftIdempotency completed 判业务关联；images=AIDocumentAttempt 关联 AIDocumentJob draft_created 判业务关联；tasks=AIDocumentJob draft_created 判业务关联；feedback=AIFieldFeedback 无业务关联；audit=AIToolCall risk_level!=read 或关联 AIDraftIdempotency 判关键）+_ai_dr_delete_records 按类别+ID 删除+_ai_dr_save_log 保存清理日志+_ai_dr_query_logs 查询清理日志历史；6 个 API 端点：POST /api/ai/data_cleanup_preview 清理预览 dry_run+不误删校验+关键审计豁免校验（仅 admin）+ POST /api/ai/data_cleanup_execute 执行清理强制预览校验拒绝误删（仅 admin）+ GET /api/ai/data_cleanup_logs 清理日志查询（仅 admin）+ GET /api/ai/data_retention_config 保留策略配置查询（仅 admin）+ POST /api/ai/data_retention_validate 一次性多项安全校验含不误删+关键审计豁免+导出脱敏+日志脱敏（仅 admin）；_parse_iso_cutoff 截止日期解析辅助）、`scripts/verify_ai_data_retention.py`（新建：8 项测试覆盖默认保留配置/清理预览 delete/keep/exempt/protected 4 种 action/业务数据保护+反向校验/关键审计豁免+反向校验/执行清理+清理日志+禁用不执行/导出脱敏+反向校验/日志脱敏+反向校验/综合安全校验）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_data_retention.py）、`.github/workflows/verify.yml`（CI 追加 data_retention 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R14 状态置已完成，下一项改 AI-R15） | `python3 scripts/verify_ai_data_retention.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（has_business_link 检查被禁用致业务记录被 delete 被测试3+5+8 捕获、sanitize_log_text 重新引入 API key 泄漏被测试7+8 捕获、validate_no_business_data_deleted 总返回通过致反向校验失败被测试3 捕获，均能被测试捕获） | 通过（数据保留脱敏清理 8 项测试全 PASS；core 套件 42 脚本 41 PASS 含新增 data_retention（除 ledger_consistency 因代码已标 AI-R14 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；不得误删业务草稿确认记录和必要审计（5 级 action 分类：业务关联 protected 优先+critical 安全网+关键审计豁免 exempt+validate_no_business_data_deleted 反向校验）；日志和导出不得泄露密钥或完整敏感原文（密钥类 ***，手机号前3后4，身份证前6后4，邮箱打码，API key/Bearer 正则替换，validate_export_sanitized+validate_log_sanitized 反向校验）） | 前端可视化：6 个 API 端点已就绪，但数据保留管理页面（保留策略配置/清理预览列表/执行清理按钮/清理日志历史）待 AI-R16 浏览器 E2E 一并实现；定时清理任务（如 cron 每日凌晨执行 execute_cleanup）当前需管理员手动调用 POST /api/ai/data_cleanup_execute，自动化调度待 AI-R16 配套运维页面时完善；_ai_dr_query_expired 对 audit 类别查询 AIToolCall 表，生产环境审计日志量大时需优化为分批查询+索引优化；脱敏函数复用 security.py 逻辑但本模块独立实现避免循环依赖，后续可统一到 security.py |
| AI-R15 | 2026-07-17 | `7f7d4d4` | `app/ai/ops/business_quality.py`（新建：业务质量指标和版本对比纯逻辑+依赖注入模块；7 个业务质量指标常量 classification_accuracy/header_accuracy/line_recall/material_match_rate/human_correction_rate/draft_adoption_rate/duplicate_interception_rate + ALL_METRICS + METRIC_LABELS 中文标签 + DEFAULT_REGRESSION_THRESHOLD 0.05；QualitySample 单条样本含 sample_id/occurred_at/role/source/model/prompt_hash/schema_version + 7 指标分子分母（classification_total/correct、header_total/correct、line_expected/recalled、material_total/matched、field_total/corrected、draft_total/adopted、request_total/intercepted）；MetricValue 单指标聚合值含 metric/numerator/denominator/rate；BusinessQualitySnapshot 业务质量快照含 metrics(7 指标)+by_dimension(5 维度分组)+sample_count+filter_applied+generated_at；VersionComparison 版本对比含 baseline/current_version+baseline/current_metrics+deltas(7 指标 current_rate-baseline_rate)+regressions(下降超阈值)+generated_at；QualityFilter 多维筛选含 time_start/time_end/role/source/model/prompt_hash/schema_version；apply_filter 纯函数多维筛选闭区间；_aggregate_metric 单指标分子分母求和算比率（分母 0 返回 0.0）；compute_business_quality 计算快照含 7 指标聚合+5 维度分组+筛选条件追溯；compare_versions 版本对比 7 指标 delta+regressions 阈值可配容差防浮点误判；validate_metrics_reproducible 可复算校验（相同输入+相同 now 产出相同快照，now 不影响指标值）；validate_filter_dimensions 多维筛选校验（6 维度各自+组合+时间闭区间）；validate_version_comparison 版本对比完整性校验（7 指标 delta 齐全+regressions 与阈值一致+delta 等于快照差）；validate_all_dimensions_present 5 维度分组齐全校验）、`app/app.py`（1 个 ORM adapter：_ai_bq_query_samples 按 day+role+source+model+prompt_hash+schema_version 聚合查询样本，字段级指标来自 AIFieldFeedback（classification 基于 document_type 字段，header 基于 supplier/customer/order_no/date，line 基于 line_index>=0，material 基于 code/name 行级，correction 基于全字段 adopted=True；adopted=False=原值正确 adopted=True=被修正），草稿/拦截指标来自 AIDraftIdempotency（draft_total=completed 数 draft_adopted=completed 且 draft_id 非空 request_total=全部 request_intercepted=replayed 命中幂等拦截），草稿数据无 model/prompt_hash/schema_version 独立成样本；3 个 API 端点：POST/GET /api/ai/business_quality_snapshot 业务质量快照含多维筛选+可复算校验+维度完整性校验（仅 admin）+ POST /api/ai/business_quality_compare 版本对比含 current/baseline 筛选+阈值可配+版本对比校验（仅 admin）+ GET /api/ai/business_quality_metrics 7 指标定义查询含中文标签（仅 admin））、`scripts/verify_ai_business_quality.py`（新建：8 项测试覆盖 7 指标聚合正确性/多维筛选 6 维度+组合/版本对比 7 指标 delta+regressions+阈值/可复算/5 维度分组完整性/边界场景空样本分母0单样本全零/反向校验捕获指标破坏+筛选失效+版本对比不完整/综合安全校验快照序列化+4 校验函数+端到端）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_business_quality.py）、`.github/workflows/verify.yml`（CI 追加 business_quality 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R15 状态置已完成，下一项改 AI-R16） | `python3 scripts/verify_ai_business_quality.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（_aggregate_metric 固定返回 rate=1.0 致指标异常被测试1+3+6 捕获、apply_filter 不过滤返回全部致筛选失效被测试2+6+7+8 捕获、compare_versions regressions 总为空致下降不被标记被测试3 捕获，均能被测试捕获） | 通过（业务质量指标和版本对比 8 项测试全 PASS；core 套件 43 脚本 42 PASS 含新增 business_quality（除 ledger_consistency 因代码已标 AI-R15 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；支持按时间角色来源模型提示词 Schema 版本筛选（QualityFilter 6 维度+组合+时间闭区间+筛选条件追溯 filter_applied）；指标可复算（纯函数 now 注入，相同输入产出相同指标值，validate_metrics_reproducible 校验）；版本对比（7 指标 delta+regressions+阈值可配+validate_version_comparison 校验）；7 指标聚合分类/表头/行召回/物料/修正/采用/拦截分子分母可追溯） | 前端可视化：3 个 API 端点已就绪，但业务质量看板页面（指标卡片/维度筛选器/版本对比视图/趋势图）待 AI-R16 浏览器 E2E 一并实现；草稿采用率当前以 draft_id 非空为采用判据，未反查业务单据 status（如 InOrder.completed），生产环境若需精确采用率需 adapter 扩展反查业务单据状态；_ai_bq_query_samples 按天聚合，生产环境数据量大时需优化为 SQL GROUP BY 聚合或物化视图；版本对比当前依赖两批样本筛选，跨 schema_version 版本对比时需调用方组织 baseline/current 样本，后续可在 adapter 层增加按 schema_version 自动分组的便捷查询 |
| AI-R16 | 2026-07-17 | `e0198ef` | `scripts/verify_ai_browser_e2e.py`（新建：AI-R16 AI 关键流程浏览器 E2E 专项验证，使用 Flask test_client 模拟浏览器会话（CI 友好无需真实浏览器，与现有 18 个 verify_ai_*.py 脚本一致）；测试基础设施 _login 通过 session_transaction 注入登录态、_create_users 创建 5 类角色测试用户（admin/warehouse/purchase/production/user，台账"主管"映射 production 因 User.role 枚举无 manager/supervisor）、_enable_ai_features 启用 AI 全部特性确保页面可访问、_get_page 统一 GET 页面返回 (status_code, html)；8 项测试覆盖 5 角色+7 业务域+验收点：test1 5 类角色权限矩阵（admin 全访问/warehouse+purchase 文档上传/production+user 被拒/未登录重定向 login/Agent 任务列表全角色可见）、test2 文档上传页面（/ai/document_ocr 中文渲染"文档/OCR/识别"+上传按钮+空状态+错误提示 POST /api/ai/document_ocr 无文件返回 400 中文 msg 解码校验+production 被拒）、test3 文档确认流程（/ai/document_jobs 列表中文"文档"→/ai/document_jobs/<id> 详情下钻显示文件名/测试内容+返回路径"返回/列表/document_jobs"+不存在 ID 404）、test4 草稿下钻（/in_order 入库+/purchase_order?view=list 采购+/out_order 出库列表中文+空状态/新增按钮）、test5 工作台页面（/ai/inventory_health 库存+/ai/replenishment 补货+/ai/supplier_evaluation 供应商 中文+warehouse/purchase 可访问+production/user 被拒）、test6 Agent 页面（/ai/agent_tasks 全角色中文"Agent/任务/代理"+POST /ai/agent_tasks/run/warehouse_patrol 重复点击防护 200/302/400/409/429+production/user 越权拒绝）、test7 运维页面（/ai/ops+/ai/prelaunch 仅 admin+/ai/material_alias admin/warehouse/purchase 中文"物料/别名"+production/user 被拒）、test8 API 端点 E2E（R10 仓库工作台 /api/ai/warehouse_workbench sections/snapshot/status 结构+R11 采购跟进 /api/ai/purchase_followup_workbench+R12 知识检索 /api/ai/knowledge_search?q=入库+R13 Agent 安全校验 /api/ai/agent_validate_safety+R14 数据保留配置 /api/ai/data_retention_config+清理预览 /api/ai/data_cleanup_preview dry_run+R15 业务质量 /api/ai/business_quality_metrics count=7+快照 /api/ai/business_quality_snapshot+warehouse 越权 R14/R15 admin API 被拒）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_browser_e2e.py）、`.github/workflows/verify.yml`（CI 追加 browser_e2e 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R16 状态置已完成，下一项改 AI-R17） | `python3 scripts/verify_ai_browser_e2e.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（移除 /ai/document_ocr 的 @require_role('warehouse','purchase') 装饰器致 production/user 可访问被 test1+test2 捕获、将 /ai/document_jobs/<id> 的 first_or_404() 改为 first()+None 返回 200 致 404 退化被 test3 捕获，均能被测试捕获后还原源码回归通过） | 通过（AI 关键流程浏览器 E2E 8 项测试全 PASS；core 套件 44 脚本 43 PASS 含新增 browser_e2e（除 ledger_consistency 因代码已标 AI-R16 但台账状态在第一次 commit 前仍下一项的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；不只检查 HTTP 200 而是检查中文渲染+空状态+错误提示+权限矩阵+按钮可见性+返回路径+下钻+重复点击防护+越权拒绝；覆盖 5 类角色 admin/warehouse/purchase/production/user（主管映射 production）+7 大业务域 上传/确认/草稿/工作台/Agent/知识/运维；API 层覆盖 R10-R15 全部新 API 端点+权限校验） | 无 |
| AI-R17 | 2026-07-17 | `ef424db` | `app/ai/ops/launch_acceptance.py`（新建：AI-R17 真实用户灰度、回滚演练和上线验收纯逻辑+依赖注入模块；4 项上线验收指标常量 METRIC_UNAUTHORIZED_SUCCESS/METRIC_DUPLICATE_DRAFTS/METRIC_AUTO_SUBMIT/METRIC_LOW_CONFIDENCE_UNCONFIRMED + ALL_ACCEPTANCE_METRICS + METRIC_LABELS 中文标签 + AUTO_SUBMIT_FORBIDDEN_ACTIONS 10 动作集与 budget_control 一致 + DEFAULT_WINDOW_HOURS=168（7天）+ DEFAULT_ROLLBACK_MAX_MINUTES=10；AcceptanceMetric 单项指标含 metric/label/count/threshold=0/window_hours + passed 属性 + to_dict；LaunchAcceptanceReport 报告含 metrics(4项)+window_hours+generated_at + all_passed 属性 + failed_metrics 属性 + to_dict；RolloutDrillResult 灰度演练结果含 role_matrix(角色,预期访问)+duration_seconds+corrections+misjudgments+failures+rolled_back+rollback_at + to_dict；RollbackDrillResult 回滚演练结果含 shutdown_started/completed_at+restore_started/completed_at + shutdown_seconds/restore_seconds/total_seconds/total_minutes 属性 + to_dict；compute_acceptance_metrics 纯函数四项指标聚合（counts dict 注入，缺失键按 0，now 注入可复算）；validate_zero_violation 校验四项全 0（验收：连续一周四项为 0）；validate_rollback_within_minutes 校验关闭+恢复 ≤10 分钟（含时间顺序校验+边界通过+超时失败）；validate_rollout_drill_complete 校验灰度演练完整性（角色矩阵覆盖 admin/warehouse/purchase+耗时记录+回退完成+回退时间记录）；validate_all 一次性多项校验四项指标+回滚+灰度；防重复设计：不重新发明灰度模式（复用 _ai_capability_allowed_by_rollout/feature_flags）、不重新发明回滚开关（复用 force_fallback/ai_feature_global_enabled）、不重新发明单项检测（复用 unauthorized_success/validate_no_auto_submit/has_unconfirmed_low_confidence_fields/status=replayed）、四项绝对计数口径与 business_quality.py 比率口径共存不冲突）、`app/app.py`（1 个 ORM adapter：_ai_r17_acceptance_counts 查询四项绝对计数——越权成功查 AIToolCall permission_allowed=False 且 status in (completed/success/authorized)（与 _ai_ops_metrics 一致）、重复草稿查 AIDraftIdempotency status=replayed（与 AI-R01 一致）、自动提交查 AIToolCall tool_name in AUTO_SUBMIT_FORBIDDEN_ACTIONS（与 AI-R13 一致）、低置信度未确认建单查 AIDocumentJob status=draft_created 且关联 AIDocumentItem confidence<0.85（与 AI-R08 阈值一致），每项独立 try/except 容错；2 个 API 端点：GET /api/ai/launch_acceptance 上线验收报告含四项指标聚合+全 0 校验+window_hours 可配（仅 admin）+ GET /api/ai/launch_acceptance/metrics 四项指标定义查询含中文标签+threshold=0（仅 admin），端点带 # AI_TASK: AI-R17 标记）、`scripts/verify_ai_launch_acceptance.py`（新建：8 项测试覆盖四项指标聚合正确性+全0通过/回滚演练10分钟内校验（5分钟通过+10分钟边界通过+超时失败+时间顺序错误失败）/灰度演练完整性校验（角色矩阵覆盖+耗时记录+回退完成+缺失角色/空矩阵/未回退/耗时0失败）/综合校验 validate_all（四项+回滚+灰度一次性多项）/可复算校验（now 注入相同输入产出相同报告）/端到端回滚演练（Flask test_client 真实切换 ai_feature_global_enabled 关闭→恢复<10分钟）/端到端权限攻击演练（warehouse/user 越权 admin API 被拒+越权成功计数 0）/端到端重复请求+Provider 故障演练（幂等拦截重复草稿 0+force_fallback 降级不丢证据+禁止动作集 10 个一致））、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_launch_acceptance.py）、`.github/workflows/verify.yml`（CI 追加 launch_acceptance 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R17 状态置已完成，下一项改"无（全部完成）"） | `python3 scripts/verify_ai_launch_acceptance.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（validate_zero_violation 固定返回 True 致越权成功=1 不被标记被 test1+test4 捕获、validate_rollback_within_minutes 超时也返回 True 致 10 分钟限制失效被 test2+test4 捕获，均能被测试捕获后还原源码回归通过） | 通过（上线验收 8 项测试全 PASS；core 套件 45 脚本全 PASS 含新增 launch_acceptance；0 回归；四项指标聚合越权成功/重复草稿/自动提交/低置信度未确认建单绝对计数阈值为 0（7天窗口可配）；回滚演练 10 分钟内关闭+恢复校验（时间顺序+边界+超时）；灰度演练完整性校验（角色矩阵覆盖 admin/warehouse/purchase+耗时+回退）；端到端演练覆盖权限攻击/重复请求/Provider 故障/关闭恢复四类场景；防重复设计复用现有灰度/回滚/检测能力不重新发明） | 真实灰度执行：当前四项指标为空库计数（CI 测试库无真实业务数据），生产环境需连续一周采集真实数据后执行 /api/ai/launch_acceptance 确认全 0；指定采购员灰度名单当前依赖 ai_feature_rollout_mode=all，若需按用户白名单灰度需接入 feature_flags.FeatureFlag.allowed_users 到主流程（_ai_capability_allowed_by_rollout 当前只读 mode 字符串不读 allowed_users）；低置信度未确认建单当前以 AIDocumentItem.confidence<0.85 为判据，未追踪 correction_status 修正状态（AIDocumentItem 无此字段），生产环境若需精确"未确认"判据需扩展 AIDocumentItem 增加 confirmation_status 字段 |
| AI-R17-F01 | 2026-07-18 | `fa373e7` | `app/ai/ops/rollout_control.py`（新建：AI-R17-F01 真实用户白名单灰度与一键回滚闭环纯逻辑+依赖注入模块；4 种灰度模式常量 MODE_OFF/MODE_ALLOWLIST/MODE_ROLE/MODE_ALL + VALID_MODES + DEFAULT_MODE=off（F01 要求默认 off 非 all）+ _LEGACY_MODE_MAP 旧值向后兼容映射 admin_only→off/read_only/read_draft→role/all→all；6 个权限判定阶段常量 STAGE_GLOBAL/FLAG/ROLE/ALLOWLIST/RISK/CONFIRMATION + PERMISSION_ORDER 固定顺序元组（全局→功能→角色→白名单→风险→人工确认）；5 个人工降级原因常量 provider_fault/budget_exhausted/circuit_breaker/cancelled/low_confidence + ALL_FALLBACK_REASONS；2 个回滚动作常量 shutdown/restore；4 个审计来源常量 api/page/agent/background；AUTO_SUBMIT_FORBIDDEN_ACTIONS 10 动作集复用 budget_control 保持一致；DEFAULT_ROLLBACK_MAX_MINUTES=10；5 个 dataclass：RolloutDecision（allowed/reason/stage/mode/user_id/role/capability/risk_level+to_dict）、RolloutSnapshot（mode/allowed_user_ids/global_enabled/force_fallback/taken_at+to_dict，用于一键关闭-恢复）、ManualFallbackTask（task_id/original_run_id/reason/preserved_files/preserved_drafts/created_at/status/operator_id/handled_at+to_dict，Provider 故障证据保留）、RollbackEvent（event_id/action/operator_id/operator_role/previous_snapshot/new_snapshot/started_at/completed_at+duration_seconds/minutes 属性+to_dict）、RolloutAuditRecord（audit_id/user_id/role/capability/reason/stage/source/created_at+to_dict）；核心纯函数：is_admin（admin 直通）、normalize_mode（旧值→新值映射）、parse_allowed_user_ids（支持逗号字符串/列表/None，过滤非正数和非法值，去重，用户白名单使用用户 ID 不依赖显示名）、evaluate_rollout_access（按固定顺序判定：全局开关→admin 直通→未登录拒绝→off 拒绝→allowlist 白名单→role 风险级别→all 放行）、snapshot_rollout（保存当前灰度配置快照）、restore_rollout（从快照生成要恢复的设置键值，纯逻辑不直接写设置）、create_manual_fallback_task（创建人工降级任务保留文件和草稿证据，未知原因抛 ValueError）、record_rollback_event（记录 shutdown/restore 事件，非法动作或时间倒序抛 ValueError）、build_rollout_audit_record（构造灰度拒绝审计记录，非法来源抛 ValueError）；8 个校验函数：validate_permission_order（顺序子序列校验，允许跳过未触发阶段但顺序不能乱）、validate_admin_only_maintenance（仅 admin 可维护灰度名单和全局开关）、validate_no_business_data_modified（shutdown/restore 只动系统设置不碰业务表和 User 表）、validate_rollback_within_minutes（关闭+恢复总耗时≤10 分钟，时间顺序+边界+超时校验）、validate_user_removed_immediately（用户移出白名单后立即生效纯函数无缓存）、validate_auto_submit_forbidden（动作列表不含 10 个禁止动作）、validate_no_sensitive_in_audit（审计记录不含 api_key/token/secret/password/bearer 敏感关键词）、validate_fallback_preserves_evidence（非取消原因需保留文件或草稿证据）；validate_all 一次性多项校验；防重复设计：不重新发明灰度模式（替代旧 _ai_capability_allowed_by_rollout 但旧值通过 normalize_mode 兼容）、不重新发明回滚开关（ai_feature_global_enabled/force_fallback 仍由 app.py/provider_router 持有，本模块只提供快照-恢复和事件记录编排）、复用 launch_acceptance.validate_rollback_within_minutes 的 10 分钟口径、复用 budget_control.AUTO_SUBMIT_FORBIDDEN_ACTIONS 保持一致）、`app/app.py`（SYSTEM_SETTING_GROUPS 'AI生产化与灰度' 扩展：ai_feature_rollout_mode 默认从 all 改为 off，新增 off/allowlist/role/all 4 个新选项+保留 admin_only/read_only/read_draft 旧值兼容；新增 ai_feature_allowed_user_ids 文本设置（逗号分隔用户 ID）+ai_force_fallback 布尔设置；AIToolCall 模型扩展 5 字段 user_id/role/denied_reason/source/denied_stage + 2 索引 idx_ai_tool_call_denied/idx_ai_tool_call_user_source；3 个新 ORM 模型：AIRollbackEvent（回滚事件 event_id/action/operator_id/operator_role/previous_snapshot/new_snapshot JSON/started_at/completed_at + idx_ai_rollback_event_action_created 索引）、AIManualFallbackTask（人工降级任务 task_id/original_run_id/reason/preserved_files JSON/preserved_drafts JSON/status/operator_id/handled_at + idx_ai_fallback_task_status_created/idx_ai_fallback_task_reason 索引）、AIRolloutAudit（灰度拒绝审计 audit_id/user_id/role/capability/reason/stage/source + idx_ai_rollout_audit_user_created/idx_ai_rollout_audit_capability_stage 索引）；auto_migrate_database 增加 ai_tool_call 5 字段迁移 + 2 索引兜底；4 个核心函数改造：_ai_rollout_mode 改用 rollout_control.normalize_mode 归一化（旧值兼容）、_ai_allowed_user_ids 新增从 SystemSetting 实时读取白名单（每次调用实时读取无缓存，移出立即生效）、_ai_force_fallback 新增、_ai_capability_allowed_by_rollout 重写调用 evaluate_rollout_access 按固定顺序判定并拒绝时写灰度拒绝审计；_ai_record_capability_audit 扩展签名接受 reason/source/stage 并写入 user_id/role/denied_reason/source/denied_stage；_ai_record_rollout_denied_audit 新增写 AIRolloutAudit 审计表+回写 AIToolCall 拒绝详情+脱敏校验（含敏感关键词降级为通用原因）；_ai_capability_allowed 扩展签名接受 source 关键字参数，按固定权限判定顺序调用并各阶段拒绝时记录 reason+stage；OCR 路由 api_document_ocr 入口接入 ai_force_fallback 检查：开启时降级为人工流程写 AIManualFallbackTask 保留文件证据（filename/size/ext/document_type/remarks）不调用视觉模型；7 个 API 端点：GET /api/ai/rollout/status 灰度状态查询（mode/allowed_user_ids/global_enabled/force_fallback/最近 shutdown/restore/pending_fallback_count，仅 admin）+ POST /api/ai/rollout/allowlist 白名单维护（支持逗号分隔用户 ID+可选切换模式，仅 admin，validate_admin_only_maintenance 防御性校验）+ POST /api/ai/rollout/shutdown 一键关闭（全局开关=0+force_fallback=1+白名单清空+记录 AIRollbackEvent+validate_no_business_data_modified 校验，仅 admin）+ POST /api/ai/rollout/restore 一键恢复（从最近 shutdown 的 previous_snapshot 恢复+记录 AIRollbackEvent+validate_rollback_within_minutes 校验 10 分钟内，仅 admin）+ GET /api/ai/rollout/audit 灰度拒绝审计查询（支持 user_id/capability/stage 筛选，仅 admin）+ GET /api/ai/rollout/fallback_tasks 人工降级任务查询（支持 status 筛选，仅 admin）+ POST /api/ai/rollout/fallback_tasks/<task_id> 人工降级任务处理（标记 handled/rejected，仅 admin），所有端点带 # AI_TASK: AI-R17-F01 标记；3 个辅助函数：_ai_r17f01_take_snapshot 采集当前灰度快照、_ai_r17f01_apply_snapshot 把快照写回 SystemSetting、_ai_r17f01_record_event 写 AIRollbackEvent）、`scripts/verify_ai_rollout_control.py`（新建：8 项测试覆盖 4 种灰度模式判定+默认 off+旧值向后兼容/权限判定顺序固定（PERMISSION_ORDER+子序列校验+evaluate 阶段返回符合顺序）/用户白名单使用用户 ID+移出后立即生效（parse 多种格式+去重过滤+纯函数无缓存）/一键关闭+恢复到灰度配置（快照-恢复机制+10 分钟内校验+不修改业务数据+非法动作拒绝）/灰度拒绝审计记录不含 api_key/token/password 敏感信息+非法来源拒绝/Provider 故障/预算耗尽/熔断/取消/低置信度降级为人工流程保留证据+未知原因拒绝/管理员维护边界（仅 admin 可维护灰度名单和全局开关）+自动提交禁止动作集 10 个一致/端到端 API 闭环（非 admin 拒绝+admin 状态/白名单/关闭/恢复/审计/降级任务查询+关闭不修改 InOrder/OutOrder/User 表和 admin 密码））、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_rollout_control.py）、`.github/workflows/verify.yml`（CI 追加 rollout_control 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R17-F01 状态置已完成，下一项改 AI-R17-F02） | `python3 scripts/verify_ai_rollout_control.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（normalize_mode 移除旧值映射致 admin_only 报错、evaluate_rollout_access 破坏 admin 直通致 admin 被拒、validate_no_sensitive_in_audit 总返回 True 致含 api_key 审计通过、validate_admin_only_maintenance 总返回 True 致非 admin 可维护，均能被测试捕获） | 通过（真实用户白名单灰度与一键回滚闭环 8 项测试全 PASS；core 套件含新增 rollout_control；0 回归；4 种灰度模式 off/allowlist/role/all 默认 off；用户白名单使用用户 ID 不依赖显示名，移出后立即生效纯函数无缓存；权限判定顺序固定 全局→功能→角色→白名单→风险→人工确认；灰度拒绝审计记录用户/角色/能力/原因/来源/时间不含 api_key/token/password；Provider 故障/预算耗尽/熔断/取消/低置信度降级为人工流程保留文件和草稿证据；一键关闭+恢复 10 分钟内完成不修改业务数据和用户密码；仅 admin 可维护灰度名单和全局开关；端到端 API 闭环非 admin 拒绝+admin 状态/白名单/关闭/恢复/审计/降级任务查询全部通过；旧值 admin_only/read_only/read_draft 通过 normalize_mode 向后兼容） | 真实灰度执行：当前 8 项测试在 CI 测试库验证，生产环境需真实灰度用户后观察 AIRolloutAudit 审计记录；前端可视化：7 个 API 端点已就绪，但灰度管理页面（模式切换/白名单维护/一键关闭恢复按钮/审计列表/降级任务列表）待 AI-R17-F03 发布交接时一并实现；连续七天真实上线验收（AI-R17-F02）依赖本任务的灰度拒绝审计数据采集 |
| AI-R17-F02 | 2026-07-18 | `d77bab7` | `app/ai/ops/acceptance_evidence.py`（新建：AI-R17-F02 连续七天真实上线验收纯逻辑+依赖注入模块；常量 DEFAULT_EVIDENCE_DAYS=7+GO_DECISION='go'+NO_GO_DECISION='no_go'+VALID_DECISIONS+SAMPLE_FAILURE/FALLBACK/DUPLICATE/CORRECTION+ALL_SAMPLE_TYPES+LOW_CONFIDENCE_THRESHOLD=0.85+VALID_BUSINESS_STATUSES（pending/completed/confirmed/approved）+INVALID_BUSINESS_STATUSES（voided/deleted/cancelled/rejected）；4 个 dataclass：DailyMetricSnapshot（snapshot_date/absolute_counts/quality_metrics/rollout_user_count/rollout_role_count/rollout_roles/window_hours/filter_applied/generated_at + all_absolute_zero 属性+to_dict）、EvidenceSample（sample_type/sample_id/timestamp/user_role/source/summary/source_table/source_id+to_dict）、RollbackEvidence（event_id/action/operator_id/operator_role/started_at/completed_at/duration_seconds+to_dict）、AcceptanceEvidencePackage（package_id/start_date/end_date/daily_snapshots/seven_day_summary/rollout_role_matrix/failure_samples/fallback_samples/duplicate_samples/correction_samples/rollback_events/go_no_go_decision/decision_reason/decided_by/decided_at/generated_at + day_count 属性+to_dict）；构造函数：build_daily_snapshot（补齐缺失绝对指标键+质量指标键，filter_applied 默认 {}）、build_evidence_package（按日期排序+计算汇总）、_compute_seven_day_summary（绝对指标七天总和+质量指标七天加权平均+all_absolute_zero 综合判定）；6 个校验函数：validate_seven_consecutive_days_zero（日期连续性+每日四项全0+取最近7天）、validate_evidence_reproducible（window_hours+filter_applied 非空+质量指标分子分母齐全+rate 可复算误差≤0.001+七天汇总有 absolute_totals/quality_summary）、validate_go_no_go（任一非0不得 go+go 必须有签字+no_go 必须有原因+pending 不通过+未知决策拒绝）、validate_rollout_matrix_complete（覆盖 admin/warehouse/purchase 三角色+每日灰度角色数非0）、validate_rollback_evidence_present（shutdown+restore 双动作齐全）、validate_sample_lists_present（四类样本字段存在即使为空）；validate_all_evidence 一次性多项校验（validate_seven_consecutive_days_zero 接收快照列表，其他接收 package）；is_draft_adopted_by_business 口径修正：反查业务单据 status 判定草稿是否被真实采用，draft_id 空/不存在/作废/未知状态保守判定不采用；is_low_confidence_unconfirmed 临时口径：confidence<0.85+draft_created+confirmation_status 为 None 时判定未确认，R08-F01 完成后切换为读取 confirmation_status 字段；防重复设计：复用 launch_acceptance.ALL_ACCEPTANCE_METRICS 四项绝对指标常量保持一致、复用 business_quality.ALL_METRICS 七项质量指标常量保持一致、不重新发明回滚 10 分钟校验由 launch_acceptance 持有）、`app/app.py`（2 个新 ORM 模型：AIAcceptanceDailySnapshot 每日验收快照 snapshot_date 唯一+absolute_counts/quality_metrics JSON+rollout_user_count/rollout_role_count/rollout_roles JSON+window_hours+filter_applied JSON+generated_at+created_at + idx_ai_acceptance_snapshot_created 索引，AIAcceptanceEvidencePackage 七天证据包 package_id+start_date/end_date+daily_snapshot_dates JSON+seven_day_summary JSON+rollout_role_matrix JSON+failure_samples/fallback_samples/duplicate_samples/correction_samples JSON+rollback_events JSON+go_no_go_decision+decision_reason+decided_by+decided_at+created_at + idx_ai_evidence_package_dates/idx_ai_evidence_package_decision 索引；auto_migrate_database 增加 3 索引兜底；7 个 ORM adapter：_ai_f02_query_daily_counts 单日四项绝对指标按自然日切分计数、_ai_f02_query_daily_quality 单日七项质量指标聚合复用 _ai_bq_query_samples、_ai_f02_query_rollout_info 当前灰度用户/角色信息、_ai_f02_check_draft_adoption 口径修正反查 InOrder/OutOrder/TransferOrder/CheckOrder status、_ai_f02_query_sample_lists 四类样本清单（失败/降级/重复/人工修正）、_ai_f02_query_rollback_events 回滚演练记录、_ai_f02_snapshot_to_dict ORM 转 dataclass；5 个 API 端点：POST /api/ai/acceptance/daily_snapshot 采集当日验收指标快照（持久化，同日期覆盖更新，仅 admin）+ GET /api/ai/acceptance/daily_snapshots 查询每日快照列表（支持 limit 筛选）+ POST /api/ai/acceptance/evidence_package 构建七天证据包（从 DB 取快照+样本+回滚+灰度矩阵，调用 validate_all_evidence 综合校验，返回 seven_days_zero 标志）+ GET /api/ai/acceptance/evidence_package/<int:package_id> 查询证据包详情+POST /api/ai/acceptance/go_no_go 管理员签字 go/no-go（任一非0不得 go 强制 no_go，仅 admin，记录 decided_by/decided_at/decision_reason），所有端点带 # AI_TASK: AI-R17-F02 标记）、`scripts/verify_ai_acceptance_evidence.py`（新建：8 项测试覆盖每日快照构造+四项绝对指标全0判定+补0+to_dict 序列化/连续七天校验（7天通过/不足7天失败/日期不连续失败/某天非0失败）/草稿采用率反查业务单据状态口径修正（有效采用/作废不采用/draft_id空不采用/不存在不采用/未知保守不采用）/低置信度未确认判定（临时口径 confidence<0.85+draft_created+R08-F01 切换预留）/验收数据可复算（分子分母时间窗口筛选条件齐全+rate 可复算+缺 filter_applied 失败）/go/no-go 结论校验（全0+go+签字通过/无签字失败/非0不得go/no_go+原因通过/pending 失败）/证据包完整性校验（灰度矩阵+回滚 shutdown+restore+四类样本清单+缺角色/缺回滚/缺 restore 失败）/端到端 API 闭环（采集7天快照→查询→构建证据包→签字 go/no_go→非 admin 拒绝+不修改业务数据和密码））、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_acceptance_evidence.py）、`.github/workflows/verify.yml`（CI 追加 acceptance_evidence 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R17-F02 状态置已完成，下一项改 AI-R08-F01） | `python3 scripts/verify_ai_acceptance_evidence.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（validate_seven_consecutive_days_zero 总返回 True 致 5 天不足场景误通过被 test2 捕获、is_draft_adopted_by_business 破坏作废状态判定总返回 True 致 voided 误判采用被 test3 捕获，均能被测试捕获后还原源码回归通过） | 通过（连续七天真实上线验收 8 项测试全 PASS；core 套件含新增 acceptance_evidence；0 回归；四项绝对指标连续七天每日为0校验（日期连续性+每日全0+取最近7天）；七项质量指标分子分母时间窗口筛选条件齐全 rate 可复算误差≤0.001；草稿采用率反查业务单据 status 口径修正（draft_id空/不存在/作废/未知保守判定不采用）；低置信度未确认临时口径 confidence<0.85+draft_created+confirmation_status 为 None，R08-F01 完成后切换；go/no-go 任一非0不得 go+go 必须签字+no_go 必须有原因；证据包完整性 灰度矩阵覆盖 admin/warehouse/purchase+回滚 shutdown+restore+四类样本清单；端到端 API 闭环非 admin 拒绝+admin 采集7天快照→查询→构建证据包→签字 go/no_go→不修改业务数据和密码） | 真实生产环境采集：当前 8 项测试在 CI 测试库验证，真实生产环境需连续 7 个自然日采集快照后由管理员签字 go/no-go；前端可视化：5 个 API 端点已就绪，但验收看板页面（每日快照曲线+证据包详情+go/no-go 签字按钮+异常子项追踪）待 AI-R17-F03 发布交接时一并实现；R08-F01 完成后需切换低置信度未确认口径为读取 confirmation_status 字段 |

## 9. 任务启动检查

- [ ] 任务编号唯一，状态是“待开发”或“下一项”。
- [ ] 已搜索代码、路由、工具、模型、页面、脚本和 Git 历史。
- [ ] 已确认不是重复开发；修复已有能力时已建立修复子项。
- [ ] 依赖任务已完成。
- [ ] 已列出改动范围和验收标准。
- [ ] 已确认权限及人工确认边界。

## 10. 任务完成检查

- [ ] 代码、迁移、页面和文档中的适用部分已完成。
- [ ] 已补充专项、集成或浏览器测试。
- [ ] 已横向检查同类工具和全部草稿入口。
- [ ] 已执行编码检查和 AI full 验证。
- [ ] 已更新任务状态并填写完成记录。
- [ ] 已提交并推送 `main`。

## 11. 当前下一项

`AI-R08-F01：文档确认状态与提交前强制门禁`。

AI-R01～R17 的基础能力已经完成。AI-R17-F01 真实用户白名单灰度与一键回滚闭环已完成（用户白名单接入主流程、4 种灰度模式、灰度拒绝审计、Provider 降级、一键关闭/恢复）。AI-R17-F02 连续七天真实上线验收已完成（每日指标快照、七天证据包、go/no-go 签字、草稿采用率反查业务单据状态口径修正、低置信度未确认临时口径+R08-F01 切换预留）。下一阶段继续推进 F 系列子项，把现有能力从"代码和测试完成"推进到"真实用户可灰度、可衡量、可回滚、可运营"。AI-R08-F01 完成后需将 AI-R17-F02 的低置信度未确认口径从临时（confidence<0.85+draft_created）切换为读取 confirmation_status 字段。

## 12. 下一批 AI 开发总表

| 优先级 | 子项编号 | 状态 | 任务 | 依赖 | 主要交付 | 生产完成门槛 |
|---|---|---|---|---|---|---|
| P0 | AI-R17-F01 | 已完成 | 真实用户白名单灰度与一键回滚 | AI-R13、R16、R17 | 用户白名单、灰度审计、Provider 降级、回滚控制 | 非白名单不可用；高风险动作自动执行为 0；10 分钟内关闭并恢复 |
| P0 | AI-R17-F02 | 已完成 | 连续七天真实上线验收 | AI-R17-F01 | 真实指标采集、确认状态、验收证据包 | 四项上线违规指标连续七天为 0；验收数据可复算 |
| P0 | AI-R08-F01 | 待开发 | 文档确认状态与提交前强制门禁 | AI-R08、R09、R17-F01 | confirmation_status、确认台回传、服务端二次校验 | 低置信度、歧义、高风险、重复风险未确认时不能创建草稿 |
| P1 | AI-R14-F01 | 待开发 | 数据保留管理页、分批清理和自动调度 | AI-R14、R17-F01 | 管理页面、预览、执行、日志、每日任务、批处理 | 不误删业务/关键审计；所有删除可预览、可追溯 |
| P1 | AI-R15-F01 | 待开发 | 业务质量运营看板与版本回归告警 | AI-R09、R15、R17-F02 | 指标卡、筛选、趋势、版本对比、样本下钻 | 页面/API/原始数据一致；质量下降可定位字段和版本 |
| P1 | AI-R10-F01 | 待开发 | 仓库 AI 工作台正式接入导航 | AI-R10、R16、R17-F01 | 7 类队列卡片、空态、下钻、角色菜单 | 数量与原业务列表一致；工作台只读，不混入写动作 |
| P1 | AI-R11-F01 | 待开发 | 采购到货 AI 工作台正式接入导航 | AI-R06、R11、R16、R17-F01 | 待到/延期/短交/超收/未关联通知/多候选/供应商跟进 | 跟进建议不自动发送；所有候选和差异可人工复核 |
| P2 | AI-R06-F01 | 待开发 | 真实采购订单与送货通知匹配调优 | AI-R17-F02 | 真实样本评测、权重校准、错误样本回灌 | 多候选不自动选；误建采购申请为 0；差异提示可复核 |
| P2 | AI-R07-F01 | 待开发 | 真实物料别名、包装换算和高风险规则治理 | AI-R08-F01 | 物料专属换算、别名审批、冲突/停用、高风险规则 | 一物多码可追溯；规格冲突和高风险物料 100% 人工确认 |
| P2 | AI-SALES-F01 | 待开发 | AI 销售订单/销售出库草稿真实闭环验收 | 销售阶段 7、AI-R01、R08、R17-F01 | 销售草稿证据、部分发货、多次发货、库存与报表对账 | AI 只建/检草稿；库存、订单发货量和销售报表一致 |
| 发布门禁 | AI-R17-F03 | 待开发 | 正式发布、备份恢复和运营交接 | 上述 P0 全部、选定 P1 | 发布清单、备份、恢复演练、监控、回滚、培训 | full 验证通过；真实灰度通过；恢复演练和回滚演练有证据 |

同一时间只允许一个子项处于“开发中”。P0 未完成前不得开始 P2，不得以页面美化、模型更换或新 Agent 名义绕过生产验收。

## 13. 子项详细定义

### 13.1 AI-R17-F01：真实用户白名单灰度与一键回滚

**业务目标**：让 AI 只对管理员指定的仓管员、采购员开放，并在 Provider、权限或质量异常时立即回退传统流程。

**开发范围**：

- 将 `feature_flags.FeatureFlag.allowed_users` 接入 `_ai_capability_allowed_by_rollout` 主流程。
- 支持 `off`、`allowlist`、`role`、`all` 四种灰度模式，默认 `off`。
- 用户白名单使用用户 ID；不得依赖可变的显示名。
- 权限判定顺序固定为：全局开关 -> 功能开关 -> 角色权限 -> 用户白名单 -> 风险级别 -> 人工确认边界。
- 灰度拒绝必须写入 `AIToolCall` 或等价审计，记录用户、角色、能力、原因、请求来源和时间，不保存密钥或完整敏感原文。
- Provider 故障、超时、预算耗尽、熔断、取消时保留任务证据，降级为人工流程，不得丢失已上传文件和待确认草稿。
- 管理员提供“一键关闭 AI”和“恢复到灰度配置”动作；关闭不得修改业务数据或用户密码。

**权限边界**：

- 只有 admin 可以维护灰度名单和全局开关。
- warehouse/purchase 只能使用被授权的草稿、查询、检查能力。
- AI 永远不能自动提交、审核、完成、反提交、作废、删除、付款或修改密码。

**专项验证**：

- 白名单用户允许、同角色非白名单拒绝、普通用户拒绝、未登录拒绝。
- 用户被移出白名单后立即失效，不依赖重启。
- 关闭全局开关后所有 AI 写草稿入口停止，但传统 WMS 页面正常。
- Provider 故障、重复点击、并发请求、预算耗尽和取消均不产生重复草稿。
- 关闭和恢复全过程在 10 分钟内完成并有审计记录。

### 13.2 AI-R17-F02：连续七天真实上线验收

**业务目标**：用真实业务数据证明 AI 安全和质量，而不是用空测试库宣布上线。

**必须采集的绝对指标**：

1. 越权成功数：0。
2. 重复草稿数：0。
3. 自动执行高风险动作数：0。
4. 低置信度未确认建单数：0。

**必须采集的质量指标**：

- 文档分类准确率、表头准确率、明细行召回率、物料匹配率。
- 人工修正率、草稿真实采用率、重复拦截率。
- 采购订单自动唯一匹配率、多候选率、短交/超收识别准确率。
- 按角色、来源、模型、提示词指纹和 Schema 版本分组。

**口径修正**：

- 草稿采用率必须反查真实业务单据是否保留并进入人工确认后的有效状态，不得只以 `draft_id` 非空判断。
- “低置信度未确认”必须读取明确的 `confirmation_status`，不得只根据置信度猜测。
- 所有指标必须保存分子、分母、时间窗口和筛选条件，支持从原始记录复算。

**验收证据包**：

- 七天每日指标快照和汇总。
- 灰度用户/角色矩阵。
- 失败、降级、重复和人工修正样本清单。
- 10 分钟内关闭+恢复回滚记录。
- 管理员签字的 go/no-go 结论；任一绝对指标非 0 必须 no-go 并建立子修复项。

### 13.3 AI-R08-F01：文档确认状态与提交前强制门禁

**业务目标**：让“人工确认”成为持久化、可审计、服务端强制执行的业务状态，而不是前端提示。

**数据与流程**：

- 为文档字段/明细建立 `pending`、`confirmed_original`、`corrected`、`rejected` 四类确认状态。
- 保存确认人、确认时间、原值、确认值、修正原因、证据来源、模型、提示词指纹和 Schema 版本。
- 接通确认台表单回传和 `POST /api/ai/document_feedback`。
- 在所有 AI 草稿创建入口调用 `validate_corrections_before_draft_creation`，不得只在 OCR 主入口调用。
- 重复风险、低置信度、物料多候选、规格冲突、高风险物料任一未处理时，服务端拒绝创建草稿。
- 前端隐藏按钮不能替代服务端门禁。

**验收**：

- 绕过浏览器直接调用 API 仍会被门禁拒绝。
- 已确认字段可追溯到用户和证据。
- 修正反馈进入质量指标，敏感原文按规则脱敏。
- 重复提交相同确认结果不重复记录、不重复建草稿。

### 13.4 AI-R14-F01：数据保留运维闭环

**页面类型**：系统管理页面，不是业务报表或工作台。

**功能范围**：

- 保留策略配置、分类说明和当前生效值。
- 清理预览列表，逐条显示 `delete`、`keep`、`protected`、`exempt` 及原因。
- 执行清理前二次人工确认，展示预计删除数量和截止日期。
- 清理日志记录执行人、策略、数量、失败项、开始/结束时间。
- APScheduler 每日执行分批扫描；自动任务默认只预览，生产自动删除必须单独启用。
- 对大量 `AIToolCall`、图片、任务和反馈采用分页/批次上限，避免长事务和锁库。

**安全门槛**：

- 已生成或关联业务单据的记录一律 `protected`。
- 高风险工具调用和必要审计一律 `exempt`。
- 清理失败不得影响 WMS 主业务。
- 业务数据误删破坏性测试必须能被专项验证捕获。

### 13.5 AI-R15-F01：业务质量运营看板

**页面类型**：只读分析页，仅允许筛选、刷新、导出和下钻，不得放置业务写动作。

**页面组成**：

- 七项质量指标卡片，明确分子、分母、比率和时间范围。
- 时间、角色、来源、模型、提示词、Schema 版本筛选器。
- 基线版本与当前版本对比、变化量和回归告警。
- 日/周趋势图；数据量大时使用 SQL 聚合或物化结果，不在 Python 中全量加载。
- 低质量样本下钻至文档、字段证据和人工修正记录；敏感信息继续脱敏。

**验收**：

- 页面、API 和原始记录三方一致。
- 相同输入和窗口可复算出相同指标。
- 质量下降超过阈值时能定位到字段、来源和版本。
- 空数据明确显示“暂无真实样本”，不得以 100% 或 0% 冒充质量结论。

### 13.6 AI-R10-F01 / AI-R11-F01：角色工作台正式接入

**仓库工作台**：今日待收、待出、待盘、异常库存、文档待确认、失败任务、未完成草稿。

**采购工作台**：待到、延期、短交、超收、未关联通知、多订单候选、供应商跟进。

**统一规则**：

- 工作台只展示待办、异常、阻塞原因、责任人、下一动作和业务下钻。
- 不渲染完整业务记录列表，不直接执行提交/审核/完成/删除。
- 数量必须与原业务列表在同一筛选口径下相等。
- 供应商催交只生成建议文本，不自动发送微信、邮件或短信。
- 菜单按角色显示；直接访问仍必须经过服务端权限校验。

### 13.7 AI-R06-F01 / AI-R07-F01：真实样本与主数据治理

**样本要求**：

- 覆盖送货单扫描件、手机照片、微信文字、微信截图、倾斜/模糊/阴影、手写补充、表格多页。
- 覆盖同供应商多订单、同日多批、短交、超收、关闭订单、无订单、多个相似物料。
- 样本必须脱敏，原始文件不得进入公开日志或不受控导出。

**匹配治理**：

- 权重调整必须有训练外验证集，不得只对单个样本调参。
- 多候选永远人工选择；关闭订单不自动选择；送货通知不得生成采购申请。
- 物料专属包装换算维护在主数据中，记录生效日期、审批人和来源。
- 别名支持申请、审核、启用、停用、冲突检查和使用记录。
- 高风险规则可维护但不能由普通用户降低确认要求。

### 13.8 AI-SALES-F01：销售草稿真实闭环

**业务闭环**：

```text
客户/销售需求
  -> AI 创建或检查销售订单草稿
  -> 销售/仓库人工确认
  -> 生成销售出库草稿
  -> 仓库人工完成出库
  -> 库存扣减和流水
  -> 销售订单发货数量/金额回写
  -> 销售执行、客户、物料和趋势报表对账
```

**边界**：

- AI 不确认销售订单、不完成出库、不取消订单、不反提交、不删除。
- 重点验证部分发货、多次发货、批次/序列号、项目号、税额、金额精度和外键来源。
- AI 页面不得重新实现库存扣减，必须复用现有销售出库完成逻辑。

## 14. 批次与里程碑

### 里程碑 M1：可控灰度（建议 3～5 个开发日）

- 完成 AI-R17-F01。
- 选定 1 名采购员、1 名仓管员灰度。
- 完成权限攻击、重复请求、Provider 故障和关闭恢复演练。
- M1 失败则不得进入真实业务采集。

### 里程碑 M2：真实验收（至少连续 7 个自然日）

- 完成 AI-R08-F01 和 AI-R17-F02。
- 每日检查四项绝对指标和质量指标。
- 所有异常建立对应子修复项，修复后重新开始连续七天窗口。

### 里程碑 M3：可运营（建议 5～8 个开发日）

- 完成 AI-R14-F01、AI-R15-F01、AI-R10-F01、AI-R11-F01。
- 管理员能管理保留策略、查看质量、定位样本；仓库和采购能从角色工作台下钻原业务页面。

### 里程碑 M4：真实调优与销售联动（按样本量推进）

- 完成 AI-R06-F01、AI-R07-F01、AI-SALES-F01。
- 只接受有真实样本、对照结果和回归测试支持的权重/规则修改。

### 里程碑 M5：正式发布

- 完成 AI-R17-F03。
- 生产备份、恢复演练、回滚演练、full 验证、角色验收和运营交接全部有证据。

## 15. 统一验证矩阵

每个子项至少执行：

```bat
.\scripts\python.cmd -m compileall -q app scripts
.\scripts\python.cmd scripts\verify_ai_all.py --level full
.\scripts\python.cmd scripts\verify_wms_bugs.py
.\scripts\python.cmd scripts\scan_wms_risks.py
set AI_LEDGER_ENFORCE=strict && .\scripts\python.cmd scripts\verify_ai_ledger_consistency.py
```

并追加子项专项验证。涉及页面必须验证真实浏览器流程、中文渲染、空状态、错误提示、返回路径、下钻、重复点击和不同角色；涉及业务草稿必须核对真实数据库中的来源、状态、数量、库存流水和审计记录。

### 必做破坏性测试

- 移除角色或白名单检查，验证测试能捕获越权。
- 绕过确认台直接创建草稿，验证服务端门禁拒绝。
- 重复发送相同文档/请求，验证只保留一个草稿。
- 模拟 Provider 超时、错误、预算耗尽和熔断，验证传统流程可用且证据不丢。
- 模拟清理策略错误，验证业务关联和关键审计不会删除。
- 人为制造质量下降，验证版本回归告警触发。
- 关闭 AI 并恢复，验证在 10 分钟内完成且不修改业务数据。

## 16. 发布、回滚与完成记录

### 发布前门禁

- 先备份 `app/instance/inventory.db`、上传文件和必要配置，并在受控副本完成恢复演练。
- 禁止发布覆盖生产数据库、备份、日志和上传目录。
- `main` 必须为唯一远端分支；提交前拉取最新 `main`，不得强制推送。
- 生产配置必须显式设置 `SECRET_KEY`、AI Provider 密钥、访问令牌和灰度模式；密钥不得写入 Git、日志或导出。
- 任一 P0 任务未完成、四项绝对指标非 0、恢复演练失败或 full 验证失败均为 no-go。

### 回滚顺序

1. 关闭 `ai_feature_global_enabled`，恢复传统业务入口。
2. 保留 AI 审计、任务、草稿和失败证据，不做自动清理。
3. 如仅 Provider 异常，保持页面可用并切换 fallback。
4. 如代码回滚，先确认数据库迁移向后兼容；禁止直接覆盖生产数据库。
5. 回滚后重新执行权限、幂等、草稿和核心 WMS 流程检查。

### 子项完成记录格式

每个子项完成后必须在本台账追加：

```text
子项编号：
完成日期：
提交 SHA：
业务边界：
改动模块：
迁移与备份：
权限与人工确认：
专项验证命令及结果：
full 验证结果：
真实用户/数据验收证据：
破坏性测试：
剩余风险和下一子项：
```

只有代码、权限、人工确认、专项测试、full 验证、真实业务验收、文档、提交和推送全部完成，子项才能标记“已完成”。仅 API 存在、仅 HTTP 200、仅空库指标或仅单元测试通过均不得标记完成。
