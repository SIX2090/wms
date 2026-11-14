# 来源采购预留完整性：pending 与新建消费点

本候选以 `8049d1e8e0a1aacc51747f9ca82b2b7afb4b1c58` 加前批 `a61311f20821df61f8a63f6e9c3f7facc9bb5dd872447f5838bd64414655115c` 为明确依赖，仅交付后续增量。前批新增3文件及 `update_completed_in_order` 函数保持不变。根任务当前BOM等其他提交不由本候选覆盖，app.py仅含新增纯验证helper及按单下推的局部调用hunk。

## 计数与证据边界

本地验证是实际源码函数、真实SQLAlchemy模型、真实Flask-login代理和新建内存库；没有导入WMS app或运行其模型module event、权限/输入/版本wrapper。模型event另经源码核对：document序号保留和warehouse命名空间监听器不规范采购counter或重算该pending头额。本候选不声称生产发生过这些事故，也不以源码模型代替完整应用验收。

* 建议 BUG-2026-11-14-001：`update_in_order_item` 把采购预留写入放在 `should_block_purchase_over_receive()` 条件内；关闭禁止超收后，普通明细1改2成功而received仍1。开/关库位均有真实模型反例。修改后仅超收限额受业务开关控制，预留记账不随其关闭。
* 建议 BUG-2026-11-14-003：旧JSON新增/替换先分别校验每一行、最后统一加counter；同源两行各6可一起突破PO剩余10或8.99。复制原两行各3、PO总10/已预留6时，也会逐行通过3<=4而累计到12。新建JSON本事务及时占用本行规范数量，复制按来源累计校验；allow模式继续允许超收，并真实记录全部预留。
* 建议 BUG-2026-11-14-004：pending改单行真实数量/单价后，行amount变8、单头仍7.77。现在只有实际量价变化才重算单头，其他未改行保留原amount，原量原价不变时保留历史行额/头额，包括0。
* BUG-2026-11-08-015继续部分闭环：历史明细或counter超过两位时，单行/别名、整单/批单删除及替换等不得靠累计净额猜原行预留贡献。新写增量也不能把既存1.005的counter累计round成另一个数量。只在实际预留写入处，复用8 ULP/至多1e-9比较和现有数量规范检查；缺证就回滚当前单据，未选中的历史来源、只读/完成校验和原量不变的备注编辑不被新guard拦截。

014-002不作为独立已证BUG或计数。裸handler的JSON后项错误确有未清理事务，但实际有效revision编辑经过 `require_role -> guarded_document_write` 的finally rollback，正常请求teardown亦有保护。本批统一handler失败出口，是即时逐行占预留所需的事务收口；保留这些外层正面防护，不以裸handler的dirty状态宣称正常受保护HTTP或生产持久化泄漏。

## 全WMS消费盘点

实际received_quantity赋值13处：in_order的JSON旧行释放/新行占用、单行新增/删除/修改、复制、单单/批单草稿删除、前批已完成行的3处，以及purchase_order选单下推、app按单下推core。前批已完成3处不重复修改。

本批新增 `_purchase_reservation_error(source_item, saved_quantity=None)` 仅检查服务端真实counter和可选已存原行数量，既不迁移/平账，也不改全局输入精度或增加库存写入口。新量仍由各既有写入口规范；需要释放旧量时传真实已存行数量，不接客户端raw delta/精度开关。所有调用只在实际counter将被改写时执行，未放到被完成/只读路径复用的全局validate函数。

非消费及已有防护：

* PO/PR导入、复制初始化received=0，为新来源，不是释放旧预留。
* Excel采购入库导入的get_num已round两位，InOrderItem不设置PO来源FK，不新增采购预留；批量粘贴无来源路径也不臆造PO归属。
* 复制到出库不修改来源PO预留；库存出库是另一业务阶段。
* 选单和按单下推的重复来源ID已有 `_aggregate_submitted_qty_by_item_id` 累加保护（BUG-2026-09-22-011），保持该既有行为，不把重复ID当应去重的删除请求。
* AI按单core调用另有AI草稿幂等；web HTTP重试幂等尚未在本候选完整复现/修复，不夹带新协议或声称已经解决。

## 事务、重复ID与财务

保留物理删除草稿及批量逐单部分成功：成功单提交，失败单整体回滚，后项继续；不改成全批原子。批删原SQL id.in_载入已去重，数字/字符串重复ID均只处理一次。

批删先整单预检所有来源，缺证单不修改任何行。受影响PO ID只在本单成功commit后加入末尾状态更新集合；实际后项DELETE故障测试证明，失败单的PO ID不应泄漏到后续更新，从而悄然改动该失败来源的既存状态/金额。原末尾PO状态更新策略保留；PO状态本来按已完成入库行计算，不能把预留释放简单当成状态变化。

JSON后项来源无效、客供标记不合法、批次/有效期错误或累计超限，handler统一rollback。不同来源成功和后项失败均覆盖；不会释放旧预留后留半套明细。普通两位、无来源且无库存动作的历史草稿物理删除保留。已反提交的普通两位草稿，净零完成/回退流水仍可按既有业务清理；本候选没有为所有历史库存/物理库位残差提供新的证明能力。

pending原量原价不变的备注编辑保留历史数量/价格/行amount和头total，不自动修历史差额。实际量价变动时计算当前行额并汇总单头，未改其他行仍用其已存金额，覆盖历史4.02/7.77和显式0。

## 验证文件与隔离

`tests/test_purchase_reservation_source_20261114.py` 显式110个方法，导依赖前拒绝app导入、SQLite文件库、网络、其他子进程；只在本进程创建合成内存库。除被测实际产品函数外，编号分配、配置源作为清楚标注的fixture seam，不冒充完整真实应用；金额/状态/计数等被测逻辑不塞恒真替身。

`tests/test_purchase_reservation_runtime_20261114.py` 显式110个实际HTTP实例。最先要求真实 `require_isolated_test_runtime()`，之后才导入w；复用真实memory URI/PRAGMA证明和合成会话的source_scene。只复用前者的夹具/断言常量，明确排除source pending_call；所有consumer通过真实document_post访问10个已核URL，core也走真实按单HTTP。模型全取w导出，配置仅经真实set_system_setting；禁止替换产品函数、伪造API返回或合成Flask app，并断言每例实际发出业务请求。

真实HTTP必须交现有Linux隔离启动器和精确SHA CI，禁止宿主import/collect/执行，不伪造runtime proof。有效revision由真实页面获取；无效签名由既有guard测试覆盖，本110不重复宣称覆盖。

消费提取器同步真实依赖：9模型审计提取新validator；7SQLite原型提取真实normalize/ULP比较/validator；10编号回归抽取真实创建分支时同时绑定其真实fail，原数量、事务、金额和编号断言不弱化。相关组存在重复共享基线，不能把各组方法数相加当唯一BUG数。

逐项结果、旧红新绿、整批私有源码逆序回退、真实Git patch应用及字节哈希见伴随proof。主任务统一登记最终BUG号、月账/索引/POST_SPLIT_BUGS并按实际AST更新INVENTORY_TRUTH的3个backfill符号引用；私有app的backfill为30478，根有额外BOM改动，不能照抄这个行号。

本候选未接触生产数据库、备份、账号、现役服务或端口；没有执行迁移或部署。其他数据库实际行锁、全部历史物理来源及web重试幂等仍各自待证。生效确认：待人工确认。

## 主任务最终集成范围（2026-11-14）

固定基线2ca31b2a424f0f41b25cfa9ac73617539e24268a，先按小hunk合冻结9，再合纠正4（共享route合计12源码/测试/报告文件），另版本/台账/索引/拆分契约/INVENTORY共18文件；版本2026.11.43。app.py只新增validator及core写前检查，已验BOM实际函数AST不变；完成入库函数及两份188测试精确保持cf。INVENTORY只按当前AST改3处backfill为30486，不覆盖私有旧app.py。独立登记001/003/004，不登记002，11月真实唯一标题189；POST_SPLIT分类只作解析兼容，生产仍待人工。170新HTTP实例须验收本批精确CI，前批库存2ca31b2a在并行验收，不用它的排队状态阻塞本任务验证。

最终消费点纠正：统一回归实际发现generic金额表达式缺new_quantity上下文和期初符号行号漂移。只补真实1.15量语境，保留14模块最小调用数、>60与4.03及BOM构造全部断言；INVENTORY的11符号全核，除backfill三处30464→30486，再把期初建账8751→8770。A9将原110中two-sources-later-failure/off的同一真实回滚用例等量命名test_fail，HELPERS/DELETE/UPDATE/COUNTER/EXTRA全部原常量字节不变，不增减110/170或削弱断言。最终18文件重新冻结验证。

上一库存批次2ca31b2a424f0f41b25cfa9ac73617539e24268a已验收：WMS43535374656、AI43535374639、性能43535374652 completed/success，三单测合计15929 passed/203 skipped/1561 subtests passed，203新实际应用实例纳入通过；Android复用cf成功且构建输入不变另具Git证明。Windows43536216561独立验收，未当成生产上线。

## 精确代码及CI验收（2026-11-14）

最终产品目标38b5440c215e74a8fdc8d6c34639b5e94efd21ae，版本2026.11.43；正常push实际输出2ca31b2a..38b5440c main -> main。pre-commit0违规，pre-push保留，不强推、不绕钩子。最终18文件（加入真实generic金额测试上下文纠正）按小hunk合入，已完成188函数/测试及BOM/库存服务均保持。

WMS CI43537505932、AI43537505750、性能43537505728均completed/success。三单测5557/5753/4791 passed，131/24/48 skipped，313/411/837 subtests passed：共16101 passed、203 skipped、1561 subtests passed。新增reservation110及input/ULP60真实HTTP合计170实例实际执行通过；其两份source guarded-worker也运行，较前批15929正好增加172个pytest通过节点。四verify、静态、smoke/browser及gate均success。前文“候选/待CI”保留为历史阶段，不再当当前未交付。

主任务最终18文件完整R8：2508个Git文本基线blob精确恢复再恢复同一候选，前后15组专项/相邻均通过。原产品对新110为74断言失败/0初始化错误，未纠正候选对新60为38断言失败/0初始化错误。没有把缺new_quantity的旧测试初始化错误计作产品旧红。证明pending-reservation-integration-r8-proof.json。

Android成功cf253742/43529573528有完整祖先及两处构建输入零差异证明（pending-38-android-proof.json）。Windows43538200056单独按实际结果验收，不等于部署。001/003/004代码及当前适用CI已验收；015整体及010诊断能力边界另核，真实设备/生产、未知拓扑和其他数据库不由本CI替代。生效确认：待人工确认。
