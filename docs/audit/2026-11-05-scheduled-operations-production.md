# 第二项生产保障启用与生效回执（2026-11-05）

用户明确选择“先启用已验收的第2项生产保障”，授权每日只读在线备份、进程故障监护及短暂重启；不修改业务记录或账号。本次只启用已交付能力并记录结果，没有开始第四项业务开发。

## 来源与边界

- 生产应用继续使用 `85df64375b68cf65dd5348276b3ddb657353e589`，目录 `C:/wms_releases/20261105_audit03_85df6437`；既有 `launch.cmd`、发布清单、覆盖层和应用代码未改。
- 运维工具从已全绿基线 `c6048a0976d0c5ab987901ebc856a679d2187e2f` 冻结到 `C:/wms_releases/operations_c6048a09`，六个文件逐个记录SHA256；与第二项交付 `19e66b051601e01871d41ffe8e1a7bd0497cb209` 对应文件无差异。
- 文档写入前再次核实基线 [WMS CI 41981919044](https://github.com/SIX2090/wms/actions/runs/41981919044)、[AI 41981918977](https://github.com/SIX2090/wms/actions/runs/41981918977) 成功；[Android 41971520345](https://github.com/SIX2090/wms/actions/runs/41971520345) 为成功祖先，Android源码及工作流无变化。
- 保留原 `C:/wms` 未提交文件，记录在独立main副本完成。没有生产账号登录、测试单据、库存写入、密码变更、数据库迁移/初始化/恢复。在线备份按本次明确授权以只读源连接复制数据库；完整性检查只打开备份，不读取源库业务行。

## 实际启用结果

| 项目 | 配置及现场证据 |
|---|---|
| 服务任务 | `WMS-Warehouse`，SYSTEM，`ExecutionTimeLimit=PT0S`（无限时），`MultipleInstances=IgnoreNew`；原触发器及身份保留 |
| 实际监护 | 2026-11-05 15:31:59（北京时间）接管；WMS监听PID3024 → release runtime PID1188 → CMD子进程PID9996 → supervisor PID15832 → release runtime PID16352 → Windows Schedule服务 |
| 故障边界 | 进程异常退出最多重试3次、间隔60秒；正常退出不重试，运行稳定5分钟后按已验收规则重新计算故障预算；仍保留WMS数据库运行锁。监护对象是进程退出，不把页面卡死或网络中断也声称为自动恢复 |
| 现场状态 | 15:42:30任务Running、8080仅一个监听、监护running且restarts=0；真实Chrome访问公网登录页成功。后续收尾检查另存外置证据 |
| 备份任务 | `WMS-Warehouse-DailyBackup`，SYSTEM，每日北京时间02:00，StartWhenAvailable、IgnoreNew、15分钟执行上限，保留30天 |
| 数据路径 | 源 `C:/wms/app/instance/inventory.db`；备份及状态 `C:/wms_backups/operations_20261105_c6048a09/daily` |
| 权限 | 备份及运维目录仅SYSTEM、Administrators及本机管理员可访问，实际备份文件ACL已核对 |
| 状态读取 | 监护子动作显式设置 `WMS_BACKUP_DIR` 指向同一私有备份目录，再调用原 `launch.cmd current --serve`；共享状态读取函数实读到success及最近成功时间。未登录生产管理页，不将此说成已完成该页的生产账号交互验收 |

Windows虚拟环境的python.exe会委托底层Python进程执行；上表同时核对启动器和父子链，不能只凭最终进程映像的全局Python路径否定独立runtime，也没有升级全局解释器。

## 首次实际备份

15:35:49手动触发**真实SYSTEM计划任务**，15:35:50完成，任务返回0，状态记录success。文件 `auto_daily_20261105_153549_442610_inventory.db`，5,955,584字节，SHA256 `28497c236f9bb71ffd929eb7f11a069f33ac5dabed1280901d35556923393214`。

备份以只读方式执行SQLite完整性检查，结果 `ok`；实际98张业务/历史表覆盖当前97张模型表。额外历史表不被当成损坏，也没有在源库删表或修表。没有执行生产恢复演练；此前92表合成库的逐表逐列恢复证据见[第二项隔离验收](2026-11-05-scheduled-operations.md)，不能用它承诺生产恢复耗时。

下一次定时运行是 **2026-11-06 02:00（北京时间）**。当前已经证实任务注册、SYSTEM身份、真实动作及首次成功备份；首次按时钟自动触发尚未到时，不提前标记已观察。备份保存在本机，跨机器副本及灾难恢复不在本次授权范围内。

## 切换过程与限制

1. 15:23:13安装任务定义后观察到8080无监听；此前实例自14:21启动且旧定义有PT1H上限。Windows任务历史事件不可用，只有时间及现场状态证据，不能声称已取得操作系统超时事件证明。
2. 15:24:07登录恢复200，但父子链仍是旧的直接启动动作，未出现监护状态文件。因此未将“任务定义已改”当成监护已经接管。
3. 第一次切换中，Stop-ScheduledTask已结束目标子进程，后续Stop-Process遇到PID已不存在；外置操作助手按失败路径恢复直接启动，并保留无限时配置，确认服务健康。修正助手对已退出PID的竞态处理后重新切换，没有修改仓库工具或产品代码。
4. 15:31:46至15:31:59完成最终切换，耗时13.39秒；这仅是最终一次切换耗时，不是本次全过程累计不可用时长。进程链、实际监护状态与新版响应头共同证明已接管。
5. 公网真实Chrome只允许GET/HEAD，未提交生产登录；登录页、CSRF字段、帮助展开/收起、Secure/HttpOnly/SameSite=Lax Cookie、产品版本头均通过，页面异常0，非GET请求0。实际下载app.js的SHA256与已封存覆盖层一致。

没有为了验证重试而故意杀死生产应用。三次重试预算、60秒间隔、耗尽锁定和Windows CMD链路已有隔离原生验收；本次只验证生产的真实配置、进程关系、正常运行和实际备份。

## 留底及交付范围

原服务任务XML、原动作与初始安装计划保存在私有运维目录；另以 `effective-plan.json` 记录最终私有备份目录及实际环境，不覆盖历史计划。若需撤销监护，按留底定义核对后恢复动作并维护服务，不恢复数据库，也不盲目恢复旧的一小时时限。

外置证据位于 `C:/wms_audit/20261104_remediation/evidence`：`operations-monitor-activation.json`、`operations-first-backup.json`、`operations-backup-integrity.json`、`operations-page-status-reader.json`、`operations-production/live-state.json`、`operations-production/production-browser.json`及截图。证据未包含Cookie值、密码或数据库内容；备份本体只保留在私有运维目录。

本批记录的台账统计、库存文档定位及审计README契约共34 passed；严格AI台账、源码编码、暂存规则检查及verify_wms_bugs均通过，验证使用合成内存库。此次仓库变更仅为本回执及相关审计/台账Markdown，统一提交推送并按精确目标验收文档CI；产品来源仍为85df6437。代码进度仍是3/5，前三项均有生产启用记录；第四项、第五项未开始。下一次时钟触发及真机等独立受限验收仍按事实单列。
