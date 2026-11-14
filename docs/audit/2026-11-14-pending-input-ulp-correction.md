# pending候选的等值与数值输入纠正

这是对未集成冻结候选 `360e14d0581e9f5acf20e24f482372eb06603231a0c144368ff9118b90752f4f` 的最小增量纠正，不新增独立BUG计数，不声称生产发生过异常。原冻结9文件目录保持不变。

验证基线另明确纳入根任务当前 `cf253742b44268c33949de3242cbf77f0d3e7c31` 的 `update_completed_in_order` 函数和source/runtime188测试；该函数AST已逐一证明与cf一致。最终补丁只改pending函数，不包含或回退completed函数及其188测试。

## 独立评审复现与纠正

* 已存quantity为1.01的上下一个Float，回显提交1.01且只改备注时，原候选exact `!=` 判为变更，重算7.77行金额与0/9.99历史头额；若counter为历史1.005还会误拒绝。单价同类ULP也应保原值。
* quantity或price为`not-a-number`时，原候选裸float可能抛异常而未返回业务400；price解析发生在counter写入后。这里只描述实际handler／新内存模型证据，没有把它宣称为正常受保护HTTP的生产500或持久化泄漏。有效revision的外层finally rollback、正常teardown仍保留。

只改 `update_in_order_item`：先完整解析数量/单价并验证有限性、规范与金额计算，再执行任何来源counter写入。复用现有 `_recorded_quantity_matches`（8 ULP且最多1e-9），等值保原quantity/price；规范后等值也不重写counter。只有实际量价变化才写新amount并汇总头额，真实价格3.5改0仍正常生效，不把0当缺失值。

非法文本、NaN/Inf、规范后为0的数量、有限数值规范溢出，均在写counter之前返回业务400。没有放宽输入精度、比较容差、超收开关或预留来源证明；没有修改其他controller、schema或库存服务。

## 验证与交付边界

新source60方法覆盖数量±ULP及精确对照、单价±ULP、counter1.005、头额0/9.99、规范后等值、真实改价0/真实改量2，以及非法文本/NaN/Inf/有限溢出和数量0/负数既有拒绝。对旧handler抛错，测试明确记为行为断言失败，不伪造HTTP400。

新runtime60实例复用已独立审阅的真实 `_http_call`、模型/设置命名空间和memory隔离fixture；只共享测试夹具/断言，排除源版pending_call。先验证真实runtime proof再导app，每例必须恰发真实业务POST `/in_order/item/update`，使用document_post真实页面revision。实际HTTP仅交现有Linux隔离CI，不在宿主import/collect/执行，不伪造证明。

本地source60、reservation110、cf当前completed188、global137及静态规则结果分别记录在伴随proof；这些有共享基线，不相加当唯一BUG数。完成整批私有源码逆序回退及Git真实patch应用/哈希验证后才交主任务；完整HTTP和精确目标CI仍待其实际证据。

只在全新私有文本源码副本及新建合成内存库操作，不接触生产数据库、备份、真实账号、现役服务或默认端口，不部署或迁移。生效确认：待人工确认。

## 本纠正实际验收补证（2026-11-14）

已经随38b5440c215e74a8fdc8d6c34639b5e94efd21ae正常推送。该目标WMS43537505932、AI43537505750、性能43537505728 completed/success，新增60实际HTTP与原reservation110全部运行通过，共16101 passed/203 skipped/1561 subtests passed；仅测试改名绑定及缺失真实上下文补齐，没有削弱原断言或调宽容差。最终18文件R8恢复2508源码基线后恢复候选15组再次通过；本纠正旧38断言失败、0初始化错误。前文待验是历史阶段；其他数据库、设备和生产生效仍待各自确认。生效确认：待人工确认。
