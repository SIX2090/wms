# 领料编码列粘贴及月报汇总生产部署（2026-11-17）

- 用户明确要求“部署生产”。2026-11-17 **16:11（北京时间）** 已沿原 `WMS-Warehouse` 计划任务完成切换，版本 **2026.11.89**；后台/UI来源均为 `3b01799655f731369d5d3138962038f2ee682883`，唯一8080监听PID为15836。
- 范围：UI-REQ-CODE-PASTE-20261117-001，普通/工单领料编码列直接粘贴、自动分行带出物料、数量留空；同时包含已验收的 BUG-2026-11-17-008 仓库月报按期间每物料一行、移除月份列。实际Excel/WPS操作与生产业务数值未由本次部署测试，正常使用反馈待人工确认。
- 原实例16:11:11停止，新实例16:11:48完成被动身份核对，切换核对窗口约38秒。原任务只发起一次启动，监护重启计数仍为1，没有预算重置或第二实例。

## 干净制品与回退

- 新制品：`C:/wms_releases/20261117_requisition_paste_3b017996`，制品ID `180749a73c2c51f8853c6f8704334db264274cdba56f9dbc3c5e9e50c2289b1b`，7475个封存程序文件、699个源码/应用文件，34项运行依赖校验通过。只从精确Git目标导出源码，没有载入共享工作目录的未提交Android或其他改动。
- 原完整回退制品保留：`C:/wms_releases/20261117_browser_fixes_813f9cc3`，来源 `813f9cc382910613ee4f5899a078313c89eb4121`，7474个文件，制品ID `d97d7aea111d13f7f0a8cb1c1873197249d6a8c9a0973102c3f31a8818b1955a`。新→旧→新私有程序指针校验通过；不是生产回退演练，不恢复数据库或覆盖业务记录。
- 沿用原运行解释器、任务注册和受保护启动入口，启动保护代码只更新固定源码SHA。模型、配置、requirements无变化；app.py仅月报列函数及仓库月报的说明/标签元数据变化，其他顶层启动语句完全一致。保留原四项UI覆盖及图片选择提示，不混入新覆盖。
- APK903原样保留，SHA256为 `e63d0de98633e452bc77d03aa7dd582d6c533837b5a3d95aa6d8edb2d42dc77b`；未安装APK。

## 数据与验收边界

- 本次部署仅沿现役受保护入口预检及正常启动，预检只读访问原库结构元数据；exit0、read_only_startup=true、schema_check=passed、listener_started=false。启动数据库保护继续保留，配置指纹仍为 `864e66e6526f80ce95748b3f1fe6ea7f7a7bce200414abb08204471283a090da`。
- 六个持久目录只建立相同目标的目录联接，未复制或扫描业务内容。未执行迁移、初始化、回填、数据库复制/备份/恢复、账号修改、测试单据或生产HTTP测试；既有外部任务状态保持，未主动触发发送或打印。
- 上线后新旧程序全量hash和被动进程/任务/端口/来源身份通过；不以监听成功冒充库存、单据、打印或手机的生产业务验收。
- 精确代码目标的 [WMS CI](https://github.com/SIX2090/wms/actions/runs/44038759149)、[AI验证](https://github.com/SIX2090/wms/actions/runs/44038759229)、[Windows发行](https://github.com/SIX2090/wms/actions/runs/44039712281) 均completed/success。全站16912 passed、207既有skipped；功能专项557项及回退恢复证据见[功能记录](2026-11-17-requisition-code-column-paste.md)。Android因路径过滤无目标构建，成功祖先 `64e3a503129073e41101351525ce6b59fc374754` 的[构建903](https://github.com/SIX2090/wms/actions/runs/43999372845)已核实，祖先、对象完整和Android输入不变的证明保留。
- 原始证据：`C:/wms_test_tmp/deploy-requisition-paste-20261117/` 的 `candidate-build-proof.json`、`deployment-preparation-proof.json`、`protected-preflight-result.json`、`cutover-result.json`、`postverify-result.json`及`release-ci-proof.json`。原启动动作的原子替换备份保留于原运维目录，不提交配置或秘密。
- 本部署记录自身提交另验精确CI；文档提交不改变已运行程序目标、不再次重启服务。
