# 原生审计修复第一批：仓库查询边界与默认仓协议

2026-11-15，任务 `AI-APP-AUDIT-FIX-20261115-001`。本批仅交付 A07（BUG-2026-11-15-015）及 A11 的服务端协议部分（BUG-2026-11-15-019）。其余 Android 修复继续在后续批次验证，不能把本批推送当成12类全部完成。

- `app.py` 的 `material_search_api`、`material_info_api`：显式传入无法唯一解析或已停用仓库时受控返回400，不能把校验错误忽略后返回全局库存；未传warehouse的元数据查询沿用现有协议。保留函数原始行数，未改变通用按行提取器的锚点。
- `native_api_warehouses`：仍仅返回启用仓库，新增明确的bool `is_default`；本批不发布依赖新协议的Android页面。
- `tests/test_native_material_warehouse_audit_20261115.py`：实际源码函数提取执行6项全通过；相同6项对原实现有3个明确业务断言失败、3项对照通过，没有夹具错误。真实应用用例覆盖无效/停用/歧义、多仓库存、无warehouse兼容及默认仓停用。歧义夹具通过合成内存库bulk update模拟历史脏别名，不把正常ORM命名闸门当产品失败。
- 本机仅运行不导入完整app的函数契约；真实Flask应用用例使用既有money_case，在导入前核验拥有者、两个内存库URI，导入后核验engine及PRAGMA无文件库。完整模块和全站回归交本批精确目标CI的隔离环境，不绕过LPAC或数据库保护。
- 本批产品包含在已完成的43文件私有反向应用/恢复哈希验证中；第一批独立提交前再核对本批完整差异和回退哈希。Windows发行输入纠正递增2026.11.74，Android输入保持52/3.9.28，Android工作流若因路径过滤不产生运行，必须证明成功祖先及工程/workflow输入无变化后复用。

本地证据：本任务审计目录同级 `native-wms-fix/backend-independent-current.log`、`backend-independent-old.log`。提交范围、实际推送完整SHA、远端可达性与CI链接在推送回执补充；未验收不算交付。

未读取或修改生产数据库，未登录生产服务、操作真实单据/账号、发送微信或打印、部署、重启或安装APK。服务端现网生效仍需用户另行授权部署到已验收干净版本；Android客户端修复及真机确认另批。

## 首批CI失败与R8纠正（2026-11-15）

首批 `829aeaa8f91d63d7902a4c913a34a629099cc378` 已实际push，但目标 [WMS CI 43709268235](https://github.com/SIX2090/wms/actions/runs/43709268235) 发现旧004 T5仍要求无效仓库回退全局，及统一台账索引/档案分类登记遗漏，不能交付。按R8用本地提交 `ec036f141d8cf6941589bba177614fcc24ca547f` 整批回退11文件，完整Git树精确等于原84fac390，未撤销或覆盖其他任务工作内容。

重新评估后同时补齐确认同根因：H5 `/mobile/api/material_lookup` 不再忽略仓库校验错误。38个消费点按函数名、路由、模块路径和通用TARGETS核查；仅002 T7和004 T5旧协议需纠正，两套历史T1-T6/T1-T4合计10项合法多仓/无仓/全局断言AST保持完全相同。`api_material_payload` / `mobile_material_payload` 实际调用只传已校验仓库对象或None，保留无仓元数据协议，不盲改为抛异常。

纠正后实际源码契约9/9通过；精确84fac旧Git源码4个业务断言失败、5对照通过，0初始化错误。历史T5/T7实际函数体执行当前4/4通过、旧源码3失败+1既有受控拒绝对照通过。新真实应用invalid矩阵扩大为4接口×missing/disabled/ambiguous，仍只在已证明隔离的目标CI执行。统一索引按脚本重建，档案新增登记不更改历史状态分布基线，也不代表软件/CI/生产已验收。

纠正提交/推送和完整目标CI另行验收，原失败目标不作为成功证据。原始证据见本任务 `backend-*-corrected-*.log`、`backend-r6-corrected-evidence.json`。Android其余修复未纳入本批。
