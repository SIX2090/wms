# BUG-2026-11-08-015：销售对账库存流水重复累计补修

固定核查基线：`80aa229c0e0a5d93911f6779bebd1e0924812faa`。本项独立于销售 Excel 零税率、备注编辑历史金额及历史数量精度研究；只修已复现的只读上下文重复统计，不修改库存、单据或对账通过条件。

## 已确认的具体问题

`sales_reconciliation_context` 在出库明细循环内，对每行按“出库单 ID＋物料 ID”查询该组合的全部 `out` 流水合计。同一张单同一物料拆成两行时，同一个完整流水合计被重复累加。

新合成内存数据：已完成出库单同物料两行数量为 3 和 2，真实 SQLite 流水各为 -3、-2。完成数量为 5，原上下文 `inventory_qty` 为 10；修复后为 5。不是 SQL JOIN 多行放大，而是 Python 明细循环对相同聚合键重复求和。

影响边界：网页路由消费该上下文，打印 collector 同样携带 `inventory_qty`；现有网页、打印列配置和旧 Excel 导出没有展示这个字段，`ok` 也只比较订单／出库数量及金额，未把此错误扩大为“库存已经被改错”或“用户当前看到了翻倍数量”。旧 Excel 没有同一库存查询，AI 对账使用独立的回调核验函数；不无证修改它们，也不新增库存核验通过规则。

## 最小修复

在每个销售订单的当前循环内，以 `(outbound.id, item.material_id)` 去重，使每个已接受的完成单据／物料组合只汇总一次原流水。保留原查询的 `reference_type='out_order'`、`transaction_type='out'`、来源行校验、完成状态及仓库归属阻断，保留原净额取绝对值语义。不同单据的同物料、同单据的不同物料仍分别计入；不新增抽象或配置，不变更金额算法或两位数量输入规则。

产品变更仅 `app/services/sales_report_print.py`。

## 隔离与验证

仅由固定 Git blob 导出源码到本次新私有目录 `C:\Users\Administrator\AppData\Local\Temp\wms-audit-sales-report-ii74g75k`。不复制运行期目录、数据库、备份、凭据或 `.env`，不修改共享 `C:\wms`、共享索引、历史、版本或公共台账。

新增 `tests/test_sales_inventory_reconciliation_dedup_20261113.py` 解析并扩充现有合成内存 harness 的 AST；不导入真实应用，保留原有禁止文件库、网络、子进程、应用导入的全部保护。保留原19项，新增5项：同料拆行／多流水、双单同料、同单不同料、pending流水排除、跨仓返回未知。原实现 **1失败／23通过**，失败值精确为10≠5；候选 **24方法全部通过**。打印 collector 同样断言5，保证不是只修一个内部函数的调用形式。没有把 subTest 或重跑重复计数。

新增 `tests/test_sales_inventory_reconciliation_runtime_20261113.py` 为真实应用补1个实例：真实模型、真实 GET `/sales/reconciliation`、模板上下文、来源销售行 FK、真实流水及打印 collector，断言 `(shipped_qty, completed_qty, inventory_qty)=(5,5,5)`。测试自身在应用导入前调用 `require_isolated_test_runtime`，fixture 清表之前再次核对唯一内存 engine及 PRAGMA 文件名为空；只能由标准 OS 隔离 CI 运行，不能在 Windows 宿主执行。本机尚未执行该实例，不能把它预填通过。

相邻验证包括现有销售汇总5项、金额舍入4项及 AI 对账20项；与24方法清单不重叠。三账历史精度和历史单头／明细报表差异另列，不因本次只读统计修复视为完成。

整批逆序回退验证、候选字节哈希和实际相邻日志保留于 `C:\Users\Administrator\Documents\Codex\2026-11-09\new-chat\audit_quantity_20261113`。本批没有操作共享 Git；由主任务统一合入、提交／推送，核对精确目标 SHA 的实际 CI，并在本记录补交付结论。尚未有本次 push／CI 的成功结论。

没有连接、读取、复制、备份、恢复或修改生产数据库／生产备份，没有请求现役服务／8080，没有真实账号、单据、打印、微信、部署、重启或迁移。生效确认：待人工确认。


本批统一验收补证：16文件在私有源码Git整批正常逆序回退，2430基线源码文件逐字节恢复；保留候选锁后，旧对账重复统计及旧性能导入副作用按预期失败；恢复后10份明确非空专项91方法通过。编码/严格AI台账/全量棘轮无新增通过（全量存量386，不是零违规）。2个实际应用方法（对账请求/collector及性能HTTP十端点+导出四端点+strict不可比）待目标LinuxCI，当前未计交付。回执 report-perf-r8-proof.json。生效确认：待人工确认。
