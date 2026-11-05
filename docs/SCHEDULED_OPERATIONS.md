# 独立每日备份与进程监护（2026-11-05）

适用：Windows 计划任务托管 WMS，实际入口未调用 `run_server.main()` 时。复用已有 `sqlite_snapshot` 的在线快照、完整性检查和原子发布，不依赖通知调度器，不需要加载 Flask。开发和验收仅使用合成库；生产任务安装、服务切换及生产备份启用另行批准。

## 独立备份

在隔离环境使用明确路径：

```powershell
python tools/run_scheduled_backup.py --source 'C:\wms-lab\synthetic.db' --directory 'C:\wms-lab\daily' --retention-days 30
```

成功退出0，失败退出1并记录日志；参数错误退出2。`AUTO_BACKUP_ENABLED=false` 时不访问源库。省略 `--retention-days` 时沿用进程环境中的 `BACKUP_RETENTION_DAYS`，默认30天。只有成功产生有效快照后才清理过期 `auto_daily_*.db`，手动、维护备份及源库保留。文件名含微秒，连续调用保留各自快照。

`WMS_BACKUP_DIR/.daily-backup-status.json` 保存最近执行状态和最近成功时间，失败保留之前的成功时间及备份。管理页面展示实际成功、失败、超过36小时未成功或无有效记录。记录缺失、损坏、不可读和未来时间不作为成功。文件目录都不可写时，任务非零退出和标准错误日志仍是失败证据。

## Windows 任务预览和安装

工具默认只读预览。以下是**合成环境示例**，`WMS-Lab` 必须是已存在的测试任务：

```powershell
$options = @{
    ServiceTaskName = 'WMS-Lab'
    PythonExe = 'C:\wms-lab\runtime\python.exe'
    SourceRoot = 'C:\wms-lab\release'
    BackupSource = 'C:\wms-lab\synthetic.db'
    BackupDirectory = 'C:\wms-lab\daily'
    StateDirectory = 'C:\wms-lab\new-operations-state'
    BackupTime = '02:00'
    RetentionDays = 30
}
$preview = & tools/configure_scheduled_operations.ps1 @options | ConvertFrom-Json
$preview
# 人工核对准确目标及预览后，才应用同一个定义：
& tools/configure_scheduled_operations.ps1 @options -Apply -ExpectedDefinitionHash $preview.definitionHash
```

要求全新状态目录，已有同名每日备份任务时拒绝覆盖。只支持一个明确的启动动作，以及不需要重新输入密码的原任务登录方式；不会索取或修改账号密码。原任务定义变化时拒绝应用。状态目录ACL限制为当前操作者、SYSTEM及Administrators，原动作与恢复XML可能包含运维参数，应保持此权限。

应用后：原任务启动动作由监护程序包装，原可执行文件、原始Windows参数和工作目录保存在受限动作文件中；原账号、触发器及其余设置保持。执行时限改为无限制，重复启动采用IgnoreNew。另注册 `<原任务名>-DailyBackup`，使用明确源路径、备份目录、时间及保留天数，错过计划后允许补跑；单次备份任务最长15分钟，使用同一任务账号。

安装工具不启动、停止或重启原服务。已经运行的旧进程不会因此立即获得监护，须在批准的维护窗口沿原任务正常切换。每日任务实际时间、目录和保留天数须与管理页面的环境配置核对；独立命令不会加载包含其他密钥的应用 `.env`。最近任务的保留天数与页面配置不同时，页面明确提示。

## 有限重试及单实例

监护程序初次启动失败后最多重试3次，间隔60秒；正常退出不重试。子进程稳定运行5分钟后，下次故障重新计算连续失败预算。`supervisor-status.json` 保存状态，预算耗尽后后续计划任务触发也不再启动子进程。人工排查后用 `--reset-budget` 明确重置；重复监护实例无法取得同一目录的OS锁，不覆盖原实例状态。

监护不导入WMS或打开业务库。WMS子进程必须保留既有数据库运行锁；监护意外中断后，即使旧子进程尚存，第二个WMS也必须由原运行锁拒绝启动。维护停机需先禁用原任务的自动触发，避免原先的重复触发器在维护中再次启动服务。

## 回退与验收

`service-task.before.xml` 留存修改前定义，`applied-plan.json` 留存应用回执及新定义哈希。应用中失败会清理本次创建的备份任务，并仅在当前启动动作仍属于本次修改时恢复原任务，避免覆盖其他操作者的后续动作。失败现场和恢复定义保留。

正式回退前必须核对当前任务仍是该回执中的定义，安排原任务停机窗口，再用原XML恢复；只移除本次明确创建的每日任务。代码回退不恢复数据库，也不能用旧快照覆盖仍在使用的业务数据。

软件验收包括：合成WAL已提交事务入快照、未提交事务不入快照；失败保留旧备份；92张模型表的恢复及留底逐表一致；损坏、无关及占用目标拒绝；实际Windows注册/预览/哈希拒绝/保留运行PID/60秒重试/独立任务执行；真实Chrome状态展示及刷新。生产定时任务、解释器和页面生效仍需单独确认。模板修改：**生产需重启 WMS 服务生效**。
