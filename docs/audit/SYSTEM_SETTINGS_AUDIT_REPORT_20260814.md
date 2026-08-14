# 系统设置模块全面审计报告

**审计范围**：`app/routes/system_settings.py`、`app/templates/system_settings.html`、`app/app.py` 中 `SystemSetting` 模型与相关业务函数、lint 脚本、AI 台账
**审计日期**：2026-08-14
**审计方法**：纯静态代码审计，未修改任何代码

## 一、审计概述

系统设置模块整体架构合理：路由采用 `register-on-app` 模式（在 `app/routes/system_settings.py` 内通过 `register_system_settings_routes(app)` 注册，符合 A10），所有路由均有 `@require_role('admin')` + `@login_required` 双重门禁，bootstrap 密码合规（固定 `'admin'` + 警告），AI API Key 以 `secret` 类型存储且不回传浏览器。

## 二、缺陷清单

### P1

#### SYS-AUDIT-001 init_business_data 响应消息谎称"SystemSetting 已保留"，实际已被删除

- **维度**：业务 / 路由
- **文件**：
  - [system_settings.py:274](file:///workspace/app/routes/system_settings.py#L274)（响应消息）
  - [app.py:6753](file:///workspace/app/app.py#L6753)（`INIT_LOG_TABLES` 包含 `('系统参数', SystemSetting)`）
  - [app.py:6932-6935](file:///workspace/app/app.py#L6932-L6935)（遍历 `INIT_LOG_TABLES` 执行 `_bulk_delete_model` 全量删除）
  - [app.py:6888](file:///workspace/app/app.py#L6888)（函数名 `_init_business_data_keep_users_and_settings` 误导）
- **现状描述**：`execute_init_business_data` 路由执行成功后返回消息 `'业务数据初始化完成，User / SystemSetting / 当前管理员账号已保留'`。但实际上 `INIT_LOG_TABLES` 明确包含 `('系统参数', SystemSetting)`，`_init_business_data_keep_users_and_settings` 会遍历该列表调用 `_bulk_delete_model`（执行 `model_cls.query.delete()` 无条件全量删除）。`ensure_default_system_settings()` 仅在服务器启动时调用，init 路由执行后**不会**重新播种。因此执行 init 后 SystemSetting 表为空，所有自定义配置（AI API Key、LLM 接口地址、超时参数等）全部丢失，直到下次服务器重启才恢复默认值。函数名 `_init_business_data_keep_users_and_settings` 也暗示"保留 settings"，与实际行为矛盾。AI 台账 AI-INIT-001 明确记载 SystemSetting 在清理范围内，说明**行为本身是设计意图**，但**响应消息和函数名是错误的**。
- **修复**：① 响应消息改为 `'业务数据初始化完成，User 账号已保留，系统参数已重置为默认值（需重启服务恢复）'`；② 函数名改为 `_init_business_data_keep_users_only` 或在 docstring 中明确说明 SystemSetting 会被清空；③ 可选：init 成功后立即调用 `ensure_default_system_settings()` 恢复默认值。

#### SYS-AUDIT-002 系统设置模块无 pytest 自动收集的测试覆盖

- **维度**：lint（A9） / 测试
- **文件**：
  - [tests/verify_app_py_split_system_settings.py](file:///workspace/tests/verify_app_py_split_system_settings.py)（命名 `verify_` 非 `test_`）
  - [tests/conftest.py](file:///workspace/tests/conftest.py)（未配置 `python_files` 收集 `verify_*.py`）
- **现状描述**：唯一的系统设置测试文件是 `tests/verify_app_py_split_system_settings.py`，文件名以 `verify_` 开头。pytest 默认只收集 `test_*.py` / `*_test.py`，conftest.py 也未通过 `python_files` 配置扩展收集规则。因此该文件**不会被 pytest 自动收集执行**，只能手动 `python verify_app_py_split_system_settings.py` 运行。即便如此，该文件的覆盖也仅限：endpoint 注册、页面渲染 200、空表单保存成功、preview GET 可访问——**完全未覆盖**高风险的 `execute_init_business_data`（密码校验/确认短语/审计写入/清理逻辑）、`test_ai_llm_settings`（连接测试）、int 字段的 min/max 校验、select 字段的选项校验、secret 字段的留空保留逻辑。
- **修复**：① 将文件重命名为 `tests/test_system_settings.py` 使 pytest 自动收集；② 补充 `execute_init_business_data` 失败路径测试（错密码 403、错短语 400、成功路径审计写入）；③ 补充 `save_system_settings` 的 int 越界校验、select 非法值校验、secret 留空保留测试。

### P2

#### SYS-AUDIT-003 全部 3 个 POST 路由使用 pydantic 豁免注释，手工校验易漏

- **维度**：lint（A8） / 路由
- **文件**：
  - [system_settings.py:41](file:///workspace/app/routes/system_settings.py#L41)（`save_system_settings` 豁免）
  - [system_settings.py:95](file:///workspace/app/routes/system_settings.py#L95)（`test_ai_llm_settings` 豁免）
  - [system_settings.py:153](file:///workspace/app/routes/system_settings.py#L153)（`execute_init_business_data` 豁免）
- **现状描述**：三个 POST 路由均带 `# pydantic:reason=存量路由从 app.py 原样迁移，保持行为不变，pydantic 迁移另行任务` 豁免注释，绕过 A8 pydantic 校验。所有参数通过 `request.form.get()` 手工读取和校验。`save_system_settings`（第 50-83 行）的 int 校验（min/max）、bool 校验、select 校验、secret 处理分散在 30 行 if-elif 中，逻辑较复杂；`execute_init_business_data`（第 167-169 行）的 `admin_password`/`confirm_phrase`/`include_master_data` 三个参数均手工 strip 和比较，无类型契约。这是已知的存量技术债，豁免注释合规，但手工校验长期维护风险高。
- **修复**：为三个路由引入 pydantic BaseModel（如 `SaveSystemSettingsForm`、`InitBusinessDataExecuteForm`），将 int min/max、select options、bool 解析逻辑声明为 Field 约束，移除豁免注释。

#### SYS-AUDIT-004 模板内联 JS 使用 `window.csrfFetch || fetch` 回退模式，lint 不覆盖内联脚本

- **维度**：前端 / lint
- **文件**：[system_settings.html:283,314,347,427,489](file:///workspace/app/templates/system_settings.html#L283)
- **现状描述**：模板 `{% block extra_js %}` 内联 `<script>` 中有 5 处 `const fetcher = window.csrfFetch || fetch;` 后跟 `fetcher(url, { method: 'POST', body: ... })`。`scripts/lint_no_raw_post_fetch.py` 仅扫描 `app/static/js/*.js`，**不扫描模板内联脚本**。若 `window.csrfFetch` 未定义，会回退到裸 `fetch`。实际风险被 `base.html` 全局 fetch 拦截器（覆盖 `window.fetch` 自动注入 `X-CSRFToken`）缓解，因此**当前不会导致 CSRF 丢失**。但这属于 lint 覆盖盲区——未来若有人删除 base.html 拦截器，此处会静默丢失 CSRF。
- **修复**：① 将内联 JS 抽取到 `app/static/js/system_settings.js`，统一走 `WMS.api.post()` 或 `csrfFetch()`；② 或扩展 `lint_no_raw_post_fetch.py` 扫描模板内联 `<script>` 块。

#### SYS-AUDIT-005 主表单缺少 `method="post"` 属性，A1 lint 规则未覆盖

- **维度**：前端 / lint（A1）
- **文件**：[system_settings.html:120](file:///workspace/app/templates/system_settings.html#L120)
- **现状描述**：主设置表单为 `<form id="systemSettingsForm" class="settings-layout">`，**没有 `method="post"` 属性**（通过 JS `event.preventDefault()` + `fetcher('/system_settings/save', { method: 'POST', ... })` 提交）。A1 规则仅匹配 `<form ... method="post"`，因此此 form **不被 A1 扫描**。表单内确实包含 `<input type="hidden" name="csrf_token" value="{{ csrf_token() }}">`，且 JS 使用 `new FormData(form)` 提交时携带该 token，实际 CSRF 保护有效。但 A1 的设计意图是"所有 POST 表单必须有 csrf_token"，此表单通过 JS 提交绕过了检测。
- **修复**：① 给 form 加 `method="post"` 属性（即使 JS 拦截提交，属性本身不影响行为，但让 A1 能扫描）；② 或扩展 A1 规则识别 JS 提交的 form。

#### SYS-AUDIT-006 execute_init_business_data 清空全部历史审计记录

- **维度**：业务 / 权限
- **文件**：
  - [system_settings.py:261-264](file:///workspace/app/routes/system_settings.py#L261-L264)
  - [system_settings.html:223](file:///workspace/app/templates/system_settings.html#L223)（用户告警）
- **现状描述**：init 成功后执行 `OperationAudit.query.filter(~OperationAudit.id.in_(keep_ids)).delete(synchronize_session=False)`，删除除本次 preview+done 两条外的**全部历史审计记录**。这会永久销毁此前所有操作的审计轨迹（谁删了什么单据、谁改了什么库存等），属于合规风险。模板已告警用户"操作写入 OperationAudit 审计（preview/done/failed）后连同历史审计一并清空"，AI 台账 AI-INIT-001 也明确记载此行为，因此是**设计意图**而非 bug。但审计日志销毁在许多合规框架（如等保、SOX）中是敏感操作。
- **修复**：① 在清空前自动导出一份 OperationAudit 全量备份（JSON/CSV）到 `output/audit_backup/` 并在响应中返回下载链接；② 或改为"软删除"（标记 archived 而非物理删除）；③ 至少在执行前要求用户先访问 `/backup` 创建数据库备份（模板已有提示但非强制）。

#### SYS-AUDIT-007 装饰器顺序非标准：`@require_role` 在 `@login_required` 之上

- **维度**：路由 / 权限
- **文件**：[system_settings.py:34-36, 42-44, 96-98, 145-147, 154-156, 285-287, 293-295, 299-301](file:///workspace/app/routes/system_settings.py#L34-L36)
- **现状描述**：所有路由的装饰器顺序为 `@app.route` → `@require_role('admin')` → `@login_required` → `def view()`。装饰器自底向上应用，因此执行顺序是 `require_role` 先于 `login_required`。标准 Flask 模式应为 `@login_required` 在上（先执行认证）、`@require_role` 在下（后执行角色检查）。但实际 `require_role`（utils.py:650-658）内部**已先检查 `current_user.is_authenticated`**（未认证则 302 重定向到 login），因此功能上不会出错——`@login_required` 实际是冗余的。这不是 bug，但非常规写法，可能误导后续开发者认为 `@login_required` 是主认证层。
- **修复**：统一调整为 `@app.route` → `@login_required` → `@require_role('admin')` → `def view()`，或移除冗余的 `@login_required`（因 `require_role` 已覆盖认证检查）。

#### SYS-AUDIT-008 错误响应向用户暴露原始异常消息

- **维度**：权限 / 安全
- **文件**：
  - [system_settings.py:142](file:///workspace/app/routes/system_settings.py#L142)（`f'连接失败：{exc}'`）
  - [system_settings.py:236](file:///workspace/app/routes/system_settings.py#L236)（`f'初始化失败：{exc}'`）
  - [system_settings.py:283](file:///workspace/app/routes/system_settings.py#L283)（`f'初始化异常：{exc}'`）
- **现状描述**：三处异常处理将原始 `Exception` 对象的字符串表示直接拼入返回给用户的 JSON 消息。`test_ai_llm_settings` 的 `except Exception as exc` 可能捕获到包含 LLM 供应商内部 URL、API Key 片段、连接超时细节的异常；`execute_init_business_data` 的异常可能暴露数据库表名、SQL 错误、文件路径等内部信息。虽然仅 admin 可见，但若 admin 浏览器被 XSS 或网络抓包，内部信息会泄露。
- **修复**：① 对外返回通用消息（如"连接失败，请查看服务器日志"），将 `str(exc)` 仅写入 `app.logger.exception()`；② 若需向 admin 展示诊断信息，截断到 100 字符并过滤敏感关键词（url/key/secret/password）。

#### SYS-AUDIT-009 init 模态框硬编码 `include_master_data='1'`，用户无法选择保留主数据

- **维度**：业务 / 前端
- **文件**：
  - [system_settings.html:488](file:///workspace/app/templates/system_settings.html#L488)（`fd.append('include_master_data', '1')`）
  - [system_settings.py:169](file:///workspace/app/routes/system_settings.py#L169)（后端读取 `include_master_data`）
- **现状描述**：前端确认按钮的 JS 硬编码 `fd.append('include_master_data', '1')`，用户没有 checkbox 或开关来选择是否同时清空主数据（物料/分类/单位/供应商/客户/仓库/部门/员工/合同/模板）。后端（第 169 行）支持 `'0'`（仅清业务数据，保留主数据）和 `'1'`（同时清主数据）两种模式，但前端从不传 `'0'`。这意味着每次 init 都会清空全部主数据，用户无法选择"只清业务单据、保留物料档案"的温和模式。
- **修复**：在模态框中增加一个 checkbox"同时清空主数据（物料/供应商/仓库等）"，默认勾选，允许用户取消以保留主数据。

#### SYS-AUDIT-010 SystemSetting 模型定义在 app.py 而非 models.py

- **维度**：模型 / 架构
- **文件**：
  - [app.py:5617-5626](file:///workspace/app/app.py#L5617-L5626)（`class SystemSetting(db.Model)`）
  - [app/models.py](file:///workspace/app/models.py)（未包含 SystemSetting）
- **现状描述**：`SystemSetting` 模型定义在 `app/app.py` 第 5617 行，而非 `app/models.py`。同样地，`OperationAudit`（app.py:3123）、`OperationLog`（app.py:4676）也在 app.py 内。这与项目的 `app/routes/` 拆分模式（A10 鼓励路由走出 app.py）精神不一致——模型也应集中在 models.py。这是存量代码，A10 仅约束新增 `@app.route`，不约束模型位置，因此不违规。但 app.py 已达约 2 万行，模型分散加剧维护困难。
- **修复**：将 `SystemSetting`、`OperationAudit`、`OperationLog` 等系统级模型迁移到 `app/models.py`（或新建 `app/models/system.py`），保持 app.py 仅作为应用工厂。

#### SYS-AUDIT-011 save_system_settings 无写锁，并发保存存在 last-write-wins 风险

- **维度**：业务 / 并发
- **文件**：[system_settings.py:48-86](file:///workspace/app/routes/system_settings.py#L48-L86)
- **现状描述**：`save_system_settings` 遍历 `SYSTEM_SETTING_DEFINITIONS`，对每个 key 调用 `get_system_setting`（读当前值）→ 比较 → `set_system_setting`（写新值），最后统一 `db.session.commit()`（第 86 行）。全程无 `with_for_update()` 行锁。若两个 admin 同时保存不同设置项，后提交者会覆盖前者的部分变更（取决于哪些 key 在两次请求中都被处理）。`set_system_setting`（app.py:2207-2220）使用 `filter_by(key=key).first()` 查询后更新，也不带锁。SQLite 的 WAL 模式缓解了读写并发，但两个并发写事务仍可能冲突。
- **修复**：在 `set_system_setting` 中对查询加 `.with_for_update()`，或在路由入口对 SystemSetting 表加表级 advisory lock。由于设置保存频率低、admin 人数少，风险等级为 P2。

---

## 三、审计确认合规的维度（无缺陷）

以下维度经审计确认**符合** AGENTS.md 规则，无缺陷：

1. **密码规则**：bootstrap 密码正确使用固定 `'admin'` 默认值 + 警告日志（app.py:5681-5686, 5729-5734, 5750），未使用 `secrets.token_urlsafe` 生成密码。`secrets.token_urlsafe(12)` 仅用于 AI 文档确认 token（非密码用途）。**合规**。

2. **AI 权限边界**：`test_ai_llm_settings` 仅 admin 可访问；不修改用户角色/密码/密钥；AI API Key 以 `secret` 类型存储，`get_grouped_system_settings` 将 secret 的 value 置空不回传浏览器；`save_system_settings` 对 secret 字段留空时保留原值。**合规**。

3. **仓库规则**：`SystemSetting` 模型无 `warehouse_id` 字段，这是正确的——系统设置是全局配置，不属于"出入库单据/库存查询/出入库报表/库存台账"范畴，AGENTS.md 仓库必填规则不适用于系统设置。`prefer_default_warehouse` 设置项仅控制录单时是否自动带出默认仓库，本身不需要关联仓库。**合规**。

4. **导出规则**：`/system_settings/export` 仅 302 重定向到 `/batch_import?type=system_settings`，系统设置导出不属于库存查询/出入库报表/库存台账，无需仓库必填筛选。**合规**。

5. **CSRF 保护（A2）**：所有 POST 路由均有 `@login_required`（Flask-WTF CSRF 默认启用），无 `@csrf.exempt`。**合规**。

6. **SQL 注入（A7）**：全部使用 SQLAlchemy ORM（`filter_by`/`query.delete`/`query.update`），无 raw SQL 字符串拼接。**合规**。

7. **敏感配置暴露**：`ai_llm_api_key` 不回传浏览器；`ai_llm_base_url`、`ai_llm_model` 等非密配置正常展示但不含凭据；数据库连接字符串不在 SystemSetting 中管理（在 config.py）。**合规**。

8. **A10 合规**：系统设置路由已迁移到 `app/routes/system_settings.py`（register-on-app 模式），app.py 内无新增 `@app.route`。**合规**。

---

## 四、修复优先级建议

1. **P1-1 响应消息纠偏**：先修 `SYS-AUDIT-001`（init 响应消息 + 函数名），避免 admin 被误导以为 SystemSetting 已保留，实际配置已清空。改动量小（仅消息文本与函数名）。
2. **P1-2 测试覆盖补齐**：修 `SYS-AUDIT-002`，将 `verify_app_py_split_system_settings.py` 重命名为 `test_system_settings.py`，并补充高风险路径（init 失败路径、save 越界校验）测试。
3. **P2 批次**：`SYS-AUDIT-003`（pydantic 迁移）、`SYS-AUDIT-004+005`（lint 覆盖盲区）、`SYS-AUDIT-006`（审计日志销毁）、`SYS-AUDIT-007`（装饰器顺序）、`SYS-AUDIT-008`（异常信息脱敏）、`SYS-AUDIT-009`（include_master_data 开关）、`SYS-AUDIT-010`（模型迁移）、`SYS-AUDIT-011`（写锁）——可合并为一次系统设置模块加固任务。

---

## 五、修复任务映射（建议登记到 WMS_BUG_BASELINE.md）

| 建议 BUG ID | 对应审计项 | 优先级 |
|---|---|---|
| BUG-2026-08-14-012 | SYS-AUDIT-001 | P1 |
| BUG-2026-08-14-013 | SYS-AUDIT-002 | P1 |
| BUG-2026-08-14-014 | SYS-AUDIT-003 | P2 |
| BUG-2026-08-14-015 | SYS-AUDIT-004 + SYS-AUDIT-005（lint 覆盖盲区一组） | P2 |
| BUG-2026-08-14-016 | SYS-AUDIT-006 | P2 |
| BUG-2026-08-14-017 | SYS-AUDIT-007 | P2 |
| BUG-2026-08-14-018 | SYS-AUDIT-008 | P2 |
| BUG-2026-08-14-019 | SYS-AUDIT-009 | P2 |
| BUG-2026-08-14-020 | SYS-AUDIT-010 | P2 |
| BUG-2026-08-14-021 | SYS-AUDIT-011 | P2 |

---

## 六、与 AI 台账对照

| 台账任务 ID | 状态 | 相关度 | 说明 |
|---|---|---|---|
| AI-INIT-001 | 已完成 | 直接相关 | init_business_data 功能的原始任务。台账明确记载 SystemSetting 在清理范围内，但路由响应消息和函数名仍错误（SYS-AUDIT-001）。建议以子修复 ID `AI-INIT-001-FIX-01` 跟踪。 |
| AI-DEPLOY-F01-FIX-01 | 已完成 | 间接相关 | `github_auto_update_enabled` 系统设置项，默认关闭。本审计未发现该设置项有缺陷。 |
| WMS_BUG_BASELINE.md | — | 无直接匹配 | 无系统设置模块的已登记 bug。本审计缺陷均未在 BUG_BASELINE 中重复登记。 |

**结论**：本审计报告的 11 项缺陷均未在 AI 台账或 BUG_BASELINE 中重复登记，可作为新增修复项录入。

---

## 七、lint 覆盖总结

| 规则 | 系统设置模块覆盖情况 | 缺口 |
|---|---|---|
| A1（form csrf） | 主表单无 `method="post"`，A1 不扫描（SYS-AUDIT-005） | 内联 JS 提交的 form 绕过检测 |
| A2（POST 路由 CSRF） | 全部 POST 路由有 `@login_required` | 无缺口 |
| A3-A5（JS console/debugger/eval） | 模板内联 JS 无违规 | lint 不扫描模板内联 JS（SYS-AUDIT-004） |
| A6（Python print） | 路由文件无 print | 无缺口 |
| A7（SQL 拼接） | 全 ORM | 无缺口 |
| A8（pydantic） | 3 个 POST 路由有豁免注释（SYS-AUDIT-003） | 存量技术债 |
| A9（新增函数测试） | verify_ 文件不被 pytest 收集（SYS-AUDIT-002） | 测试覆盖不足 |
| A10（app.py 路由） | 路由已迁移到 routes/ | 无缺口 |
| 裸 fetch | 模板内联 JS 用 `window.csrfFetch \|\| fetch`（SYS-AUDIT-004） | lint 不扫描模板内联 JS |
