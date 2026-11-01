# 固定29项安全软件检查（2026-11-01）

29项均完成本轮授权内的源码、隔离HTTP或页面运行时检查，未检查项为0；不代表29项真实端到端通过。真实验收条件逐项保留。禁止生产测试；不启用真实设备、外部发送、付费模型或真实凭据操作。

HTTP只用Flask test_client和每例全新StaticPool内存SQLite，不启动对外服务；源码为C:/wms_backups/known_issues_20261101_round30/source，临时文件只在其runtime目录。Python审计钩子拒绝网络及范围外SQLite，Node页面脚本注入模拟DOM/媒体/网络。isolation-proof-final.log已验证实际engine、源码路径及拦截效果；不读取生产.env、数据库或接口，不操作PID11112。

新增确认BUG-2026-11-01-023：打印调用失败且回传断网时，旧afterprint/超时回调能重新开放出纸确认；隔离修复清除旧监听和定时器，保留失败重试。旧码1失败/2对照通过，修后与原打印回归共9通过，物理回退反证及字节恢复已留证。该打印相关检查不新增到原29按钮分母。BUG-022的dca29b2e与BUG-023的ffb1c0b9已随下述产品目标推送并通过完整CI；生产均未部署。

最新分组：外部服务本地协议/页面124通过，硬件模拟/打印全模块/凭据拒绝66通过，账号与工作站页面38通过，库存精确边界4通过；另008重开1、022重开1通过。组内为测试实例数，含既有用例复验，不计作新增按钮。旧码反证及夹具修正中间日志保留，不能把它们算产品新缺陷。

| 编号/入口 | 已验证的软件层（均通过） | 测试/证据 | 尚未验证的真实条件 |
|---|---|---|---|
| BTN-PENDING-003 系统设置／测试文字连接 | 参数页实际事件：请求字段、HTTP/业务/登录/网络异常恢复；后端路由只读审查 | test_system_settings_transport_runtime.py；safe29-external-local.log | 指定测试模型、接口、费用与真实连接；本轮无外发 |
| BTN-PENDING-004 系统设置／测试图片识别 | 图片测试事件；供应商异常、错误JSON及原始错误不回显的HTTP替身 | test_system_settings_transport_runtime.py + test_round26_risks_http.py；safe29-external-local.log | 真实视觉模型与指定合成图片、费用 |
| BTN-PENDING-006 物料／网上找图（工具栏） | 工具栏与行内共用搜索生命周期；网络失败、空结果和搜索引擎回退替身 | test_material_image_search_lifecycle_runtime.py + test_material_image_search.py；safe29-external-local.log | 实际搜索服务连通与真实候选图片 |
| BTN-PENDING-007 物料／网上找图（行内） | 行内入口复用同一搜索实现；迟到结果、切换目标与失败恢复 | test_material_image_search_lifecycle_runtime.py；safe29-external-local.log | 实际搜索服务与目标物料；未下载真实外部图片 |
| BTN-PENDING-008 物料／修复空分类和单位 | 空字段修复后新HTTP会话读取；完整记录、双仓库存及流水不变 | test_round30_empty_fields_reopen.py；empty-fields-reopen-new.log | 浏览器原生确认与真实页面交互，未由HTTP替代 |
| BTN-PENDING-009 打印路由／创建工作站 | 工作站新增表单、令牌回显替身；真实HTTP鉴权/CSRF/空参数拒绝，阻断生成器 | test_page_feedback_runtime.py + test_round30_credential_guards.py；safe29-credential-dom.log + credential-guards.log | 具体隔离工作站与实际专用凭据创建授权 |
| BTN-PENDING-012 打印路由／重置令牌 | 令牌重置取消、替身回显；真实HTTP权限/CSRF/不存在目标拒绝，无令牌生成 | test_page_feedback_runtime.py + test_round30_credential_guards.py；safe29-credential-dom.log + credential-guards.log | 具体隔离工作站、凭据失效影响和重置授权 |
| BTN-PENDING-017 单据OCR／开始识别 | OCR实际页面监听器：选择、清除、替换图片、读取失败、迟到响应及业务失败 | test_bug_2026_10_31_audit_followup.py::test_followup_frontend_runtime；safe29-external-local.log | 真实OCR供应商、测试图片及费用范围 |
| BTN-PENDING-018 供应商智能评估／生成评估报告 | 本地合成已完成入库数据聚合、复用价格查询与模型分析替身；低置信度提示源码 | test_round26_risks_http.py + test_ai_supplier_eval_hint.py；safe29-external-local.log | 真实模型质量/服务异常与指定费用；不发生产数据 |
| BTN-PENDING-019 需求预测／生成预测 | 真实合成读取与页面生命周期：期限、分类、网络、畸形响应、重复请求和迟到结果 | test_ai_forecast_lifecycle_runtime.py；safe29-external-local.log | 真实模型服务与预测有效性，非凭软件回归证明准确率 |
| BTN-PENDING-021 微信分享／立即分享今日入库单 | 立即发送普通确认/取消与HTTP异常替身；总开关关闭与pending重复请求阻止投递 | test_wechat_share_transport_runtime.py + test_round26_risks_http.py；safe29-external-local.log | 具体隔离接收人、助手、发送任务与专项外发授权 |
| BTN-PENDING-022 微信分享／保存设置 | 总开关关闭时保存并以新HTTP会话重开；真实CSRF，禁止构图/发送 | test_round30_share_settings_reopen.py；share-settings-reopen-new.log | 实际浏览器确认/布局；不需要打开生产发送开关 |
| BTN-PENDING-023 微信分享／重新生成并再次发送今日入库单 | force重复发送确认、取消、失败恢复和请求字段替身；关闭总开关仍拒绝force | test_wechat_share_transport_runtime.py + test_round26_risks_http.py；safe29-external-local.log | 明确新发送任务、具体接收人及重复投递后果授权 |
| BTN-PENDING-024 手机 in／拍照识物 | in实际HTTP页面核对拍照/条码按钮和共用处理器；图片超时/断网/业务错误/新请求取代旧请求 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-025 手机 in／条码扫描 | in实际HTTP页面核对拍照/条码按钮和共用处理器；无相机/占用/初始化与打开异常/断连/重复与迟到回调/取消/pagehide/轨道释放 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-026 手机 out／拍照识物 | out实际HTTP页面核对拍照/条码按钮和共用处理器；图片超时/断网/业务错误/新请求取代旧请求 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-027 手机 out／条码扫描 | out实际HTTP页面核对拍照/条码按钮和共用处理器；无相机/占用/初始化与打开异常/断连/重复与迟到回调/取消/pagehide/轨道释放 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-028 手机 check／拍照识物 | check实际HTTP页面核对拍照/条码按钮和共用处理器；图片超时/断网/业务错误/新请求取代旧请求 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-029 手机 check／条码扫描 | check实际HTTP页面核对拍照/条码按钮和共用处理器；无相机/占用/初始化与打开异常/断连/重复与迟到回调/取消/pagehide/轨道释放 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-030 手机 query／拍照识物 | query实际HTTP页面核对拍照/条码按钮和共用处理器；图片超时/断网/业务错误/新请求取代旧请求 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-031 手机 query／条码扫描 | query实际HTTP页面核对拍照/条码按钮和共用处理器；无相机/占用/初始化与打开异常/断连/重复与迟到回调/取消/pagehide/轨道释放 | test_round30_device_failure_runtime.py；hardware-render-and-print.log | 真实手机权限、相机画面/解码、浏览器差异与触摸操作；未启用硬件 |
| BTN-PENDING-032 用户管理／保存新用户 | 新用户表单成功/失败/重复提交/CSRF/登录过期替身；后端权限与空参数拒绝 | test_user_transport_runtime.py + test_round30_credential_guards.py；safe29-credential-dom.log + credential-guards.log | 具体隔离账号与密码创建专项授权；本轮不创建可登录凭据 |
| BTN-PENDING-034 用户管理／确认重置密码 | 重置表单字段、失败重试和防重；后端鉴权与校验拒绝，哈希生成器被禁止 | test_user_transport_runtime.py + test_round30_credential_guards.py；safe29-credential-dom.log + credential-guards.log | 指定隔离目标账号和实际重置专项授权 |
| BTN-PENDING-037 AI七日验收／构建最近七日证据 | 合成证据的缺日、非零违规、缺回退、快照变更不能签go；时间窗口源码复核 | test_bug_2026_10_31_audit_acceptance.py；safe29-external-local.log | 连续七个真实自然日的观察记录；合成日期不充作真实七日 |
| BTN-PENDING-042 物料／确认合并 | 16个HTTP确认凭证/权限/锁场景及3个实际JS交互锁；执行端无变更哨兵 | test_material_merge_consent.py + test_material_merge_receipt_js.py；merge-complete-related.log + merge-preview-r8.json | 确切可永久合并的隔离源/保留对象与当次确认；真实并发仍待验 |
| BTN-PENDING-043 盘点详情／仍要完成 | 精确RAM样本A13/B20；期间变动确认后完成盘点，只生成+2未提交调整草稿 | test_round30_inventory_bounded.py::test_043_period_movement_force_only_creates_plus_two_draft；bounded-status-final.log | 浏览器仍要完成；调整草稿的实际过账未由此例验证 |
| BTN-PENDING-044 调整详情／保存并完成 | 新草稿保存/完成/反提交状态pending→completed→pending；A10→12→10/B20，流水对称；旧明细重建用禁止删除替身 | test_round30_inventory_bounded.py；bounded-status-final.log | 浏览器保存并完成组合操作；确切非空明细删除目标授权，未实际删除旧明细 |
| BTN-PENDING-047 修改密码页／修改密码并继续 | 本人修改密码表单成功/失败/导航防重替身；HTTP鉴权/CSRF与错误当前密码拒绝 | test_account_forms_transport_runtime.py + test_round30_credential_guards.py；safe29-credential-dom.log + credential-guards.log | 具体隔离账号与真实改密专项授权；不验证正常密码登录 |
| BTN-PENDING-072 库存调拨／反提交 | 新RAM一致的已完成调拨样本3件；反提交A7/B23→10/20，状态pending、明细保留 | test_round30_inventory_bounded.py::test_072_reverse_exact_three_transfer_restores_both_warehouses；bounded-status-final.log | 实际浏览器原生确认；此例没有重测调拨从新增到完成全链路 |

044新草稿保存路径的DELETE匹配0行；带已有明细的重建请求在删除前由明确替身抛错，原明细/库存/流水保持不变。该受控失败不是产品缺陷，也不证明真实删除通过。043盘点完成只生成草稿，未提交差异；072从一致的合成已完成检查点验证反提交，未冒充整个调拨流程。

人工确认授权只用于已授权、非生产且可恢复范围；工具不支持原生弹窗的分支保留未验，不绕过工具/URL拒绝。真实设备、实际接收人、模型费用、真实账号凭据、永久合并/删除及七日观察均不能用替身关闭。

证据根：C:/wms_backups/known_issues_20261101_round30/evidence；逐项机器清单safe29-matrix.json。旧BUG-2026-10-21-001凭据迁移/轮换仍未处理，本轮不读取或变更真实凭据。

## GitHub交付验收

2026-11-01正常钩子推送三笔本地提交dca29b2e、ffb1c0b9、3b9be6cd，实际输出d7a8f2b1..3b9be6cd main→main；精确产品目标`3b9be6cd84afc5f20e5b4fffa14c88ccb352b794`的[WMS CI](https://github.com/SIX2090/wms/actions/runs/41296286463)、[AI验证](https://github.com/SIX2090/wms/actions/runs/41296286338)及[性能基线](https://github.com/SIX2090/wms/actions/runs/41296286440)均success。三个单测分片、四个专项分片、隔离冒烟及静态检查完整执行通过；docs-checks因本次选择full分支正常跳过，gate成功。Android41245230422成功祖先、完整对象及源码/工作流无差异证明通过。

整批回退在另一个仅含公开Git文件的隔离副本完成：四个产品文件全部回退到d7a8f2b1，保留22个新锁，17 failed/5权限与失败对照passed；全部字节恢复后22 passed。证据whole-batch-r8.json。没有在共享待验工作目录回退文件，不更改断言，不重复提交既有成果。微信历史清理2d029b59及文档d7a8f2b1已在本批远端基线，属于先前交付，未混报为本批新功能。后续仅回填文档验收记录，不改业务代码；本次推送不触发生产部署。
