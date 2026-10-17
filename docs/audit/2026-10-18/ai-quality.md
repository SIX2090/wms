# WMS 全面审计 · AI 功能 / 测试 / 质量门禁（ai-quality）

- 审计日期：2026-10-18
- 代码基线：main HEAD `0f8442b`（`app/app.py` 35,995 行；`app/` 167 个 .py（不含 Android）、`app/ai/` 74 个 .py、`app/templates/` 136 个 html、`app/static/js` 10 个 js、`tests/` 688 个 .py）
- 审计方式：**纯静态**（本会话无法执行任何外部进程：pwsh 0xC0000142 / python、git EPERM）。所有"运行时才可断言"的结论均标注 `[需运行验证]`。
- 团队任务：task-5（AI 功能、测试与质量门禁）
- 不做缺陷报告的两项（AGENTS.md §〇 已拍板）：入/出库无作废态、主链路无审核岗；库位未开启时库位不必填。本报告未将其列为缺陷。

---

## ① 审计范围与覆盖度

### 1.1 逐行精读（primary evidence）

| 文件 | 行数 | 覆盖 |
|---|---|---|
| `scripts/lint_wms_rules.py` | 2,169 | **全文**（A1–A14 实现、staged 索引、--full/--full-gate、main） |
| `scripts/lint_full_scan_baseline.json` | 46 | 全文 |
| `scripts/verify_ai_all.py` | 273 | 1–180（CORE/SMOKE/FULL 清单、并发调度） |
| `scripts/run_tests_sharded.py` | 99 | 全文 |
| `scripts/run_verify_parallel.py` | 214 | 全文 |
| `scripts/verify_stability_gate.py` | 45 | 全文 |
| `.githooks/pre-commit` | 141 | 全文 |
| `.githooks/pre-push` | 107 | 全文 |
| `.github/workflows/ci.yml` | 488 | 全文 |
| `.github/workflows/verify.yml` | 109 | 全文 |
| `app/ai/routes.py` | 452 | 全文 |
| `app/ai/v2_routes.py` | 368 | 40–290（鉴权/LLM 调试端点/熔断器/反馈） |
| `app/ai/orchestrator.py` | 47 | 全文 |
| `app/ai/policies.py` | 229 | 全文（1–200） |
| `app/ai/idempotency.py` | 208 | 全文 |
| `app/ai/tools/registry.py` | 432 | 全文 |
| `app/ai/security.py` | 557 | 结构与 249–365（注入检测/PII/令牌） |
| `app/ai/audit.py` | 242 | 178–242（确认令牌读写） |
| `app/ai/draft_idempotency.py` | 320 | 83–190（acquire/complete/fail） |
| `app/ai/documents/document_confirmation.py` | 758 | 结构 + 1–270（阈值/证据聚合） |
| `app/ai/documents/document_confirmation_status.py` | 329 | 252–329（草稿创建门禁纯逻辑） |
| `app/models/ai.py` | — | AIDocumentJob 473–510（风险标记列） |
| `app/models/documents.py` | — | InOrder 145–174、InventoryCheck 277–310 |

### 1.2 `app/app.py` 定点阅读（约 1,900 行片段）

AI 能力调度/建单：11363–11500、11503–11613、11615–11800、14742–14991、14993–15230、17010–17140、21436–21470、22400–22820、32300–32560；
OCR/确认台：14290–14450、14685–14760、22706–22816。

### 1.3 tests/ 抽样（25 个文件）

- 纯静态"源码字符串"样本：`test_bug_2026_09_13_010/011`、`test_ai_supplier_eval_hint`、`test_offline_wheelhouse`、`test_stability_gate`、`test_bug_2026_09_27_001_*`、`test_p1_2_purchase_order_validation`、`test_lint_*` 等。
- 真行为测试样本：`test_ai_assistant_mobile_001_chat_endpoint.py`（import app + client 15 处、内存库、覆盖 6 条端点契约）、`test_ci_inventory_identity_gate.py`（起子进程跑三账判据）等。
- `tests/` 全量做了一次机器分类（见 §③ P2-3），非只靠抽样。

### 1.4 明确**未覆盖**（时间/可验证性所限）

- `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`（271KB）**未通读**：只做 grep 统计（168 条"已完成"表格行）+ 条目文件引用抽样核对。
- `app/ai/ops/*`（release_handover / rollout_control / data_retention / acceptance_evidence / business_quality 等约 10 个文件 4,000+ 行）仅做 grep + 函数级抽查，**未逐行读**。
- `app/ai/documents/` 其余（material_governance* / image_preprocessing / provider_router / provider_evaluation / delivery_matcher* / golden_samples / sales_draft_validation）仅结构级。
- `app/ai/legacy.py`、`streaming.py`、`providers.py` 内部、`app/ai/handlers.py` 之下真实聊天链路未逐行审计。
- `app/android-native-wms/`（3 万行 Kotlin）未审（不属本任务主线；仅核实模板/JSON 无消费方时扫过引用）。
- 688 个测试文件中约 25 个人工读过，其余为机器分类统计。
- **无法运行**：pytest / lint / smoke / CI 日志均不可得，故"CI 是否真的全绿""规则实际扫描耗时"无法实测。

---

## ② 结论摘要

| 等级 | 数量 |
|---|---|
| P0 | **0** |
| P1 | **4** |
| P2 | **8** |
| P3 | **6** |

**一句话总评**：AI 侧的"禁止 AI 直接写业务数据"这条底线是守住的（所有 AI 写操作止步于 `pending` 草稿、AI 路由全部有 `@login_required`、工具注册表带角色+SchemA+风险级、草稿幂等与审计表齐全）；但**"人工确认/仓库必填/低置信度拦截"这三道关键边界大面积停留在"代码写了、没接线/没生效"**，同时质量门禁（A1–A14、测试、verify 脚本）存在可量化的覆盖面缺口——规则数很足，执行面对高风险模块反而最松。

### 2.1 A1–A14 是否真实现（逐条核对，本审计最有价值的定量结论）

结论：**14/14 都有真实 `scan()` 实现（非空壳、非 TODO），但覆盖面有 6 处系统性缺口**。逐条核对如下（行号均为 `scripts/lint_wms_rules.py`）：

| 规则 | 实现行 | 扫描面 / 判定口径 | 核对结论与缺口 |
|---|---|---|---|
| A1 | 509–561 | `app/templates/**`（136 html），POST form 体内须含 `csrf_token`，`nocsrf:reason`/HTML 注释豁免 | ✅真实现。仅检查"第一个 `</form>` 之前"的字符串包含，宏/嵌套表单形态未覆盖（P3 级） |
| A2 | 568–632 | `app/**`，**排除 `app/ai`**（L575）；只匹配 `@app.route(..., methods=[...POST...])`（L579–582）；30 行窗口内须有鉴权装饰器（L623–625） | ⚠️**对 app/ai 全豁免**；**不匹配 `@bp.post(...)`/`@xx_bp.route`**（全仓 17 个 `@bp.post` + 7 个 blueprint 路由零覆盖） |
| A3 | 639–686 | 仅 `app/static/js/*.js`（**10 个文件**） | ⚠️不扫 136 个模板的内联 `<script>`：实测模板内 **4 处 `console.log`** 从未被规则拦截（`app/templates/in_order_add.html:1789`、`out_order_add.html:1460`、`base.html:2322/2324`） |
| A4 | 693–753 | 同 A3 | ⚠️不扫模板：实测模板内联脚本 **199 处 `alert(`**、0 处 `debugger` 零覆盖（如 `ai_business_quality.html:213`、`ai_data_retention.html:139`） |
| A5 | 760–799 | 同 A3 | ⚠️模板内联脚本的 `eval(`/`new Function(` 零覆盖（实测当前 0 处，属"暂时无害的盲区"） |
| A6 | 806–903 | `app/**`，**排除 `app/ai`**（L814–816、L842–844）；`__main__` 块与 `# allow-print` 豁免 | ✅真实现。app/ai 实测 0 处 `print(`，豁免当前无害 |
| A7 | 910–958 | `app/**`，**排除 `app/ai`**（L917、L937–938）；仅 3 类正则：`text(f"...SELECT...{x}")`、`execute(f"...{x}")`、`text("...%s")`（L922–931） | ⚠️对 app/ai 全豁免；**不覆盖 `ALTER TABLE ...{col}`/`PRAGMA({name})`/字符串 `+` 拼接/.format()**。实测 `app/app.py` 有 18 处 f-string `cursor.execute(...)`（如 L811、L1187、L6181）全部漏检；当前插值均为内部常量，**未发现可利用注入**（故不列 P0/P1） |
| A8 | 965–1110 | `app/**`，**排除 `app/ai`**（L987、L1061）；仅 staged 新增行；路由函数体内须出现 `BaseModel`/`from pydantic`/`Field(`（L1009–1014、L1026–1055） | ⚠️对 app/ai 全豁免（AI 侧改用 JSON-Schema 校验，见 `app/ai/tools/registry.py:371–408`，口径更强，故豁免可接受但应显式化）；**只认 `@app.route`**，不认 blueprint；CI 全量模式存量 **66 处**（`lint_full_scan_baseline.json:24–27`） |
| A9 | 1117–1255 | `app/**`，**排除 `app/ai`、`app/migrations`**（L1142）；只查 staged 新增 def；匹配 `tests/` 中同名 `test_<func>` | ⚠️**对 app/ai 全豁免**；存量缺口 **217 个业务函数无对应测试**（baseline:28–31）；`_tests_dir_has_test`（L1175–1191）对每个未命中 def **全量 rglob 重读 484 个 test 文件且无缓存** → 最坏 1732 个非下划线 def × 484 ≈ 83.8 万次读，属性能悬崖 [需运行验证] |
| A10 | 1262–1335 | 仅 `app/app.py`（L1298）+ staged 新增行；禁新增 `@app.route` | ✅真实现（棘轮）。存量快照 **102 处**（baseline:32–35）；app.py 当前仍有 **94 个 `@app.route`**、35,995 行——"禁新增"成立，"app.py 已拆干净"不成立 |
| A11 | 1338–1501 | `app/**`（含 app/ai），`--full-a11` 全量；仅抓"比较语境/`is_stock_sufficient`/赋值后比较"（L1413–1449） | ✅真实现且 CI 全量跑（`ci.yml:76–77`）。⚠️**启发式盲区**：`sys_stock = normalize_stock_quantity(material.stock or 0)` 这类"赋值进单据字段"的消费点不触发 → 见 P1-2 实例 |
| A12 | 1508–1566 | `tests/**`，仅列 0（无缩进）的 `\w*(ctx|context)\w*\.(push|pop)`（L1531），三引号块跳过，`# allow-ctx-push` 豁免 | ✅真实现，口径与 R7 一致 |
| A13 | 1573–1626 | `WMS_BUG_BASELINE.md` + `docs/ledger/bugs/**` 的 **staged 新增** 行，仅识别 `^###\s+(BUG|WECOM|INV|PUR|SALES|SYS|AUDIT)-`（L1594–1595） | ⚠️**只认三级标题**：`docs/ledger/bugs/entries-2026-10.md` 有 **12/74（16%）条目用 `## BUG-…` 二级标题**，完全绕过 A13（当前这些条目都含"生效确认"，属"暂未出事"的盲区） |
| A14 | 1633–1704 | `scripts/**.py` staged 新增行含 `from app import app`/`import app`，须显式 `WMS_ALLOW_INSECURE_COOKIE`/`FLASK_ENV=testing`（L1664–1669） | ✅真实现。存量快照 **32 处**（baseline:41–45） |

**机制层面核实（正面）**：
- "新增代码生效"五条（A8/A9/A10/A13/A14）在 CI 里**不是空转**：`--full` 会把 `get_staged_added_lines` monkey-patch 为"全部行"（L402–437、L2114–2115），并以存量快照棘轮（`ci.yml:98–99`、`check_full_scan_baseline` L2018–2080）。该修复（BUG-2026-09-25-005）真实有效。
- pre-commit 确实跑 `--staged`（`.githooks/pre-commit:117`），`core.hooksPath=C:/wms/.githooks` 已配置；`--no-verify` 无滥用痕迹（全仓仅文档提及"不推荐"）。
- CI 无 `continue-on-error` 滥用：`ci.yml:156` 仅"钩子可重现性"为软检查，`perf.yml:35` 为性能观测（声明式非阻塞），lint/测试/verify/gitleaks/pip-audit 全部阻塞。

### 2.2 测试有效性定量（详见 P2-3）

| 指标 | 数值 |
|---|---|
| tests/ 顶层 `.py` | 688（test_ 484 / verify_ 191 / 其他 13） |
| CI 实际执行的测试文件 | **675**（`run_tests_sharded.py` 收 `test_*.py`；`run_verify_parallel.py` 收 `verify_*.py`） |
| **纯静态"源码字符串/正则"测试文件**（不 import app、不发 HTTP，仅读源码/模板断言字符串） | **175 / 675 = 25.9%**（test_ 92 + verify_ 83） |
| 纯静态文件的构成 | 抽样估计约一半为 Android/Kotlin 静态检查（本地无 SDK，属客观限制），另一半为 web/Python/模板断言（可用真实测试替代） |
| 引用 `ai.*` 的测试文件 | **16 / 688**（AI 模块 74 个 py、2.2 万行） |
| A9 存量缺口（无同名测试的业务函数） | **217**（baseline 自报） |

典型伪测试（可复核）：`tests/test_bug_2026_09_13_010_ai_sales_warehouse_stock.py:5-15`、`tests/test_bug_2026_09_13_011_ai_draft_warehouse_stock.py:5-10`——它们只是把 A11 的 grep 用 Python 再写一遍（`assert "material.stock" not in block`），既不能发现"调用了 get_warehouse_stock_quantities 却传错仓库"，也不能发现 P1-2 那种消费点。

---

## ③ 详细 findings

### [P1] AI 生成的 5 类出入库草稿全部不校验/不填写仓库，绕过 §二 硬规则
- 位置：`app/app.py:11391-11399`（OutOrder）、`11462-11470`（InOrder）、`11544-11578`（TransferOrder）、`11654-11671`（InventoryCheck）、`11747-11752`（AdjustmentOrder）、`15132-15164`（"其他入库"直建分支）、`app/templates/ai_document_confirm.html`（全文 0 处 warehouse 字段）
- 现象：所有 AI/确认台建单函数都不接收、不解析、不写入仓库字段；调拨单的两端仓库是正则从中文里抓的任意词，未与 `Warehouse` 表校验。模型列却声明"必填"：`app/models/documents.py:283` `warehouse = db.Column(String(100), nullable=False, default='')`，注释"盘点仓库，必填（AGENTS.md 规则）"。
- 证据：
  ```python
  # app/app.py:11462（入库）
  order = InOrder(order_no=..., date=date.today(), business_type='产品入库',
                  status='pending', operator_id=current_user.id)     # 无 warehouse
  # app/app.py:11544（调拨）
  from_loc, to_loc = _ai_extract_transfer_locations(message)         # 纯正则抽取，无 Warehouse 校验
  #  11513: r'从\s*([\u4e00-\u9fffA-Za-z0-9]{1,20})\s*仓库?\s*(?:转到|…)\s*…'
  # app/app.py:11654（盘点）
  order = InventoryCheck(check_no=..., date=..., remark=..., status='pending', operator_id=...)  # 无 warehouse
  ```
  对照：业务页路由统一走 `validate_inventory_warehouse`（`AGENTS.md` §二 明确"所有出入库新增/编辑/完成路由必须校验仓库"），AI 路径完全绕过。
- 影响：4 仓环境（AGENTS §〇）下，AI 建出的草稿归属空仓/任意文本仓：①报表与库存查询按仓筛选查不到该单；②完成时因仓库为空被拒，人工二次返工；③调拨单可指向不存在的仓库名（如"从A到B"被解析成 `from_loc='A'`），后续按仓库名匹配必然失配。属 §二 铁律违反 + R2 多仓口径风险。
- 根因：AI 建单走了"快捷建模"路径而非复用业务路由的校验层；确认台模板没有仓库选择控件。
- 建议：在 `_ai_create_*_draft` / `_ai_create_confirmed_document_draft` 入口统一做 ①`warehouse = resolve_default_warehouse()` 或 ②文本解析后 `validate_inventory_warehouse(name)`（失败即拒绝并回问），并把 `warehouse` 写进 5 类模型；确认台增加必选仓库下拉。
- 确认程度：已确认（静态读码；业务后果需运行验证）
- 关联规则：§二 / R2 / A2（app/ai 豁免）

### [P1] AI 盘点草稿用总账 `material.stock` 当账面数，多仓盘盈亏必错（A11 漏检点）
- 位置：`app/app.py:11635`、`11654-11671`、`11683`
- 现象：AI 生成的盘点单每行 `system_stock = material.stock`（**全仓合计总账**），且盘点单本身不带仓库；`actual_stock` 默认等于 system（`difference=0`）。
- 证据：
  ```python
  # app/app.py:11635（候选物料取总账）
  items = [(m, normalize_stock_quantity(m.stock or 0)) for m in candidates]
  # app/app.py:11663-11671
  for material, _ in items:
      sys_stock = normalize_stock_quantity(material.stock or 0)   # ← 总账，不是仓库级
      db.session.add(InventoryCheckItem(..., system_stock=sys_stock,
                                        actual_stock=sys_stock, difference=0))
  ```
  这正是 A11 文档注释里点名的历史根因（`scripts/lint_wms_rules.py:1356-1359`："盘点算出错误的盘盈盘亏并生成错误调整单（BUG-2026-09-02-001）"），但 A11 的校验语境启发式（L1413–1449）只认比较运算符/充分性函数/赋值后比较，**不认"赋值进单据字段"**，所以 CI 的 `--rule a11 --full-a11` 仍报 0 违规。
- 影响：4 仓环境下账面数是"各仓之和"，实盘按单仓录 → 差异被系统性放大/抵消；用户一旦按默认值一路确认，会生成错误调整单并直接改库存（账实不符）。即使人工改 actual，页面上显示的"系统库存"也是错的参考值。
- 根因：A11 规则的消费点建模不全 + AI 建单函数沿用老口径。
- 建议：改为 `get_warehouse_stock_quantities(warehouse, material_ids)`（先补 P1-1 的仓库）；A11 增加"material.stock 赋给 `system_stock`/`*_stock` 字段"模式；盘点草稿缺仓库时拒绝创建。
- 确认程度：已确认（代码可断定；差异金额影响需运行验证）
- 关联规则：A11 / R2

### [P1] AI-R08"低置信度/风险人工确认门禁"三重失效：字段从不写入、记录永不 pending、异常即放行
- 位置：`app/app.py:14909-14991`（门禁）、`14742-14907`（确认记录写入）、`32456-32499`+`32541`（证据聚合与出口）、`app/models/ai.py:504-508`（风险列）、`app/ai/documents/document_confirmation_status.py:257-329`（纯逻辑）
- 现象：门禁 `_ai_check_draft_creation_gate` 依赖 5 个 job 风险标记（`duplicate_risk/low_confidence_fields/material_ambiguity/specification_conflict/high_risk_material`）。全仓 **只有读、没有任何写入点**（grep 全量确认：仅 `app/app.py:14969-14977` 读 + 模型定义）；确认记录一律写成 `confirmed_original/corrected`，**从不产生 `pending`**；门禁任何异常 `return True, []`（fail-open）。
- 证据：
  ```python
  # app/app.py:14969-14977 —— 读的永远是默认值
  duplicate_risk = bool(getattr(job, 'duplicate_risk', False))       # 无写入点 => 恒 False
  low_confidence_fields_raw = getattr(job, 'low_confidence_fields', None) or '[]'  # 恒 '[]'
  # app/app.py:14989-14991
  except Exception as e:
      app.logger.error(f'门禁校验失败: {e}')
      return True, []          # ← 校验失败降级"允许创建"
  # app/app.py:14786-14792 / 14826-14832 / 14852-14858 —— 只会是 confirmed_original 或 corrected
  status = STATUS_CORRECTED if ... else STATUS_CONFIRMED_ORIGINAL
  # app/app.py:32486-32499 / 32541 —— 证据只进 g 和 JSON
  _g_dc.ai_document_confirmation = _dc_evidence.to_dict()
  ... 'document_confirmation': document_confirmation_info,
  ```
  且该证据在全仓 **无任何消费方**：`app/templates/**`、`app/static/**`、`app/android-native-wms/**` grep `document_confirmation`/`ai_document_confirmation` 命中 **0**；确认页 `ai_document_confirm.html:274` 只显示 `置信度 {{ row.confidence }}` 数字，无低置信度高亮/阻断。
- 影响：R5"低置信度必须回退人工、禁止 AI 结果不经确认写入业务数据"**名义已实现、实际不设防**——低置信度 OCR 结果可一键"确认原值"直接生成草稿；一旦 DB 缺表/JSON 解析失败，门禁 100% 放行。台账 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md:112`（AI-C05"高风险硬拦截和人工确认边界 已完成"）与实现不符。
- 根因：只实现了"数据结构 + 纯逻辑 + 证据聚合"，没接线到 OCR→确认→建单链路；fail-open 取舍未受约束。
- 建议：①`_ai_record_document_job` 里用 `build_confirmation_evidence()` 的结果回写 5 个风险列；②确认页渲染证据并对未确认低置信字段禁用提交；③门禁 `except` 改 fail-closed（拒绝建单并提示重试）；④回归锁：制造一个 confidence=0.1 的 job，断言不确认即不能建单（当前代码下该断言必失败）。
- 确认程度：已确认（静态可断定；"无写入点"为全仓 grep 结论）
- 关联规则：R5 / A9（AI 模块豁免）/ 台账 AI-C05、AI-R08

### [P1] 草稿幂等槽位无超时/回收：一次崩溃即永久锁死同一业务键
- 位置：`app/ai/draft_idempotency.py:117-148`（acquire）、`136-141`（processing 冲突）
- 现象：`acquire()` 先落 `status='processing'` 并 `commit()`；若进程在 `complete()/fail()` 之前崩溃/被 kill（Windows 部署常见），该行永久停留在 processing。同 `idempotency_key`（= user+capability+source+business_fields）的后续请求一律被拒，且无任何超时接管或管理端重置入口（全文件 grep `processing` 仅 L29/136/143/164 四处）。
- 证据：
  ```python
  # app/ai/draft_idempotency.py:136-141
  if existing.status == DRAFT_STATUS_PROCESSING:
      return DraftIdempotencySlot(acquired=False, record=existing,
                                  conflict_reason='该草稿请求正在处理中，请勿重复提交')
  # L164-169：先写 processing 并 commit，之后才建单
  status=DRAFT_STATUS_PROCESSING ... self.db.session.commit()
  ```
- 影响：同一张送货单/同一组物料在 AI 侧**永久**无法再生成草稿，只能手工改库；用户侧表现为"重试永远提示处理中"，无自愈路径。
- 根因：缺少 lease/过期语义；调用方（`app/app.py:11390-11430` 等）虽在 except 里 `fail()`，但覆盖不到进程级崩溃。
- 建议：processing 行加 `locked_at`，acquire 时若 `now-locked_at > N 分钟` 允许接管重试；或提供 admin 重置端点并在 UI 暴露。
- 确认程度：已确认（静态）；触发条件（进程崩溃）`[需运行验证]`
- 关联规则：R5（失败回退）/ 幂等

### [P2] A1–A14 覆盖面缺口：高风险模块（app/ai）被 5 条规则整体豁免，模板内联 JS 与 blueprint 路由零覆盖
- 位置：`scripts/lint_wms_rules.py:575`（A2 排 app/ai）、`814-816`+`842-844`（A6）、`917`+`937-938`（A7）、`987`+`1061`（A8）、`1142`+`1198`（A9）、`645/699/766`（A3/A4/A5 仅 `app/static/js`）、`579-582`+`991-994`（只认 `@app.route`）、`1594-1595`（A13 只认 `###`）
- 现象：见 §2.1 表。可量化事实：①app/ai 74 个 py / 2.2 万行对 A2/A6/A7/A8/A9 全部免疫；②A3–A5 只扫 10 个 js，136 个模板的内联脚本不在扫描面（实测模板内 199 处 `alert(`、4 处 `console.log`）；③17 个 `@bp.post/@bp.put` + 7 个 `@xx_bp.route` 不被 A2/A8 识别（当前这些路由都有鉴权装饰器，属覆盖盲区而非漏洞）；④A13 对 `## BUG-` 二级标题条目无感（12/74）。
- 证据（A2 排除语句与只认 app.route）：
  ```python
  # scripts/lint_wms_rules.py:574-576
  scan_paths = ("app",)
  exclude_paths = ("app/ai",)  # AI 模块不需要此规则
  # L579-581：只匹配 @app.route(...)
  _ROUTE_POST = re.compile(r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*,\s*methods\s*=\s*\[[^\]]*['\"]POST['\"]")
  ```
- 影响：规则全绿 ≠ 高风险面被检查。app/ai 是"新代码增长最快 + 调 LLM + 会被注入"的模块，恰恰被豁免最多；模板内联 JS 是历史 bug 高发区（CSRF/alert 调试残留）却不在 A3/A4。
- 根因：规则按"路径黑名单"豁免而非按"能力/风险"豁免；A2/A8 的正则只覆盖 register-on-app 单一写法。
- 建议：①A2/A8 支持 `Blueprint`/`@bp.post` 形态；②A3/A4/A5 增加模板内联 `<script>` 扫描（与 `lint_no_raw_post_fetch` 的 warn 模式同机制）；③A13 标题正则放宽到 `^#{2,4}\s+`；④app/ai 的豁免改为"逐规则白名单 + 理由"，A7/A2 至少覆盖 app/ai。
- 确认程度：已确认（读码 + 全仓计数）
- 关联规则：A2/A3/A4/A5/A6/A7/A8/A9/A13

### [P2] 全量棘轮基线偏高，"新增代码生效"实际上允许 417 处存量违规
- 位置：`scripts/lint_full_scan_baseline.json:23-45`；`ci.yml:90-99`
- 现象：CI 的 `--full --full-gate` 不是硬门禁而是棘轮：允许上限 `a8=66 / a9=217 / a10=102 / a14=32`（合计 417），a13 才是 0 硬门禁。同时 app.py 仍有 94 个 `@app.route`、35,995 行——A10 的"禁新增"成立，但"app.py 已拆分"只对新增生效。
- 证据：`"a9": {"count": 217, ...}`、`"a10": {"count": 102, ...}`、`"a14": {"count": 32, ...}`；季度棘轮 -10%/季（L1911、baseline:17-22），全部清零需 ~2.5 年（217→0）。
- 影响：这些数字会被误读为"门禁在拦"，实际只拦"比昨天更多"。例如 A9 有 217 个业务函数无测试仍全绿。
- 建议：把基线数字写进 CI step summary / README 可见处；每季度必须真的收紧（否则 -10% 是纸面承诺）；优先清理 A9（217）与 A10（102）。
- 确认程度：已确认
- 关联规则：A8/A9/A10/A14

### [P2] 测试真实有效性：25.9% 的"测试"只是源码字符串断言，核心库存路径缺行为级回归
- 位置：全 `tests/`（机器分类）；代表文件 `tests/test_bug_2026_09_13_010_ai_sales_warehouse_stock.py:5-15`、`test_bug_2026_09_13_011_ai_draft_warehouse_stock.py:5-10`、`test_stability_gate.py:6-30`、`test_p1_2_purchase_order_validation.py:16-47`
- 现象：675 个 CI 执行文件中 175 个（25.9%）**不 import app、不发 HTTP**，只 `read_text()` 后 `assert "xxx" in source`；引用 `ai.*` 的测试仅 16 个。极端例：`test_bug_2026_09_13_011` 全文 10 行，断言 `"get_warehouse_stock_quantities" in block` + `"material.stock" not in block`——正是 A11 lint 的 Python 复写，无法发现"传错仓库/消费点漏检"（见 P1-2）。
- 证据：
  ```python
  # tests/test_bug_2026_09_13_011_ai_draft_warehouse_stock.py 全文核心
  source = (Path(__file__).parents[1] / "app" / "app.py").read_text(encoding="utf-8")
  block = source.split("def _ai_check_draft(module_key, order):", 1)[1].split("def _ai_draft_check_response", 1)[0]
  assert "validate_inventory_warehouse" in block
  assert "get_warehouse_stock_quantities" in block
  assert "material.stock" not in block
  ```
  正面样本（说明团队已知问题并在改进）：`tests/test_bug_2026_09_27_001_in_order_warehouse_submit_field.py:31-44` 明确用 node **真实执行**从模板抽取的 JS 片段；该文 docstring 自述"原有 21 项全绿却没拦住"。
- 影响：这类测试对回归几乎无锁力（改个变量名/注释就红，逻辑错却绿），会制造"覆盖率幻觉"；库存/建单路径真正需要的行为断言（多仓、并发、越权）覆盖不足。
- 根因：Android/Kotlin 无法本地编译的客观限制被"顺手用于 web/Python"；A9 只看测试函数"名字存在"。
- 建议：①把"纯静态断言"测试单独打标签（如 `@pytest.mark.static_check`）并在 CI 汇总中单列，避免计入覆盖率；②对库存/草稿路径补 true-behavior 用例（client 方式）优先覆盖 P1-1/P1-2；③A9 增强为"必须 import 被测模块并调用"。
- 确认程度：已确认（机器分类 + 25 个样本人工复核）
- 关联规则：A9 / R8

### [P2] 9 个 AI 专项校验脚本 + "稳定版发布门禁"在 CI 中从不执行
- 位置：`scripts/verify_ai_all.py:17-85`（CORE 58 个 vs `_all_ai_scripts()` glob 66 个）；`verify.yml:108`（只跑 `--level core`）；`scripts/verify_stability_gate.py:12-28`（门禁清单，无 CI 调用）
- 现象：`scripts/verify_ai_*.py` 共 66 个，CI 只跑 `--level core` 的 58 个；`--level full` 无任何 workflow 调用，故 **9 个脚本永不执行**，其中包含 `verify_ai_cross_user_isolation.py`（跨用户越权校验）与 `verify_ai_photo_document_flow.py`（拍照单据链路）；承载这些脚本的 `verify_stability_gate.py` 本身也不在 CI。
- 证据：
  ```python
  # scripts/verify_ai_all.py:107-114
  if level == "core":  return CORE_SCRIPTS
  if level == "full":  return _all_ai_scripts()   # 无 workflow 调用 full
  ```
  ```
  # .github/workflows/verify.yml:108
  run: python3 scripts/verify_ai_all.py --level core
  ```
  未被 CI 覆盖的 9 个：`verify_ai_cross_user_isolation / verify_ai_intent_corpus / verify_ai_photo_document_flow / verify_ai_sales_followup_workbench / verify_ai_stage1_platform / verify_ai_stage2_documents / verify_ai_stage3_agents / verify_ai_stage4_analysis / verify_ai_stage5_production`
- 影响：跨用户隔离与拍照确认台这两条最贴近本报告 P1 结论的校验，恰好没有被 CI 守住；"WMS AI Verification 全绿"不能证明这些能力正常。
- 根因：verify_ai_all 增加了 core/full 分级，但 workflow 未跟进跑 full；stability gate 是"文档级门禁"，只有静态测试断言它"列了这些命令"。
- 建议：①verify.yml 增加 `--level full`（或把 9 个脚本并入 core 并计时）；②给 `verify_stability_gate.py` 一个 CI job，或删除该脚本并把其清单折进 verify_ai_all；③`tests/test_stability_gate.py` 改为真的跑门禁（当前只是字符串断言，见 P2-3）。
- 确认程度：已确认
- 关联规则：R8 / §三 CI 全绿门禁

### [P2] "低置信度"阈值三处漂移 + 缺省 confidence=0，导致验收指标恒告警
- 位置：`app/ai/documents/document_confirmation.py:40`（0.80）、`app/app.py:17060-17065` 与 `17119-17120`（硬编码 0.85，注释称"与 document_confirmation 阈值一致"）、`app/ai/ops/acceptance_evidence.py:56`（0.85）
- 现象：同一概念 3 个值：0.80 / 0.85 / 0.85；且 `_ai_ocr_confidence` 缺省返回 **0**（`app/app.py:14033-14037`），本地规则链路（未配 LLM）不产出 confidence → 所有行都是 0 < 任何阈值。
- 证据：
  ```python
  LOW_CONFIDENCE_THRESHOLD = 0.80        # document_confirmation.py:40
  # app/app.py:17060-17065
  # AIDocumentItem.confidence < 0.85 表示低置信度（与 document_confirmation 阈值一致）
  AIDocumentItem.confidence < 0.85,
  # app/app.py:14033
  def _ai_ocr_confidence(value):
      confidence = _ai_ocr_number(value, 0)      # 缺省 0
  ```
- 影响：①0.80~0.85 区间的行在两处判定相反，AI-R17"低置信度未确认建单"指标与实际门禁不同源；②未配 LLM 时每条 OCR 行 confidence=0，指标把**所有** draft_created 任务计为风险，形成告警噪音，真风险被淹没。
- 建议：单一常量（放 `ai/documents/constants.py` 或 `document_confirmation`）并被 app.py/acceptance_evidence 引用；缺省 confidence 用 `None` 表示"未提供"而不是 0，指标侧区分"未知"与"低置信"。
- 确认程度：已确认
- 关联规则：R5 / AI-R08 / AI-R17

### [P2] `app/ai/security.py` 的注入防护与 PII 脱敏在生产链路中零调用
- 位置：`app/ai/security.py:267-327`（`check_prompt_safety / sanitize_prompt / detect_prompt_injection / safe_document_context`）、`129-247`（`desensitize_text / detect_pii_in_text / mask_*`）
- 现象：对 `app/**/*.py`（排除 security.py 自身）全量 grep：`detect_prompt_injection` 0 次、`check_prompt_safety` 0 次、`sanitize_prompt` 0 次、`safe_document_context` 0 次、`detect_pii_in_text` 0 次、`sanitize_markdown` 0 次、`get_token_store` 0 次；仅 `mask_phone/email/id_card/desensitize_text` 被 `app/ai/ops/data_retention.py`（离线留存工具）使用。
- 证据（grep 结果摘录）：
  ```
  detect_prompt_injection: 0 refs     check_prompt_safety: 0 refs
  sanitize_prompt: 0 refs             safe_document_context: 0 refs
  detect_pii_in_text: 0 refs          sanitize_markdown: 0 refs
  ```
- 影响：LLM 对话与 OCR 文本从未经过注入检测/数据区隔离包装；`_INJECTION_PATTERNS`（L297–302）只是死代码。当前"防注入"实际靠"模型没有工具执行权 + 工具分发由服务端按角色决定"（`app/ai/orchestrator.py:12-46`）——这是真实且有效的第二道防线，但不是台账宣称的那道。
- 根因：安全能力先建库未接线；缺少"能力→调用点"的校验（对比 `verify_ai_tool_compliance.py` 覆盖工具表，但没有覆盖 security 函数）。
- 建议：在 `handle_chat_stream`/`handle_warehouse_assistant` 的入口与 OCR prompt 组装处调用 `detect_prompt_injection` + `safe_document_context`；补一条 verify 脚本断言"每个 security 公开函数至少 1 个生产调用点"。
- 确认程度：已确认（grep 全仓无调用）
- 关联规则：A9（AI 豁免）/ R5

### [P2] AI 对话链路无速率/配额控制，成本控制只在 Agent 预算模块内生效
- 位置：`app/ai/routes.py:125-132`（`/chat/stream` 仅 `@login_required + @require_ai_role + @ai_idempotent_request`）、`app/ai/policies.py:15-27`、`app/ai/agents/budget_control.py` 仅被 Agent 端点使用（`app/app.py:32884-33190`）
- 现象：全仓限流只存在于登录（`app/routes/user_auth.py:128`）与手机识别（`app/routes/mobile.py:110-126`，5 次）；`/api/ai/chat/stream`、`/api/ai/warehouse_assistant` 无每分钟/每日调用上限，也无 token/费用预算。`check_budget` 只出现在 `/api/ai/agent_budget_check` 等 Agent 端点。
- 影响：任何被授权的角色（admin/warehouse/purchase/production/sales）可无限刷 LLM 计费；单用户环境风险低，但一次误触循环（前端重试）即可烧配额；且这是 AI-LLM-GATE-002 类"防刷计费"问题的同类漏网点。
- 建议：给 chat/warehouse_assistant 加与 mobile 同款的进程内滑动窗口限流（如 20 次/分/用户）+ 每日预算计数（复用 budget_control 的 `BudgetConfig`）。
- 确认程度：已确认（静态）
- 关联规则：R6（同根因排查全消费点）

### [P2] 台账"已完成"与代码能力不一致（抽样 2 条已确认虚高）
- 位置：`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md:112`（AI-C05"高风险硬拦截和人工确认边界｜已完成"）、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md:131`（AI-R01 已完成 全部 AI 草稿统一幂等与审计闭环）
- 现象：168 条"已完成"表格行中，AI-C05 声称的"人工确认边界"对应实现即 P1-3（门禁三重失效，实际不设防）；AI-R08 相关的"低置信度拦截"同样未接线。台账核对方法为文件存在性 + 字符串命中，无法发现"函数存在但无调用方"。
- 证据（对照）：台账行 `| AI-C05 | 高风险硬拦截和人工确认边界 | b9aca0e、高风险专项验证 | 已完成 |`；代码侧 `app/ai/documents/document_confirmation.py` 与 `document_confirmation_status.py` 均存在且被 `verify_ai_high_risk_boundaries.py`（在 core 清单内）校验——但该校验只查工具表/风险级别，不查"证据是否被页面消费""风险字段是否被写入"。
- 影响：台账是用户/AI 判断"是否重复开发"的唯一索引，虚高会直接导致后续任务误判"已具备"而不修复。
- 建议：把本报告 P1-3/P1-2 作为 AI-C05/AI-R08 的子修复 ID 登记；给"已完成"增加一条硬判据：能力必须有 ≥1 个生产调用点（可用 grep 断言脚本机械化）。
- 确认程度：已确认（这 2 条）；其余 167 条未逐条核（见覆盖度）
- 关联规则：§五台账 / R3

### [P3] A2/A8 不识别 Blueprint 路由（当前均为已鉴权，属覆盖盲区）
- 位置：`scripts/lint_wms_rules.py:579-582`、`991-994`；受影响路由 `app/routes/ai_excel.py:104`、`app/routes/unit.py:47/73/123`、`app/ai/routes.py`（12 个 `@ai_bp.post/put`）、`app/ai/v2_routes.py`（5 个 `@v2_bp.post`）
- 现象：17 个 `@bp.post/@bp.put` + 7 个 `@xx_bp.route` 不被 A2（鉴权装饰器）/A8（pydantic）正则识别。逐个核对：`ai_excel.py:104-105` 有 `@_web_or_api_role_required`，`unit.py` 有 `@require_role+@login_required`，`app/ai/*` 全部 `@login_required`——**当前无未鉴权路由**。
- 影响：规则对新写法静默失效，未来新增 blueprint 写路由可绕过 A2/A8。
- 建议：A2/A8 正则扩展为 `@\w*(?:app|bp|blueprint)\w*\.(?:route|post|put|patch|delete)\(`；或改"白名单装饰器必须出现"的正向扫描。
- 确认程度：已确认
- 关联规则：A2/A8

### [P3] 确认令牌创建接受客户端 `expires_minutes`/未校验 `ai_run_id` 归属
- 位置：`app/ai/routes.py:363-398`（`expires_minutes=payload.get('expires_minutes', 30)`；`ai_run_id=payload.get('ai_run_id')` 无归属校验）、`app/ai/audit.py:178-205`（无 clamp，`datetime.now()+timedelta(minutes=expires_minutes)`）
- 现象：`expires_minutes` 未做类型/范围校验：传 `-1` → 令牌创建即过期；传非数字 → `TypeError` → 500；传 `10**7` → 有效约 19 年。另 `ai_run_id` 未像 message/feedback 那样调用 `_validate_ai_run_owner`（`routes.py:266/308`），可引用他人运行记录。
- 影响：单人环境下影响有限；多用户/被恶意调用时会话确认令牌有效期失控、跨用户引用污染审计。属 R5 确认边界的边缘缺陷。
- 建议：`expires_minutes` 用 `int()` + clamp(1..120)；`ai_run_id` 走 `_validate_ai_run_owner`。
- 确认程度：已确认
- 关联规则：R5 / A8（app/ai 豁免）

### [P3] AI v2 只读工具端点仅 `@login_required`，未按角色收窄（风险提示）
- 位置：`app/ai/v2_routes.py:116-213`（`/tools/inventory/{material,transactions,health,low-stock,value}`、`/tools/purchase/*`、`/tools/navigation/*`）
- 现象：这些端点只校验登录，不校验 `require_ai_role`/`require_role`；返回库存金额、采购洞察等数据。对照 `policies.py:30-74` 的同名能力均有角色白名单，页面侧（`warehouse_insights` 等）亦限定角色。
- 影响：任何可登录账号（含 viewer/user）可绕过页面角色限制直接读库存价值/采购数据。当前单人使用，列为风险提示。
- 建议：这些端点改为 `@require_ai_role` + 按能力补 `require_role`（与 `AI_CAPABILITY_ROLES` 对齐）。
- 确认程度：已确认（静态）；实际越权后果 `[需运行验证]`
- 关联规则：§一 / R5

### [P3] 死调用：`_ai_dispatch_registered_tool('stock_query', ...)`
- 位置：`app/app.py:23562`
- 现象：`AI_TOOL_REGISTRY`（`app/ai/tools/registry.py:371-408`）无 `stock_query`，`dispatch_registered_tool` 对未知工具直接返回 `None`（`orchestrator.py:20-23`），该分支永远走不通。
- 影响：无功能影响，但会误导后续维护者以为存在该工具；属 AI 工具表与调用点漂移。
- 建议：删除该分支或把工具名改为 `warehouse_insights`。
- 确认程度：已确认
- 关联规则：A9/台账一致性

### [P3] CI/验证脚本注释中的规模数字已过时
- 位置：`.github/workflows/ci.yml:170,183,289,294`（"362 个 test_*.py""178 个 verify"）、`verify.yml:25`（"58 个脚本"）
- 现象：实测 `tests/test_*.py` 484 个、`tests/verify_*.py` 191 个；注释仍写 362/178/173。ci.yml:294 的"178 = 45+45+44+44"离线验算已不成立（现应为 191 按 4 片）。
- 影响：分片数与文件数的对应关系变化后，注释的"不重不漏"论证失真（代码逻辑本身按取模分片仍不重不漏，仅注释误导）。
- 建议：注释改为"按排序取模分片，不重不漏（数量随测试增长）"，去掉硬编码数字或用脚本生成。
- 确认程度：已确认
- 关联规则：§五文档漂移

### [P3] 模板内联 JS 遗留调试输出 4 处（A3 因不扫模板而未拦截）
- 位置：`app/templates/in_order_add.html:1789`、`app/templates/out_order_add.html:1460`、`app/templates/base.html:2322`、`app/templates/base.html:2324`
- 现象：`console.log(message)`、`console.log('[CSRF] token 已刷新')` 等调试输出在生产模板内联脚本中；A3 只扫 `app/static/js`（10 个文件）故未报。
- 影响：轻微（日志噪音/CSRF token 刷新痕迹外泄到控制台），不涉数据。
- 建议：与 P2-1 的"模板内联 JS 纳入 A3/A4"一并修；`base.html` 的两条属统一层（类似 `api.js` 白名单），可用行内 `// allow-console` 标记豁免。
- 确认程度：已确认
- 关联规则：A3

---

## ④ 建议优先级路线图（≤10 条）

1. **（P1-3）接线 AI-R08 人工确认门禁**：`_ai_record_document_job` 回写 5 个风险列 → 门禁 fail-closed → 确认页渲染证据并阻断未确认低置信字段。这是本报告最高优先项（R5 底线）。
2. **（P1-1+P1-2）AI 建单统一补仓库层**：5 类草稿入口 `resolve/validate_inventory_warehouse`，盘点改 `get_warehouse_stock_quantities()`，确认台加仓库必选控件；同时修 A11 启发式。
3. **（P1-4）幂等槽位加 lease 超时/接管**，提供 admin 重置入口。
4. **（P2-1）门禁补覆盖**：模板内联 JS 纳入 A3/A4/A5；A2/A8 支持 Blueprint；A13 标题正则放宽；app/ai 豁免改为逐规则白名单。
5. **（P2-4）CI 补跑 9 个 AI 校验脚本**：verify.yml 增加 `verify_ai_all.py --level full` 或把 `verify_ai_cross_user_isolation`/`verify_ai_photo_document_flow` 并入 core；给 `verify_stability_gate.py` 一个真实 job。
6. **（P2-3）测试分级与补行为锁**：纯静态测试打标单列；为库存/草稿/AI 确认链路补 client 级真测试（至少覆盖 P1-1、P1-2、P1-3 三处）。
7. **（P2-5）收敛置信度常量**：单一来源 + 缺省 `None` 语义，修 AI-R17 指标口径。
8. **（P2-6）把 `ai/security.py` 接到聊天/OCR 链路**，并加"安全函数必须有生产调用点"的机械化断言。
9. **（P2-7）chat 端点加限流+日预算**（复用 mobile 限流与 budget_control）。
10. **（P2-2/P2-8/P3）治理性收尾**：清理 A9(217)/A10(102) 基线并把数字可见化；台账为 AI-C05/AI-R08 补子修复 ID；删除死调用、修注释计数、清模板 console.log。

---

## 附录：关键正向结论（避免只报坏消息）

1. **AI 不直接写业务数据**：全 `app/ai/**` grep 无 `.status='completed'`/revert/complete 调用（唯一命中的是幂等表自身）；AI 建单函数全部产出 `status='pending'` 草稿（`app/app.py:11397/11468/11576/11658` 等）。R5"提交/完成由人工"成立。
2. **AI 路由鉴权完整**：`app/ai/routes.py` 17 个端点全部 `@login_required`，写 LLM 的 3 个再加 `@require_ai_role`（`policies.py:18-27`）；`v2_routes.py` 熔断器/预算类端点有内联 admin 校验。
3. **工具注册表设计良好**：Schema（`additionalProperties: False` + 数值上下限）、角色白名单、风险级、`confirmation_required` 三者统一在 `AI_TOOL_REGISTRY`，且 `confirmation_required` 在 `orchestrator.py:24` 被真正强制执行（非死字段）；配套 4 个 verify 脚本在 CI core 内。
4. **模型不持有工具执行权**：LLM 不做 function-calling 自主执行，工具由服务端按意图白名单分发（`app/app.py:21436-23570`），从结构上掐断"模型越权调工具"。
5. **草稿幂等 + 审计表齐全**：`AIDraftIdempotency`（唯一键 + IntegrityError 竞态兜底，`draft_idempotency.py:150-190`）、`AIRun/AIToolCall/AIDocumentAttempt` 审计链完整；`/api/ai/chat*" 强制 `request_id`（`idempotency.py:78-100`）。
6. **CI 无"假门禁"**：无 `continue-on-error` 滥用，gitleaks/pip-audit 已收紧为阻塞；`--full` 机制修复了"五条规则在 CI 空转"的历史缺陷（BUG-2026-09-25-005 真实闭环）。
7. **pre-commit 实际生效**：`core.hooksPath` 已指向 `.githooks`，14 条规则 + 裸 fetch 双门禁，纯文档提交不被误伤（`pre-commit:38-42`）。
8. **团队已识破"假绿"**：`tests/test_bug_2026_09_27_001_*.py:31-44` 用 node 真实执行抽出的 JS 片段并做了回退验证，方向正确，值得推广到 §③ 列出的静态测试上。
