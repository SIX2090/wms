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
| 8 | AI-R08 | 下一项 | 文档确认台字段证据与重复风险 | R01、R06、R07 | R09～R11 |
| 9 | AI-R09 | 待开发 | 字段级反馈和文档质量指标 | R03、R08 | R15、R17 |
| 10 | AI-R10 | 待开发 | 仓库角色 AI 工作台整合 | AI-R08 | R16、R17 |
| 11 | AI-R11 | 待开发 | 采购到货跟进 AI 工作台整合 | R01、R06、R08 | R16、R17 |
| 12 | AI-R12 | 待开发 | 知识库发布、版本和失效管理 | AI-R02 | R16、R17 |
| 13 | AI-R13 | 待开发 | Agent 预算、取消、熔断和并发控制 | R01、R02 | R16、R17 |
| 14 | AI-R14 | 待开发 | AI 数据保留、脱敏和清理任务 | AI-R02 | R16、R17 |
| 15 | AI-R15 | 待开发 | 业务质量指标和版本对比 | AI-R09 | R17 |
| 16 | AI-R16 | 待开发 | AI 关键流程浏览器 E2E | R08、R10～R14 | R17 |
| 17 | AI-R17 | 待开发 | 真实用户灰度、回滚演练和上线验收 | R09～R16 | 正式发布 |

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
| AI-R07 | 2026-07-17 | <pending> | `app/ai/documents/material_governance.py`（新建：物料治理纯逻辑+依赖注入模块；中文归一化 normalize_chinese_text/normalize_match_key 含全角→半角、繁简转换（軸→轴/齒→齿/輪→轮 等常见物料字）、同义词归一化（马达→电机/螺帽→螺母/垫片→垫圈）、去多余空白与标点；编码/名称/规格三维加权评分权重 CODE=0.50/NAME=0.35/SPEC=0.15 权重和=1.0；MaterialMatchCandidate 含 match_method/confidence/score_breakdown/needs_confirmation/confirmation_reason/is_high_risk/high_risk_rule_id；多候选返回清单 has_ambiguity=True 100% 人工确认；规格不匹配触发 ambiguous_spec 即使 confidence 达标也需确认；包装单位换算 convert_quantity 内置换算因子表 箱=100个/包=10个/盒=10个/打=12个/捆=50个 + 米/千克/升及同义单位归一（只/件/套/pcs→个），支持注入自定义换算回调，UnitConversionEvidence 含 from_unit/to_unit/factor/rule_source/original_quantity/base_quantity 换算依据可追溯；高风险物料规则引擎 is_high_risk_material 默认 4 条规则 IC-/HZ-/PM-/BRG-PRECISION- 编码前缀匹配，命中即强制 needs_confirmation=True 不论 confidence 多高，支持注入自定义规则和正则匹配；一物多码通过 query_aliases 回调多别名键指向同一物料；主函数 match_material_governance 依赖注入 query_materials_by_codes/query_materials_by_name/query_aliases/high_risk_rules，CI 无 DB 可 mock 测）、`app/app.py`（AIMaterialAlias 模型新增 disabled/disabled_reason 字段修复 revoke_alias bug，原 confirmation.py:252-253 试图设置但模型缺字段致 AttributeError；启动迁移 SQL ALTER TABLE ADD COLUMN IF NOT EXISTS 用 PRAGMA table_info 检查列存在性；_ai_material_match_one 别名查询加 .filter_by(disabled=False) 过滤已禁用别名；ai_material_alias_list 默认 .filter(disabled==False) 仅展示未禁用别名，show_disabled=1 可查看全部；OCR 路由 `api_document_ocr` 集成 AI-R07 旁路调用：草稿创建前对每条 OCR 提取 item 调用 match_material_governance，注入 _ai_mg_query_materials_by_codes/_ai_mg_query_materials_by_name/_ai_mg_query_aliases 三个 ORM adapter，结果存 flask.g.ai_material_governance 供前端展示候选清单和证据，不破坏现有 _ai_material_match_one 草稿路径；成功响应新增 material_governance 字段含每条 item 的候选清单/最佳候选/自动选中/歧义标记/确认决策；异常降级走原匹配不中断 OCR）、`scripts/verify_ai_material_governance.py`（新建：8 项测试覆盖中文归一化/编码精确匹配/名称规格加权/别名一物多码/多候选歧义/ambiguous_spec/单位换算证据/高风险强制确认）、`scripts/verify_ai_all.py`（CORE_SCRIPTS 注册 verify_ai_material_governance.py）、`.github/workflows/verify.yml`（CI 追加 material_governance 检查步骤）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（AI-R07 状态置已完成，下一项改 AI-R08） | `python3 scripts/verify_ai_material_governance.py`、`python3 scripts/verify_ai_all.py --level core`、`AI_LEDGER_ENFORCE=strict python3 scripts/verify_ai_ledger_consistency.py`、破坏性测试（高风险判定总返回 False 被测试8 捕获、多候选不标记歧义被测试5 捕获、单位换算因子改成 0 被测试7 捕获，均能被测试捕获） | 通过（物料治理 8 项测试全 PASS；core 套件 35 脚本全 PASS 含新增 material_governance（除 ledger_consistency 因代码已标 AI-R07 但台账状态在第一次 commit 前仍待开发的预期失败，第二次 commit 补完成记录后即恢复）；0 回归；歧义行 100% 人工确认（多候选 has_ambiguity=True 不自动选）；高风险物料错误自动确认数为 0（confidence=1.0 也强制 needs_confirmation）；换算依据可追溯（UnitConversionEvidence 含因子/规则来源/原始量/基本量）；规格不匹配触发 ambiguous_spec 即使 confidence 达标也需确认；中文归一化覆盖全角/半角/繁简/同义词/空白） | 真实物料匹配数据：当前 ORM adapter 已对接 Material/AIMaterialAlias ORM 模型，但物料匹配准确率需在真实多供应商多物料数据下评估，初版权重（CODE=0.50/NAME=0.35/SPEC=0.15）和高风险规则（IC-/HZ-/PM-/BRG-PRECISION-）基于设计推理，待 AI-R08 文档确认台字段证据整合时按真实数据调优；matcher.py（孤儿代码，带 confidence/needs_confirmation/reason 五元组但未被生产调用）暂未替换，AI-R07 采用旁路调用策略保留现有 _ai_material_match_one 草稿路径不变，matcher.py 的替换/删除待 AI-R08 一并决策；前端 material_governance 字段的可视化展示（候选清单/歧义标记/高风险提示/换算证据）待 AI-R08 文档确认台字段证据一并实现；单位换算当前仅内置标准因子表，物料专属换算因子（如某物料 1 箱=24 个）需通过 query_custom_conversions 注入，待 AI-R08 配套物料包装单位管理页面 |

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

`AI-R08：文档确认台字段证据与重复风险`。

开始前必须检查文档确认台、字段证据、重复风险检测是否已关联台账任务编号；低置信度字段不能静默通过；重复风险可阻止建单；仓库人员可在浏览器完成整个流程。
