# 单据现存编号选择修复（2026-11-09，未交付）

关联 BUG-2026-11-08-018、BUG-2026-08-16-020 和 BUG-2026-10-30-007。当前以 C:\wms 本地 main 为依据，不读取生产库或备份，不访问真实业务服务，不执行迁移、部署或重启。

本阶段只修复“从现有单据中选择下一个候选号码”。首次成功保存时事务分配正式号、删除号不复用、跨进程并发及全部入口幂等尚未实现，不能把本阶段称为统一编号方案完成。

## 根因、范围与行为

原通用函数部分前缀按最后插入 ID 选择历史号码，乱序导入后可能从较小号码递增并撞已存在号；部分分支把后缀 cast 成数据库整数，大值溢出；异常后缀可能回退 0001。销售独立函数只取末四位，9999 之后同样可能重号。

`_numbering_existing_max` 只读取本月单号列，检查完整 ASCII 数字后缀，在 Python 中选最大值；过长数字明确失败，不回退已有号码。只对选中的确切既存编号加行锁，未给整月查询加 FOR UPDATE；选中行已经变化则重试并明确失败。原进程内锁、重试次数和编号前缀／日期格式保持。此机制仍不是跨进程的号段保留或完整并发分配协议。

16 个实际模型的 20 个前缀一起核查：IN／PI／OI、OU／SO／OO、CK／CS、SC／SUB、SF／SR、PR／PO、ASO、BOM、REQ、TF、ADJ、QS；OUT 仍映射 OU。SO 检查出库与销售订单，SR 检查委外收料与销售退货入库，PR 检查采购申请与采购退货出库。销售独立函数复用同一入口。原期初历史归单的独立迁移取号已经比较完整后缀，本次保持并回归，不运行生产迁移。

全仓检索取号调用、历史台账及构造／导入／下推／复制消费点，核对动态前缀来自业务类型映射与导入 helper。尚未改变新增／编辑按 ID、预览号、指定导入号或移动回执的现有产品协议；这些正是下一阶段正式分配必须继续处理的范围。

## 隔离及验证

复用本机新建的只读 LPAC 源码／解释器副本和父进程状态回执，实际 WMS、Flask test_client、私有内存库、合成账号及双仓库存；所有外连由本次 package-SID 的 IPv4／IPv6 WFP 规则阻断，测试无法修改监督器或源码。详见 [隔离补证](2026-11-09-local-appcontainer-validation.md)。

- 旧源码选择对照的外层 pytest 为 1 failed，内部 8 个方法共 19 个失败子例；随后用实际 16 个模型及 20 个前缀、SO 双向共享和行锁检查补证，两文件为 **20 failed / 7 passed**。失败值包括应取 0078 却取 0005，超过四位及整数范围后重号，异常后缀回退等。
- 候选 13 个明确文件 **154 passed / 29 warnings，66.71 秒**，包括实际模型、原入库同号保护、按 ID 编辑、销售冲突、工单、期初迁移和导入、金额／采购历史及库存文档引用。真实 MySQL／PostgreSQL 未运行；仅将实际捕获的行锁查询编译成两种方言，检查确切编号条件且没有 LIKE 整月锁。
- 另补期初 QS 和旧并发／盘点相邻 10 项，9 项通过，1 项仅因静态测试仍断言原 elif 文本而失败。改为 AST 精确核对 QS 对应 OpeningStockDoc.doc_no 且生成器实际调用映射 helper，保持其余运行、格式、跨月、连续取号及库存断言；未用删断言或添加豁免放行。
- 逆向对照后恢复候选，最终 6 文件 **66 passed / 5 warnings，29.19 秒**，包含该静态契约、全部实际模型与原并发／盘点及金额对照。154 与 66 的清单重叠，不累加为总数；原名为并发的旧唯一号测试是顺序创建，不能据其名称宣称多进程并发通过。

组件逆向在仅含本次源码及引用文档的新合成 main 仓库 C:\Users\Administrator\AppData\Local\Temp\wms-number-selection-inverse-lavrvy23，候选 `121269139def29692e3ae3138a96bdbf288646e2`。revert 后两个文件精确恢复原始 SHA-256，将确切字节放回隔离副本，同一选择／实际模型用例加 7 项金额对照为 **20 failed / 14 passed**；恢复候选后上述 66 项通过。没有在共享仓库回退、stash、reset、清理或切分支。

日志位于 C:\Users\Administrator\AppData\Local\Temp\wms-restricted-validation-66i0081z：number-selection-old-19-failures.log、number-current-models-old-20-failed-7-passed.log、number-selection-13-files-154-passed.log、number-qs-old-source-contract-1-failed-9-passed.log、number-selection-inverse-20-failed-14-passed.log、number-selection-final-66-passed.log。非空文件清单、原始代码哈希和合入回执保留在对应任务目录。

最终身份 wms.synthetic.11a5586303344002b5aa04bae455c3ab 的父进程回执确认退出 0、自有 Job 活跃进程归零、规则 78349／78350 和 profile 清理、受保护文件哈希不变。按原始哈希合入 C:\wms 的产品代码、必要库存文档和测试；Git 索引及 HEAD 未改，未提交推送。整批逆序回退、其他实际数据库、完整 CI、正式分配方案和生产生效仍待完成。生效确认：待人工确认。
