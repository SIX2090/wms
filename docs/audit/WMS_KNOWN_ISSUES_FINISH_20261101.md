# 当前已知问题有限清单（2026-11-01）

口径：21个已交付软件登记、原29个真实验收类别、1个本轮确认的预览绑定缺陷和1个明确权限受限的旧凭据项分别列示；不混为按钮数量，也不把全部历史台账重新开审。

生产保持固定867e369a / PID11112。已从既有日志核实GET /wechat_share在16:12:00.672返回200；16:36健康和登录GET仍200。用户短暂异常反馈没有具体页面/操作，未归因于暂停能力。布局及全部交互不由HTTP200推导。

## 已交付软件（不重复实现）

| ID | 问题 | 代码状态 |
|---|---|---|
| BUG-2026-11-01-001 | 助手实际出入库及供应商到货查询混入未完成草稿 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-002 | 完成态查询被误当执行且部分高风险措辞没有明确拒绝 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-003 | 助手指定仓库被默认仓覆盖且全库口径未说明 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-004 | 需求够不够被错误替换为安全库存判断 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-005 | 只读追问丢失物料仓库数量并误走调整草稿 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-006 | 文本提取把编码数字当数量并混淆供应商与物料 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-007 | 精确编码流水扩大到同名其他规格 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-008 | 关键词路由抢走金额口径推理和导航问题 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-009 | 找到采购订单后未回答订购已收欠收数量 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-010 | 采购入库规则回答与默认仓及状态事实不一致 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-011 | AI请求根JSON及公共字段类型错误返回500 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-012 | 解析器把物料名中的动作前缀误删并漏行 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-013 | 文本发货清单的明确供应商标签未提取 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-014 | Excel列标题被识别为零数量物料行 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-015 | 明确复述确认文本被重复计为物料数量行 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-016 | round26五个按钮接口的根JSON和字段类型缺少校验 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-017 | 视觉连接测试回显供应商原始错误和异常细节 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-018 | 供应商评估按每条重复物料明细反复读取相同价格历史 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-019 | 微信分享先查后发缺少跨进程原子领取 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-020 | 微信分享接收确认后提交失败导致普通重试再次投递 | 精确代码CI通过；受控源已含该代码，外部路径暂停 |
| BUG-2026-11-01-021 | 微信分享已发送历史记录缺少清理入口 | 精确代码CI通过；主线已交付，固定生产源尚未含该功能 |

## 本轮确认项与明确未修项

- 合并预览确认未绑定：隔离候选已修，尚未推送/部署；不等于库存账务并发缺陷。首次19个新锁的旧码对照为16失败/3权限对照通过；61项合并及相邻通过，另7项恢复开关条件通过、008重开分支1项通过。不同测试共69项，重叠的19项不累计。
- BUG-2026-10-21-001：旧忽略启动脚本中的云凭据字面量仍需由有云权限的操作员迁移/轮换。本轮不读取、复制或修改真实凭据；受控入口不再加载旧脚本并不等于该项已消除。
- 042真实永久合并并发/库存引用变化仍是待验风险；不以协调替身到达证明真实删除或真实并发已通过。

## 原29项真实验收缺口

| 编号 | 入口 | 真实验收主类 | 当前软件证据 |
|---|---|---|
| BTN-PENDING-003 | 系统设置／测试文字连接 | external_service | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-004 | 系统设置／测试图片识别 | external_service | 关联已修BUG-017 |
| BTN-PENDING-006 | 物料／网上找图（工具栏） | external_service | 关联已修BUG-016 |
| BTN-PENDING-007 | 物料／网上找图（行内） | external_service | 关联已修BUG-016 |
| BTN-PENDING-008 | 物料／修复空分类和单位 | destructive_or_inventory_confirmation | fresh HTTP session rereads repaired fields; no stock mutation; native dialog still not tested |
| BTN-PENDING-009 | 打印路由／创建工作站 | credential_operation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-012 | 打印路由／重置令牌 | credential_operation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-017 | 单据OCR／开始识别 | external_service | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-018 | 供应商智能评估／生成评估报告 | external_service | 关联已修BUG-018 |
| BTN-PENDING-019 | 需求预测／生成预测 | external_service | 关联已修BUG-016 |
| BTN-PENDING-021 | 微信分享／立即分享今日入库单 | external_service | 关联已修BUG-019/020 |
| BTN-PENDING-022 | 微信分享／保存设置 | ui_confirmation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-023 | 微信分享／重新生成并再次发送今日入库单 | external_service | 关联已修BUG-019/020 |
| BTN-PENDING-024 | 手机 in／拍照识物 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-025 | 手机 in／条码扫描 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-026 | 手机 out／拍照识物 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-027 | 手机 out／条码扫描 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-028 | 手机 check／拍照识物 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-029 | 手机 check／条码扫描 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-030 | 手机 query／拍照识物 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-031 | 手机 query／条码扫描 | physical_device | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-032 | 用户管理／保存新用户 | credential_operation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-034 | 用户管理／确认重置密码 | credential_operation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-037 | AI七日验收／构建最近七日证据 | seven_day_observation | 关联已修BUG-016 |
| BTN-PENDING-042 | 物料／确认合并 | destructive_or_inventory_confirmation | consent-binding defect reproduced without permanent merge; isolated repair passed |
| BTN-PENDING-043 | 盘点详情／仍要完成 | destructive_or_inventory_confirmation | 关联已修BUG-016 |
| BTN-PENDING-044 | 调整详情／保存并完成 | destructive_or_inventory_confirmation | 关联已修BUG-016 |
| BTN-PENDING-047 | 修改密码页／修改密码并继续 | credential_operation | 既有静态/软件证据；不冒充真实验收 |
| BTN-PENDING-072 | 库存调拨／反提交 | ui_confirmation | 既有静态/软件证据；不冒充真实验收 |

29项类别仍各有真实分支未完成；008本轮补的是API保存重开，不是原生确认；022已有保存/重开软件测试，本轮没有将它重新计为新增。043/044/072需先确定本次合成单、仓库、数量和回退边界，未执行未知库存动作。

## 受控运行暂停能力与最小恢复条件

| 能力 | 当前影响 | 恢复前最小条件 |
|---|---|---|
| scheduler_and_patrol | No scheduled notifications, patrol records or retention preview. | Approved controlled restart with selected jobs; existing launcher has no global scheduler-off flag. Do not start the whole scheduler blindly. |
| automatic_backup | Daily automatic backup and its retention job are paused. | Approve backup destination and retention deletion separately. Registration-only positive/negative tests use a fake scheduler; no production backup copied. |
| inventory_alerts | Scheduled in-app warnings and email are paused. | Choose in-app-only versus explicit email recipients; approve operational notification writes. Synthetic switch tests do not prove real email. |
| printing | Local print agent, automatic enqueue and device operations are paused. | User previously reported no available real device. Supply client workstation/printer and a specific test job; do not expect a cloud VM to have a printer. |
| wechat_share | Menu readable; automatic/manual delivery and configuration changes paused. | Only delivery needs dispatch table. No table needed for menu. Approve one-table DDL/backup and a specific channel/recipient/task before real delivery. |
| external_ai_ocr_voice | Outbound network and external subprocess-dependent features are blocked. | Specify provider/model/destination, synthetic input and cost limit. Existing credentials loaded only by the application; no extraction or generation. |
| destructive_retention | Startup backfills and automatic image/backup deletion are not running. | Approve exact affected scope before restoration. A normal restart with NO_DB_TOUCH alone does not suppress these independent calls. |

当前进程的出站审计屏障不会因修改数据库开关而卸载。恢复后台/外部能力需要另次具体授权与受控重启；本轮没有准备新的恢复平台、没有启动这些任务，也没有操作生产迁移、历史回填、删除恢复、设备或收费接口。

证据见同目录known-issues.json、evidence/runtime-short-check.json、evidence/merge-complete-related.log、evidence/merge-preview-r8.json、evidence/empty-fields-reopen-new.log。

## 本批范围、验证与交付边界

本批仅修BUG-2026-11-01-022的网页合并预览确认边界，并同步已授权分享批次的精确CI/受控菜单结果。产品3文件：routes/material.py、static/js/material_merge.js、新services/material_merge_preview.py。测试保留原有全部库存/别名/单位/回滚断言，增加真实HTTP预览准备与19个新锁；另有008的全新HTTP会话重开测试，不执行库存过账。

修前合并及相邻42 passed；最初确认边界回归8 failed/3权限对照passed。最终61个不同合并/相邻实例通过；整批旧码对照16 failed/3passed，三个产品文件SHA256恢复一致。后台恢复条件7项只验证备份注册开关、伪线程打印开关及合成站内预警开关，不创建生产任务、不发送邮件、不作真实备份保留清理。008新增1项是合成修复后用新HTTP会话重开，库存与流水快照不变，不冒充浏览器原生确认通过。

远端基线d7a8f2b102f7313ba4bab5510077beacd1ebf0f0的WMS CI41289975902、AI41289975827成功；其产品2d029b59的完整CI证明独立保留。新批次尚未批准推送/发布；本地候选不视为远端交付。生产当前仍固定867e369a/PID11112，后台能力暂停，无新停启/建表/历史回填/生产测试写入。

008/022/043/044/072按旧证据去重：008此前已测修复/重复幂等，本轮只新增重新打开API读取；022旧测试已有保存总开关关闭再GET重开，不重计。043期间库存变化仍完成、044非零双仓完成、072反提交需精确新合成单、数量和可逆边界后再做，不执行未知副作用；无记录不自动归为BUG。

当前工作区另有已交付微信历史清理2d029b59/d7a8f2b1，固定生产源未含它；本轮没有混入或重复实现。原3个无关未跟踪文件保留。外部证据根C:/wms_backups/known_issues_20261101_round30，原始中间失败日志保留，不把隔离缺公开verifier输入误归为产品失败。

最终在d7a8f2b1基线上复验：69个不同产品/相邻/暂停开关/008新增实例与10个台账契约实例，共79 passed；旧码反证19项中的16失败/3对照通过不计通过数。未修改的完整BUG验证器通过；原full_smoke_test.py在一次性SQLite/合成会话桥接中退出0，包装1 passed及2个既有Query.get弃用警告，不代表正常密码登录。自动化仅使用本轮新建的RAM/临时库、公开源码及固定非生产测试会话；无生产测试写入。

副作用边界：新增19个预览确认回归的执行端由无变更哨兵拦住；既有42项模块回归则按原测试在本轮新建RAM中实际执行了合成合并、引用改指、别名及回滚，不能笼统写成“所有测试都没有调用合并”。这些内存夹具不是旧QA库、旧草稿或生产记录；没有把它们计为真实浏览器永久合并验收。后续手工不可逆验收仍须具体对象和当次确认。

## 固定29项后续安全检查

上文的未执行/待准备描述是较早检查点。后续已完成固定29项授权内安全软件检查，逐项证据、008/022重开及043/044/072精确库存边界见[29项后续记录](WMS_29_SAFE_SOFTWARE_20261101.md)。硬件与打印模拟新增确认BUG-2026-11-01-023，隔离候选已修；真实验收仍分别保留。此后用户明确禁止全部生产测试，不沿用此前只读探测许可；本轮无生产接口/数据库探测或服务操作，新候选不发布。
