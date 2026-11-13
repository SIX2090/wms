# BUG-2026-11-13-004：物料初始库存与期初行来源 ID 碰撞

本项是独立来源身份根因，不混入 BUG-2026-11-08-015 的数量逆向剩余项。基线为 `80aa229c0e0a5d93911f6779bebd1e0924812faa`，依赖已经批准的物料数量规范候选 `material.py` SHA256 `f7e36d791ff58cf9c33e6f59ea1e0b48be9e1dc0f2dda06ca64dca4d4934b928`；本次增量保留这次规范，不用旧整文件覆盖它。

## 已复现的原始错误

新增物料带初始库存通过 `apply_opening_balance` 默认写 `reference_type='opening_stock'`、`reference_id=material.id`；真正期初明细通过同一默认类型写 `reference_id=OpeningStock.id`。这两个数字来自不同表，碰号合法。

真实模型类体及真实业务函数的新合成内存反例中，物料 ID 与期初行 ID 均为1、同物料同仓：先物料初始5，再期初7，原总账与流水均12。旧 `_reverse_opening_stock_line` 仅按旧类型／数字ID整组删除，回冲7后总账5而流水0，误删初始库存5。10方法中原9项仍通过，该严格库存断言失败；没有访问实际业务数据。

## 最小产品修改

1. 新增物料的来源显式改成 `material_initial`，仍用原 `reference_id=material.id`，不增加schema、不迁移、不改真正期初的 `opening_stock` 类型；此前两位数量规范继续使用同一值写三账。
2. `_opening_stock_line_transaction_ids(line)` 在调用方事务中重读锁定当前行和源流水，只选旧 `opening_stock` 类型＋该行ID＋该行物料ID的准确流水ID。实际删除只针对返回的明确ID，不能把其他物料的同数字来源一起删掉。
3. 对旧 `reference_id==material_id` 且存在固定文字“新增物料初始库存”的组合一律保守拒绝，caller既有错误路径整体rollback。不根据备注、数量子集、相同操作者／时间或 best-effort `OperationAudit` 猜归属；审计没有绑定具体库存流水ID，因此相似成功日志不是允许删除的证据。
4. 新来源增加中文类型／编号说明，保留无错误期初链接；历史可能初始的旧marker不借用期初仓库、单据日期或链接。期初来源映射也检查物料ID，防异物料碰号被错误关联。无可证明仓库仍保持未知，不按默认仓补写。

没有新增 `opening_stock_line` 身份域。原因是旧代码的回冲／清理只识别原期初类型，新期初域会扩大代码回退兼容风险。

## 消费点完整核对表

| 消费点 | 当前处理 |
|---|---|
| `routes/material.py::add_material` | 唯一新物料初始来源生产者，显式 `material_initial`，数量规范保留 |
| `app.py::_apply_opening_stock_balance` | 真正期初来源生产者，类型与编号保持 |
| `apply_opening_balance` | 默认 `opening_stock` 保持；不放宽数量精度或服务语义 |
| `_reverse_opening_stock_line` | 新结构性来源检查及精确ID删除，库存数量算法不在此批改 |
| 三个显式删除URL | 删单、勾选删行、全部删除共用该核心 |
| 两个保存URL的移除行分支 | `/opening_stock/save`、`/opening_stock/batch_save` 同样共用核心；不能只统计三个按钮入口 |
| `cleanup_dangling_opening_stock_transactions` | 原SQL保守排除旧marker，新 `material_initial` 完全不在其删除类型范围；不新增启动数据库操作 |
| `REFERENCE_TYPE_LABELS` | 新来源显示“物料初始库存” |
| `_ledger_source_warehouse_map` | 历史可能初始不猜期初仓；异物料ID不匹配；新来源沿用已存warehouse_id/location，未知不猜 |
| `_ledger_document_date_map` | 不将旧可能初始的创建日错误替换成碰号期初单日期；新物料来源回退自身流水创建日 |
| `_report_reference_info`／台账collector | 新物料来源给明确中文说明且不伪造期初链接；旧不明来源标待核对 |
| H5／原生台账、报表／打印导出 | 复用上述后端row builder／标签；原生明细原样返回机器字段，不新增Android代码 |
| 原始物料初始化verifier | 两处旧类型断言同步为新明确契约，数量、物料、原子性等断言保留；真正期初的旧类型断言不改 |

## 事务和并发边界

现有 `_acquire_order_write_lock`／编辑锁在SQLite会先rollback，不能在已经回冲第一行的批量事务中复用。命名空间锁另有业务域用途，不用它做无关仓库DML。

新helper仅在实际DBAPI SQLite `in_transaction` 为false时显式 `BEGIN IMMEDIATE`；已有批量写事务不重开、不rollback、不commit。锁后 `refresh(...with_for_update=True)` 重读当前期初行并比较原观察快照；源流水使用 `populate_existing`＋行锁，避免ORM identity map保留旧备注而误放行。若行已变化则拒绝，由caller统一rollback。

真实共享内存双连接反例已证明：单纯分类、尚未改业务DML时，另一连接对同组源流水的插入已被SQLite写锁阻止；caller rollback后第二连接才可写。批量第二行来源不明不会提交或撤回第一行，caller整体rollback恢复两行；两条正常行没有隐藏commit。这是SQLite证据；其他数据库的实际写入者锁竞争没有实跑，不因出现 `with_for_update` 文字宣称已验收。

## 本地证据与待CI实例

本机没有可重验的LPAC监督器，因此没有在宿主导入WMS应用。所有执行均为显式清单、真实源码提取／真实模型类体及新合成SQLite内存库，先禁应用导入、文件库、网络及后续子进程；共享内存连接使用本次UUID的 `mode=memory` URI，不接触任何文件数据库。

- 新来源专项30方法：原9项＋新增21项。覆盖同ID／异物料、source身份、固定文字复用、相似／重复／缺失／伪装审计全部拒绝、旧日期／仓库错误关联、ORM缓存重读、真实SQLite双连接锁、批量回滚、无隐藏commit及新来源保留于旧cleanup SQL。
- 数量规范及期初相邻40方法：原26项＋已批准新增物料14项，确保来源改动没有撤掉数量修复。与30方法的原9项是不同清单；不再把单跑的26或9重复相加。
- `INVENTORY_TRUTH` 当前符号和引用共22断言通过；此基线中backfill定义由30442移至30487，主任务合并其他app增量后还必须按最终实际源码重新生成行号。
- 新增 `test_opening_reference_ownership_runtime_20261113.py` 为21个预期真实应用实例，**尚未在本机执行**：五入口分别在库位开／关验证新源成功保留与旧歧义整体回滚，共20；另1例明确记录特殊旧marker兼容限制。fixture只用真实新内存库、合成账号／库存，测试本身在app导入前核验OS隔离，须精确目标CI实际执行。

旧红新绿组件对照只覆盖历史真实回冲／读取函数和旧物料来源生产参数，保留测试新helper以避免“旧版缺函数”被冒充红测。整批逆序回退包含所有本批文件，恢复固定Git源码＋明确批准的三个依赖原字节，再跑原9／26方法；恢复后再跑30／40。实际日志、失败方法、完整字节哈希和增量patch见 `C:\Users\Administrator\Documents\Codex\2026-11-09\new-chat\opening_sources_20261113` 的回执。

## 代码回退与兼容限制

新 `material_initial` 流水即使由旧版 `_reverse_opening_stock_line` 或旧cleanup执行，类型条件也不会命中；专项实际执行旧cleanup的未变SQL，确认新初始5仍在。旧版本可能把这个新类型显示为原始机器字段；只读标签降级不等于新增业务操作或数据迁移。

旧同ID／固定marker的记录不能自动消除歧义，可能出现“此前允许删、现在明确拒绝”的兼容限制；极端的新期初行恰好使用该文字且同ID时也可能拒绝。**不声称所有历史单据已能自动删除。** 普通新期初备注不受此歧义保护影响；保留期初全删、回冲、负库存提示及不新增审批的既定规则。历史数量1.005等精度逆向仍属于015，当前数量算法没有被悄悄放宽。

没有读取／复制／备份／恢复／修改生产数据库或备份，没有现役服务／8080请求，没有真实账号／单据、微信、打印、部署、重启或迁移。此处为候选证据，提交／推送、精确目标CI及生产生效分别由主任务补证；生效确认：待人工确认。
