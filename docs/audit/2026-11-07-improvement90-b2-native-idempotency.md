# 90分改善计划 B2：原生请求原子幂等

日期：2026-11-07。关联A01、BUG-2026-11-07-007、AI-ASSISTANT-MOBILE-001-FIX-IDEMPOTENCY-20261107-001。

## 交付范围与边界

本批候选已完成28个完整模块393项、专用真实文件并发7项和AI full70脚本验证；新增行A1–A14、A11全量、既有全量棘轮、原生fetch、编码、严格AI台账及文档差异检查通过。代码已交付：1dd7388558d1775814aea78e7e9cb20f59e16cd1，WMS CI42386094902、AI42386094820均completed/success，所有实质检查与gate成功；Windows42386510483成功，本地/origin一致。B1代码已在8db506cc完成；整个90分计划及前端第5项均未完成。

只修改独立delivery-repo的main；生产数据库及旁文件、别名、链接不连接/打开/读取/复制/校验/写入，不发生产测试HTTP，不操作生产账号/密码/令牌/库存/单据/服务/监护或恢复预算。仅内存或明确fresh白名单合成文件库，无schema、启动迁移或回填。生产部署另需本批明确授权，且不会自动解除数据库禁令。

## 根因和消费点

原mobile_api_idempotent先查历史、执行业务提交，再单独保存响应；收据失败仍回200，并发可能重复库存或单据，且同key换内容仍回旧成功。相邻真实双连接又证明：单号在数据库写锁之前读取，两个不同请求也可能取到同号。原进程取号互斥只包住读取，不能保护随后的提交；自动建档物料也必须在匹配之前串行重读。

全部九个消费点保留原认证/角色、人工确认和业务验证：

| 消费点 | 路径 | 原业务边界 |
|---|---|---|
| inbound | /api/inbound | 用户明确提交入库，库存/流水/单据一致 |
| outbound | /api/outbound | 用户明确提交出库，仓库级库存边界保留 |
| stocktake | /api/stocktake | 必须关联进行中PC盘点单 |
| opening_stock_edit | /api/opening_stock/<line_id> | 保留版本比较及既有BEGIN IMMEDIATE；路径进入指纹 |
| opening_stock | /api/opening_stock | 保留期初兼容单及差额口径 |
| inbound_draft | /api/mobile/inbound_draft | 仅草稿，自动建档前串行匹配，不直接入库 |
| voice_out_draft | /api/mobile/voice_out_draft | 先解析/人工选择，只建pending草稿，不扣库存 |
| voice_intent | /api/mobile/voice_intent | 导航/建议及降级，不扩大写权限 |
| assistant_chat | /api/mobile/assistant_chat | 复用PC链和人工确认，历史与结果避免重复 |

## 实现与接口约定

复用MobileApiRequest现有唯一(user_id,endpoint,request_key)、status_code、response_json、created_at。短事务预占请求，JSON存内容SHA256和随机owner，随后释放写锁。实际业务首次flush/commit之前核验owner、取得业务写锁；当前真实Session的内层commit仅flush，最终完整响应收据与业务一次commit。Session通过Flask-SQLAlchemy正式session_class扩展，未猴补全局方法；没有原生请求上下文的PC/H5/普通Session仍走默认行为。

原生正式取号在Python互斥前激活数据库事务，避免锁顺序反转和不同请求撞号；自动物料建档在匹配前激活。AI/语音模型阶段尚未进入写事务，真实第二连接验证仍能提交其他写入；第一次实际写入后所有共用服务内部commit都受同一事务约束。内部rollback即使被吞成200也不会提交半成品。

调用方每次新操作使用一个新X-Idempotency-Key（也兼容JSON request_id）；网络故障重试必须复用原key和原内容。指纹包含请求路径及去除request_id的原JSON，所以同一编辑key不能串到另一行。成功相同内容原样重放，不同内容409；旧/损坏、缺指纹的历史收据明确拒绝确认，不修改旧行或猜测内容。409应先核对原操作，不能自动换key再投；503可能仍在处理或结果未确认，应保留原key重试，不能仅据503推断业务未保存。缺key保留既有兼容行为，不承诺去重。

120秒预占租约只允许CAS换owner；过期不代表旧线程已退出，旧owner在写入或最终提交前被隔离。真实HTTP接管验证只保留一个草稿，旧线程503且不能删除新owner收据。异常、验证失败、最终收据故障均回滚业务，只释放自有owner预占；释放本身失败时保留租约，重试仍受所有权保护。无新表/字段/配置，不增加外部调用。

原生APK源码已查：WmsRepository/OfflineQueueManager为同一提交及离线补传复用requestId；本批没有修改Android源码或工作流。APK/真机行为不能由这些后端测试冒充验收。

## 本地验证和整批R8

- 修改前9个完整原生/AI模块串行86 passed；Web/H5原三模块经明确fresh concurrent.db及固定Node驱动适配后旧基线95 passed。
- 首批12个正确契约在旧产品11 failed/1对照passed。初次夹具未先设置TESTING，12个setup错误单独保留，不能冒充产品失败。
- 最终28个不同的完整受影响/相邻模块，393 passed、0 failed/0 skipped；包括九个真实HTTP入口精确重放/不同内容冲突、嵌套commit、吞rollback、最终/初次收据故障、旧收据、路径、无key及真实Bearer活动刷新和过期先于重放。提交完成后响应丢失模拟503，原key重试只保留一份单据/库存/收据。库存真相源码引用22项及原契约53内部检查、台账和既有H5消费模块通过。
- 另一个完整专用模块在fresh synthetic.sqlite上7 passed：两真实连接同key/不同内容/不同key/不同用户、自动建档复用与独立正式号、模型等待可写、过期owner接管后不能再次建单。默认内存CI中该专用模块明确skip，实际文件库通过证据单列，不能把skip算通过。
- 首轮六个产品/任务文件、最终十一份产品/登记/文档文件均整批撤回到8db：内存26项为24 failed/2对照passed；文件7项为6 failed/1对照passed。原Web/H5三模块旧基线95 passed已成功，不无故重复；最终回退仍核验相同8db基线。候选逐文件SHA256恢复一致。新内部lease API单元不在旧缺模块时制造ImportError充数。四个运行时代码文件哈希等于最终R8候选；随后只增加测试及更新验收记录。
- AI full原70脚本清单完整保留。首轮前29成功，第30项严格台账拒绝把进行中通用修复冒记为已完成能力；改为普通唯一修复ID引用，既有44个能力标记不变、子项仍待验收，严格检查器未改。从第30项起余41全部通过；前三个运行时文件逐字节不变，新服务只改模块文档注释且去该注释后AST完全一致。最终原生核心38项及真实并发7项已按修正后哈希重验；精确目标CI仍须全量重验。
- 盘点测试补进行中check_id、删除错误warehouse_id夹具参数；语音stub改为复用既有解析结构。未删断言或放宽业务校验。不同key正式号竞争曾真实失败，已在事务锁位置修复后重新验收。所有失败保留。
- 早期两组worker尾部重叠1.44秒未计最终验收，已串行重跑并加任务专用OS互斥。每组最多3模块；启动416MiB，连续3次低192MiB只停止自有进程；没有降低阈值或关闭用户应用。服务/浏览器未启动。

证据：仓库外wms-improvement-90/B2-final-local-results.json、B2-ai-full-results.json、lab/b2-final-static-01及各lab运行的manifest/XML/process/I-O；r8-b2-files-whole01及whole02的proof.json与candidate.zip；原审计7项观察未更改。AI运行曾短时低于192MiB，但未满足连续三次停止条件、无自有worker终止，未降低阈值或关闭用户应用。A9要求精确函数名，已仅将原九入口测试改名test_wrapped、全部断言不变，完整核心38项再次通过；运行时代码未动。精确CI以随后实际记录为准。

已读现有CI冒烟源码：run_smoke_in_ci.py使用新建wms-isolated-smoke目录，排除instance、数据库和环境文件，清除继承配置，创建全新synthetic.db，并以身份文件关联自有PID/端口/数据库。云端既有全量CI使用自身合成环境；本机不对生产运行默认冒烟。原H5独立子进程并发用例保持原样，交完整CI执行，未为本地驱动放行任意Python子进程。

## 验收和生效

开工基线8db506cc的WMS CI42377215120和AI42377215211成功；交付目标1dd7388558d1775814aea78e7e9cb20f59e16cd1的WMS CI42386094902和AI42386094820均completed/success，全部实质检查及gate成功，Windows42386510483成功。Android42311667571在8d3b4c5d成功，为交付目标祖先且原生及工作流构建输入不变；不是任意旧绿替代。

生效确认：代码已通过Git Data准确15文件/完整tree4975044fa6f499f6d9db255a12e6113167b516a0、两提交parent和expected_sha/force=false推送；两原本地提交bundle保留，公共fetch逐blob、完整tree及CAS核对后HEAD/origin一致，精确目标完整CI通过。仅隔离合成验证，未部署/切换/重启生产；不能用生产查库、测试请求或真实业务单据补证。本收尾事实随下一相关批次推送。
