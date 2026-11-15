# 2026-11-15 H5 与原生 App 界面及操作习惯统一

当前状态：H5最终代码 `5b8bed39b038fcd05702d49a904eb9efc873bb12`（2026.11.64）已正常提交推送并通过完整精确CI；两轮失败与完整R8保留，下述阶段待验文字为历史过程。文档收口基于实际main `843ea7ec0f648da21fd7c2997e09a160f5bec33c`，保留另一任务已提交的Android改动，本次文档自身CI另验。生产未部署或重启，生效确认：待人工确认。

用户目标：H5是正式手机操作入口，保留浏览器摄像头扫码，界面与原生App保持同一套导航和操作语言。不是取消H5，也不是将现有功能降级为仅下载/备用页面。

基线：53b891344270363f6102e09f4ff117c4e8ea3569，main，Windows版本2026.11.61；首轮2026.11.62未通过静态契约，纠正候选2026.11.63。共享原2删除/2未跟踪文件保持；不新建分支或worktree。以下代码未验收前不表示生产生效。

## 实现与边界

- 新增 `/mobile` 和 `/mobile/me`，使用现有登录会话。手机端5项主导航与App一致；首页使用紧凑三列功能卡，连接和原生App下载放在“我的”。入库、出库、查库存、盘点、期初、物料、识物、识别单据、报表均连接现有真实入口，保留待确认。
- 已有物料详情、连接页面以及显式 `mobile=1` 页面共用手机布局；GET导航保留关键词/筛选/片段，外站、API、签名链接、导出/打印/下载及明确电脑版入口不改。POST表单/JSON/请求幂等键不变。嵌入页面不重复展示主导航，普通桌面不改变布局和多标签行为。
- 浏览器摄像头扫码、拍照识物、手工录入均保留，沿用现有ZXing与pagehide/取消/迟到回调防护。安全连接和摄像头授权是实际条件；不再宣称浏览器不能扫码或H5等同原生离线能力。扫码页、首页及下载回退三处误导同修。
- 仅界面与入口统一。现有H5入出库草稿/人工确认、盘点单必选、仓库口径、权限、CSRF、请求幂等、模型灰度与人工确认保持。未复制原生Room离线队列，未新增业务操作/数据库模型/角色/收费调用。
- 首页按已有业务角色呈现入口；点击识别的后端授权仍生效。手机布局允许浏览器缩放，输入区保持仓库、数量等现有控件与锚点，未收起或丢弃可选值。

## 验证证据

私有源码副本承载修改，全部app导入/测试使用本次新建LPAC、父进程句柄与nonce、内存合成库、WFP阻断网络和Job后代约束；仅自有哨兵验证隔离，未尝试连接生产。源/runtime/驱动指纹、活动进程清零及WFP/profile回收均由父进程回执核验。

- 修改前明确4模块72 passed/9 warnings，运行wms.synthetic.385af137949e4998985e275670f296a6。
- 第一轮新增13项全部通过；新增与原扫码/草稿/设备回归合并5模块85 passed/9 warnings，运行wms.synthetic.9b252aef26fe4b99b6b08b7b9072b2b7。后续修改必须再验冻结候选，不把此阶段结果称为最终通过。
- 原生代码未改；界面对照来源为HomeScreen/Screen/NavGraph，未使用原生旧绿冒充新H5布局验收。
- 既有Linux隔离browser-material-entry门禁增加真实Chrome三宽度320/375/414：底部5项、功能卡不横向溢出、入库扫码/拍照按钮、我的账号、首页往返及物料页保留手机导航；保留全部原物料/单据/CSP/库存断言。截图在该CI浏览器产物内，未运行时不能宣称浏览器通过。

最终统一测试、整批逆序回退、普通commit/push实际输出与精确SHA CI在独立回执登记；当前未取得这些实际结果前不能标记完成。

## 生产与设备

不连接/读取/复制/备份/修改生产库及生产备份，不请求现有服务或8080，不使用真实账号/单据，不调用真实模型/ASR/微信/打印/摄像头。生产未部署、重启或迁移；生产需重启WMS服务生效，生效确认：待人工确认。真实手机摄像头授权/取景、微信内置浏览器、软键盘、安全区及系统大字体仍需设备验收。

统一回归阶段：22个明确完整模块532 passed、4 skipped、9 warnings，88.36秒（wms.synthetic.7d6075c4a9f64abb9ad825a92cbbe804）。4个skip均为原有Linux HTTP子进程隔离测试在Windows的既定平台限定；不将它们算通过，对应目标CI仍须实际运行。

## 首轮失败与完整R8纠正

首轮30902085690393b2ef463eb097c69199a1a598c9已普通推送。真实Chrome三宽度导航/布局、AI-core、4个verify及smoke成功，但WMS/AI静态检查BUG-NEW-017失败，不能称为交付通过。根因是本批直接在base的原body标签尾部加H5 class，改变既有检查锁定的桌面/嵌入标签原文；不是摄像头或库存断言失败。22模块本地覆盖漏掉scripts/verify_wms_bugs.py内这个直接消费者。

已在共享main正常完整revert本任务为0bea41ee5c912ffa2c29990f8cd722d68dbc24e3；提交树与53b89134完全一致，未撤销他人Android未提交工作，回退不单独推送旧版本。新增测试直接提取并执行原BUG-NEW-017 AST元组，原首轮源码安全复现1 failed/14 passed。保留verify原规则全部字节及断言；重评后使用真正互斥的H5和桌面body分支，桌面/嵌入实际仍走原标签，H5单独渲染一次body。原扫码/权限/业务行为不变。

首轮真实浏览器截图在容器内生成，但既有上传步骤报告未发现文件，不能声称截图已交付或已人工看图；实际点击/几何断言有成功日志。纠正目标额外输出三宽度断言摘要，仍需完整新目标CI，不能借用首轮局部通过。

首轮全量单元还有两个失败：旧frontend_audit_failure_runtime的scanner-missing/permission VM未提供新增安全上下文检测所需的window。已在LPAC复现2 failed/35 passed，夹具补真实浏览器环境window.isSecureContext=true，保留所有原库缺失、权限拒绝、关闭/轨道释放断言。按函数名和mobile_scan.html模块路径检查其他Node提取器；它们已有window或不执行扫码启动。此夹具缺依赖不作为旧产品缺陷证据，原始输出留存。

纠正冻结候选：23个明确完整模块555 passed、4原有Linux-only skipped、9 warnings，89.73秒（wms.synthetic.dacbe476230a40c18afc2a45f78b66e0）。保留所有旧断言，原静态BUG-NEW-017从未经修改的检查器提取执行，真实HTTP确认每页只输出一个body。后续整批逆序及恢复通过相同候选SHA256核对；精确新CI仍待实际验收。

## 第二次CI失败与最终分支顺序纠正

9a5e13f8423a8875c4fdebab3113ea02be61962b的静态、AI、真实Chrome、verify、smoke及unit1/2均通过，但unit0有56个采购详情原角色/状态/嵌入案例失败。测试从base源码第一条body行抽取父模板；H5分支位于首位，导致该消费者丢失父body_class定义，不能将前述局部通过当成整批交付。原源码在本批LPAC复现56 failed/75 passed（wms.synthetic.53f8e81649584abca52ee1af227dd2a2）。

已协调并等待Android任务保存、释放其共用文件增量，再正常完整revert本任务9a5e13f8为f961fc8d39a5e819bde148c4db19ad5e3737a1c6；树与53b89134完全一致，未覆盖其未提交Android文件或保存补丁。最终候选版本2026.11.64。原桌面/嵌入body分支放在源码首位，H5互斥分支放后，所有原检查器/采购详情角色和状态断言均未修改；采购原完整116项与H5新增17项合计133 passed（wms.synthetic.4691952387ed4ea391772ba95ded171a）。新增真实HTTP验证继承super()的库存台账/日报页面仍只输出一套body及手机导航。

全仓按base.html、body_slot、startswith('<body')、body_class、super()检查测试/脚本与模板：唯一抽首body行的消费者为test_purchase_order_detail_transport_runtime；after_sale_entry、document_table_transport、independent_report_toolbars、report_toolbar_controls的既有最小父模板均显式声明body_class，原行为保留；verify_wms_bugs原规则不变。此计数是用例/消费者，非新增56个业务BUG。

第二目标真实Chrome日志确认320/375/414三宽度均navigation=true、no_horizontal_overflow=true、account_matches=true；截图上传仍未取得文件，不宣称人工看图或真机验收。最终完整新目标CI另验，所有失败历史保留。

最终冻结版本64：24个明确完整模块673 passed、4原有Linux-only skipped、9 warnings，179.54秒（wms.synthetic.9bff7a633fcc498596e4c28afba36531）。采购原116项与H517项完整执行，不跳过56个角色/状态用例。其余同类模板消费者已按源码和原回归核对；最终整批逆序、恢复及精确目标CI另列实际回执。

## 最终代码验收

- H5代码目标：`5b8bed39b038fcd05702d49a904eb9efc873bb12`；实际普通push `9a5e13f8..5b8bed39 main -> main`，无强推、无跳钩。22文件Git blobs逐个匹配冻结候选，正常pre-commit A1–A14零违规。另一任务后续推进main不改变该代码目标验收；当前收口仅修改四份文档，不纳入其未提交工作。
- [WMS CI43672083322](https://github.com/SIX2090/wms/actions/runs/43672083322)：精确目标completed/success，3个unit、4个verify、静态、smoke、真实Chrome及gate均success。
- [WMS AI Verification43672083263](https://github.com/SIX2090/wms/actions/runs/43672083263)：同一SHA completed/success，ai-core/static/gate均success；代码分流docs-checks正常skipped。
- Android目标无APK Build，复用[c5708563的43615763759](https://github.com/SIX2090/wms/actions/runs/43615763759)实时success：源是目标祖先，五条输入路径未变，222所需Git对象完整，replace refs/lazy fetch均关闭。此证明属于H5代码目标，不替代后续并行Android新目标的构建。
- 最终本地24完整模块673 passed、4个原Linux-only skipped、9 warnings；4个跨平台用例由完整目标CI验证。最后22文件私有副本整批逆序恢复准确53b89134，保留新锁：15 failed/118原控制passed；逐文件恢复同一候选后133 passed。专项相互重叠，不累加为总数或BUG数。
- 原静态checker、采购详情116项原断言保持字节不变。两个Node消费者只补window环境，权限拒绝/库缺失/取消及设备释放断言不变。真实Chrome在320/375/414宽度执行导航、库存/扫码入口、我的账号及物料页跳转，日志均navigation/no_horizontal_overflow/account_matches=true。现有截图上传未取得文件，未宣称人工看图或真机验收。
- 首轮30902085与第二轮9a5e13f8确有失败，分别完整revert为0bea41ee、f961fc8d，两次提交树均与53b89134一致；协调保护并行文件和独立补丁后再纠正，不掩盖失败历史。

当前main包含另一任务的新Android提交，文档收口目标的WMS/AI及Android证据仍按其自身SHA单独验收。实际结果保存于本任务独立交付回执并在最终报告列出，不用H5代码旧绿冒充文档目标成功。

生效确认：待人工确认；生产需重启WMS服务生效，本次未部署/重启/迁移，未访问生产数据库或备份、现有服务、真实凭据/单据/模型/ASR/微信/打印机。真实手机摄像头授权、取景、微信内置浏览器、软键盘和系统大字体仍需设备确认。
