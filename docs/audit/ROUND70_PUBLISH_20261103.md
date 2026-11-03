# round70修复发布核验（2026-11-03）

独立main副本，生产目录/库/服务未操作；当前只提交推送，不部署。原本地252834e及d676345经正常rebase保留同一改动为386674e1b7ee72b3a4fa2738c2c7133307001c62和f78ad7982e163c3ad32730cc49f8bfae2562f2b1，基线7d374fc6d989ed3342b7c0aa7af499280a772f1b。实际push输出`7d374fc..f78ad79 main -> main`，未force或跳钩子，推送前精确基线三工作流全绿。

范围为BUG-2026-11-02-013/014/015日志最终异常脱敏、供应商HTTP/数据/活动请求、令牌防重，以及016强禁用启动维护控制。9个既有真实子进程兼容测试明确改用仅跳升级模式，原断言谓词全部不变；强禁用有独立20例正反控制（后加9例模式契约）。本地针对与文档90 passed；导出夹具41纯替身及原合成库24份GET/XLSX/表头/数据通过，其中3主数据、21空数据，不是全系统按钮验收。真实导出证据在C:/wms_backups/code_audit_remaining_20261102_round70/evidence/export-once-03/RESULT.md。

## 首次精确CI结果与最小纠正

[WMS AI41571003979](https://github.com/SIX2090/wms/actions/runs/41571003979)和性能41571003939成功；[WMS CI41571003940](https://github.com/SIX2090/wms/actions/runs/41571003940)失败，仅4项旧静态接线契约查找直接调用字符串，实际代码已改集中派发。服务器冒烟、全部四组业务验证脚本、静态/规则/三账/安全检查均成功；三个unit分片分别因这些旧静态契约失败，不能把整体当通过。

- test_cleanup_dangling_opening_stock_transactions::test_startup_wiring_and_delete_semantics_static：直接调用字符串index定位失败。
- test_ensure_stock_transaction_warehouse_id_column::TestStartupWiring::test_module_level_call_after_print_job：直接调用find=-1。
- test_fix_inventory_check_columns::test_ddl_matches_app_py_ensure_function：末尾直接调用字符串断言失败，DDL一致性循环保留。
- test_ensure_opening_stock_doc_table::test_migration_and_ensure_share_same_helpers：直接调用index定位失败，共享DDL/回填唯一性和顺序断言保留。

最小纠正仅4项测试定位、纯AST接线工具及6个反证/控制，未改业务代码或SQL。改为读取真实模块级`_run_startup_db_maintenance(callback)`并校验顺序；注释、字符串、函数定义内调用、未受控直接调用均不能冒充接线，重复和未知调用形式拒绝。并未删除/放宽原DDL、物理删除边界、单实现或顺序断言。

4个静态测试体在不导入app/DB fixture情况下提取执行，盘点DDL常量静态读取原脚本：修前0/4、修后4/4；新增AST反证/控制6例及相关/文档组合96 passed。完整4个原模块含DB/账号/清理fixture未在本地另行运行，须由纠正后完整CI验证，不拿静态提取冒充模块全量。

当前最小纠正只形成可审本地提交；因远端CI实际非绿，纠正推送需要本次具体门禁例外批准，不能借用过去一次许可。尚未使用WMS_SKIP_CI_GATE，不把已有失败视为绿。批准后仍保留正常提交钩子，必须核新精确SHA完整CI。生产需重启WMS服务生效，但本轮未部署/重启。
