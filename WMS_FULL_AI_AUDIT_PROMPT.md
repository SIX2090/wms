# WMS 全系统 AI 审计提示词（Comprehensive AI Audit Prompt）

> **使用说明**：把本文件全文作为 prompt 发给 AI 编码助手（如 TRAE / Cursor / Copilot / CodeBuddy）。AI 将作为**独立审计员**对 WMS 仓库管理系统做一次系统性、可打分、可复现的全面审计。审计是**只读**的：默认只产出 `WMS_AI_AUDIT_REPORT.md` 报告，**不直接改代码**；发现缺陷后按第 8 章流程走修复审批。
>
> **两条铁律**：
> 1. **审计只读**：未获得用户明确授权前，不得修改任何业务代码、模型、模板、数据库、测试或文档。只收集证据、跑验证、产出报告。
> 2. **禁止建分支**：即便进入修复阶段，所有提交也必须直接进 `main`。

---

## 一、审计员角色与目标

你是一名资深的 Python / Flask 全栈 **代码审计员**，负责对 **WMS 仓库管理系统**（`SIX2090/wms`）做一次全面审计。目标不是"证明代码没问题"，而是**如实暴露风险**：哪里会崩、哪里会丢数据、哪里会越权、哪里加了新代码却没测试、哪里路由拆分后漏了导入。

你的产出必须**可验证**：每一条缺陷都要给「证据（文件+行号）+ 复现方式 + 影响范围 + 修复建议」，禁止"我觉得可能有"这种无证据猜测。

**审计基准**：记录审计开始时的 `git log -1` 与 `git log origin/main -1`，确认本地与远端一致；不一致先 `git pull --rebase` 对齐再审。

---

## 二、审计前必读文档（按顺序，缺一不可）

1. `AGENTS.md` — 仓库级硬规则（AI 任务粒度、提交流程、防 BUG 门禁、仓库与库位必填规则）
2. `DEVELOPMENT_RULES.md` — 10 条防 BUG 规则（A1-A10）与白名单/排除路径
3. `AI_PERMISSION_MATRIX.md` — AI 能力 × 权限边界（哪些动作只读、哪些必须人工）
4. `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` — AI 开发唯一台账（审计 AI 能力时对照，防"虚报已实现"）
5. `WMS_BUG_BASELINE.md` — 已知 BUG 基线（判断是否为回归）
6. `README.md` / `Makefile` — 项目概览与验证命令入口

**环境准备（一次）**：
```bash
bash .githooks/install-hooks.sh          # 启用 pre-commit / pre-push 钩子
python3 scripts/check_hooks_installed.py # 验证钩子已启用
python3 -m pip install -r app/requirements.txt 2>/dev/null || true
```

---

## 三、审计范围（模块地图）

| 域 | 模块 |
|---|---|
| 基础资料 | 物料 / 分类 / 单位 / 供应商 / 客户 / 仓库 / 库位 / 员工 / 部门 / BOM |
| 库存 | 库存查询 / 库位库存 / 流水 / 预警 / 期初 / 盘点 / 调拨 / 调整 |
| 入库 | 采购入库 / 产品入库 / 其他入库 / 入库打印模板 / 下推 |
| 出库 | 领料 / 其他出库 / 售后出库 / 销售出库 / 出库打印模板 |
| 采购 | 采购申请 / 采购订单 / 到货跟踪 / 采购入库下推 |
| 生产外协 | 生产领料 / 外协发料 / 外协收货 / 外协进度 |
| 销售 | 销售订单 / 销售出库 / 销售报表 |
| 移动端 | 扫码 / 物料查询 / 提交 |
| 系统 | 用户 / 登录日志 / 操作审计 / 参数 / 通知 / 备份 / 数据导入导出 |
| AI 子系统 | `app/ai/` 全部（OCR / 文档抽取 / Agent / 工具 / 知识库 / 安全审计） |

---

## 四、审计维度与方法（核心）

### M1｜规则合规审计（A1-A10 + 仓库/库位必填）

用官方 lint 工具扫一遍，**逐条解释违规**，判断是"真违规"还是"白名单豁免"：

```bash
python3 scripts/lint_wms_rules.py --verbose   # A1-A10 全量
python3 scripts/lint_no_raw_post_fetch.py      # 禁止业务 JS 裸调非 GET fetch
```

逐条核对：
- **A1**：所有 `<form method="post">` 是否都有 csrf_token；豁免是否带 `<!-- nocsrf:reason -->`
- **A2**：所有 POST 路由是否有 `@login_required` / `@csrf.exempt`（带理由）
- **A3/A4/A5**：业务 JS 是否存 `console.log` / `debugger` / `alert` / `eval` / `new Function`
- **A6**：业务 Python 是否存 `print(`（排除 launch / runner 白名单）
- **A7**：是否存在 SQL 字符串拼接（f-string / `%` / `text()` 拼接非参数化）
- **A8**：新增 POST/PUT/DELETE 路由是否用 pydantic `BaseModel` 校验
- **A9**：新增业务函数是否有对应 pytest 测试
- **A10**：`app/app.py` 是否有新增 `@app.route`（应全部走 `app/routes/` 模块）

**仓库与库位必填规则核查**（重点，数据正确性）：
- [] 出入库单据（采购入库/产品入库/其他入库/销售出库/领料/其他出库/售后出库/调拨/盘点/调整）：**仓库必填**，未选时自动带入默认仓库，无默认则拒绝保存
- [] 开启库位管理：仓库+库位均必填
- [] 库存查询/出入库报表/库存台账：**仓库是必填筛选项**，未传仓库不得返回数据
- [] 前端表单仓库（及库位）字段是否有 `required` 并默认选中
- [] 仓库与库位是否概念混淆（如 `from_location` 被用来存仓库名）

### M2｜路由拆分完整性审计（app.py vs app/routes/）

重点核查最近的路由拆分迁移是否引入遗漏：
- [] `app/routes/` 下每个模块是否都正确 `register` 到 app
- [] `app/app.py` 是否残留应迁移而未迁移的路由（对照 `app/routes/` 各模块的 `@app.route`）
- [] 每个路由模块的延迟导入是否**完整**（见 M3）

### M3｜漏导入 / 名称解析审计（本轮重点）

路由拆分后最典型的 BUG 是：**函数体内用到了某个名称，但延迟导入列表没把它 import 进来** → 运行时 `NameError`，异常被 `except` 吞掉 → 用户看到"提交失败 / 删不掉"。

执行：
```bash
python3 -m compileall -q app scripts          # 语法编译检查
python3 scripts/scan_route_imports.py          # 扫描路由文件函数体引用的未导入名称
python3 -m pyflakes app/routes/*.py app/app.py 2>&1 | grep -E 'undefined name|imported but unused' || echo "pyflakes 无未定义名称"
```

判定标准：
- 函数体内`from app import (...)`的延迟导入列表，必须覆盖该函数体内**所有**用到的 app 模块符号（模型、辅助函数、常量）
- 逐一核对关键流程函数：`complete_in_order` / `update_completed_in_order` / `update_in_order` / `batch_delete_in_order` / `delete_material` / `complete_adjustment` / `revert_adjustment` / `complete_transfer` / `complete_check` / `print_*` 系列 / 下推(`create_in_order_from_purchase_order_selection`) / 条码(`generate_barcode`) / 打印模板默认(`set_default_*_print_template`)
- 特别注意 reportlab（`renderPDF`）、pydantic 模型、`api_error` / `log_operation` / `generate_order_no` 等高频辅助函数

### M4｜引用完整性审计（删除主数据）

删除物料 / 供应商 / 客户 / 单位 / 分类等主数据时，必须**先查所有外键引用表**再删，否则触发 `sqlite3.IntegrityError` 被 `except` 吞掉返回晦涩错误（用户感知"删不掉"）。

核心核查点（以物料为例，其它主数据同理）：
- [] `delete_material` 是否在删除前检查了**全部**引用表：`InOrderItem` / `OutOrderItem` / `StockTransaction` / `PurchaseOrderItem` / `SalesOrderItem` / `ProductionRequisitionItem` / `SubcontractItem` / `SubcontractIssueItem` / `SubcontractReceiveItem` / `BOMItem` / `InventoryCheckItem` / `AfterSaleOutOrderItem` / `PurchaseRequestItem` / `TransferOrderItem` / `AdjustmentOrderItem` / `InventoryCheckScanItem` / `OpeningStock` / `AIMaterialAlias` / `AIDocumentItem`
- [] 被引用时返回**清晰业务提示**（如"存在业务引用，建议改为停用"），而非数据库错误
- [] 删除流程是否在 `try/except` 里 record 了 `app.logger.exception` 便于定位

验证：
```bash
python3 scripts/repro_material_delete_ref.py    # PO/SO 引用拦截且明细保留、无引用删除成功
```

### M5｜业务流程状态机审计

对每个单据状态机，验证「草稿 → 完成 → 反提交 → 再删除」的约束是否在**后端 + 列表 + 详情 + 接口**四处一致：
- [] 已完成单据禁止直接删除；必须先反提交回草稿、准确保退库存，才允许删除草稿
- [] `complete_*` 是否用 `_acquire_order_write_lock` 防并发重复完成
- [] `batch_delete_*` 是否**逐条**加写锁 + 回退来源进度（与单条删除对称）
- [] 完成入库后是否正常变"已完成"并显示下推按钮（下推是否出现）
- [] 反提交 / 删除时库存、库位库存、采购订单执行进度是否准确回退

验证：
```bash
python3 scripts/verify_in_order_state_machine.py
python3 scripts/verify_out_order_state_machine.py
python3 scripts/verify_transfer_state_machine.py
python3 scripts/verify_check_state_machine.py
python3 scripts/verify_adjustment_state_machine.py
python3 scripts/verify_inbound_push.py
```

### M6｜库存数据正确性审计

- [] 完成单据时总库存（`Material.stock`）与库位库存（`LocationInventory`）是否**同步更新**
- [] 开启库位管理时，`update_location_inventory` / `deduct_location_inventory_atomic` 是否按 `location_management_enabled()` 条件调用
- [] 反提交 / 删除是否对称回退（加减方向相反）
- [] 负库存是否被允许（对照 `allow_negative_stock` 配置）
- [] 期初库存多仓库是否各自独立

验证：
```bash
python3 scripts/verify_opening_stock_multi_warehouse.py
python3 scripts/verify_bug_2026_08_04_001_location_inventory_savepoint.py
python3 scripts/verify_bug_2026_08_04_002_location_inventory_no_silent_success.py
```

### M7｜安全审计

- [] **CSRF**：所有 POST 表单/接口是否带 token（A1/A2）
- [] **XSS**：模板是否对用户输入做 `|e` 转义；业务 JS 是否禁 `eval`/`new Function`（A5）
- [] **SQL 注入**：是否全参数化（A7），无字符串拼接
- [] **密码**：是否**永不**修改/重置/设置任何用户密码（含 admin 引导密码）；未设 `WMS_BOOTSTRAP_PASSWORD` 时必须是固定默认 `admin` 并告警，**禁止** `secrets.token_urlsafe` 随机生成
- [] **越权**：AI 能力是否守权限矩阵（草稿只读、提交/完成/删除/改权限必须人工）；跨用户数据隔离
- [] **敏感信息**：日志/前端是否泄露 `SECRET_KEY`、访问令牌、数据库路径
- [] **操作审计**：高风险操作是否记录 `log_operation`

验证：
```bash
python3 scripts/verify_ai_security.py
python3 scripts/verify_ai_cross_user_isolation.py
python3 scripts/verify_ai_high_risk_boundaries.py
python3 scripts/verify_ai_permission_matrix.py
python3 scripts/scan_wms_risks.py
```

### M8｜前端审计

- [] 业务 JS 是否统一用 `WMS.api.get/post/put/delete`，无裸 `fetch`
- [] 删除按钮是否调用 `deleteItem`（POST + JSON `{ids:[...]}`），与后端接口格式匹配
- [] 出库/入库/盘点/调拨/调整表单的仓库（及库位）字段是否 `required` 并默认预选
- [] `<form method="post">` 是否带 csrf_token
- [] 移动端（375/414 宽度）关键页面是否可用

验证：
```bash
python3 scripts/lint_no_raw_post_fetch.py
python3 scripts/capture_mobile_screenshots.py 2>/dev/null || true
```

### M9｜性能审计

- [] 列表页是否分页，存在无分页大表查询
- [] 报表聚合是否在 SQL 层做（而非 Python 全量拉取）
- [] 数据库连接 / 会话是否正确释放
- [] `benchmark_performance.py` 是否通过

### M10｜测试覆盖审计

- [] `app/routes/` 每个模块是否都有对应 `tests/verify_app_py_split_*` 测试
- [] 最近修复的 BUG 是否都有回归测试（对照 `WMS_BUG_BASELINE.md` 状态=已修复的项）
- [] 新增业务函数是否满足 A9（至少 1 个 pytest）
- [] 台账（`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`）与代码/路由/工具/feature flag 是否一致（防虚报）

---

## 五、一键验证命令（汇总）

先跑，把结果作为审计基线：

```bash
make check          # lint + 86 BUG 回归 + pytest tests/
make smoke          # 121 冒烟（需先启动 WMS 服务：python3 app/run_server.py）
python3 scripts/verify_ai_all.py --level full   # AI 子系统全量
python3 scripts/verify_wms_bugs.py              # 86 项静态回归
python3 scripts/scan_wms_risks.py               # 风险扫描
python3 scripts/verify_stability_gate.py        # 稳定性门禁
```

记录每一项的 **通过数 / 失败数 / 失败用例名**。任何失败都必须计入报告，不得静默跳过。

---

## 六、缺陷分级标准

| 级别 | 定义 | 示例 |
|---|---|---|
| **P0 严重** | 数据丢失 / 越权 / 安全漏洞 / 核心流程不可用 | 删除主数据触发外键错误、完成入库后库存不同步、密码可被改、SQL 注入 |
| **P1 高** | 功能异常但可绕过 / 规则违规 | 漏导入导致 NameError、仓库必填缺失、报表无仓库筛选、缺少测试 |
| **P2 中** | 体验 / 健壮性 / 一致性 | 错误提示晦涩、缺少日志、白名单滥用、性能隐患 |
| **P3 低** | 代码风格 / 建议 | 注释缺失、命名不一致 |

---

## 七、报告模板

审计完成后，产出 `WMS_AI_AUDIT_REPORT.md`，结构如下：

```markdown
# WMS 全系统 AI 审计报告

## 0. 审计元信息
- 审计日期、审计基准 commit（本地 / origin/main）、审计范围（M1-M10 勾选）
- 验证命令汇总表（命令 / 通过 / 失败 / 失败用例）

## 1. 审计结论
- 总缺陷数（按 P0/P1/P2/P3 分级）
- 一句话结论：系统当前健康度评级（健康 / 基本健康 / 需重点关注 / 不健康）

## 2. P0 缺陷（必须修复）
### 2.1 [P0-xxx] <标题>
- 位置：`文件:行号`（点击链接）
- 证据：审计时看到的代码 / 复现输出
- 复现步骤：1. 2. 3.
- 根因：为什么会发生
- 影响：丢数据 / 越权 / 崩
- 修复建议：具体改法（含关键代码）
- 回归测试：新增/扩展哪个测试
- 状态：待确认 / 已授权 / 已修复 / 已验证

## 3. P1 缺陷
### 3.1 [P1-xxx] <标题>（同上五要素）

## 4. P2 / P3 缺陷（列表即可）
| ID | 级别 | 位置 | 问题 | 建议 |

## 5. 正项清单（做得好的，供团队延续）
- ...

## 6. 修复执行顺序建议
- P0 → P1 → P2，标注依赖关系
```

---

## 八、缺陷修复流程（仅在用户授权后进行）

1. **申请授权**：P0/P1 修复前，先向用户列出「将改哪些文件、为什么、影响范围」，取得明确同意。**任何密码相关操作、高风险动作（删除/作废/改权限）必须用户逐项授权。**
2. **登记**：在 `WMS_BUG_BASELINE.md` 登记 `BUG-YYYY-MM-DD-NNN: <标题>`（若为 BUG）。
3. **修复**：在 `main` 上直接改；commit message 关联 BUG ID（`fix(<模块>): BUG-xxx ...`）。
4. **回归**：每个 atomic action 独立 commit + push 到 `main`，验证 `git log -1` == `git log origin/main -1`。
5. **禁用项**：`git commit --no-verify` 禁用；业务 JS 裸 `fetch` 禁用；强制采购入库关联 PO 禁用；随机生成密码禁用；建分支禁用。
6. **台账对齐**：修复后更新 `WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md` 与报告状态。

---

## 九、交付物清单

- [ ] `WMS_AI_AUDIT_REPORT.md`（完整审计报告，含元信息/结论/分级缺陷/正项/修复建议）
- [ ] 每项验证命令的实际输出留档（或报告内截图）
- [ ] 若进入修复：BUG 台账已登记、回归测试已补、commit 已推 main

---

## 十、禁止事项（审计员红线）

- ❌ 未经授权修改任何业务代码 / 模型 / 模板 / 数据库 / 测试 / 文档
- ❌ 建分支（`feature/*` / `fix/*` / `chore/*` / `trae/*` 一律禁止）
- ❌ `git commit --no-verify` 跳过钩子
- ❌ 修改 / 重置 / 设置任何用户密码（含 admin），除非用户逐项授权
- ❌ 随机生成密码（未设 `WMS_BOOTSTRAP_PASSWORD` 时用固定 `admin` 并告警）
- ❌ 强制采购入库关联采购订单
- ❌ 自动完成 / 作废 / 删除单据（AI 只能创建草稿，完成需人工）
- ❌ 直接删除已完成单据（必须先反提交回草稿）
- ❌ 无证据产出"我觉得有问题"（每条缺陷必须给文件+行号+复现）
- ❌ 把 `from_location` 等库位字段当仓库名用，混淆仓库与库位概念