# WMS 全面代码审计报告（2026-09-13）

## 1. 摘要

审计对象：当前工作区 `main`，审计 HEAD 为 `57f13b47ba0d6ade146ed12225df579c4cef44d0`。规则文件按要求依次通读：`AGENTS.md`、`DEVELOPMENT_RULES.md`、`WMS_BUG_BASELINE.md`、`INVENTORY_TRUTH.md`、`AI_PERMISSION_MATRIX.md`、`WMS_AI_FUNCTION_DEVELOPMENT_PLAN.md`。

总体健康度：**C+（核心库存近期修复较强，但仍存在多个仓库级库存校验消费点和工程/环境风险；不宜称为无 BUG）**。

维度结论：

- D1 库存一致性：**需整改**。统一 `deduct_stock_atomic` 已加强，但仍有多个库存校验直接使用 `material.stock`，与 A11/R2 的仓库级真相不一致。
- D2 分页：**基本通过，需持续审计**。移动端主要接口提供 `total/page/page_size/total_pages`，Android 关键消费方存在翻页合并；Web 列表主要使用服务端分页。
- D3 安全：**静态门禁通过，生产配置需确认**。CSRF/危险模板扫描通过；生产日志中明确出现 `SESSION_COOKIE_SECURE=False` 警告，必须确认反向代理 HTTPS 配置。
- D4 业务规则：**核心库存/盘点边界近期已修复并有回归**；已完成单据删除、人工确认边界和采购入库解耦与规则一致。
- D5 打印降级：**代码已有 busy timeout、低频重试和中文指引**；`wechat_helper.py:603` 仍有 `traceback.print_exc()`，需人工确认是否位于生产打印/写库热路径。
- D6 前端：**静态门禁通过**；模板 `innerHTML` 较多，已见点主要配套 `escapeHtml`，仍建议持续做运行时 XSS 审查。
- D7 工程质量：**需整改**。`app/app.py` 仍有 34,164 行；全仓 679 个 `@app.route` 注册点，且多项存量 POST 路由只以注释说明未来迁移 pydantic。
- D8 Android：**契约文档和翻页/离线/幂等回归较完整，仍需 CI/APK 结果确认**；本次未运行 Gradle 真机测试。
- D9 测试/台账：**总体良好但未全绿**。全量 1,588 passed、85 skipped、4 failed；AI 台账规模大，已完成状态需继续逐项对账。
- D10 运维：**需整改**。WMS CI 和 Android APK CI 在审计时仍为 `in_progress`；Windows 路径/文件占用测试问题未解决。

Top 5 风险：

1. 仍存在跨仓库库存校验使用全局 `material.stock`，可能发生 A 仓掩护 B 仓。
2. `material.stock` 与流水/仓库级库存的派生关系依赖大量调用方手工保持，架构上仍易复发。
3. 大量路由集中在单体 `app.py`，新增路由和输入契约审计成本高。
4. 生产若未启用 HTTPS cookie，登录会话可能经 HTTP 明文传输。
5. 全量测试仍有 4 个失败，虽在原始提交复现，但会降低发布信号可信度。

## 2. 发现明细

| ID | severity | 维度 | 标题 | 文件:行号 | 根因 | 同根因扩散点 | 基线查重结果 | 修复建议 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| AUDIT-2026-09-13-001 | P0 | D1 | 库存校验仍有全局总账消费点 | `app/routes/requisition.py:360,460`；`app/routes/transfer.py:374,994`；`app/routes/subcontract.py:320,1211,1274`；`app/routes/sales.py:1177`；`app/app.py:16908` | 这些路径以 `material.stock` 或其派生值判断可用量；在多仓库模式下总账是全系统合计，不代表当前仓库。场景：A 仓 0、B 仓 100，从 A 仓提交数量 10，若命中这些旧消费点，校验可能通过。 | 已排查 `after_sale_out.py:409`、`adjustment.py:364`、调拨完成/反提交；本次四个修复提交已覆盖其中部分路径，但上述点仍需逐一按单据仓库替换为 `get_warehouse_stock_quantities()`。 | `INVENTORY_TRUTH.md:185-205` 与 A11 明确禁止；`WMS_BUG_BASELINE.md` 已记录同根因历史，但未登记这些当前剩余消费点；不是重复已修复项。 | 以仓库对象/ID为输入，统一调用 `get_warehouse_stock_quantities()`；在事务写锁内按物料累计需求校验；为每个消费点补 A/B 两仓回归。 |
| AUDIT-2026-09-13-002 | P1 | D1/D4 | 库存校验规则仍未形成单一强制入口 | `app/app.py:3745-3790`；`app/routes/*.py` 多处直接调用 `material.stock` | 虽然 `deduct_stock_atomic` 已有仓库级保护，但大量路由先做一次全局预校验，造成“前置判断与最终扣减口径不一致”，错误消息也可能显示全局库存。未来新入口容易复制旧模式。 | 同 AUDIT-2026-09-13-001，尤其 requisition/transfer/subcontract/sales 和 AI 缺货判断；应按模块完成同类点清单。 | 基线包含多仓库反复 BUG（08-16/08-17/08-23/08-27），但当前剩余消费点未单独登记；待维护者确认历史记录是否已覆盖这些 exact path。 | 删除重复前置全局校验，或将其改为统一仓库级 helper；A11 lint 应从“新增行”逐步扩大到存量白名单收敛。 |
| AUDIT-2026-09-13-003 | P1 | D3/D10 | 生产会话安全依赖外部配置，默认明确警告不安全 | `app/app.py` 启动日志（运行时警告）；配置项 `SESSION_COOKIE_SECURE` | 启动时可出现 `SESSION_COOKIE_SECURE=False in production`。若生产没有 TLS 终止或 cookie secure 配置，session cookie 可经 HTTP 发送。 | `app/run_server.py`、部署 checklist、反向代理配置需联合确认。 | `WMS_BUG_BASELINE.md` 未发现同一 exact 生产配置问题；该发现是部署风险，标为待人工确认，不宣称已被利用。 | 生产环境强制 HTTPS；启动时在 production + 非 secure 时阻止启动或要求显式 `WMS_ALLOW_INSECURE_COOKIE=1` 且记录高危告警；部署 checklist 加硬门禁。 |
| AUDIT-2026-09-13-004 | P1 | D5 | WeChat helper 仍存在裸 `traceback.print_exc()` | `app/wechat_helper.py:603` | 异常处理直接打印完整 traceback，可能在定时/消息处理失败时刷屏，且可能泄露路径、SQL/请求上下文；R4 要求打印/写库链路降级静默。 | `app/local_print_agent.py` 已有较完整降级；需继续确认 `wechat_helper.py` 是否触达打印/写库/定时任务。 | `WMS_BUG_BASELINE.md` 有打印锁/降级历史，但未确认本行是否已登记；待人工确认调用路径。 | 改用带节流的 logger；区分业务可见中文提示与内部 debug 日志；增加异常频率回归。 |
| AUDIT-2026-09-13-005 | P1 | D7 | 新增/存量 POST 路由的 pydantic 覆盖不可机械证明 | 统计：679 个 `@app.route`，其中约 328 个含 POST/PUT/DELETE 的路由记录；多个路由带注释 `pydantic:reason=存量路由...` | A8 只对 staged 新增行生效，存量路由大量仍是 `request.form`/`request.get_json` 手工解析。当前规则允许存量，但审计无法证明近 90 天所有新增写路由都完成 BaseModel 输入契约。 | `app/routes/` 全部写入域，重点 `in_order.py`、`out_order.py`、`subcontract.py`、`native_api.py`、`mobile.py`。 | `DEVELOPMENT_RULES.md` 明确 A8 仅新增代码生效；因此不将全部存量路由误报成违规。需要结合逐提交 diff 复核。 | 在 CI 加“近 90 天新增写路由 diff 对照”；为高风险库存写入口优先增加 Pydantic model，并将错误响应统一 422/业务 JSON。 |
| AUDIT-2026-09-13-006 | P2 | D10 | Windows 测试环境存在 4 个既有失败 | `tests/test_auto_migrate_db_path.py:44,63`；`tests/test_material_image_static_path.py:34,48,54` | POSIX 路径断言在 Windows 得到反斜杠；图片测试清理时文件仍被程序占用。4 项在原始 `51ddf0c` 上复现，非本次改动引入，但全量 CI 信号不干净。 | 所有使用 `Path` 与硬编码 `/` 的测试；所有图片读取/写入后未显式关闭句柄的测试/实现。 | 原始提交同样失败，不能登记为本次新业务 BUG；属于工程质量遗留。 | 使用 `Path`/`as_posix()` 明确契约；图片操作使用上下文管理并在测试 teardown 前关闭资源；Windows CI 单独纳入门禁。 |

上述 P0/P1 均有源码证据；AUDIT-001 的业务后果可按“两仓库存 A=0/B=100、从 A 扣 10”复现。数据库路由级复现应使用隔离 SQLite 和登录测试账号，禁止在生产库操作。

## 3. 误报澄清

- `app/app.py:4617` 的 `material.stock` 单仓短路是库存历史脏数据兼容分支，不直接认定为漏洞；需在新增第二仓库时验证连续性。
- 大量 `material.stock` 展示、估值、库存天数、AI 说明属于全局合计语义，不按 A11 误报；只有比较/拦截可用量才列为风险。
- `secrets.token_urlsafe()` 出现在打印 lease/auth token 和移动登录 token 生成处，不等同于账号密码随机生成；未发现 bootstrap 密码随机生成。
- `app/local_print_agent.py` 的 `traceback` 与 `database is locked` 处理已有低频降级和中文提示，未重复报告；仅 `wechat_helper.py:603` 待确认。
- 4 个 pytest 失败在原始审计基线复现，因此不报告为本次修复回归。
- 679 个 route 注册点不等于 679 个公开 URL：包含同 endpoint 兼容注册和迁移模块；报告使用静态注册计数，不冒充运行时 URL 唯一计数。

## 4. 台账对账差异

### 台账说完成但本次代码审计仍需人工确认

- AI 计划与 `AI_PERMISSION_MATRIX.md` 声明的多项 AI 能力在静态回归中有注册/审计/幂等基础，但本次没有逐项调用真实 provider；“代码路径存在”不等于 provider 线上可用。
- Android 离线队列、错误文案和幂等相关 BUG 已有大量回归文件，但未执行 Gradle build、真机网络切换和进程杀死恢复；发布前仍需 CI/设备确认。
- 打印降级相关历史项已标已修复，但 `wechat_helper.py:603` 的实际调用链尚未通过生产式任务运行确认。

### 代码存在但台账/审计计划需继续核对

- `app/app.py:16908`、`app/routes/requisition.py:360,460`、`app/routes/transfer.py:374,994`、`app/routes/subcontract.py:320,1211,1274`、`app/routes/sales.py:1177` 仍有全局库存判断；本报告登记为 AUDIT-001/002，避免只修一处。
- 运行时明确打印 production session cookie 不安全警告；部署 checklist 是否在所有环境强制 secure cookie，需要维护者补充证据。
- 近 90 天新增路由的 pydantic 对账没有现成机器可读报告，建议新增提交级审计脚本，而不是凭注释判断。

## 5. 修复优先级路线图

- **P0 立即修：** 完成 AUDIT-001 全仓库级库存消费点迁移（约 10 个文件、20 个判断点），补两仓隔离和历史脏数据回归；预计 1–2 个 atomic action。
- **P1 本周：** 把库存可用量统一封装为单一 helper，收敛 AUDIT-002（约 3–6 个文件）；生产强制 HTTPS cookie（配置/部署清单/启动检查）；清理 `wechat_helper.py` traceback 并增加节流测试。
- **P1 本周：** 建立近 90 天 POST/PUT/DELETE 路由 diff 审计脚本，输出 route、auth、role、BaseModel、测试映射；预计 1 个 scripts action。
- **P2 排期：** 解决 Windows 路径断言和图片句柄释放；将 `app.py` 路由继续拆入域模块；补全 Android Gradle/真机离线恢复与契约测试。

## 6. 附录：覆盖统计与命令

### 代码规模

- `app/app.py`：34,164 行。
- `app/routes/`：47 个 Python 模块；合计约 37,000 行，模块清单见目录，最大模块为 `in_order.py` 2,913 行、`native_api.py` 2,544 行、`sales.py` 2,105 行、`subcontract.py` 2,279 行。
- `app/static/js/`：6 个 JS 文件（含第三方 `xlsx.full.min.js`）。
- `app/templates/`：133 个 HTML 模板。
- `tests/`：1745 个测试定义匹配项/类项静态计数；全量执行报告 1,588 passed、85 skipped、4 failed。
- `app/android-native-wms/`：92 个文件，包含 Android app、data/model/repository、UI/viewmodel 等模块。
- 静态 `@app.route` 注册：679；蓝图声明计数：6；含写方法的静态路由记录约 328。具体 auth/role/pydantic 机器输出保存在审计运行临时结果中，重点缺口已在 AUDIT-005 列出。

### 库存写入与读取出口

- 写入核心：`add_stock()`、`deduct_stock_atomic()`、`add_stock_transaction()`、`add_location_inventory_atomic()`、`deduct_location_inventory_atomic()`、`update_location_inventory()`、`_apply_opening_stock_balance()`。
- 单据写入域：`in_order.py`、`out_order.py`、`transfer.py`、`check.py`、`adjustment.py`、`after_sale_out.py`、`requisition.py`、`subcontract.py`、`opening_stock.py`、`native_api.py`、`mobile.py`、`sales.py`。
- 读取出口：`stock_query.py` 库存查询、`report.py` 报表、`app.py` 台账/库存聚合、`mobile.py`/`native_api.py` Android API、AI warehouse/purchase/admin 工具、Android `WmsRepository.kt` 与 `StockQueryModels.kt`。

### 验证命令

```text
python -m pytest tests/ -q --disable-warnings --tb=short
  1588 passed, 85 skipped, 4 failed
  失败：2 个 Windows POSIX 路径断言；2 个 Windows 图片文件占用/迁移测试；均在原始 51ddf0c 复现

python scripts/verify_wms_bugs.py
  通过

python scripts/lint_wms_rules.py
  0 违规

python scripts/lint_no_raw_post_fetch.py --repo-root .
  通过

python scripts/verify_remote_sync.py
  本地/远端 1352 个文件 blob 与模式完全同步，远端 main=57f13b47ba...
```

本次未修改业务代码、账号密码、生产数据或分支；仅新增本审计报告。所有“待人工确认”项不会当作已确认漏洞计入 P0/P1 结论，直至补充运行时或部署证据。
