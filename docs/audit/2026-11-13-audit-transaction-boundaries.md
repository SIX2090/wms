# BUG-2026-11-08-011／013／017：事务及仓库边界专项补证

本文为本批验收候选。核查固定源码基线为 `80aa229c0e0a5d93911f6779bebd1e0924812faa`；没有把台账保留的历史“未提交／未推送”文字当作当前状态。三个产品修复已在该基线中，本次只补两份测试，未修改产品源码、既定业务或生产配置。

## 当前结论与验收边界

| 条目 | 本批已经证明 | 尚待证明 |
|---|---|---|
| 011 入库删行及日志事务 | 从当前源码提取真实模型类体、删行／别名、日志及采购状态函数，在新内存库验证业务提交失败不出现成功日志、日志插入失败不撤销成功删行、来源数量 7.25→4.05、单据金额 17→5。原有 2＋7 项专项再次通过 | 新增 4 个真实 WMS 请求实例须在本次目标 SHA 的 OS 隔离 CI 实跑；其他数据库驱动故障及间接消费者的全部运行分支不因源代码扫描自动视为穷尽 |
| 013 盘点风险与确认 | 真实模型下同时存在未盘、部分归属及净零动销时风险并列；真实 `_apply_scan_to_batch` 更新盘点行后，旧签名确认凭据失效；扫码阶段不生成调整单或库存流水。原有 28＋2＋12＋4 项后端、合成 Flask、旧契约及前端 Node VM 专项通过 | 新增原生 `/api/stocktake`→重新确认→PC 完成的真实应用链路 1 项待 CI；其他数据库并发仍保守拒绝，未证明其安全可用；完整浏览器点击及设备交互未验收 |
| 017 期初回冲负库存提示 | 真实历史来源模型 10 类全部纳入：入库、出库、售后出库、领料、销售、调整、盘点、委外、期初、调拨；核对调拨正负方向与两仓隔离。真实 SQLite 驱动查询错误在保存点内回滚，保留成功回冲及可继续提交的外层事务。原有 26 项专项通过 | 真实 WMS 请求中的 10 种来源实例及删单／批量删行／全删三个入口的驱动错误 3 项待 CI；其他数据库、连接彻底失效／进程中断和现场历史来源未验收 |

盘点仍只生成 `pending` 调整草稿，不自动影响库存。期初仍保留用户认可的全删、删除回冲和负库存只提示规则，不新增审批，不写回历史归属。代码验收、精确 SHA 的 CI 验收及生产生效分别记录；生效确认：待人工确认。

## 隔离与实际执行方法

本机仅从固定 Git SHA 的 blob 导出 2318 个允许的源码文本文件到新目录 `C:\Users\Administrator\AppData\Local\Temp\wms-audit-011-013-017-kbka1hy4`。不是复制当前工作目录；排除数据库、备份、instance、runtime、上传、日志、构建产物、`.env`、私钥及凭据路径。原工作区、共享索引和历史均未修改，没有创建分支／worktree，没有提交或推送。

Windows 当前未找到可重新核验的 LPAC 监督器，因此**没有在宿主导入 WMS 应用**，也没有拿历史隔离日志、环境标志或伪造证明放行应用。新真实应用测试在任何 `app` 导入之前调用 `require_isolated_test_runtime()`；单独的无证明入口反例确认该入口在 `app` 导入、SQLite 连接及网络操作之前报“安全阻断：未取得真实 LPAC 合成测试身份”。`--noconftest` 不能绕过这份测试自身的前置要求。

本机新模型专项使用 `python -I -S -B -X utf8`，依赖包仅手工加入 purelib、不运行 site／`.pth`；工作进程提前拒绝真实应用导入、SQLite 文件库、网络及进一步子进程，唯一保留的 SQLite creator 只能新建 `:memory:`。每个用例重新建内存表，并核验 `PRAGMA database_list` 的文件名为空。模型 class body 直接来自真实源码，不使用手写替代模型；模块注册事件、路由装饰器、完整应用请求钩子没有执行，不能称为完整应用集成。

整个过程没有连接、读取、复制或修改生产数据库／备份，没有请求现役服务／8080，没有使用真实账号、单据、打印或微信，也没有部署、重启或迁移。真实应用测试仅允许由现有经核验的 Linux OS 隔离 CI 运行，并在 fixture 清表之前再次断言内存 engine URL 及所有 PRAGMA 数据库的文件名为空。合成账号的密码仅用于该新隔离库内的登录链路。

## 90 项本机结果的计数口径

以下为八份**明确非空**专项中 unittest 方法数之和，全部退出 0。循环／subTest 的多种来源、前端场景没有额外折算为多个“BUG”或额外方法，也不把同一专项重跑、回退后重跑再次相加。

| 安全入口 | 实际方法数 | 结果 |
|---|---:|---|
| `tests/test_inbound_item_audit_order_20261108.py` | 2 | 通过 |
| `tests/test_inbound_audit_sqlite_prototype_20261108.py` | 7 | 通过 |
| `tests/verify_inventory_check_confirmation_risks_20261108.py` | 28 | 通过 |
| `tests/test_inventory_confirmation_flask_memory_20261109.py` | 2 | 通过 |
| `tests/verify_check_legacy_contract_20261109.py` | 12 | 通过 |
| `tests/test_check_confirmation_token_runtime_20261109.py` | 4 | 通过 |
| `tests/verify_opening_stock_negative_hint_20261108.py` | 26 | 通过 |
| 新增 `tests/verify_audit_real_models_20261113.py` | 9 | 通过 |
| 合计 | **90** | **全部通过** |

这是纯源码／真实提取模型／合成 Flask／Node VM 的专项计数。它不等于全站 pytest、不等于新增真实应用的 18 个实例，也不等于生产数据或其他数据库已验收。新增真实应用测试通过当前 `tests/conftest.py` 和其自身 OS 隔离检查后，才由 CI 另行报告实际运行结果。

## 真实应用 18 实例的精确清单

候选：`tests/test_audit_transaction_boundaries_20261113.py`。18 是 pytest 参数展开后的预期实例数，**当前尚未运行**。

| 请求／消费点 | 参数实例 | 保留的断言 |
|---|---:|---|
| `POST /in_order/{id}/delete_item/{item_id}` 与别名 `/in_order/{id}/item/{item_id}/delete`，业务提交失败 | 2 | 实际删行 DML 故障注入必须命中；响应 500；明细、来源数量、金额不变；没有成功日志 |
| 同两入口，真实 ORM 日志 insert 故障 | 2 | 故障必须命中；成功响应；已提交删行、来源数量及金额保留；日志未落库 |
| `_opening_stock_negative_hint`＋真实模型来源及仓库汇总 | 10 | 全局 +4、甲仓 -3、乙仓 +7，提示仅属于甲仓；10 类来源与调拨符号归属全部覆盖 |
| `POST /opening_stock/{id}/delete`、`/{id}/lines/delete`、`/opening_stock/delete_all` | 3 | 实际 SQLite 缺表查询异常必须发生在提示保存点内；删除回冲成功、原期初流水清除、查询失败中文提示及会话可继续使用 |
| `POST /api/login`→`/api/stocktake`→`/check/{id}/complete` | 1 | 新扫码使旧确认 token 无效；必须重新提示并确认；只生成 loss 草稿 -2，库存与流水不变 |

在固定 80aa229c 源码中逐项核对了路由 URL／POST 方法、`line_ids`、`confirm`／`confirm_phrase`、`request_id`、`warehouse`／`check_id`／`lines`、`actual_stock`、`force`／`confirmation_token`、登录 `data.token` 与原生 `success` 返回格式；fixture 的真实模型字段／非空字段也已核对。入库删行两入口属于 `document_edit_guard.EDIT_ENDPOINTS`，沿用现有 `document_post` 的真实 GET 页面／版本获取，不伪造 revision 或关闭编辑门禁；盘点完成和期初三个命令按当前契约直接提交。fixture 临时关闭 CSRF 只用于这些事务专项，认证、角色、请求钩子、编辑版本保护、移动幂等及 OS 隔离仍实际运行；这批不是 CSRF 专项。

## 同根因与消费点核查

已对照 BUG-NEW2-005、BUG-2026-08-16-012、BUG-2026-08-30-007、BUG-2026-09-06-001／002／003、BUG-2026-09-16-007。当前 011 两条 URL 委托同一业务实现；017 的有效消费者为删单、批量删行、全删三个入口，废弃单行 URL 只保留历史注释，未恢复它。013 的完成入口唯一，H5 `mobile_scan_submit` 与原生 `native_api_stocktake` 都通过批次锁和 `_apply_scan_to_batch` 归并，不存在单独移动“直接完成盘点并写库存”的新入口。

在固定源码的 `app/**/*.py` 按 AST 函数作用域扫描了 154 个日志调用作用域、173 处 `log_operation`／`log_audit` 调用。词法上“日志之后仍有 commit”的六个作用域为 AI 草稿多分支、扫码作废补日志、入库批删后的采购状态刷新、物料编辑后的图片追加、H5 三种扫码分支、采购申请下推不同分支；核对其日志对应业务均先有自己的成功提交，没有确认另一个与 011 完全相同的直接提前记录点。此扫描不能证明每个间接函数及每个失败分支都已运行，未把没有复现的新风险硬改为产品缺陷。

## 旧红新绿及整批私有源码回退

1. 新版模型专项 9／9 通过。
2. 在同一个私有副本中，仅把 `delete_in_order_item` 和 `_opening_stock_negative_hint` 两个函数的源码替换为历史 `c0d0cb7851fa2e3b96d476054eb86c85ebf0cded` 的对应函数，不回退共享目录或整个过时文件。新版 9 项中 **4 个明确断言失败、5 个通过**：目标删行的真实 DELETE 已经 flush 后才注入业务提交故障，旧版返回 500 并回滚业务，但其提前提交的成功日志仍有 1 条；其余三个反例分别为未知归属没有提示、无法核验没有提示、全局正数掩盖单仓负数。故障不再按“第一次 commit”触发，避免被旧日志自己的 commit 提前消费；断言仍严格要求成功日志为 0。
3. 恢复固定基线两个产品文件精确字节，新版模型专项再次 9／9 通过。
4. 本批新增两份测试和本文。按写入逆序先移除报告、再移除真实应用测试、最后移除真实模型专项，核对原始 manifest 的 **2318 个源码 blob 全部 SHA256 精确相同**；原入库相邻 7 项仍通过。
5. 按原字节恢复三份候选，核对候选 SHA256 一致，新模型专项再为 9／9 通过。该过程为整批新增文件的私有源码字节回退，没有操作共享 Git，也不是已修复产品代码整批撤销。

这里的旧码对照用于既有缺陷的回归锁；本批没有新增产品修复，不宣称又修了三个 BUG。011／013／017 的新增完整应用边界仍以目标 CI 的实际执行为准。

## 证据、候选哈希及待合并项

冻结测试 SHA256：

- `tests/verify_audit_real_models_20261113.py`：`74c5bbc9ff3795dc9d0b84d5561240b68f0b0a3b863b9ed9ddede92c132d2b6f`
- `tests/test_audit_transaction_boundaries_20261113.py`：`12b60e9e6b46da4942fddf77575d0836ad0cf87aada5d770219f87761f0a24cd`

本机原始证据目录：`C:\Users\Administrator\Documents\Codex\2026-11-09\new-chat\audit_validation_20261113`。`export-receipt.json`、`adjacent-results.json`、八份独立日志、`consumer-scan.json`、`controls-and-rollback.json`、`legacy-product-controls.log`、`restored-model-boundaries.log`、`candidate-entry-guard.log` 保留实际结果及路径。普通 `lint_wms_rules.py --verbose` A1–A14 0 违规，不冒称已完成 `--full --full-gate`。

由主任务统一合入、维护台账和版本、提交／推送，核对新增 18 个真实应用实例在精确新 SHA 上实际执行、没有跳过，再补充 CI 证据与最终结论。本报告阶段没有该新 SHA，没有 push 输出或新目标 CI 结果。其他数据库、连接彻底失效、完整浏览器／设备及生产生效继续单列，不能因时间流逝或通用 CI 绿色自动视为通过。


集成批本机验收补证（2026-11-13）：本批 14 文件在私有源码 Git 整批正常逆序回退，2418 个基线源码文件逐字节核对；保留候选回归锁后，旧版销售金额与缺失安全诊断入口按预期失败；精确恢复后 18 个非空专项共 147 方法通过。纯源码编码与严格 AI 台账通过，全量棘轮无新增违规（存量 386，不是零违规）。本机不运行 WMS；新增实际应用 8 个金额实例、18 个事务/盘点/期初实例、1 个诊断子进程方法（1/25 行）等待目标隔离 CI。回执位于本聊天 parallel-audit-r8-proof.json；提交、推送及目标 CI 后续补证，生产生效待人工确认。


精确代码交付补证：`1faf24363c7ce7d3221eeed4c2bd6ce80f13e052` 已正常非强制推送 `80aa229c..1faf2436 main -> main`；[WMS CI 43408794476](https://github.com/SIX2090/wms/actions/runs/43408794476)、[AI 43408794508](https://github.com/SIX2090/wms/actions/runs/43408794508) 和性能 43408794456 均 completed/success。Android 复用成功祖先8cba9986的43399657746，祖先及两个构建输入零差异已核对。三个真实单元分片4833/4843/5095 passed，39/29/134 skipped，362/123/723 subtests passed，合计14771 passed、202 skipped、1208 subtests passed；新增8个历史金额、18个事务/盘点/期初实例及诊断子进程1方法在Linux隔离CI通过，新增实际用例没有skip/xfail。代码验收仅覆盖所述边界；其他数据库、设备和未恢复诊断继续单列，Windows发行另查，不冒充生产生效。生效确认：待人工确认。
