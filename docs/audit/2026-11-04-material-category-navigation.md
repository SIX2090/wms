# 物料分类切换清除旧搜索词（2026-11-04）

本批仅修复 BUG-2026-11-04-201。输入 `1.25-8` 搜索后，点击分类树任一入口自动清空搜索词、回到第一页，保留库存和启用状态筛选。选定分类后仍可在该分类内搜索，翻页和导出继续保留当前查询条件。

基线 `e69fdb484032a9d33e1fc844e16bc00ffe85fffb` 三工作流已核实；Android `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba` 为目标祖先且工程和工作流无变化。独立 main 副本 `C:/wms_audit/20261104_material_category_fix` 避开 `C:/wms` 现有未提交改动。

验证：旧模板专项6失败、1项对照通过；修后以下组合45通过（16项既有SQLAlchemy弃用警告）。新锁直接跟随服务端渲染的导航地址并检查返回表格和搜索框，覆盖父子分类、两个全部入口、旧页码清除、其他筛选保持及分类内搜索。

```powershell
python -m pytest -q tests/test_material_category_navigation.py tests/test_quick_select_enter_behavior.py tests/test_quick_select_lifecycle_runtime.py tests/test_bug_2026_09_05_004_material_export_category.py tests/test_material_status_toggle.py tests/test_filter_advanced.py tests/test_audit_material_search_normalization.py
```

统一门禁：`verify_wms_bugs.py`、常规规则、A11全量、UTF-8编码及diff检查通过；台账契约和A13测试15通过。`full_smoke_test.py`通过隔离Flask请求桥执行117/117通过，不连接网络；首次内存库因备份页仅支持文件库为116/117，改用全新隔离文件库后117/117。未修改产品或既有断言迁就环境。

验证日志和请求桥保留于 `C:/wms_audit/20261104_category_evidence`。

代码提交 `20c22ba26d7156da3251ea82b28854c3fafbcc5d` 已读取实际push成功输出（e69fdb48..20c22ba2 main -> main），本地和origin/main一致；[WMS CI](https://github.com/SIX2090/wms/actions/runs/41787450464)及[WMS AI Verification](https://github.com/SIX2090/wms/actions/runs/41787450599)精确匹配该SHA且completed/success，WMS CI三个单元测试分片、四个验证分片、静态检查、冒烟及聚合均通过；本批为代码全量验证，docs分流任务按策略跳过。性能工作流亦成功。

[Android APK Build](https://github.com/SIX2090/wms/actions/runs/41740259322)为最新成功构建，完整SHA `3aeaaf1c2199ad03d4b2b2c4002f10277f5615ba`；`git merge-base --is-ancestor`和工程/工作流完整diff均退出0，证明可复用。首次pre-push匿名查询WMS CI时403限流；通过已连接GitHub工具重新取最新main记录并核实同一基线全部成功，仅该次push临时使用现有门禁替代证据开关，随后移除；未读取内部凭据或改动钩子。证据见外部日志。

生产尚未部署，生产需重启 WMS 服务生效；未操作生产业务记录、账号密码或服务。上线需另行授权。本文档验收更新单独提交，只有台账与audit Markdown，无新增业务代码。

## 生产生效确认：2026-11-04 14:58（Asia/Shanghai）

用户随后明确授权“现在应用这项修复并重启 WMS”，本节更新前述未部署快照。

现场为 `C:/wms_backups/audit_repair_0634b9d5_20261104` 的封存后端 `0634b9d5eb752a73aab228ad4869e2628bf51567` 和界面覆盖，启动方式为 WMS-Warehouse 原计划任务。仅替换 `overlay/app/templates/material.html` 分类导航的三个 `search` 参数，与已通过完整CI的20c22ba2三个链接逐一一致；同步overlay-manifest及release-manifest中的SHA256和界面版本。其他界面覆盖、后端源文件、C:/wms未提交工作、任务动作、凭据、自动发送/打印暂停与图片运行模式均保留。

证据目录 `C:/wms_backups/category_navigation_20c22ba2_20261104`：

- `production-online-before.db` 和 `production-stopped-before.db`：SQLite在线备份API完成并integrity_check通过；保留三个原文件及task-before.xml，回退脚本只恢复界面和清单，不自动恢复生产数据库。
- `lab-result.json`：生产同版隔离库验证46个分类链接及3次跟随导航，搜索词/页码清空，状态和内嵌参数保留；隔离数据库摘要不变，schema只读检查通过，自动任务仍暂停。
- `production-preflight.log`：只读生产启动预检通过，未启动监听，不执行数据库迁移/初始化。
- `deployment-result.json`：旧PID3144已退出，新PID2080于14:57:42启动，独占127.0.0.1:8080；HTTP登录200且新界面版本可见，任务启动动作未改。
- `database-before.json` 与 `database-after.json`：逐表行数和行摘要完全相同，integrity_check为ok。未修改任何业务记录或密码。
- `https-login.html`：curl将gd2026.top解析至本机127.0.0.1的443端口，HTTPS登录200且包含 `24fb0dc07ebbd6e9-cat20c22ba2`。仅证明本机Nginx HTTPS链路，不扩大为外网可达证明。

计划任务保持Running，轮询触发的LastTaskResult现场为2147946720（重复实例策略IgnoreNew），保留该真实值，不以其断言零退出；服务有效性由单一新进程、端口、HTTP/HTTPS200和新界面版本共同确认。
