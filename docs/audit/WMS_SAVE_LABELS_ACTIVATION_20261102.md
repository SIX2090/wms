# 保存按钮名称生产生效记录

2026-11-02，Asia/Shanghai。用户明确授权沿用现有启动方式重启一次WMS，使采购入库和普通领料的按钮名称显示为“保存”。

## 实际发布范围

生产由SYSTEM身份的`WMS-Warehouse`计划任务托管，入口保持为`C:/wms_backups/image_search_release_20261102_094356_r2/launch.cmd current --serve`。后端仍为已封存的`867e369a8bf7227a093374ac185f7bfc186450ab`，界面覆盖层版本由`fae2b0b8fb5caa86`变为`24fb0dc07ebbd6e9`。

本次在该覆盖层加入`app/templates/in_order_add.html`与`app/templates/out_order_add.html`，只修改按钮文字及既有`data-wms-save-complete-label`属性。模板从实际封存后端取出，反向替换后与原文件逐字节相同，`submitForm`及后续代码逐字节保持。原有23个界面覆盖文件的SHA256全部保持；两个完整性清单同步登记新增模板。启动命令、任务身份、后端代码及找图联网模块保持现状。

文案变更对应main上的`7ce3b3658b0c3e8b2e6dbb1ea418aa13901706bd`和`c74e14a6dd0003ec30ef4f96b842cc734aa8df4e`；c74e14a6的[WMS CI](https://github.com/SIX2090/wms/actions/runs/41397709288)及[AI Verification](https://github.com/SIX2090/wms/actions/runs/41397709253)完整成功，Android祖先及输入不变证明通过。本次是现有生产发布层的文案补丁，上述main整体代码并未替换封存后端。

## 重启及核验

- 原覆盖层、清单和任务XML已备份；使用`online_backup.py`对生产SQLite在线备份并通过完整性检查，未恢复数据库。
- 候选发布包预检通过：后端SHA符合原封存清单、全部模板可编译、启动数据库保护有效、没有启动监听器。实际候选模板渲染为“保存”，实际生产工具栏JS执行两个caption代理场景均通过。
- 按现有计划任务停止、启动一次，旧PID`17832`已退出，新PID`15812`于16:38:07启动；16:38:18验收时只有一个`127.0.0.1:8080`监听器，计划任务处于Running，身份仍为SYSTEM。
- 本机及`https://gd2026.top/login`均HTTP 200，均能观察到新界面版本。生产返回的主题CSS和app.js字节与原覆盖层一致，原CSS回退正常，匿名访问物料页仍跳转登录。
- user、material、in_order、out_order、stock_transaction、location_inventory表计数及物料stock合计在重启前后一致。本次未操作生产保存/完成按钮，未改变账号或密码。

已打开的单据页需要重新打开或Ctrl+F5，以载入新的服务端页面。验证未通过时可恢复本次备份的覆盖层和清单，再按同一任务入口启动；数据库不在该回退范围内。

原始证据及回退材料：`C:/wms_backups/save_labels_activation_20261102/`。`evidence/plan.json`、`preflight.log`、`process-before.json`、`process-after.json`、`production-health.json`、`public-health.json`、`business-before.json`、`business-after.json`记录本次检查。`before-inventory.db`为只读在线备份产生的副本。
