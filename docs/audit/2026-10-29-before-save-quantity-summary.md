# 保存前实时数量合计验收（2026-10-29）

任务：用户需要在保存之前看到单据全部录入明细的数量合计。

## 范围与使用

入库（采购/产品/其他/销售退货）、出库（领料/销售/其他/采购退货）、售后出库、期初库存、采购申请、采购订单、销售新增/编辑、委外产品与发料/收货录单弹窗，共 13 个模板、10 类页面。数量合计位于明细下方，录入时即时计算；无需保存、提交或发起接口请求。空物料行不计入；原有金额合计保留；列隐藏或重排不影响独立合计条。数量按各行原始数值相加，显示最少 2 位、最多 4 位小数，不做单位换算。

共享 quantity-summary.js 仅读取目标表 tbody，监听输入、变更、增删行和表单重置；现有 calcTotal/updateTotals/recalc/updateTotal/委外行计算入口显式刷新，以覆盖直接赋 value 的程序填充与草稿恢复。未增加或更改保存接口、库存写入、权限、密码和生产服务配置。

入出库详情复用原有合计行并接通新增未保存行、已有行输入框以及取消编辑恢复；空单也保留合计行，读 DOM 量时优先未保存输入，其次已恢复的 data-value，不把编辑图标当数量。

本批按最终用户目标仅覆盖保存前录单。打印模板和其他只读详情的数量合计缺口另列，不计为本批已修复。期初原有“导入并保存”仍是原来的写入流程，本次未改变其确认或库存回冲边界，也未对该流程进行生产操作。

## 基线门禁

目标 main：2da561cf95c6b4ef51c6b6b47e7af615abccd542，本地、origin/main 与实时 ls-remote 一致。开始写入前由 GitHub 连接器读取 main 最新运行（本地查询遇 HTTP403，未把查询失败当红灯或放行）：

- [WMS CI 40838928409](https://github.com/SIX2090/wms/actions/runs/40838928409)：精确目标 completed/success。
- [AI 40838928416](https://github.com/SIX2090/wms/actions/runs/40838928416)：精确目标 completed/success。
- [Android 40791277115](https://github.com/SIX2090/wms/actions/runs/40791277115)：3d17eb803a006f2abf14e6e091f1b7b24636c60a completed/success；git merge-base --is-ancestor 成功，完整对象可用，至目标的 app/android-native-wms/ 与构建工作流差异为空。

提交前再次核实远端 main 未变化，连接器最新三工作流仍满足以上证据；本地脚本再次 HTTP403。依据 AGENTS 的同基线替代证据条款，仅本次 push 临时设置 WMS_SKIP_CI_GATE=1，保留分支与 pre-commit 门禁，不提取连接器凭据。

## 本地验证

- 修复前受影响定向基线 197 passed。
- 13 项新增回归直接读取实际模板配置及共享 JS，覆盖输入不失焦即可更新、空行排除、复制/增删、程序填充、四位小数、已有委外行加未保存行、清空及重置。
- 物理备份改动文件、用 HEAD 文件还原产品代码，新回归 13 failed；finally 恢复全部修复文件并逐字节核对。未使用 stash。
- 中间两组定向回归分别 208 passed、287 passed（有重叠，不相加为总数）；最终统一受影响/相邻回归 733 passed（11 条既有 SQLAlchemy LegacyAPIWarning）。台账测试显式补登新 ID，保留拆分前状态分布的原始断言。
- 浏览器使用独立 18129/18131 内存数据库及合成物料 Q-001，服务拒绝全部 POST。13 页实际输入正确；入库两行 2.5+1.25=3.75，金额仍 11.25，改第一行 5 后合计 6.25，删除第二行后 5.00；出库 4.50；售后 2.50；采购订单/申请 3.75；销售新增/编辑 4.25；期初 0.0003；委外产品已有 2.5 加未保存 1.25 为 3.75；委外发料/收货弹窗各 6.25。
- 截图、独立服务脚本、回退文件及记录：C:/wms_backups/quantity_summary_20261029/。

- lint_wms_rules 全量 0 违规、verify_wms_bugs 通过、业务 JS 原生非 GET fetch 检查通过（模板存量 warn 保持）、node --check 及 git diff --check 通过。
- 原 full_smoke_test 的页面/导出/API 只读部分在独立文件库 18130 为 111/111；未运行登录写入、改密码及新增物料步骤。初次内存库为 110/111，唯一失败是 /backup 明确仅支持文件库；改用外置隔离文件库后原检查全部通过，未改产品断言。完整标准冒烟由提交 CI 执行。

- 最终补查两张出入库详情：已有 2.5 加未保存行 1.25 为 3.75；原行暂改 5 显示 6.25，Escape 取消编辑恢复 3.75，不触发保存。最终新增回归 13 项旧代码回退全部失败，包含恢复编辑图标后数量不丢失的运行时断言。

## 交付与生效

代码提交 `33596bdd857be5a9a7149184bf5cd861b7d4d41a` 已实际 push（2da561cf..33596bdd main -> main），本地与 origin/main 相同。GitHub main 分支返回的 tree 与本地 HEAD tree 均为 `338f85485e11a9f93d5068f187b619393b10f504`。

- [WMS CI 40844098589](https://github.com/SIX2090/wms/actions/runs/40844098589)：精确目标 completed/success；标准 smoke、所有 verify 分片及静态检查均成功。
- [AI 40844098590](https://github.com/SIX2090/wms/actions/runs/40844098590)：精确目标 completed/success。
- Android 最新成功仍为 [40791277115](https://github.com/SIX2090/wms/actions/runs/40791277115)，已再次验证至本代码目标为祖先且工程/构建工作流无变化。
- 代码推送使用已记录同基线替代门禁证据；WMS_SKIP_CI_GATE 仅在该次 push 设置，finally 移除，pre-commit 正常执行。

2026-10-29 16:46（Asia/Shanghai）代码 CI 验收通过。生产只读核对仍为 WMS-Warehouse / run_wms_task.bat / Python311 run_server.py，PID 14104、创建于 15:55:04、唯一 127.0.0.1:8080。生产需重启 WMS 服务生效；重启授权待用户确认，未重启生产。

交付补证批次仅修改本记录和月度 BUG 条目。开工/提交前再次连接器核实 33596bdd 为远端 main，WMS CI/AI 精确目标成功；本地 check_ci_green.py --target-sha 33596bdd857be5a9a7149184bf5cd861b7d4d41a --json 查询已恢复，三个工作流均 green，退出码 0。台账回归 30 passed；该补证 push 不使用跳过开关。
