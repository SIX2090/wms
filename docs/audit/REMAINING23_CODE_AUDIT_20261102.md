# 固定23项代码复核及三类修复（2026-11-02）

本批依据“条件不足的只检查代码”，完成固定23项和已列局部边界的源码映射。基线 `c74e14a6dd0003ec30ef4f96b842cc734aa8df4e`；独立 main 副本位于 `C:/wms_backups/code_audit_remaining_20261102_round70/repo`。未访问生产文件、库、接口或服务，未接真实模型、设备、发送端或账号凭据。旧合并/删除授权已用尽，本轮没有再次执行。

相对 round69 的 `7ce3b365`，基线只增加出库录单按钮文案及相关文档/测试；下表涉及实现未变的旧证据按源码调用链映射，不把旧验收重计为新增。开工前精确基线 WMS CI41397709288、AI41397709253成功；Android41356189466对应 `2afd4c055213ddc62c2b3daa07453af926b4f2fc`，成功祖先、完整对象和构建输入无变化已核。

三类确认缺陷：BUG-2026-11-02-013最终异常堆栈日志脱敏遗漏；014供应商HTTP/数据/活动请求防护；015同工作站令牌重复重置。除此之外的条件性风险不升级为已复现缺陷，不扩大本批产品改动。

## 23项映射

行号以本批候选为准，函数名用于后续定位；“未发现新问题”仅指本次有界源码检查。

| ID / 入口 | 当前源码锚点及调用链 | 既有证据与版本关系 | 本轮结论 / 仍缺条件 |
|---|---|---|---|
| 003 文本连接测试 | `app/routes/system_settings.py:125` → `app/app.py:13263` `_ai_call_llm_intent`；超时12984、令牌上限12993 | `test_system_settings_transport_runtime.py`现版替身回归；权限/输入旧HTTP证据沿用 | 013共用日志缺陷已修；配置URL若携凭据被写入操作记录是条件性静态风险，未读取真实参数。真实供应商响应/收费未验 |
| 004 图片连接测试 | `system_settings.py:125` → `app.py:23081` `_ai_test_llm_vision`，公共错误掩码 | `test_round26_risks_http.py::test_vision_diagnostics_do_not_echo_provider_internals`旧证据；现版安全模块比对 | 013共用日志缺陷已修；图像调用成功率与质量仍需专用接口/预算 |
| 006 工具栏找图 | `app/templates/material.html:1516` → `:2003` `findMaterialImage` → `app/routes/material.py:451` → `app.py:8843` | `test_material_image_search_lifecycle_runtime.py`现版替身回归；外部360运行包不是当前Git实现 | 未发现新的生命周期问题。当前Git仍百度优先、Bing回退，两源失败返回空；属于版本/可用性限制，不能引用其他运行包宣称已改成360 |
| 007 行内找图及选定 | `material.html:200` → 同一找图函数 → `:2075`选定 → `routes/material.py:468` → `app.py:8905`下载保存 | 同006；既有候选错误修复005；旧联网12图可加载不代表识图准确或已选定 | 已核URL/公网地址/逐跳重定向、大小、类型及图片解码。下载文件成功后数据库提交失败可能留孤立文件是静态风险；本轮未下载/写图片 |
| 009 创建工作站 | `app/templates/print_routing.html:400` `addWs` → `app/routes/print_routing.py:359` | `test_page_feedback_runtime.py`；现有addWs已互斥，未重复开发 | 未发现新问题；管理员、输入校验、唯一编码、一笔提交后一次展示；实际新凭据及代理握手未验 |
| 012 重置工作站令牌 | `print_routing.html:444` `resetToken` → `routes/print_routing.py:404` | 现版实际JS替身；旧码两条重复派发反证 | 015已修：同目标活动请求/成功导航前锁，取消无请求、失败可人工重试、不同目标独立。未生成或重置真实令牌，跨客户端旋转未验 |
| 017 OCR开始识别 | `app/templates/document_ocr.html:144,270`取消/代次 → `app.py:32419` → `app/ai/documents/provider_router.py:292` → `services/document_ocr_feedback.py:5` | 既有35/36/37协议、数量/包装修复证据；调用链本版复核 | 013共用日志缺陷已修；重试有界、公共错误不带原始上游内容，前端迟到丢弃。真实中文单据质量/服务失败费用未验 |
| 018 供应商生成评估 | `app/templates/ai_supplier_evaluation.html:129` → `app.py:34818` → 请求内历史缓存34857 → AI建议 | 既有AI-C13及BUG-2026-11-01-018只修价格缓存；本轮9个实际JS+api.js替身场景 | 014已修：HTTP失败不再渲染成功、结构/汇总校验、活动请求防重。真实模型评估质量与数据规模未验 |
| 019 生成需求预测 | `app/templates/ai_demand_forecast.html`请求代次/筛选 → `app.py:35144` `ForecastInput` → 预测/建议 | `test_ai_forecast_lifecycle_runtime.py`安全JS部分现版回归；原后端空库用例本轮排除 | 未发现新问题；显式100物料上限是既有限制，不能称全物料预测。真实需求准确性未验 |
| 021 立即分享今日 | `wechat_share.html:450` → `routes/wechat_share.py:163` → `app.py:25102` → `services/wechat_share_dispatch.py:142` | 现版`test_wechat_share_transport_runtime.py`；既有dispatch独立worker、提交失败替身证据映射 | 未发现新问题；总开关先于投递，领取先提交，未知回执转uncertain不自动重发。真实送达/客户端回执未验 |
| 023 重生成再发今日 | 同021，显式force确认 → dispatch唯一领取/CAS/uncertain规则 | 同021；未重新发送任何历史消息 | 未发现新的强制重发边界问题。历史日志级resend是否受总开关统一约束是静态策略疑点（UI只明确今日/自动入口），不据此宣称已复现误发 |
| 024 入库拍照 | `mobile_scan.html:968-1065`代次/取消 → `routes/mobile.py:1115`识物只读匹配 | BUG-2026-11-02-007及round30/相邻移动生命周期旧证据；现版调用链一致 | 未发现新生命周期问题；扩展名/大小限制不能替代真实文件内容与模型质量验收；无手机 |
| 025 入库条码 | `mobile_scan.html:459,487,606` stop/start/pagehide → 当前reader/stream身份守卫 | 既有SDK迟到采流/停止轨道证据；现版同实现 | 未发现新问题；真实摄像头授权、对焦、持续扫描未验 |
| 026 出库拍照 | 同024，mode=out；识别后仍走单据人工操作 | 同024；没有本轮出库或库存动作 | 同024，真实设备未验 |
| 027 出库条码 | 同025，mode=out | 同025；共享生命周期不按入口重计新用例 | 同025，真实设备未验 |
| 028 盘点拍照 | 同024，mode=check | 同024；识别与盘点完成权限分离 | 同024，真实设备与盘点业务后续动作未新增验收 |
| 029 盘点条码 | 同025，mode=check | 同025 | 同025，实机和连续扫码未验 |
| 030 查询拍照 | 同024，mode=query；后端匹配最多5条 | 同024；未把查询识别当库存写入 | 同024；查询匹配召回与真实图片未验 |
| 031 查询条码 | 同025，mode=query | 同025 | 同025，实机未验 |
| 032 保存新用户 | `app/routes/user_auth.py:554`管理员/角色 → 参数/唯一用户名/密码强度 → 一次提交 | `test_user_transport_runtime.py`、`test_account_forms_transport_runtime.py`现版替身 | 未发现新问题；未创建账号、设置密码或验证正常登录会话 |
| 034 重置密码 | `user_auth.py:795`管理员/角色 → 禁止重置自己/管理员附加确认 → hash与must_change同事务 | 同032；后端源码核查，不执行真实密码生成 | 未发现新问题；真实账户权限、失败事务与会话失效未新增实测 |
| 037 七日证据 | `app.py:34566`日期/全集 → `ai/ops/acceptance_evidence.py:344,412,501` → 签署重查快照指纹 | 既有44日期/签署旧证据；现版完整七日校验调用链一致 | 未发现新问题；预览可选天数不放宽最终七日门禁。合成日期不能代替连续七自然日观察 |
| 047 修改密码继续 | `user_auth.py:43`本人认证 → 当前密码/确认/强度 → commit/rollback | 同032安全前端替身；不尝试密码登录 | 未发现新问题；真实密码修改与重新登录未验 |

## 已列局部边界

| 边界 | 当前复核 / 旧证据 | 本次结论 |
|---|---|---|
| 008 物料空分类/单位 | round60 Chrome证据，当前物料补齐入口和校验映射 | 仅旧局部通过，不扩大到物料全流程 |
| 022 分享保存停用 | round61 Chrome证据及本轮分享前端组合 | 保存停用通过不等于真实消息送达 |
| 042 合并可选索引 | `app/routes/material.py:939-994`：合并commit后可选索引异常单独捕获；round68结果保留 | 后置索引失败不回滚已提交合并，不把DDL被守卫拒绝当合并失败；本轮不补建索引/合并/删除 |
| 043 盘点其他分支 | `app/routes/check.py`期间变动确认及反提交草稿删除；round65只覆盖已列分支 | 其他差异/草稿分支只静态审查，旧授权不复用 |
| 044 调整原录单 | `app/routes/adjustment.py:234`保存，replace_items路径删除旧明细；round66/67/69原保存/互斥/双worker证据 | 不撤DELETE守卫、不重跑或删除其他明细 |
| 072 调拨原录单 | `app/routes/transfer.py`保存替换旧明细、完成/反提交事务；round64/69证据 | 旧四个跨进程竞争不是本轮新增；原录单替换仍受删除边界约束 |

## 验证与交付边界

- 三类产品候选共3文件，新增3个测试模块共24例。物理切回基线后同组为14 failed / 10 passed，恢复后三文件字节哈希一致；原单组19/31和255组合仅阶段证据，不累加。
- 最终同版安全组合：10模块 **260 passed / 1 deselected**，包含全部24新增和相邻消费点；实际标准库最终日志输出、实际页面函数与实际api.js，HTTP/媒体/凭据由明确替身提供。不是Chrome端到端或真实模型调用。
- 完整排除名：`tests/test_ai_forecast_lifecycle_runtime.py::test_real_isolated_backend_empty_envelope_is_accepted`。该函数明确执行 `wms.db.drop_all(); wms.db.create_all()`；本轮只读RAM/禁DDL守卫不允许其副作用，因此未运行、未计通过，也未修改/删除断言。正常全量CI仍包含该原测试。
- Python子进程守卫拒绝生产路径、范围外SQLite、全部SQLite写入/DDL、外网/DNS、真实密码生成；仅放行已审阅Node路径。Node VM使用测试代码提供的假fetch/DOM，不将其描述为操作系统级网络沙箱。
- 原`full_smoke_test.py`默认8080，包含登录、创建和表单写入，且无只读选项，本轮不调用；本地以页面运行时和模板检查替代，完整服务器/数据库冒烟交正常完整CI运行，不伪称本地全站冒烟通过。
- 本批不新增路由、模型、工具、参数、迁移、AI自动业务权限或生产部署。后端/模板改动生产需重启 WMS 服务生效；本次未重启。
- 发布补记：2026-11-03，产品提交386674e1b7ee72b3a4fa2738c2c7133307001c62及f78ad7982e163c3ad32730cc49f8bfae2562f2b1、最小静态契约纠正提交`5d64242ad9f9dba17b4ca6b77fbcf9c7ab210667`均已实际推送；[WMS CI41583760064](https://github.com/SIX2090/wms/actions/runs/41583760064)和[AI41583760086](https://github.com/SIX2090/wms/actions/runs/41583760086)精确匹配该SHA，完整completed/success。Android41557773962为7d374fc6d989ed3342b7c0aa7af499280a772f1b成功记录，已核实祖先、对象完整及Android源码/工作流无变化。生产未访问、未部署/重启，生产需重启 WMS 服务生效；本收尾文档提交自身CI另行验收。 首次4项静态接线契约失败及最小纠正授权保留于docs/audit/ROUND70_PUBLISH_20261103.md；本代码审查不因此升级为所有按钮、设备或真实模型端到端通过。

本机证据根目录：`C:/wms_backups/code_audit_remaining_20261102_round70/evidence/`；最终组合 `final-combined.log`，三文件反证 `r8-batch-old.log` / `r8-batch-restored-hashes.json`。早期Node守卫识别错误的失败单独保留，不当作产品失败；检索无匹配与命令路径错误也不计测试结果。
