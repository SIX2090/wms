# 物料档案：批量删除未使用档案（2026-11-04）

## 使用方式

在物料档案勾选需要清理的条目，点击“删除”，核对数量和提示后人工确认。系统仅删除未使用、无库存、无业务引用、无图片的档案，其余自动保留。结果窗口显示每一条物料的处理结果和保留原因；有删除成功的条目时，关闭结果窗口刷新原筛选页面。

表头全选仅选择当前页，不会隐式选择其他页或整库；可使用每页条数及筛选缩小范围。库存显示为0不代表从未使用：草稿、历史单据、净额为0的流水、BOM成品编码、仅保存编码的采购申请均会阻止删除。仓库间正负余额相抵仍不允许删除。图片包括图片记录和旧版单图字段，需另行人工处理。

## 本批范围与保护

BUG-2026-11-04-202。复用原 `/material/delete`（权限与CSRF不变），不新增全库清理接口。JSON及原表单ids兼容，严格正整数、去重、最多1000条；不存在ID作为保留结果。业务JS使用WMS.api.post的解包结果，全部保留的原400响应也可显示逐条结果，失败可重试。确认前固定勾选快照，确认及请求期间防重复点击，动态结果以textContent呈现。

独立main副本 `C:/wms_audit/20261104_material_unused_delete`，基线 `b45c9aa5cf2c2b8ee91197f9699ed804c2a5a671`。三个工作流最新main均success；Android旧成功祖先及工程/工作流无变证明齐全。避开C:/wms未提交工作。

引用预检覆盖ORM metadata中所有material_id表及material_code/product_code列，避免遗漏未来同类点；仅物理缺失的ai_material_alias、ai_document_item视为历史可选表，其余缺表/检查异常不执行删除。所有库位记录逐行检查，包含未归属或停用仓库，不用汇总相抵判空；历史孤立总账余额是额外拒删条件，不代替仓库余额校验。无库存/无引用的零库位辅助行随档案一起清除。SQLite BEGIN IMMEDIATE串行化新引用/库存写入，单条savepoint隔离失败，整批commit失败全部回滚；审计只记录实际提交的删除快照。

## 验证

- 原实现专项14失败、7对照通过；后端首轮29通过。
- 物料模块及相邻32模块576通过，6项既有SQLAlchemy弃用警告。随后补旧版主图字段保护，最终受影响专项结果另记，不与重叠组相加。
- 页面处理器及真实api.js的11个JS场景：空/多选、取消、选择变化快照、重复点击、混合/全部保留、网络/503失败、关闭刷新及XSS文本输出。
- SQLite文件库并发：检查期间另一个写入被锁拒绝；删除提交后晚到引用被外键拒绝，不生成孤儿记录。
- 合成触发器模拟第二条删除失败，首尾成功保留且失败项零库位行回滚；模拟最终commit失败，全批档案及审计均不丢失。
- 真实in-app浏览器仅访问5098合成库，CSRF开启：全选4条、取消后再确认，删除2条未使用物料，保留业务引用和库存各1条；关闭后列表刷新为2条。再次全选得到0删除/2保留，关闭后不丢选择。截图 `C:/wms_audit/20261104_material_unused_delete_evidence/batch-result.jpg`。
- full_smoke_test.py经隔离Flask请求桥运行117/117；专用新文件库及合成账号，不连接生产网络，不运行密码修改。

既有勾选打印回归仅按用户新要求把“删除必须单选”契约改为“有选择可删”；编辑/复制/找图仍要求单选，打印和发送打印原有断言保留，并继续运行实际全选/取消全选事件链。

最终代码在全新合成库重启后再次通过真实浏览器混合清理与关闭刷新；旧版单图保护补测后，最终专项（含并发、实际JS、勾选打印、历史删除兼容、审计、台账及A13）65通过，1项既有弃用警告。规则常规/staged、A11全量、裸非GET fetch、UTF-8编码、diff检查及verify_wms_bugs全部通过。模板裸fetch门禁保留既有34处warn，未新增。

推送前同步远端新增 `1db8e60309f2151c028552616679a6e80fdb8e3a` 索引/自动更新超时批次，精确WMS CI41790821414、AI41790821448成功；无物料路由或模板改动，文档冲突逐项保留。合并后，最终专项/台账及两个新增基线模块组合80通过（1项既有弃用警告），隔离冒烟再次117/117；Git逐文件diff证明物料产品代码及其新测试与浏览器冻结版本完全相同。

## 提交推送与CI验收

代码 `b956269a2a8604ee49293f1ec083d645c172ac8c` 实际push输出为 `1db8e603..b956269a main -> main`，本地HEAD和origin/main一致。该次push未跳过钩子；pre-commit规则检查通过。

- [WMS CI41793487745](https://github.com/SIX2090/wms/actions/runs/41793487745)：精确代码SHA，completed/success。三个单元测试分片、四个验证分片、静态检查、冒烟及聚合完整通过；docs分支按代码全量模式跳过。
- [WMS AI Verification41793487656](https://github.com/SIX2090/wms/actions/runs/41793487656)：精确代码SHA，completed/success。
- [Android APK Build41740259322](https://github.com/SIX2090/wms/actions/runs/41740259322)：最新main成功记录，SHA `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba`；git祖先检查与Android工程/工作流全路径diff均退出0，可复用。

验证日志、浏览器截图及合成数据库保留在 `C:/wms_audit/20261104_material_unused_delete_evidence`。测试浏览器页和5098测试服务均已关闭。

生产未部署，生产需重启 WMS 服务生效；本批不执行任何生产物料删除、数据库变更、密码操作或服务重启。

## 生产生效确认（2026-11-04 16:12，Asia/Shanghai）

用户随后明确授权“现在部署并重启 WMS”，本节更新前述未部署快照。现场运行入口仍为 `C:/wms_backups/audit_repair_0634b9d5_20261104/serve_images.py` 及WMS-Warehouse原计划任务；封存后端SHA0634b9d5、现有25项界面覆盖、分类导航修复、主题、图片运行模式、启动只读屏障与自动外部任务暂停保持。

只部署本项：从已验收b956269a提交逐字导出物料路由源码和material_delete服务，固定SHA256；运行适配器从已固定路由源码提取唯一delete_material函数，移除已存在的URL注册装饰器，保留warehouse权限及login_required装饰器，替换既有POST视图绑定。其余路由函数不执行、不替换，CSRF配置不变。对应UI改动应用至现有覆盖模板，其余样式/图标保持。新适配器、两个固定源码、功能清单及启动器/模板均受发布哈希清单校验；X-WMS-Material-Cleanup标识本项完整提交，原X-WMS-Release继续标识封存后端。

证据 `C:/wms_backups/material_cleanup_b956269a_20261104`：

- `lab-result.json`：使用实际封存后端并将测试请求绑定到全新内存库，2删除/2保留、全部保留400、缺CSRF400、销售403、匿名401及成功审计快照通过；原lab-state库摘要完全相同。未对生产或已有lab档案执行删除。
- `production-online-before.db`、`production-stopped-before.db`：两次SQLite在线一致性备份，integrity_check通过；原8项替换/新增文件计划、before/和task-before.xml可用于恢复原界面/处理器及清单，不自动恢复生产数据库。
- `ci-release-approved.json`：组件目标b956269a的完整CI成功。切换前等待同时提交的c48a44f6完成，最新main的WMS CI41796889024、AI41796888999均success，Android祖先/输入无变证明齐全；不部署该无关业务批次。
- `production-preflight.log`：生产启动全程只读，schema检查通过、未启动监听，确认cleanup完整SHA，未执行迁移/初始化。
- `deployment-result.json`：原PID6004退出，新PID2896于16:11:46启动并独占127.0.0.1:8080；原任务动作未改、状态Running。HTTP200、界面版本 `24fb0dc07ebbd6e9-cat20c22ba2-cleanb956269a` 可见。
- `https-result.json`：curl将gd2026.top解析至本机443，HTTPS登录200，功能响应头精确匹配b956269a完整SHA，页面含新界面版本。仅确认本机Nginx HTTPS链路，不扩大为外网可达。
- `database-before.json`、`database-after.json`：逐表行数与行摘要完全相同。未对生产/material/delete执行POST，未删除任何生产物料，未改密码、库存、数据库结构或任务启动动作。

操作员刷新物料档案页面后即可使用；实际勾选和删除确认仍由人工执行。
